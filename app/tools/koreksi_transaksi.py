"""Tool `koreksi_transaksi` — membetulkan catatan yang sudah tersimpan.

Tanpa ini, setiap salah catat jadi permanen — dan pengguna yang tidak bisa
membetulkan kesalahannya akan berhenti percaya pada seluruh angkanya, bukan
cuma pada baris yang salah.

Sasaran default = **catatan terakhir** yang masih berlaku. Itu yang paling
sering dimaksud ("eh salah, harusnya 57rb"), dan konfirmasinya selalu menyebut
baris mana yang berubah — jadi kalau sasarannya meleset, pengguna langsung
melihatnya, bukan menemukannya sebulan kemudian di laporan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.kontrak import AdapterLLM, Gagal
from app.llm.penjaga import periksa_nominal
from app.llm.skema import Koreksi, instruksi_koreksi
from app.models import Transaction
from app.services.catat import (
    ringkas_transaksi,
    terapkan_koreksi,
    transaksi_terakhir,
)
from app.tools.catat_transaksi import Klarifikasi

__all__ = ["Terkoreksi", "koreksi_transaksi"]


@dataclass
class Terkoreksi:
    konfirmasi: str
    id_dibatalkan: int | None = None
    id_pengganti: int | None = None
    yang_kurang: list[str] = field(default_factory=list)


def koreksi_transaksi(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
    transaksi_id: int | None = None,
) -> Terkoreksi | Klarifikasi:
    """Betulkan satu catatan. Default sasaran: catatan terakhir."""
    lama = (
        _milik(session, business_id, transaksi_id)
        if transaksi_id is not None
        else transaksi_terakhir(session, business_id)
    )
    if lama is None:
        return Klarifikasi(
            pertanyaan="Belum ada catatan yang bisa dibetulkan.",
        )

    hasil = adapter.ekstrak(
        instruksi_koreksi(hari_ini, ringkas_transaksi(lama)), teks, Koreksi
    )
    if isinstance(hasil, Gagal):
        return Klarifikasi(
            pertanyaan=(
                f"Yang mau dibetulkan ini ya?\n• {ringkas_transaksi(lama)}\n"
                "Bagian mana yang keliru — nominalnya, tanggalnya, "
                "atau memang mau dihapus?"
            ),
            yang_kurang=hasil.yang_kurang,
        )

    koreksi = hasil.data

    # Penjaga aturan #1 berlaku di sini juga: "harusnya 3 kotak 20rb" bisa
    # membuat model mengalikan, dan angka karangan lewat jalur koreksi sama
    # merusaknya dengan lewat jalur pencatatan.
    if koreksi.nominal is not None:
        qty = koreksi.qty if koreksi.qty is not None else lama.qty
        if alasan := periksa_nominal(teks, koreksi.nominal, qty):
            return Klarifikasi(pertanyaan=_tanya_total(alasan), yang_kurang=["nominal"])

    terap = terapkan_koreksi(session, business_id, lama, koreksi, teks)
    return Terkoreksi(
        konfirmasi=terap.konfirmasi,
        id_dibatalkan=terap.dibatalkan.id if terap.dibatalkan else None,
        id_pengganti=terap.pengganti.id if terap.pengganti else None,
    )


def _milik(session: Session, business_id: int, transaksi_id: int) -> Transaction | None:
    """Ambil transaksi HANYA bila milik usaha ini (aturan #6).

    Difilter di query, bukan diperiksa setelah diambil — supaya tidak ada jalan
    baris usaha lain sempat tersentuh.
    """
    return session.scalars(
        select(Transaction).where(
            Transaction.id == transaksi_id,
            Transaction.business_id == business_id,
            Transaction.dibatalkan_pada.is_(None),
        )
    ).first()


def _tanya_total(_alasan: str) -> str:
    """Pertanyaan balik dari template kode — `_alasan` teknis, bukan untuk layar."""
    return "Totalnya jadi berapa ya? Sebut angka yang benar-benar dibayar."

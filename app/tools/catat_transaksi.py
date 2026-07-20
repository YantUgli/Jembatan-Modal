"""Tool `catat_transaksi` — kalimat pemilik warung → transaksi tersimpan.

Aksi bervolume tertinggi di produk ini. Alurnya sengaja pendek:

    teks → ekstrak_transaksi() [penjaga aturan #1 di sini] → simpan_transaksi()

Dua keluaran saja, dan keduanya jujur:

    Tercatat    — tersimpan, dengan konfirmasi yang bisa dibaca ulang.
    Klarifikasi — TIDAK tersimpan, plus pertanyaan balik yang spesifik.

`Klarifikasi` bukan jalur kegagalan; ia jalur normal. Kalimat warung memang
sering kurang satu keping ("keluar 50rb" — buat apa?), dan menebaknya berarti
menaruh angka di kategori yang salah lalu memburukkan setiap laporan di atasnya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.llm.ekstraksi import ekstrak_transaksi
from app.llm.kontrak import AdapterLLM, Gagal
from app.models import SumberInput
from app.services.catat import simpan_transaksi

__all__ = ["Klarifikasi", "Tercatat", "catat_transaksi"]


@dataclass
class Tercatat:
    konfirmasi: str
    ids: list[int] = field(default_factory=list)


@dataclass
class Klarifikasi:
    pertanyaan: str
    yang_kurang: list[str] = field(default_factory=list)


# Pertanyaan balik dirender dari template kode — alasan yang sama dengan
# konfirmasi: ini terjadi berkali-kali sehari, dan memanggil LLM untuk menyusun
# satu kalimat tanya adalah biaya yang berlipat tanpa menambah apa pun.
_PERTANYAAN = {
    "nominal": "Berapa nominalnya?",
    "tanggal": "Itu tanggal berapa ya?",
    "jenis": (
        "Uangnya buat apa ya — belanja barang dagangan, biaya warung "
        "(listrik, gas, plastik), atau keperluan pribadi?"
    ),
    "produk": "Barangnya apa?",
}

_PEMBUKA = "Boleh dilengkapi dulu?"

# Urutan bertanya ditentukan KODE, bukan urutan `yang_kurang` dari model.
# Terpantau live: "hari ini rame banget" membuat model mengembalikan
# ["jenis", "nominal"], sehingga pertanyaannya dibuka dengan "uangnya buat apa"
# padahal tidak ada uang yang disebut sama sekali. Nominal dulu — itu keping
# yang membuat sisanya masuk akal untuk ditanyakan.
_URUTAN = ("nominal", "jenis", "tanggal", "produk")


def catat_transaksi(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
    sumber: SumberInput = SumberInput.chat,
) -> Tercatat | Klarifikasi:
    """Catat transaksi dari satu kalimat. Tidak pernah menyimpan sebagian."""
    hasil = ekstrak_transaksi(adapter, teks, hari_ini)
    if isinstance(hasil, Gagal):
        return Klarifikasi(pertanyaan=_tanya(hasil), yang_kurang=hasil.yang_kurang)

    if not hasil.data.baris:
        return Klarifikasi(
            pertanyaan="Belum ketemu catatan uangnya. Coba sebut nominalnya ya.",
            yang_kurang=["nominal"],
        )

    simpan = simpan_transaksi(session, business_id, hasil.data.baris, teks, sumber)
    return Tercatat(
        konfirmasi=simpan.konfirmasi,
        ids=[t.id for t in simpan.tersimpan],
    )


def _tanya(gagal: Gagal) -> str:
    """Pertanyaan balik yang spesifik, dari kode.

    `gagal.alasan` sengaja **tidak** ditampilkan apa adanya: teks itu datang
    dari model dan dipengaruhi kalimat pengguna, jadi ia masukan tak tepercaya
    (aturan #6) — dan bunyinya pun teknis, bukan bahasa warung.
    """
    kurang = set(gagal.yang_kurang)
    pertanyaan = [_PERTANYAAN[k] for k in _URUTAN if k in kurang]
    if not pertanyaan:
        return "Maaf, belum tertangkap maksudnya. Boleh diulang lebih lengkap?"
    return f"{_PEMBUKA} " + " ".join(pertanyaan)

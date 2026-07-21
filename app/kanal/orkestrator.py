"""Orchestrator deterministik tipis — memetakan tool/service ke kartu kontrak.

Slice 1 sengaja **tanpa** loop function-calling LLM: adapter yang ada hari ini
adalah permukaan dua-verba (`ekstrak`/`narasikan`), dan jalur bervolume-tertinggi
(pencatatan) tidak membutuhkannya — `catat_transaksi` sudah memanggil ekstraksi
di dalamnya. Di sini kode kita yang memilih tool, lalu membungkus hasilnya jadi
`PesanKeluar`. Router multi-tool berbasis LLM menyusul di slice berikutnya.

Isolasi tenant (aturan #6): tiap fungsi menerima `business_id` dan setiap query
di sini difilter olehnya — input pengguna dianggap tak tepercaya.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.kontrak import (
    BarisKonfirmasi,
    KartuKlarifikasi,
    KartuKonfirmasi,
    KartuSapaan,
    KartuUntung,
    PesanKeluar,
    PilihanKategori,
)
from app.llm.kontrak import AdapterLLM
from app.llm.skema import AksiKoreksi, Koreksi
from app.models import Business, JenisTransaksi, Transaction
from app.services.angka import _dec, _uang, rupiah
from app.services.catat import terapkan_koreksi
from app.tools import Klarifikasi, Tercatat, catat_transaksi

__all__ = [
    "tangani_pesan",
    "koreksi_kategori",
    "sapaan",
    "kartu_untung_stub",
]

# Badge jenis pada kartu (bahasa warung, bukan istilah akuntansi).
_JENIS_LABEL = {
    JenisTransaksi.pemasukan: "Uang masuk",
    JenisTransaksi.pengeluaran: "Belanja",
    JenisTransaksi.operasional: "Biaya",
    JenisTransaksi.prive: "Dipakai pribadi",
}

# Empat kategori untuk chip koreksi, dalam urutan tetap yang ditentukan kode.
_KATEGORI: list[tuple[JenisTransaksi, str]] = [
    (JenisTransaksi.pemasukan, "Pemasukan"),
    (JenisTransaksi.pengeluaran, "Pengeluaran"),
    (JenisTransaksi.operasional, "Operasional"),
    (JenisTransaksi.prive, "Prive"),
]


# ── Pencatatan ───────────────────────────────────────────────────────────────


def tangani_pesan(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
) -> PesanKeluar:
    """Satu kalimat pengguna → kartu. Jalur pencatatan (Pilar 1)."""
    hasil = catat_transaksi(session, adapter, business_id, teks, hari_ini)
    if isinstance(hasil, Klarifikasi):
        return PesanKeluar(
            [KartuKlarifikasi(pertanyaan=hasil.pertanyaan, yang_kurang=hasil.yang_kurang)]
        )
    return PesanKeluar([_kartu_konfirmasi(session, business_id, hasil)])


def koreksi_kategori(
    session: Session,
    business_id: int,
    transaksi_id: int,
    jenis: JenisTransaksi,
) -> PesanKeluar:
    """Ketuk chip kategori → betulkan jenis transaksi.

    Aksi terstruktur (bukan bahasa natural), jadi kita memanggil service
    `terapkan_koreksi` langsung tanpa melibatkan LLM — jenis sasarannya sudah
    pasti. Tetap append-only: baris lama ditandai batal, penggantinya baris baru
    (keputusan.md 2026-07-20).
    """
    lama = _ambil_milik(session, business_id, transaksi_id)
    if lama is None:
        return PesanKeluar(
            [KartuKlarifikasi(pertanyaan="Catatan itu tidak ketemu — mungkin sudah dibetulkan.")]
        )
    if lama.jenis is jenis:  # tidak berubah → cukup gambar ulang kartunya
        return PesanKeluar(
            [
                KartuKonfirmasi(
                    baris=[_baris(lama)],
                    ids=[lama.id],
                    konfirmasi="Kategorinya memang sudah itu, Bu.",
                )
            ]
        )

    terap = terapkan_koreksi(
        session,
        business_id,
        lama,
        Koreksi(aksi=AksiKoreksi.ubah, jenis=jenis),
        raw_text="(ketuk chip kategori)",
    )
    pengganti = terap.pengganti
    assert pengganti is not None  # aksi `ubah` selalu menghasilkan pengganti
    return PesanKeluar(
        [
            KartuKonfirmasi(
                baris=[_baris(pengganti)],
                ids=[pengganti.id],
                konfirmasi=terap.konfirmasi,
            )
        ]
    )


# ── Sapaan & stub ────────────────────────────────────────────────────────────


def sapaan(business: Business, salam: str = "Selamat datang") -> PesanKeluar:
    """Kartu pembuka, diturunkan dari data usaha (bukan hardcode di UI)."""
    sub = " · ".join(x for x in (business.jenis_usaha, business.lokasi) if x)
    return PesanKeluar(
        [
            KartuSapaan(
                nama_usaha=business.nama_usaha,
                sub=sub,
                salam=salam,
                ajakan=(
                    "Ada yang laku hari ini? Ceritakan saja seperti biasa — nanti saya "
                    "bantu catat dan hitung untungnya."
                ),
                catatan_jujur=(
                    "Angka Ibu tidak pernah saya karang. Kalau modalnya belum ketahuan, "
                    "saya bilang apa adanya — belum tahu."
                ),
            )
        ]
    )


def kartu_untung_stub() -> PesanKeluar:
    """Kartu untung/HPP sebelum tool HPP di-wire.

    Mengaku "belum tersambung" alih-alih mengarang angka (aturan #1/#2). Service
    HPP (`app/services/hpp.py`) sudah matang; menyambungkannya adalah slice
    berikutnya, bukan sekarang.
    """
    return PesanKeluar(
        [
            KartuUntung(
                pesan=(
                    "Hitung untung per porsi belum saya sambungkan di sini. Modal bahannya "
                    "sudah dihitung mesin secara pasti — saya tampilkan begitu jalurnya siap, "
                    "supaya angkanya benar, bukan kira-kira."
                ),
            )
        ]
    )


# ── Pembangun kartu ──────────────────────────────────────────────────────────


def _kartu_konfirmasi(
    session: Session, business_id: int, hasil: Tercatat
) -> KartuKonfirmasi:
    """Baca-balik transaksi yang baru dibuat → isi baris terstruktur.

    Dibaca ulang dari DB (difilter `business_id`) supaya angka di kartu berasal
    dari baris tersimpan, bukan dari teks pengguna.
    """
    rows = session.scalars(
        select(Transaction).where(
            Transaction.id.in_(hasil.ids),
            Transaction.business_id == business_id,
        )
    ).all()
    by_id = {r.id: r for r in rows}
    baris = [_baris(by_id[i]) for i in hasil.ids if i in by_id]
    return KartuKonfirmasi(baris=baris, ids=hasil.ids, konfirmasi=hasil.konfirmasi)


def _baris(t: Transaction) -> BarisKonfirmasi:
    return BarisKonfirmasi(
        jenis=t.jenis.value,
        jenis_label=_JENIS_LABEL[t.jenis],
        nominal_tampil=rupiah(_dec(t.nominal)),
        nominal=str(_uang(_dec(t.nominal))),
        produk=t.deskripsi,
        qty_tampil=_qty_tampil(t),
        transaksi_id=t.id,
        kategori_pilihan=[
            PilihanKategori(nilai=j.value, label=label, aktif=(t.jenis is j))
            for j, label in _KATEGORI
        ],
    )


def _qty_tampil(t: Transaction) -> str | None:
    """'5 kotak' dari qty+satuan; None bila takaran tak dicatat."""
    if t.qty is None:
        return None
    d = _dec(t.qty).normalize()
    if d == d.to_integral_value():
        d = d.to_integral_value()
    angka = f"{d:f}"
    return " ".join(x for x in (angka, t.satuan) if x)


def _ambil_milik(
    session: Session, business_id: int, transaksi_id: int
) -> Transaction | None:
    """Ambil transaksi HANYA bila milik usaha ini & masih berlaku (aturan #6).

    Difilter di query, bukan diperiksa setelah diambil.
    """
    return session.scalars(
        select(Transaction).where(
            Transaction.id == transaksi_id,
            Transaction.business_id == business_id,
            Transaction.dibatalkan_pada.is_(None),
        )
    ).first()

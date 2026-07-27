"""`lihat_transaksi_terakhir` — jalur baca daftar catatan lewat chat.

Menguji router → service baca → kartu riwayat + koreksi kategori dari daftar,
memakai `AdapterPalsu` terskrip (tanpa LLM nyata). Jalur baca deterministik:
hanya `pilih_aksi` yang memanggil adapter; penyusunan daftar murni query.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.kontrak import TipeKartu
from app.kanal.orkestrator import koreksi_kategori, tangani_pesan
from app.llm.palsu import AdapterPalsu
from app.llm.skema import AksiRouter
from app.models import Business, JenisTransaksi, Transaction
from app.services.catat import daftar_transaksi_periode, daftar_transaksi_terakhir
from app.tools.pilih_aksi import pilih_aksi
from tests.conftest import buat_transaksi

TGL = date(2026, 7, 24)


def _catat(session, business, jenis, nominal, tanggal=TGL, **kw) -> Transaction:
    return buat_transaksi(session, business, jenis, Decimal(nominal), tanggal, **kw)


# ── Router ──────────────────────────────────────────────────────────────────


def test_router_kalimat_lihat_ke_lihat_transaksi(session: Session, business: Business):
    teks = "coba lihat catatan terakhir"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "lihat_transaksi"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.lihat_transaksi


def test_router_rekap_tetap_tanya_keuangan(session: Session, business: Business):
    """Disambiguasi: minta rekap angka gabungan ≠ minta daftar entri mentah."""
    teks = "rekap untung bulan ini dong"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "tanya_keuangan"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.tanya_keuangan


# ── Service baca ────────────────────────────────────────────────────────────


def test_daftar_terbaru_dulu_dan_batas(session: Session, business: Business):
    # Tujuh transaksi, id menaik → daftar mengembalikan 5 terakhir, terbaru dulu.
    dibuat = [_catat(session, business, JenisTransaksi.pemasukan, 1000 * (i + 1)) for i in range(7)]
    rows = daftar_transaksi_terakhir(session, business.id, batas=5)

    assert [r.id for r in rows] == [t.id for t in reversed(dibuat)][:5]


def test_daftar_kecualikan_dibatalkan(session: Session, business: Business):
    hidup = _catat(session, business, JenisTransaksi.pemasukan, 75000)
    batal = _catat(session, business, JenisTransaksi.pengeluaran, 38000)
    batal.dibatalkan_pada = datetime(2026, 7, 24, 10, 0, 0)
    session.flush()

    rows = daftar_transaksi_terakhir(session, business.id)
    ids = {r.id for r in rows}
    assert hidup.id in ids
    assert batal.id not in ids  # baris dibatalkan tak pernah tampil


def test_daftar_isolasi_tenant(session: Session, business: Business, tetangga: Business):
    milik = _catat(session, business, JenisTransaksi.pemasukan, 75000)
    _catat(session, tetangga, JenisTransaksi.pemasukan, 999000)  # tetangga

    rows = daftar_transaksi_terakhir(session, business.id)
    assert [r.id for r in rows] == [milik.id]  # buku tetangga tak bocor (aturan #6)


# ── Service baca berperiode ─────────────────────────────────────────────────


def test_periode_inklusif_di_kedua_ujung(session: Session, business: Business):
    """Rentang sama persis dengan `hitung_laba_periode` & `cakupan_hpp` —
    kalau tidak, daftar dan angka rekap bisa berbeda isi untuk periode yang sama.
    """
    sebelum = _catat(session, business, JenisTransaksi.pemasukan, 1000, date(2026, 5, 31))
    awal = _catat(session, business, JenisTransaksi.pemasukan, 2000, date(2026, 6, 1))
    akhir = _catat(session, business, JenisTransaksi.pemasukan, 3000, date(2026, 6, 30))
    sesudah = _catat(session, business, JenisTransaksi.pemasukan, 4000, date(2026, 7, 1))

    rows = daftar_transaksi_periode(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    ids = {r.id for r in rows}

    assert {awal.id, akhir.id} <= ids
    assert sebelum.id not in ids
    assert sesudah.id not in ids


def test_periode_kecualikan_dibatalkan(session: Session, business: Business):
    hidup = _catat(session, business, JenisTransaksi.pemasukan, 75000, date(2026, 6, 10))
    batal = _catat(session, business, JenisTransaksi.pengeluaran, 38000, date(2026, 6, 11))
    batal.dibatalkan_pada = datetime(2026, 6, 12, 10, 0, 0)
    session.flush()

    rows = daftar_transaksi_periode(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert [r.id for r in rows] == [hidup.id]


def test_periode_isolasi_tenant(session: Session, business: Business, tetangga: Business):
    milik = _catat(session, business, JenisTransaksi.pemasukan, 75000, date(2026, 6, 10))
    _catat(session, tetangga, JenisTransaksi.pemasukan, 999000, date(2026, 6, 10))

    rows = daftar_transaksi_periode(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert [r.id for r in rows] == [milik.id]  # aturan #6 ditegakkan di query


# ── Orchestrator end-to-end ─────────────────────────────────────────────────


def test_orkestrator_kartu_riwayat_lengkap(session: Session, business: Business):
    _catat(
        session, business, JenisTransaksi.pemasukan, 75000,
        product=None, qty=Decimal("5"), satuan="kotak",
    )
    _catat(session, business, JenisTransaksi.operasional, 20000, kategori_detail="gas")

    teks = "lihat catatan terakhir"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "lihat_transaksi"}})
    pesan = tangani_pesan(session, adapter, business.id, teks, TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.riwayat.value
    assert len(kartu.baris) == 2
    # Terbaru dulu: operasional (id lebih besar) di atas.
    assert kartu.baris[0].jenis == JenisTransaksi.operasional.value
    assert kartu.baris[1].jenis == JenisTransaksi.pemasukan.value
    # Tiap baris bisa dibetulkan di tempat: bawa id + chip + tanggal.
    for b in kartu.baris:
        assert b.transaksi_id is not None
        assert len(b.kategori_pilihan) == 4
        assert b.tanggal_tampil == "24 Jul"


def test_orkestrator_riwayat_kosong_jujur(session: Session, business: Business):
    """Aturan #2: tak ada transaksi → pesan jujur, bukan baris karangan."""
    teks = "lihat catatan terakhir"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "lihat_transaksi"}})
    pesan = tangani_pesan(session, adapter, business.id, teks, TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.riwayat.value
    assert kartu.baris == []
    assert "belum ada catatan" in kartu.pesan.lower()


# ── Koreksi kategori dari daftar ─────────────────────────────────────────────


def test_koreksi_kategori_dari_baris_riwayat(session: Session, business: Business):
    """Baris di daftar bisa dibetulkan lewat jalur koreksi_kategori yang ada."""
    salah = _catat(session, business, JenisTransaksi.pengeluaran, 20000, kategori_detail="gas")

    pesan = koreksi_kategori(session, business.id, salah.id, JenisTransaksi.operasional)
    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.konfirmasi.value
    assert kartu.baris[0].jenis == JenisTransaksi.operasional.value

    # Append-only: baris lama dibatalkan, daftar kini menampilkan penggantinya.
    rows = daftar_transaksi_terakhir(session, business.id)
    assert [r.jenis for r in rows] == [JenisTransaksi.operasional]


def test_koreksi_lintas_tenant_ditolak(session: Session, business: Business, tetangga: Business):
    """Aturan #6: id milik usaha lain → tak ditemukan, tak ada penulisan."""
    milik = _catat(session, business, JenisTransaksi.pengeluaran, 20000)

    pesan = koreksi_kategori(session, tetangga.id, milik.id, JenisTransaksi.operasional)
    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value

    # Tak ada baris baru tertulis untuk tetangga; milik `business` utuh.
    tetangga_rows = session.scalars(
        select(Transaction).where(Transaction.business_id == tetangga.id)
    ).all()
    assert tetangga_rows == []
    assert session.get(Transaction, milik.id).dibatalkan_pada is None

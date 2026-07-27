"""Service laporan — angka & bentuk periode. Tanpa render, tanpa LLM.

Yang dijaga di sini bukan cuma "angkanya benar", tapi tiga sifat yang mudah
hilang saat kode disunting nanti:

1. **Bulan bolong tetap tampil** (aturan #2). Melewati bulan tanpa catatan akan
   membuat periode terlihat lebih rapat daripada kenyataannya.
2. **Total dihitung sekali untuk seluruh rentang**, bukan menjumlahkan hasil per
   bulan — dua jalan menuju angka yang sama adalah dua jalan untuk berbeda.
3. **Arus kas memasukkan prive, laba bersih tidak.** Keduanya benar; menyamakan
   salah satu ke yang lain merusak arti keduanya.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Business, JenisTransaksi
from app.models.base import JenisProduk
from app.services.laporan import ringkas_laporan
from tests.conftest import buat_produk, buat_transaksi

HARI_INI = date(2026, 7, 26)


def _susun(session: Session, business: Business) -> None:
    """Mei & Juli ada catatan, **Juni sengaja kosong** (uji bolong)."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 5, 4))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 120_000, date(2026, 5, 5))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 800_000, date(2026, 7, 2))
    buat_transaksi(
        session, business, JenisTransaksi.operasional, 50_000, date(2026, 7, 3),
        kategori_detail="gas",
    )
    buat_transaksi(session, business, JenisTransaksi.prive, 100_000, date(2026, 7, 4))


def test_tiga_bulan_kalender_termasuk_bulan_berjalan(session: Session, business: Business):
    _susun(session, business)
    r = ringkas_laporan(session, business, HARI_INI)

    assert [b.label for b in r.bulan] == ["Mei 2026", "Jun 2026", "Jul 2026"]
    assert r.mulai == date(2026, 5, 1)
    # Bulan berjalan ditutup di hari ini — laporan tak pernah menyiratkan punya
    # data untuk hari yang belum terjadi.
    assert r.selesai == HARI_INI
    assert [b.penuh for b in r.bulan] == [True, True, False]


def test_bulan_tanpa_catatan_tampil_sebagai_nol_bertanda(session: Session, business: Business):
    _susun(session, business)
    r = ringkas_laporan(session, business, HARI_INI)

    juni = r.bulan[1]
    assert juni.hari_tercatat == 0
    assert juni.laba.omzet == Decimal("0.00")
    assert juni.laba.laba_bersih == Decimal("0.00")
    # Barisnya ADA — bukan dilewati diam-diam.
    assert len(r.bulan) == 3
    assert any("tanpa catatan" in c for c in r.catatan)


def test_hari_tercatat_menghitung_tanggal_berbeda(session: Session, business: Business):
    # Dua transaksi di tanggal yang sama = satu hari tercatat, bukan dua.
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 10_000, date(2026, 7, 10))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 20_000, date(2026, 7, 10))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 30_000, date(2026, 7, 11))
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.bulan[-1].hari_tercatat == 2
    assert r.fakta.hari_tercatat == 2


def test_total_periode_bukan_penjumlahan_per_bulan(session: Session, business: Business):
    _susun(session, business)
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.total.omzet == Decimal("1300000.00")  # 500rb + 800rb
    assert r.total.belanja == Decimal("120000.00")
    assert r.total.operasional == Decimal("50000.00")
    assert r.total.laba_bersih == Decimal("1130000.00")
    # Prive tidak pernah jadi biaya usaha (aturan #9).
    assert r.total.prive == Decimal("100000.00")


def test_arus_kas_memasukkan_prive_laba_bersih_tidak(session: Session, business: Business):
    _susun(session, business)
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.arus_kas.uang_masuk == r.total.omzet
    assert r.arus_kas.prive == Decimal("100000.00")
    # 1.300.000 − (170.000 biaya + 100.000 prive)
    assert r.arus_kas.uang_keluar == Decimal("270000.00")
    assert r.arus_kas.sisa == Decimal("1030000.00")
    # Bedanya dengan laba bersih tepat sebesar prive — itu inti dua angka ini.
    assert r.total.laba_bersih - r.arus_kas.sisa == r.total.prive


def test_bulan_berturut_terputus_oleh_bulan_kosong(session: Session, business: Business):
    _susun(session, business)  # Juni kosong
    r = ringkas_laporan(session, business, HARI_INI)
    assert r.fakta.bulan_berturut == 1  # cuma Juli
    assert r.fakta.bulan_bercatatan == 2


def test_bulan_berturut_boleh_melampaui_periode_laporan(session: Session, business: Business):
    # Catatan sejak Februari, tanpa bolong → rentetannya 6, walau laporannya 3 bulan.
    for bulan in (2, 3, 4, 5, 6, 7):
        buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, date(2026, bulan, 8))
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.fakta.bulan_berturut == 6
    assert len(r.bulan) == 3  # periodenya tetap 3 bulan


def test_bulan_terakhir_tanpa_catatan_membuat_rentetan_nol(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, date(2026, 5, 8))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, date(2026, 6, 8))
    r = ringkas_laporan(session, business, HARI_INI)
    # Yang ditanya "sampai sekarang" — Juli kosong, jadi nol; bukan diambil dari Juni.
    assert r.fakta.bulan_berturut == 0


def test_periode_kosong_sama_sekali(session: Session, business: Business):
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.total.omzet == Decimal("0.00")
    assert r.total.laba_bersih == Decimal("0.00")
    assert r.fakta.bulan_bercatatan == 0
    assert r.fakta.omzet_total == Decimal("0.00")
    # Laba nol → rasio prive tak dapat dihitung; jangan dipaksa jadi 0%.
    assert r.fakta.rasio_prive_persen is None
    assert r.cakupan.persen == Decimal("0.0")


def test_laba_negatif_dilaporkan_apa_adanya(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, date(2026, 7, 5))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 400_000, date(2026, 7, 6))
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.total.laba_bersih == Decimal("-300000.00")
    assert r.total.untung is False
    assert r.fakta.rasio_prive_persen is None  # laba ≤ 0 → tidak dihitung
    assert any("lebih besar" in c for c in r.catatan)


def test_periode_eksplisit_dipotong_per_bulan(session: Session, business: Business):
    _susun(session, business)
    r = ringkas_laporan(
        session, business, HARI_INI, mulai=date(2026, 5, 15), selesai=date(2026, 6, 10)
    )

    assert [(b.mulai, b.selesai) for b in r.bulan] == [
        (date(2026, 5, 15), date(2026, 5, 31)),
        (date(2026, 6, 1), date(2026, 6, 10)),
    ]
    # Dua-duanya terpotong rentang → tak ada yang disebut bulan penuh.
    assert [b.penuh for b in r.bulan] == [False, False]
    # 4 Mei di luar rentang → tidak terhitung.
    assert r.total.omzet == Decimal("0.00")


def test_cakupan_hpp_ikut_per_bulan(session: Session, business: Business):
    produk = buat_produk(
        session, business, "nugget", JenisProduk.reseller, satuan_beli="pak", satuan_jual="pak"
    )
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, 200_000, date(2026, 7, 1),
        product=produk, qty=10, satuan="pak",
    )
    buat_transaksi(
        session, business, JenisTransaksi.pemasukan, 300_000, date(2026, 7, 2),
        product=produk, qty=10, satuan="pak",
    )
    r = ringkas_laporan(session, business, HARI_INI)

    assert r.bulan[-1].cakupan.persen == Decimal("100.0")
    assert r.cakupan.persen == Decimal("100.0")
    assert r.fakta.cakupan_hpp_persen == Decimal("100.0")


def test_isolasi_tenant(session: Session, business: Business, tetangga: Business):
    _susun(session, business)
    buat_transaksi(session, tetangga, JenisTransaksi.pemasukan, 9_000_000, date(2026, 7, 7))

    r = ringkas_laporan(session, business, HARI_INI)
    assert r.total.omzet == Decimal("1300000.00")  # buku tetangga tak ikut terbaca

    r_tetangga = ringkas_laporan(session, tetangga, HARI_INI)
    assert r_tetangga.total.omzet == Decimal("9000000.00")
    assert r_tetangga.identitas.nama_usaha == "Warung Tetangga"


def test_identitas_dari_db_bukan_dari_pemanggil(session: Session, business: Business):
    r = ringkas_laporan(session, business, HARI_INI)
    assert r.identitas.nama_usaha == "Warung Uji"
    assert r.identitas.nama_pemilik == "Uji"
    assert r.identitas.no_hp == "0810000TEST"

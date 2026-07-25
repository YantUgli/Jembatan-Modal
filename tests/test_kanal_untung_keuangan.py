"""Kartu untung (HPP per porsi) & kartu keuangan (untung usaha periode).

Menjaga jantung H1 di sisi tampilan:
- **Dua angka tetap terpisah** (aturan #9): kartu untung = "laba kotor dari
  bahan per porsi"; kartu keuangan = "untung usaha" (laba bersih). Diuji lewat
  kosakata yang muncul/tak-muncul di tiap kartu.
- **Data kurang tampil jujur** (aturan #2): produk tanpa resep → `diketahui`
  False & angka `None`, BUKAN "Rp0".
- **Cakupan HPP wajib tampil**; **isolasi business_id** (aturan #6).
- Angka **dihitung ulang independen** di test dari nilai mentah yang dimasukkan,
  bukan disamakan dengan keluaran service (bukan echo).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.kanal import VERSI_KONTRAK, kartu_keuangan, kartu_untung
from app.kanal.kontrak import KartuKeuangan, KartuUntung
from app.models import Business, JenisTransaksi
from app.models.base import JenisProduk
from tests.conftest import (
    buat_material,
    buat_produk,
    buat_resep,
    buat_transaksi,
    set_harga,
)

HARI_INI = date(2026, 7, 22)
MULAI = date(2026, 7, 1)  # bulan berjalan
SELESAI = HARI_INI


def _susun_skenario(session: Session, biz: Business) -> None:
    """Warung produksi+reseller dengan sebagian data sengaja kurang.

    Nilai dipilih bulat supaya bisa dihitung ulang di kepala:
    - risol (produksi): 1 kg tepung @12.000 ÷ yield 20 → HPP 600, jual 1.000 → laba 400
    - kroket (produksi): TANPA resep → HPP belum diketahui
    - nugget (reseller): beli 40.000/2 pak → HPP 20.000, jual 25.000 → laba 5.000
    """
    # risol — produksi, resep lengkap
    tepung = buat_material(session, biz, "tepung", satuan="kg")
    set_harga(session, tepung, Decimal("12000"), date(2026, 7, 1), satuan="kg")
    risol = buat_produk(session, biz, "risol", JenisProduk.produksi, harga_jual=Decimal("1000"))
    buat_resep(session, risol, 20, [(tepung, 1, "kg")], yield_satuan="unit")

    # kroket — produksi TANPA resep (degradasi jujur)
    buat_produk(session, biz, "kroket", JenisProduk.produksi, harga_jual=Decimal("1500"))

    # nugget — reseller, ada pembelian
    nugget = buat_produk(session, biz, "nugget", JenisProduk.reseller, harga_jual=Decimal("25000"))
    buat_transaksi(
        session, biz, JenisTransaksi.pengeluaran, Decimal("40000"), date(2026, 7, 5),
        kategori_detail="nugget", product=nugget, qty=2, satuan="pak",
    )

    # penjualan (omzet + cakupan). Satu penjualan tanpa produk → cakupan < 100%.
    buat_transaksi(
        session, biz, JenisTransaksi.pemasukan, Decimal("75000"), date(2026, 7, 10),
        product=risol, qty=5, satuan="kotak",
    )
    buat_transaksi(
        session, biz, JenisTransaksi.pemasukan, Decimal("50000"), date(2026, 7, 12),
        product=nugget, qty=2, satuan="pak",
    )
    buat_transaksi(  # titipan kue — tak terkenali produk
        session, biz, JenisTransaksi.pemasukan, Decimal("30000"), date(2026, 7, 11),
    )

    # biaya operasional + prive
    buat_transaksi(
        session, biz, JenisTransaksi.operasional, Decimal("20000"), date(2026, 7, 8),
        kategori_detail="gas",
    )
    buat_transaksi(
        session, biz, JenisTransaksi.operasional, Decimal("15000"), date(2026, 7, 9),
        kategori_detail="listrik",
    )
    buat_transaksi(
        session, biz, JenisTransaksi.prive, Decimal("20000"), date(2026, 7, 15),
    )


# ── Kartu untung ─────────────────────────────────────────────────────────────


def test_untung_per_produk_angka_dari_db(session: Session, business: Business):
    _susun_skenario(session, business)
    keluar = kartu_untung(session, business.id, MULAI, SELESAI)

    assert keluar.versi == VERSI_KONTRAK == 3
    kartu = keluar.kartu[0]
    assert isinstance(kartu, KartuUntung)
    per = {b.nama: b for b in kartu.produk}
    assert set(per) == {"risol", "kroket", "nugget"}

    # risol: HPP 12.000/20 = 600, laba 1.000 − 600 = 400 (dihitung ulang di sini)
    risol = per["risol"]
    assert risol.diketahui is True
    assert risol.hpp_tampil == "Rp600"
    assert risol.laba_kotor_tampil == "Rp400"
    assert risol.harga_jual_tampil == "Rp1.000"

    # nugget reseller: HPP 40.000/2 = 20.000, laba 25.000 − 20.000 = 5.000
    nugget = per["nugget"]
    assert nugget.diketahui is True
    assert nugget.hpp_tampil == "Rp20.000"
    assert nugget.laba_kotor_tampil == "Rp5.000"

    assert kartu.status == "sebagian"


def test_untung_kurang_data_jujur_bukan_nol(session: Session, business: Business):
    _susun_skenario(session, business)
    kartu = kartu_untung(session, business.id, MULAI, SELESAI).kartu[0]
    kroket = {b.nama: b for b in kartu.produk}["kroket"]

    assert kroket.diketahui is False
    assert kroket.hpp_tampil is None  # BUKAN "Rp0" / karangan (aturan #2)
    assert kroket.laba_kotor_tampil is None
    assert kroket.sebab == "resepnya belum diatur"  # bahasa warung
    # teks_alt tak boleh menampilkan angka palsu untuk yang belum diketahui
    assert "Rp0" not in kartu.teks_alt


def test_untung_menampilkan_cakupan(session: Session, business: Business):
    _susun_skenario(session, business)
    kartu = kartu_untung(session, business.id, MULAI, SELESAI).kartu[0]
    # cakupan = tercakup 125.000 (risol 75k + nugget 50k) ÷ omzet 155.000 = 80,6%
    assert kartu.cakupan_tampil == "80.6%"
    assert "80.6%" in kartu.pesan


def test_untung_tak_pernah_menyebut_untung_usaha(session: Session, business: Business):
    """Aturan #9: kartu untung tak pernah melabeli angkanya 'untung usaha' —
    itu label khusus kartu keuangan. Di sini yang benar adalah 'laba kotor'."""
    _susun_skenario(session, business)
    kartu = kartu_untung(session, business.id, MULAI, SELESAI).kartu[0]
    blob = json.dumps(kartu.__dict__, default=lambda o: o.__dict__).lower()
    assert "untung usaha" not in blob
    assert "untung kotor" in kartu.pesan or "laba kotor" in kartu.pesan


def test_untung_kosong_saat_belum_ada_produk(session: Session, business: Business):
    kartu = kartu_untung(session, business.id, MULAI, SELESAI).kartu[0]
    assert kartu.produk == []
    assert kartu.status == "belum_diketahui"
    assert kartu.cakupan_tampil == ""


# ── Kartu keuangan ───────────────────────────────────────────────────────────


def test_keuangan_untung_usaha_angka_dari_db(session: Session, business: Business):
    _susun_skenario(session, business)
    keluar = kartu_keuangan(session, business.id, MULAI, SELESAI)
    kartu = keluar.kartu[0]
    assert isinstance(kartu, KartuKeuangan)

    # Dihitung ulang di test:
    # omzet   = 75.000 + 50.000 + 30.000 = 155.000
    # belanja = 40.000 (nugget); operasional = 20.000 + 15.000 = 35.000
    # laba    = 155.000 − 75.000 = 80.000
    assert kartu.omzet_tampil == "Rp155.000"
    assert kartu.belanja_tampil == "Rp40.000"
    assert kartu.operasional_tampil == "Rp35.000"
    assert kartu.biaya_tampil == "Rp75.000"
    assert kartu.laba_bersih_tampil == "Rp80.000"
    assert kartu.untung is True
    assert kartu.ada_data is True

    # pos biaya terbesar: nugget 40k > gas 20k > listrik 15k
    assert [p.nominal_tampil for p in kartu.pos_biaya[:3]] == ["Rp40.000", "Rp20.000", "Rp15.000"]


def test_keuangan_prive_dikecualikan_dan_terpisah(session: Session, business: Business):
    _susun_skenario(session, business)
    kartu = kartu_keuangan(session, business.id, MULAI, SELESAI).kartu[0]
    # prive 20.000 TIDAK masuk biaya (80.000 sudah tanpa prive) tapi dilaporkan
    assert kartu.prive_tampil == "Rp20.000"
    assert kartu.rasio_prive_tampil == "25%"  # 20.000 / 80.000 × 100


def test_keuangan_cakupan_dan_catatan_bahasa_warung(session: Session, business: Business):
    _susun_skenario(session, business)
    kartu = kartu_keuangan(session, business.id, MULAI, SELESAI).kartu[0]
    assert kartu.cakupan_tampil == "80.6%"  # aturan #2 wajib tampil
    gabung = " ".join(kartu.catatan).lower()
    assert "basis kas" not in gabung  # jargon dilarang
    assert "belanja" in gabung  # penjelasan warung memang ada


def test_keuangan_tanpa_skor_komposit(session: Session, business: Business):
    """Aturan #9: fakta mentah untuk penyalur, tak pernah skor komposit."""
    _susun_skenario(session, business)
    kartu = kartu_keuangan(session, business.id, MULAI, SELESAI).kartu[0]
    blob = json.dumps(kartu.__dict__, default=lambda o: o.__dict__).lower()
    assert "skor" not in blob
    # angka utama tetap dilabeli 'untung usaha' di teks_alt (bukan HPP)
    assert "untung usaha" in kartu.teks_alt.lower()


def test_keuangan_kosong_jujur(session: Session, business: Business):
    kartu = kartu_keuangan(session, business.id, MULAI, SELESAI).kartu[0]
    assert kartu.ada_data is False
    assert kartu.laba_bersih_tampil == "Rp0"
    assert any("belum ada catatan" in c.lower() for c in kartu.catatan)


# ── Isolasi tenant (aturan #6) ───────────────────────────────────────────────


def test_isolasi_tenant_untung_dan_keuangan(
    session: Session, business: Business, tetangga: Business
):
    _susun_skenario(session, business)
    # Tetangga punya produk & penjualan sendiri — tak boleh bocor ke usaha kita.
    lain = buat_produk(session, tetangga, "seblak", JenisProduk.produksi, harga_jual=Decimal("8000"))
    buat_transaksi(
        session, tetangga, JenisTransaksi.pemasukan, Decimal("999000"), date(2026, 7, 10),
        product=lain, qty=1, satuan="porsi",
    )

    untung = kartu_untung(session, business.id, MULAI, SELESAI).kartu[0]
    assert "seblak" not in {b.nama for b in untung.produk}

    keuangan = kartu_keuangan(session, business.id, MULAI, SELESAI).kartu[0]
    assert keuangan.omzet_tampil == "Rp155.000"  # 999.000 tetangga tak masuk

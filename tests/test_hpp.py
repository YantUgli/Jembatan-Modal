"""Unit test service HPP — formula & semua jalur degradasi (02-arsitektur.md §7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models import (
    JenisProduk,
    JenisTransaksi,
    SumberInput,
    TipeKomponen,
    Transaction,
)
from app.services.hpp import (
    StatusHpp,
    cakupan_hpp,
    hitung_hpp_produk,
)
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga


# ── Produksi: formula pokok ─────────────────────────────────────────────────


def test_hpp_produksi_lengkap(session, business):
    tepung = buat_material(session, business, "tepung")
    minyak = buat_material(session, business, "minyak", "liter")
    ayam = buat_material(session, business, "ayam")
    set_harga(session, tepung, 13000, date(2026, 6, 1))
    set_harga(session, minyak, 19000, date(2026, 6, 1), "liter")
    set_harga(session, ayam, 36000, date(2026, 6, 1))

    risol = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15000)
    buat_resep(session, risol, 10, [(tepung, 1, "kg"), (minyak, 0.5, "liter"), (ayam, 0.5, "kg")])

    hasil = hitung_hpp_produk(session, risol.id, business.id)

    # (13000 + 9500 + 18000) / 10 = 4050
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("4050.00")
    assert hasil.laba_kotor_per_unit == Decimal("10950.00")
    assert len(hasil.komponen) == 3
    assert hasil.bahan_kurang_harga == []


def test_hpp_produksi_pakai_harga_terakhir(session, business):
    """Harga yang dipakai adalah yang paling baru (append-only, bertanggal)."""
    gula = buat_material(session, business, "gula")
    set_harga(session, gula, 10000, date(2026, 5, 1))
    set_harga(session, gula, 14000, date(2026, 6, 1))  # terbaru → yang dipakai

    p = buat_produk(session, business, "kue", JenisProduk.produksi, harga_jual=5000)
    buat_resep(session, p, 10, [(gula, 1, "kg")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.hpp_per_unit == Decimal("1400.00")  # 14000/10
    assert hasil.komponen[0].tanggal_harga == date(2026, 6, 1)


# ── Degradasi produksi ──────────────────────────────────────────────────────


def test_produksi_tanpa_resep_belum_diketahui(session, business):
    p = buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20000)
    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.belum_ada_resep
    assert hasil.hpp_per_unit is None
    assert hasil.laba_kotor_per_unit is None
    assert not hasil.diketahui


def test_produksi_bahan_tanpa_harga_belum_lengkap(session, business):
    tepung = buat_material(session, business, "tepung")
    keju = buat_material(session, business, "keju")  # sengaja tanpa harga
    set_harga(session, tepung, 13000, date(2026, 6, 1))

    p = buat_produk(session, business, "risol keju", JenisProduk.produksi, harga_jual=18000)
    buat_resep(session, p, 10, [(tepung, 1, "kg"), (keju, 0.2, "kg")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.harga_tidak_lengkap
    assert hasil.hpp_per_unit is None
    assert "keju" in hasil.bahan_kurang_harga
    assert "tepung" not in hasil.bahan_kurang_harga


def test_yield_nol_tidak_membagi_nol(session, business):
    tepung = buat_material(session, business, "tepung")
    set_harga(session, tepung, 13000, date(2026, 6, 1))
    p = buat_produk(session, business, "aneh", JenisProduk.produksi, harga_jual=1000)
    buat_resep(session, p, 0, [(tepung, 1, "kg")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.hpp_per_unit is None
    assert hasil.status is StatusHpp.belum_ada_resep


def test_komponen_non_material_belum_didukung(session, business):
    """Slot labor_time/overhead ada di skema tapi kalkulasinya belum boleh ada."""
    tepung = buat_material(session, business, "tepung")
    set_harga(session, tepung, 13000, date(2026, 6, 1))
    tenaga = buat_material(session, business, "tenaga kerja")
    tenaga.tipe = TipeKomponen.labor_time  # paksa slot
    session.flush()

    p = buat_produk(session, business, "kue jasa", JenisProduk.produksi, harga_jual=20000)
    buat_resep(session, p, 5, [(tepung, 1, "kg"), (tenaga, 2, "jam")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.tipe_belum_didukung
    assert hasil.hpp_per_unit is None


def test_resep_baru_langsung_terlihat_di_sesi_yang_sama(session, business):
    """Regresi: `product.recipe` yang sudah ter-cache sebagai None membuat resep
    baru tidak terlihat — persis alur `atur_resep` lalu tanya HPP."""
    p = buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20000)
    assert hitung_hpp_produk(session, p.id, business.id).status is StatusHpp.belum_ada_resep

    coklat = buat_material(session, business, "coklat")
    set_harga(session, coklat, 50000, date(2026, 6, 1))
    buat_resep(session, p, 10, [(coklat, 1, "kg")], yield_satuan="kotak")

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("5000.00")


# ── Reseller ────────────────────────────────────────────────────────────────


def test_hpp_reseller_dari_harga_beli_terakhir(session, business):
    nugget = buat_produk(session, business, "nugget", JenisProduk.reseller, harga_jual=30000)
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=250000,
        deskripsi="kulakan", tanggal=date(2026, 5, 1), sumber_input=SumberInput.manual,
        product_id=nugget.id, qty=10, satuan="pack",
    ))
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=260000,
        deskripsi="kulakan", tanggal=date(2026, 6, 1), sumber_input=SumberInput.manual,
        product_id=nugget.id, qty=10, satuan="pack",
    ))
    session.flush()

    hasil = hitung_hpp_produk(session, nugget.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("26000.00")  # harga beli terbaru
    assert hasil.laba_kotor_per_unit == Decimal("4000.00")


def test_reseller_tanpa_pembelian_belum_diketahui(session, business):
    p = buat_produk(session, business, "sabun", JenisProduk.reseller, harga_jual=5000)
    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.belum_ada_harga_beli
    assert hasil.hpp_per_unit is None


# ── Cakupan HPP ─────────────────────────────────────────────────────────────


def test_cakupan_hpp_parsial(session, business):
    tepung = buat_material(session, business, "tepung")
    set_harga(session, tepung, 10000, date(2026, 6, 1))
    risol = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15000)
    buat_resep(session, risol, 10, [(tepung, 1, "kg")])  # HPP = 1000/kotak

    # penjualan tercakup: 4 kotak risol = 60000
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pemasukan, nominal=60000,
        tanggal=date(2026, 6, 10), sumber_input=SumberInput.chat,
        product_id=risol.id, qty=4, satuan="kotak",
    ))
    # penjualan tanpa produk: 40000 (tidak tercakup)
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pemasukan, nominal=40000,
        tanggal=date(2026, 6, 11), sumber_input=SumberInput.chat, deskripsi="titipan kue",
    ))
    session.flush()

    cak = cakupan_hpp(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert cak.omzet_total == Decimal("100000.00")
    assert cak.omzet_tercakup == Decimal("60000.00")
    assert cak.persen == Decimal("60.0")
    assert cak.hpp_total == Decimal("4000.00")       # 4 × 1000
    assert cak.laba_kotor == Decimal("56000.00")     # 60000 − 4000
    assert cak.penjualan_tanpa_produk == Decimal("40000.00")


def test_cakupan_produk_tanpa_hpp_tidak_tercakup(session, business):
    """Produk terjual tapi HPP belum diketahui → tidak dipaksa masuk cakupan."""
    p = buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20000)
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pemasukan, nominal=20000,
        tanggal=date(2026, 6, 10), sumber_input=SumberInput.chat,
        product_id=p.id, qty=1, satuan="kotak",
    ))
    session.flush()

    cak = cakupan_hpp(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert cak.omzet_total == Decimal("20000.00")
    assert cak.omzet_tercakup == Decimal("0.00")
    assert cak.persen == Decimal("0.0")
    assert "brownies" in cak.produk_tak_terhitung


def test_cakupan_tanpa_penjualan(session, business):
    cak = cakupan_hpp(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert cak.omzet_total == Decimal("0.00")
    assert cak.persen == Decimal("0.0")


# ── Isolasi tenant (prinsip #6) ─────────────────────────────────────────────


def test_produk_usaha_lain_ditolak(session, business):
    from app.models import Business, User

    u2 = User(nama="Lain", no_hp="0899LAIN")
    session.add(u2)
    session.flush()
    biz2 = Business(user_id=u2.id, nama_usaha="Usaha Lain")
    session.add(biz2)
    session.flush()
    p = buat_produk(session, biz2, "punya orang", JenisProduk.produksi, harga_jual=1000)

    with pytest.raises(ValueError):
        hitung_hpp_produk(session, p.id, business.id)  # business salah


# ── Snapshot rincian menyebut asal angka ────────────────────────────────────


def test_rincian_json_menyebut_asal_angka(session, business):
    tepung = buat_material(session, business, "tepung")
    set_harga(session, tepung, 12000, date(2026, 6, 1))
    p = buat_produk(session, business, "roti", JenisProduk.produksi, harga_jual=3000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")])

    rincian = hitung_hpp_produk(session, p.id, business.id).rincian_json()
    assert rincian["status"] == "lengkap"
    assert rincian["komponen"][0]["nama"] == "tepung"
    assert rincian["komponen"][0]["harga_satuan"] == "12000.00"
    assert rincian["komponen"][0]["tanggal_harga"] == "2026-06-01"

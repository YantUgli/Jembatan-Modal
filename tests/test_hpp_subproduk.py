"""Unit test resep bertingkat / sub-produk (keputusan.md 2026-07-18).

Kasus penguji diambil langsung dari `docs/05-analisis-9-kasus-hpp.md`: bakso
gerobak, di mana **pentol adalah output resep A sekaligus bahan resep B**. Tanpa
sub-produk, pengguna harus menghitung sendiri "Rp 1.150/butir" — aritmatika
berpindah ke kepala pengguna (aturan #1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import JenisProduk, JenisTransaksi, RecipeItem, SumberInput, Transaction
from app.services.hpp import StatusHpp, hitung_hpp_produk
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga

HARI = date(2026, 6, 1)


def _pentol(session, business):
    """Adonan 1 kg daging + 0,5 kg tapioka + bumbu → 130 butir pentol kecil.

    Angka dari rangkuman bakso gerobak: Rp 150.000 ÷ 130 ≈ Rp 1.153,85/butir.
    """
    daging = buat_material(session, business, "daging sapi")
    tapioka = buat_material(session, business, "tapioka")
    bumbu = buat_material(session, business, "bumbu & es", "batch")
    set_harga(session, daging, 140_000, HARI)
    set_harga(session, tapioka, 12_000, HARI)
    set_harga(session, bumbu, 4_000, HARI, "batch")

    pentol = buat_produk(session, business, "pentol kecil", JenisProduk.produksi)
    buat_resep(
        session, pentol, 130,
        [(daging, 1, "kg"), (tapioka, 0.5, "kg"), (bumbu, 1, "batch")],
        yield_satuan="butir",
    )
    return pentol


# ── Formula pokok ───────────────────────────────────────────────────────────


def test_sub_produk_dihitung_rekursif(session, business):
    """Bakso: 7 butir pentol setara + mie + sayur + kuah."""
    pentol = _pentol(session, business)
    mie = buat_material(session, business, "mie & bihun", "porsi")
    set_harga(session, mie, 800, HARI, "porsi")

    mangkok = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, mangkok, 1, [(pentol, 7, "butir"), (mie, 1, "porsi")])

    hasil = hitung_hpp_produk(session, mangkok.id, business.id)

    # pentol: (140.000 + 6.000 + 4.000) / 130 = 1.153,85/butir → ×7 = 8.076,95
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("8876.95")
    assert hasil.laba_kotor_per_unit == Decimal("6123.05")

    komp = {k.nama: k for k in hasil.komponen}
    assert komp["pentol kecil"].tipe == "sub_produk"
    assert komp["pentol kecil"].harga_satuan == Decimal("1153.85")
    assert komp["pentol kecil"].product_id == pentol.id
    assert komp["mie & bihun"].tipe == "material"


def test_sub_produk_bertingkat_tiga_lapis(session, business):
    """Adonan → pentol → mangkok. Rekursi tidak berhenti di satu lapis."""
    tepung = buat_material(session, business, "tepung")
    set_harga(session, tepung, 10_000, HARI)

    adonan = buat_produk(session, business, "adonan", JenisProduk.produksi)
    buat_resep(session, adonan, 10, [(tepung, 1, "kg")])  # 1.000/unit

    isi = buat_produk(session, business, "isi", JenisProduk.produksi)
    buat_resep(session, isi, 2, [(adonan, 1, "unit")])  # 500/unit

    jadi = buat_produk(session, business, "jadi", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, jadi, 1, [(isi, 4, "unit")])  # 2.000

    hasil = hitung_hpp_produk(session, jadi.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("2000.00")


def test_sub_produk_boleh_reseller(session, business):
    """Pentol dibeli jadi dari pemasok — HPP-nya harga beli terakhir."""
    pentol = buat_produk(session, business, "pentol beli", JenisProduk.reseller)
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=100_000,
        tanggal=HARI, sumber_input=SumberInput.manual,
        product_id=pentol.id, qty=100, satuan="butir",
    ))
    session.flush()

    mangkok = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, mangkok, 1, [(pentol, 7, "butir")])

    hasil = hitung_hpp_produk(session, mangkok.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("7000.00")  # 7 × 1.000


# ── Degradasi menjalar (aturan #2) ──────────────────────────────────────────


def test_sub_produk_tanpa_harga_menjalar_ke_induk(session, business):
    """Bahan pentol belum ada harganya → bakso ikut 'belum diketahui', bukan dikarang."""
    daging = buat_material(session, business, "daging sapi")  # sengaja tanpa harga
    pentol = buat_produk(session, business, "pentol kecil", JenisProduk.produksi)
    buat_resep(session, pentol, 130, [(daging, 1, "kg")])

    mangkok = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, mangkok, 1, [(pentol, 7, "butir")])

    hasil = hitung_hpp_produk(session, mangkok.id, business.id)

    assert hasil.status is StatusHpp.subproduk_tidak_lengkap
    assert hasil.hpp_per_unit is None
    assert hasil.laba_kotor_per_unit is None
    # penyebab akarnya ikut terbawa naik — pengguna tahu apa yang harus diisi
    assert "daging sapi" in hasil.bahan_kurang_harga
    assert any("pentol kecil" in c for c in hasil.catatan)


def test_sub_produk_tanpa_resep_menjalar_ke_induk(session, business):
    pentol = buat_produk(session, business, "pentol kecil", JenisProduk.produksi)  # tanpa resep
    mangkok = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, mangkok, 1, [(pentol, 7, "butir")])

    hasil = hitung_hpp_produk(session, mangkok.id, business.id)
    assert hasil.status is StatusHpp.subproduk_tidak_lengkap
    assert hasil.hpp_per_unit is None


# ── Penjaga siklus ──────────────────────────────────────────────────────────


def test_resep_melingkar_langsung_tidak_hang(session, business):
    """A memakai A. Harus mengaku, bukan rekursi tanpa henti."""
    a = buat_produk(session, business, "A", JenisProduk.produksi, harga_jual=1_000)
    buat_resep(session, a, 1, [(a, 1, "unit")])

    hasil = hitung_hpp_produk(session, a.id, business.id)
    assert hasil.status is StatusHpp.resep_melingkar
    assert hasil.hpp_per_unit is None
    assert any("melingkar" in c for c in hasil.catatan)


def test_resep_melingkar_tidak_langsung(session, business):
    """A → B → A."""
    a = buat_produk(session, business, "A", JenisProduk.produksi, harga_jual=1_000)
    b = buat_produk(session, business, "B", JenisProduk.produksi)
    buat_resep(session, a, 1, [(b, 1, "unit")])
    buat_resep(session, b, 1, [(a, 1, "unit")])

    hasil = hitung_hpp_produk(session, a.id, business.id)
    assert hasil.status is StatusHpp.resep_melingkar
    assert hasil.hpp_per_unit is None


# ── Isolasi tenant & integritas skema ───────────────────────────────────────


def test_sub_produk_lintas_usaha_ditolak(session, business, tetangga):
    """Prinsip #6: resep tidak boleh menarik produk usaha lain."""
    punya_tetangga = buat_produk(session, tetangga, "pentol orang", JenisProduk.produksi)
    tepung = buat_material(session, tetangga, "tepung")
    set_harga(session, tepung, 10_000, HARI)
    buat_resep(session, punya_tetangga, 10, [(tepung, 1, "kg")])

    mangkok = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, mangkok, 1, [(punya_tetangga, 7, "butir")])

    hasil = hitung_hpp_produk(session, mangkok.id, business.id)

    assert hasil.status is StatusHpp.subproduk_tidak_lengkap
    assert hasil.hpp_per_unit is None  # angka usaha lain tidak pernah ikut terhitung


def test_baris_resep_wajib_salah_satu(session, business):
    """CHECK constraint: tidak boleh dua-duanya, tidak boleh kosong dua-duanya."""
    tepung = buat_material(session, business, "tepung")
    p = buat_produk(session, business, "p", JenisProduk.produksi)
    sub = buat_produk(session, business, "sub", JenisProduk.produksi)
    resep = buat_resep(session, p, 1, [(tepung, 1, "kg")])

    session.add(RecipeItem(recipe_id=resep.id, cost_item_id=tepung.id, product_id=sub.id, qty=1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_baris_resep_kosong_ditolak(session, business):
    p = buat_produk(session, business, "p", JenisProduk.produksi)
    resep = buat_resep(session, p, 1, [])

    session.add(RecipeItem(recipe_id=resep.id, qty=1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

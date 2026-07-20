"""Unit test faktor kehilangan — satu angka untuk susut/reject/waste/gagal panen.

Angka acuan diambil dari `docs/05-analisis-9-kasus-hpp.md`:
- konveksi: reject 4%, `HPP = subtotal ÷ (1 − 0,04)`
- hidroponik: survival 90%
- bakso: pentol jatuh di gerobak

Semuanya matematika yang sama: biaya dibagi ke unit yang **benar-benar laku**.

Susut pengeceran (toko kelontong: sak → literan) **bukan** di sini — repacking
bukan transformasi, jadi ia hidup di jalur reseller (keputusan.md 2026-07-19).
Lihat `test_hpp_reseller_susut.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import JenisProduk, Recipe
from app.services.hpp import StatusHpp, hitung_hpp_produk
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga

HARI = date(2026, 6, 1)



def test_reject_konveksi(session, business):
    """HPP final = subtotal ÷ (1 − reject), bukan dikurangi angka datar."""
    kain = buat_material(session, business, "kain", "kg")
    set_harga(session, kain, 115_000, HARI, "kg")

    kaos = buat_produk(session, business, "kaos", JenisProduk.produksi, harga_jual=60_000)
    # 1 kg → 4 pcs, reject 4%
    buat_resep(session, kaos, 4, [(kain, 1, "kg")], yield_satuan="pcs",
               faktor_kehilangan=0.04)

    hasil = hitung_hpp_produk(session, kaos.id, business.id)

    # 115.000 / (4 × 0,96) = 115.000 / 3,84 = 29.947,92
    assert hasil.hpp_per_unit == Decimal("29947.92")
    assert hasil.yield_efektif == Decimal("3.84")


def test_tanpa_faktor_hasil_tidak_berubah(session, business):
    """NULL = belum diukur. Jangan diam-diam diperlakukan sebagai nol lalu
    dinarasikan seolah sudah memperhitungkan kehilangan."""
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 13_000, HARI, "kg")
    p = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")], yield_satuan="kotak")

    hasil = hitung_hpp_produk(session, p.id, business.id)

    assert hasil.hpp_per_unit == Decimal("1300.00")
    assert hasil.faktor_kehilangan is None
    assert hasil.yield_efektif == hasil.yield_qty
    assert not any("kehilangan" in c for c in hasil.catatan)


def test_faktor_nol_tidak_mengubah_angka(session, business):
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 13_000, HARI, "kg")
    p = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")], yield_satuan="kotak",
               faktor_kehilangan=0)

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.hpp_per_unit == Decimal("1300.00")
    assert not any("kehilangan" in c for c in hasil.catatan)  # 0% tak perlu diumumkan


def test_kehilangan_pada_sub_produk_menjalar_ke_induk(session, business):
    """Pentol jatuh 5% di gerobak → HPP per butir naik → bakso ikut naik."""
    daging = buat_material(session, business, "daging", "kg")
    set_harga(session, daging, 130_000, HARI, "kg")

    pentol = buat_produk(session, business, "pentol", JenisProduk.produksi)
    buat_resep(session, pentol, 130, [(daging, 1, "kg")], yield_satuan="butir",
               faktor_kehilangan=0.05)

    bakso = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, bakso, 1, [(pentol, 7, "butir")], yield_satuan="mangkok")

    sub = hitung_hpp_produk(session, pentol.id, business.id)
    induk = hitung_hpp_produk(session, bakso.id, business.id)

    # 130.000 / (130 × 0,95) = 1.052,63/butir  (tanpa kehilangan: 1.000)
    assert sub.hpp_per_unit == Decimal("1052.63")
    assert induk.hpp_per_unit == Decimal("7368.41")  # 7 × 1.052,63
    assert induk.status is StatusHpp.lengkap


def test_hasil_efektif_nol_tidak_membagi_nol(session, business):
    """Pertahanan di service: yield 0 + faktor tetap tidak boleh membagi nol.

    (faktor = 1 tidak bisa diuji lewat sini — CHECK constraint DB menolaknya
    lebih dulu; lihat `test_faktor_di_luar_rentang_ditolak_db`.)
    """
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 13_000, HARI, "kg")
    p = buat_produk(session, business, "aneh", JenisProduk.produksi, harga_jual=1_000)
    buat_resep(session, p, 0, [(tepung, 1, "kg")], yield_satuan="kotak",
               faktor_kehilangan=0.5)

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.hpp_per_unit is None
    assert hasil.status is StatusHpp.belum_ada_resep


def test_faktor_di_luar_rentang_ditolak_db(session, business):
    p = buat_produk(session, business, "p", JenisProduk.produksi)
    session.add(Recipe(product_id=p.id, yield_qty=10, yield_satuan="kotak",
                       faktor_kehilangan=1.5))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_faktor_negatif_ditolak_db(session, business):
    p = buat_produk(session, business, "p", JenisProduk.produksi)
    session.add(Recipe(product_id=p.id, yield_qty=10, yield_satuan="kotak",
                       faktor_kehilangan=-0.1))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()



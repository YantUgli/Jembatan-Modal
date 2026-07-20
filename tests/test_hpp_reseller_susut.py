"""Unit test jalur reseller: susut & konversi satuan (keputusan.md 2026-07-19).

**Repacking bukan transformasi.** Beras 1 sak yang dijual literan tetap
`reseller` — beras = beras. Yang berubah cuma kemasan/satuan, jadi mereka tidak
pernah ditawari wawancara resep (aturan #8). Yang ditanyakan ke mereka adalah
*isi per kemasan* dan *susut*.

    HPP_jual = (harga_beli ÷ qty_beli) ÷ (isi_per_satuan_beli × (1 − susut))

Angka acuan dari `rangkuman-toko-kelontong.md`: modal Rp 320.000/sak (25 kg),
1 liter ≈ 0,8 kg → 31,25 liter kotor, susut 2,5%.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    JenisProduk,
    JenisTransaksi,
    Product,
    SumberInput,
    Transaction,
)
from app.services.hpp import StatusHpp, hitung_hpp_produk
from tests.conftest import buat_produk

HARI = date(2026, 6, 1)


def _beli(session, business, product, nominal, qty, satuan, tanggal=HARI):
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=nominal,
        tanggal=tanggal, sumber_input=SumberInput.manual,
        product_id=product.id, qty=qty, satuan=satuan,
    ))
    session.flush()


def _beras(session, business, **kw):
    p = buat_produk(
        session, business, "beras literan", JenisProduk.reseller, harga_jual=12_500,
        satuan_beli="sak", satuan_jual="liter", isi_per_satuan_beli=31.25, **kw
    )
    _beli(session, business, p, 320_000, 1, "sak")
    return p


# ── Kasus kelontong ─────────────────────────────────────────────────────────


def test_susut_beras_kelontong(session, business):
    """Yang dokumennya sebut 'paling sering salah dihitung pemilik kelontong'."""
    beras = _beras(session, business, faktor_kehilangan=0.025)

    hasil = hitung_hpp_produk(session, beras.id, business.id)

    assert hasil.status is StatusHpp.lengkap
    assert hasil.jenis == "reseller"          # ⬅ bukan produksi
    assert hasil.satuan_hpp == "liter"
    assert hasil.yield_qty == Decimal("31.250")
    assert hasil.yield_efektif == Decimal("30.46875")
    assert hasil.hpp_per_unit == Decimal("10502.56")   # naif tanpa susut: 10.240,00
    assert hasil.laba_kotor_per_unit == Decimal("1997.44")
    assert any("1 sak = 31.25 liter" in c for c in hasil.catatan)
    assert any("susut 2.5%" in c for c in hasil.catatan)


def test_konversi_tanpa_susut(session, business):
    """Isi per kemasan diketahui, susut belum diukur → jangan diam-diam dianggap nol."""
    beras = _beras(session, business)

    hasil = hitung_hpp_produk(session, beras.id, business.id)

    assert hasil.hpp_per_unit == Decimal("10240.00")   # 320.000 / 31,25
    assert hasil.faktor_kehilangan is None
    assert not any("susut" in c for c in hasil.catatan)


def test_susut_tanpa_konversi(session, business):
    """Beli per kg, jual per kg, tapi tetap ada susut 2%."""
    p = buat_produk(
        session, business, "gula curah", JenisProduk.reseller, harga_jual=15_000,
        satuan_beli="kg", satuan_jual="kg", faktor_kehilangan=0.02,
    )
    _beli(session, business, p, 170_000, 10, "kg")   # Rp 17.000/kg

    hasil = hitung_hpp_produk(session, p.id, business.id)

    assert hasil.hpp_per_unit == Decimal("17346.94")  # 17.000 / 0,98
    assert hasil.satuan_hpp == "kg"
    assert hasil.yield_qty is None                    # tidak ada konversi kemasan


def test_reseller_polos_tidak_berubah(session, business):
    """Tanpa kolom jalur reseller sama sekali → perilaku lama persis."""
    nugget = buat_produk(session, business, "nugget", JenisProduk.reseller, harga_jual=30_000)
    _beli(session, business, nugget, 260_000, 10, "pack")

    hasil = hitung_hpp_produk(session, nugget.id, business.id)

    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("26000.00")
    assert hasil.satuan_hpp == "pack"
    assert hasil.yield_efektif is None


# ── Satuan: bandingkan, jangan konversi ─────────────────────────────────────


def test_satuan_pembelian_beda_ditolak(session, business):
    """Kadang beli per sak, kadang per kg → konversinya akan salah diam-diam."""
    p = buat_produk(
        session, business, "beras literan", JenisProduk.reseller, harga_jual=12_500,
        satuan_beli="sak", satuan_jual="liter", isi_per_satuan_beli=31.25,
        faktor_kehilangan=0.025,
    )
    _beli(session, business, p, 320_000, 25, "kg")   # ⬅ dibeli per kg, bukan sak

    hasil = hitung_hpp_produk(session, p.id, business.id)

    assert hasil.status is StatusHpp.satuan_tidak_cocok
    assert hasil.hpp_per_unit is None
    assert "sak" in hasil.satuan_bertabrakan[0]
    assert "kg" in hasil.satuan_bertabrakan[0]


def test_pembelian_terbaru_yang_dipakai(session, business):
    beras = _beras(session, business, faktor_kehilangan=0.025)
    _beli(session, business, beras, 350_000, 1, "sak", tanggal=date(2026, 7, 1))

    hasil = hitung_hpp_produk(session, beras.id, business.id)
    assert hasil.hpp_per_unit == Decimal("11487.18")  # 350.000 / 30,46875


# ── Integritas skema ────────────────────────────────────────────────────────


def test_isi_harus_positif(session, business):
    session.add(Product(business_id=business.id, nama="x", jenis=JenisProduk.reseller,
                        satuan_beli="sak", satuan_jual="liter", isi_per_satuan_beli=0))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_konversi_wajib_menyebut_satuannya(session, business):
    """isi_per_satuan_beli tanpa satuan = angka tanpa arti."""
    session.add(Product(business_id=business.id, nama="x", jenis=JenisProduk.reseller,
                        isi_per_satuan_beli=31.25))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_faktor_kehilangan_produk_di_luar_rentang_ditolak(session, business):
    session.add(Product(business_id=business.id, nama="x", jenis=JenisProduk.reseller,
                        faktor_kehilangan=1.0))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

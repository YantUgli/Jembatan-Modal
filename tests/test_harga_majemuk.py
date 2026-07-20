"""Unit test harga jual majemuk — satu produk, banyak harga.

Kasus dari `docs/05-analisis-9-kasus-hpp.md`:
- frozen food : eceran Rp 30.000 (MAP) vs tebus reseller Rp 23.000
- hidroponik  : resto Grade A Rp 22.000/kg vs ecer Grade B Rp 35.000/kg
- konveksi    : tier kuantitas 50 / 100 / 500 pcs

Aturan pemilihan: **yang paling spesifik menang**, seri diputus tanggal terbaru.
Tidak ada yang cocok → None, bukan harga kanal lain diam-diam (aturan #2).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models import JenisProduk
from app.services.harga import daftar_harga, harga_jual_berlaku
from app.services.hpp import KonteksHarga, StatusHpp, hitung_hpp_produk
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga, set_harga_jual

HARI = date(2026, 6, 1)


def _dimsum(session, business):
    """Frozen food: HPP produksi + dua kanal harga."""
    ayam = buat_material(session, business, "ayam giling", "kg")
    set_harga(session, ayam, 42_000, HARI, "kg")
    p = buat_produk(session, business, "dimsum", JenisProduk.produksi)
    buat_resep(session, p, 20, [(ayam, 2, "kg")], yield_satuan="pack")  # 4.200/pack
    set_harga_jual(session, p, 30_000, berlaku_dari=HARI)                      # umum/eceran
    set_harga_jual(session, p, 23_000, kanal="reseller", berlaku_dari=HARI)    # tebus
    return p


# ── Pemilihan harga ─────────────────────────────────────────────────────────


def test_tanpa_konteks_pakai_harga_umum(session, business):
    p = _dimsum(session, business)
    h = harga_jual_berlaku(session, p.id, business.id, tanggal=HARI)
    assert h.harga == Decimal("30000.00")
    assert h.umum is True


def test_kanal_lebih_spesifik_menang(session, business):
    p = _dimsum(session, business)
    h = harga_jual_berlaku(session, p.id, business.id, tanggal=HARI, kanal="reseller")
    assert h.harga == Decimal("23000.00")
    assert h.kanal == "reseller"


def test_kanal_tak_dikenal_jatuh_ke_harga_umum(session, business):
    """Baris ber-kanal disaring keluar; baris umum tetap berlaku."""
    p = _dimsum(session, business)
    h = harga_jual_berlaku(session, p.id, business.id, tanggal=HARI, kanal="tokopedia")
    assert h.harga == Decimal("30000.00")
    assert h.umum is True


def test_tanpa_harga_sama_sekali_none(session, business):
    p = buat_produk(session, business, "belum dihargai", JenisProduk.produksi)
    assert harga_jual_berlaku(session, p.id, business.id, tanggal=HARI) is None


def test_harga_belum_berlaku_diabaikan(session, business):
    p = buat_produk(session, business, "risol", JenisProduk.produksi)
    set_harga_jual(session, p, 15_000, berlaku_dari=date(2026, 6, 1))
    set_harga_jual(session, p, 17_000, berlaku_dari=date(2026, 8, 1))  # belum berlaku

    assert harga_jual_berlaku(session, p.id, business.id, tanggal=date(2026, 7, 1)).harga == Decimal("15000.00")
    assert harga_jual_berlaku(session, p.id, business.id, tanggal=date(2026, 8, 1)).harga == Decimal("17000.00")


def test_kenaikan_harga_pakai_yang_terbaru(session, business):
    p = buat_produk(session, business, "risol", JenisProduk.produksi)
    set_harga_jual(session, p, 15_000, berlaku_dari=date(2026, 6, 1))
    set_harga_jual(session, p, 17_000, berlaku_dari=date(2026, 7, 1))

    h = harga_jual_berlaku(session, p.id, business.id, tanggal=date(2026, 7, 15))
    assert h.harga == Decimal("17000.00")
    assert h.berlaku_dari == date(2026, 7, 1)


# ── Grade (hidroponik) ──────────────────────────────────────────────────────


def test_grade_dan_kanal_bersamaan(session, business):
    selada = buat_produk(session, business, "selada", JenisProduk.produksi)
    set_harga_jual(session, selada, 22_000, kanal="resto", grade="A", berlaku_dari=HARI)
    set_harga_jual(session, selada, 35_000, kanal="ecer", grade="B", berlaku_dari=HARI)
    set_harga_jual(session, selada, 25_000, berlaku_dari=HARI)

    resto = harga_jual_berlaku(session, selada.id, business.id, tanggal=HARI,
                               kanal="resto", grade="A")
    ecer = harga_jual_berlaku(session, selada.id, business.id, tanggal=HARI,
                              kanal="ecer", grade="B")
    campur = harga_jual_berlaku(session, selada.id, business.id, tanggal=HARI,
                                kanal="resto", grade="B")  # tak ada padanan tepat

    assert resto.harga == Decimal("22000.00")
    assert ecer.harga == Decimal("35000.00")
    assert campur.harga == Decimal("25000.00")  # jatuh ke umum, bukan asal ambil


# ── Tier kuantitas (konveksi) ───────────────────────────────────────────────


def _kaos(session, business):
    p = buat_produk(session, business, "kaos", JenisProduk.produksi)
    set_harga_jual(session, p, 68_000, min_qty=50, berlaku_dari=HARI)
    set_harga_jual(session, p, 60_000, min_qty=100, berlaku_dari=HARI)
    set_harga_jual(session, p, 55_000, min_qty=500, berlaku_dari=HARI)
    return p


@pytest.mark.parametrize(("qty", "harga"), [(50, "68000.00"), (99, "68000.00"),
                                            (100, "60000.00"), (499, "60000.00"),
                                            (500, "55000.00"), (1000, "55000.00")])
def test_tier_ambil_yang_tertinggi_masih_terpenuhi(session, business, qty, harga):
    p = _kaos(session, business)
    h = harga_jual_berlaku(session, p.id, business.id, tanggal=HARI, qty=qty)
    assert h.harga == Decimal(harga)


def test_qty_di_bawah_tier_terendah_tidak_dapat_harga(session, business):
    """Order 10 pcs sementara tier mulai 50 → jangan diam-diam pakai harga tier 50."""
    p = _kaos(session, business)
    assert harga_jual_berlaku(session, p.id, business.id, tanggal=HARI, qty=10) is None


def test_tier_tanpa_qty_tidak_dipakai(session, business):
    """Tier tak bisa diverifikasi tanpa kuantitas — jangan menebak."""
    p = _kaos(session, business)
    assert harga_jual_berlaku(session, p.id, business.id, tanggal=HARI) is None


# ── daftar_harga ────────────────────────────────────────────────────────────


def test_daftar_harga_menampilkan_semua_kanal(session, business):
    p = _dimsum(session, business)
    daftar = daftar_harga(session, p.id, business.id, tanggal=HARI)
    assert [(d.kanal, d.harga) for d in daftar] == [
        ("reseller", Decimal("23000.00")),
        (None, Decimal("30000.00")),
    ]


def test_daftar_harga_hanya_yang_terbaru_per_kombinasi(session, business):
    p = buat_produk(session, business, "risol", JenisProduk.produksi)
    set_harga_jual(session, p, 15_000, berlaku_dari=date(2026, 6, 1))
    set_harga_jual(session, p, 17_000, berlaku_dari=date(2026, 7, 1))

    daftar = daftar_harga(session, p.id, business.id, tanggal=date(2026, 7, 15))
    assert len(daftar) == 1
    assert daftar[0].harga == Decimal("17000.00")


# ── Terhubung ke HPP ────────────────────────────────────────────────────────


def test_laba_berbeda_per_kanal(session, business):
    """HPP sama, laba berbeda — inti dari harga majemuk."""
    p = _dimsum(session, business)

    eceran = hitung_hpp_produk(session, p.id, business.id)
    tebus = hitung_hpp_produk(session, p.id, business.id,
                              KonteksHarga(tanggal=HARI, kanal="reseller"))

    assert eceran.hpp_per_unit == tebus.hpp_per_unit == Decimal("4200.00")
    assert eceran.harga_jual == Decimal("30000.00")
    assert tebus.harga_jual == Decimal("23000.00")
    assert eceran.laba_kotor_per_unit == Decimal("25800.00")
    assert tebus.laba_kotor_per_unit == Decimal("18800.00")
    assert "kanal reseller" in tebus.harga_jual_konteks


def test_hpp_tetap_lengkap_walau_harga_jual_belum_ada(session, business):
    """HPP tidak bergantung harga jual — laba yang belum diketahui, bukan HPP."""
    ayam = buat_material(session, business, "ayam giling", "kg")
    set_harga(session, ayam, 42_000, HARI, "kg")
    p = buat_produk(session, business, "dimsum", JenisProduk.produksi)
    buat_resep(session, p, 20, [(ayam, 2, "kg")], yield_satuan="pack")

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("4200.00")
    assert hasil.harga_jual is None
    assert hasil.laba_kotor_per_unit is None


def test_memo_tidak_mencampur_laba_antar_kanal(session, business):
    """Memo dikunci (product_id, konteks) — kanal berbeda tidak saling pakai."""
    from app.services.hpp import hitung_hpp_semua

    _dimsum(session, business)
    umum = hitung_hpp_semua(session, business.id)
    tebus = hitung_hpp_semua(session, business.id, KonteksHarga(tanggal=HARI, kanal="reseller"))

    assert umum[0].harga_jual == Decimal("30000.00")
    assert tebus[0].harga_jual == Decimal("23000.00")


def test_isolasi_tenant(session, business, tetangga):
    p = buat_produk(session, tetangga, "punya orang", JenisProduk.produksi, harga_jual=9_000)
    with pytest.raises(ValueError):
        harga_jual_berlaku(session, p.id, business.id, tanggal=HARI)
    with pytest.raises(ValueError):
        daftar_harga(session, p.id, business.id, tanggal=HARI)

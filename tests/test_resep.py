"""`atur_resep` (Pilar 4, jalur produksi) — inti deterministik.

Menguji loop produksi ujung-ke-ujung di level service: resep terstruktur →
`Recipe`/`RecipeItem`/`CostItem` + harga bahan (dari pembelian & yang ditanyakan)
→ `hitung_hpp_produk` menghasilkan modal per porsi. Angka HPP dihitung ulang
independen di test, bukan disalin dari kode.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Business,
    CostItem,
    CostItemPrice,
    JenisProduk,
    JenisTransaksi,
    Recipe,
    RecipeItem,
    SumberHarga,
    Transaction,
)
from app.services.entitas import cari_cost_item, cari_produk
from app.services.hpp import StatusHpp, hitung_hpp_produk
from app.services.resep import atur_resep, catat_harga_bahan

from tests.conftest import buat_produk

TGL = date(2026, 6, 10)


def _beli(session, business, nama, nominal, qty, satuan, tanggal=TGL) -> Transaction:
    """Pembelian bahan (pengeluaran yatim ber-deskripsi = nama bahan)."""
    t = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran,
        nominal=Decimal(nominal), tanggal=tanggal, deskripsi=nama,
        qty=Decimal(qty), satuan=satuan,
    )
    session.add(t)
    session.flush()
    return t


def _risol(*bahan) -> list[tuple]:
    return list(bahan)


# ── Loop produksi lengkap ───────────────────────────────────────────────────


def test_loop_produksi_lengkap(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")
    _beli(session, business, "minyak", 19000, 1, "liter")
    ayam = _beli(session, business, "ayam", 36000, 1, "kg")

    res = atur_resep(
        session, business.id, "risol", Decimal("10"), "kotak",
        _risol(("tepung", Decimal("1"), "kg"),
               ("minyak", Decimal("0.5"), "liter"),
               ("ayam", Decimal("0.5"), "kg")),
        TGL,
    )

    # Jenis dipromosikan ke produksi (sinyal eksplisit aturan #8).
    produk = cari_produk(session, business.id, "risol")
    assert produk.jenis is JenisProduk.produksi

    # Resep + bahan terbentuk.
    assert res.recipe_id is not None
    assert len(session.scalars(select(CostItem)).all()) == 3
    assert len(session.scalars(select(RecipeItem)).all()) == 3

    # HPP: (1×13000 + 0.5×19000 + 0.5×36000) / 10 = 40500/10 = 4050.
    assert res.hpp.status is StatusHpp.lengkap
    assert res.hpp.hpp_per_unit == Decimal("4050.00")
    assert "Rp4.050" in res.konfirmasi and "risol" in res.konfirmasi

    # Pembelian teradopsi: cost_item_id terisi + harga bersumber transaksi.
    session.refresh(ayam)
    ci_ayam = cari_cost_item(session, business.id, "ayam")
    assert ayam.cost_item_id == ci_ayam.id
    harga_ayam = session.scalars(
        select(CostItemPrice).where(CostItemPrice.cost_item_id == ci_ayam.id)
    ).one()
    assert harga_ayam.sumber is SumberHarga.transaksi
    assert harga_ayam.transaction_id == ayam.id
    assert harga_ayam.harga_satuan == Decimal("36000.00")


# ── Degradasi jujur & harga yang ditanyakan ─────────────────────────────────


def test_bahan_tanpa_pembelian_jujur(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")  # keju tidak dibeli

    res = atur_resep(
        session, business.id, "kroket", Decimal("8"), "kotak",
        _risol(("tepung", Decimal("1"), "kg"), ("keju", Decimal("0.1"), "kg")),
        TGL,
    )

    assert res.hpp.status is StatusHpp.harga_tidak_lengkap
    assert res.bahan_perlu_harga == ["keju"]
    assert res.hpp.hpp_per_unit is None  # tidak dikarang (aturan #2)
    assert "keju" in res.konfirmasi


def test_harga_ditanya_melengkapi_hpp(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")

    res = atur_resep(
        session, business.id, "kroket", Decimal("10"), "kotak",
        _risol(("tepung", Decimal("1"), "kg"), ("keju", Decimal("0.1"), "kg")),
        TGL,
        harga_bahan={"keju": (Decimal("90000"), "kg")},
    )

    # (1×13000 + 0.1×90000) / 10 = (13000 + 9000)/10 = 2200.
    assert res.hpp.status is StatusHpp.lengkap
    assert res.hpp.hpp_per_unit == Decimal("2200.00")

    keju = cari_cost_item(session, business.id, "keju")
    harga_keju = session.scalars(
        select(CostItemPrice).where(CostItemPrice.cost_item_id == keju.id)
    ).one()
    assert harga_keju.sumber is SumberHarga.ditanya


def test_catat_harga_bahan_menyusul(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")
    res = atur_resep(
        session, business.id, "kroket", Decimal("10"), "kotak",
        _risol(("tepung", Decimal("1"), "kg"), ("keju", Decimal("0.1"), "kg")),
        TGL,
    )
    assert res.hpp.status is StatusHpp.harga_tidak_lengkap

    keju = cari_cost_item(session, business.id, "keju")
    catat_harga_bahan(session, business.id, keju.id, Decimal("90000"), "kg", TGL)

    ulang = hitung_hpp_produk(session, res.product_id, business.id)
    assert ulang.status is StatusHpp.lengkap
    assert ulang.hpp_per_unit == Decimal("2200.00")


# ── Invariant disambiguasi & isolasi tenant ─────────────────────────────────


def test_adopsi_tidak_mencuri_pembelian_reseller(session: Session, business: Business):
    """Pembelian yang sudah tertaut produk (restock reseller) tak boleh diklaim
    jadi bahan — invariant: barang-dagangan XOR bahan."""
    gula = buat_produk(session, business, "gula", JenisProduk.reseller)
    restock = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=Decimal("14000"),
        tanggal=TGL, deskripsi="gula", qty=Decimal("1"), satuan="kg", product_id=gula.id,
    )
    session.add(restock)
    session.flush()

    res = atur_resep(
        session, business.id, "kolak", Decimal("10"), "porsi",
        _risol(("gula", Decimal("0.2"), "kg")), TGL,
    )

    session.refresh(restock)
    assert restock.product_id == gula.id      # tetap milik jalur reseller
    assert restock.cost_item_id is None       # tidak dicuri jadi bahan
    assert res.hpp.status is StatusHpp.harga_tidak_lengkap
    assert res.bahan_perlu_harga == ["gula"]


def test_isolasi_tenant_bahan(session: Session, business: Business, tetangga: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")  # pembelian milik `business`

    atur_resep(
        session, tetangga.id, "roti", Decimal("10"), "buah",
        _risol(("tepung", Decimal("1"), "kg")), TGL,
    )

    # Dua CostItem 'tepung' berbeda; adopsi milik tetangga tak menyentuh pembelian
    # `business`, jadi bahan tetangga belum berharga.
    tepung_kita = cari_cost_item(session, business.id, "tepung")
    tepung_tetangga = cari_cost_item(session, tetangga.id, "tepung")
    assert tepung_kita is None or tepung_kita.id != tepung_tetangga.id
    harga_tetangga = session.scalars(
        select(CostItemPrice).where(CostItemPrice.cost_item_id == tepung_tetangga.id)
    ).all()
    assert harga_tetangga == []


# ── Upsert & promosi ────────────────────────────────────────────────────────


def test_upsert_mengganti_bukan_menggandakan(session: Session, business: Business):
    atur_resep(
        session, business.id, "risol", Decimal("10"), "kotak",
        _risol(("tepung", Decimal("1"), "kg"), ("minyak", Decimal("0.5"), "liter")), TGL,
    )
    atur_resep(
        session, business.id, "risol", Decimal("12"), "kotak",
        _risol(("tepung", Decimal("1.2"), "kg")), TGL,
    )

    resep = session.scalars(select(Recipe)).one()  # unik per product_id
    assert resep.yield_qty == Decimal("12.000")
    items = session.scalars(select(RecipeItem).where(RecipeItem.recipe_id == resep.id)).all()
    assert len(items) == 1


def test_promosi_reseller_ke_produksi(session: Session, business: Business):
    buat_produk(session, business, "risol", JenisProduk.reseller)

    atur_resep(
        session, business.id, "risol", Decimal("10"), "kotak",
        _risol(("tepung", Decimal("1"), "kg")), TGL,
    )

    produk = cari_produk(session, business.id, "risol")
    assert produk.jenis is JenisProduk.produksi

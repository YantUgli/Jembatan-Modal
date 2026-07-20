"""Fixture uji — DB SQLite in-memory, dibangun dari metadata (bukan Alembic).

Membangun skema via `create_all` di memori adalah praktik standar untuk unit
test service layer: cepat, terisolasi, tak menyentuh DB dev.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    Business,
    CostItem,
    CostItemPrice,
    JenisTransaksi,
    Product,
    ProductPrice,
    Recipe,
    RecipeItem,
    SumberHarga,
    SumberInput,
    TipeKomponen,
    Transaction,
    User,
)
from app.models.base import JenisProduk


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as s:
        yield s
    Base.metadata.drop_all(engine)


@pytest.fixture
def business(session: Session) -> Business:
    user = User(nama="Uji", no_hp="0810000TEST")
    session.add(user)
    session.flush()
    biz = Business(user_id=user.id, nama_usaha="Warung Uji")
    session.add(biz)
    session.flush()
    return biz


@pytest.fixture
def tetangga(session: Session) -> Business:
    """Usaha kedua — untuk menguji isolasi tenant (prinsip #6)."""
    user = User(nama="Tetangga", no_hp="0810001TEST")
    session.add(user)
    session.flush()
    biz = Business(user_id=user.id, nama_usaha="Warung Tetangga")
    session.add(biz)
    session.flush()
    return biz


# ── Builder ringkas untuk menyusun skenario di test ──


def buat_material(session: Session, business: Business, nama: str, satuan: str = "kg") -> CostItem:
    ci = CostItem(business_id=business.id, tipe=TipeKomponen.material, nama=nama, satuan_baku=satuan)
    session.add(ci)
    session.flush()
    return ci


def set_harga(session: Session, ci: CostItem, harga, tanggal, satuan: str = "kg") -> None:
    session.add(CostItemPrice(
        cost_item_id=ci.id, harga_satuan=harga, satuan=satuan, tanggal=tanggal,
        sumber=SumberHarga.ditanya,
    ))
    session.flush()


def buat_produk(
    session: Session,
    business: Business,
    nama: str,
    jenis: JenisProduk,
    harga_jual=None,
    *,
    satuan_beli: str | None = None,
    satuan_jual: str | None = None,
    isi_per_satuan_beli=None,
    faktor_kehilangan=None,
) -> Product:
    """`harga_jual` = jalan pintas untuk satu baris `product_prices` umum.
    Empat argumen kata-kunci terakhir = jalur reseller (susut & konversi satuan).
    """
    p = Product(
        business_id=business.id,
        nama=nama,
        jenis=jenis,
        satuan_beli=satuan_beli,
        satuan_jual=satuan_jual,
        isi_per_satuan_beli=isi_per_satuan_beli,
        faktor_kehilangan=faktor_kehilangan,
    )
    session.add(p)
    session.flush()
    if harga_jual is not None:
        set_harga_jual(session, p, harga_jual)
    return p


def set_harga_jual(
    session: Session,
    product: Product,
    harga,
    *,
    kanal: str | None = None,
    grade: str | None = None,
    min_qty=None,
    berlaku_dari: date = date(2020, 1, 1),
) -> ProductPrice:
    """Tambah satu baris harga jual (append-only, bertanggal)."""
    pp = ProductPrice(
        product_id=product.id, kanal=kanal, grade=grade, min_qty=min_qty,
        harga=harga, berlaku_dari=berlaku_dari,
    )
    session.add(pp)
    session.flush()
    return pp


def buat_transaksi(
    session: Session,
    business: Business,
    jenis: JenisTransaksi,
    nominal,
    tanggal,
    *,
    kategori_detail: str | None = None,
    product: Product | None = None,
    qty=None,
    satuan: str | None = None,
) -> Transaction:
    t = Transaction(
        business_id=business.id,
        jenis=jenis,
        nominal=nominal,
        tanggal=tanggal,
        kategori_detail=kategori_detail,
        product_id=product.id if product is not None else None,
        qty=qty,
        satuan=satuan,
        sumber_input=SumberInput.chat,
    )
    session.add(t)
    session.flush()
    return t


def buat_resep(
    session: Session,
    product: Product,
    yield_qty,
    bahan: list[tuple],
    yield_satuan: str = "unit",
    faktor_kehilangan=None,
) -> Recipe:
    """bahan = list of (komponen, qty, satuan).

    `komponen` boleh `CostItem` (bahan dibeli) **atau** `Product` (sub-produk).
    `yield_satuan` penting saat produk ini dipakai sebagai sub-produk: satuan
    pemakaian di resep induk harus sama dengannya.
    `faktor_kehilangan` = pecahan 0..<1 (0,025 = susut 2,5%).
    """
    r = Recipe(
        product_id=product.id,
        yield_qty=yield_qty,
        yield_satuan=yield_satuan,
        faktor_kehilangan=faktor_kehilangan,
    )
    session.add(r)
    session.flush()
    for komponen, qty, satuan in bahan:
        baris = RecipeItem(recipe_id=r.id, qty=qty, satuan=satuan)
        if isinstance(komponen, Product):
            baris.product_id = komponen.id
        else:
            baris.cost_item_id = komponen.id
        session.add(baris)
    session.flush()
    return r

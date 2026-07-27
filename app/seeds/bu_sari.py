"""Seeder data demo Bu Sari — ±2 bulan transaksi.

Bu Sari (§ konsep-produk §3): katering & frozen food rumahan, Bandung.
Sengaja produsen (risol, kroket) + satu barang reseller (nugget beli-jadi)
agar kedua jalur HPP hidup di data nyata. Sebagian pemasukan tanpa produk
terkenali ("titipan kue") sehingga cakupan HPP wajar di bawah 100%.

Idempoten: kalau Bu Sari sudah ada, tidak menyeed ulang.

Kredensial demo untuk login UI: no.HP `08120000001`, PIN `123456`.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Business,
    CostItem,
    CostItemPrice,
    JenisProduk,
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
from app.services.auth import hash_pin

NO_HP = "08120000001"
PIN_DEMO = "123456"  # kredensial demo: login no.HP di atas + PIN ini
MULAI = date(2026, 5, 18)
SELESAI = date(2026, 7, 17)  # currentDate = 2026-07-18


def _material(session: Session, business_id: int, nama: str, satuan: str) -> CostItem:
    ci = CostItem(
        business_id=business_id, tipe=TipeKomponen.material, nama=nama, satuan_baku=satuan
    )
    session.add(ci)
    session.flush()
    return ci


def _harga(session: Session, ci: CostItem, harga: float, satuan: str, tanggal: date) -> None:
    session.add(
        CostItemPrice(
            cost_item_id=ci.id,
            harga_satuan=harga,
            satuan=satuan,
            tanggal=tanggal,
            sumber=SumberHarga.ditanya,
        )
    )


def sudah_terseed(session: Session) -> bool:
    return session.scalar(select(User).where(User.no_hp == NO_HP)) is not None


def seed(session: Session) -> Business:
    """Isi DB dengan data demo Bu Sari. Kembalikan Business-nya."""
    existing = session.scalar(select(User).where(User.no_hp == NO_HP))
    if existing is not None:
        # Backfill PIN demo bila DB lama sudah ter-seed sebelum ada auth.
        if existing.pin_hash is None:
            existing.pin_hash = hash_pin(PIN_DEMO)
            session.flush()
        biz = session.scalar(select(Business).where(Business.user_id == existing.id))
        assert biz is not None
        return biz

    rng = random.Random(42)  # deterministik

    user = User(nama="Bu Sari", no_hp=NO_HP, pin_hash=hash_pin(PIN_DEMO))
    session.add(user)
    session.flush()

    biz = Business(
        user_id=user.id,
        nama_usaha="Katering & Frozen Food Bu Sari",
        jenis_usaha="katering & frozen food rumahan",
        lokasi="Bandung",
        mulai_usaha=date(2024, 3, 1),
    )
    session.add(biz)
    session.flush()

    # ── Bahan (material) + harga bertanggal (append-only) ──
    tepung = _material(session, biz.id, "tepung terigu", "kg")
    minyak = _material(session, biz.id, "minyak goreng", "liter")
    ayam = _material(session, biz.id, "ayam", "kg")
    kentang = _material(session, biz.id, "kentang", "kg")
    keju = _material(session, biz.id, "keju", "kg")

    # dua tanggal harga → "harga terakhir" deterministik (yang belakangan menang)
    _harga(session, tepung, 12000, "kg", MULAI)
    _harga(session, tepung, 13000, "kg", MULAI + timedelta(days=30))
    _harga(session, minyak, 18000, "liter", MULAI)
    _harga(session, minyak, 19000, "liter", MULAI + timedelta(days=30))
    _harga(session, ayam, 34000, "kg", MULAI)
    _harga(session, ayam, 36000, "kg", MULAI + timedelta(days=30))
    _harga(session, kentang, 14000, "kg", MULAI)
    _harga(session, keju, 90000, "kg", MULAI)

    # ── Produk produksi + resep ──
    risol = Product(business_id=biz.id, nama="risol", jenis=JenisProduk.produksi)
    kroket = Product(business_id=biz.id, nama="kroket", jenis=JenisProduk.produksi)
    # reseller: nugget dibeli jadi lalu dijual lagi
    nugget = Product(business_id=biz.id, nama="nugget frozen", jenis=JenisProduk.reseller)
    session.add_all([risol, kroket, nugget])
    session.flush()

    # Harga jual hidup di `product_prices` (bertanggal & berkanal), bukan kolom
    # skalar di `products`. Nugget punya dua kanal: eceran & tebus reseller.
    session.add_all([
        ProductPrice(product_id=risol.id, harga=15000, berlaku_dari=MULAI),
        ProductPrice(product_id=kroket.id, harga=12000, berlaku_dari=MULAI),
        ProductPrice(product_id=nugget.id, harga=30000, berlaku_dari=MULAI),
        # Tebus reseller: margin tipis tapi tetap positif (HPP nugget ± 26.000).
        # Sengaja dijaga di atas HPP — data demo tidak boleh terbaca seperti bug.
        ProductPrice(product_id=nugget.id, kanal="reseller", harga=28000, berlaku_dari=MULAI),
    ])
    session.flush()

    # resep risol: yield 10 kotak → tepung 1kg + minyak 0.5L + ayam 0.5kg
    r_risol = Recipe(product_id=risol.id, yield_qty=10, yield_satuan="kotak")
    session.add(r_risol)
    session.flush()
    session.add_all([
        RecipeItem(recipe_id=r_risol.id, cost_item_id=tepung.id, qty=1, satuan="kg"),
        RecipeItem(recipe_id=r_risol.id, cost_item_id=minyak.id, qty=0.5, satuan="liter"),
        RecipeItem(recipe_id=r_risol.id, cost_item_id=ayam.id, qty=0.5, satuan="kg"),
    ])

    # resep kroket: yield 8 → kentang 1kg + tepung 0.25kg + keju 0.1kg
    r_kroket = Recipe(product_id=kroket.id, yield_qty=8, yield_satuan="kotak")
    session.add(r_kroket)
    session.flush()
    session.add_all([
        RecipeItem(recipe_id=r_kroket.id, cost_item_id=kentang.id, qty=1, satuan="kg"),
        RecipeItem(recipe_id=r_kroket.id, cost_item_id=tepung.id, qty=0.25, satuan="kg"),
        RecipeItem(recipe_id=r_kroket.id, cost_item_id=keju.id, qty=0.1, satuan="kg"),
    ])

    # ── Pembelian nugget (reseller) — menetapkan harga beli terakhir ──
    session.add(Transaction(
        business_id=biz.id, jenis=JenisTransaksi.pengeluaran, nominal=250000,
        deskripsi="kulakan nugget 10 pack", tanggal=MULAI, sumber_input=SumberInput.manual,
        product_id=nugget.id, qty=10, satuan="pack",
    ))
    session.add(Transaction(
        business_id=biz.id, jenis=JenisTransaksi.pengeluaran, nominal=260000,
        deskripsi="kulakan nugget 10 pack", tanggal=MULAI + timedelta(days=28),
        sumber_input=SumberInput.manual, product_id=nugget.id, qty=10, satuan="pack",
    ))

    # ── ±2 bulan penjualan & pengeluaran harian ──
    hari = MULAI
    while hari <= SELESAI:
        # risol tiap hari
        q = rng.randint(3, 6)
        session.add(Transaction(
            business_id=biz.id, jenis=JenisTransaksi.pemasukan, nominal=q * 15000,
            deskripsi=f"risol {q} kotak", tanggal=hari, sumber_input=SumberInput.chat,
            product_id=risol.id, qty=q, satuan="kotak",
            raw_text=f"laku {q} kotak risol {q * 15}rb",
        ))
        # kroket tiap 2 hari
        if hari.toordinal() % 2 == 0:
            qk = rng.randint(2, 5)
            session.add(Transaction(
                business_id=biz.id, jenis=JenisTransaksi.pemasukan, nominal=qk * 12000,
                deskripsi=f"kroket {qk} kotak", tanggal=hari, sumber_input=SumberInput.chat,
                product_id=kroket.id, qty=qk, satuan="kotak",
            ))
        # nugget tiap 3 hari
        if hari.toordinal() % 3 == 0:
            qn = rng.randint(1, 3)
            session.add(Transaction(
                business_id=biz.id, jenis=JenisTransaksi.pemasukan, nominal=qn * 30000,
                deskripsi=f"nugget {qn} pack", tanggal=hari, sumber_input=SumberInput.chat,
                product_id=nugget.id, qty=qn, satuan="pack",
            ))
        # titipan kue tetangga — pemasukan TANPA produk terkenali (menekan cakupan)
        if hari.weekday() == 5:  # Sabtu
            session.add(Transaction(
                business_id=biz.id, jenis=JenisTransaksi.pemasukan, nominal=rng.randint(30, 80) * 1000,
                deskripsi="titipan kue tetangga", tanggal=hari, sumber_input=SumberInput.chat,
                raw_text="jual titipan kue",
            ))
        hari += timedelta(days=1)

    # ── beberapa operasional & prive ──
    for offset in (7, 21, 35, 49):
        t = MULAI + timedelta(days=offset)
        session.add(Transaction(
            business_id=biz.id, jenis=JenisTransaksi.operasional, nominal=rng.randint(10, 25) * 1000,
            deskripsi="gas & plastik kemasan", tanggal=t, sumber_input=SumberInput.chat,
        ))
    for offset in (10, 24, 40):
        t = MULAI + timedelta(days=offset)
        session.add(Transaction(
            business_id=biz.id, jenis=JenisTransaksi.prive, nominal=rng.randint(40, 100) * 1000,
            deskripsi="ambil buat jajan anak", tanggal=t, sumber_input=SumberInput.chat,
            raw_text="ambil buat anak",
        ))

    session.flush()
    return biz


def main() -> None:
    from app.db import session_scope

    with session_scope() as session:
        biz = seed(session)
        print(f"Seed selesai untuk business_id={biz.id} ({biz.nama_usaha}).")


if __name__ == "__main__":
    main()

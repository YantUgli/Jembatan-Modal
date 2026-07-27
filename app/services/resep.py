"""Service `atur_resep` (Pilar 4, jalur produksi) — inti deterministik.

Loop produksi = analog produksi dari loop reseller: pemilik **menyatakan** resep,
lalu melihat modal per porsi jujur atas data sendiri. Mesin HPP produksi
(`hpp._hpp_produksi`) sudah ada & teruji; di sinilah **jalan masuk data**-nya
dibangun — `Recipe` + `RecipeItem` + `CostItem` + harga bahan.

Deterministik, **tanpa LLM** (aturan #1). Harga satuan bahan (`nominal ÷ qty`)
dihitung service, bukan model. Isolasi tenant (aturan #6): setiap resolusi & query
difilter `business_id`.

⛔ **`atur_resep` hanya jalur produksi** (aturan #8): menetapkan resep adalah
sinyal produksi yang *dinyatakan pengguna*. `CostItem` dibuat di sini karena
pengguna menyebutnya sebagai bahan — bukan ditebak dari belanja, yang akan salah
mengklaim barang dagangan reseller sebagai bahan (dan merusak loop reseller).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    CostItem,
    CostItemPrice,
    JenisProduk,
    JenisTransaksi,
    Product,
    Recipe,
    RecipeItem,
    SumberHarga,
    Transaction,
)
from app.services.angka import _dec, _uang, rupiah
from app.services.entitas import _normalisasi_nama, resolusi_cost_item, resolusi_produk
from app.services.hpp import (
    HasilHpp,
    StatusHpp,
    hitung_hpp_produk,
    simpan_snapshot_semua,
)

__all__ = [
    "HasilAturResep",
    "atur_resep",
    "catat_harga_bahan",
    "rangkai_hasil",
]


@dataclass
class HasilAturResep:
    product_id: int
    nama: str
    recipe_id: int
    hpp: HasilHpp
    bahan_perlu_harga: list[str] = field(default_factory=list)
    konfirmasi: str = ""


def catat_harga_bahan(
    session: Session,
    business_id: int,
    cost_item_id: int,
    harga: Decimal,
    satuan: str | None,
    tanggal: date,
    sumber: SumberHarga = SumberHarga.ditanya,
) -> CostItemPrice:
    """Catat harga sebuah bahan (append-only, bertanggal).

    Jalur "harga yang **ditanyakan**" (`sumber=ditanya`) — dipakai juga oleh NL
    follow-up saat pengguna menjawab "keju sekilo 90rb". Bahan wajib milik usaha
    ini (aturan #6): diperiksa di query, bukan dipercayakan pemanggil.
    """
    ci = session.scalars(
        select(CostItem).where(
            CostItem.id == cost_item_id, CostItem.business_id == business_id
        )
    ).first()
    if ci is None:
        raise ValueError(f"Bahan {cost_item_id} tidak ditemukan untuk usaha {business_id}.")

    pp = CostItemPrice(
        cost_item_id=ci.id,
        harga_satuan=_uang(_dec(harga)),
        satuan=satuan,
        tanggal=tanggal,
        sumber=sumber,
    )
    session.add(pp)
    session.flush()
    return pp


def _adopsi_harga_dari_pembelian(
    session: Session, business_id: int, cost_item: CostItem
) -> list[CostItemPrice]:
    """Serap harga bahan dari transaksi pembelian yang namanya cocok.

    Analog `entitas.adopsi_pembelian_yatim` (loop reseller), tapi menghasilkan
    `cost_item_prices` (`sumber=transaksi`) alih-alih menautkan produk. Hanya
    pembelian **yatim penuh** (`product_id` & `cost_item_id` sama-sama NULL, belum
    dibatalkan, `qty > 0`) ber-`deskripsi` sama-persis yang diadopsi — restock
    reseller yang sudah tertaut tak terusik (invariant disambiguasi).

    Beberapa pembelian pada tanggal berbeda → beberapa baris harga (riwayat;
    `hpp._harga_terakhir` memilih yang terbaru). Re-adopsi mustahil: begitu
    `cost_item_id` terisi, pembelian itu bukan yatim lagi.
    """
    target = _normalisasi_nama(cost_item.nama)
    if target is None:
        return []

    calon = session.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.jenis == JenisTransaksi.pengeluaran,
            Transaction.product_id.is_(None),
            Transaction.cost_item_id.is_(None),
            Transaction.dibatalkan_pada.is_(None),
            Transaction.qty.is_not(None),
            Transaction.qty > 0,
        )
    ).all()

    dibuat: list[CostItemPrice] = []
    for t in calon:
        if _normalisasi_nama(t.deskripsi) != target:
            continue
        harga_unit = _dec(t.nominal) / _dec(t.qty)
        pp = CostItemPrice(
            cost_item_id=cost_item.id,
            harga_satuan=_uang(harga_unit),
            satuan=t.satuan,
            tanggal=t.tanggal,
            sumber=SumberHarga.transaksi,
            transaction_id=t.id,
        )
        session.add(pp)
        t.cost_item_id = cost_item.id
        dibuat.append(pp)
    if dibuat:
        session.flush()
    return dibuat


def atur_resep(
    session: Session,
    business_id: int,
    nama_produk: str,
    yield_qty: Decimal,
    yield_satuan: str | None,
    bahan: list[tuple[str, Decimal, str | None]],
    hari_ini: date,
    harga_bahan: dict[str, tuple[Decimal, str | None]] | None = None,
) -> HasilAturResep:
    """Tetapkan resep sebuah produk → HPP produksi atas data sendiri.

    `bahan` = daftar `(nama, qty, satuan)`. `harga_bahan` = harga yang
    **ditanyakan** langsung, `{nama: (harga, satuan)}` — opsional; sisanya
    diserap dari pembelian. Menetapkan resep mempromosikan `jenis → produksi`
    (promosi eksplisit, aturan #8).
    """
    produk, _ = resolusi_produk(session, business_id, nama_produk)
    produk.jenis = JenisProduk.produksi

    # Upsert: resep = konfigurasi (mutable), bukan buku uang. "Atur" = set —
    # panggilan berikutnya mengganti isinya, tidak menggandakan.
    recipe = session.scalars(
        select(Recipe).where(Recipe.product_id == produk.id)
    ).first()
    if recipe is None:
        recipe = Recipe(product_id=produk.id, yield_qty=yield_qty, yield_satuan=yield_satuan)
        session.add(recipe)
        session.flush()
    else:
        recipe.yield_qty = yield_qty
        recipe.yield_satuan = yield_satuan
        recipe.updated_at = datetime.now()
        session.execute(delete(RecipeItem).where(RecipeItem.recipe_id == recipe.id))
        session.flush()

    # Bahan → CostItem (dibuat bila baru) + baris resep. Simpan peta nama→bahan
    # untuk mencocokkan `harga_bahan` yang ditanyakan.
    peta: dict[str, CostItem] = {}
    for nama, qty, satuan in bahan:
        ci, _ = resolusi_cost_item(session, business_id, nama, satuan)
        session.add(
            RecipeItem(recipe_id=recipe.id, cost_item_id=ci.id, qty=qty, satuan=satuan)
        )
        kunci = _normalisasi_nama(nama)
        if kunci is not None:
            peta[kunci] = ci
    session.flush()

    # Harga: serap dari pembelian, lalu timpa/lengkapi dengan yang ditanyakan.
    for ci in peta.values():
        _adopsi_harga_dari_pembelian(session, business_id, ci)
    for nama, (harga, satuan) in (harga_bahan or {}).items():
        ci = peta.get(_normalisasi_nama(nama) or "")
        if ci is not None:
            catat_harga_bahan(
                session, business_id, ci.id, harga, satuan, hari_ini,
                sumber=SumberHarga.ditanya,
            )

    hasil = hitung_hpp_produk(session, produk.id, business_id)

    # Bukan cuma produk ini: harga bahan yang baru diserap/ditanya di atas dipakai
    # bersama produk lain, dan menjalar lewat sub-produk. Snapshot seluruh usaha.
    simpan_snapshot_semua(session, business_id)

    return HasilAturResep(
        product_id=produk.id,
        nama=produk.nama,
        recipe_id=recipe.id,
        hpp=hasil,
        bahan_perlu_harga=list(hasil.bahan_kurang_harga),
        konfirmasi=_konfirmasi(hasil),
    )


def rangkai_hasil(
    session: Session, business_id: int, product_id: int
) -> HasilAturResep | None:
    """Bungkus ulang HPP produk jadi `HasilAturResep` (tanpa mengubah resep).

    Dipakai setelah harga bahan menyusul (mis. jawaban tanya-jawab) untuk
    menghitung ulang modal per porsi & merangkai konfirmasi yang sama. Tenant
    diperiksa di query (aturan #6): produk bukan milik usaha ini → `None`.
    """
    produk = session.scalars(
        select(Product).where(
            Product.id == product_id, Product.business_id == business_id
        )
    ).first()
    if produk is None:
        return None
    recipe = session.scalars(
        select(Recipe).where(Recipe.product_id == produk.id)
    ).first()
    hasil = hitung_hpp_produk(session, produk.id, business_id)
    return HasilAturResep(
        product_id=produk.id,
        nama=produk.nama,
        recipe_id=recipe.id if recipe is not None else 0,
        hpp=hasil,
        bahan_perlu_harga=list(hasil.bahan_kurang_harga),
        konfirmasi=_konfirmasi(hasil),
    )


def _konfirmasi(hasil: HasilHpp) -> str:
    """Konfirmasi dirender template kode (bukan LLM kedua), bahasa warung.

    ⛔ Bukan "untung usaha" (aturan #9): ini modal per porsi. Bila belum bisa
    dihitung, mengaku jujur + sebut bahan yang kurang (aturan #2), bukan Rp0.
    """
    if hasil.status is StatusHpp.lengkap and hasil.hpp_per_unit is not None:
        satuan = f" per {hasil.satuan_hpp}" if hasil.satuan_hpp else " per porsi"
        return f"Resep {hasil.nama} tercatat. Modal{satuan} sekitar {rupiah(hasil.hpp_per_unit)}."
    kepala = f"Resep {hasil.nama} tercatat, tapi modal per porsi belum bisa dihitung"
    if hasil.bahan_kurang_harga:
        return f"{kepala} — harga bahan ini belum tercatat: {', '.join(hasil.bahan_kurang_harga)}."
    return f"{kepala}."

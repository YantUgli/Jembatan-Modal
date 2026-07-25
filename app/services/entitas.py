"""Resolver entitas — menautkan kalimat pencatatan ke `Product` (Pilar 1→4).

Tanpa resolver ini, transaksi dari chat tersimpan dengan `product_id = NULL` dan
**tak pernah menyentuh HPP**: seluruh mesin Pilar 4 menyaring lewat
`Transaction.product_id`. Di sinilah "saluran bahan bakar" dari bahasa warung ke
kalkulasi HPP disambung.

Deterministik, **tanpa LLM** (aturan #1). Isolasi tenant (aturan #6): setiap
query difilter `business_id` — nama produk sama di dua usaha = dua produk berbeda.

⛔ **`jenis` produk baru default `reseller`** (keputusan pemilik). Tebakan default
yang salah terdegradasi jujur (HPP `belum_ada_harga_beli`), dan yang terpenting:
reseller **tak pernah** ditawari wawancara resep (larangan keras aturan #8).
Produksi ditegakkan eksplisit lewat `atur_resep` nanti — bukan ditebak dari satu
kalimat jual.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CostItem,
    JenisProduk,
    JenisTransaksi,
    Product,
    TipeKomponen,
    Transaction,
)

__all__ = [
    "adopsi_pembelian_yatim",
    "cari_cost_item",
    "cari_produk",
    "resolusi_cost_item",
    "resolusi_produk",
]


def _normalisasi_nama(nama: str | None) -> str | None:
    """Normalisasi minimal: spasi & besar-kecil huruf saja.

    Sejalan filosofi `hpp._samakan_satuan` — **bandingkan, jangan tebak**. Tidak
    ada tabel sinonim ("nugget" ≠ "naget"); menebak maksud pengguna dari string
    nama adalah mengarang tautan lewat pintu belakang.
    """
    if nama is None:
        return None
    bersih = nama.strip().casefold()
    return bersih or None


def cari_produk(session: Session, business_id: int, nama: str) -> Product | None:
    """Produk milik usaha ini yang namanya cocok — **find-only, tidak membuat**.

    Kandidat difilter `business_id` di query (aturan #6); pencocokan nama dilakukan
    di Python dengan `_normalisasi_nama` (set per-tenant kecil). Bila ada lebih
    dari satu yang cocok, yang `id`-nya terkecil menang (deterministik).
    """
    target = _normalisasi_nama(nama)
    if target is None:
        return None
    kandidat = session.scalars(
        select(Product)
        .where(Product.business_id == business_id)
        .order_by(Product.id)
    ).all()
    for p in kandidat:
        if _normalisasi_nama(p.nama) == target:
            return p
    return None


def resolusi_produk(session: Session, business_id: int, nama: str) -> tuple[Product, bool]:
    """Find-or-create. Kembalikan `(produk, dibuat_baru)`.

    Produk baru dibuat `jenis=reseller` (default aman-gagal, lihat modul).
    """
    ada = cari_produk(session, business_id, nama)
    if ada is not None:
        return ada, False

    produk = Product(business_id=business_id, nama=nama.strip(), jenis=JenisProduk.reseller)
    session.add(produk)
    session.flush()
    return produk, True


def cari_cost_item(session: Session, business_id: int, nama: str) -> CostItem | None:
    """Bahan (`CostItem`) milik usaha ini yang namanya cocok — find-only.

    Sejajar `cari_produk`: difilter `business_id` (aturan #6), pencocokan nama
    lewat `_normalisasi_nama`, `id` terkecil menang bila lebih dari satu.
    """
    target = _normalisasi_nama(nama)
    if target is None:
        return None
    kandidat = session.scalars(
        select(CostItem)
        .where(CostItem.business_id == business_id)
        .order_by(CostItem.id)
    ).all()
    for ci in kandidat:
        if _normalisasi_nama(ci.nama) == target:
            return ci
    return None


def resolusi_cost_item(
    session: Session, business_id: int, nama: str, satuan: str | None = None
) -> tuple[CostItem, bool]:
    """Find-or-create bahan. Kembalikan `(cost_item, dibuat_baru)`.

    ⛔ Selalu `tipe=material` (aturan #7): `labor_time`/`overhead` adalah slot,
    tak pernah dibuat di sini. Penciptaannya dipicu resep (pengguna menyatakan
    "ini bahannya") — bukan ditebak dari belanja, yang akan salah mengklaim
    barang dagangan reseller sebagai bahan.
    """
    ada = cari_cost_item(session, business_id, nama)
    if ada is not None:
        return ada, False

    ci = CostItem(
        business_id=business_id,
        tipe=TipeKomponen.material,
        nama=nama.strip(),
        satuan_baku=satuan,
    )
    session.add(ci)
    session.flush()
    return ci, True


def adopsi_pembelian_yatim(
    session: Session, business_id: int, product: Product
) -> list[Transaction]:
    """Tautkan pembelian **yatim** ke produk yang baru dibuat dari penjualan.

    Menutup urutan alami warung *beli-dulu-baru-jual*: saat "beli nugget 250rb"
    dicatat, produknya belum ada sehingga pembeliannya belum tertaut. Begitu
    penjualan pertama melahirkan produknya, pembelian itu diadopsi supaya
    `hpp._hpp_reseller` (yang membaca "harga beli terakhir" dari `pengeluaran`
    ber-`product_id`) langsung punya modal.

    Yang diadopsi hanya `pengeluaran` yang: belum tertaut produk **maupun**
    komponen biaya, belum dibatalkan, dan `deskripsi`-nya **sama-persis** (setelah
    normalisasi) dengan nama produk. Kecocokan longgar sengaja tidak diadopsi —
    tautan salah lebih berbahaya daripada satu pembelian yang menunggu kulakan
    berikutnya. Isolasi tenant: difilter `business_id` di query (aturan #6).
    """
    target = _normalisasi_nama(product.nama)
    if target is None:
        return []

    calon = session.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.jenis == JenisTransaksi.pengeluaran,
            Transaction.product_id.is_(None),
            Transaction.cost_item_id.is_(None),
            Transaction.dibatalkan_pada.is_(None),
        )
    ).all()

    diadopsi: list[Transaction] = []
    for t in calon:
        if _normalisasi_nama(t.deskripsi) == target:
            t.product_id = product.id
            diadopsi.append(t)
    if diadopsi:
        session.flush()
    return diadopsi

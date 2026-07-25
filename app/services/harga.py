"""Service harga jual majemuk (Pilar 4) — satu produk, banyak harga.

Deterministik, ber-unit-test. LLM tidak pernah masuk ke sini (prinsip #1).

Satu produk bisa punya harga berbeda menurut **kanal** (eceran vs tebus reseller
vs resto), **grade** (A/B), dan **tier kuantitas** (50/100/300/500 pcs). Ketiganya
muncul di kasus lapangan yang sama, jadi ditangani satu mekanisme, bukan tiga.

Aturan pemilihan — **yang paling spesifik menang**:

    1. Buang baris yang belum berlaku (`berlaku_dari` > tanggal).
    2. Buang baris yang tidak cocok: `kanal`/`grade` terisi tapi beda dengan yang
       diminta; `min_qty` di atas kuantitas yang diminta.
       Kolom NULL = berlaku umum → selalu lolos.
    3. Urutkan: cocok-kanal > umum, lalu cocok-grade > umum, lalu `min_qty`
       terbesar (tier tertinggi yang masih terpenuhi), lalu `berlaku_dari`
       terbaru, lalu `id` terbesar.
    4. Ambil yang teratas. Tidak ada yang cocok → **None**, bukan tebakan.

Kalau tidak ada harga yang cocok, laba tidak dihitung. "Belum diketahui" lebih
jujur daripada memakai harga kanal lain diam-diam (aturan #2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductPrice
from app.services.angka import _dec, _uang


@dataclass
class HargaTerpilih:
    harga: Decimal
    kanal: str | None
    grade: str | None
    min_qty: Decimal | None
    berlaku_dari: date
    catatan: str | None = None

    @property
    def umum(self) -> bool:
        """True bila baris ini tidak menyaring apa pun (harga default produk)."""
        return self.kanal is None and self.grade is None and self.min_qty is None

    def sebagai_teks(self) -> str:
        bagian = []
        if self.kanal:
            bagian.append(f"kanal {self.kanal}")
        if self.grade:
            bagian.append(f"grade {self.grade}")
        if self.min_qty is not None:
            bagian.append(f"mulai {self.min_qty} unit")
        rinci = ", ".join(bagian) if bagian else "harga umum"
        return f"{rinci}, berlaku sejak {self.berlaku_dari.isoformat()}"


def _cocok(
    baris: ProductPrice, kanal: str | None, grade: str | None, qty: Decimal | None
) -> bool:
    if baris.kanal is not None and baris.kanal != kanal:
        return False
    if baris.grade is not None and baris.grade != grade:
        return False
    if baris.min_qty is not None:
        # Tier tanpa kuantitas yang diminta tidak bisa diverifikasi — jangan dipakai.
        if qty is None or _dec(qty) < _dec(baris.min_qty):
            return False
    return True


def _kekhususan(baris: ProductPrice) -> tuple:
    """Kunci urut: makin spesifik makin dulu, seri diputus tanggal lalu id."""
    return (
        1 if baris.kanal is not None else 0,
        1 if baris.grade is not None else 0,
        _dec(baris.min_qty) if baris.min_qty is not None else Decimal("-1"),
        baris.berlaku_dari,
        baris.id,
    )


def harga_jual_berlaku(
    session: Session,
    product_id: int,
    business_id: int,
    *,
    tanggal: date | None = None,
    kanal: str | None = None,
    grade: str | None = None,
    qty=None,
) -> HargaTerpilih | None:
    """Harga jual yang berlaku untuk satu produk pada konteks tertentu.

    `business_id` wajib (isolasi tenant, prinsip #6). Mengembalikan None bila
    tidak ada baris harga yang cocok — pemanggil wajib memperlakukan itu sebagai
    "belum diketahui", bukan nol.
    """
    produk = session.scalars(
        select(Product).where(Product.id == product_id, Product.business_id == business_id)
    ).first()
    if produk is None:
        raise ValueError(f"Produk {product_id} tidak ditemukan untuk usaha {business_id}.")

    tanggal = tanggal or date.today()
    baris = session.scalars(
        select(ProductPrice).where(
            ProductPrice.product_id == product_id,
            ProductPrice.berlaku_dari <= tanggal,
        )
    ).all()

    qty_dec = _dec(qty) if qty is not None else None
    kandidat = [b for b in baris if _cocok(b, kanal, grade, qty_dec)]
    if not kandidat:
        return None

    pilihan = max(kandidat, key=_kekhususan)
    return HargaTerpilih(
        harga=_uang(_dec(pilihan.harga)),
        kanal=pilihan.kanal,
        grade=pilihan.grade,
        min_qty=_dec(pilihan.min_qty) if pilihan.min_qty is not None else None,
        berlaku_dari=pilihan.berlaku_dari,
        catatan=pilihan.catatan,
    )


def catat_harga_jual_dari_penjualan(
    session: Session,
    product_id: int,
    business_id: int,
    harga_unit: Decimal,
    tanggal: date,
) -> ProductPrice | None:
    """Tangkap harga jual dari sebuah penjualan → `product_prices` (append-only).

    HPP membaca **modal** dari pembelian, tapi **harga jual** dari `product_prices`
    — yang jalur chat tak pernah isi. Tanpa ini, loop reseller hanya menampilkan
    modal, bukan untung. Harga satuan (`harga_unit = nominal ÷ qty`) dihitung
    service pemanggil, deterministik — LLM tidak dilibatkan (aturan #1).

    **Dedup** (meniru `hpp.simpan_snapshot_hpp`): hanya menulis baris baru bila
    harga umum yang berlaku pada `tanggal` memang berbeda. Menulis satu baris tiap
    penjualan hanya mengubur sinyal perubahan harga; `harga_jual_berlaku` sudah
    memilih yang terbaru, jadi baris identik tak menambah apa pun.

    `kanal`/`grade`/`min_qty` = NULL (umum): satu kalimat jual tak mengungkap
    kanal. Berlaku untuk semua `jenis` produk — harga jual valid bagi reseller
    maupun produksi, jadi bukan kode khusus-reseller.
    """
    nilai = _uang(harga_unit)
    umum = harga_jual_berlaku(session, product_id, business_id, tanggal=tanggal)
    if umum is not None and umum.umum and umum.harga == nilai:
        return None

    pp = ProductPrice(
        product_id=product_id,
        harga=nilai,
        berlaku_dari=tanggal,
        catatan="dari catatan penjualan",
    )
    session.add(pp)
    session.flush()
    return pp


def daftar_harga(
    session: Session, product_id: int, business_id: int, *, tanggal: date | None = None
) -> list[HargaTerpilih]:
    """Semua harga yang sedang berlaku, terurut dari yang paling spesifik.

    Dipakai untuk menjawab "untung berapa kalau dijual eceran vs ke reseller"
    tanpa memaksa pemanggil menebak daftar kanalnya.
    """
    produk = session.scalars(
        select(Product).where(Product.id == product_id, Product.business_id == business_id)
    ).first()
    if produk is None:
        raise ValueError(f"Produk {product_id} tidak ditemukan untuk usaha {business_id}.")

    tanggal = tanggal or date.today()
    baris = session.scalars(
        select(ProductPrice).where(
            ProductPrice.product_id == product_id,
            ProductPrice.berlaku_dari <= tanggal,
        )
    ).all()
    # Untuk tiap kombinasi penyaring, hanya yang terbaru yang masih berlaku.
    terbaru: dict[tuple, ProductPrice] = {}
    for b in baris:
        kunci = (b.kanal, b.grade, _dec(b.min_qty) if b.min_qty is not None else None)
        ada = terbaru.get(kunci)
        if ada is None or (b.berlaku_dari, b.id) > (ada.berlaku_dari, ada.id):
            terbaru[kunci] = b

    return [
        HargaTerpilih(
            harga=_uang(_dec(b.harga)),
            kanal=b.kanal,
            grade=b.grade,
            min_qty=_dec(b.min_qty) if b.min_qty is not None else None,
            berlaku_dari=b.berlaku_dari,
            catatan=b.catatan,
        )
        for b in sorted(terbaru.values(), key=_kekhususan, reverse=True)
    ]

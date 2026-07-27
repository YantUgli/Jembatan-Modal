"""Tool resep — kalimat pemilik → resep tersimpan + modal per porsi.

Pembungkus tipis di atas `services.resep.atur_resep`: ekstraksi bahasa-natural
(`ekstrak_resep`) di depan, service deterministik di belakang. Sejalan
`catat_transaksi`: dua keluaran jujur —

    HasilAturResep — resep tersimpan, dengan HPP + konfirmasi bisa dibaca ulang.
    Klarifikasi    — TIDAK tersimpan, plus pertanyaan balik yang spesifik.

Isolasi tenant (aturan #6): `business_id` diteruskan ke setiap resolusi di
service; input pengguna dianggap tak tepercaya.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.ekstraksi import ekstrak_resep
from app.llm.kontrak import AdapterLLM, Gagal
from app.llm.penjaga import periksa_nominal
from app.llm.skema import JawabHarga, instruksi_harga
from app.models import Product, SumberHarga
from app.services.angka import _dec, _uang
from app.services.entitas import cari_cost_item
from app.services.hpp import simpan_snapshot_semua
from app.services.resep import (
    HasilAturResep,
    atur_resep,
    catat_harga_bahan,
    rangkai_hasil,
)
from app.tools.catat_transaksi import Klarifikasi

__all__ = ["atur_resep_dari_teks", "jawab_harga_bahan"]

_TAK_LENGKAP = (
    "Resepnya belum lengkap. Coba sebut: sekali bikin jadi berapa, dan "
    "bahan-bahannya apa saja beserta takarannya."
)


def atur_resep_dari_teks(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
) -> HasilAturResep | Klarifikasi:
    """Tetapkan resep dari satu kalimat. Tidak pernah menyimpan resep separuh."""
    hasil = ekstrak_resep(adapter, teks, hari_ini)
    if isinstance(hasil, Gagal):
        return Klarifikasi(pertanyaan=_TAK_LENGKAP, yang_kurang=hasil.yang_kurang)

    resep = hasil.data
    if not resep.bahan:
        return Klarifikasi(pertanyaan=_TAK_LENGKAP, yang_kurang=["bahan"])

    bahan = [(b.nama, b.qty, b.satuan) for b in resep.bahan]
    return atur_resep(
        session,
        business_id,
        resep.nama_produk,
        resep.yield_qty,
        resep.yield_satuan,
        bahan,
        hari_ini,
    )


def jawab_harga_bahan(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    product_id: int,
    bahan: str,
    teks: str,
    hari_ini: date,
) -> HasilAturResep | None:
    """Tangkap jawaban harga bahan (tanya-jawab multi-turn) → HPP dihitung ulang.

    `product_id`/`bahan` datang dari token kelanjutan yang dibawa klien — **tak
    tepercaya**. Produk divalidasi milik tenant (aturan #6) sebelum apa pun
    ditulis; bila bukan, `None` (orchestrator jatuh ke router).

    `None` juga dikembalikan bila pesan ternyata **bukan** jawaban harga
    (ekstraksi gagal, atau nominal tampak dihitung sendiri) — supaya pengguna
    yang ganti topik ("laku 5 risol") tidak terjebak: pesannya diteruskan ke
    alur normal. Harga satuan = `nominal ÷ qty` dihitung **kode** (aturan #1).
    """
    produk = session.scalars(
        select(Product).where(
            Product.id == product_id, Product.business_id == business_id
        )
    ).first()
    if produk is None:
        return None

    ci = cari_cost_item(session, business_id, bahan)
    if ci is None:
        return None

    hasil = adapter.ekstrak(instruksi_harga(bahan, hari_ini), teks, JawabHarga)
    if isinstance(hasil, Gagal):
        return None

    jawab = hasil.data
    if periksa_nominal(teks, jawab.nominal, jawab.qty) is not None:
        return None

    qty = _dec(jawab.qty) if jawab.qty is not None else Decimal("1")
    if qty <= 0:
        return None
    harga_satuan = _uang(_dec(jawab.nominal) / qty)

    catat_harga_bahan(
        session, business_id, ci.id, harga_satuan, jawab.satuan, hari_ini,
        sumber=SumberHarga.ditanya,
    )

    # Harga bahan dipakai bersama produk lain — snapshot seluruh usaha, bukan
    # hanya produk yang sedang ditanyakan.
    simpan_snapshot_semua(session, business_id)

    return rangkai_hasil(session, business_id, product_id)

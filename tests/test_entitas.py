"""Penautan entitas (Pilar 1→4): resolver + loop reseller ujung-ke-ujung.

Menguji dua lapis:
1. Resolver murni (`app/services/entitas.py`) — buat/cari/adopsi, isolasi tenant.
2. Integrasi: `simpan_transaksi` menautkan produk → `hitung_hpp_produk` &
   `kartu_untung` menghasilkan modal + harga jual + untung dari data chat, tanpa
   penautan manual maupun seed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.orkestrator import kartu_untung
from app.llm.skema import BarisTransaksi
from app.models import (
    Business,
    JenisProduk,
    JenisTransaksi,
    Product,
    ProductPrice,
    Transaction,
)
from app.services.catat import simpan_transaksi
from app.services.entitas import adopsi_pembelian_yatim, cari_produk, resolusi_produk
from app.services.harga import harga_jual_berlaku
from app.services.hpp import StatusHpp, hitung_hpp_produk

TGL = date(2026, 6, 10)


def _baris(jenis, nominal, **kw) -> BarisTransaksi:
    return BarisTransaksi(jenis=jenis, nominal=Decimal(nominal), tanggal=TGL, **kw)


def _beli(nominal, **kw) -> BarisTransaksi:
    return _baris(JenisTransaksi.pengeluaran, nominal, **kw)


def _jual(nominal, **kw) -> BarisTransaksi:
    return _baris(JenisTransaksi.pemasukan, nominal, **kw)


# ── Resolver murni ───────────────────────────────────────────────────────────


def test_produk_baru_default_reseller(session: Session, business: Business):
    """Default aman-gagal: tebakan tak pernah memindahkan ke jalur produksi
    (yang akan memicu wawancara resep — larangan keras aturan #8)."""
    produk, baru = resolusi_produk(session, business.id, "nugget")

    assert baru is True
    assert produk.jenis is JenisProduk.reseller
    assert produk.nama == "nugget"
    assert produk.business_id == business.id


def test_resolusi_idempoten_tanpa_peduli_huruf(session: Session, business: Business):
    p1, baru1 = resolusi_produk(session, business.id, "Nugget")
    p2, baru2 = resolusi_produk(session, business.id, "  nugget ")

    assert baru1 is True and baru2 is False
    assert p1.id == p2.id
    assert session.scalars(select(Product)).all() == [p1]


def test_isolasi_tenant_nama_sama_dua_produk(
    session: Session, business: Business, tetangga: Business
):
    """Aturan #6: nama sama di dua usaha = dua produk berbeda, tidak bocor."""
    milik_kita, _ = resolusi_produk(session, business.id, "nugget")
    milik_tetangga, baru = resolusi_produk(session, tetangga.id, "nugget")

    assert baru is True
    assert milik_kita.id != milik_tetangga.id
    assert cari_produk(session, business.id, "nugget").id == milik_kita.id
    assert cari_produk(session, tetangga.id, "nugget").id == milik_tetangga.id


def test_cari_produk_tidak_membuat(session: Session, business: Business):
    assert cari_produk(session, business.id, "nugget") is None
    assert session.scalars(select(Product)).all() == []


def test_adopsi_hanya_kecocokan_persis(session: Session, business: Business):
    """Pembelian yatim yang namanya sama-persis diadopsi; yang mirip-tapi-beda
    tidak — tautan salah lebih berbahaya daripada menunggu kulakan berikutnya."""
    cocok = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran,
        nominal=Decimal("250000"), tanggal=TGL, deskripsi="Nugget", qty=Decimal("10"),
        satuan="pack",
    )
    beda = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran,
        nominal=Decimal("38000"), tanggal=TGL, deskripsi="nugget stik", qty=Decimal("1"),
    )
    session.add_all([cocok, beda])
    session.flush()

    produk, _ = resolusi_produk(session, business.id, "nugget")
    diadopsi = adopsi_pembelian_yatim(session, business.id, produk)

    assert [t.id for t in diadopsi] == [cocok.id]
    assert cocok.product_id == produk.id
    assert beda.product_id is None


def test_adopsi_tidak_menyentuh_yang_sudah_tertaut_atau_dibatalkan(
    session: Session, business: Business
):
    lain, _ = resolusi_produk(session, business.id, "kroket")
    sudah_tertaut = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=Decimal("1"),
        tanggal=TGL, deskripsi="nugget", product_id=lain.id,
    )
    dibatalkan = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=Decimal("1"),
        tanggal=TGL, deskripsi="nugget", dibatalkan_pada=date(2026, 6, 11),
    )
    session.add_all([sudah_tertaut, dibatalkan])
    session.flush()

    nugget, _ = resolusi_produk(session, business.id, "nugget")
    diadopsi = adopsi_pembelian_yatim(session, business.id, nugget)

    assert diadopsi == []
    assert sudah_tertaut.product_id == lain.id
    assert dibatalkan.product_id is None


# ── Integrasi: loop reseller ujung-ke-ujung dari chat ───────────────────────


def test_loop_reseller_beli_lalu_jual_menghasilkan_untung(
    session: Session, business: Business
):
    """Beli-dulu-baru-jual: pembelian yatim diadopsi saat produk lahir, harga
    jual ditangkap dari penjualan → HPP lengkap dengan modal + harga + untung."""
    simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )
    beli = session.scalars(select(Transaction)).one()
    assert beli.product_id is None  # produknya belum ada saat dibeli

    simpan_transaksi(
        session, business.id,
        [_jual("60000", produk="nugget", qty=Decimal("2"), satuan="pack")],
        "laku 2 pack nugget 60rb",
    )

    nugget = cari_produk(session, business.id, "nugget")
    assert nugget is not None and nugget.jenis is JenisProduk.reseller
    # Pembelian yatim kini teradopsi ke produk yang sama.
    session.refresh(beli)
    assert beli.product_id == nugget.id
    # Harga jual ditangkap dari penjualan (60.000 / 2 = 30.000).
    harga = harga_jual_berlaku(session, nugget.id, business.id, tanggal=TGL)
    assert harga is not None and harga.harga == Decimal("30000.00")

    hasil = hitung_hpp_produk(session, nugget.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("25000.00")        # 250.000 / 10
    assert hasil.harga_jual == Decimal("30000.00")
    assert hasil.laba_kotor_per_unit == Decimal("5000.00")  # 30.000 − 25.000


def test_kartu_untung_dari_data_chat(session: Session, business: Business):
    simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )
    simpan_transaksi(
        session, business.id,
        [_jual("60000", produk="nugget", qty=Decimal("2"), satuan="pack")],
        "laku 2 pack nugget 60rb",
    )

    pesan = kartu_untung(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    (kartu,) = pesan.kartu
    (baris,) = kartu.produk
    assert baris.diketahui is True
    assert baris.hpp_tampil == "Rp25.000"
    assert baris.harga_jual_tampil == "Rp30.000"
    assert baris.laba_kotor_tampil == "Rp5.000"
    assert kartu.cakupan_tampil == "100%"  # satu penjualan, modalnya terhitung


def test_penjualan_produksi_tanpa_pembelian_jujur_belum_diketahui(
    session: Session, business: Business
):
    """Aturan #2 & #8: tebakan default reseller yang 'salah' (risol sebenarnya
    produksi) terdegradasi jujur — bukan angka karangan — dan tetap reseller,
    jadi tak pernah dipicu wawancara resep."""
    simpan_transaksi(
        session, business.id, [_jual("75000", produk="risol")], "laku risol 75rb"
    )

    risol = cari_produk(session, business.id, "risol")
    assert risol is not None and risol.jenis is JenisProduk.reseller

    hasil = hitung_hpp_produk(session, risol.id, business.id)
    assert hasil.status is StatusHpp.belum_ada_harga_beli
    assert hasil.hpp_per_unit is None            # tidak dikarang
    assert hasil.laba_kotor_per_unit is None


def test_belanja_tak_dikenal_tidak_membuat_produk(session: Session, business: Business):
    """Pengeluaran tanpa produk yang cocok dibiarkan NULL — mungkin bahan baku,
    yang routing-nya digarap slice berikutnya (tidak diimprovisasi jadi produk)."""
    simpan_transaksi(
        session, business.id,
        [_beli("38000", produk="minyak goreng", qty=Decimal("1"), satuan="liter")],
        "beli minyak 38rb",
    )

    assert session.scalars(select(Product)).all() == []
    t = session.scalars(select(Transaction)).one()
    assert t.product_id is None


# ── Harga jual: dedup & perubahan ───────────────────────────────────────────


def test_harga_jual_dedup_saat_tak_berubah(session: Session, business: Business):
    for _ in range(3):
        simpan_transaksi(
            session, business.id,
            [_jual("60000", produk="nugget", qty=Decimal("2"), satuan="pack")],
            "laku 2 pack nugget 60rb",
        )

    nugget = cari_produk(session, business.id, "nugget")
    harga_rows = session.scalars(
        select(ProductPrice).where(ProductPrice.product_id == nugget.id)
    ).all()
    assert len(harga_rows) == 1  # harga sama → tidak ditulis berulang


def test_harga_jual_baru_dicatat_saat_berubah(session: Session, business: Business):
    simpan_transaksi(
        session, business.id,
        [_jual("60000", produk="nugget", qty=Decimal("2"), satuan="pack")],
        "laku 2 pack nugget 60rb",
    )
    simpan_transaksi(
        session, business.id,
        [_jual("64000", produk="nugget", qty=Decimal("2"), satuan="pack")],
        "laku 2 pack nugget 64rb",
    )

    nugget = cari_produk(session, business.id, "nugget")
    harga_rows = session.scalars(
        select(ProductPrice).where(ProductPrice.product_id == nugget.id)
    ).all()
    assert len(harga_rows) == 2
    berlaku = harga_jual_berlaku(session, nugget.id, business.id, tanggal=TGL)
    assert berlaku.harga == Decimal("32000.00")  # 64.000 / 2, yang terbaru menang

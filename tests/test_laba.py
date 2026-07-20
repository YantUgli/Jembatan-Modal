"""Unit test laba periode & rekonsiliasi biaya (keputusan.md 2026-07-18).

Yang diuji bukan cuma aritmatikanya, tapi juga **kejujurannya**: prive tidak
dihitung sebagai biaya, biaya operasional diakui berada di luar HPP, dan basis
kas dinyatakan alih-alih dipoles.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import JenisProduk, JenisTransaksi
from app.services.laba import (
    CATATAN_BASIS_KAS,
    TANPA_KATEGORI,
    hitung_laba_periode,
    rekonsiliasi_biaya,
)
from tests.conftest import (
    buat_material,
    buat_produk,
    buat_resep,
    buat_transaksi,
    set_harga,
)

MULAI = date(2026, 6, 1)
SELESAI = date(2026, 6, 30)


# ── Laba periode ────────────────────────────────────────────────────────────


def test_laba_periode_dasar(session, business):
    """omzet − (belanja + operasional). Tidak ada alokasi, cakupan biaya 100%."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 5_000_000, date(2026, 6, 5))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 3_000_000, date(2026, 6, 6))
    buat_transaksi(session, business, JenisTransaksi.operasional, 900_000, date(2026, 6, 7))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.omzet == Decimal("5000000.00")
    assert hasil.belanja == Decimal("3000000.00")
    assert hasil.operasional == Decimal("900000.00")
    assert hasil.biaya_total == Decimal("3900000.00")
    assert hasil.laba_bersih == Decimal("1100000.00")
    assert hasil.untung is True
    assert CATATAN_BASIS_KAS in hasil.catatan


def test_prive_bukan_biaya_usaha(session, business):
    """Aturan #9: prive dikeluarkan dari biaya, dilaporkan sebagai fakta terpisah."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 4_000_000, date(2026, 6, 5))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 2_000_000, date(2026, 6, 6))
    buat_transaksi(session, business, JenisTransaksi.prive, 500_000, date(2026, 6, 20))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.biaya_total == Decimal("2000000.00")  # prive TIDAK masuk
    assert hasil.laba_bersih == Decimal("2000000.00")
    assert hasil.prive == Decimal("500000.00")
    assert hasil.rasio_prive == Decimal("25.0")  # 500rb / 2jt
    assert any("pribadi" in c for c in hasil.catatan)


def test_rasio_prive_none_saat_rugi(session, business):
    """Rasio terhadap laba ≤ 0 tidak bermakna — kembalikan None, jangan dikarang."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 1_000_000, date(2026, 6, 5))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 1_500_000, date(2026, 6, 6))
    buat_transaksi(session, business, JenisTransaksi.prive, 200_000, date(2026, 6, 7))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.laba_bersih == Decimal("-500000.00")
    assert hasil.untung is False
    assert hasil.rasio_prive is None
    assert any("lebih besar daripada pemasukan" in c for c in hasil.catatan)


def test_periode_kosong(session, business):
    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.omzet == Decimal("0.00")
    assert hasil.laba_bersih == Decimal("0.00")
    assert hasil.pos_biaya == []
    assert any("Belum ada catatan" in c for c in hasil.catatan)


def test_batas_tanggal_dihormati(session, business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 1_000_000, date(2026, 5, 31))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 2_000_000, date(2026, 6, 1))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 3_000_000, date(2026, 6, 30))
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 4_000_000, date(2026, 7, 1))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.omzet == Decimal("5000000.00")  # hanya 1 & 30 Juni (inklusif)


def test_isolasi_tenant(session, business, tetangga):
    """Prinsip #6: tiap query difilter business_id."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 1_000_000, date(2026, 6, 5))
    buat_transaksi(session, tetangga, JenisTransaksi.pemasukan, 9_000_000, date(2026, 6, 5))
    buat_transaksi(session, tetangga, JenisTransaksi.pengeluaran, 7_000_000, date(2026, 6, 5))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert hasil.omzet == Decimal("1000000.00")
    assert hasil.biaya_total == Decimal("0.00")


def test_pos_biaya_dikelompokkan_dan_terurut(session, business):
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, 300_000, date(2026, 6, 2),
        kategori_detail="bahan",
    )
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, 200_000, date(2026, 6, 3),
        kategori_detail="bahan",
    )
    buat_transaksi(
        session, business, JenisTransaksi.operasional, 800_000, date(2026, 6, 4),
        kategori_detail="sewa",
    )
    buat_transaksi(session, business, JenisTransaksi.operasional, 50_000, date(2026, 6, 5))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    assert [(p.kategori, p.nominal) for p in hasil.pos_biaya] == [
        ("sewa", Decimal("800000.00")),
        ("bahan", Decimal("500000.00")),  # 300rb + 200rb digabung
        (TANPA_KATEGORI.format(jenis="operasional"), Decimal("50000.00")),
    ]


def test_pos_tanpa_kategori_tidak_tampak_kembar(session, business):
    """Dua jenis biaya tanpa rincian harus tetap terbedakan, bukan dua baris sama."""
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 260_000, date(2026, 6, 2))
    buat_transaksi(session, business, JenisTransaksi.operasional, 39_000, date(2026, 6, 3))

    hasil = hitung_laba_periode(session, business.id, MULAI, SELESAI)

    label = [p.kategori for p in hasil.pos_biaya]
    assert label == ["pengeluaran (tanpa rincian)", "operasional (tanpa rincian)"]
    assert len(set(label)) == 2


# ── Rekonsiliasi biaya ──────────────────────────────────────────────────────


def _warung_mini(session, business):
    """Warteg-mini: HPP hanya menyerap bahan; sewa & gaji di luar HPP.

    Nasi bungkus: resep 1 kg beras (Rp 13.000) → yield 10 porsi = Rp 1.300/porsi.
    """
    beras = buat_material(session, business, "beras")
    set_harga(session, beras, 13_000, date(2026, 6, 1))
    nasi = buat_produk(session, business, "nasi bungkus", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, nasi, 10, [(beras, 1, "kg")])
    return nasi


def test_rekonsiliasi_menemukan_biaya_di_luar_hpp(session, business):
    """Inti keputusan 2026-07-18: cakupan omzet 100% ≠ cakupan biaya 100%."""
    nasi = _warung_mini(session, business)
    # 100 porsi terjual — seluruh omzet tertaut produk (cakupan omzet 100%)
    buat_transaksi(
        session, business, JenisTransaksi.pemasukan, 1_500_000, date(2026, 6, 10),
        product=nasi, qty=100, satuan="porsi",
    )
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, 130_000, date(2026, 6, 9),
        kategori_detail="beras",
    )
    buat_transaksi(
        session, business, JenisTransaksi.operasional, 2_000_000, date(2026, 6, 1),
        kategori_detail="sewa & gaji",
    )

    rek = rekonsiliasi_biaya(session, business.id, MULAI, SELESAI)

    # HPP menyerap 100 × Rp 1.300 = Rp 130.000 dari Rp 2.130.000 biaya nyata
    assert rek.terserap_hpp == Decimal("130000.00")
    assert rek.biaya_total == Decimal("2130000.00")
    assert rek.di_luar_hpp == Decimal("2000000.00")
    assert rek.persen_terserap == Decimal("6.1")
    assert rek.pos_biaya_terbesar[0].kategori == "sewa & gaji"
    assert any("operasional" in c for c in rek.catatan)


def test_rekonsiliasi_mengaku_saat_hpp_melebihi_belanja(session, business):
    """Basis kas: menjual stok periode lalu. Selisih negatif TIDAK dipoles jadi nol."""
    nasi = _warung_mini(session, business)
    buat_transaksi(
        session, business, JenisTransaksi.pemasukan, 1_500_000, date(2026, 6, 10),
        product=nasi, qty=100, satuan="porsi",
    )
    # tidak ada belanja beras bulan ini — berasnya dibeli bulan lalu

    rek = rekonsiliasi_biaya(session, business.id, MULAI, SELESAI)

    assert rek.terserap_hpp == Decimal("130000.00")
    assert rek.biaya_total == Decimal("0.00")
    assert rek.di_luar_hpp == Decimal("-130000.00")
    # Dua sebab disebut berdampingan — tidak memilih salah satu seolah pasti.
    catatan = " ".join(rek.catatan)
    assert "belum dicatat" in catatan
    assert "dibeli sebelum periode ini" in catatan


def test_rekonsiliasi_periode_tanpa_pengeluaran(session, business):
    rek = rekonsiliasi_biaya(session, business.id, MULAI, SELESAI)

    assert rek.biaya_total == Decimal("0.00")
    assert rek.persen_terserap == Decimal("0.0")
    assert any("Belum ada pengeluaran" in c for c in rek.catatan)


def test_rekonsiliasi_batas_pos(session, business):
    for i, nominal in enumerate([100_000, 200_000, 300_000, 400_000, 500_000, 600_000]):
        buat_transaksi(
            session, business, JenisTransaksi.operasional, nominal, date(2026, 6, 2 + i),
            kategori_detail=f"pos-{i}",
        )

    rek = rekonsiliasi_biaya(session, business.id, MULAI, SELESAI, batas_pos=3)

    assert len(rek.pos_biaya_terbesar) == 3
    assert rek.pos_biaya_terbesar[0].nominal == Decimal("600000.00")

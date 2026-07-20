"""Service pencatatan: penyimpanan, isolasi tenant, dan kalimat konfirmasi."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.skema import BarisTransaksi, JenisTransaksi
from app.models import Business, SumberInput, Transaction
from app.services.angka import rupiah
from app.services.catat import simpan_transaksi

TGL = date(2026, 6, 10)


def _baris(jenis=JenisTransaksi.pemasukan, nominal="75000", **kw) -> BarisTransaksi:
    return BarisTransaksi(jenis=jenis, nominal=Decimal(nominal), tanggal=TGL, **kw)


# ── Penyimpanan ────────────────────────────────────────────────────────────


def test_transaksi_tersimpan_dengan_business_id(session: Session, business: Business):
    hasil = simpan_transaksi(session, business.id, [_baris()], "laku 75rb")

    (t,) = session.scalars(select(Transaction)).all()
    assert t.business_id == business.id
    assert t.nominal == Decimal("75000")
    assert t.jenis is JenisTransaksi.pemasukan
    assert hasil.tersimpan == [t]


def test_kalimat_asli_ikut_disimpan(session: Session, business: Business):
    """Kalau pengguna protes 'kok jadi segitu?', kalimat aslinya harus ada."""
    simpan_transaksi(session, business.id, [_baris()], "tadi laku 5 kotak risol 75rb")

    t = session.scalars(select(Transaction)).one()
    assert t.raw_text == "tadi laku 5 kotak risol 75rb"
    assert t.sumber_input is SumberInput.chat


def test_takaran_ikut_tersimpan_untuk_hpp(session: Session, business: Business):
    simpan_transaksi(
        session, business.id,
        [_baris(produk="risol", qty=Decimal("5"), satuan="kotak")],
        "laku 5 kotak risol 75rb",
    )

    t = session.scalars(select(Transaction)).one()
    assert t.qty == Decimal("5")
    assert t.satuan == "kotak"
    assert t.deskripsi == "risol"


def test_tidak_bocor_ke_tenant_lain(session: Session, business: Business, tetangga):
    """Aturan #6: tiap baris terikat satu usaha."""
    simpan_transaksi(session, business.id, [_baris()], "laku 75rb")

    milik_tetangga = session.scalars(
        select(Transaction).where(Transaction.business_id == tetangga.id)
    ).all()
    assert milik_tetangga == []


def test_daftar_kosong_tidak_menyimpan_apa_pun(session: Session, business: Business):
    hasil = simpan_transaksi(session, business.id, [], "hari ini rame banget")

    assert hasil.tersimpan == []
    assert session.scalars(select(Transaction)).all() == []
    assert "Belum ada" in hasil.konfirmasi


# ── Konfirmasi (template kode, bukan panggilan LLM kedua) ──────────────────


def test_konfirmasi_menyebut_nominal_dan_rincian(session: Session, business: Business):
    hasil = simpan_transaksi(
        session, business.id,
        [_baris(produk="risol", qty=Decimal("5"), satuan="kotak")],
        "laku 5 kotak risol 75rb",
    )

    assert "Rp75.000" in hasil.konfirmasi
    assert "5 kotak risol" in hasil.konfirmasi
    assert "10 Jun" in hasil.konfirmasi


def test_konfirmasi_memakai_bahasa_warung(session: Session, business: Business):
    """Non-goal: istilah akuntansi teknis di UI."""
    hasil = simpan_transaksi(
        session, business.id,
        [_baris(), _baris(JenisTransaksi.pengeluaran, "38000", produk="minyak")],
        "laku 75rb, beli minyak 38rb",
    )

    teks = hasil.konfirmasi.lower()
    for haram in ("debit", "kredit", "jurnal", "transaksi kas", "akun"):
        assert haram not in teks
    assert "masuk" in teks
    assert "belanja" in teks


def test_konfirmasi_tanpa_rincian_tetap_rapi(session: Session, business: Business):
    hasil = simpan_transaksi(session, business.id, [_baris()], "hari ini dapat 75rb")

    assert "()" not in hasil.konfirmasi
    assert "Rp75.000" in hasil.konfirmasi


def test_ringkasan_tidak_pernah_menghitung_laba(session: Session, business: Business):
    """Menampilkan 'masuk - keluar' di konfirmasi akan mengajari pengguna angka
    yang berbeda dari laporan bulanannya (prive dikecualikan di sana)."""
    hasil = simpan_transaksi(
        session, business.id,
        [_baris(), _baris(JenisTransaksi.prive, "50000")],
        "dapat 75rb, ambil 50rb buat jajan anak",
    )

    assert "masuk Rp75.000" in hasil.konfirmasi
    assert "keluar Rp50.000" in hasil.konfirmasi
    assert "25.000" not in hasil.konfirmasi  # selisihnya TIDAK dihitung
    assert "laba" not in hasil.konfirmasi.lower()
    assert "untung" not in hasil.konfirmasi.lower()


def test_satu_baris_tidak_diberi_ringkasan(session: Session, business: Business):
    hasil = simpan_transaksi(session, business.id, [_baris()], "laku 75rb")
    assert "Total" not in hasil.konfirmasi


# ── Format rupiah ──────────────────────────────────────────────────────────


def test_rupiah_gaya_indonesia():
    assert rupiah(Decimal("75000")) == "Rp75.000"
    assert rupiah(Decimal("1500000")) == "Rp1.500.000"
    assert rupiah(Decimal("500")) == "Rp500"


def test_rupiah_menampilkan_sen_bila_ada():
    """Sen nol dibuang, sen nyata tidak — jangan ada angka yang diam-diam hilang."""
    assert rupiah(Decimal("75000.00")) == "Rp75.000"
    assert rupiah(Decimal("4050.75")) == "Rp4.050,75"

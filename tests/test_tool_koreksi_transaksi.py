"""Tool `koreksi_transaksi` + jaminan buku append-only.

Bagian terpenting berkas ini bukan koreksinya, melainkan **buktinya bahwa baris
yang dibatalkan berhenti ikut dihitung** di laba, omzet, dan HPP. Kolom
`dibatalkan_pada` menaruh kewajiban menyaring pada setiap pembaca; kalau satu
pembaca lupa, angka yang sudah dibetulkan pengguna diam-diam hidup lagi.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.kontrak import Gagal
from app.llm.palsu import AdapterPalsu
from app.models import Business, JenisTransaksi, Transaction
from app.services.laba import hitung_laba_periode
from app.tools import Klarifikasi, Tercatat, Terkoreksi, catat_transaksi, koreksi_transaksi

HARI_INI = date(2026, 6, 10)
AWAL, AKHIR = date(2026, 6, 1), date(2026, 6, 30)
ASLI = "tadi laku 5 kotak risol 75rb"


def _catat(session, business, adapter=None, teks=ASLI):
    adapter = adapter or AdapterPalsu(jawaban_ekstrak={teks: {"baris": [
        {"jenis": "pemasukan", "nominal": "75000", "tanggal": "2026-06-10",
         "produk": "risol", "qty": "5", "satuan": "kotak"},
    ]}})
    hasil = catat_transaksi(session, adapter, business.id, teks, HARI_INI)
    assert isinstance(hasil, Tercatat)
    return hasil


def _koreksi(session, business, teks, jawab, transaksi_id=None):
    adapter = AdapterPalsu(jawaban_ekstrak={teks: jawab})
    return koreksi_transaksi(
        session, adapter, business.id, teks, HARI_INI, transaksi_id
    )


# ── Ubah ───────────────────────────────────────────────────────────────────


def test_ubah_nominal_membuat_baris_baru_bukan_menimpa(
    session: Session, business: Business
):
    _catat(session, business)
    teks = "eh salah, harusnya 57rb"

    hasil = _koreksi(session, business, teks, {"aksi": "ubah", "nominal": "57000"})

    assert isinstance(hasil, Terkoreksi)
    semua = session.scalars(select(Transaction).order_by(Transaction.id)).all()
    assert len(semua) == 2, "baris lama harus tetap ada — buku append-only"
    assert semua[0].dibatalkan_pada is not None
    assert semua[1].nominal == Decimal("57000")
    assert semua[1].koreksi_dari_id == semua[0].id


def test_field_yang_tidak_disebut_tidak_ikut_terhapus(
    session: Session, business: Business
):
    """'harusnya 57rb' tidak boleh menghapus produk & takaran yang sudah benar."""
    _catat(session, business)

    _koreksi(session, business, "harusnya 57rb", {"aksi": "ubah", "nominal": "57000"})

    baru = session.scalars(
        select(Transaction).where(Transaction.dibatalkan_pada.is_(None))
    ).one()
    assert baru.deskripsi == "risol"
    assert baru.qty == Decimal("5")
    assert baru.satuan == "kotak"


def test_ubah_jenis_ke_prive(session: Session, business: Business):
    _catat(session, business)

    hasil = _koreksi(session, business, "itu buat pribadi",
                     {"aksi": "ubah", "jenis": "prive"})

    assert isinstance(hasil, Terkoreksi)
    baru = session.get(Transaction, hasil.id_pengganti)
    assert baru.jenis is JenisTransaksi.prive
    assert baru.nominal == Decimal("75000")  # nominal ikut terbawa


def test_konfirmasi_menyebut_nilai_lama_dan_baru(session: Session, business: Business):
    _catat(session, business)

    hasil = _koreksi(session, business, "harusnya 57rb",
                     {"aksi": "ubah", "nominal": "57000"})

    assert "Rp57.000" in hasil.konfirmasi
    assert "Rp75.000" in hasil.konfirmasi  # yang lama ikut ditunjukkan
    assert "Sebelumnya" in hasil.konfirmasi


# ── Batal ──────────────────────────────────────────────────────────────────


def test_batal_menandai_bukan_menghapus_baris(session: Session, business: Business):
    _catat(session, business)

    hasil = _koreksi(session, business, "hapus yang tadi", {"aksi": "batal"})

    assert isinstance(hasil, Terkoreksi)
    t = session.scalars(select(Transaction)).one()
    assert t.dibatalkan_pada is not None
    assert "dihapus" in hasil.konfirmasi.lower()


# ── Yang dibatalkan berhenti dihitung ──────────────────────────────────────


def test_baris_batal_tidak_ikut_laba(session: Session, business: Business):
    _catat(session, business)
    sebelum = hitung_laba_periode(session, business.id, AWAL, AKHIR)
    assert sebelum.omzet == Decimal("75000")

    _koreksi(session, business, "hapus yang tadi", {"aksi": "batal"})

    sesudah = hitung_laba_periode(session, business.id, AWAL, AKHIR)
    assert sesudah.omzet == Decimal("0")


def test_koreksi_nominal_terpakai_di_laba(session: Session, business: Business):
    """Yang lama batal DAN yang baru terhitung — bukan salah satunya saja."""
    _catat(session, business)

    _koreksi(session, business, "harusnya 57rb", {"aksi": "ubah", "nominal": "57000"})

    laba = hitung_laba_periode(session, business.id, AWAL, AKHIR)
    assert laba.omzet == Decimal("57000")


# ── Penjaga & batas ────────────────────────────────────────────────────────


def test_nominal_hasil_perkalian_ditolak_juga_di_jalur_koreksi(
    session: Session, business: Business
):
    """Angka karangan lewat koreksi sama merusaknya dengan lewat pencatatan."""
    _catat(session, business)
    teks = "harusnya 3 kotak 20rb"

    hasil = _koreksi(session, business, teks,
                     {"aksi": "ubah", "nominal": "60000", "qty": "3"})

    assert isinstance(hasil, Klarifikasi)
    tetap = session.scalars(
        select(Transaction).where(Transaction.dibatalkan_pada.is_(None))
    ).one()
    assert tetap.nominal == Decimal("75000")  # tak tersentuh


def test_tidak_bisa_mengoreksi_transaksi_usaha_lain(
    session: Session, business: Business, tetangga
):
    """Aturan #6 di jalur yang paling berbahaya: menulis, bukan membaca."""
    milik_kita = _catat(session, business)
    id_kita = milik_kita.ids[0]

    teks = "hapus yang tadi"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "batal"}})
    hasil = koreksi_transaksi(
        session, adapter, tetangga.id, teks, HARI_INI, transaksi_id=id_kita
    )

    assert isinstance(hasil, Klarifikasi)
    assert session.get(Transaction, id_kita).dibatalkan_pada is None


def test_belum_ada_catatan_dijawab_jujur(session: Session, business: Business):
    teks = "hapus yang tadi"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "batal"}})

    hasil = koreksi_transaksi(session, adapter, business.id, teks, HARI_INI)

    assert isinstance(hasil, Klarifikasi)
    assert "Belum ada" in hasil.pertanyaan


def test_baris_yang_sudah_batal_tidak_jadi_sasaran_berikutnya(
    session: Session, business: Business
):
    _catat(session, business)
    _koreksi(session, business, "hapus yang tadi", {"aksi": "batal"})

    hasil = _koreksi(session, business, "hapus yang tadi", {"aksi": "batal"})

    assert isinstance(hasil, Klarifikasi)
    assert "Belum ada" in hasil.pertanyaan


def test_kalimat_koreksi_tak_jelas_ditanya_balik_dengan_sasarannya(
    session: Session, business: Business
):
    _catat(session, business)
    teks = "itu kok gitu"

    hasil = _koreksi(session, business, teks,
                     Gagal(alasan="tidak jelas", yang_kurang=[]))

    assert isinstance(hasil, Klarifikasi)
    assert "Rp75.000" in hasil.pertanyaan  # tunjukkan yang mana
    assert session.scalars(
        select(Transaction).where(Transaction.dibatalkan_pada.is_(None))
    ).one()


# ── Pembaca lain: HPP reseller memakai harga beli TERAKHIR ─────────────────


def test_pembelian_yang_dibatalkan_tidak_dipakai_sebagai_harga_hpp(
    session: Session, business: Business
):
    """Pembaca ketiga dari `transactions`. Kalau di sini lupa disaring, HPP
    memakai harga dari pembelian yang sudah dibetulkan pengguna — salah tanpa
    satu pun pesan error."""
    from datetime import date as _date

    from app.models.base import JenisProduk
    from app.services.hpp import StatusHpp, hitung_hpp_produk
    from tests.conftest import buat_produk, buat_transaksi

    beras = buat_produk(session, business, "beras", JenisProduk.reseller,
                        harga_jual=13000)
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 120000,
                   _date(2026, 6, 1), product=beras, qty=10, satuan="kg")
    salah = buat_transaksi(session, business, JenisTransaksi.pengeluaran, 990000,
                           _date(2026, 6, 5), product=beras, qty=10, satuan="kg")

    keliru = hitung_hpp_produk(session, beras.id, business.id)
    assert keliru.hpp_per_unit == Decimal("99000.00")  # harga terakhir (salah tulis)

    salah.dibatalkan_pada = datetime.now()
    session.flush()

    benar = hitung_hpp_produk(session, beras.id, business.id)
    assert benar.status is StatusHpp.lengkap
    assert benar.hpp_per_unit == Decimal("12000.00")  # kembali ke pembelian sah

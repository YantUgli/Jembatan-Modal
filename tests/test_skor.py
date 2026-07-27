"""Skor Kesehatan Usaha — kalkulasi, degradasi, normalisasi bobot, isolasi.

Yang dijaga di sini bukan cuma "angkanya benar", tapi tiga janji produk:
aturan #2 (komponen tak terhitung ≠ nol), aturan #9 (skor komposit tidak pernah
bocor ke dokumen penyalur), dan aturan #6 (isolasi tenant).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Business, JenisTransaksi
from app.services.laporan import ringkas_laporan
from app.services.skor import (
    BOBOT,
    HARI_SKOR,
    StatusKomponen,
    hitung_skor,
    simpan_snapshot_skor,
    snapshot_terakhir_skor,
)
from tests.conftest import buat_transaksi

HARI_INI = date(2026, 7, 27)
MULAI = HARI_INI - timedelta(days=HARI_SKOR - 1)  # 28 Jun 2026


def _komponen(hasil, kunci: str):
    return next(k for k in hasil.komponen if k.kunci == kunci)


def _jual(session: Session, business: Business, nominal, tanggal, **kw):
    return buat_transaksi(session, business, JenisTransaksi.pemasukan, nominal, tanggal, **kw)


def _belanja(session: Session, business: Business, nominal, tanggal, **kw):
    return buat_transaksi(session, business, JenisTransaksi.pengeluaran, nominal, tanggal, **kw)


def _ambil(session: Session, business: Business, nominal, tanggal):
    return buat_transaksi(session, business, JenisTransaksi.prive, nominal, tanggal)


# ── Periode ─────────────────────────────────────────────────────────────────


def test_periode_default_30_hari_bergulir(session: Session, business: Business):
    """Bukan bulan berjalan — jendela bergulir yang menutup di hari ini."""
    hasil = hitung_skor(session, business.id, HARI_INI)
    assert hasil.periode.mulai == MULAI
    assert hasil.periode.selesai == HARI_INI
    assert hasil.periode.label == "30_hari"


# ── Konsistensi pencatatan ──────────────────────────────────────────────────


def test_konsistensi_penuh_saat_semua_hari_tercatat(session: Session, business: Business):
    for i in range(HARI_SKOR):
        _jual(session, business, 100_000, MULAI + timedelta(days=i))

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "konsistensi")
    assert k.nilai == BOBOT["konsistensi"]


def test_konsistensi_separuh(session: Session, business: Business):
    for i in range(0, HARI_SKOR, 2):  # 15 dari 30 hari
        _jual(session, business, 100_000, MULAI + timedelta(days=i))

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "konsistensi")
    assert k.nilai == BOBOT["konsistensi"] // 2


def test_usaha_baru_dinilai_atas_umurnya_bukan_30_hari(session: Session, business: Business):
    """Mencatat 5 hari dari 5 hari usianya = rajin, bukan 5/30."""
    for i in range(5):
        _jual(session, business, 100_000, HARI_INI - timedelta(days=4 - i))

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "konsistensi")
    assert k.nilai == BOBOT["konsistensi"]
    assert "5 dari 5 hari" in k.rincian_tampil


def test_tanpa_catatan_konsistensi_belum_diketahui(session: Session, business: Business):
    k = _komponen(hitung_skor(session, business.id, HARI_INI), "konsistensi")
    assert k.status is StatusKomponen.belum_diketahui
    assert k.nilai is None
    assert k.bobot_efektif == 0


# ── Margin laba ─────────────────────────────────────────────────────────────


def test_margin_20_persen_penuh(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 800_000, HARI_INI)  # laba 200rb = 20%

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "margin")
    assert k.nilai == BOBOT["margin"]


def test_margin_10_persen_separuh(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 900_000, HARI_INI)  # laba 100rb = 10%

    # 12,5 dibulatkan ROUND_HALF_UP seperti seluruh jalur uang — bukan bankers'
    # rounding bawaan `round()`.
    k = _komponen(hitung_skor(session, business.id, HARI_INI), "margin")
    assert k.nilai == 13


def test_margin_rugi_nol_bukan_belum_diketahui(session: Session, business: Business):
    """Rugi adalah hasil yang terhitung — nol di sini sah, beda dari ketiadaan data."""
    _jual(session, business, 500_000, HARI_INI)
    _belanja(session, business, 900_000, HARI_INI)

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "margin")
    assert k.status is StatusKomponen.dihitung
    assert k.nilai == 0


def test_margin_tanpa_omzet_belum_diketahui(session: Session, business: Business):
    _belanja(session, business, 300_000, HARI_INI)

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "margin")
    assert k.status is StatusKomponen.belum_diketahui
    assert k.bobot_efektif == 0


def test_margin_tidak_digerbangi_cakupan_hpp(session: Session, business: Business):
    """Keputusan 2026-07-27: cakupan HPP nol tidak boleh mematikan komponen ini.

    Penjualan tanpa `product_id` → cakupan HPP 0%. Margin tetap terhitung, karena
    laba bersih basis kas tak bergantung HPP (keputusan 2026-07-26).
    """
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 800_000, HARI_INI)

    hasil = hitung_skor(session, business.id, HARI_INI)
    assert hasil.cakupan_hpp_persen == Decimal("0.0")
    assert _komponen(hasil, "margin").nilai == BOBOT["margin"]


# ── Tren omzet ──────────────────────────────────────────────────────────────


def test_tren_naik_penuh(session: Session, business: Business):
    _jual(session, business, 1_000_000, MULAI - timedelta(days=1))  # periode lalu
    _jual(session, business, 2_000_000, HARI_INI)

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "tren")
    assert k.nilai == BOBOT["tren"]


def test_tren_stabil_sebagian(session: Session, business: Business):
    _jual(session, business, 1_000_000, MULAI - timedelta(days=1))
    _jual(session, business, 1_020_000, HARI_INI)  # +2%

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "tren")
    assert 0 < k.nilai < BOBOT["tren"]


def test_tren_anjlok_nol(session: Session, business: Business):
    _jual(session, business, 1_000_000, MULAI - timedelta(days=1))
    _jual(session, business, 300_000, HARI_INI)  # −70%

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "tren")
    assert k.nilai == 0


def test_tren_tanpa_pembanding_belum_diketahui(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "tren")
    assert k.status is StatusKomponen.belum_diketahui
    assert k.bobot_efektif == 0


# ── Disiplin prive ──────────────────────────────────────────────────────────


def test_prive_di_bawah_separuh_laba_penuh(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 600_000, HARI_INI)  # laba 400rb
    _ambil(session, business, 100_000, HARI_INI)  # 25% dari laba

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "prive")
    assert k.nilai == BOBOT["prive"]


def test_prive_melebihi_laba_nol(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 600_000, HARI_INI)
    _ambil(session, business, 500_000, HARI_INI)  # 125% dari laba

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "prive")
    assert k.nilai == 0


def test_prive_saat_rugi_belum_diketahui(session: Session, business: Business):
    """Membandingkan ambilan dengan laba yang tak ada = angka yang tampak menilai."""
    _jual(session, business, 300_000, HARI_INI)
    _belanja(session, business, 900_000, HARI_INI)
    _ambil(session, business, 100_000, HARI_INI)

    k = _komponen(hitung_skor(session, business.id, HARI_INI), "prive")
    assert k.status is StatusKomponen.belum_diketahui
    assert k.bobot_efektif == 0


# ── Normalisasi bobot & degradasi ───────────────────────────────────────────


def test_bobot_dinormalisasi_bukan_dianggap_nol(session: Session, business: Business):
    """Rugi mematikan komponen prive → penyebut 80, bukan 100.

    Kalau prive diperlakukan sebagai nol, skornya akan lebih rendah dari yang
    seharusnya — menghukum pengguna untuk data yang memang tidak ada (aturan #2).
    """
    _jual(session, business, 1_000_000, MULAI - timedelta(days=1))
    _jual(session, business, 500_000, HARI_INI)
    _belanja(session, business, 900_000, HARI_INI)  # rugi → prive mati

    hasil = hitung_skor(session, business.id, HARI_INI)
    assert hasil.bobot_terpakai == 100 - BOBOT["prive"]

    raih = sum(k.nilai for k in hasil.komponen if k.diketahui)
    assert hasil.skor_total == round(raih / hasil.bobot_terpakai * 100)


def test_tanpa_data_sama_sekali_skor_none_bukan_nol(session: Session, business: Business):
    hasil = hitung_skor(session, business.id, HARI_INI)
    assert hasil.skor_total is None
    assert hasil.bobot_terpakai == 0
    assert not hasil.diketahui
    assert all(not k.diketahui for k in hasil.komponen)


def test_catatan_menyebut_bagian_yang_belum_dinilai(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    hasil = hitung_skor(session, business.id, HARI_INI)
    assert any("belum bisa dinilai" in c for c in hasil.catatan)


# ── Buku append-only ────────────────────────────────────────────────────────


def test_transaksi_dibatalkan_tidak_ikut_terhitung(session: Session, business: Business):
    """Catatan yang sudah dikoreksi pengguna tidak boleh diam-diam ikut menskor."""
    t = _jual(session, business, 9_000_000, HARI_INI)
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 800_000, HARI_INI)

    sebelum = hitung_skor(session, business.id, HARI_INI)
    t.dibatalkan_pada = HARI_INI
    session.flush()
    sesudah = hitung_skor(session, business.id, HARI_INI)

    assert sebelum.omzet == Decimal("10000000.00")
    assert sesudah.omzet == Decimal("1000000.00")
    assert _komponen(sesudah, "margin").nilai == BOBOT["margin"]


# ── Snapshot & progres ──────────────────────────────────────────────────────


def test_snapshot_dedup_saat_skor_tidak_berubah(session: Session, business: Business):
    _jual(session, business, 1_000_000, HARI_INI)
    hasil = hitung_skor(session, business.id, HARI_INI)

    pertama = simpan_snapshot_skor(session, business.id, hasil)
    kedua = simpan_snapshot_skor(session, business.id, hitung_skor(session, business.id, HARI_INI))

    assert pertama.baru is True
    assert kedua.baru is False
    assert kedua.snapshot.id == pertama.snapshot.id


def test_snapshot_ditulis_juga_saat_skor_belum_diketahui(session: Session, business: Business):
    hasil = hitung_skor(session, business.id, HARI_INI)
    simpan = simpan_snapshot_skor(session, business.id, hasil)

    assert simpan.baru is True
    assert simpan.snapshot.skor_total is None


def test_delta_none_saat_pembanding_periode_sama(session: Session, business: Business):
    """Snapshot periode yang sama adalah tulisan kita sendiri — bukan progres."""
    _jual(session, business, 1_000_000, HARI_INI)
    simpan_snapshot_skor(session, business.id, hitung_skor(session, business.id, HARI_INI))

    assert hitung_skor(session, business.id, HARI_INI).delta is None


def test_delta_terhitung_terhadap_periode_sebelumnya(session: Session, business: Business):
    kemarin = HARI_INI - timedelta(days=1)
    _jual(session, business, 1_000_000, kemarin)
    simpan_snapshot_skor(session, business.id, hitung_skor(session, business.id, kemarin))

    lama = snapshot_terakhir_skor(session, business.id).skor_total
    _jual(session, business, 2_000_000, HARI_INI)
    hasil = hitung_skor(session, business.id, HARI_INI)

    assert hasil.delta == hasil.skor_total - lama


# ── Aturan #9: skor tidak pernah bocor ke dokumen penyalur ──────────────────


def test_ringkasan_laporan_tidak_memuat_skor(session: Session, business: Business):
    """Jaring regresi: `RingkasanLaporan` membawa fakta mentah, bukan penilaian.

    Kalau suatu saat ada yang menambahkan skor ke laporan penyalur, test ini yang
    berteriak — bukan AO bank yang membaca otoritas yang belum kita punya.
    """
    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 700_000, HARI_INI)

    ringkasan = ringkas_laporan(session, business, HARI_INI)

    assert not hasattr(ringkasan, "skor")
    assert not hasattr(ringkasan, "skor_total")
    assert not hasattr(ringkasan.fakta, "skor_total")
    # `fakta_penyalur` hanya fakta yang bisa ditelusuri ke transaksi.
    assert set(vars(ringkasan.fakta)) == {
        "omzet_total",
        "bulan_bercatatan",
        "bulan_berturut",
        "hari_tercatat",
        "cakupan_hpp_persen",
        "rasio_prive_persen",
    }


def test_html_laporan_tidak_membawa_angka_skor(session: Session, business: Business):
    """Dokumen penyalur boleh **menyebut** bahwa ia tanpa skor — itu justru janjinya.

    Yang dilarang adalah angkanya: skor komposit maupun label komponennya. Kata
    "skor" sendiri muncul di kalimat penyangkalan, jadi test ini mencari bentuk
    penilaiannya, bukan katanya.
    """
    from app.laporan.html import render_html
    from app.services.skor import LABEL

    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 700_000, HARI_INI)
    _ambil(session, business, 100_000, HARI_INI)

    html = render_html(ringkas_laporan(session, business, HARI_INI), HARI_INI).lower()

    assert "tanpa skor" in html  # janji yang ditulis di dokumennya sendiri
    assert "dari 100" not in html
    assert "/100" not in html
    for label in LABEL.values():
        assert label.lower() not in html


# ── Aturan #6: isolasi tenant ───────────────────────────────────────────────


def test_skor_tetangga_tidak_ikut_terhitung(
    session: Session, business: Business, tetangga: Business
):
    for i in range(HARI_SKOR):
        _jual(session, tetangga, 500_000, MULAI + timedelta(days=i))
    _jual(session, business, 1_000_000, HARI_INI)

    milik_kita = hitung_skor(session, business.id, HARI_INI)
    assert milik_kita.omzet == Decimal("1000000.00")
    assert _komponen(milik_kita, "konsistensi").rincian_tampil.startswith("1 dari 1")


def test_snapshot_tetangga_tidak_jadi_pembanding(
    session: Session, business: Business, tetangga: Business
):
    kemarin = HARI_INI - timedelta(days=1)
    _jual(session, tetangga, 5_000_000, kemarin)
    simpan_snapshot_skor(session, tetangga.id, hitung_skor(session, tetangga.id, kemarin))

    _jual(session, business, 1_000_000, HARI_INI)
    assert hitung_skor(session, business.id, HARI_INI).delta is None
    assert snapshot_terakhir_skor(session, business.id) is None


# ── Kartu (lapisan kanal) ───────────────────────────────────────────────────


def test_kartu_skor_menyebut_periodenya(session: Session, business: Business):
    """Invarian 2026-07-27: kartu berangka wajib menuliskan rentangnya."""
    from app.kanal import VERSI_KONTRAK, kartu_skor

    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 700_000, HARI_INI)

    keluar = kartu_skor(session, business.id, HARI_INI)
    kartu = keluar.kartu[0]

    assert keluar.versi == VERSI_KONTRAK
    assert kartu.tipe == "skor"
    assert kartu.periode_tampil
    assert kartu.periode_label == "30_hari"
    assert kartu.skor_tampil.endswith("dari 100")
    assert len(kartu.komponen) == len(BOBOT)


def test_kartu_skor_membawa_komponen_yang_belum_dinilai(session: Session, business: Business):
    """Komponen tak terhitung tetap digambar — itu yang memberitahu apa yang kurang."""
    from app.kanal import kartu_skor

    _jual(session, business, 1_000_000, HARI_INI)
    kartu = kartu_skor(session, business.id, HARI_INI).kartu[0]

    belum = [k for k in kartu.komponen if k.nilai is None]
    assert belum
    assert all(k.sebab for k in belum)
    assert all(k.status == "belum_diketahui" for k in belum)


def test_kartu_tanpa_data_belum_diketahui_bukan_nol(session: Session, business: Business):
    from app.kanal import kartu_skor

    kartu = kartu_skor(session, business.id, HARI_INI).kartu[0]

    assert kartu.tipe == "belum_diketahui"
    assert not hasattr(kartu, "skor_total")  # tak ada angka untuk disodorkan
    assert "dari 100" not in kartu.teks_alt
    assert kartu.yang_kurang


def test_kartu_skor_mengaku_untuk_pengguna_bukan_bank(session: Session, business: Business):
    """Aturan #9 diucapkan di kartunya sendiri, bukan cuma dijaga di kode."""
    from app.kanal import kartu_skor

    _jual(session, business, 1_000_000, HARI_INI)
    _belanja(session, business, 700_000, HARI_INI)

    kartu = kartu_skor(session, business.id, HARI_INI).kartu[0]
    assert any("bank" in c.lower() for c in kartu.catatan)


# ── Lapisan HTTP ────────────────────────────────────────────────────────────


def test_aksi_tanya_skor_mengembalikan_kartu(session: Session, business: Business):
    import pytest

    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from app.api import main as api

    hari_ini = date.today()
    _jual(session, business, 1_000_000, hari_ini)
    _belanja(session, business, 700_000, hari_ini)

    data = api.chat(
        api.PesanMasuk(aksi="tanya_skor"), session=session, business=business, adapter=None
    )

    assert data["kartu"][0]["tipe"] == "skor"
    assert data["kartu"][0]["periode_tampil"]


def test_aksi_tanya_skor_label_asing_ditolak(session: Session, business: Business):
    """Label salah → 422, tak pernah jatuh diam-diam ke periode lain."""
    import pytest

    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from fastapi import HTTPException

    from app.api import main as api

    with pytest.raises(HTTPException) as e:
        api.chat(
            api.PesanMasuk(aksi="tanya_skor", periode="sejak_lebaran"),
            session=session,
            business=business,
            adapter=None,
        )
    assert e.value.status_code == 422

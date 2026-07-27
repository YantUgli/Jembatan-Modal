"""Parser periode — kosakata tertutup, diuji habis.

Tanggal acuan dipatok (Kamis, 23 Juli 2026) supaya hasilnya tidak berubah tiap
hari dijalankan. Yang paling penting di berkas ini bukan tiap frasa satu-satu,
melainkan tiga invarian: rentang **tak pernah** berakhir setelah hari ini, nama
bulan tanpa tahun **tak pernah** menunjuk masa depan, dan frasa yang mendua
menjadi `None` (bukan tebakan).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.periode import (
    baca_periode,
    menyebut_masa_depan,
    periode_dari_label,
)

# Kamis. Sengaja bukan Senin: "minggu ini" pada hari Senin cuma satu hari, dan
# bug pergeseran awal-pekan tak akan kelihatan.
HARI_INI = date(2026, 7, 23)


def rentang(teks: str) -> tuple[date, date] | None:
    p = baca_periode(teks, HARI_INI)
    return None if p is None else (p.mulai, p.selesai)


# ── Kosakata dasar ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("teks", "harap"),
    [
        ("untung hari ini berapa", (date(2026, 7, 23), date(2026, 7, 23))),
        ("rekap kemarin dong", (date(2026, 7, 22), date(2026, 7, 22))),
        ("gimana minggu ini", (date(2026, 7, 20), date(2026, 7, 23))),
        ("rekap keuangan minggu lalu", (date(2026, 7, 13), date(2026, 7, 19))),
        ("untung saya bulan ini berapa", (date(2026, 7, 1), date(2026, 7, 23))),
        ("untung bulan lalu berapa", (date(2026, 6, 1), date(2026, 6, 30))),
        ("omzet tahun ini", (date(2026, 1, 1), date(2026, 7, 23))),
    ],
)
def test_frasa_dasar(teks: str, harap: tuple[date, date]) -> None:
    assert rentang(teks) == harap


def test_bulan_kemarin_bukan_kemarin() -> None:
    """Overlap yang paling gampang salah: "bulan kemarin" mengandung "kemarin".
    Kalau pola pendeknya menang, jawabannya meleset sebulan penuh."""
    assert rentang("untung bulan kemarin berapa") == (date(2026, 6, 1), date(2026, 6, 30))


def test_minggu_kemarin_bukan_kemarin() -> None:
    assert rentang("rekap minggu kemarin") == (date(2026, 7, 13), date(2026, 7, 19))


def test_huruf_besar_dan_tanda_baca_tidak_mengganggu() -> None:
    assert rentang("Rekap, Bulan Lalu?") == (date(2026, 6, 1), date(2026, 6, 30))


# ── N bulan terakhir ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "teks",
    ["rekap 3 bulan terakhir", "rekap tiga bulan terakhir", "rekap 3 bulan ini"],
)
def test_n_bulan(teks: str) -> None:
    assert rentang(teks) == (date(2026, 5, 1), date(2026, 7, 23))


def test_n_bulan_satu_sama_dengan_bulan_berjalan() -> None:
    assert rentang("rekap 1 bulan terakhir") == (date(2026, 7, 1), date(2026, 7, 23))


@pytest.mark.parametrize("teks", ["rekap 0 bulan terakhir", "rekap 13 bulan terakhir"])
def test_n_bulan_di_luar_batas_tidak_dilayani(teks: str) -> None:
    """Di luar batas → None (default bulan berjalan yang tertulis di kartu),
    bukan diam-diam dipotong ke 12."""
    assert rentang(teks) is None


# ── Nama bulan ──────────────────────────────────────────────────────────────


def test_nama_bulan_lampau_tahun_ini() -> None:
    assert rentang("rekap juni") == (date(2026, 6, 1), date(2026, 6, 30))


def test_nama_bulan_berjalan_ditutup_hari_ini() -> None:
    assert rentang("rekap juli") == (date(2026, 7, 1), date(2026, 7, 23))


def test_nama_bulan_belum_lewat_ambil_tahun_sebelumnya() -> None:
    """Di Juli 2026, "Desember" berarti Des 2025. Memilih Des 2026 akan dijawab
    nol dan terbaca seperti usaha yang mati."""
    assert rentang("rekap desember") == (date(2025, 12, 1), date(2025, 12, 31))


def test_nama_bulan_dengan_tahun_eksplisit() -> None:
    assert rentang("rekap juni 2025") == (date(2025, 6, 1), date(2025, 6, 30))


def test_bulan_masa_depan_eksplisit_tidak_terbaca_sebagai_periode() -> None:
    assert rentang("rekap desember 2030") is None


def test_nama_bulan_di_dalam_kalimat_panjang() -> None:
    assert rentang("coba lihat laporan bulan agustus") == (date(2025, 8, 1), date(2025, 8, 31))


# ── Invarian ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "teks",
    [
        "hari ini",
        "bulan ini",
        "minggu ini",
        "tahun ini",
        "juli",
        "3 bulan terakhir",
        "12 bulan terakhir",
        "bulan lalu",
    ],
)
def test_tak_pernah_berakhir_setelah_hari_ini(teks: str) -> None:
    """Aturan #2 dalam bentuk tanggal: menyiratkan punya data untuk hari yang
    belum terjadi sama saja dengan mengarang angka."""
    p = baca_periode(teks, HARI_INI)
    assert p is not None
    assert p.selesai <= HARI_INI
    assert p.mulai <= p.selesai


def test_dua_frasa_berbeda_menjadi_none() -> None:
    """Menebak salah satu lebih buruk daripada default yang tertulis di kartu."""
    assert rentang("dari bulan lalu sampai bulan ini") is None


def test_frasa_yang_sama_dua_kali_tetap_terbaca() -> None:
    assert rentang("bulan lalu, iya bulan lalu") == (date(2026, 6, 1), date(2026, 6, 30))


@pytest.mark.parametrize(
    "teks",
    [
        "gimana keuangan saya",
        "untung risol berapa sih",
        "sejak lebaran gimana",
        "awal bulan sampai sekarang",
        "laporan singkat dong",
    ],
)
def test_tanpa_frasa_dikenal_menjadi_none(teks: str) -> None:
    """Batas kosakata yang diakui sadar. Pemanggil jatuh ke bulan berjalan —
    dan kartunya menuliskan periode itu, jadi meleset tetap terlihat."""
    assert rentang(teks) is None


def test_dua_bulan_belakangan_terbaca() -> None:
    assert rentang("dua bulan belakangan gimana") == (date(2026, 6, 1), date(2026, 7, 23))


# ── Masa depan ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "teks",
    ["untung besok berapa", "rekap bulan depan", "minggu depan gimana", "rekap desember 2030"],
)
def test_menyebut_masa_depan(teks: str) -> None:
    assert menyebut_masa_depan(teks, HARI_INI) is True


@pytest.mark.parametrize("teks", ["untung bulan lalu", "rekap kemarin", "rekap desember"])
def test_bukan_masa_depan(teks: str) -> None:
    assert menyebut_masa_depan(teks, HARI_INI) is False


# ── Label ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "harap"),
    [
        ("hari_ini", (date(2026, 7, 23), date(2026, 7, 23))),
        ("kemarin", (date(2026, 7, 22), date(2026, 7, 22))),
        ("minggu_ini", (date(2026, 7, 20), date(2026, 7, 23))),
        ("minggu_lalu", (date(2026, 7, 13), date(2026, 7, 19))),
        ("bulan_ini", (date(2026, 7, 1), date(2026, 7, 23))),
        ("bulan_lalu", (date(2026, 6, 1), date(2026, 6, 30))),
        ("tahun_ini", (date(2026, 1, 1), date(2026, 7, 23))),
        ("3_bulan", (date(2026, 5, 1), date(2026, 7, 23))),
        ("bulan:2026-06", (date(2026, 6, 1), date(2026, 6, 30))),
    ],
)
def test_periode_dari_label(label: str, harap: tuple[date, date]) -> None:
    p = periode_dari_label(label, HARI_INI)
    assert (p.mulai, p.selesai) == harap


@pytest.mark.parametrize(
    "label", ["", "bulan depan", "13_bulan", "bulan:2030-12", "bulan:2026-13", "BULAN_LALU"]
)
def test_label_asing_melempar(label: str) -> None:
    """Melempar, bukan diam-diam default: klien yang salah kirim harus dapat
    422, bukan jawaban periode lain yang tampak sah."""
    with pytest.raises(ValueError):
        periode_dari_label(label, HARI_INI)


@pytest.mark.parametrize(
    "teks",
    ["bulan lalu", "bulan ini", "minggu lalu", "kemarin", "3 bulan terakhir", "juni", "desember"],
)
def test_label_bisa_dibalik_jadi_rentang_yang_sama(teks: str) -> None:
    """Kartu mengirim balik `label` miliknya sendiri saat pengguna mengetuk chip
    lain — kalau labelnya tidak bisa dibalik, periode kartu berubah diam-diam."""
    p = baca_periode(teks, HARI_INI)
    assert p is not None
    ulang = periode_dari_label(p.label, HARI_INI)
    assert (ulang.mulai, ulang.selesai) == (p.mulai, p.selesai)

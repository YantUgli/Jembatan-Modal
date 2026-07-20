"""Penjaga sisi-input aturan #1.

Kasus-kasusnya diambil dari kegagalan NYATA di `docs/06-evaluasi-ekstraksi.md`,
bukan dikarang: Groq mengubah "laku 5 kotak risol 75rb" jadi 375.000 dan
"jual 2,5 kg ayam 90rb" jadi 225.000.

Setengah berkas ini menguji penjaganya JANGAN berbunyi. Itu disengaja — penjaga
yang sering salah tuduh akan dimatikan orang, dan penjaga yang mati tidak
menjaga apa pun.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.llm.penjaga import angka_di_teks, hasil_kali_terdeteksi, periksa_nominal

D = Decimal


# ── Angka yang benar-benar terbaca di kalimat ───────────────────────────────


def test_angka_bersuffix_dibaca_dua_bentuk():
    a = angka_di_teks("laku 5 kotak risol 75rb")
    assert D("5") in a
    assert D("75000") in a
    assert D("75") in a  # pengguna kadang menulis "75" untuk 75 ribu


def test_pemisah_ribuan_bukan_desimal():
    assert D("75000") in angka_di_teks("laku 75.000")
    assert D("15000") in angka_di_teks("harganya 15,000")


def test_koma_desimal_hanya_saat_bersuffix():
    """'1,5jt' = 1.500.000, sedangkan '1,500' tanpa suffix = seribu lima ratus."""
    assert D("1500000") in angka_di_teks("dapat 1,5jt")
    assert D("1500") in angka_di_teks("dapat 1,500")


def test_slang_dikenali():
    assert D("5000") in angka_di_teks("laku goceng")
    assert D("10000") in angka_di_teks("beli es ceban")
    assert D("1000000") in angka_di_teks("omzet sejuta")


# ── Pola perkalian: yang HARUS ditangkap ───────────────────────────────────


def test_perkalian_risol_ditangkap():
    """Kegagalan nyata Groq: 5 x 75rb = 375.000, padahal 75rb itu totalnya."""
    assert hasil_kali_terdeteksi("laku 5 kotak risol 75rb", D("375000"), D("5")) == D("75000")


def test_perkalian_desimal_ditangkap():
    """Kegagalan nyata kedua: 2,5 x 90rb = 225.000."""
    assert hasil_kali_terdeteksi("jual 2,5 kg ayam 90rb", D("225000"), D("2.5")) == D("90000")


def test_harga_satuan_disebut_total_tidak():
    """Pola paling menggoda: harga per kotak DAN jumlah ada di kalimat, tapi
    totalnya tidak pernah diucapkan. Qwen menjawab `Gagal` di sini; penjaga ini
    adalah jaring untuk model yang tidak sedisiplin itu."""
    teks = "risol 15rb sekotak, tadi laku 5 kotak"
    assert hasil_kali_terdeteksi(teks, D("75000"), D("5")) == D("15000")


def test_alasan_penolakan_menyebut_cara_benarnya():
    alasan = periksa_nominal("laku 5 kotak risol 75rb", D("375000"), D("5"))
    assert alasan is not None
    assert "375000" in alasan
    assert "ditanyakan" in alasan  # arahkan ke bertanya, bukan sekadar menolak


# ── Yang HARUS dibiarkan lewat ─────────────────────────────────────────────


def test_nominal_yang_diucapkan_tidak_dituduh():
    """Justru ini perilaku yang kita mau: model menyalin, bukan menghitung."""
    assert hasil_kali_terdeteksi("laku 5 kotak risol 75rb", D("75000"), D("5")) is None


def test_qty_satu_tidak_pernah_dituduh():
    assert hasil_kali_terdeteksi("beli beras 1 sak 320rb", D("320000"), D("1")) is None


def test_tanpa_qty_tidak_dituduh():
    assert hasil_kali_terdeteksi("hari ini dapat 300rb", D("300000"), None) is None


def test_kebetulan_yang_tidak_terbaca_di_kalimat_tidak_dituduh():
    """Nominal 150.000 = 3 x 50.000, tapi 50.000 tak pernah disebut. Tanpa
    syarat 'pengali harus terbaca di kalimat', penjaga ini akan menuduh
    kalimat jujur sepanjang hari."""
    assert hasil_kali_terdeteksi("laku 3 lusin 150rb", D("150000"), D("3")) is None


def test_pisang_dua_sisir_lolos():
    assert periksa_nominal("beli pisang 2 sisir 30rb", D("30000"), D("2")) is None


@pytest.mark.parametrize(
    "teks,nominal,qty",
    [
        ("laku 3 lusin 180rb", D("180000"), D("3")),
        ("beli tepung setengah kilo 7rb", D("7000"), D("0.5")),
        ("jual 2,5 kg ayam 90rb", D("90000"), D("2.5")),
        ("kemarin beli ayam 200rb", D("200000"), None),
        ("laku goceng", D("5000"), None),
    ],
)
def test_kasus_evaluasi_yang_benar_tidak_ada_yang_kena(teks, nominal, qty):
    """Seluruh kasus benar dari set evaluasi harus lolos penjaga ini."""
    assert periksa_nominal(teks, nominal, qty) is None

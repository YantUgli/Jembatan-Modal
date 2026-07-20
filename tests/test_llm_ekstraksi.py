"""Jalur ekstraksi domain: penjaga aturan #1 harus tak terlewatkan."""

from __future__ import annotations

from datetime import date

from app.llm.ekstraksi import ekstrak_transaksi
from app.llm.kontrak import Ekstraksi, Gagal
from app.llm.palsu import AdapterPalsu

HARI_INI = date(2026, 6, 10)

RISOL = "laku 5 kotak risol 75rb"


def _adapter(jawab):
    return AdapterPalsu(jawaban_ekstrak={RISOL: jawab})


def _baris(nominal: str, qty: str | None = None):
    b = {"jenis": "pemasukan", "nominal": nominal, "tanggal": "2026-06-10",
         "produk": "risol"}
    if qty:
        b["qty"] = qty
        b["satuan"] = "kotak"
    return {"baris": [b]}


def test_nominal_yang_diucapkan_diteruskan():
    hasil = ekstrak_transaksi(_adapter(_baris("75000", "5")), RISOL, HARI_INI)

    assert isinstance(hasil, Ekstraksi)
    assert hasil.data.baris[0].nominal == 75000


def test_nominal_hasil_perkalian_ditolak():
    """Model mengalikan 5 x 75rb. Ini pernah terjadi sungguhan pada Groq —
    dan kalau lolos, 375.000 masuk database sebagai fakta."""
    hasil = ekstrak_transaksi(_adapter(_baris("375000", "5")), RISOL, HARI_INI)

    assert isinstance(hasil, Gagal)
    assert "375000" in hasil.alasan
    assert hasil.yang_kurang == ["nominal"]


def test_satu_baris_bermasalah_menolak_seluruh_kalimat():
    """Menyimpan separuh kalimat membuat pengguna kehilangan jejak apa yang
    sudah tercatat dan apa yang belum."""
    dua = {"baris": [
        {"jenis": "pemasukan", "nominal": "75000", "tanggal": "2026-06-10"},
        {"jenis": "pemasukan", "nominal": "375000", "tanggal": "2026-06-10",
         "qty": "5", "satuan": "kotak", "produk": "risol"},
    ]}
    hasil = ekstrak_transaksi(_adapter(dua), RISOL, HARI_INI)

    assert isinstance(hasil, Gagal)


def test_gagal_dari_adapter_diteruskan_apa_adanya():
    asli = Gagal(alasan="Kalimat tidak menyebut nominal", yang_kurang=["nominal"])
    hasil = ekstrak_transaksi(_adapter(asli), RISOL, HARI_INI)

    assert hasil is asli


def test_tanggal_acuan_disuntik_ke_instruksi():
    a = _adapter(_baris("75000"))
    ekstrak_transaksi(a, RISOL, HARI_INI)

    assert "2026-06-10" in a.panggilan[0].instruksi

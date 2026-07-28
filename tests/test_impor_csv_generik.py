"""`baca_csv_generik` — pipa unggah CSV generik (§5 B3 rencana eksekusi).

Cakupan: deteksi encoding, deteksi pemisah kolom, deteksi baris header,
validasi berkas (tipe/ukuran/isi kosong). Pemetaan kolom→transaksi sengaja
BELUM ada (`petakan_baris_generik`) — ditahan sampai fixture A3, lihat
docstring modul `app/impor/csv_generik.py`.
"""

from __future__ import annotations

import pytest

from app.impor.csv_generik import (
    UKURAN_MAKS_BYTES,
    BerkasTidakValid,
    baca_csv_generik,
    petakan_baris_generik,
)


# ── Deteksi encoding ─────────────────────────────────────────────────────────


def test_baca_csv_utf8_polos():
    data = "tanggal,keterangan,nominal\n2026-07-01,Jual risol,75000\n".encode("utf-8")
    hasil = baca_csv_generik("catatan.csv", data)
    # utf-8-sig mendekode utf-8 tanpa BOM sama persis dengan utf-8 — dicoba
    # lebih dulu (lihat _ENCODING_DICOBA), jadi keduanya sah di sini.
    assert hasil.encoding in ("utf-8", "utf-8-sig")
    assert hasil.header == ["tanggal", "keterangan", "nominal"]
    assert hasil.baris == [
        {"tanggal": "2026-07-01", "keterangan": "Jual risol", "nominal": "75000"}
    ]


def test_baca_csv_utf8_bom_tidak_bocor_ke_header():
    data = "tanggal,keterangan\n2026-07-01,Beli tepung\n".encode("utf-8-sig")
    hasil = baca_csv_generik("catatan.csv", data)
    assert hasil.encoding == "utf-8-sig"
    assert hasil.header[0] == "tanggal"  # bukan '﻿tanggal'


def test_baca_csv_cp1252_fallback():
    """Karakter non-UTF-8 (mis. dari ekspor Windows lama) tetap terbaca."""
    data = "keterangan,nominal\nJual kue cokelat\xe9,50000\n".encode("cp1252")
    hasil = baca_csv_generik("rekening.csv", data)
    assert hasil.encoding == "cp1252"
    assert "cokelaté" in hasil.baris[0]["keterangan"]


# ── Deteksi pemisah kolom ────────────────────────────────────────────────────


def test_baca_csv_pemisah_titik_koma():
    data = "tanggal;nominal;keterangan\n2026-07-01;75000;Jual risol\n".encode("utf-8")
    hasil = baca_csv_generik("export_bank.csv", data)
    assert hasil.delimiter == ";"
    assert hasil.baris[0]["nominal"] == "75000"


def test_baca_csv_pemisah_tab():
    data = "tanggal\tnominal\n2026-07-01\t75000\n".encode("utf-8")
    hasil = baca_csv_generik("export.csv", data)
    assert hasil.delimiter == "\t"


# ── Deteksi header ───────────────────────────────────────────────────────────


def test_baca_csv_header_terdeteksi():
    data = "tanggal,nominal\n2026-07-01,75000\n2026-07-02,50000\n".encode("utf-8")
    hasil = baca_csv_generik("catatan.csv", data)
    assert hasil.header_terdeteksi is True
    assert len(hasil.baris) == 2


def test_baca_csv_tanpa_header_dapat_nama_kolom_sintetis():
    """Semua baris tampak seperti data (semua numerik) → tak ada header asli;
    kolom dapat nama sintetis, bukan baris pertama diam-diam hilang."""
    data = "2026-07-01,75000\n2026-07-02,50000\n2026-07-03,60000\n".encode("utf-8")
    hasil = baca_csv_generik("catatan.csv", data)
    assert hasil.header_terdeteksi is False
    assert hasil.header == ["kolom_1", "kolom_2"]
    assert len(hasil.baris) == 3  # baris pertama tetap ikut sebagai data


def test_baca_csv_baris_ragged_tidak_crash():
    """Baris yang jumlah kolomnya beda-beda tidak boleh melempar exception."""
    data = "tanggal,keterangan,nominal\n2026-07-01,Jual,75000\n2026-07-02,Cuma dua\n".encode(
        "utf-8"
    )
    hasil = baca_csv_generik("catatan.csv", data)
    assert hasil.baris[1]["nominal"] == ""


# ── Validasi berkas ──────────────────────────────────────────────────────────


def test_baca_csv_ekstensi_asing_ditolak():
    with pytest.raises(BerkasTidakValid, match="Tipe berkas"):
        baca_csv_generik("catatan.xlsx", b"a,b\n1,2\n")


def test_baca_csv_kosong_ditolak():
    with pytest.raises(BerkasTidakValid, match="kosong"):
        baca_csv_generik("catatan.csv", b"")


def test_baca_csv_hanya_baris_kosong_ditolak():
    with pytest.raises(BerkasTidakValid):
        baca_csv_generik("catatan.csv", b"\n\n   \n")


def test_baca_csv_terlalu_besar_ditolak():
    data = b"a,b\n" + b"1,2\n" * (UKURAN_MAKS_BYTES // 4 + 1)
    with pytest.raises(BerkasTidakValid, match="terlalu besar"):
        baca_csv_generik("catatan.csv", data)


# ── Pemetaan kolom: sengaja belum ada ────────────────────────────────────────


def test_petakan_baris_generik_belum_diimplementasikan():
    """Ditahan sampai fixture A3 — gagal jelas (NotImplementedError), bukan
    diam-diam menebak format dan salah petakan kolom."""
    with pytest.raises(NotImplementedError, match="fixture A3"):
        petakan_baris_generik({"tanggal": "2026-07-01", "nominal": "75000"})

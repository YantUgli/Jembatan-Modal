"""Aksi impor di lapisan HTTP: validasi masukan & pagar tenant.

Mengikuti pola `tests/test_api_dokumen.py` — `fastapi` di-skip bila belum
terpasang (janji: core bisa diinstal tanpa dependensi berat), dan fungsi rute
dipanggil langsung alih-alih lewat `TestClient` (yang menuntut klien HTTP
tambahan hanya untuk melintasi loopback).

Yang diuji di sini adalah keputusan yang memang hidup di lapisan ini: kode status
yang dipilih saat masukan kurang, dan bahwa `business_id` tak pernah datang dari
klien.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.impor import GAGAL, YAKIN, BarisDraft
from app.llm.skema import BarisTransaksi
from app.models import Business, JenisTransaksi, StatusBarisImpor, Transaction
from app.services.impor import buat_draft, putuskan_baris, tinjau_impor

pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")

from fastapi import HTTPException  # noqa: E402

from app.api import main as api  # noqa: E402

HARI_INI = date(2026, 7, 26)


def _draft(session: Session, business: Business):
    return buat_draft(
        session,
        business.id,
        "teks",
        [
            BarisDraft(
                raw="12/7 laku risol 75rb",
                baris=BarisTransaksi(
                    jenis=JenisTransaksi.pemasukan,
                    nominal=75_000,
                    tanggal=date(2026, 7, 12),
                ),
                keyakinan=YAKIN,
            ),
            BarisDraft(raw="Catatan Juli", keyakinan=GAGAL, catatan="Tidak terbaca."),
        ],
    )


def _chat(session: Session, business: Business, **pesan) -> dict:
    """`adapter` tak dipakai jalur aksi terstruktur — impor tak memanggil LLM."""
    return api.chat(
        api.PesanMasuk(**pesan), session=session, business=business, adapter=None
    )


def _row_ids(session: Session, business: Business, import_id: int) -> list[int]:
    r = tinjau_impor(session, business.id, import_id)
    assert r is not None
    return [b.row_id for b in r.baris]


def _jumlah_transaksi(session: Session) -> int:
    return len(list(session.scalars(select(Transaction)).all()))


# ── Validasi masukan ────────────────────────────────────────────────────────


def test_aksi_impor_tanpa_import_id_422(session: Session, business: Business):
    with pytest.raises(HTTPException) as e:
        _chat(session, business, aksi="impor_tinjau")
    assert e.value.status_code == 422
    assert "import_id" in e.value.detail


def test_putuskan_tanpa_row_id_422(session: Session, business: Business):
    impor = _draft(session, business)
    with pytest.raises(HTTPException) as e:
        _chat(session, business, aksi="impor_putuskan", import_id=impor.id)
    assert e.value.status_code == 422


def test_aksi_impor_tak_dikenal_422(session: Session, business: Business):
    impor = _draft(session, business)
    with pytest.raises(HTTPException) as e:
        _chat(session, business, aksi="impor_ngawur", import_id=impor.id)
    assert e.value.status_code == 422


def test_mencentang_baris_tak_terbaca_422_bukan_500(session: Session, business: Business):
    impor = _draft(session, business)
    gagal = _row_ids(session, business, impor.id)[1]

    with pytest.raises(HTTPException) as e:
        _chat(
            session,
            business,
            aksi="impor_putuskan",
            import_id=impor.id,
            row_id=gagal,
            terima=True,
        )
    assert e.value.status_code == 422
    assert "belum ada yang bisa disimpan" in e.value.detail


# ── Jalur normal ────────────────────────────────────────────────────────────


def test_tinjau_lalu_centang_lalu_simpan(session: Session, business: Business):
    impor = _draft(session, business)

    data = _chat(session, business, aksi="impor_tinjau", import_id=impor.id)
    assert data["versi"] == 9
    assert data["kartu"][0]["tipe"] == "impor"
    assert data["kartu"][0]["jumlah"] == 2

    baik = _row_ids(session, business, impor.id)[0]
    data = _chat(
        session, business, aksi="impor_putuskan", import_id=impor.id, row_id=baik, terima=True
    )
    assert data["kartu"][0]["jumlah_diterima"] == 1
    assert _jumlah_transaksi(session) == 0  # ← aturan #3

    data = _chat(session, business, aksi="impor_konfirmasi", import_id=impor.id)
    assert data["kartu"][0]["jumlah_tersimpan"] == 1
    assert _jumlah_transaksi(session) == 1


def test_terima_yakin_lewat_api(session: Session, business: Business):
    impor = _draft(session, business)
    data = _chat(session, business, aksi="impor_terima_yakin", import_id=impor.id)

    assert data["kartu"][0]["jumlah_diterima"] == 1
    assert _jumlah_transaksi(session) == 0


# ── Pagar tenant (aturan #6) ────────────────────────────────────────────────


def test_import_id_tetangga_tak_bisa_dikonfirmasi(
    session: Session, business: Business, tetangga: Business
):
    """`business_id` diselesaikan server dari sesi, jadi `import_id` milik orang
    lain tak menemukan apa pun — dijawab kalimat, bukan 403 yang mengonfirmasi
    bahwa draft itu ada."""
    impor = _draft(session, tetangga)
    baik = _row_ids(session, tetangga, impor.id)[0]
    putuskan_baris(session, tetangga.id, impor.id, baik, True)

    data = _chat(session, business, aksi="impor_konfirmasi", import_id=impor.id)
    assert data["kartu"][0]["tipe"] == "klarifikasi"
    assert _jumlah_transaksi(session) == 0

    # Draft aslinya tak tersentuh: masih tercentang, masih belum tersimpan.
    r = tinjau_impor(session, tetangga.id, impor.id)
    assert r is not None
    assert r.baris[0].status == StatusBarisImpor.diterima.value
    assert r.jumlah_tersimpan == 0

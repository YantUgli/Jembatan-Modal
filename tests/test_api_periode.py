"""Parameter `periode` di lapisan HTTP — chip kartu, bukan kalimat.

Pola sama dengan `tests/test_api_impor.py`: `fastapi` di-skip bila belum
terpasang, dan fungsi rute dipanggil langsung.

Yang diuji di sini keputusan yang memang hidup di lapisan ini: **label asing
ditolak 422, bukan diam-diam jatuh ke default** (klien salah kirim akan dapat
jawaban periode lain yang tampak sah), dan urutan menang antara `mulai`/`selesai`
dan `periode`.

Tanggal acuan rute adalah `date.today()` yang sebenarnya, jadi rentang di sini
dihitung ulang sendiri dari kalender — bukan diambil dari `app.services.periode`.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import Business, JenisTransaksi
from tests.conftest import buat_transaksi

pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")

from fastapi import HTTPException  # noqa: E402

from app.api import main as api  # noqa: E402


def _chat(session: Session, business: Business, **pesan) -> dict:
    """Jalur aksi terstruktur tak memanggil LLM — `adapter` sengaja None."""
    return api.chat(api.PesanMasuk(**pesan), session=session, business=business, adapter=None)


def _bulan_lalu() -> tuple[date, date]:
    """Bulan kalender penuh sebelum bulan berjalan, dihitung sendiri."""
    akhir = date.today().replace(day=1) - timedelta(days=1)
    return akhir.replace(day=1), akhir


def _jual(session, business, nominal, tanggal):
    return buat_transaksi(
        session, business, JenisTransaksi.pemasukan, Decimal(nominal), tanggal
    )


def _dua_bulan(session: Session, business: Business) -> None:
    lalu_awal, _ = _bulan_lalu()
    _jual(session, business, 400000, lalu_awal + timedelta(days=5))
    _jual(session, business, 75000, date.today().replace(day=1))


# ── Label periode ───────────────────────────────────────────────────────────


def test_label_menggeser_rentang(session: Session, business: Business):
    _dua_bulan(session, business)

    data = _chat(session, business, aksi="tanya_keuangan", periode="bulan_lalu")

    kartu = data["kartu"][0]
    assert kartu["omzet_tampil"] == "Rp400.000"  # bulan berjalan tak ikut
    assert kartu["periode_label"] == "bulan_lalu"


def test_tanpa_periode_default_bulan_berjalan(session: Session, business: Business):
    _dua_bulan(session, business)

    data = _chat(session, business, aksi="tanya_keuangan")

    kartu = data["kartu"][0]
    assert kartu["omzet_tampil"] == "Rp75.000"
    assert kartu["periode_label"] == "bulan_ini"


@pytest.mark.parametrize("label", ["bulan depan", "kapan_saja", "13_bulan", ""])
def test_label_asing_422(session: Session, business: Business, label: str):
    """⛔ Bukan diam-diam default: jawaban periode lain yang tampak sah adalah
    kesalahan yang tak terlihat siapa pun."""
    with pytest.raises(HTTPException) as e:
        _chat(session, business, aksi="tanya_keuangan", periode=label)
    assert e.value.status_code == 422


def test_mulai_selesai_menang_atas_label(session: Session, business: Business):
    _dua_bulan(session, business)
    awal, akhir = _bulan_lalu()

    data = _chat(
        session,
        business,
        aksi="tanya_keuangan",
        periode="bulan_ini",
        mulai=awal,
        selesai=akhir,
    )

    assert data["kartu"][0]["omzet_tampil"] == "Rp400.000"


def test_untung_menerima_label_dan_menyebut_periodenya(session: Session, business: Business):
    _dua_bulan(session, business)

    kartu = _chat(session, business, aksi="tanya_untung", periode="bulan_lalu")["kartu"][0]

    assert kartu["periode_label"] == "bulan_lalu"
    assert kartu["periode_tampil"]  # kartu untung tak pernah lagi tanpa periode


# ── Riwayat ─────────────────────────────────────────────────────────────────


def test_riwayat_tanpa_periode_tak_berfilter(session: Session, business: Business):
    _dua_bulan(session, business)

    kartu = _chat(session, business, aksi="lihat_transaksi")["kartu"][0]

    assert len(kartu["baris"]) == 2
    assert kartu["periode_tampil"] == ""


def test_riwayat_dengan_label_terfilter(session: Session, business: Business):
    _dua_bulan(session, business)

    kartu = _chat(session, business, aksi="lihat_transaksi", periode="bulan_lalu")["kartu"][0]

    assert len(kartu["baris"]) == 1
    assert kartu["baris"][0]["nominal_tampil"] == "Rp400.000"
    assert kartu["periode_label"] == "bulan_lalu"

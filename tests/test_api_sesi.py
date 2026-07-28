"""GET /sesi — kartu pembuka + pemicu snapshot skor harian (E1, 2026-07-28).

Riwayat `score_snapshots` dipakai untuk grafik tren, jadi dipilih pemicu
"lazy-daily" yang menumpang request `/sesi` (dibuka sekali per kunjungan)
alih-alih proses cron baru — lihat `docs/keputusan.md` 2026-07-28 (E1) dan
`docs/plan-lanjutan.md` §E1. `simpan_snapshot_skor` sendiri sudah dedup nilai
identik (`app/services/skor.py`), jadi yang diuji di sini murni efek samping
di jalur produksi: snapshot benar-benar ada di storage setelah `/sesi`
dipanggil, dan dedup itu tetap berlaku dari jalur produksi ini juga.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, JenisTransaksi, ScoreSnapshot
from tests.conftest import buat_transaksi

pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")

from app.api import main as api  # noqa: E402

HARI_INI = date(2026, 7, 28)


class _TanggalBeku(date):
    """`date` dengan `today()` dibekukan — sama pola dengan test_api_dokumen.py."""

    @classmethod
    def today(cls) -> date:
        return HARI_INI


@pytest.fixture(autouse=True)
def tanggal_beku(monkeypatch):
    monkeypatch.setattr(api, "date", _TanggalBeku)


def _snapshot_business(session: Session, business_id: int) -> list[ScoreSnapshot]:
    return list(
        session.scalars(select(ScoreSnapshot).where(ScoreSnapshot.business_id == business_id)).all()
    )


def test_sesi_menulis_snapshot_skor_ke_storage(session: Session, business: Business):
    """Bukan sekadar memverifikasi fungsi dipanggil (mock) — baris snapshot
    benar-benar terbaca kembali dari `score_snapshots` setelah /sesi."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, HARI_INI)

    assert _snapshot_business(session, business.id) == []

    api.sesi(business=business, session=session)

    snapshot = _snapshot_business(session, business.id)
    assert len(snapshot) == 1
    assert snapshot[0].periode.endswith(HARI_INI.isoformat())


def test_sesi_dipanggil_berkali_kali_sehari_tidak_menduplikasi(
    session: Session, business: Business
):
    """Tanpa transaksi baru di antaranya, nilai skor identik → dedup
    `simpan_snapshot_skor` tetap berlaku dari jalur produksi ini."""
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, HARI_INI)

    api.sesi(business=business, session=session)
    api.sesi(business=business, session=session)
    api.sesi(business=business, session=session)

    assert len(_snapshot_business(session, business.id)) == 1


def test_sesi_menulis_snapshot_walau_skor_belum_diketahui(session: Session, business: Business):
    """Usaha baru tanpa transaksi sama sekali — skor belum diketahui, tapi
    riwayat "belum bisa dihitung pada tanggal sekian" tetap sah dicatat
    (docstring `simpan_snapshot_skor`)."""
    api.sesi(business=business, session=session)

    snapshot = _snapshot_business(session, business.id)
    assert len(snapshot) == 1
    assert snapshot[0].skor_total is None


def test_sesi_tetap_mengembalikan_kartu_sapaan(session: Session, business: Business):
    """Regresi: efek samping snapshot tidak mengubah kontrak kartu pembuka."""
    data = api.sesi(business=business, session=session)

    assert data["kartu"][0]["tipe"] == "sapaan"


def test_sesi_isolasi_tenant_snapshot(session: Session, business: Business, tetangga: Business):
    """Aturan #6 — snapshot business lain tidak ikut terhitung/tercampur."""
    buat_transaksi(session, tetangga, JenisTransaksi.pemasukan, 50_000, HARI_INI)

    api.sesi(business=tetangga, session=session)

    assert _snapshot_business(session, business.id) == []
    assert len(_snapshot_business(session, tetangga.id)) == 1

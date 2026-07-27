"""Skema `panduan_entries` & tautannya ke `kur_outcomes` (aturan #4).

Fitur "4c" (asisten KUR) belum digarap — belum ada tool/service yang
membaca tabel ini (lihat docs/keputusan.md). Yang diuji di sini murni lapisan
skema: field wajib, default, dan tautan FK yang jadi prasyarat penegakan
aturan #4 saat 4c akhirnya dibangun.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Business, HasilKur, KurOutcome, PanduanEntry, StatusPanduan, TingkatSumber

TGL = date(2026, 7, 27)


def _entri(
    session: Session,
    *,
    topik: str = "bunga",
    tingkat_sumber: TingkatSumber = TingkatSumber.resmi_regulasi,
    status: StatusPanduan | None = None,
    **kw,
) -> PanduanEntry:
    entri = PanduanEntry(
        topik=topik,
        isi=kw.pop("isi", "KUR Mikro & Kecil sektor produksi: 6% efektif/tahun."),
        sumber_url=kw.pop("sumber_url", "https://peraturan.go.id/permenko-1-2026"),
        tingkat_sumber=tingkat_sumber,
        tanggal_akses=kw.pop("tanggal_akses", TGL),
        **kw,
    )
    if status is not None:
        entri.status = status
    session.add(entri)
    session.flush()
    return entri


def test_entri_minimal_tersimpan_dengan_status_default_aktif(session: Session):
    entri = _entri(session)

    assert entri.id is not None
    assert entri.status is StatusPanduan.aktif  # default ORM, bukan tebakan
    assert entri.digantikan_oleh is None
    assert entri.versi_regulasi is None
    assert entri.pasal_rujukan is None


def test_tingkat_sumber_wajib_diisi(session: Session):
    """Aturan #4: entri tanpa tingkat_sumber tak boleh lolos ke DB —
    tanpa kolom ini, penjaga 'jangan pakai sumber lainnya' tak bisa ditegakkan."""
    entri = PanduanEntry(
        topik="bunga",
        isi="isi tanpa tingkat sumber",
        sumber_url="https://ekon.go.id/x",
        tanggal_akses=TGL,
    )
    session.add(entri)
    with pytest.raises(IntegrityError):
        session.flush()


def test_topik_tetap_string_bebas_bukan_enum(session: Session):
    """Konvensi repo (base.py): topik panduan sengaja string bebas karena
    daftarnya tumbuh — nilai di luar 'kur' pun harus tetap tersimpan."""
    entri = _entri(session, topik="izin_usaha")
    assert entri.topik == "izin_usaha"


def test_entri_superseded_menunjuk_penggantinya_dan_tetap_tersimpan(session: Session):
    """Entri lama tidak dihapus saat digantikan — dibutuhkan untuk audit &
    kalibrasi kur_outcomes historis dengan aturan yang berlaku saat itu."""
    lama = _entri(
        session,
        isi="KUR Mikro berjenjang 6%-9% (Permenko 7/2025 — usang per 2026-01-13).",
        versi_regulasi="Permenko 7/2025",
    )
    baru = _entri(
        session,
        isi="KUR Mikro flat 6%/tahun (Permenko 1/2026).",
        versi_regulasi="Permenko 1/2026",
        tanggal_berlaku=date(2026, 1, 13),
    )
    lama.status = StatusPanduan.superseded
    lama.digantikan_oleh = baru.id
    session.flush()

    semua = session.scalars(select(PanduanEntry).order_by(PanduanEntry.id)).all()
    assert [e.status for e in semua] == [StatusPanduan.superseded, StatusPanduan.aktif]
    assert semua[0].digantikan_oleh == baru.id

    hanya_aktif = session.scalars(
        select(PanduanEntry).where(PanduanEntry.status == StatusPanduan.aktif)
    ).all()
    assert hanya_aktif == [baru]


def test_entri_tingkat_sumber_lainnya_tetap_tersimpan_untuk_ditolak_di_layer_lain(
    session: Session,
):
    """Skema sendiri tidak menolak `lainnya` — penolakannya nanti tugas guard
    di service layer (belum ada), bukan constraint DB. Diuji di sini supaya
    nilainya tersimpan persis, prasyarat guard tsb bisa dites nanti."""
    entri = _entri(session, tingkat_sumber=TingkatSumber.lainnya)
    assert entri.tingkat_sumber is TingkatSumber.lainnya


def test_entri_draft_tetap_tersimpan_untuk_ditolak_di_layer_lain(session: Session):
    """Pola sama dengan StatusImpor.draft/StatusBarisImpor.draft: isi ada,
    tapi belum dicek ke pasal resmi — guard (belum ada) yang wajib menolaknya
    saat 4c dibangun, bukan constraint DB. Diuji di sini agar nilainya
    tersimpan persis, prasyarat guard tsb bisa dites nanti."""
    entri = _entri(session, status=StatusPanduan.draft, versi_regulasi="Permenko 1/2026")
    assert entri.status is StatusPanduan.draft

    hanya_aktif = session.scalars(
        select(PanduanEntry).where(PanduanEntry.status == StatusPanduan.aktif)
    ).all()
    assert entri not in hanya_aktif


def test_kur_outcome_bisa_menunjuk_panduan_entry_yang_berlaku_saat_pengajuan(
    session: Session, business: Business
):
    panduan = _entri(session)
    outcome = KurOutcome(
        business_id=business.id,
        panduan_entry_id=panduan.id,
        hasil=HasilKur.lolos,
        plafon_cair=50_000_000,
        tanggal=TGL,
    )
    session.add(outcome)
    session.flush()

    tersimpan = session.scalars(select(KurOutcome)).one()
    assert tersimpan.panduan_entry_id == panduan.id


def test_kur_outcome_panduan_entry_nullable(session: Session, business: Business):
    """Outcome bisa dicatat tanpa tautan panduan (panduan_entries masih
    kosong) — mencatat hasil tak boleh diblokir oleh gap data lain."""
    outcome = KurOutcome(
        business_id=business.id,
        hasil=HasilKur.ditolak,
        alasan_penolakan="SLIK OJK bermasalah",
        tanggal=TGL,
    )
    session.add(outcome)
    session.flush()

    assert outcome.panduan_entry_id is None

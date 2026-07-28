"""Seed panduan bunga KUR (app/seeds/panduan_kur_bunga.py).

Bukan data demo per-tenant (panduan_entries global, bukan business_id) —
diuji seperti fitur lain: idempoten, dan status aktif benar-benar tersimpan
(A1 terverifikasi 2026-07-28 — lihat docs/checklist-verifikasi-bunga-kur.md).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_bunga import VERSI, seed


def test_seed_menghasilkan_delapan_entri_berstatus_aktif(session: Session):
    entri = seed(session)

    assert len(entri) == 8
    assert all(e.topik == "bunga" for e in entri)
    assert all(e.status is StatusPanduan.aktif for e in entri)
    assert all(e.versi_regulasi == VERSI for e in entri)
    assert all(e.sumber_url and "Details" in e.sumber_url for e in entri)


def test_seed_mikro_dan_kecil_nonekspor_terpisah(session: Session):
    """Koreksi load-bearing: jenjang non-ekspor Mikro (6-7%) dan Kecil
    (6-7-8-9%) tidak boleh jadi satu entri yang sama."""
    entri = seed(session)
    mikro = next(e for e in entri if "Mikro untuk usaha perdagangan" in e.pertanyaan_kanonik)
    kecil = next(e for e in entri if "Kecil untuk usaha perdagangan" in e.pertanyaan_kanonik)

    assert mikro.id != kecil.id
    assert "9%" not in mikro.isi
    assert "maksimal 2 akad" in mikro.isi
    assert "9%" in kecil.isi
    assert "Rp500 juta" in kecil.isi


def test_seed_idempoten_tidak_menduplikasi(session: Session):
    seed(session)
    seed(session)

    semua = session.scalars(select(PanduanEntry).where(PanduanEntry.versi_regulasi == VERSI)).all()
    assert len(semua) == 8


def test_seed_menimpa_draft_lama_dengan_isi_terverifikasi(session: Session):
    """Database yang sudah kadung menyimpan draft riset-sekunder lama ikut
    ter-upgrade begitu seed dijalankan ulang — bukan cuma dilewati."""
    lama = PanduanEntry(
        topik="bunga",
        pertanyaan_kanonik="Berapa bunga KUR Super Mikro?",
        isi="Isi draft lama yang belum diverifikasi.",
        sumber_url="https://contoh.tidak-final/",
        tingkat_sumber=TingkatSumber.resmi_regulasi,
        versi_regulasi=VERSI,
        status=StatusPanduan.draft,
        tanggal_akses=date(2026, 7, 1),
    )
    session.add(lama)
    session.flush()

    seed(session)

    session.refresh(lama)
    assert lama.status is StatusPanduan.aktif
    assert lama.isi != "Isi draft lama yang belum diverifikasi."
    assert "Details" in lama.sumber_url

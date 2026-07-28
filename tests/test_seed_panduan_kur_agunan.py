"""Seed panduan agunan KUR (app/seeds/panduan_kur_agunan.py).

Data sudah terverifikasi (Lampiran A.3, `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`) →
masuk langsung `status=aktif`, bukan lewat gerbang `draft` — pengecualian yang
dicatat di `docs/keputusan.md` 2026-07-28 (E2), bukan preseden umum untuk topik
KUR berikutnya.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_agunan import PERTANYAAN_AGUNAN, TOPIK, VERSI, seed


def test_seed_menghasilkan_satu_entri_berstatus_aktif(session: Session):
    entri = seed(session)

    assert entri.topik == TOPIK
    assert entri.pertanyaan_kanonik == PERTANYAAN_AGUNAN
    assert entri.status is StatusPanduan.aktif
    assert entri.versi_regulasi == VERSI
    assert entri.sumber_url and "Details" in entri.sumber_url
    assert "Pasal 20" in entri.pasal_rujukan
    assert "Pasal 21" in entri.pasal_rujukan


def test_seed_menyebut_ambang_plafon_dan_sanksi(session: Session):
    entri = seed(session)

    assert "Rp100 juta" in entri.isi
    assert "petani tebu" in entri.isi
    assert "tidak dibayarkan" in entri.isi


def test_seed_idempoten_tidak_menduplikasi(session: Session):
    seed(session)
    seed(session)

    semua = session.scalars(
        select(PanduanEntry).where(
            PanduanEntry.topik == TOPIK, PanduanEntry.versi_regulasi == VERSI
        )
    ).all()
    assert len(semua) == 1


def test_seed_menimpa_draft_lama_dengan_isi_terverifikasi(session: Session):
    lama = PanduanEntry(
        topik=TOPIK,
        pertanyaan_kanonik=PERTANYAAN_AGUNAN,
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

"""Seed panduan agunan KUR (app/seeds/panduan_kur_agunan.py).

Data sudah terverifikasi (Lampiran A.3, `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`) →
masuk langsung `status=aktif`, bukan lewat gerbang `draft` — pengecualian yang
dicatat di `docs/keputusan.md` (E2 2026-07-28, F2 2026-07-29), bukan preseden
umum untuk topik KUR berikutnya.

F2 memecah entri overview lama (plafon-agnostik) jadi tiga entri
plafon-kondisional, dan mempensiunkan entri lama ke `status=superseded`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_agunan import (
    PERTANYAAN_AGUNAN,
    PERTANYAAN_AGUNAN_DIATAS_AMBANG_PENGECUALIAN,
    PERTANYAAN_AGUNAN_DIATAS_AMBANG_TANPA_PENGECUALIAN,
    PERTANYAAN_AGUNAN_DIBAWAH_AMBANG,
    TOPIK,
    VERSI,
    seed,
)


def test_seed_menghasilkan_tiga_entri_baru_berstatus_aktif(session: Session):
    entri = seed(session)

    assert len(entri) == 3
    pertanyaan = {e.pertanyaan_kanonik for e in entri}
    assert pertanyaan == {
        PERTANYAAN_AGUNAN_DIBAWAH_AMBANG,
        PERTANYAAN_AGUNAN_DIATAS_AMBANG_PENGECUALIAN,
        PERTANYAAN_AGUNAN_DIATAS_AMBANG_TANPA_PENGECUALIAN,
    }
    for e in entri:
        assert e.topik == TOPIK
        assert e.status is StatusPanduan.aktif
        assert e.versi_regulasi == VERSI
        assert e.sumber_url and "Details" in e.sumber_url


def test_seed_entri_dibawah_ambang_isi_dan_pasal(session: Session):
    entri = {e.pertanyaan_kanonik: e for e in seed(session)}
    dibawah = entri[PERTANYAAN_AGUNAN_DIBAWAH_AMBANG]

    assert "Rp100 juta" in dibawah.isi
    assert "tidak dibayarkan" in dibawah.isi
    assert "Pasal 20 (1)" in dibawah.pasal_rujukan
    assert "Pasal 21" in dibawah.pasal_rujukan


def test_seed_entri_pengecualian_isi_dan_pasal(session: Session):
    entri = {e.pertanyaan_kanonik: e for e in seed(session)}
    pengecualian = entri[PERTANYAAN_AGUNAN_DIATAS_AMBANG_PENGECUALIAN]

    assert "petani tebu" in pengecualian.isi
    assert pengecualian.pasal_rujukan == "Pasal 20 (2)"
    assert "Pasal 21" not in pengecualian.pasal_rujukan


def test_seed_entri_tanpa_pengecualian_isi_dan_pasal(session: Session):
    entri = {e.pertanyaan_kanonik: e for e in seed(session)}
    tanpa_pengecualian = entri[PERTANYAAN_AGUNAN_DIATAS_AMBANG_TANPA_PENGECUALIAN]

    assert "tidak mengatur" in tanpa_pengecualian.isi
    assert "dapat mensyaratkan" not in tanpa_pengecualian.isi
    assert "Pasal 20 (1)" in tanpa_pengecualian.pasal_rujukan
    assert "Pasal 20 (2)" in tanpa_pengecualian.pasal_rujukan
    assert "Pasal 21" not in tanpa_pengecualian.pasal_rujukan


def test_seed_entri_overview_lama_menjadi_superseded(session: Session):
    """Entri overview lama (gaya E2) yang sudah ada di DB dipensiunkan, bukan
    dihapus — audit trail tetap ada."""
    lama = PanduanEntry(
        topik=TOPIK,
        pertanyaan_kanonik=PERTANYAAN_AGUNAN,
        isi="Isi overview lama plafon-agnostik.",
        sumber_url="https://peraturan.bpk.go.id/Details/342969/permenko-perekonomian-no-1-tahun-2026",
        tingkat_sumber=TingkatSumber.resmi_regulasi,
        versi_regulasi=VERSI,
        status=StatusPanduan.aktif,
        tanggal_akses=date(2026, 7, 28),
    )
    session.add(lama)
    session.flush()

    seed(session)

    session.refresh(lama)
    assert lama.status is StatusPanduan.superseded
    assert lama.digantikan_oleh is None


def test_seed_idempoten_tidak_menduplikasi(session: Session):
    seed(session)
    seed(session)

    semua = session.scalars(
        select(PanduanEntry).where(
            PanduanEntry.topik == TOPIK, PanduanEntry.versi_regulasi == VERSI
        )
    ).all()
    assert len(semua) == 3


def test_seed_menimpa_draft_lama_dengan_isi_terverifikasi(session: Session):
    lama = PanduanEntry(
        topik=TOPIK,
        pertanyaan_kanonik=PERTANYAAN_AGUNAN_DIBAWAH_AMBANG,
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

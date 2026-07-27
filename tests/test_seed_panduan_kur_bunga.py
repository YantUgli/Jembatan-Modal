"""Seed draft panduan bunga KUR (app/seeds/panduan_kur_bunga.py).

Bukan data demo per-tenant (panduan_entries global, bukan business_id) —
diuji seperti fitur lain: idempoten, dan status draft benar-benar tersimpan
(aturan #4: entri ini belum boleh menjawab pengguna sampai diverifikasi
manual, lihat docs/checklist-verifikasi-bunga-kur.md).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan
from app.seeds.panduan_kur_bunga import VERSI, seed


def test_seed_menghasilkan_empat_entri_berstatus_draft(session: Session):
    entri = seed(session)

    assert len(entri) == 4
    assert all(e.topik == "bunga" for e in entri)
    assert all(e.status is StatusPanduan.draft for e in entri)
    assert all(e.versi_regulasi == VERSI for e in entri)


def test_seed_idempoten_tidak_menduplikasi(session: Session):
    seed(session)
    seed(session)

    semua = session.scalars(select(PanduanEntry).where(PanduanEntry.versi_regulasi == VERSI)).all()
    assert len(semua) == 4

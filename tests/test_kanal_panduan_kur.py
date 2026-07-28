"""Asisten KUR (4c, slice pertama) — C1 (guard wired) + C2 (router/handler).

C1: tidak ada jalur jawaban KUR yang melewati guard aturan #4 — draft ditolak,
aktif diteruskan. C2: tiap kombinasi jenis KUR × sektor menjawab tarif yang
cocok Lampiran A rencana eksekusi, selalu dengan pasal_rujukan + sumber_url,
dan tak pernah menyimpulkan status ekspor sendiri.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.kanal.kontrak import KartuKlarifikasi, KartuPanduanKur
from app.kanal.orkestrator import kartu_panduan_kur
from app.models import Business, PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_agunan import seed as seed_agunan
from app.seeds.panduan_kur_bunga import seed as seed_bunga
from app.services.panduan_kur import KategoriKur, KonteksBunga, SektorUsaha

TGL = date(2026, 7, 28)


# ── C1: guard wired — draft ditolak, aktif diteruskan ───────────────────────


def test_kartu_panduan_kur_menolak_entri_draft(session: Session):
    """Entri yang cocok tapi masih draft (belum diverifikasi) → klarifikasi,
    bukan angka. Simulasi state sebelum A1: seed manual berstatus draft."""
    session.add(
        PanduanEntry(
            topik="bunga",
            pertanyaan_kanonik="Berapa bunga KUR Super Mikro?",
            isi="3% (draft, belum diverifikasi).",
            sumber_url="https://contoh.tidak-final/",
            tingkat_sumber=TingkatSumber.resmi_regulasi,
            status=StatusPanduan.draft,
            tanggal_akses=TGL,
        )
    )
    session.flush()

    hasil = kartu_panduan_kur(session, KonteksBunga(kategori=KategoriKur.super_mikro))

    assert isinstance(hasil.kartu[0], KartuKlarifikasi)


def test_kartu_panduan_kur_menjawab_entri_aktif(session: Session):
    """Data aktif nyata (seed pasca-D1) → kartu jawaban, bukan klarifikasi."""
    seed_bunga(session)

    hasil = kartu_panduan_kur(session, KonteksBunga(kategori=KategoriKur.super_mikro))

    assert isinstance(hasil.kartu[0], KartuPanduanKur)
    assert "3%" in hasil.kartu[0].isi
    assert hasil.kartu[0].sumber_url
    assert hasil.kartu[0].pasal_rujukan


def test_kartu_panduan_kur_konteks_kosong_selalu_klarifikasi(session: Session):
    """I6 — konteks kosong tak pernah jatuh ke `bunga-overview` sebagai jawaban
    tarif final, walau data sudah aktif."""
    seed_bunga(session)

    hasil = kartu_panduan_kur(session, KonteksBunga())

    assert isinstance(hasil.kartu[0], KartuKlarifikasi)
    assert "%" not in hasil.kartu[0].pertanyaan


# ── C2: cakupan tarif per Lampiran A ─────────────────────────────────────────


@pytest.mark.parametrize(
    "konteks,tarif_diharapkan",
    [
        (KonteksBunga(kategori=KategoriKur.super_mikro), "3%"),
        (KonteksBunga(kategori=KategoriKur.mikro, sektor=SektorUsaha.produksi), "6%"),
        (KonteksBunga(kategori=KategoriKur.kecil, sektor=SektorUsaha.produksi), "6%"),
        (
            KonteksBunga(
                kategori=KategoriKur.mikro,
                sektor=SektorUsaha.perdagangan,
                berorientasi_ekspor=False,
            ),
            "7%",  # jenjang 6%->7%, maks 2 akad
        ),
        (
            KonteksBunga(
                kategori=KategoriKur.kecil,
                sektor=SektorUsaha.perdagangan,
                berorientasi_ekspor=False,
            ),
            "9%",  # jenjang 6-7-8-9%
        ),
        (KonteksBunga(kategori=KategoriKur.khusus), "6%"),
        (KonteksBunga(kategori=KategoriKur.pmi), "6%"),
    ],
    ids=[
        "super_mikro",
        "mikro_produksi_ekspor",
        "kecil_produksi_ekspor",
        "mikro_nonekspor",
        "kecil_nonekspor",
        "khusus",
        "pmi",
    ],
)
def test_kartu_panduan_kur_tarif_cocok_lampiran_a(
    session: Session, konteks: KonteksBunga, tarif_diharapkan: str
):
    seed_bunga(session)

    hasil = kartu_panduan_kur(session, konteks)

    kartu = hasil.kartu[0]
    assert isinstance(kartu, KartuPanduanKur), konteks
    assert tarif_diharapkan in kartu.isi
    assert kartu.pasal_rujukan
    assert "Details" in kartu.sumber_url
    assert kartu.versi_regulasi == "Permenko 1/2026"


def test_kartu_panduan_kur_mikro_nonekspor_membatasi_dua_akad(session: Session):
    """Koreksi load-bearing: Mikro non-ekspor TIDAK boleh menyebut 8%/9% —
    itu khusus Kecil (Lampiran A.2)."""
    seed_bunga(session)

    hasil = kartu_panduan_kur(
        session,
        KonteksBunga(
            kategori=KategoriKur.mikro, sektor=SektorUsaha.perdagangan, berorientasi_ekspor=False
        ),
    )

    kartu = hasil.kartu[0]
    assert isinstance(kartu, KartuPanduanKur)
    assert "9%" not in kartu.isi
    assert "2 akad" in kartu.isi


def test_kartu_panduan_kur_ekspor_tidak_disimpulkan_kode(session: Session):
    """A.4 — sebelum `berorientasi_ekspor` diisi eksplisit, sektor perdagangan
    tidak pernah dijawab sebagai produksi/ekspor secara diam-diam."""
    seed_bunga(session)

    hasil = kartu_panduan_kur(
        session, KonteksBunga(kategori=KategoriKur.mikro, sektor=SektorUsaha.perdagangan)
    )

    assert isinstance(hasil.kartu[0], KartuKlarifikasi)


def test_kartu_panduan_kur_disclaimer_selalu_ada(session: Session):
    """Rule #5 semangatnya: panduan kredit membawa disclaimer, bukan janji lolos."""
    seed_bunga(session)

    hasil = kartu_panduan_kur(session, KonteksBunga(kategori=KategoriKur.super_mikro))

    kartu = hasil.kartu[0]
    assert isinstance(kartu, KartuPanduanKur)
    assert any("bukan jaminan" in c for c in kartu.catatan)


# ── Topik agunan (E2, 2026-07-28) — generik, tanpa cabang kategori/sektor ───


def test_kartu_panduan_kur_agunan_menjawab_entri_aktif(session: Session):
    seed_agunan(session)

    hasil = kartu_panduan_kur(session, topik="agunan")

    kartu = hasil.kartu[0]
    assert isinstance(kartu, KartuPanduanKur)
    assert "Rp100 juta" in kartu.isi
    assert kartu.pasal_rujukan and "Pasal 20" in kartu.pasal_rujukan
    assert kartu.sumber_url


def test_kartu_panduan_kur_agunan_belum_di_seed_ditolak_bukan_kosong(session: Session):
    """Belum ada entri agunan tersimpan → Penolakan/klarifikasi, bukan kartu
    jawaban kosong atau exception."""
    hasil = kartu_panduan_kur(session, topik="agunan")

    assert isinstance(hasil.kartu[0], KartuKlarifikasi)


def test_kartu_panduan_kur_agunan_disclaimer_selalu_ada(session: Session):
    seed_agunan(session)

    hasil = kartu_panduan_kur(session, topik="agunan")

    kartu = hasil.kartu[0]
    assert isinstance(kartu, KartuPanduanKur)
    assert any("bukan jaminan" in c for c in kartu.catatan)


# ── Lapisan HTTP (aksi terstruktur, bukan label router) ─────────────────────


def test_aksi_tanya_kur_mengembalikan_kartu(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from app.api import main as api

    seed_bunga(session)

    data = api.chat(
        api.PesanMasuk(aksi="tanya_kur", jenis_kur="super_mikro"),
        session=session,
        business=business,
        adapter=None,
    )

    assert data["kartu"][0]["tipe"] == "panduan_kur"
    assert "3%" in data["kartu"][0]["isi"]


def test_aksi_tanya_kur_jenis_asing_ditolak(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from fastapi import HTTPException

    from app.api import main as api

    with pytest.raises(HTTPException) as e:
        api.chat(
            api.PesanMasuk(aksi="tanya_kur", jenis_kur="menengah"),
            session=session,
            business=business,
            adapter=None,
        )
    assert e.value.status_code == 422


def test_aksi_tanya_kur_sektor_asing_ditolak(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from fastapi import HTTPException

    from app.api import main as api

    with pytest.raises(HTTPException) as e:
        api.chat(
            api.PesanMasuk(aksi="tanya_kur", jenis_kur="mikro", sektor_usaha="jasa"),
            session=session,
            business=business,
            adapter=None,
        )
    assert e.value.status_code == 422


def test_aksi_tanya_kur_tanpa_konteks_minta_klarifikasi(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from app.api import main as api

    seed_bunga(session)

    data = api.chat(
        api.PesanMasuk(aksi="tanya_kur"), session=session, business=business, adapter=None
    )

    assert data["kartu"][0]["tipe"] == "klarifikasi"


def test_aksi_tanya_kur_topik_agunan_mengembalikan_kartu(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from app.api import main as api

    seed_agunan(session)

    data = api.chat(
        api.PesanMasuk(aksi="tanya_kur", topik_kur="agunan"),
        session=session,
        business=business,
        adapter=None,
    )

    assert data["kartu"][0]["tipe"] == "panduan_kur"
    assert "Rp100 juta" in data["kartu"][0]["isi"]


def test_aksi_tanya_kur_topik_asing_ditolak(session: Session, business: Business):
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from fastapi import HTTPException

    from app.api import main as api

    with pytest.raises(HTTPException) as e:
        api.chat(
            api.PesanMasuk(aksi="tanya_kur", topik_kur="plafon"),
            session=session,
            business=business,
            adapter=None,
        )
    assert e.value.status_code == 422


def test_aksi_tanya_kur_default_topik_tetap_bunga(session: Session, business: Business):
    """Regresi: klien lama yang tak pernah mengirim `topik_kur` tetap dapat
    perilaku bunga seperti sebelum E2."""
    pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")
    from app.api import main as api

    seed_bunga(session)

    data = api.chat(
        api.PesanMasuk(aksi="tanya_kur", jenis_kur="super_mikro"),
        session=session,
        business=business,
        adapter=None,
    )

    assert data["kartu"][0]["tipe"] == "panduan_kur"
    assert "3%" in data["kartu"][0]["isi"]

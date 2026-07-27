"""Guard aturan #4 (`app/services/panduan_kur.py`) — kontrak `SPEC_GUARD_4C.md`.

Tiap test dipetakan ke invariant (I1..I7) / acceptance criteria (AC1..AC11)
di §6 spec tsb — nama test sengaja mengikuti tabel itu agar keterkaitannya
langsung terlihat tanpa perlu membuka dokumen.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_bunga import (
    PERTANYAAN_PERDAGANGAN_NONEKSPOR,
    PERTANYAAN_PRODUKSI_EKSPOR,
    PERTANYAAN_SUPER_MIKRO,
    seed as seed_bunga,
)
from app.services.panduan_kur import (
    JawabanTerkutip,
    KategoriKur,
    KonteksBunga,
    Penolakan,
    SektorUsaha,
    jawab_bunga_kur,
    jawab_panduan,
    pilih_jawaban,
)

TGL = date(2026, 7, 27)


def _entri(
    session: Session,
    *,
    topik: str = "izin_usaha",
    pertanyaan_kanonik: str | None = None,
    tingkat_sumber: TingkatSumber = TingkatSumber.resmi_regulasi,
    status: StatusPanduan = StatusPanduan.aktif,
    sumber_url: str = "https://peraturan.go.id/permenko-1-2026",
    isi: str = "Isi panduan resmi.",
) -> PanduanEntry:
    entri = PanduanEntry(
        topik=topik,
        pertanyaan_kanonik=pertanyaan_kanonik,
        isi=isi,
        sumber_url=sumber_url,
        tingkat_sumber=tingkat_sumber,
        status=status,
        tanggal_akses=TGL,
    )
    session.add(entri)
    session.flush()
    return entri


# ── Menolak dengan benar ─────────────────────────────────────────────────────


def test_guard_tolak_draft(session: Session):
    """I2/AC1 — entri cocok berstatus draft tidak pernah dijawab."""
    entri = _entri(session, status=StatusPanduan.draft)
    hasil = pilih_jawaban([entri])
    assert isinstance(hasil, Penolakan)


def test_guard_tolak_superseded(session: Session):
    """I3/AC2 — entri cocok berstatus superseded tidak pernah dijawab."""
    entri = _entri(session, status=StatusPanduan.superseded)
    hasil = pilih_jawaban([entri])
    assert isinstance(hasil, Penolakan)


def test_guard_tolak_sumber_lainnya(session: Session):
    """I4/AC3 — entri dengan tingkat_sumber=lainnya tidak pernah dijawab."""
    entri = _entri(session, tingkat_sumber=TingkatSumber.lainnya)
    hasil = pilih_jawaban([entri])
    assert isinstance(hasil, Penolakan)


def test_guard_tolak_tanpa_entri(session: Session):
    """I5/AC4 — tak ada entri cocok sama sekali → Penolakan, tanpa fallback."""
    hasil = pilih_jawaban([])
    assert isinstance(hasil, Penolakan)


def test_guard_pilih_layak_bukan_mirip(session: Session):
    """I5/AC5 — kandidat draft (sangat cocok) + aktif (kurang cocok):
    guard memilih yang layak-jawab, bukan yang paling mirip."""
    kurang_cocok_tapi_layak = _entri(
        session, status=StatusPanduan.aktif, isi="Jawaban resmi walau kurang spesifik."
    )
    sangat_cocok_tapi_draft = _entri(
        session, status=StatusPanduan.draft, isi="Jawaban sangat spesifik tapi belum diverifikasi."
    )

    hasil = pilih_jawaban([sangat_cocok_tapi_draft, kurang_cocok_tapi_layak])

    assert isinstance(hasil, JawabanTerkutip)
    assert hasil.panduan_entry_id == kurang_cocok_tapi_layak.id


def test_guard_pilih_layak_menolak_bila_tak_ada_yang_layak(session: Session):
    """I5/AC5 (cabang kedua) — yang paling cocok justru draft dan tak ada
    aktif yang relevan → Penolakan, bukan diturunkan ke yang draft."""
    hanya_draft = _entri(session, status=StatusPanduan.draft)
    hasil = pilih_jawaban([hanya_draft])
    assert isinstance(hasil, Penolakan)


# ── Menjawab dengan benar ────────────────────────────────────────────────────


def test_guard_jawab_entri_layak(session: Session):
    """AC6 — entri aktif + resmi_regulasi/resmi_bank + sumber_url sah yang
    cocok → JawabanTerkutip berisi isi + atribusi."""
    entri = _entri(session, isi="KUR Mikro sektor produksi: 6% efektif/tahun.")
    hasil = pilih_jawaban([entri])
    assert isinstance(hasil, JawabanTerkutip)
    assert hasil.isi == entri.isi


def test_guard_bunga_minta_sektor(session: Session):
    """I6/AC7 — pertanyaan bunga generik tanpa konteks sektor → permintaan
    klarifikasi, bukan angka tarif."""
    hasil = jawab_bunga_kur(session, KonteksBunga())
    assert isinstance(hasil, Penolakan)
    assert "%" not in hasil.alasan


def test_guard_bunga_perdagangan_nonekspor(session: Session):
    """AC8 — sektor perdagangan non-ekspor → jawaban berjenjang; tidak
    memuat frasa 'tetap' atau 'tanpa batas frekuensi' (khusus produksi/ekspor)."""
    _entri(
        session,
        topik="bunga",
        pertanyaan_kanonik=PERTANYAAN_PERDAGANGAN_NONEKSPOR,
        isi="Berjenjang: akad pertama 6%, kedua 7%, ketiga 8%, keempat 9%.",
    )
    konteks = KonteksBunga(
        kategori=KategoriKur.mikro_kecil,
        sektor=SektorUsaha.perdagangan,
        berorientasi_ekspor=False,
    )

    hasil = jawab_bunga_kur(session, konteks)

    assert isinstance(hasil, JawabanTerkutip)
    assert "6% tetap" not in hasil.isi
    assert "tanpa batas frekuensi" not in hasil.isi


def test_guard_bunga_produksi_ekspor(session: Session):
    """AC9 — sektor produksi/ekspor → jawaban 6% tetap."""
    _entri(
        session,
        topik="bunga",
        pertanyaan_kanonik=PERTANYAAN_PRODUKSI_EKSPOR,
        isi="Sektor produksi: 6% efektif per tahun secara tetap.",
    )
    konteks = KonteksBunga(kategori=KategoriKur.mikro_kecil, sektor=SektorUsaha.produksi)

    hasil = jawab_bunga_kur(session, konteks)

    assert isinstance(hasil, JawabanTerkutip)
    assert "tetap" in hasil.isi
    assert "6%" in hasil.isi


def test_guard_bunga_super_mikro_tak_butuh_sektor(session: Session):
    """Kategori Super Mikro tidak bercabang sektor — cukup kategori saja."""
    _entri(
        session,
        topik="bunga",
        pertanyaan_kanonik=PERTANYAAN_SUPER_MIKRO,
        isi="Super Mikro: 3% efektif per tahun.",
    )
    hasil = jawab_bunga_kur(session, KonteksBunga(kategori=KategoriKur.super_mikro))
    assert isinstance(hasil, JawabanTerkutip)


# ── Atribusi & audit ─────────────────────────────────────────────────────────


def test_guard_atribusi_ada(session: Session):
    """I7/AC10 — JawabanTerkutip membawa sumber_url + versi_regulasi yang
    bisa ditampilkan, dan mencatat id entri yang dipakai."""
    entri = _entri(session, sumber_url="https://peraturan.go.id/permenko-1-2026")
    entri.versi_regulasi = "Permenko 1/2026"
    session.flush()

    hasil = pilih_jawaban([entri])

    assert isinstance(hasil, JawabanTerkutip)
    assert hasil.sumber_url == "https://peraturan.go.id/permenko-1-2026"
    assert hasil.versi_regulasi == "Permenko 1/2026"
    assert hasil.panduan_entry_id == entri.id


# ── Penolakan bebas-kebocoran & tanpa jalur bypass ──────────────────────────


def test_guard_tolak_tidak_mengarang(session: Session):
    """AC11 — teks Penolakan tidak memuat angka/aturan tebakan."""
    hasil = pilih_jawaban([])
    assert isinstance(hasil, Penolakan)
    assert not any(ch.isdigit() for ch in hasil.alasan)


def test_guard_tanpa_jalur_bypass(session: Session):
    """I1 — fungsi jawab KUR selalu JawabanTerkutip | Penolakan, tak pernah
    string model mentah, di seluruh skenario kandidat yang mungkin."""
    aktif = _entri(session, status=StatusPanduan.aktif)
    draft = _entri(session, status=StatusPanduan.draft)
    lainnya = _entri(session, tingkat_sumber=TingkatSumber.lainnya)

    for kandidat in ([], [draft], [lainnya], [aktif], [draft, lainnya, aktif]):
        hasil = pilih_jawaban(kandidat)
        assert isinstance(hasil, JawabanTerkutip | Penolakan)


def test_guard_adversarial_paksa_tebak(session: Session):
    """I1/I5 — walau konteks bunga lengkap (user "memaksa" jawaban), guard
    tetap menolak selama satu-satunya entri yang cocok belum layak-jawab.

    Memakai state DB nyata: empat entri bunga dari `panduan_kur_bunga.seed`
    semuanya masih `status=draft` (belum diverifikasi manusia ke pasal resmi,
    lihat `docs/checklist-verifikasi-bunga-kur.md`) — skenario adversarial
    paling realistis yang ada di produk ini hari ini.
    """
    seed_bunga(session)
    konteks_lengkap = [
        KonteksBunga(kategori=KategoriKur.super_mikro),
        KonteksBunga(kategori=KategoriKur.mikro_kecil, sektor=SektorUsaha.produksi),
        KonteksBunga(
            kategori=KategoriKur.mikro_kecil,
            sektor=SektorUsaha.perdagangan,
            berorientasi_ekspor=False,
        ),
    ]
    for konteks in konteks_lengkap:
        hasil = jawab_bunga_kur(session, konteks)
        assert isinstance(hasil, Penolakan)


# ── jawab_panduan (guard generik lintas-topik) ──────────────────────────────


def test_jawab_panduan_generik_menjawab_dan_menolak(session: Session):
    layak = _entri(session, topik="nib", isi="Syarat NIB.")
    hasil = jawab_panduan(session, "nib")
    assert isinstance(hasil, JawabanTerkutip)
    assert hasil.panduan_entry_id == layak.id

    hasil_kosong = jawab_panduan(session, "topik_tak_ada")
    assert isinstance(hasil_kosong, Penolakan)


def test_jawab_panduan_filter_pertanyaan_kanonik(session: Session):
    """Kandidat difilter juga oleh topik lain yang sama pertanyaan_kanonik-nya
    tidak boleh ikut terpilih (isolasi antar-pertanyaan, bukan cuma antar-topik)."""
    _entri(session, topik="izin_usaha", pertanyaan_kanonik="Bagaimana cara urus NIB?")
    lain = _entri(session, topik="izin_usaha", pertanyaan_kanonik="Berapa biaya NIB?")

    hasil = jawab_panduan(session, "izin_usaha", pertanyaan_kanonik="Berapa biaya NIB?")

    assert isinstance(hasil, JawabanTerkutip)
    assert hasil.panduan_entry_id == lain.id


def test_semua_entri_bunga_tersimpan_sesuai_topik(session: Session):
    """Sanity check query select tetap benar meski tabel punya entri lintas topik."""
    seed_bunga(session)
    semua_bunga = session.scalars(select(PanduanEntry).where(PanduanEntry.topik == "bunga")).all()
    assert len(semua_bunga) == 4

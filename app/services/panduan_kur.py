"""Guard aturan #4 untuk asisten KUR (4c) — kontrak `SPEC_GUARD_4C.md`.

4c (`susun_dokumen_kur`, `panduan_perizinan`, wawancara multi-turn) belum
dibangun (`docs/04-rencana-kerja.md` Tahap 4c). Modul ini HANYA guard: titik
tunggal yang memutuskan apakah sebuah `panduan_entries` boleh dipakai
menjawab pengguna. Ia **tidak** memverifikasi kebenaran isi terhadap teks
Permenko — itu pekerjaan manusia lewat `docs/checklist-verifikasi-bunga-kur.md`
(status `draft` → `aktif`). Guard hanya menegakkan *kelayakan* entri
(status/sumber), bukan *kebenaran faktual*-nya.

Kelayakan (`SPEC_GUARD_4C.md` §1) — entri boleh dipakai menjawab hanya bila
SEMUA benar: `status == aktif`, `tingkat_sumber ∈ {resmi_regulasi,
resmi_bank}`, `sumber_url` terisi. Tak ada entri layak yang cocok → menolak;
guard **tidak pernah** menurunkan standar ke entri tak-layak yang paling
mirip (I5), dan `Penolakan.alasan` **selalu** string kode/template, tidak
pernah hasil generasi LLM (I1/§2) — mencegah kebocoran tebakan (AC11).

Bunga bercabang kategori × sektor × orientasi ekspor (§5): pertanyaan bunga
generik wajib ditolak dengan permintaan klarifikasi sebelum sektor diketahui
(I6) — mengutip `bunga-overview` sebagai jawaban final adalah bug, bukan
sekadar kurang tepat.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber
from app.seeds.panduan_kur_bunga import (
    PERTANYAAN_KECIL_NONEKSPOR,
    PERTANYAAN_KECIL_PRODUKSI_EKSPOR,
    PERTANYAAN_KHUSUS,
    PERTANYAAN_MIKRO_NONEKSPOR,
    PERTANYAAN_MIKRO_PRODUKSI_EKSPOR,
    PERTANYAAN_PMI,
    PERTANYAAN_SUPER_MIKRO,
)

__all__ = [
    "JawabanTerkutip",
    "KategoriKur",
    "KonteksBunga",
    "Penolakan",
    "SektorUsaha",
    "jawab_bunga_kur",
    "jawab_panduan",
    "pilih_jawaban",
]


@dataclass(frozen=True)
class JawabanTerkutip:
    """Jawaban yang boleh disampaikan ke pengguna — selalu berasal dari satu
    entri `panduan_entries` yang lolos filter kelayakan (§1), lengkap dengan
    atribusi (I7) untuk ditampilkan & dicatat (mis. `kur_outcomes`)."""

    isi: str
    sumber_url: str
    versi_regulasi: str | None
    pasal_rujukan: str | None
    panduan_entry_id: int


@dataclass(frozen=True)
class Penolakan:
    """Guard menolak menjawab. `alasan` selalu string kode (template) — lihat
    docstring modul. Tidak mengarang angka/aturan (AC11)."""

    alasan: str


# ── Teks penolakan — kode, bukan LLM (§2) ───────────────────────────────────

_BELUM_ADA_PANDUAN = (
    "Untuk pertanyaan ini kami belum punya panduan resmi yang terverifikasi. "
    "Silakan cek langsung ke sumber resmi (mis. kur.ekon.go.id) atau tanyakan "
    "ke petugas bank penyalur."
)

_KLARIFIKASI_BUNGA = (
    "Bunga KUR berbeda menurut kategori dan sektor usaha. Supaya jawabannya "
    "tepat: usahanya kategori Super Mikro (plafon sampai Rp10 juta) atau "
    "Mikro/Kecil? Kalau Mikro/Kecil, usahanya produksi atau perdagangan? "
    "Kalau perdagangan, berorientasi ekspor atau tidak?"
)


def _layak_jawab(entri: PanduanEntry) -> bool:
    """Kelayakan (§1) — bukan penilaian kebenaran isi, hanya status & sumber."""
    return (
        entri.status is StatusPanduan.aktif
        and entri.tingkat_sumber in (TingkatSumber.resmi_regulasi, TingkatSumber.resmi_bank)
        and bool(entri.sumber_url and entri.sumber_url.strip())
    )


def pilih_jawaban(
    kandidat: list[PanduanEntry], alasan_kosong: str = _BELUM_ADA_PANDUAN
) -> JawabanTerkutip | Penolakan:
    """Satu-satunya jalan ke `JawabanTerkutip` (I1) — saring kelayakan, lalu pilih.

    `kandidat` boleh datang dalam urutan relevansi apa pun dari pemanggil:
    guard menyaring yang tak-layak lebih dulu, baru memilih dari sisanya
    (I5/AC5) — tidak pernah "yang paling mirip" bila ia tak layak.
    """
    layak = [e for e in kandidat if _layak_jawab(e)]
    if not layak:
        return Penolakan(alasan_kosong)

    entri = layak[0]
    return JawabanTerkutip(
        isi=entri.isi,
        sumber_url=entri.sumber_url,
        versi_regulasi=entri.versi_regulasi,
        pasal_rujukan=entri.pasal_rujukan,
        panduan_entry_id=entri.id,
    )


def jawab_panduan(
    session: Session, topik: str, pertanyaan_kanonik: str | None = None
) -> JawabanTerkutip | Penolakan:
    """Guard generik lintas-topik (non-bunga): cari kandidat lalu `pilih_jawaban`."""
    stmt = select(PanduanEntry).where(PanduanEntry.topik == topik)
    if pertanyaan_kanonik is not None:
        stmt = stmt.where(PanduanEntry.pertanyaan_kanonik == pertanyaan_kanonik)
    kandidat = list(session.scalars(stmt).all())
    return pilih_jawaban(kandidat)


# ── Bunga: kategori × sektor × orientasi ekspor (§5) ────────────────────────


class KategoriKur(str, enum.Enum):
    """Jenis KUR — **Mikro dan Kecil dipisah**, bukan digabung.

    Koreksi load-bearing (Lampiran A.2 rencana eksekusi, 2026-07-28): jenjang
    non-ekspor Mikro (6→7%, maks 2 akad) berbeda dari Kecil (6→7→8→9%,
    akumulasi maks Rp500jt) — menyeragamkan keduanya di satu nilai enum
    `mikro_kecil` adalah kesalahan yang guard ini dirancang untuk menangkap.
    """

    super_mikro = "super_mikro"
    mikro = "mikro"
    kecil = "kecil"
    khusus = "khusus"
    pmi = "pmi"


class SektorUsaha(str, enum.Enum):
    produksi = "produksi"
    perdagangan = "perdagangan"


@dataclass(frozen=True)
class KonteksBunga:
    """Slot yang harus terisi sebelum bunga spesifik boleh dikutip (I6).

    `None` pada sebuah field = belum diketahui, bukan asumsi netral apa pun —
    guard meminta klarifikasi, tidak menebak nilai default. `sektor` dan
    `berorientasi_ekspor` hanya relevan untuk kategori `mikro`/`kecil` —
    `super_mikro`/`khusus`/`pmi` tidak bercabang sektor sama sekali.
    """

    kategori: KategoriKur | None = None
    sektor: SektorUsaha | None = None
    berorientasi_ekspor: bool | None = None


_PRODUKSI_EKSPOR = {
    KategoriKur.mikro: PERTANYAAN_MIKRO_PRODUKSI_EKSPOR,
    KategoriKur.kecil: PERTANYAAN_KECIL_PRODUKSI_EKSPOR,
}
_NONEKSPOR = {
    KategoriKur.mikro: PERTANYAAN_MIKRO_NONEKSPOR,
    KategoriKur.kecil: PERTANYAAN_KECIL_NONEKSPOR,
}


def _pertanyaan_bunga(konteks: KonteksBunga) -> str | None:
    """Petakan konteks ke `pertanyaan_kanonik` entri spesifik-segmen, atau
    `None` bila slot penentu belum terisi (guard lalu meminta klarifikasi).

    Produksi dan perdagangan-berorientasi-ekspor berbagi entri yang sama
    per kategori (flat 6% tetap); hanya perdagangan non-ekspor yang memakai
    skema berjenjang, dan jenjangnya **beda antara Mikro dan Kecil**
    (`docs/checklist-verifikasi-bunga-kur.md`). `khusus`/`pmi` flat tanpa
    sektor sama sekali — ekspor bukan atribut yang boleh diasumsikan (A.4).
    """
    if konteks.kategori is None:
        return None
    if konteks.kategori is KategoriKur.super_mikro:
        return PERTANYAAN_SUPER_MIKRO
    if konteks.kategori is KategoriKur.khusus:
        return PERTANYAAN_KHUSUS
    if konteks.kategori is KategoriKur.pmi:
        return PERTANYAAN_PMI

    # Sisanya: mikro/kecil — bercabang sektor & (bila perdagangan) ekspor.
    if konteks.sektor is None:
        return None
    if konteks.sektor is SektorUsaha.produksi:
        return _PRODUKSI_EKSPOR[konteks.kategori]

    if konteks.berorientasi_ekspor is None:
        return None
    return (
        _PRODUKSI_EKSPOR[konteks.kategori]
        if konteks.berorientasi_ekspor
        else _NONEKSPOR[konteks.kategori]
    )


def jawab_bunga_kur(session: Session, konteks: KonteksBunga) -> JawabanTerkutip | Penolakan:
    """Guard topik bunga — menolak dengan klarifikasi sebelum sektor diketahui (I6/AC7)."""
    pertanyaan = _pertanyaan_bunga(konteks)
    if pertanyaan is None:
        return Penolakan(_KLARIFIKASI_BUNGA)

    kandidat = list(
        session.scalars(
            select(PanduanEntry).where(
                PanduanEntry.topik == "bunga",
                PanduanEntry.pertanyaan_kanonik == pertanyaan,
            )
        ).all()
    )
    return pilih_jawaban(kandidat)

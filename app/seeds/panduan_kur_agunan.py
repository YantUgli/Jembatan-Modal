"""Seed `panduan_entries` — larangan agunan tambahan KUR (Permenko 1/2026).

**Terverifikasi (Lampiran A.3, `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`)**: dicocokkan
ke teks resmi `docs/regulasi/2026PemenkoEkon001.pdf`. Tiga entri di sini masuk
langsung sebagai `status=aktif` — lihat `docs/keputusan.md` 2026-07-28 ("Topik
agunan KUR: entri kedua yang seed langsung aktif — pengecualian, bukan
preseden") untuk kenapa ini boleh melewati gerbang `draft` tanpa membuka gerbang
itu untuk topik KUR berikutnya secara umum.

**F2 (plafon-kondisional)**: entri overview plafon-agnostik lama
(`PERTANYAAN_AGUNAN`) dipensiunkan ke `status=superseded` oleh `seed()` di
bawah, digantikan tiga entri baru yang masing-masing hanya mengutip pasal
relevan ke skenario plafon spesifiknya (aturan #4) — lihat entri
`docs/keputusan.md` untuk F2. `digantikan_oleh` sengaja dibiarkan `None`:
satu entri lama dipecah jadi tiga entri baru, tak ada satu FK target tunggal
yang valid tanpa memalsukan jejak audit.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber

TOPIK = "agunan"
VERSI = "Permenko 1/2026"
TANGGAL_BERLAKU = date(2026, 1, 13)
TANGGAL_TINJAU = date(2027, 1, 1)
TANGGAL_AKSES = date(2026, 7, 28)
SUMBER_URL = "https://peraturan.bpk.go.id/Details/342969/permenko-perekonomian-no-1-tahun-2026"

# Entri overview lama (E2, plafon-agnostik) — dipensiunkan oleh seed() di
# bawah, dibiarkan di DB berstatus superseded untuk audit historis.
PERTANYAAN_AGUNAN = "Apakah KUR butuh agunan tambahan?"

PERTANYAAN_AGUNAN_DIBAWAH_AMBANG = (
    "Apakah KUR dengan plafon sampai Rp100 juta butuh agunan tambahan?"
)
PERTANYAAN_AGUNAN_DIATAS_AMBANG_PENGECUALIAN = (
    "Apakah KUR di atas Rp100 juta untuk petani tebu rakyat/KUR khusus "
    "pertanian butuh agunan tambahan?"
)
PERTANYAAN_AGUNAN_DIATAS_AMBANG_TANPA_PENGECUALIAN = (
    "Apakah KUR di atas Rp100 juta di luar petani tebu rakyat/KUR khusus "
    "pertanian butuh agunan tambahan?"
)

_ENTRI = [
    dict(
        pertanyaan_kanonik=PERTANYAAN_AGUNAN_DIBAWAH_AMBANG,
        isi=(
            "Untuk KUR dengan plafon sampai dengan Rp100 juta, penyalur TIDAK "
            "BOLEH mensyaratkan agunan tambahan di luar objek yang dibiayai. "
            "Bila penyalur melanggar larangan ini, subsidi bunga/marjin untuk "
            "pinjaman tersebut tidak dibayarkan pemerintah — dan bila "
            "subsidinya sudah terlanjur diterima, wajib dikembalikan ke kas "
            "negara."
        ),
        pasal_rujukan="Pasal 20 (1); Pasal 21 (1); Pasal 21 (2)",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_AGUNAN_DIATAS_AMBANG_PENGECUALIAN,
        isi=(
            "Untuk KUR di atas Rp100 juta, penyalur tetap TIDAK BOLEH "
            "mensyaratkan agunan tambahan bila usahanya petani tebu rakyat "
            "atau KUR khusus pertanian dengan offtaker avalis — ini "
            "pengecualian yang memperluas larangan agunan di atas ambang "
            "Rp100 juta."
        ),
        pasal_rujukan="Pasal 20 (2)",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_AGUNAN_DIATAS_AMBANG_TANPA_PENGECUALIAN,
        isi=(
            "Larangan mensyaratkan agunan tambahan hanya berlaku untuk KUR "
            "dengan plafon sampai dengan Rp100 juta, atau di atas itu khusus "
            "untuk petani tebu rakyat/KUR khusus pertanian dengan offtaker "
            "avalis. Di luar dua kondisi itu, Permenko ini tidak mengatur "
            "soal agunan — sebaiknya ditanyakan langsung ke bank/lembaga "
            "penyalur."
        ),
        pasal_rujukan="Pasal 20 (1); Pasal 20 (2)",
    ),
]


def seed(session: Session) -> list[PanduanEntry]:
    """Isi/perbarui tiga entri panduan agunan KUR plafon-kondisional (F2).

    Upsert per `pertanyaan_kanonik`, pola sama dengan `panduan_kur_bunga.seed()`.
    Entri overview lama (`PERTANYAAN_AGUNAN`) dipensiunkan ke `superseded` bila
    ada — tidak dihapus (audit).
    """
    existing = {
        e.pertanyaan_kanonik: e
        for e in session.scalars(
            select(PanduanEntry).where(
                PanduanEntry.topik == TOPIK, PanduanEntry.versi_regulasi == VERSI
            )
        ).all()
    }

    hasil: list[PanduanEntry] = []
    for e in _ENTRI:
        entri = existing.get(e["pertanyaan_kanonik"])
        if entri is None:
            entri = PanduanEntry(topik=TOPIK, versi_regulasi=VERSI)
            session.add(entri)
        entri.pertanyaan_kanonik = e["pertanyaan_kanonik"]
        entri.isi = e["isi"]
        entri.sumber_url = SUMBER_URL
        entri.tingkat_sumber = TingkatSumber.resmi_regulasi
        entri.pasal_rujukan = e["pasal_rujukan"]
        entri.tanggal_akses = TANGGAL_AKSES
        entri.tanggal_berlaku = TANGGAL_BERLAKU
        entri.tanggal_tinjau = TANGGAL_TINJAU
        entri.status = StatusPanduan.aktif
        hasil.append(entri)

    overview_lama = existing.get(PERTANYAAN_AGUNAN)
    if overview_lama is not None:
        overview_lama.status = StatusPanduan.superseded

    session.flush()
    return hasil


def main() -> None:
    from app.db import session_scope

    with session_scope() as session:
        entri = seed(session)
        print(f"Seed selesai: {len(entri)} entri panduan agunan KUR (status=aktif).")


if __name__ == "__main__":
    main()

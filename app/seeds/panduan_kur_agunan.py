"""Seed `panduan_entries` — larangan agunan tambahan KUR (Permenko 1/2026).

**Terverifikasi (Lampiran A.3, `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`)**: dicocokkan
ke teks resmi `docs/regulasi/2026PemenkoEkon001.pdf`. Satu entri overview di sini
masuk langsung sebagai `status=aktif` — lihat `docs/keputusan.md` 2026-07-28
("Topik agunan KUR: entri kedua yang seed langsung aktif — pengecualian, bukan
preseden") untuk kenapa ini boleh melewati gerbang `draft` tanpa membuka gerbang
itu untuk topik KUR berikutnya secara umum.

⚠️ **Sengaja belum plafon-kondisional.** Entri ini menjawab aturan agunan secara
umum (ambang Rp100 juta + pengecualian petani tebu/KUR khusus pertanian +
sanksi), bukan pertanyaan bernominal ("saya mau pinjam 200 juta, butuh agunan
tidak?"). Menjawab pertanyaan bernominal butuh guard baca `plafon` dari input
pengguna dan membandingkan ke ambang — belum dibangun di slice ini. Lihat
`docs/keputusan.md` 2026-07-28 untuk follow-up bernama.
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

PERTANYAAN_AGUNAN = "Apakah KUR butuh agunan tambahan?"

_ISI = (
    "Untuk KUR dengan plafon sampai dengan Rp100 juta, penyalur TIDAK BOLEH "
    "mensyaratkan agunan tambahan di luar objek yang dibiayai. Pengecualian "
    "hanya berlaku untuk petani tebu rakyat dan KUR khusus pertanian dengan "
    "offtaker avalis untuk plafon di atas Rp100 juta. Bila penyalur melanggar "
    "larangan ini, subsidi bunga/marjin untuk pinjaman tersebut tidak "
    "dibayarkan pemerintah — dan bila subsidinya sudah terlanjur diterima, "
    "wajib dikembalikan ke kas negara."
)

_PASAL_RUJUKAN = "Pasal 20 (1); Pasal 20 (2); Pasal 21 (1); Pasal 21 (2)"


def seed(session: Session) -> PanduanEntry:
    """Isi/perbarui entri panduan agunan KUR. Kembalikan entri (baru atau ter-upgrade).

    Upsert per `pertanyaan_kanonik`, pola sama dengan `panduan_kur_bunga.seed()`.
    """
    entri = session.scalars(
        select(PanduanEntry).where(
            PanduanEntry.topik == TOPIK,
            PanduanEntry.pertanyaan_kanonik == PERTANYAAN_AGUNAN,
            PanduanEntry.versi_regulasi == VERSI,
        )
    ).first()
    if entri is None:
        entri = PanduanEntry(topik=TOPIK, versi_regulasi=VERSI)
        session.add(entri)

    entri.pertanyaan_kanonik = PERTANYAAN_AGUNAN
    entri.isi = _ISI
    entri.sumber_url = SUMBER_URL
    entri.tingkat_sumber = TingkatSumber.resmi_regulasi
    entri.pasal_rujukan = _PASAL_RUJUKAN
    entri.tanggal_akses = TANGGAL_AKSES
    entri.tanggal_berlaku = TANGGAL_BERLAKU
    entri.tanggal_tinjau = TANGGAL_TINJAU
    entri.status = StatusPanduan.aktif

    session.flush()
    return entri


def main() -> None:
    from app.db import session_scope

    with session_scope() as session:
        entri = seed(session)
        print(f"Seed selesai: entri panduan agunan KUR (id={entri.id}, status=aktif).")


if __name__ == "__main__":
    main()

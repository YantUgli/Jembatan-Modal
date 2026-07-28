"""Seed `panduan_entries` — bunga/marjin KUR per jenis KUR × sektor (Permenko 1/2026).

**Terverifikasi (A1, 2026-07-28)**: diambil langsung dari teks resmi
`docs/regulasi/2026PemenkoEkon001.pdf`, dicocokkan ke Lampiran A rencana
eksekusi. Delapan entri di sini masuk sebagai `status=aktif` — lihat
`docs/checklist-verifikasi-bunga-kur.md` untuk riwayat verifikasi.

Kenapa 8 entri, bukan 4: bunga KUR bercabang menurut jenis KUR × sektor ×
orientasi ekspor × urutan akad — dan **Mikro dan Kecil dipecah terpisah**
(koreksi load-bearing): jenjang perdagangan non-ekspor Mikro (6%→7%, maks 2
akad, Pasal 36 (3) b + Pasal 37 (1) b) BEDA dari Kecil (6%→7%→8%→9%,
akumulasi maks Rp500jt, Pasal 43 (3) b + Pasal 44 (1) b) — menyeragamkan
keduanya adalah kesalahan yang guard (`app/services/panduan_kur.py`) dirancang
untuk menangkap. Khusus dan Penempatan PMI ditambahkan sebagai kategori flat
tersendiri (Pasal 51 (1), Pasal 58 (1)).

Idempoten lewat upsert: entri dicocokkan per (`topik`, `pertanyaan_kanonik`,
`versi_regulasi`) — bila sudah ada, kontennya **ditimpa** dengan versi
terverifikasi ini (bukan cuma dilewati), supaya database yang sudah kadung
menyimpan draft riset-sekunder lama ikut ter-upgrade saat seed dijalankan ulang.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber

VERSI = "Permenko 1/2026"
TANGGAL_BERLAKU = date(2026, 1, 13)
TANGGAL_TINJAU = date(2027, 1, 1)
TANGGAL_AKSES = date(2026, 7, 28)
SUMBER_URL = (
    "https://peraturan.bpk.go.id/Details/342969/permenko-perekonomian-no-1-tahun-2026"
)

# Kunci pencocokan dipakai `app/services/panduan_kur.py` (guard aturan #4) untuk
# memilih entri spesifik-segmen — diekspor di sini supaya satu-satunya sumber
# kebenaran teksnya adalah seed ini, bukan disalin ulang di guard.
PERTANYAAN_OVERVIEW = "Berapa bunga KUR saya sekarang?"
PERTANYAAN_SUPER_MIKRO = "Berapa bunga KUR Super Mikro?"
PERTANYAAN_MIKRO_PRODUKSI_EKSPOR = (
    "Berapa bunga KUR Mikro untuk usaha produksi atau perdagangan ekspor?"
)
PERTANYAAN_MIKRO_NONEKSPOR = "Berapa bunga KUR Mikro untuk usaha perdagangan yang bukan ekspor?"
PERTANYAAN_KECIL_PRODUKSI_EKSPOR = (
    "Berapa bunga KUR Kecil untuk usaha produksi atau perdagangan ekspor?"
)
PERTANYAAN_KECIL_NONEKSPOR = "Berapa bunga KUR Kecil untuk usaha perdagangan yang bukan ekspor?"
PERTANYAAN_KHUSUS = "Berapa bunga KUR Khusus?"
PERTANYAAN_PMI = "Berapa bunga KUR Penempatan PMI?"

_ENTRI = [
    dict(
        pertanyaan_kanonik=PERTANYAAN_OVERVIEW,
        isi=(
            "Bunga/marjin KUR berbeda menurut jenis KUR dan sektor usaha. Super "
            "Mikro (plafon sampai Rp10 juta): 3% efektif per tahun, sektor apa "
            "pun. KUR Mikro (plafon >Rp10 juta s.d. Rp100 juta): 6% untuk sektor "
            "produksi atau perdagangan berorientasi ekspor (tanpa batas frekuensi "
            "maupun akumulasi akad), atau berjenjang 6%→7% untuk perdagangan "
            "non-ekspor (maksimal 2 akad). KUR Kecil (plafon >Rp100 juta s.d. "
            "Rp500 juta): 6% untuk produksi/ekspor (tanpa batas), atau berjenjang "
            "6%→7%→8%→9% untuk perdagangan non-ekspor (akumulasi maksimal "
            "Rp500 juta, termasuk akumulasi dari KUR Mikro sebelumnya). KUR "
            "Khusus dan KUR Penempatan PMI: 6% flat. Untuk menjawab tepat, perlu "
            "diketahui: jenis KUR (super mikro/mikro/kecil/khusus/PMI), sektor "
            "usaha (produksi atau perdagangan), status ekspor (dibuktikan "
            "dokumen dari kementerian/instansi terkait), dan ini pengajuan akad "
            "ke berapa."
        ),
        pasal_rujukan=None,
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_SUPER_MIKRO,
        isi=(
            "KUR Super Mikro (plafon sampai Rp10 juta) dikenakan bunga 3% "
            "efektif per tahun, tanpa membedakan sektor usaha, tanpa batas "
            "frekuensi maupun akumulasi akad."
        ),
        pasal_rujukan="Pasal 30; Pasal 29 (3)",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_MIKRO_PRODUKSI_EKSPOR,
        isi=(
            "KUR Mikro (plafon >Rp10 juta s.d. Rp100 juta) untuk sektor "
            "produksi, atau perdagangan yang berorientasi ekspor (dibuktikan "
            "dokumen proses ekspor dari kementerian/instansi terkait), "
            "dikenakan bunga 6% efektif per tahun secara tetap — tanpa batas "
            "frekuensi maupun akumulasi akad."
        ),
        pasal_rujukan="Pasal 37 (1) a; Pasal 36 (3) a",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_MIKRO_NONEKSPOR,
        isi=(
            "KUR Mikro (plafon >Rp10 juta s.d. Rp100 juta) untuk sektor "
            "perdagangan yang TIDAK berorientasi ekspor dikenakan bunga "
            "berjenjang menurut urutan akad: akad pertama 6%, akad kedua 7% "
            "efektif per tahun — dibatasi maksimal 2 akad."
        ),
        pasal_rujukan="Pasal 37 (1) b; Pasal 36 (3) b",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_KECIL_PRODUKSI_EKSPOR,
        isi=(
            "KUR Kecil (plafon >Rp100 juta s.d. Rp500 juta) untuk sektor "
            "produksi, atau perdagangan yang berorientasi ekspor (dibuktikan "
            "dokumen proses ekspor dari kementerian/instansi terkait), "
            "dikenakan bunga 6% efektif per tahun secara tetap — tanpa batas "
            "frekuensi maupun akumulasi akad."
        ),
        pasal_rujukan="Pasal 44 (1) a; Pasal 43 (3) a",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_KECIL_NONEKSPOR,
        isi=(
            "KUR Kecil (plafon >Rp100 juta s.d. Rp500 juta) untuk sektor "
            "perdagangan yang TIDAK berorientasi ekspor dikenakan bunga "
            "berjenjang menurut urutan akad: akad pertama 6%, kedua 7%, "
            "ketiga 8%, keempat 9% efektif per tahun — akumulasi plafon "
            "dibatasi maksimal Rp500 juta, termasuk akumulasi dari KUR Mikro "
            "sebelumnya."
        ),
        pasal_rujukan="Pasal 44 (1) b; Pasal 43 (3) b",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_KHUSUS,
        isi=(
            "KUR Khusus (plafon sampai Rp500 juta) dikenakan bunga 6% "
            "efektif per tahun secara flat."
        ),
        pasal_rujukan="Pasal 51 (1); Pasal 50 (1)",
    ),
    dict(
        pertanyaan_kanonik=PERTANYAAN_PMI,
        isi=(
            "KUR Penempatan Pekerja Migran Indonesia (plafon sampai Rp100 "
            "juta) dikenakan bunga 6% efektif per tahun secara flat."
        ),
        pasal_rujukan="Pasal 58 (1); Pasal 57 (1)",
    ),
]


def seed(session: Session) -> list[PanduanEntry]:
    """Isi/perbarui entri panduan bunga KUR. Kembalikan entri (baru atau ter-upgrade).

    Upsert per `pertanyaan_kanonik` (bukan cuma "sudah ada versi ini? lewati"):
    database yang sudah kadung menyimpan draft riset-sekunder lama ikut
    ter-timpa dengan isi terverifikasi begitu seed ini dijalankan ulang.
    """
    existing = {
        e.pertanyaan_kanonik: e
        for e in session.scalars(
            select(PanduanEntry).where(
                PanduanEntry.topik == "bunga", PanduanEntry.versi_regulasi == VERSI
            )
        ).all()
    }

    hasil: list[PanduanEntry] = []
    for e in _ENTRI:
        entri = existing.get(e["pertanyaan_kanonik"])
        if entri is None:
            entri = PanduanEntry(topik="bunga", versi_regulasi=VERSI)
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

    session.flush()
    return hasil


def main() -> None:
    from app.db import session_scope

    with session_scope() as session:
        entri = seed(session)
        print(f"Seed selesai: {len(entri)} entri panduan bunga KUR (status=aktif).")


if __name__ == "__main__":
    main()

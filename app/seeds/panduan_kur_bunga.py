"""Seed draft `panduan_entries` — bunga KUR per sektor (Permenko 1/2026).

BELUM TERVERIFIKASI ke pasal resmi. Empat entri di sini masuk sebagai
`status=draft` (aturan #4: guard nanti wajib menolak entri draft persis
seperti `tingkat_sumber=lainnya`) — hasil riset sekunder + satu halaman resmi
Kemenko Perekonomian, bukan bacaan pasal-per-pasal. Lihat
`docs/checklist-verifikasi-bunga-kur.md` untuk syarat promosi ke `aktif`.

Kenapa 4 entri, bukan 1: bunga KUR bercabang menurut kategori × sektor ×
orientasi ekspor × urutan akad — satu entri "flat 6%" generik pernah nyaris
ter-seed dan salah (klaim tanpa-batas-frekuensi ikut kebawa ke segmen yang
tidak berhak). Router (saat 4c dibangun) sebaiknya menanyakan sektor/ekspor
dulu, baru mengutip entri spesifik — bukan langsung mengutip overview.

Idempoten: kalau entri versi_regulasi ini sudah ada, tidak menyeed ulang.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PanduanEntry, StatusPanduan, TingkatSumber

VERSI = "Permenko 1/2026"
TANGGAL_BERLAKU = date(2026, 1, 13)
TANGGAL_TINJAU = date(2027, 1, 1)
TANGGAL_AKSES = date(2026, 7, 27)
SUMBER_URL_PLACEHOLDER = (
    "https://peraturan.bpk.go.id/... (Permenko 1/2026 — isi URL final setelah verifikasi)"
)

# Kunci pencocokan dipakai `app/services/panduan_kur.py` (guard aturan #4) untuk
# memilih entri spesifik-segmen — diekspor di sini supaya satu-satunya sumber
# kebenaran teksnya adalah seed ini, bukan disalin ulang di guard.
PERTANYAAN_OVERVIEW = "Berapa bunga KUR saya sekarang?"
PERTANYAAN_SUPER_MIKRO = "Berapa bunga KUR Super Mikro?"
PERTANYAAN_PRODUKSI_EKSPOR = "Berapa bunga KUR untuk usaha produksi atau perdagangan ekspor?"
PERTANYAAN_PERDAGANGAN_NONEKSPOR = "Berapa bunga KUR untuk usaha perdagangan yang bukan ekspor?"

_ENTRI = [
    dict(
        pertanyaan_kanonik=PERTANYAAN_OVERVIEW,
        isi=(
            "Bunga KUR bergantung pada kategori dan sektor usaha. Super Mikro "
            "(plafon sampai Rp10 juta): 3% efektif per tahun. KUR Mikro/Kecil "
            "untuk sektor produksi atau perdagangan berorientasi ekspor: 6% "
            "efektif per tahun secara tetap. KUR Mikro/Kecil untuk perdagangan "
            "yang tidak berorientasi ekspor: berjenjang menurut urutan akad "
            "(6%, 7%, 8%, 9%). Untuk menjawab tepat, perlu diketahui: jenis "
            "usaha (produksi atau perdagangan), berorientasi ekspor atau "
            "tidak, besar plafon, dan ini pengajuan ke berapa."
        ),
        pasal_rujukan=None,
    ),
    dict(
        pertanyaan_kanonik="Berapa bunga KUR Super Mikro?",
        isi=(
            "KUR Super Mikro (plafon sampai Rp10 juta) dikenakan bunga 3% "
            "efektif per tahun. 'Efektif' berarti bunga dihitung dari sisa "
            "pokok pinjaman, sehingga bebannya menurun seiring cicilan "
            "berjalan."
        ),
        pasal_rujukan="(pasal tarif Super Mikro — KONFIRMASI ke teks resmi)",
    ),
    dict(
        pertanyaan_kanonik="Berapa bunga KUR untuk usaha produksi atau perdagangan ekspor?",
        isi=(
            "Untuk KUR Mikro dan KUR Kecil di sektor produksi (misalnya "
            "pertanian, perikanan, industri pengolahan, jasa) serta "
            "perdagangan yang berorientasi ekspor, bunga ditetapkan 6% "
            "efektif per tahun secara tetap, berapa pun urutan atau jumlah "
            "pengajuan. Segmen ini juga tidak dibatasi frekuensi maupun "
            "akumulasi penarikan KUR, selama kapasitas pembayaran dan "
            "kualitas kredit (SLIK OJK) tetap terjaga."
        ),
        pasal_rujukan=(
            "(kandidat: Pasal 37 KUR Mikro, Pasal 44 KUR Kecil — nomor "
            "BERBEDA antar sumber, KONFIRMASI ke teks resmi)"
        ),
    ),
    dict(
        pertanyaan_kanonik="Berapa bunga KUR untuk usaha perdagangan yang bukan ekspor?",
        isi=(
            "Untuk KUR Mikro dan KUR Kecil di sektor perdagangan yang TIDAK "
            "berorientasi ekspor, berlaku skema bunga berjenjang mengikuti "
            "urutan akad: akad pertama 6%, akad kedua 7%, akad ketiga 8%, "
            "dan akad keempat 9% efektif per tahun. Tarif 9% pada akad "
            "keempat berlaku khusus untuk KUR Kecil. Untuk segmen ini, "
            "skema berjenjang tidak dihapus."
        ),
        pasal_rujukan="(pasal skema berjenjang perdagangan non-ekspor — KONFIRMASI ke teks resmi)",
    ),
]


def seed(session: Session) -> list[PanduanEntry]:
    """Isi draft panduan bunga KUR. Kembalikan entri (baru atau yang sudah ada)."""
    existing = session.scalars(
        select(PanduanEntry).where(
            PanduanEntry.topik == "bunga", PanduanEntry.versi_regulasi == VERSI
        )
    ).all()
    if existing:
        return list(existing)

    entri = [
        PanduanEntry(
            topik="bunga",
            pertanyaan_kanonik=e["pertanyaan_kanonik"],
            isi=e["isi"],
            sumber_url=SUMBER_URL_PLACEHOLDER,
            tingkat_sumber=TingkatSumber.resmi_regulasi,
            versi_regulasi=VERSI,
            pasal_rujukan=e["pasal_rujukan"],
            tanggal_akses=TANGGAL_AKSES,
            tanggal_berlaku=TANGGAL_BERLAKU,
            tanggal_tinjau=TANGGAL_TINJAU,
            status=StatusPanduan.draft,
        )
        for e in _ENTRI
    ]
    session.add_all(entri)
    session.flush()
    return entri


def main() -> None:
    from app.db import session_scope

    with session_scope() as session:
        entri = seed(session)
        print(f"Seed selesai: {len(entri)} entri panduan bunga KUR (status=draft).")


if __name__ == "__main__":
    main()

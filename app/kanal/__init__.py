"""Lapisan KANAL — seam channel-agnostic antara orchestrator dan UI.

Sesuai 02-arsitektur.md: UI web chat hanyalah **satu adaptor**; adaptor WhatsApp
nanti me-render kontrak yang sama tanpa menyentuh inti. Karena itu keluaran
orchestrator berbentuk `PesanKeluar` (amplop ber-versi berisi kartu), bukan HTML
atau string yang terikat ke satu kanal.

- `kontrak`     — tipe kartu + amplop ber-versi (tanpa dependensi model/HTTP).
- `orkestrator` — memetakan tool/service ke kartu kontrak (deterministik tipis).
"""

from app.kanal.kontrak import (
    VERSI_KONTRAK,
    BarisImpor,
    BarisKomponen,
    BarisKonfirmasi,
    BarisPos,
    BarisRingkas,
    BarisUntung,
    KartuBelumDiketahui,
    KartuDokumen,
    KartuImpor,
    KartuKeuangan,
    KartuKlarifikasi,
    KartuKonfirmasi,
    KartuNarasi,
    KartuPanduanKur,
    KartuResep,
    KartuRiwayat,
    KartuSapaan,
    KartuSkor,
    KartuUntung,
    PesanKeluar,
    PilihanKategori,
    TipeKartu,
)
from app.kanal.orkestrator import (
    KonteksTunggu,
    kartu_impor_konfirmasi,
    kartu_impor_putuskan,
    kartu_impor_terima_yakin,
    kartu_impor_teks,
    kartu_impor_tinjau,
    kartu_keuangan,
    kartu_laporan,
    kartu_panduan_kur,
    kartu_riwayat,
    kartu_skor,
    kartu_untung,
    koreksi_kategori,
    sapaan,
    tangani_pesan,
)

__all__ = [
    "VERSI_KONTRAK",
    "BarisImpor",
    "BarisKomponen",
    "BarisKonfirmasi",
    "BarisPos",
    "BarisRingkas",
    "BarisUntung",
    "KartuBelumDiketahui",
    "KartuDokumen",
    "KartuImpor",
    "KartuKeuangan",
    "KartuKlarifikasi",
    "KartuKonfirmasi",
    "KartuNarasi",
    "KartuPanduanKur",
    "KartuResep",
    "KartuRiwayat",
    "KartuSapaan",
    "KartuSkor",
    "KartuUntung",
    "KonteksTunggu",
    "PesanKeluar",
    "PilihanKategori",
    "TipeKartu",
    "kartu_impor_konfirmasi",
    "kartu_impor_putuskan",
    "kartu_impor_teks",
    "kartu_impor_terima_yakin",
    "kartu_impor_tinjau",
    "kartu_keuangan",
    "kartu_laporan",
    "kartu_panduan_kur",
    "kartu_riwayat",
    "kartu_skor",
    "kartu_untung",
    "koreksi_kategori",
    "sapaan",
    "tangani_pesan",
]

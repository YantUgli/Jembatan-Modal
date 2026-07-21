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
    BarisKonfirmasi,
    KartuBelumDiketahui,
    KartuKlarifikasi,
    KartuKonfirmasi,
    KartuNarasi,
    KartuSapaan,
    KartuUntung,
    PesanKeluar,
    PilihanKategori,
    TipeKartu,
)
from app.kanal.orkestrator import (
    kartu_untung_stub,
    koreksi_kategori,
    sapaan,
    tangani_pesan,
)

__all__ = [
    "VERSI_KONTRAK",
    "BarisKonfirmasi",
    "KartuBelumDiketahui",
    "KartuKlarifikasi",
    "KartuKonfirmasi",
    "KartuNarasi",
    "KartuSapaan",
    "KartuUntung",
    "PesanKeluar",
    "PilihanKategori",
    "TipeKartu",
    "kartu_untung_stub",
    "koreksi_kategori",
    "sapaan",
    "tangani_pesan",
]

"""Kontrak parser impor (Pilar 2) — `parse(muatan) → list[BarisDraft]`.

Satu bentuk untuk semua sumber (tempelan teks, foto buku tulis, CSV, export
platform). Yang membuat bentuk ini layak jadi seam: **`BarisDraft` bukan
transaksi**. Ia calon transaksi yang masih harus dilewatkan mata pengguna
(aturan #3). Sumber baru = satu parser baru; alur draft, peninjau, dan jalur
commit tidak ikut berubah.

`BarisDraft.baris` memakai ulang `BarisTransaksi` — skema yang sama dengan jalur
chat, dan yang sama pula yang dikonsumsi `simpan_transaksi`. Konsekuensinya
disengaja: transaksi hasil impor mendapat perlakuan **identik** dengan transaksi
hasil chat (penautan produk, penangkapan harga jual, umpan ke HPP). Tidak ada
jalur tulis kedua yang bisa menyimpang perlahan dari yang pertama.

## Keyakinan dihitung kode, bukan dilaporkan model

`keyakinan` **tidak** ditanyakan ke LLM. Model yang menilai keyakinannya sendiri
adalah angka berbaju wibawa — dan aturan #1 melarang angka datang dari model.
Di sini ia turunan dari **apa yang secara struktur ada atau tidak ada di teks
sumbernya**, sehingga bisa diuji dan bisa dijelaskan ke pengguna dengan kalimat
yang menyebut sebabnya.

Sebab yang paling penting: **tanggal yang tidak tertulis.** Di jalur chat,
membiarkan tanggal jatuh ke hari ini hampir selalu benar — orang bercerita
tentang hari yang sedang berjalan. Di jalur impor ia justru berbahaya: halaman
buku tulis bulan Juni yang ditempel hari ini akan memindahkan uangnya ke bulan
ini, dan setiap laporan di atasnya ikut bergeser tanpa ada yang salah tampak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.llm.skema import BarisTransaksi

__all__ = [
    "AMBANG_YAKIN",
    "GAGAL",
    "RAGU",
    "YAKIN",
    "BarisDraft",
    "Parser",
    "nilai_keyakinan",
    "tanggal_disebut",
]

# Tiga tingkat, bukan skala halus: yang dibutuhkan peninjau hanyalah "boleh
# disapu borongan" vs "harus dilihat sendiri". Kolomnya Float (`import_rows`)
# supaya parser lain kelak bisa lebih bergradasi tanpa migrasi.
YAKIN = 1.0
RAGU = 0.6
GAGAL = 0.0

# Batas untuk aksi borongan "centang semua yang yakin". Di bawah ini, baris
# hanya bisa diterima satu per satu — lihat `terima_yakin` di services/impor.py.
AMBANG_YAKIN = 0.9


@dataclass(frozen=True)
class BarisDraft:
    """Satu **calon** transaksi dari satu baris sumber. Belum masuk buku.

    `baris=None` = tidak terbaca sebagai peristiwa uang (judul halaman, baris
    "jumlah", coretan). Baris seperti itu tetap dibawa masuk sebagai draft,
    **tidak dibuang diam-diam**: pengguna yang menempel 20 baris berhak melihat
    20 baris kembali, supaya ia tahu mana yang terbaca dan mana yang tidak.

    Satu baris sumber bisa melahirkan lebih dari satu `BarisDraft` ("laku 75rb,
    beli minyak 38rb" dalam satu baris) — semuanya membawa `raw` yang sama.
    """

    raw: str
    baris: BarisTransaksi | None = None
    keyakinan: float = GAGAL
    catatan: str = ""
    yang_kurang: tuple[str, ...] = ()

    @property
    def terbaca(self) -> bool:
        return self.baris is not None

    @property
    def ragu(self) -> bool:
        """Perlu dilihat sendiri — tak boleh ikut tersapu aksi borongan."""
        return self.keyakinan < AMBANG_YAKIN


class Parser(Protocol):
    """Antarmuka seragam tiap sumber impor.

    `sumber` masuk ke `imports.sumber` (string bebas, bukan enum — daftar sumber
    memang tumbuh; lihat `app/models/base.py`).
    """

    sumber: str

    def parse(self, muatan: str, hari_ini: date) -> list[BarisDraft]: ...


# ── Keyakinan: turunan struktur teks, bukan penilaian model ─────────────────

# Penanda tanggal yang lazim di catatan warung. Sengaja **tidak** mencoba
# mem-parse tanggalnya (itu tugas ekstraksi); ia cuma menjawab "apakah baris ini
# menyebut waktu?".
_POLA_TANGGAL = re.compile(
    r"""
    \b\d{1,2}\s*[/-]\s*\d{1,2}(\s*[/-]\s*\d{2,4})?\b   # 12/6 · 12-06-2026
  | \b(tgl|tanggal)\b
  | \b(jan|feb|mar|apr|mei|jun|jul|agu|agt|sep|okt|nov|des)
    (uari|ruari|et|il|i|us|tus|tember|ober|ember)?\b     # jan · januari · agt
  | \b(kemarin|kmrn|tadi|barusan|lusa|besok|semalam)\b
  | \bhari\s+ini\b
  | \b(senin|selasa|rabu|kamis|jumat|jum'at|sabtu|minggu|ahad)\b
  | \b(minggu|bulan|pekan)\s+(lalu|kemarin|ini)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def tanggal_disebut(teks: str) -> bool:
    """Apakah baris ini menyebut waktu sama sekali?

    Bias-nya sengaja **ke arah curiga**: pola ini hanya menangkap penyebutan yang
    jelas, dan yang lolos dari pola akan ditandai ragu. Salah menandai baris yang
    sebetulnya bertanggal hanya merepotkan pengguna satu ketukan; sebaliknya —
    meloloskan baris yang tanggalnya ditebak — memindahkan uang antar bulan tanpa
    jejak. Dua kesalahan itu tidak setara, jadi penjaganya tidak simetris.
    """
    return _POLA_TANGGAL.search(teks) is not None


def nilai_keyakinan(raw: str, baris: BarisTransaksi, hari_ini: date) -> tuple[float, str]:
    """→ (keyakinan, catatan bahasa warung). Deterministik, tanpa model."""
    if tanggal_disebut(raw):
        return YAKIN, ""
    if baris.tanggal == hari_ini:
        return RAGU, (
            "Tanggalnya tidak tertulis di baris ini, jadi saya pakai tanggal hari ini. "
            "Kalau catatan ini dari hari lain, tolong dibetulkan dulu."
        )
    return RAGU, "Tanggalnya tidak tertulis jelas di baris ini — tolong dicek."

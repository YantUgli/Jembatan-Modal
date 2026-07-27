"""Format & aritmatika tanggal bersama — satu tabel bulan untuk seluruh produk.

Dipisah dari `orkestrator.py` saat laporan PDF lahir: kartu chat dan dokumen PDF
harus menyebut periode yang sama dengan **bunyi yang sama persis** ("1–26 Jul
2026"). Dua salinan tabel nama bulan = dua tempat yang bisa menyimpang, dan
penyimpangannya baru terlihat saat AO bank membandingkan dokumen dengan layar.

Murni tipe data + string — tanpa DB, tanpa LLM, tanpa uang (uang ada di
`angka.py`).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

__all__ = [
    "BULAN",
    "akhir_bulan",
    "awal_bulan",
    "bulan_kalender_terakhir",
    "nama_bulan",
    "periode_tampil",
    "tgl_pendek",
]

# Singkatan bulan Indonesia; indeks 1..12 (indeks 0 sengaja kosong).
BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def nama_bulan(t: date) -> str:
    """'Jul 2026' — label satu baris bulan di tabel laporan."""
    return f"{BULAN[t.month]} {t.year}"


def tgl_pendek(t: date) -> str:
    """'24 Jul' — tanggal ringkas per baris riwayat."""
    return f"{t.day} {BULAN[t.month]}"


def periode_tampil(mulai: date, selesai: date) -> str:
    """'1–21 Jul 2026', atau '18 Mei–21 Jul 2026' bila beda bulan."""
    if mulai.year == selesai.year and mulai.month == selesai.month:
        return f"{mulai.day}–{selesai.day} {BULAN[selesai.month]} {selesai.year}"
    kiri = f"{mulai.day} {BULAN[mulai.month]}"
    if mulai.year != selesai.year:
        kiri += f" {mulai.year}"
    return f"{kiri}–{selesai.day} {BULAN[selesai.month]} {selesai.year}"


def awal_bulan(t: date) -> date:
    return t.replace(day=1)


def akhir_bulan(t: date) -> date:
    """Tanggal terakhir bulan `t` **menurut kalender** — bukan hari ini.

    Dipakai laporan untuk membedakan bulan yang sudah penuh dari bulan berjalan
    yang baru separuh: bulan penuh selalu ditutup di tanggal kalendernya.
    """
    return t.replace(day=calendar.monthrange(t.year, t.month)[1])


def bulan_kalender_terakhir(hari_ini: date, jumlah: int = 3) -> list[tuple[date, date]]:
    """`jumlah` bulan kalender terakhir **termasuk bulan berjalan**, terlama dulu.

    Tiap elemen `(awal, akhir)`. Bulan berjalan ditutup di `hari_ini`, bukan di
    akhir kalendernya — laporan tidak boleh menyiratkan punya data untuk hari
    yang belum terjadi (aturan #2). Pemanggil membedakan keduanya lewat
    `akhir_bulan()`.
    """
    if jumlah < 1:
        raise ValueError("jumlah bulan minimal 1")

    rentang: list[tuple[date, date]] = []
    kursor = awal_bulan(hari_ini)
    for _ in range(jumlah):
        bulan_berjalan = (kursor.year, kursor.month) == (hari_ini.year, hari_ini.month)
        rentang.append((kursor, hari_ini if bulan_berjalan else akhir_bulan(kursor)))
        # Mundur satu bulan lewat tanggal 1 bulan sebelumnya — panjang bulan tak
        # seragam, jadi jangan pernah mengurangi 30 hari.
        kursor = awal_bulan(kursor - timedelta(days=1))
    rentang.reverse()
    return rentang

"""Membaca periode dari kalimat pemilik — **deterministik, tanpa LLM**.

Sampai slice ini seluruh produk hanya bisa menjawab satu periode: bulan
berjalan. *"untung bulan lalu berapa"* dijawab dengan angka bulan ini, tanpa
tanda apa pun bahwa pertanyaannya tidak dijawab. Modul ini yang menutupnya.

**Kenapa kode, bukan model.** Prompt router hari ini justru berkata "Periode
/tanggal TIDAK PERNAH kamu perlukan" (`app/llm/skema.py`), dan menambah field
kedua ke `PilihanAksi` berisiko menggeser akurasi label — di ukuran model yang
kita pakai, prompt jungkat-jungkit (`docs/06-evaluasi-ekstraksi.md`). Kosakata
waktu warung sendiri kecil dan tertutup, jadi regex + aritmatika kalender
menyelesaikannya dengan nol token, nol latensi, dan bisa diuji habis. Kalau
suatu saat terbukti kurang, jalur LLM bisa ditumpuk **di atas** modul ini tanpa
membongkarnya.

**Frasa tak dikenal → `None`, bukan tebakan.** Pemanggil memakai default bulan
berjalan (perilaku sebelum modul ini ada) — tapi kartunya wajib menuliskan
periode yang benar-benar dipakai. Salah baca jadi terlihat pengguna dan bisa
dibetulkan satu ketukan, bukan diam-diam salah (aturan #2).

Murni: tanpa DB, tanpa LLM, tanpa uang. Aritmatika kalender dipinjam dari
`app/services/tanggal.py` — jangan menulis tabel bulan kedua di sini.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.services.tanggal import akhir_bulan, awal_bulan, bulan_kalender_terakhir, nama_bulan

__all__ = [
    "MAKS_BULAN",
    "MAKS_HARI",
    "Periode",
    "baca_periode",
    "menyebut_masa_depan",
    "periode_dari_label",
    "periode_n_hari",
]

# Rentang "N bulan terakhir" yang dilayani. Di atas ini pertanyaannya bukan lagi
# soal warung berjalan, dan laporan multi-tahun bukan permukaan chat.
MAKS_BULAN = 12

# Rentang "N hari terakhir" yang dilayani lewat label chip.
MAKS_HARI = 366


@dataclass(frozen=True)
class Periode:
    """Rentang tanggal + dua nama untuknya.

    `label` mesin-readable, dipakai chip UI & parameter API — dan sengaja bisa
    dibalik lagi jadi `Periode` lewat `periode_dari_label`, supaya kartu bisa
    mengirim balik periodenya sendiri tanpa mengirim tanggal mentah.
    `sebutan` dibaca manusia (isi chip).
    """

    mulai: date
    selesai: date
    label: str
    sebutan: str


# ── Kosakata ────────────────────────────────────────────────────────────────
#
# Tabel nama bulan di bawah dipakai **hanya untuk MEMBACA**, tak pernah
# dirender — yang tampil di layar tetap `tanggal.py` (satu tabel tampilan untuk
# seluruh produk). Sengaja tanpa singkatan tiga huruf: "jan" adalah "jangan"
# dalam bahasa sehari-hari Jakarta, dan salah tembak di sini berarti menjawab
# periode yang sama sekali lain.
_BULAN_NAMA = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}

_ANGKA_KATA = {
    "satu": 1,
    "dua": 2,
    "tiga": 3,
    "empat": 4,
    "lima": 5,
    "enam": 6,
    "tujuh": 7,
    "delapan": 8,
    "sembilan": 9,
    "sepuluh": 10,
    "sebelas": 11,
    "dua belas": 12,
}

_KATA_N = "|".join(sorted(_ANGKA_KATA, key=len, reverse=True))
_NAMA_N = "|".join(_BULAN_NAMA)

_P_N_BULAN = re.compile(rf"\b(?:(\d{{1,2}})|({_KATA_N}))\s+bulan\s+(?:terakhir|belakangan|ini)\b")
_P_BULAN_LALU = re.compile(r"\bbulan\s+(?:lalu|kemarin|kemaren)\b")
_P_BULAN_INI = re.compile(r"\bbulan\s+ini\b")
_P_MINGGU_LALU = re.compile(r"\bminggu\s+(?:lalu|kemarin|kemaren)\b")
_P_MINGGU_INI = re.compile(r"\bminggu\s+ini\b")
_P_TAHUN_INI = re.compile(r"\btahun\s+ini\b")
_P_HARI_INI = re.compile(r"\bhari\s+(?:ini|ni)\b")
_P_KEMARIN = re.compile(r"\b(?:kemarin|kemaren)\b")
_P_BULAN_NAMA = re.compile(rf"\b({_NAMA_N})\b(?:\s+(\d{{4}}))?")

_P_MASA_DEPAN = re.compile(r"\b(?:besok|besuk|lusa|(?:bulan|minggu|tahun)\s+depan)\b")


# ── Pembangun rentang ───────────────────────────────────────────────────────


def _hari(t: date, label: str, sebutan: str) -> Periode:
    return Periode(t, t, label, sebutan)


def _sampai_hari_ini(mulai: date, hari_ini: date, label: str, sebutan: str) -> Periode:
    return Periode(mulai, hari_ini, label, sebutan)


def _bulan_bernama(tahun: int, bulan: int, hari_ini: date) -> Periode:
    """Satu bulan kalender. Bulan berjalan ditutup di hari ini — bukan di akhir
    kalendernya: menyiratkan punya data untuk hari yang belum terjadi sama saja
    dengan mengarang angka (aturan #2)."""
    mulai = date(tahun, bulan, 1)
    selesai = min(akhir_bulan(mulai), hari_ini)
    return Periode(mulai, selesai, f"bulan:{tahun}-{bulan:02d}", nama_bulan(mulai))


def _bulan_lalu(hari_ini: date) -> Periode:
    akhir = awal_bulan(hari_ini) - timedelta(days=1)
    return Periode(awal_bulan(akhir), akhir, "bulan_lalu", "Bulan lalu")


def _minggu_ini(hari_ini: date) -> Periode:
    senin = hari_ini - timedelta(days=hari_ini.weekday())
    return Periode(senin, hari_ini, "minggu_ini", "Minggu ini")


def _minggu_lalu(hari_ini: date) -> Periode:
    senin = hari_ini - timedelta(days=hari_ini.weekday() + 7)
    return Periode(senin, senin + timedelta(days=6), "minggu_lalu", "Minggu lalu")


def _n_bulan(n: int, hari_ini: date) -> Periode | None:
    if not 1 <= n <= MAKS_BULAN:
        return None
    mulai = bulan_kalender_terakhir(hari_ini, n)[0][0]
    return Periode(mulai, hari_ini, f"{n}_bulan", f"{n} bulan terakhir")


def _tahun_ini(hari_ini: date) -> Periode:
    return Periode(date(hari_ini.year, 1, 1), hari_ini, "tahun_ini", "Tahun ini")


def periode_n_hari(n: int, hari_ini: date) -> Periode:
    """`n` hari terakhir **termasuk hari ini** — jendela bergulir, bukan kalender.

    Dipakai skor kesehatan usaha: komponen "% hari bercatatan" atas bulan berjalan
    membaca 2 dari 3 hari pada tanggal 3 lalu bergeser sepanjang bulan, jadi
    skornya turun-naik karena kalender, bukan karena perilaku pemilik
    (`docs/keputusan.md` 2026-07-27).

    ⛔ Tidak masuk kosakata `baca_periode`: tak ada pemilik warung yang bertanya
    "30 hari terakhir". Ia hidup di jalur label/chip saja.
    """
    if not 1 <= n <= MAKS_HARI:
        raise ValueError(f"rentang hari di luar jangkauan: {n}")
    return Periode(hari_ini - timedelta(days=n - 1), hari_ini, f"{n}_hari", f"{n} hari terakhir")


# ── Pembacaan kalimat ───────────────────────────────────────────────────────


def _dari_n_bulan(m: re.Match[str], hari_ini: date) -> Periode | None:
    n = int(m.group(1)) if m.group(1) else _ANGKA_KATA[m.group(2)]
    return _n_bulan(n, hari_ini)


def _dari_nama_bulan(m: re.Match[str], hari_ini: date) -> Periode | None:
    bulan = _BULAN_NAMA[m.group(1)]
    if m.group(2):
        tahun = int(m.group(2))
        # Bulan yang seluruhnya di masa depan bukan periode yang bisa dijawab —
        # `menyebut_masa_depan` yang menanganinya, jangan diam-diam digeser.
        return None if date(tahun, bulan, 1) > hari_ini else _bulan_bernama(tahun, bulan, hari_ini)
    # Tanpa tahun: kejadian terakhir yang sudah lewat / sedang berjalan. Di Juli
    # 2026 "Desember" berarti Des 2025 — memilih Des 2026 akan dijawab nol dan
    # terbaca seperti usaha yang mati.
    tahun = hari_ini.year if bulan <= hari_ini.month else hari_ini.year - 1
    return _bulan_bernama(tahun, bulan, hari_ini)


# Urutan penting: pola yang lebih panjang dibaca lebih dulu, lalu potongannya
# dihapus dari teks. Tanpa itu "bulan kemarin" ikut terbaca sebagai "kemarin",
# dan "3 bulan terakhir" ikut terbaca sebagai "bulan ini".
_URUTAN: list[tuple[re.Pattern[str], object]] = [
    (_P_N_BULAN, _dari_n_bulan),
    (_P_BULAN_LALU, lambda m, h: _bulan_lalu(h)),
    (_P_BULAN_INI, lambda m, h: _sampai_hari_ini(awal_bulan(h), h, "bulan_ini", "Bulan ini")),
    (_P_MINGGU_LALU, lambda m, h: _minggu_lalu(h)),
    (_P_MINGGU_INI, lambda m, h: _minggu_ini(h)),
    (_P_TAHUN_INI, lambda m, h: _tahun_ini(h)),
    (_P_HARI_INI, lambda m, h: _hari(h, "hari_ini", "Hari ini")),
    (_P_KEMARIN, lambda m, h: _hari(h - timedelta(days=1), "kemarin", "Kemarin")),
    (_P_BULAN_NAMA, _dari_nama_bulan),
]


def baca_periode(teks: str, hari_ini: date) -> Periode | None:
    """Periode yang disebut kalimat, atau `None` bila tak ada / tak terbaca.

    `None` bukan kegagalan: pemanggil memakai default bulan berjalan **dan
    menuliskannya di kartu**. Dua frasa waktu berbeda dalam satu kalimat juga
    `None` — "bulan lalu sampai bulan ini" di luar kosakata ini, dan memilih
    salah satunya lebih buruk daripada default yang tertulis jelas.

    ⚠️ Hanya untuk kalimat **pertanyaan**. Jangan panggil di jalur pencatatan:
    di sana tanggal adalah isi transaksi ("kemarin jual bakso 400rb") dan sudah
    diurus ekstraksi.
    """
    sisa = teks.lower()
    ketemu: list[Periode] = []
    for pola, buat in _URUTAN:
        for m in pola.finditer(sisa):
            p = buat(m, hari_ini)  # type: ignore[operator]
            if p is not None:
                ketemu.append(p)
        sisa = pola.sub(lambda m: " " * len(m.group(0)), sisa)

    rentang = {(p.mulai, p.selesai) for p in ketemu}
    if len(rentang) != 1:
        return None
    return ketemu[0]


def menyebut_masa_depan(teks: str, hari_ini: date) -> bool:
    """Kalimat menanyakan waktu yang belum terjadi.

    Dipisah dari `baca_periode` supaya masing-masing satu tugas. Pemanggil
    membalasnya dengan pertanyaan balik, **bukan** kartu berisi nol: nol yang
    tampak seperti hasil hitungan atas periode yang belum ada = mengarang
    (aturan #2).
    """
    rendah = teks.lower()
    if _P_MASA_DEPAN.search(rendah):
        return True
    for m in _P_BULAN_NAMA.finditer(rendah):
        if m.group(2) and date(int(m.group(2)), _BULAN_NAMA[m.group(1)], 1) > hari_ini:
            return True
    return False


def periode_dari_label(label: str, hari_ini: date) -> Periode:
    """Resolusi label chip/API jadi rentang. Label asing → `ValueError`.

    ⛔ Sengaja melempar, bukan diam-diam memakai default: klien yang mengirim
    label salah harus dapat 422, bukan jawaban periode lain yang tampak sah.
    """
    tetap = {
        "hari_ini": lambda h: _hari(h, "hari_ini", "Hari ini"),
        "kemarin": lambda h: _hari(h - timedelta(days=1), "kemarin", "Kemarin"),
        "minggu_ini": _minggu_ini,
        "minggu_lalu": _minggu_lalu,
        "bulan_ini": lambda h: _sampai_hari_ini(awal_bulan(h), h, "bulan_ini", "Bulan ini"),
        "bulan_lalu": _bulan_lalu,
        "tahun_ini": _tahun_ini,
    }
    if label in tetap:
        return tetap[label](hari_ini)

    if (m := re.fullmatch(r"(\d{1,2})_bulan", label)) and (p := _n_bulan(int(m.group(1)), hari_ini)):
        return p

    if m := re.fullmatch(r"(\d{1,3})_hari", label):
        n = int(m.group(1))
        if 1 <= n <= MAKS_HARI:
            return periode_n_hari(n, hari_ini)

    if m := re.fullmatch(r"bulan:(\d{4})-(\d{2})", label):
        tahun, bulan = int(m.group(1)), int(m.group(2))
        if 1 <= bulan <= 12 and date(tahun, bulan, 1) <= hari_ini:
            return _bulan_bernama(tahun, bulan, hari_ini)

    raise ValueError(f"periode tidak dikenal: {label!r}")

"""Helper angka bersama seluruh service.

Dipisah agar `hpp.py` dan `harga.py` bisa saling dipakai tanpa impor melingkar.
Semua uang dibulatkan 2 desimal, ROUND_HALF_UP — jangan pakai float di jalur
perhitungan mana pun.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DUA_DESIMAL = Decimal("0.01")

# Karakter selain digit/koma/titik/minus dibuang — menyapu "Rp", spasi ribuan,
# dan kotoran lain dari salinan CSV/rekening koran sekaligus.
_BUKAN_ANGKA = re.compile(r"[^0-9,.\-]")


def _dec(x) -> Decimal:
    """Koersi nilai DB (Decimal/float/int) ke Decimal dengan aman."""
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _uang(x: Decimal) -> Decimal:
    return x.quantize(DUA_DESIMAL, rounding=ROUND_HALF_UP)


def rupiah(x: Decimal) -> str:
    """Uang dalam bentuk yang dibaca pemilik warung: 75000 → 'Rp75.000'.

    Sen dibuang bila nol — "Rp75.000,00" bukan cara orang menyebut uang di
    warung. Kalau ada sennya, tetap ditampilkan supaya tidak ada angka yang
    diam-diam hilang.

    Nilai negatif ditulis '−Rp1.500', bukan 'Rp-1.500': tandanya di depan seluruh
    jumlah, sebagaimana orang menuliskannya. Ini bukan soal selera — laba bersih
    minus dan "biaya di luar HPP" yang negatif keduanya muncul di laporan yang
    dibaca analis kredit, dan 'Rp-' di sana terbaca seperti salah cetak.
    """
    nilai = _uang(_dec(x))
    tanda = "−" if nilai < 0 else ""
    nilai = abs(nilai)
    utuh = int(nilai)
    teks = f"Rp{utuh:,}".replace(",", ".")
    sen = nilai - utuh
    if sen:
        teks += "," + f"{sen:.2f}"[2:]
    return tanda + teks


def persen(x) -> str:
    """0..100 (Decimal) → '78%' / '78.5%'. Bukan uang, jadi bukan `rupiah()`.

    Dipakai bersama kartu chat dan laporan PDF — cakupan HPP wajib berbunyi sama
    di layar dan di dokumen (aturan #2).
    """
    return f"{_rapikan(_dec(x))}%"


def angka_rupiah(teks: str | None) -> Decimal | None:
    """Angka gaya Indonesia (teks bebas) → `Decimal`, atau `None` bila tak terbaca.

    Konvensi Indonesia yang dipakai, **tanpa kecuali**: titik selalu pemisah
    ribuan, koma selalu pemisah desimal. `"1.250.000,50"` → 1250000.50;
    `"1.000"` → 1000 (bukan 1.0) — titik di sana bukan desimal, walau posisinya
    mirip notasi Inggris. Dipakai jalur impor CSV (§5 rencana eksekusi): angka
    dari rekening koran/pembukuan tak boleh salah baca cuma karena beda gaya
    pemisah.

    String kosong/tak terbaca → `None` (aturan #2: mengaku, bukan mengarang),
    **tidak pernah** melempar exception — baris CSV yang rusak tidak boleh
    menghentikan seluruh impor (lihat filosofi `ParserTeks`: satu baris busuk
    tidak membunuh baris lain).
    """
    if teks is None:
        return None
    bersih = _BUKAN_ANGKA.sub("", teks.strip())
    if not bersih or bersih in {"-", ".", ","}:
        return None

    tanda = ""
    if bersih.startswith("-"):
        tanda, bersih = "-", bersih[1:]
    if bersih.count(",") > 1 or not bersih:
        return None

    bersih = bersih.replace(".", "").replace(",", ".")
    try:
        return Decimal(tanda + bersih)
    except InvalidOperation:
        return None


def _rapikan(x: Decimal) -> str:
    """Buang nol berekor untuk teks yang dibaca pengguna: 30.4687500 → 30.46875."""
    t = x.normalize()
    if t == t.to_integral_value():
        t = t.to_integral_value()
    return f"{t:f}"

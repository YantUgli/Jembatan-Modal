"""Penjaga sisi-input: menolak angka yang dihitung model, bukan diucapkan.

Pasangan dari `angka_asing()` di sisi keluaran. Keduanya menegakkan aturan #1,
tapi di dua tempat yang berbeda — dan sisi input jauh lebih berbahaya:

    narasi   : angka karangan muncul di layar, sekali, lalu hilang.
    ekstraksi: angka karangan masuk DATABASE sebagai fakta. Setiap laporan,
               HPP, dan skor di atasnya ikut salah — dan `angka_asing` tidak
               akan pernah menangkapnya, karena angkanya memang "ada di fakta".

Evaluasi 2026-07-19 menemukan ini nyata: "laku 5 kotak risol 75rb" dijawab
nominal 375.000 (5 × 75rb), dan "jual 2,5 kg ayam 90rb" jadi 225.000. Prompt
sudah dilarang berhitung dan tetap terjadi — larangan menutup contoh yang
disebut, bukan perilakunya. Karena itu penjaganya di sini, bukan di prompt.

⛔ Ini **bukan** parser nominal. Kita tidak menerjemahkan kalimat jadi angka —
itu pekerjaan yang error-prone dan bukan tugas kita. Kita cuma mengumpulkan
angka yang **terbaca di kalimat**, lalu memeriksa satu pola yang sangat spesifik:
`nominal = qty × angka lain di kalimat`, padahal nominalnya sendiri tidak
pernah diucapkan. Sempit dengan sengaja — penjaga yang sering salah tuduh akan
dimatikan orang, dan penjaga yang mati tidak menjaga apa pun.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

__all__ = ["angka_di_teks", "hasil_kali_terdeteksi", "periksa_nominal"]

# Satuan nominal yang lazim di percakapan warung.
_SUFIKS = {
    "rb": 1_000, "ribu": 1_000, "k": 1_000,
    "jt": 1_000_000, "juta": 1_000_000,
    "miliar": 1_000_000_000, "milyar": 1_000_000_000,
}

# Slang nominal yang bentuknya kata utuh, bukan angka bersuffix.
_SLANG = {
    "gopek": 500, "cepek": 100, "seceng": 1_000, "noceng": 2_000,
    "ceceng": 3_000, "goceng": 5_000, "ceban": 10_000, "goban": 50_000,
    "sejuta": 1_000_000,
}

_POLA_ANGKA = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(rb|ribu|k|jt|juta|miliar|milyar)?\b",
    re.IGNORECASE,
)
_POLA_KATA = re.compile(r"[a-zA-Z]+")


def _ke_desimal(mentah: str, bersuffix: bool) -> Decimal | None:
    """'75.000' → 75000 ; '1,5' + suffix → 1.5 ; '15' → 15."""
    pisah = re.findall(r"[.,]", mentah)
    try:
        # Satu pemisah + ada suffix ("1,5jt") = koma desimal.
        # Tanpa suffix, pemisah di angka rupiah hampir selalu ribuan ("75.000").
        if bersuffix and len(pisah) == 1:
            return Decimal(mentah.replace(",", "."))
        return Decimal(re.sub(r"[.,]", "", mentah))
    except InvalidOperation:
        return None


def angka_di_teks(teks: str) -> set[Decimal]:
    """Semua nilai yang benar-benar TERBACA di kalimat.

    "laku 5 kotak risol 75rb" → {5, 75, 75000}. Bentuk mentah (75) ikut
    disertakan karena pengguna kadang menulis "75" untuk 75 ribu; menyertakannya
    membuat penjaga lebih pemaaf, dan pemaaf adalah sikap yang benar di sini.
    """
    hasil: set[Decimal] = set()

    for mentah, suffix in _POLA_ANGKA.findall(teks):
        nilai = _ke_desimal(mentah, bool(suffix))
        if nilai is None:
            continue
        hasil.add(nilai)
        if suffix:
            hasil.add(nilai * _SUFIKS[suffix.lower()])

    for kata in _POLA_KATA.findall(teks):
        nilai = _SLANG.get(kata.lower())
        if nilai is not None:
            hasil.add(Decimal(nilai))

    return hasil


def hasil_kali_terdeteksi(
    teks: str, nominal: Decimal, qty: Decimal | None
) -> Decimal | None:
    """Angka pengali bila `nominal` tampak hasil `qty × <angka di kalimat>`.

    `None` = tidak ada tanda perkalian. Tiga syarat harus terpenuhi sekaligus,
    supaya tuduhan ini jarang tapi hampir selalu benar:

    1. ada `qty` dan lebih dari 1 — kalau qty 1, perkalian tak mengubah apa pun;
    2. `nominal` **tidak** terbaca di kalimat — kalau pengguna menyebutnya,
       model hanya menyalin, dan itu justru yang kita mau;
    3. ada angka di kalimat yang bila dikali `qty` menghasilkan `nominal` persis.
    """
    if qty is None or qty <= 1:
        return None

    angka = angka_di_teks(teks)
    if nominal in angka:
        return None

    for a in sorted(angka, reverse=True):
        if a > 0 and qty * a == nominal:
            return a
    return None


def periksa_nominal(
    teks: str, nominal: Decimal, qty: Decimal | None = None
) -> str | None:
    """→ alasan penolakan, atau `None` bila nominal boleh dipercaya."""
    pengali = hasil_kali_terdeteksi(teks, nominal, qty)
    if pengali is None:
        return None
    return (
        f"Nominal {nominal} tampak dihitung sendiri ({qty} x {pengali}), "
        f"padahal tidak disebut di kalimat. Totalnya perlu ditanyakan, "
        f"bukan dihitung."
    )

"""Adaptor impor #1 — **tempelan teks banyak baris** (WhatsApp, notes HP, SMS).

Adaptor pertama sengaja bukan foto, walau [04-rencana-kerja.md](../../docs/04-rencana-kerja.md)
Tahap 3 menyebut foto lebih dulu. Alasannya bukan kemudahan, melainkan apa yang
bisa **diuji**: berkas impor nyata masih utang Tahap 0, jadi fixture foto hari
ini akan berisi gambar karangan sendiri — yang menguji imajinasi penulisnya,
bukan buku tulis orang. Yang benar-benar perlu dibuktikan di slice fondasi ini
adalah **alur draft**-nya, dan tempelan teks membuktikannya dengan mesin
ekstraksi yang sudah teruji. Foto masuk ke slot `Parser` yang sama.

## Satu baris = satu panggilan ekstraksi

Kelihatan mahal, dan itu keputusan sadar (lihat [02-arsitektur.md §6a](../../docs/02-arsitektur.md)):

- **Impor jarang & sengaja.** Ia peristiwa onboarding/menyusul, bukan aksi
  harian seperti `catat_transaksi`. Disiplin biaya §6a mengarah ke jalur
  bervolume tinggi; jalur ini bukan itu.
- **Satu baris busuk tidak boleh membunuh 29 baris sehat.** `ekstrak_transaksi`
  menolak **seluruh** teks bila penjaga aturan #1 curiga di satu baris — perilaku
  yang benar untuk satu kalimat chat, tapi merusak untuk satu halaman buku.
- **Penjaga jadi tepat sasaran.** `periksa_nominal` membandingkan nominal dengan
  angka yang terbaca **di teks yang sama**; menyuapkan 30 baris sekaligus
  membuat angka baris 4 dianggap "terbaca" saat memeriksa baris 17.
- **`import_rows.raw` jadi jujur.** Satu baris draft menunjuk persis satu baris
  sumber, jadi peninjau melihat tulisannya sendiri, bukan potongan blob.

Kalau kelak terasa mahal, obatnya adalah mem-chunk beberapa baris per panggilan
dengan jatuh-balik per-baris saat gagal — dan itu **tidak** mengubah kontrak
`Parser`.
"""

from __future__ import annotations

import re
from datetime import date

from app.impor.kontrak import GAGAL, BarisDraft, nilai_keyakinan
from app.llm.ekstraksi import ekstrak_transaksi
from app.llm.kontrak import AdapterLLM, Gagal

__all__ = ["MAKS_BARIS", "MIN_BARIS_TEMPELAN", "ParserTeks", "TerlaluBanyakBaris", "tampak_tempelan"]

# Batas atas satu impor. Bukan sekadar pagar biaya: tempelan raksasa juga tak
# bisa ditinjau dengan jujur di layar HP, dan peninjauan yang tak mungkin
# dilakukan adalah peninjauan yang akan dilewati (aturan #3 jadi formalitas).
MAKS_BARIS = 60

# Sejak berapa baris sebuah pesan dianggap tempelan, bukan kalimat. Dua baris
# masih lazim diketik tangan ("laku 5 risol\nbeli minyak 38rb"); tiga ke atas
# nyaris selalu hasil salin-tempel.
MIN_BARIS_TEMPELAN = 3

# Awalan penomoran/bullet yang ikut tersalin dari notes & WhatsApp.
_AWALAN = re.compile(r"^\s*(?:[-*•·–—]+|\d{1,3}[.)])\s*")


class TerlaluBanyakBaris(ValueError):
    """Tempelan melewati `MAKS_BARIS`. Sengaja menolak, bukan memotong.

    Memotong di baris ke-60 akan menghilangkan sisanya tanpa pengguna tahu —
    kehilangan data yang diam, jenis kegagalan yang paling dilarang di repo ini.
    """


def baris_bersih(muatan: str) -> list[str]:
    """Pecah tempelan jadi baris berisi, tanpa bullet/penomoran."""
    hasil = []
    for mentah in muatan.splitlines():
        baris = _AWALAN.sub("", mentah).strip()
        if baris:
            hasil.append(baris)
    return hasil


def tampak_tempelan(teks: str) -> bool:
    """Apakah pesan ini tempelan banyak baris, bukan satu kalimat?

    Dipakai **orchestrator** untuk membelokkan tempelan ke jalur draft. Tanpa
    belokan itu, menempel 30 baris ke kotak chat akan diklasifikasi
    `catat_transaksi` lalu ditulis langsung ke buku — impor yang auto-commit
    tanpa pernah disebut impor, tepat yang dilarang aturan #3. Definisinya hidup
    di sini, satu tempat, supaya parser dan orchestrator tak pernah berbeda
    pendapat soal "apa itu tempelan".
    """
    return len(baris_bersih(teks)) >= MIN_BARIS_TEMPELAN


class ParserTeks:
    """Tempelan teks → daftar `BarisDraft`. Tidak menyentuh database."""

    sumber = "teks"

    def __init__(self, adapter: AdapterLLM) -> None:
        self._adapter = adapter

    def parse(self, muatan: str, hari_ini: date) -> list[BarisDraft]:
        baris = baris_bersih(muatan)
        if len(baris) > MAKS_BARIS:
            raise TerlaluBanyakBaris(
                f"Sekali tempel maksimal {MAKS_BARIS} baris; ini {len(baris)} baris."
            )

        draft: list[BarisDraft] = []
        for mentah in baris:
            draft.extend(self._satu_baris(mentah, hari_ini))
        return draft

    def _satu_baris(self, mentah: str, hari_ini: date) -> list[BarisDraft]:
        hasil = ekstrak_transaksi(self._adapter, mentah, hari_ini)

        if isinstance(hasil, Gagal):
            return [
                BarisDraft(
                    raw=mentah,
                    keyakinan=GAGAL,
                    catatan=_sebab_gagal(hasil),
                    yang_kurang=tuple(hasil.yang_kurang),
                )
            ]

        if not hasil.data.baris:
            return [
                BarisDraft(
                    raw=mentah,
                    keyakinan=GAGAL,
                    catatan="Tidak terbaca sebagai catatan uang.",
                    yang_kurang=("nominal",),
                )
            ]

        keluar = []
        for b in hasil.data.baris:
            keyakinan, catatan = nilai_keyakinan(mentah, b, hari_ini)
            keluar.append(
                BarisDraft(raw=mentah, baris=b, keyakinan=keyakinan, catatan=catatan)
            )
        return keluar


# Sebab ditulis dari kode, bukan dari `Gagal.alasan`. Alasan itu dipengaruhi
# teks pengguna (masukan tak tepercaya, aturan #6) dan bunyinya teknis — sama
# alasannya dengan `_tanya()` di `app/tools/catat_transaksi.py`.
_SEBAB = {
    "nominal": "Nominalnya tidak terbaca di baris ini.",
    "jenis": "Belum jelas ini uang masuk, belanja, biaya, atau untuk pribadi.",
    "tanggal": "Tanggalnya tidak terbaca.",
    "produk": "Barangnya tidak disebut.",
}
_URUTAN = ("nominal", "jenis", "tanggal", "produk")


def _sebab_gagal(gagal: Gagal) -> str:
    kurang = set(gagal.yang_kurang)
    sebab = [_SEBAB[k] for k in _URUTAN if k in kurang]
    return " ".join(sebab) if sebab else "Baris ini belum tertangkap maksudnya."

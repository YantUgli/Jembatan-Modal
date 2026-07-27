"""Titik masuk ekstraksi transaksi — satu-satunya pintu yang boleh dipakai tool.

`AdapterLLM.ekstrak()` sengaja generik: ia tahu skema, tidak tahu domain.
Di sinilah pengetahuan domain ditambahkan, dan yang terpenting: **penjaga
aturan #1 dipasang di jalur yang tidak bisa dilewati**.

⛔ Jangan memanggil `adapter.ekstrak(...)` langsung dari tool `catat_transaksi`.
Kalau itu dilakukan, penjaganya terlewat tanpa suara — dan angka hasil hitungan
model masuk database sebagai fakta.
"""

from __future__ import annotations

from datetime import date

from app.llm.kontrak import AdapterLLM, Ekstraksi, Gagal
from app.llm.penjaga import periksa_nominal
from app.llm.skema import HasilCatat, HasilResep, instruksi_catat, instruksi_resep

__all__ = ["ekstrak_resep", "ekstrak_transaksi"]


def ekstrak_transaksi(
    adapter: AdapterLLM, teks: str, hari_ini: date
) -> Ekstraksi[HasilCatat] | Gagal:
    """Ubah kalimat pemilik warung jadi daftar transaksi yang bisa dipercaya."""
    hasil = adapter.ekstrak(instruksi_catat(hari_ini), teks, HasilCatat)
    if isinstance(hasil, Gagal):
        return hasil

    masalah = [
        alasan
        for b in hasil.data.baris
        if (alasan := periksa_nominal(teks, b.nominal, b.qty))
    ]
    if masalah:
        # Seluruh kalimat ditolak, bukan sebagian barisnya. Menyimpan separuh
        # kalimat lalu menanyakan sisanya membuat pengguna kehilangan jejak apa
        # yang sudah tercatat dan apa yang belum.
        return Gagal(
            alasan=" ".join(masalah),
            yang_kurang=["nominal"],
            mentah=hasil.mentah,
        )

    return hasil


def ekstrak_resep(
    adapter: AdapterLLM, teks: str, hari_ini: date
) -> Ekstraksi[HasilResep] | Gagal:
    """Ubah kalimat resep pemilik jadi resep terstruktur.

    ⛔ Tanpa penjaga `periksa_nominal` — dan itu disengaja, bukan kelalaian:
    skema resep **bebas-uang** (hanya bahan + takaran). Tidak ada nominal yang
    bisa dikarang model, jadi tak ada yang perlu dijaga di sini. Harga bahan
    masuk lewat jalur lain (pembelian / jawaban harga), yang punya penjaganya
    sendiri.
    """
    return adapter.ekstrak(instruksi_resep(hari_ini), teks, HasilResep)

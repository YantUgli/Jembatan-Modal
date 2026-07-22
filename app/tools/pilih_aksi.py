"""Tool `pilih_aksi` — router intent untuk kalimat bebas.

Bukan tool-calling generik: ini `ekstrak()` yang sudah ada, dipakai dengan
skema baru (`PilihanAksi`, enum tertutup `AksiRouter`). LLM tetap hanya
mengekstrak (bahasa → data terstruktur); orchestrator yang membaca hasilnya
dan memilih fungsi mana yang dipanggil — aturan #1 tidak tersentuh
(keputusan.md 2026-07-22: "Router intent bahasa-bebas").
"""

from __future__ import annotations

from app.llm.kontrak import AdapterLLM, Gagal
from app.llm.skema import AksiRouter, PilihanAksi, instruksi_router

__all__ = ["pilih_aksi"]


def pilih_aksi(adapter: AdapterLLM, teks: str) -> AksiRouter | None:
    """Klasifikasikan `teks` ke `AksiRouter`, atau `None` bila tak yakin.

    `None` bukan error — itu jalur jujur yang sama dengan `Gagal` di tool lain
    (aturan #2). Pemanggil memperlakukannya sebagai "tidak diketahui" dan jatuh
    ke perilaku default (pencatatan), bukan menebak.
    """
    hasil = adapter.ekstrak(instruksi_router(), teks, PilihanAksi)
    if isinstance(hasil, Gagal):
        return None
    return hasil.data.aksi

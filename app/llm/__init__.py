"""Lapisan LLM — provider-agnostic.

⛔ Jangan pernah memanggil SDK vendor dari luar `app/llm/`. Seluruh dunia luar
bicara lewat `AdapterLLM` (lihat `kontrak.py`).
"""

from app.llm.kontrak import (
    AdapterLLM,
    Ekstraksi,
    Gagal,
    KesalahanSkema,
    Narasi,
    angka_asing,
    angka_huruf,
    bangun,
    skema_json,
)
from app.llm.openai_kompatibel import (
    AdapterOpenAIKompatibel,
    KesalahanProvider,
)
from app.llm.palsu import AdapterPalsu

__all__ = [
    "AdapterLLM",
    "AdapterOpenAIKompatibel",
    "AdapterPalsu",
    "KesalahanProvider",
    "Ekstraksi",
    "Gagal",
    "KesalahanSkema",
    "Narasi",
    "angka_asing",
    "angka_huruf",
    "bangun",
    "skema_json",
]

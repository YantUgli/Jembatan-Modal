"""Konfigurasi aplikasi.

Sengaja tanpa dependensi berat (mis. pydantic-settings) supaya core bisa
diinstal & diuji tanpa lapisan API. Kalau nanti butuh, tinggal diganti.
"""

from __future__ import annotations

import os
from pathlib import Path

# Root repo = folder di atas paket `app/`.
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


def _muat_env() -> None:
    """Baca `.env` di root repo, sekali, tanpa dependensi.

    Variabel lingkungan yang sudah ada **tidak** ditimpa — shell selalu menang
    atas berkas, supaya produksi tidak diam-diam memakai kunci dev.

    Kalau satu kunci muncul dua kali, **yang terakhir menang** — sama seperti
    dotenv pada umumnya, dan sesuai cara orang memakai berkas ini: blok provider
    yang aktif ditaruh/di-uncomment di bawah. Versi pertama fungsi ini memakai
    `setdefault` per baris sehingga yang MENANG justru yang pertama; efeknya
    `base_url` provider lama tercampur `api_key` provider baru — gagal 401 yang
    menuduh kunci, padahal berkasnya yang dibaca terbalik.
    """
    berkas = ROOT_DIR / ".env"
    if not berkas.exists():
        return
    isi: dict[str, str] = {}
    for baris in berkas.read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, nilai = baris.partition("=")
        isi[kunci.strip()] = nilai.strip().strip("'\"")
    for kunci, nilai in isi.items():
        os.environ.setdefault(kunci, nilai)


_muat_env()


def database_url() -> str:
    """URL koneksi database.

    Dev default: SQLite di `data/jembatan.db`. Produksi: set `DATABASE_URL`
    ke PostgreSQL. Skema dirancang agar migrasi ke Postgres mulus.
    """
    env = os.getenv("DATABASE_URL")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(DATA_DIR / 'jembatan.db').as_posix()}"


# ── LLM ─────────────────────────────────────────────────────────────────────
# Ketiga provider yang tersedia (Groq, Qwen, Fireworks) berbicara protokol yang
# sama, jadi berpindah = mengganti tiga baris di `.env`, bukan mengganti kode.

BASE_URL_GROQ = "https://api.groq.com/openai/v1"


def llm_base_url() -> str:
    return os.getenv("LLM_BASE_URL", BASE_URL_GROQ)


def llm_model() -> str:
    return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def llm_api_key() -> str:
    return os.getenv("LLM_API_KEY", "")

"""Periksa sambungan LLM: `pipenv run python -m app.llm.periksa`

Sekali jalan, memakai kunci dari `.env`. Bukan set evaluasi — ini cuma
memastikan kunci, base_url, dan model benar-benar tersambung, dan kedua
metode kontrak berperilaku seperti seharusnya.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app import config
from app.llm.kontrak import Ekstraksi, Gagal
from app.llm.openai_kompatibel import AdapterOpenAIKompatibel, KesalahanProvider


@dataclass
class Transaksi:
    jenis: str
    nominal: Decimal
    tanggal: date
    produk: str | None = None
    qty: Decimal | None = None
    satuan: str | None = None


ACUAN = "Tanggal acuan hari ini: 2026-07-19."


def main() -> int:
    if not config.llm_api_key():
        print("!!  LLM_API_KEY kosong. Salin .env.example jadi .env lalu isi kuncinya.")
        return 1

    print(f"  base_url : {config.llm_base_url()}")
    print(f"  model    : {config.llm_model()}\n")
    adapter = AdapterOpenAIKompatibel.dari_env()

    try:
        # 1. Ekstraksi yang seharusnya berhasil.
        hasil = adapter.ekstrak(
            f"Ambil satu transaksi dari kalimat pemilik warung. {ACUAN}",
            "tadi laku 5 kotak risol, 75rb",
            Transaksi,
        )
        if isinstance(hasil, Ekstraksi):
            print(f"OK  ekstrak  : {hasil.data}")
        else:
            print(f"!!  ekstrak  : gagal — {hasil.alasan}")

        # 2. Kalimat ambigu — yang BENAR di sini adalah `Gagal`, bukan tebakan.
        ragu = adapter.ekstrak(
            f"Ambil satu transaksi dari kalimat pemilik warung. {ACUAN}",
            "tadi ada yang beli tapi lupa berapa",
            Transaksi,
        )
        tanda = "OK " if isinstance(ragu, Gagal) else "!!  (menebak!)"
        print(f"{tanda} ambigu   : {ragu if isinstance(ragu, Gagal) else ragu.data}")

        # 3. Narasi + penjaga aturan #1.
        fakta = {"omzet": Decimal("3533000"), "laba": Decimal("3234000"),
                 "bulan": "Juni 2026"}
        n = adapter.narasikan("Ringkas dalam 2 kalimat untuk pemilik warung.", fakta)
        print(f"\n  narasi   : {n.teks}")
        print(f"{'OK ' if n.aman else '!! '} aman     : {n.aman}"
              f"{'' if n.aman else f' — asing={n.angka_asing} huruf={n.angka_huruf}'}")
    except KesalahanProvider as e:
        print(f"!!  provider : {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

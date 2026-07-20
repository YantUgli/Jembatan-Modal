"""Adapter LLM palsu — deterministik, offline, tanpa API key.

Bukan mainan: inilah adapter yang dipakai seluruh test suite supaya test tetap
cepat, gratis, dan tidak flaky. Ia juga peserta pertama di
`tests/test_llm_kontrak.py` — kalau adapter nyata berperilaku beda dari yang
ini, salah satunya melanggar kontrak.

Jawaban di-skrip lewat konstruktor. Dipanggil di luar skrip → melempar, supaya
test yang diam-diam memanggil LLM lebih banyak dari yang diniatkan ketahuan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.llm.kontrak import (
    Ekstraksi,
    Gagal,
    KesalahanSkema,
    Narasi,
    angka_asing,
    angka_huruf,
    bangun,
)

T = TypeVar("T")


@dataclass
class Panggilan:
    metode: str
    instruksi: str
    muatan: str


class AdapterPalsu:
    """Adapter dengan jawaban terskrip.

    `jawaban_ekstrak` — dict {teks masukan: dict hasil} atau daftar antrean.
      Nilai boleh berupa `Gagal` untuk mensimulasikan penolakan jujur, atau
      string mentah untuk mensimulasikan keluaran rusak (JSON tidak sah).
    `jawaban_narasi` — dict {kunci: teks} atau daftar antrean.
    """

    nama = "palsu"

    def __init__(
        self,
        jawaban_ekstrak: dict[str, Any] | list[Any] | None = None,
        jawaban_narasi: list[str] | None = None,
    ) -> None:
        self._ekstrak = jawaban_ekstrak if jawaban_ekstrak is not None else {}
        self._narasi = list(jawaban_narasi or [])
        self.panggilan: list[Panggilan] = field(default_factory=list)  # type: ignore[assignment]
        self.panggilan = []

    # ── kontrak ──

    def ekstrak(self, instruksi: str, teks: str, skema: type[T]) -> Ekstraksi[T] | Gagal:
        self.panggilan.append(Panggilan("ekstrak", instruksi, teks))

        if isinstance(self._ekstrak, list):
            if not self._ekstrak:
                raise AssertionError("AdapterPalsu: ekstrak() dipanggil di luar skrip")
            jawab = self._ekstrak.pop(0)
        else:
            if teks not in self._ekstrak:
                raise AssertionError(
                    f"AdapterPalsu: tidak ada jawaban terskrip untuk {teks!r}"
                )
            jawab = self._ekstrak[teks]

        if isinstance(jawab, Gagal):
            return jawab

        # String = simulasi keluaran mentah provider (bisa JSON rusak).
        if isinstance(jawab, str):
            mentah = jawab
            try:
                jawab = json.loads(jawab)
            except json.JSONDecodeError as e:
                return Gagal(alasan=f"Keluaran model bukan JSON yang sah: {e}", mentah=mentah)
        else:
            mentah = json.dumps(jawab, default=str, ensure_ascii=False)

        try:
            data = bangun(skema, jawab)
        except KesalahanSkema as e:
            return Gagal(alasan=str(e), mentah=mentah)
        return Ekstraksi(data=data, mentah=mentah)

    def narasikan(self, instruksi: str, fakta: dict) -> Narasi:
        self.panggilan.append(Panggilan("narasikan", instruksi, str(fakta)))
        if not self._narasi:
            raise AssertionError("AdapterPalsu: narasikan() dipanggil di luar skrip")
        teks = self._narasi.pop(0)
        return Narasi(
            teks=teks,
            angka_asing=angka_asing(teks, fakta),
            angka_huruf=angka_huruf(teks),
        )

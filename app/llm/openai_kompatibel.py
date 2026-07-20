"""Adapter untuk provider ber-API OpenAI-compatible.

Satu kelas melayani **Groq, Qwen (DashScope mode kompatibel), Fireworks, dan
siapa pun yang meniru `/chat/completions`** — yang berbeda cuma `base_url` +
`model` + `api_key`. Ganti provider = ganti tiga variabel lingkungan, bukan
ganti kode.

⛔ Tanpa SDK vendor. Sengaja memakai `urllib` dari pustaka standar supaya core
tetap bisa diinstal & diuji tanpa dependensi tambahan — permukaan yang kita
pakai (satu POST JSON) tidak sebanding dengan menyeret SDK penuh.

Jaringan disuntik lewat `transport`, jadi adapter ini bisa ikut suite
konformansi tanpa kartu kredit dan tanpa flakiness. Yang benar-benar butuh
jaringan diberi mark `llm_nyata`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.llm.kontrak import (
    Ekstraksi,
    Gagal,
    KesalahanSkema,
    Narasi,
    angka_asing,
    angka_huruf,
    bangun,
    skema_json,
)

T = TypeVar("T")

# (url, headers, body) → (status, teks). Diganti saat test.
Transport = Callable[[str, dict[str, str], dict[str, Any]], "tuple[int, str]"]

# Kunci sepakat antara prompt & adapter: cara model bilang "saya tidak tahu".
# Aturan #2 butuh jalan keluar yang sah — tanpa ini, model dipaksa menebak.
KUNCI_GAGAL = "_gagal"

# Identitas klien. Bukan kosmetik: lihat catatan di `_panggil`.
PENGENAL = "JembatanModal/0.1"

_DISIPLIN_EKSTRAK = """
Jawab HANYA dengan satu objek JSON, tanpa penjelasan dan tanpa pagar kode.

Objek itu harus cocok dengan skema berikut:
{skema}

Aturan yang tidak boleh dilanggar:
- Jangan menebak. Kalau ada informasi wajib yang tidak disebut pengguna,
  jawab {{"{kunci}": {{"alasan": "...", "yang_kurang": ["nama_field", ...]}}}}.
- Jangan menambah field di luar skema.
- Tanggal selalu format YYYY-MM-DD. Kalau pengguna hanya bilang "kemarin" atau
  "tadi", pakai tanggal acuan yang diberikan; kalau tidak ada acuan, itu
  informasi yang kurang.
- Nominal berupa angka polos tanpa pemisah ribuan dan tanpa "Rp".
  "goceng" = 5000, "75rb" = 75000, "1,5jt" = 1500000.
""".strip()

_DISIPLIN_NARASI = """
Kamu merangkai kalimat, bukan menghitung.

- Setiap angka yang kamu sebut WAJIB sudah ada di data yang diberikan. Dilarang
  menjumlah, mengurangi, menghitung persentase, atau memperkirakan apa pun.
- Tulis angka dengan DIGIT (mis. 3.234.000), jangan dengan huruf
  ("tiga juta") — angka berhuruf akan ditolak sistem.
- Kalau ada yang belum diketahui, katakan belum diketahui. Jangan mengarang.
- Bahasa warung sehari-hari. Hindari istilah akuntansi (debit, kredit, jurnal).
""".strip()


@dataclass
class KesalahanProvider(Exception):
    """Panggilan ke provider gagal secara teknis (jaringan, auth, kuota).

    Sengaja **bukan** `Gagal`: "model bilang datanya kurang" dan "API-nya mati"
    adalah dua peristiwa berbeda, dan menyamakannya membuat kita menyalahkan
    pengguna atas kesalahan infrastruktur.
    """

    status: int
    pesan: str

    def __str__(self) -> str:  # pragma: no cover - representasi saja
        return f"[{self.status}] {self.pesan}"


def transport_urllib(timeout: float = 30.0) -> Transport:
    def kirim(url: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[int, str]:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise KesalahanProvider(0, f"Tidak bisa menghubungi provider: {e.reason}") from e
        except (TimeoutError, OSError) as e:
            # `urlopen` melempar TimeoutError telanjang saat timeout terjadi
            # ketika MEMBACA jawaban (bukan saat menyambung) — tidak terbungkus
            # URLError. Sempat mematikan evaluasi 120 permintaan di tengah
            # jalan dengan stack trace, padahal ini gangguan sesaat.
            raise KesalahanProvider(0, f"Sambungan terputus: {e}") from e

    return kirim


class AdapterOpenAIKompatibel:
    """Adapter `AdapterLLM` untuk endpoint `/chat/completions`."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        *,
        nama: str | None = None,
        transport: Transport | None = None,
        suhu_ekstrak: float = 0.0,
        suhu_narasi: float = 0.4,
        percobaan: int = 3,
        jeda: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.nama = nama or f"{self.base_url}::{model}"
        self._api_key = api_key
        self._kirim = transport or transport_urllib()
        self._suhu_ekstrak = suhu_ekstrak
        self._suhu_narasi = suhu_narasi
        self._percobaan = percobaan
        self._jeda = jeda

    # ── kontrak ──

    def ekstrak(self, instruksi: str, teks: str, skema: type[T]) -> Ekstraksi[T] | Gagal:
        sistem = "\n\n".join(
            [
                instruksi,
                _DISIPLIN_EKSTRAK.format(
                    skema=json.dumps(skema_json(skema), ensure_ascii=False, indent=2),
                    kunci=KUNCI_GAGAL,
                ),
            ]
        )
        isi = self._panggil(
            sistem,
            teks,
            suhu=self._suhu_ekstrak,
            response_format={"type": "json_object"},
        )

        mentah = isi
        try:
            data = json.loads(_lepas_pagar(isi))
        except json.JSONDecodeError as e:
            return Gagal(alasan=f"Keluaran model bukan JSON yang sah: {e}", mentah=mentah)

        if isinstance(data, dict) and KUNCI_GAGAL in data:
            alasan = data[KUNCI_GAGAL]
            if isinstance(alasan, dict):
                return Gagal(
                    alasan=str(alasan.get("alasan", "Model tidak yakin")),
                    yang_kurang=[str(x) for x in alasan.get("yang_kurang", [])],
                    mentah=mentah,
                )
            return Gagal(alasan=str(alasan), mentah=mentah)

        try:
            return Ekstraksi(data=bangun(skema, data), mentah=mentah)
        except KesalahanSkema as e:
            return Gagal(alasan=str(e), mentah=mentah)

    def narasikan(self, instruksi: str, fakta: dict) -> Narasi:
        sistem = "\n\n".join([instruksi, _DISIPLIN_NARASI])
        muatan = json.dumps(fakta, ensure_ascii=False, default=str)
        teks = self._panggil(sistem, muatan, suhu=self._suhu_narasi).strip()
        return Narasi(
            teks=teks,
            angka_asing=angka_asing(teks, fakta),
            angka_huruf=angka_huruf(teks),
        )

    # ── HTTP ──

    def _panggil(
        self,
        sistem: str,
        pengguna: str,
        *,
        suhu: float,
        response_format: dict | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": suhu,
            "messages": [
                {"role": "system", "content": sistem},
                {"role": "user", "content": pengguna},
            ],
        }
        if response_format:
            body["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # Wajib. Groq ada di belakang Cloudflare, dan User-Agent bawaan
            # `Python-urllib/x.y` diblokir mentah-mentah (403 kode 1010) —
            # sebelum permintaan sempat menyentuh API-nya. Terverifikasi
            # 2026-07-19: kunci yang sama lolos via curl, ditolak via urllib.
            "User-Agent": PENGENAL,
        }

        terakhir: KesalahanProvider | None = None
        for percobaan in range(self._percobaan):
            try:
                status, isi = self._kirim(url, headers, body)
            except KesalahanProvider as e:
                if e.status != 0:
                    raise
                terakhir = e  # gangguan jaringan: layak diulang
                status = 0
            else:
                if status == 200:
                    return _isi_pesan(isi)
                terakhir = KesalahanProvider(status, _ringkas(isi))
            # 429 = kuota tier gratis; 5xx = provider goyah; 0 = jaringan.
            # Sisanya (401 kunci salah, 400 permintaan cacat) tidak akan
            # membaik dengan diulang.
            if status not in (0, 429) and status < 500:
                break
            if percobaan < self._percobaan - 1:
                time.sleep(self._jeda * (2**percobaan))
        raise terakhir or KesalahanProvider(0, "Tidak ada jawaban")

    @classmethod
    def dari_env(cls, **kwargs: Any) -> AdapterOpenAIKompatibel:
        """Bangun dari `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`."""
        from app import config

        kunci = config.llm_api_key()
        if not kunci:
            raise KesalahanProvider(0, "LLM_API_KEY belum diisi (lihat .env.example)")
        return cls(config.llm_base_url(), config.llm_model(), kunci, **kwargs)


def _isi_pesan(badan: str) -> str:
    try:
        data = json.loads(badan)
        return data["choices"][0]["message"]["content"] or ""
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise KesalahanProvider(200, f"Bentuk jawaban provider tak dikenali: {e}") from e


def _lepas_pagar(teks: str) -> str:
    """Buang pagar kode ```json … ``` yang kadang tetap muncul."""
    t = teks.strip()
    if not t.startswith("```"):
        return t
    t = t.split("\n", 1)[-1] if "\n" in t else t
    if t.rstrip().endswith("```"):
        t = t.rstrip()[:-3]
    return t.strip()


def _ringkas(badan: str, batas: int = 300) -> str:
    try:
        data = json.loads(badan)
        pesan = data.get("error", {}).get("message")
        if pesan:
            return str(pesan)[:batas]
    except (json.JSONDecodeError, AttributeError):
        pass
    return badan[:batas]

"""Perilaku HTTP adapter OpenAI-compatible.

Konformansi kontraknya diuji di `test_llm_kontrak.py` bersama adapter lain.
Di sini yang diuji hal-hal yang **khas provider sungguhan**: pagar kode,
kuota habis, kunci salah, dan bentuk jawaban yang tak dikenali.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.llm.openai_kompatibel import (
    AdapterOpenAIKompatibel,
    PENGENAL,
    Gagal,
    KesalahanProvider,
)


@dataclass
class Angka:
    nominal: Decimal


def _balas(isi: str) -> str:
    return json.dumps({"choices": [{"message": {"content": isi}}]})


def _adapter(*balasan: tuple[int, str], **kw) -> tuple[AdapterOpenAIKompatibel, list]:
    antre = list(balasan)
    jejak: list = []

    def transport(url, headers, body):
        jejak.append(body)
        return antre.pop(0) if antre else (500, "{}")

    a = AdapterOpenAIKompatibel(
        "https://contoh.invalid/v1", "m", "k", transport=transport, jeda=0, **kw
    )
    return a, jejak


def test_user_agent_dikirim():
    """Groq ada di belakang Cloudflare: User-Agent bawaan `Python-urllib/x.y`
    kena blok 403 kode 1010 sebelum menyentuh API. Terverifikasi 2026-07-19 —
    kunci yang sama lolos via curl, ditolak via urllib. Jangan dihapus."""
    jejak: list = []

    def transport(url, headers, body):
        jejak.append(headers)
        return 200, _balas('{"nominal": 1}')

    a = AdapterOpenAIKompatibel("https://contoh.invalid/v1", "m", "k", transport=transport)
    a.ekstrak("i", "t", Angka)

    ua = jejak[0]["User-Agent"]
    assert ua == PENGENAL
    assert "urllib" not in ua.lower()


def test_pagar_kode_dilepas():
    """Model sering tetap membungkus JSON dengan ```json walau diminta tidak."""
    a, _ = _adapter((200, _balas('```json\n{"nominal": 75000}\n```')))
    hasil = a.ekstrak("i", "t", Angka)
    assert hasil.data.nominal == Decimal("75000")


def test_model_boleh_mengaku_tidak_tahu():
    """Aturan #2 butuh jalan keluar yang sah, kalau tidak model dipaksa menebak."""
    isi = json.dumps({"_gagal": {"alasan": "nominal tak disebut",
                                 "yang_kurang": ["nominal"]}})
    a, _ = _adapter((200, _balas(isi)))
    hasil = a.ekstrak("i", "tadi ada gitu deh", Angka)
    assert isinstance(hasil, Gagal)
    assert hasil.yang_kurang == ["nominal"]


def test_kuota_habis_diulang_lalu_menyerah_dengan_jujur():
    a, jejak = _adapter((429, '{"error":{"message":"rate limit"}}'),
                        (429, '{"error":{"message":"rate limit"}}'),
                        (200, _balas('{"nominal": 1}')))
    assert a.ekstrak("i", "t", Angka).data.nominal == Decimal("1")
    assert len(jejak) == 3


def test_kunci_salah_tidak_diulang():
    """401 tidak akan membaik dengan diulang — mengulangnya cuma membakar kuota."""
    a, jejak = _adapter((401, '{"error":{"message":"Invalid API Key"}}'))
    with pytest.raises(KesalahanProvider) as e:
        a.ekstrak("i", "t", Angka)
    assert len(jejak) == 1
    assert "Invalid API Key" in e.value.pesan


def test_gangguan_provider_bukan_gagal():
    """Membedakan 'datanya kurang' dari 'API-nya mati'. Menyamakan keduanya
    berarti menyalahkan pengguna atas kesalahan infrastruktur."""
    a, _ = _adapter((500, "{}"), (500, "{}"), (500, "{}"))
    with pytest.raises(KesalahanProvider):
        a.ekstrak("i", "t", Angka)


def test_gangguan_jaringan_diulang_bukan_mematikan():
    """Timeout saat MEMBACA jawaban melempar TimeoutError telanjang (bukan
    URLError). Sempat mematikan evaluasi 120 permintaan di tengah jalan."""
    sisa = [KesalahanProvider(0, "Sambungan terputus: timed out")]

    def transport(url, headers, body):
        if sisa:
            raise sisa.pop()
        return 200, _balas('{"nominal": 7}')

    a = AdapterOpenAIKompatibel(
        "https://contoh.invalid/v1", "m", "k", transport=transport, jeda=0
    )
    assert a.ekstrak("i", "t", Angka).data.nominal == Decimal("7")


def test_bentuk_jawaban_asing_dilaporkan_bukan_crash_samar():
    a, _ = _adapter((200, '{"hasil": "bentuk lain"}'))
    with pytest.raises(KesalahanProvider):
        a.ekstrak("i", "t", Angka)


def test_ekstrak_memakai_suhu_nol_dan_minta_json():
    """Ekstraksi harus sedeterministik mungkin; narasi boleh lebih luwes."""
    a, jejak = _adapter((200, _balas('{"nominal": 1}')), (200, _balas("halo")))
    a.ekstrak("i", "t", Angka)
    a.narasikan("i", {})
    assert jejak[0]["temperature"] == 0.0
    assert jejak[0]["response_format"] == {"type": "json_object"}
    assert jejak[1]["temperature"] > 0
    assert "response_format" not in jejak[1]


def test_skema_dikirim_ke_model():
    a, jejak = _adapter((200, _balas('{"nominal": 1}')))
    a.ekstrak("Ambil transaksi.", "t", Angka)
    sistem = jejak[0]["messages"][0]["content"]
    assert "Ambil transaksi." in sistem
    assert "nominal" in sistem


def test_narasi_tetap_dijaga_aturan_satu():
    """Penjaga angka berlaku di adapter nyata, bukan cuma di yang palsu."""
    a, _ = _adapter((200, _balas("Omzetmu 3.533.000, naik 12% dari bulan lalu.")))
    n = a.narasikan("ringkas", {"omzet": Decimal("3533000")})
    assert not n.aman
    assert n.angka_asing == ["12"]

"""Adaptor tempelan teks: pemecahan baris & **keyakinan yang dihitung kode**.

Yang dijaga di sini bukan kualitas ekstraksi (itu urusan `test_llm_ekstraksi.py`),
melainkan dua janji adaptor:

- Setiap baris sumber tetap terwakili — tak ada baris yang hilang diam-diam.
- Keyakinan lahir dari **struktur teks**, bukan dari model. Sebab paling penting:
  baris tanpa tanggal ditandai ragu, karena tanggal yang ditebak memindahkan uang
  antar bulan dan menggeser setiap laporan di atasnya.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.impor import (
    MAKS_BARIS,
    MIN_BARIS_TEMPELAN,
    RAGU,
    YAKIN,
    ParserTeks,
    TerlaluBanyakBaris,
    baris_bersih,
    tampak_tempelan,
    tanggal_disebut,
)
from app.llm.kontrak import Gagal
from app.llm.palsu import AdapterPalsu

HARI_INI = date(2026, 7, 26)


def _pemasukan(nominal: int, tanggal: str, produk: str | None = None) -> dict:
    return {
        "baris": [
            {"jenis": "pemasukan", "nominal": nominal, "tanggal": tanggal, "produk": produk}
        ]
    }


# ── Pemecahan baris ─────────────────────────────────────────────────────────


def test_bullet_dan_penomoran_dibuang():
    muatan = "1. laku risol 75rb\n- beli minyak 38rb\n• bayar gas 22rb\n\n  \n2) setor 50rb"
    assert baris_bersih(muatan) == [
        "laku risol 75rb",
        "beli minyak 38rb",
        "bayar gas 22rb",
        "setor 50rb",
    ]


def test_tempelan_dikenali_dari_jumlah_baris():
    assert not tampak_tempelan("laku risol 75rb")
    assert not tampak_tempelan("laku risol 75rb\nbeli minyak 38rb")  # masih diketik tangan
    assert tampak_tempelan("a 1rb\nb 2rb\nc 3rb")
    assert MIN_BARIS_TEMPELAN == 3


def test_tempelan_terlalu_panjang_ditolak_bukan_dipotong():
    """Memotong di baris ke-N menghilangkan sisanya tanpa pengguna tahu."""
    adapter = AdapterPalsu(jawaban_ekstrak={})
    muatan = "\n".join(f"laku risol {i}rb" for i in range(MAKS_BARIS + 1))
    with pytest.raises(TerlaluBanyakBaris):
        ParserTeks(adapter).parse(muatan, HARI_INI)
    # Tak satu pun panggilan model terjadi — ditolak sebelum biaya keluar.
    assert adapter.panggilan == []


# ── Keyakinan ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "teks",
    [
        "12/6 laku risol 75rb",
        "tgl 3 beli minyak 38rb",
        "5 jan setor 50rb",
        "kemarin laku 90rb",
        "hari ini bayar gas 22rb",
        "senin laku risol 75rb",
        "minggu lalu beli tepung 60rb",
        "12-06-2026 laku 75rb",
    ],
)
def test_penyebutan_waktu_dikenali(teks: str):
    assert tanggal_disebut(teks)


@pytest.mark.parametrize("teks", ["laku risol 75rb", "beli minyak 38rb", "setor 50rb"])
def test_tanpa_penyebutan_waktu(teks: str):
    assert not tanggal_disebut(teks)


def test_baris_bertanggal_yakin_tanpa_catatan():
    teks = "12/6 laku risol 75rb"
    parser = ParserTeks(AdapterPalsu(jawaban_ekstrak={teks: _pemasukan(75_000, "2026-06-12")}))

    draft = parser.parse(teks, HARI_INI)[0]
    assert draft.keyakinan == YAKIN
    assert draft.catatan == ""
    assert not draft.ragu


def test_baris_tanpa_tanggal_ditandai_ragu_dengan_sebab():
    """Sebab dipakai: halaman buku Juni yang ditempel Juli tak boleh diam-diam
    pindah bulan."""
    teks = "laku risol 75rb"
    parser = ParserTeks(
        AdapterPalsu(jawaban_ekstrak={teks: _pemasukan(75_000, HARI_INI.isoformat())})
    )

    draft = parser.parse(teks, HARI_INI)[0]
    assert draft.keyakinan == RAGU
    assert draft.ragu
    assert "tanggal hari ini" in draft.catatan
    assert draft.terbaca  # ragu ≠ tak terbaca


def test_model_tak_punya_slot_untuk_melaporkan_keyakinan():
    """Aturan #1 ditegakkan lewat **bentuk**, bukan lewat kedisiplinan pemanggil.

    Skema ekstraksi tak punya field keyakinan, dan `bangun()` menolak field asing
    — jadi model yang mencoba menilai keyakinannya sendiri ditolak di pintu, bukan
    diabaikan diam-diam di suatu tempat yang bisa lupa mengabaikannya.
    """
    from app.llm.skema import BarisTransaksi, HasilCatat

    assert not hasattr(BarisTransaksi, "keyakinan")
    assert not hasattr(HasilCatat, "keyakinan")

    teks = "laku risol 75rb"
    jawab = _pemasukan(75_000, HARI_INI.isoformat())
    jawab["baris"][0]["keyakinan"] = 0.99  # ← disuntik model
    parser = ParserTeks(AdapterPalsu(jawaban_ekstrak={teks: jawab}))

    draft = parser.parse(teks, HARI_INI)[0]
    assert not draft.terbaca  # ditolak skema, tak jadi calon

    # Dan baris yang sah tetap dinilai kode: tanpa tanggal → ragu.
    bersih = "beli minyak 38rb"
    lain = ParserTeks(
        AdapterPalsu(
            jawaban_ekstrak={
                bersih: {
                    "baris": [
                        {
                            "jenis": "pengeluaran",
                            "nominal": 38_000,
                            "tanggal": HARI_INI.isoformat(),
                        }
                    ]
                }
            }
        )
    )
    assert lain.parse(bersih, HARI_INI)[0].keyakinan == RAGU


# ── Baris yang tak terbaca ──────────────────────────────────────────────────


def test_baris_tak_terbaca_tetap_dibawa_masuk():
    """Judul halaman & baris "jumlah" tidak dibuang: pengguna menempel 3 baris,
    ia berhak melihat 3 baris kembali."""
    baik = "12/6 laku risol 75rb"
    judul = "Catatan Juni"
    parser = ParserTeks(
        AdapterPalsu(
            jawaban_ekstrak={
                judul: Gagal(alasan="tak ada uang", yang_kurang=["nominal"]),
                baik: _pemasukan(75_000, "2026-06-12"),
                "jumlah": {"baris": []},
            }
        )
    )

    draft = parser.parse(f"{judul}\n{baik}\njumlah", HARI_INI)
    assert len(draft) == 3
    assert [d.terbaca for d in draft] == [False, True, False]
    assert draft[0].raw == judul
    assert "Nominalnya tidak terbaca" in draft[0].catatan
    assert draft[0].yang_kurang == ("nominal",)
    # Baris yang ekstraksinya kosong juga mengaku, bukan hilang.
    assert draft[2].raw == "jumlah"


def test_satu_baris_bisa_melahirkan_dua_calon():
    teks = "12/6 laku risol 75rb, beli minyak 38rb"
    parser = ParserTeks(
        AdapterPalsu(
            jawaban_ekstrak={
                teks: {
                    "baris": [
                        {"jenis": "pemasukan", "nominal": 75_000, "tanggal": "2026-06-12"},
                        {"jenis": "pengeluaran", "nominal": 38_000, "tanggal": "2026-06-12"},
                    ]
                }
            }
        )
    )

    draft = parser.parse(teks, HARI_INI)
    assert len(draft) == 2
    assert all(d.raw == teks for d in draft)  # keduanya menunjuk baris sumber yang sama


def test_satu_baris_busuk_tidak_membunuh_yang_sehat():
    """`ekstrak_transaksi` menolak seluruh teks bila penjaga aturan #1 curiga —
    benar untuk satu kalimat chat, merusak untuk satu halaman buku. Per-baris
    membuat kerusakannya lokal."""
    busuk = "laku 5 kotak risol 75rb"  # penjaga menolak 5×75rb
    sehat = "12/6 bayar gas 22rb"
    parser = ParserTeks(
        AdapterPalsu(
            jawaban_ekstrak={
                busuk: {
                    "baris": [
                        {
                            "jenis": "pemasukan",
                            "nominal": 375_000,  # dihitung model
                            "tanggal": "2026-07-26",
                            "qty": 5,
                            "satuan": "kotak",
                            "produk": "risol",
                        }
                    ]
                },
                sehat: {
                    "baris": [
                        {"jenis": "operasional", "nominal": 22_000, "tanggal": "2026-06-12"}
                    ]
                },
            }
        )
    )

    draft = parser.parse(f"{busuk}\n{sehat}", HARI_INI)
    assert len(draft) == 2
    assert not draft[0].terbaca  # ditolak penjaga, tak jadi calon
    assert draft[1].terbaca and draft[1].keyakinan == YAKIN

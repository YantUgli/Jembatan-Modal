"""Suite konformansi adapter LLM — **wajib dilewati setiap provider**.

Ini mekanisme yang membuat "provider-agnostic" tetap benar, bukan sekadar
diklaim. Menambah provider = tulis satu kelas, daftarkan di `ADAPTER`, jalankan
suite ini. Kalau perilakunya beda, salah satunya melanggar kontrak.

Adapter palsu selalu ikut (offline, gratis, deterministik). Provider sungguhan
menyusul di daftar yang sama begitu diimplementasi; yang butuh jaringan diberi
mark `llm_nyata` agar bisa di-skip di CI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from app.llm.openai_kompatibel import KUNCI_GAGAL

from app.llm import (
    AdapterOpenAIKompatibel,
    AdapterPalsu,
    Ekstraksi,
    Gagal,
    KesalahanSkema,
    angka_asing,
    angka_huruf,
    bangun,
    skema_json,
)

INSTRUKSI = "Ambil transaksi dari kalimat pengguna."


# ── Skema contoh: sedekat mungkin dengan kebutuhan `catat_transaksi` ────────


@dataclass
class BarisTransaksi:
    jenis: str
    nominal: Decimal
    tanggal: date
    produk: str | None = None
    qty: Decimal | None = None
    satuan: str | None = None


@dataclass
class HasilCatat:
    baris: list[BarisTransaksi] = field(default_factory=list)


SATU_BARIS = {
    "jenis": "pemasukan",
    "nominal": "75000",
    "tanggal": "2026-06-10",
    "produk": "risol",
    "qty": "5",
    "satuan": "kotak",
}


def _palsu(jawaban=None, narasi=None):
    return AdapterPalsu(jawaban_ekstrak=jawaban, jawaban_narasi=narasi)


def _openai(jawaban=None, narasi=None):
    """Adapter OpenAI-compatible dengan jaringan disuntik.

    Bukan mock dari adapter — ini adapter **sungguhan**, hanya soketnya diganti.
    Seluruh parsing, pelepasan pagar kode, jalur `_gagal`, dan koersi skema yang
    dipakai saat bicara ke Groq dijalankan apa adanya di sini.
    """
    antre = list(narasi or [])

    def transport(url, headers, body):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"].startswith("Bearer ")
        pengguna = body["messages"][-1]["content"]

        if body.get("response_format"):  # ekstrak
            jawab = (jawaban or {}).get(pengguna)
            if jawab is None:
                raise AssertionError(f"tidak ada jawaban terskrip untuk {pengguna!r}")
            if isinstance(jawab, Gagal):
                isi = json.dumps({KUNCI_GAGAL: {"alasan": jawab.alasan,
                                                "yang_kurang": jawab.yang_kurang}})
            elif isinstance(jawab, str):
                isi = jawab  # simulasi keluaran rusak
            else:
                isi = json.dumps(jawab, ensure_ascii=False)
        else:  # narasi
            if not antre:
                raise AssertionError("narasikan() dipanggil di luar skrip")
            isi = antre.pop(0)

        return 200, json.dumps({"choices": [{"message": {"content": isi}}]})

    return AdapterOpenAIKompatibel(
        "https://contoh.invalid/v1", "model-uji", "kunci-uji",
        nama="openai-kompatibel", transport=transport,
    )


# Daftar adapter yang diuji. Provider nyata ditambahkan di sini.
ADAPTER = [
    pytest.param(_palsu, id="palsu"),
    pytest.param(_openai, id="openai-kompatibel"),
]


# ── Kontrak: ekstraksi ──────────────────────────────────────────────────────


@pytest.mark.parametrize("bikin", ADAPTER)
def test_ekstraksi_menghasilkan_instance_skema(bikin):
    a = bikin({"laku 5 risol 75rb": SATU_BARIS})
    hasil = a.ekstrak(INSTRUKSI, "laku 5 risol 75rb", BarisTransaksi)

    assert isinstance(hasil, Ekstraksi)
    assert isinstance(hasil.data, BarisTransaksi)
    # tipe dikoersi, bukan diserahkan mentah sebagai string
    assert hasil.data.nominal == Decimal("75000")
    assert isinstance(hasil.data.nominal, Decimal)
    assert hasil.data.tanggal == date(2026, 6, 10)
    assert hasil.data.qty == Decimal("5")


@pytest.mark.parametrize("bikin", ADAPTER)
def test_field_wajib_hilang_jadi_gagal_bukan_none(bikin):
    """Aturan #2 di lapisan input: jangan isi None diam-diam."""
    kurang = {k: v for k, v in SATU_BARIS.items() if k != "nominal"}
    a = bikin({"apa ya": kurang})

    hasil = a.ekstrak(INSTRUKSI, "apa ya", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert "nominal" in hasil.alasan


@pytest.mark.parametrize("bikin", ADAPTER)
def test_field_asing_ditolak(bikin):
    """Model mengarang field = sinyal prompt meleset. Jangan diabaikan diam-diam."""
    a = bikin({"x": {**SATU_BARIS, "catatan_tambahan": "halo"}})

    hasil = a.ekstrak(INSTRUKSI, "x", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert "catatan_tambahan" in hasil.alasan


@pytest.mark.parametrize("bikin", ADAPTER)
def test_tipe_salah_jadi_gagal(bikin):
    a = bikin({"x": {**SATU_BARIS, "nominal": "tujuh puluh lima ribu"}})

    hasil = a.ekstrak(INSTRUKSI, "x", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert "nominal" in hasil.alasan


@pytest.mark.parametrize("bikin", ADAPTER)
def test_tanggal_ambigu_ditolak(bikin):
    """'12/03/2026' itu dd/mm atau mm/dd? Menebaknya = mengarang tanggal."""
    a = bikin({"x": {**SATU_BARIS, "tanggal": "12/03/2026"}})

    hasil = a.ekstrak(INSTRUKSI, "x", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert "tanggal" in hasil.alasan


@pytest.mark.parametrize("bikin", ADAPTER)
def test_keluaran_rusak_jadi_gagal_bukan_lempar(bikin):
    """Provider kadang mengembalikan JSON tidak sah. Itu jalur normal, bukan crash."""
    a = bikin({"x": "{ini bukan json"})

    hasil = a.ekstrak(INSTRUKSI, "x", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert hasil.mentah == "{ini bukan json"


@pytest.mark.parametrize("bikin", ADAPTER)
def test_kalimat_ambigu_boleh_gagal_dengan_alasan(bikin):
    a = bikin({"tadi ada gitu deh": Gagal(alasan="Kalimat tidak menyebut nominal",
                                          yang_kurang=["nominal"])})

    hasil = a.ekstrak(INSTRUKSI, "tadi ada gitu deh", BarisTransaksi)

    assert isinstance(hasil, Gagal)
    assert hasil.yang_kurang == ["nominal"]


@pytest.mark.parametrize("bikin", ADAPTER)
def test_multi_transaksi_dalam_satu_pesan(bikin):
    a = bikin({"laku 5 risol 75rb, terus beli minyak 38rb": {"baris": [
        SATU_BARIS,
        {"jenis": "pengeluaran", "nominal": "38000", "tanggal": "2026-06-10",
         "produk": "minyak"},
    ]}})

    hasil = a.ekstrak(INSTRUKSI, "laku 5 risol 75rb, terus beli minyak 38rb", HasilCatat)

    assert isinstance(hasil, Ekstraksi)
    assert len(hasil.data.baris) == 2
    assert hasil.data.baris[1].nominal == Decimal("38000")
    assert hasil.data.baris[1].qty is None  # opsional, boleh kosong


@pytest.mark.parametrize("bikin", ADAPTER)
def test_mentah_selalu_terbawa_untuk_penelusuran(bikin):
    a = bikin({"x": SATU_BARIS})
    hasil = a.ekstrak(INSTRUKSI, "x", BarisTransaksi)
    assert "risol" in hasil.mentah


# ── Kontrak: narasi (aturan #1) ─────────────────────────────────────────────


@pytest.mark.parametrize("bikin", ADAPTER)
def test_narasi_yang_hanya_memakai_angka_fakta_dianggap_aman(bikin):
    fakta = {"omzet": Decimal("3533000"), "laba": Decimal("3234000")}
    a = bikin(narasi=["Omzetmu 3.533.000 dan labanya 3.234.000."])

    n = a.narasikan("ringkas", fakta)

    assert n.aman
    assert n.angka_asing == []


@pytest.mark.parametrize("bikin", ADAPTER)
def test_narasi_yang_melahirkan_angka_ditandai(bikin):
    """Inti aturan #1: LLM boleh merangkai kalimat, tidak boleh melahirkan angka."""
    fakta = {"omzet": Decimal("3533000")}
    a = bikin(narasi=["Omzetmu 3.533.000, naik 12% dari bulan lalu."])

    n = a.narasikan("ringkas", fakta)

    assert not n.aman
    assert "12" in n.angka_asing


@pytest.mark.parametrize("bikin", ADAPTER)
def test_narasi_tanpa_angka_selalu_aman(bikin):
    a = bikin(narasi=["Catatanmu bulan ini sudah rapi."])
    assert a.narasikan("ringkas", {}).aman


@pytest.mark.parametrize("bikin", ADAPTER)
def test_narasi_berangka_huruf_tidak_dianggap_aman(bikin):
    """Lubang yang sempat terlewat: 'tiga juta' tak punya digit untuk dicocokkan,
    jadi kalau dibiarkan, seluruh penjaga angka bisa dilangkahi begitu saja."""
    fakta = {"laba": Decimal("3234000")}
    a = bikin(narasi=["Labamu tiga juta dua ratus ribu."])

    n = a.narasikan("ringkas", fakta)

    assert not n.aman
    assert n.angka_asing == []        # memang tak ada digit
    assert "juta" in n.angka_huruf    # tapi ada klaim angka yang tak terverifikasi


@pytest.mark.parametrize("bikin", ADAPTER)
def test_satuan_setelah_digit_tidak_ikut_ditandai(bikin):
    """'3,5 juta' sudah diperiksa lewat digitnya — jangan ditandai dua kali."""
    fakta = {"laba": Decimal("3.5")}
    a = bikin(narasi=["Labamu 3,5 juta."])

    n = a.narasikan("ringkas", fakta)

    assert n.angka_huruf == []
    assert n.aman


# ── Detail penjaga angka ────────────────────────────────────────────────────


def test_angka_asing_menyamakan_bentuk_pemisah():
    fakta = {"nominal": Decimal("15000.00")}
    assert angka_asing("harganya 15.000", fakta) == []
    assert angka_asing("harganya 15,000", fakta) == []
    assert angka_asing("harganya 15000", fakta) == []
    assert angka_asing("harganya 16.000", fakta) == ["16.000"]


def test_angka_asing_menelusuri_struktur_bersarang():
    fakta = {"produk": [{"nama": "risol", "hpp": Decimal("4050")}]}
    assert angka_asing("HPP risol 4.050", fakta) == []
    assert angka_asing("HPP risol 4.050 dan kroket 3.281", fakta) == ["3.281"]


def test_angka_asing_menerima_tanggal_dari_fakta():
    assert angka_asing("per 2026-06-01", {"tanggal": date(2026, 6, 1)}) == []


def test_angka_asing_mengabaikan_boolean():
    """True/False jangan diperlakukan sebagai angka 1/0."""
    assert angka_asing("ada 1 catatan", {"lengkap": True}) == ["1"]


def test_angka_huruf_ketat_dan_batasnya_disadari():
    """Sikapnya sengaja KETAT: menahan kalimat benar lebih murah daripada
    meloloskan satu angka karangan ke laporan yang dibaca penyalur.

    Konsekuensinya "setengah kilo" ikut ditandai walau takarannya ada di fakta.
    Itu ditebus di prompt narasi (wajib memakai digit), bukan dengan melonggarkan
    penjaganya."""
    assert angka_huruf("Sudah rapi catatanmu.") == []
    assert angka_huruf("Naik 12 persen.") == []
    assert "setengah" in angka_huruf("Beli setengah kilo tepung.")
    assert angka_huruf("Untungmu 3,5 juta.") == []


# ── skema_json (untuk provider ber-structured-output) ──────────────────────


def test_skema_json_menandai_field_wajib():
    s = skema_json(BarisTransaksi)
    assert s["required"] == ["jenis", "nominal", "tanggal"]
    assert s["additionalProperties"] is False
    assert s["properties"]["nominal"] == {"type": "number"}
    assert s["properties"]["tanggal"] == {"type": "string", "format": "date"}


def test_skema_json_bersarang():
    s = skema_json(HasilCatat)
    assert s["properties"]["baris"]["type"] == "array"
    assert s["properties"]["baris"]["items"]["properties"]["produk"] == {"type": "string"}


# ── bangun() dipakai langsung oleh adapter mana pun ────────────────────────


def test_string_kosong_jadi_none_bukan_data_palsu():
    """qwen3.6-flash mengisi `satuan: ""` ketimbang menghilangkan field-nya.
    '' di kolom satuan tampak seperti data padahal bukan — dan setiap
    pemeriksaan "belum diketahui" akan melewatinya."""
    hasil = bangun(BarisTransaksi, {**SATU_BARIS, "satuan": "  ", "produk": ""})
    assert hasil.satuan is None
    assert hasil.produk is None


def test_string_kosong_di_field_wajib_ditolak():
    with pytest.raises(KesalahanSkema):
        bangun(BarisTransaksi, {**SATU_BARIS, "jenis": ""})


def test_bangun_menolak_bukan_objek():
    with pytest.raises(KesalahanSkema):
        bangun(BarisTransaksi, ["bukan", "objek"])  # type: ignore[arg-type]


def test_bangun_memakai_default_saat_field_opsional_absen():
    hasil = bangun(BarisTransaksi, {"jenis": "pemasukan", "nominal": 1000,
                                    "tanggal": "2026-06-01"})
    assert hasil.produk is None
    assert hasil.qty is None


# ── Disiplin adapter palsu ─────────────────────────────────────────────────


def test_palsu_melempar_bila_dipanggil_di_luar_skrip():
    a = _palsu({"x": SATU_BARIS})
    with pytest.raises(AssertionError):
        a.ekstrak(INSTRUKSI, "kalimat yang tidak diskrip", BarisTransaksi)


def test_palsu_mencatat_panggilan():
    a = _palsu({"x": SATU_BARIS}, narasi=["oke"])
    a.ekstrak(INSTRUKSI, "x", BarisTransaksi)
    a.narasikan("ringkas", {})
    assert [p.metode for p in a.panggilan] == ["ekstrak", "narasikan"]

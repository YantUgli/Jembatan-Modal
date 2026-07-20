"""Kontrak adapter LLM — provider-agnostic (02-arsitektur.md).

**Adapter ini sengaja sempit, dan kesempitannya dibayar oleh aturan #1.**

Yang biasanya membuat adapter LLM sulit ditukar antar-provider adalah format
tool-calling, loop agentik, dan bentuk streaming — di situlah vendor paling
berbeda. Produk ini tidak memakai satu pun dari ketiganya: LLM tidak pernah
menghitung dan tidak pernah memutuskan langkah. Orchestrator (kode kita) yang
memilih tool. Maka permukaan yang perlu ditiru saat ganti provider tinggal dua:

    ekstrak()    — bahasa natural  → data terstruktur
    narasikan()  — angka dari service → kalimat

Dua aturan keras yang ditegakkan **di lapisan ini**, bukan di tiap adapter:

1. **`ekstrak()` tidak pernah menebak.** Hasilnya `Ekstraksi` yang sah menurut
   skema, atau `Gagal` berisi apa yang kurang. Field wajib yang hilang tidak
   pernah diisi None diam-diam (aturan #2 di lapisan input).

2. **`narasikan()` memeriksa keluarannya sendiri.** Setiap angka di kalimat yang
   tidak ada di `fakta` ditandai sebagai `angka_asing`. Ini mengubah aturan #1
   dari harapan jadi mekanisme — LLM boleh merangkai kalimat, tidak boleh
   melahirkan angka.

Slot yang **sengaja belum diimplementasi** (pola yang sama dengan
`labor_time`/`overhead` di model biaya): `baca_gambar()` untuk impor foto buku
tulis (pilar 2). Kontraknya menyediakan tempat; kodenya menyusul saat pilar 2
digarap. ⛔ Jangan menulis kalkulasi atau tool di atas slot itu sekarang.
"""

from __future__ import annotations

import dataclasses
import enum
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Generic, Protocol, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


class KesalahanSkema(ValueError):
    """Data dari LLM tidak sesuai skema yang diminta."""


# ── Hasil ───────────────────────────────────────────────────────────────────


@dataclass
class Ekstraksi(Generic[T]):
    data: T
    mentah: str = ""              # keluaran apa adanya, untuk penelusuran
    keyakinan: float | None = None  # 0..1 bila provider menyediakannya


@dataclass
class Gagal:
    """Ekstraksi tidak bisa dipertanggungjawabkan.

    Bukan error teknis semata — ini juga jalur sah saat kalimat pengguna memang
    ambigu. Lebih baik bertanya balik daripada menebak (aturan #2).
    """

    alasan: str
    yang_kurang: list[str] = field(default_factory=list)
    mentah: str | None = None


@dataclass
class Narasi:
    teks: str
    # Angka (dalam digit) yang muncul di `teks` tapi tidak ada di `fakta`.
    angka_asing: list[str] = field(default_factory=list)
    # Bilangan yang ditulis dengan HURUF ("tiga juta") — tidak bisa diverifikasi
    # terhadap fakta, jadi diperlakukan sama berbahayanya dengan angka asing.
    angka_huruf: list[str] = field(default_factory=list)

    @property
    def aman(self) -> bool:
        """Tidak ada satu pun klaim angka yang tak berasal dari `fakta`.

        Tidak aman = narasi **tidak boleh ditampilkan apa adanya** (aturan #1).
        """
        return not self.angka_asing and not self.angka_huruf


# ── Protokol adapter ────────────────────────────────────────────────────────


class AdapterLLM(Protocol):
    """Permukaan yang wajib ditiru setiap provider.

    Implementasi apa pun harus lulus `tests/test_llm_kontrak.py` — itulah yang
    menjaga "agnostic" tetap benar saat provider kedua ditambahkan.
    """

    nama: str

    def ekstrak(
        self, instruksi: str, teks: str, skema: type[T]
    ) -> Ekstraksi[T] | Gagal:
        """Ubah bahasa natural jadi instance `skema`, atau akui gagal."""
        ...

    def narasikan(self, instruksi: str, fakta: dict) -> Narasi:
        """Rangkai kalimat dari angka yang SUDAH dihitung service."""
        ...


# ── Validasi & koersi skema ────────────────────────────────────────────────


def _opsional(tipe: Any) -> tuple[bool, Any]:
    """Bongkar `X | None` jadi (True, X)."""
    if get_origin(tipe) is Union:
        args = [a for a in get_args(tipe) if a is not type(None)]
        if len(args) != len(get_args(tipe)):
            return True, args[0] if len(args) == 1 else Union[tuple(args)]
    return False, tipe


def _koersi(nilai: Any, tipe: Any, jalur: str) -> Any:
    boleh_kosong, tipe = _opsional(tipe)
    if nilai is None:
        if boleh_kosong:
            return None
        raise KesalahanSkema(f"{jalur}: wajib diisi")

    # String kosong = tidak ada isinya, bukan isi yang kebetulan pendek.
    # Model kerap mengisi `satuan: ""` ketimbang menghilangkan field-nya
    # (terpantau pada qwen3.6-flash). Kalau dibiarkan, kolomnya berisi ''
    # alih-alih NULL — di database itu tampak seperti data padahal bukan, dan
    # setiap pemeriksaan "belum diketahui" akan melewatinya diam-diam.
    if isinstance(nilai, str) and not nilai.strip():
        if boleh_kosong:
            return None
        raise KesalahanSkema(f"{jalur}: wajib diisi")

    asal = get_origin(tipe)
    if asal is list:
        if not isinstance(nilai, list):
            raise KesalahanSkema(f"{jalur}: harus berupa daftar")
        (dalam,) = get_args(tipe)
        return [_koersi(v, dalam, f"{jalur}[{i}]") for i, v in enumerate(nilai)]

    if dataclasses.is_dataclass(tipe):
        if not isinstance(nilai, dict):
            raise KesalahanSkema(f"{jalur}: harus berupa objek")
        return bangun(tipe, nilai, jalur=jalur)

    if isinstance(tipe, type) and issubclass(tipe, enum.Enum):
        try:
            return tipe(nilai)
        except ValueError as e:
            pilihan = ", ".join(x.value for x in tipe)
            raise KesalahanSkema(f"{jalur}: '{nilai}' bukan salah satu dari {pilihan}") from e

    if tipe is Decimal:
        try:
            return Decimal(str(nilai))
        except (InvalidOperation, ValueError) as e:
            raise KesalahanSkema(f"{jalur}: '{nilai}' bukan angka") from e

    if tipe is date:
        if isinstance(nilai, date):
            return nilai
        try:
            # ISO saja — menebak "12/03/2026" itu dd/mm atau mm/dd sama dengan
            # mengarang tanggal.
            return date.fromisoformat(str(nilai))
        except ValueError as e:
            raise KesalahanSkema(f"{jalur}: '{nilai}' bukan tanggal ISO (YYYY-MM-DD)") from e

    if tipe is bool:
        if isinstance(nilai, bool):
            return nilai
        raise KesalahanSkema(f"{jalur}: harus true/false")

    if tipe is int:
        if isinstance(nilai, bool) or not isinstance(nilai, (int, float, str)):
            raise KesalahanSkema(f"{jalur}: harus bilangan bulat")
        try:
            return int(nilai)
        except ValueError as e:
            raise KesalahanSkema(f"{jalur}: '{nilai}' bukan bilangan bulat") from e

    if tipe is float:
        try:
            return float(nilai)
        except (TypeError, ValueError) as e:
            raise KesalahanSkema(f"{jalur}: '{nilai}' bukan angka") from e

    if tipe is str:
        if not isinstance(nilai, str):
            raise KesalahanSkema(f"{jalur}: harus teks")
        return nilai

    return nilai


def bangun(skema: type[T], data: dict, jalur: str = "") -> T:
    """Bangun instance `skema` dari dict keluaran LLM.

    Field asing **ditolak**, bukan diabaikan diam-diam: kalau model mengarang
    field, itu sinyal promptnya meleset dan kita ingin tahu.
    """
    if not dataclasses.is_dataclass(skema):
        raise KesalahanSkema(f"{skema} bukan dataclass")
    if not isinstance(data, dict):
        raise KesalahanSkema(f"{jalur or 'akar'}: harus berupa objek")

    petunjuk = get_type_hints(skema)
    dikenal = {f.name for f in dataclasses.fields(skema)}
    asing = set(data) - dikenal
    if asing:
        raise KesalahanSkema(
            f"{jalur or 'akar'}: field tidak dikenal: {', '.join(sorted(asing))}"
        )

    nilai = {}
    for f in dataclasses.fields(skema):
        sub = f"{jalur}.{f.name}" if jalur else f.name
        if f.name in data:
            nilai[f.name] = _koersi(data[f.name], petunjuk[f.name], sub)
        elif f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            continue
        else:
            nilai[f.name] = _koersi(None, petunjuk[f.name], sub)
    return skema(**nilai)


def skema_json(skema: type) -> dict:
    """JSON Schema dari dataclass — untuk provider yang mendukung structured
    output (decoding dibatasi skema). Provider yang tidak mendukung boleh
    mengabaikannya; jaminan kesahihan tetap datang dari `bangun()`."""
    sifat: dict[str, Any] = {}
    wajib: list[str] = []
    petunjuk = get_type_hints(skema)
    for f in dataclasses.fields(skema):
        tipe = petunjuk[f.name]
        boleh_kosong, inti = _opsional(tipe)
        sifat[f.name] = _json_tipe(inti)
        if not boleh_kosong and f.default is dataclasses.MISSING and (
            f.default_factory is dataclasses.MISSING  # type: ignore[misc]
        ):
            wajib.append(f.name)
    return {
        "type": "object",
        "properties": sifat,
        "required": wajib,
        "additionalProperties": False,
    }


def _json_tipe(tipe: Any) -> dict:
    if get_origin(tipe) is list:
        (dalam,) = get_args(tipe)
        return {"type": "array", "items": _json_tipe(dalam)}
    if dataclasses.is_dataclass(tipe):
        return skema_json(tipe)
    if isinstance(tipe, type) and issubclass(tipe, enum.Enum):
        return {"type": "string", "enum": [x.value for x in tipe]}
    if tipe is Decimal or tipe is float:
        return {"type": "number"}
    if tipe is int:
        return {"type": "integer"}
    if tipe is bool:
        return {"type": "boolean"}
    if tipe is date:
        return {"type": "string", "format": "date"}
    return {"type": "string"}


# ── Penjaga aturan #1: narasi tidak boleh melahirkan angka ──────────────────

_ANGKA = re.compile(r"\d[\d.,]*")


def _normalkan(teks: str) -> str:
    """Samakan bentuk angka: '15.000' / '15,000' / '15000' → '15000'."""
    return re.sub(r"[.,]", "", teks).lstrip("0") or "0"


def _angka_di(nilai: Any, keranjang: set[str]) -> None:
    if isinstance(nilai, dict):
        for v in nilai.values():
            _angka_di(v, keranjang)
    elif isinstance(nilai, (list, tuple, set)):
        for v in nilai:
            _angka_di(v, keranjang)
    elif isinstance(nilai, bool):
        return
    elif isinstance(nilai, (int, float, Decimal)):
        teks = f"{nilai:f}" if isinstance(nilai, (Decimal, float)) else str(nilai)
        keranjang.add(_normalkan(teks))
        # 10950.00 juga sah ditulis "10950"
        if "." in teks:
            keranjang.add(_normalkan(teks.split(".")[0]))
    elif isinstance(nilai, str):
        for m in _ANGKA.findall(nilai):
            keranjang.add(_normalkan(m))
    elif isinstance(nilai, date):
        keranjang.add(_normalkan(nilai.isoformat()))
        for bagian in nilai.isoformat().split("-"):
            keranjang.add(_normalkan(bagian))


# Bilangan yang ditulis dengan huruf tidak bisa dicocokkan ke `fakta` — dan
# diam-diam meloloskannya membuat seluruh penjaga ini bocor ("labamu tiga juta").
# Kita tidak mencoba mengurai angka Indonesia jadi bilangan; itu pekerjaan yang
# error-prone. Kita cuma MENOLAK-nya, dan prompt narasi mewajibkan digit.
_KATA_BILANGAN = {
    "nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
    "sembilan", "sepuluh", "sebelas", "belas", "puluh", "seratus", "ratus",
    "seribu", "ribu", "sejuta", "juta", "miliar", "milyar", "triliun",
    "setengah", "seperempat", "separuh",
}
_KATA = re.compile(r"[A-Za-zÀ-ÿ]+")


def angka_huruf(teks: str) -> list[str]:
    """Bilangan yang ditulis dengan huruf, tanpa digit di dekatnya.

    "3,5 juta" lolos (digitnya diperiksa `angka_asing`); "tiga juta" ditandai.
    """
    hasil: list[str] = []
    token = list(_KATA.finditer(teks))
    for m in token:
        kata = m.group(0).casefold()
        if kata not in _KATA_BILANGAN:
            continue
        # Ada digit tepat sebelum kata satuan? ("3,5 juta") → sudah terperiksa.
        sebelum = teks[max(0, m.start() - 12) : m.start()]
        if re.search(r"\d[\d.,]*\s*$", sebelum):
            continue
        if kata not in hasil:
            hasil.append(kata)
    return hasil


def angka_asing(teks: str, fakta: dict) -> list[str]:
    """Angka di `teks` yang tidak berasal dari `fakta`.

    Dipakai untuk menolak narasi yang mengarang angka. Sengaja **ketat**: lebih
    baik menahan kalimat yang sebenarnya benar daripada meloloskan satu angka
    karangan ke laporan yang dibaca penyalur.
    """
    dikenal: set[str] = set()
    _angka_di(fakta, dikenal)
    hasil: list[str] = []
    for m in _ANGKA.findall(teks):
        if _normalkan(m) not in dikenal and m not in hasil:
            hasil.append(m)
    return hasil

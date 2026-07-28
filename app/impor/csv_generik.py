"""Adaptor impor #2 (parsial) — unggah berkas CSV generik (§5 B3 rencana eksekusi).

Sengaja berhenti di **struktur**, bukan sampai `BarisDraft`. Membaca CSV
mentah (encoding, pemisah kolom, baris header) tidak butuh tahu formatnya;
memetakan kolom ke `BarisTransaksi` justru butuh — dan pemetaan itu beda per
sumber (rekening koran bank, ekspor QRIS/e-wallet, CSV pembukuan). Memaksakan
pemetaan dari asumsi bentuk berkas berisiko rework total begitu fixture asli
(A3) ternyata beda bentuknya — lihat `docs/02-arsitektur.md` (pemetaan kolom
lewat LLM, bukan aturan hardcode per-platform) dan rencana eksekusi §5.

Yang dibangun di sini: `baca_csv_generik` mengubah berkas mentah jadi baris
tabel yang sudah rapi (header terdeteksi, tiap sel bisa dibaca) — siap
dipetakan begitu `petakan_baris_generik` (stub) diimplementasikan.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

__all__ = [
    "EKSTENSI_DIIZINKAN",
    "UKURAN_MAKS_BYTES",
    "BerkasTidakValid",
    "HasilBacaCsv",
    "baca_csv_generik",
    "petakan_baris_generik",
]

EKSTENSI_DIIZINKAN = (".csv",)
# 5 MB cukup lapang untuk pembukuan warung/rekening koran bulanan; berkas lebih
# besar dari ini nyaris pasti bukan satu unggahan yang wajar untuk ditinjau di HP.
UKURAN_MAKS_BYTES = 5 * 1024 * 1024

# Dicoba berurutan. `utf-8-sig` lebih dulu supaya BOM Excel/Windows tidak ikut
# terbaca sebagai bagian header kolom pertama. `cp1252` menangkap ekspor
# Windows lama (mis. rekening koran) yang bukan UTF-8.
_ENCODING_DICOBA = ("utf-8-sig", "utf-8", "cp1252")

_PEMISAH_DICOBA = ",;\t|"


class BerkasTidakValid(ValueError):
    """Berkas ditolak sebelum diproses: ekstensi, ukuran, atau isi kosong.

    Sengaja subclass `ValueError` yang jelas maknanya, bukan biarkan
    `UnicodeDecodeError`/`csv.Error` mentah bocor ke pemanggil — jalur unggah
    butuh alasan yang bisa ditampilkan ke pengguna, bukan traceback.
    """


@dataclass(frozen=True)
class HasilBacaCsv:
    """CSV mentah yang sudah rapi — belum jadi `BarisDraft` (lihat docstring modul)."""

    header: list[str]
    baris: list[dict[str, str]]
    delimiter: str
    encoding: str
    header_terdeteksi: bool = field(default=True)


def _decode(data: bytes) -> tuple[str, str]:
    """Bytes → (teks, encoding dipakai). Tak pernah gagal: `latin-1` di akhir
    daftar bisa mendekode byte apa pun, jadi selalu ada hasil — kalaupun
    tebakannya meleset, itu lebih baik daripada baris impor menghentikan
    seluruh proses unggah karena satu karakter aneh.
    """
    for enc in _ENCODING_DICOBA:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1"), "latin-1"


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=_PEMISAH_DICOBA).delimiter
    except csv.Error:
        # Fallback: pemisah yang paling konsisten jumlahnya di beberapa baris
        # pertama — lebih defensif daripada memaksakan koma begitu saja.
        baris_contoh = sample.splitlines()[:5] or [sample]
        hitung = {p: [b.count(p) for b in baris_contoh] for p in _PEMISAH_DICOBA}
        kandidat = [p for p, jml in hitung.items() if jml and jml[0] > 0 and len(set(jml)) == 1]
        return kandidat[0] if kandidat else ","


def _sniff_header(sample: str, delimiter: str) -> bool:
    try:
        return csv.Sniffer().has_header(sample)
    except csv.Error:
        # Tak bisa disimpulkan dari bentuknya → asumsikan ada header. Rekening
        # koran/CSV pembukuan hampir selalu berkepala kolom; salah asumsi di
        # sini cuma membuat baris pertama tampak sebagai nama kolom yang aneh,
        # bukan kehilangan satu baris data secara diam-diam.
        return True


def baca_csv_generik(nama_berkas: str, data: bytes) -> HasilBacaCsv:
    """Berkas CSV mentah → tabel rapi (header + baris sebagai dict).

    Validasi (§5 B3): ekstensi, ukuran, isi tidak kosong — gagal di sini
    berarti `BerkasTidakValid` dengan alasan yang bisa ditampilkan, bukan
    exception generik dari lapisan `csv`/`codecs`.
    """
    if not nama_berkas.lower().endswith(EKSTENSI_DIIZINKAN):
        raise BerkasTidakValid(
            f"Tipe berkas tidak didukung — hanya {', '.join(EKSTENSI_DIIZINKAN)}."
        )
    if not data:
        raise BerkasTidakValid("Berkas kosong.")
    if len(data) > UKURAN_MAKS_BYTES:
        maks_mb = UKURAN_MAKS_BYTES // (1024 * 1024)
        raise BerkasTidakValid(f"Berkas terlalu besar — maksimal {maks_mb} MB.")

    teks, encoding = _decode(data)
    baris_mentah = [b for b in teks.splitlines() if b.strip()]
    if not baris_mentah:
        raise BerkasTidakValid("Berkas tidak berisi baris apa pun.")

    contoh = "\n".join(baris_mentah[:10])
    delimiter = _sniff_delimiter(contoh)
    ada_header = _sniff_header(contoh, delimiter)

    reader = csv.reader(io.StringIO(teks), delimiter=delimiter)
    grid = [row for row in reader if any(cell.strip() for cell in row)]
    if not grid:
        raise BerkasTidakValid("Berkas tidak berisi baris apa pun.")

    lebar = max(len(row) for row in grid)
    if ada_header:
        header = [h.strip() or f"kolom_{i + 1}" for i, h in enumerate(grid[0])]
        header += [f"kolom_{i + 1}" for i in range(len(header), lebar)]
        sisa = grid[1:]
    else:
        header = [f"kolom_{i + 1}" for i in range(lebar)]
        sisa = grid

    baris = [
        {header[i]: (row[i].strip() if i < len(row) else "") for i in range(lebar)} for row in sisa
    ]
    return HasilBacaCsv(
        header=header,
        baris=baris,
        delimiter=delimiter,
        encoding=encoding,
        header_terdeteksi=ada_header,
    )


def petakan_baris_generik(baris: dict[str, str]) -> None:
    """Pemetaan kolom → `BarisTransaksi`. **Belum diimplementasikan.**

    # TODO: butuh fixture A3 (contoh berkas asli per format — rekening koran
    # bank, ekspor QRIS/e-wallet, CSV pembukuan, foto tulis tangan) sebelum ini
    # ditulis. `docs/02-arsitektur.md` membayangkan pemetaan lewat LLM (kolom
    # bebas → skema kita), bukan aturan hardcode per-platform — tapi menulis
    # itu pun dari asumsi bentuk berkas berisiko rework total begitu contoh
    # asli ternyata beda. Lihat rencana eksekusi §5 B3 dan §8 (A3).
    """
    raise NotImplementedError(
        "Pemetaan kolom CSV ke transaksi belum diimplementasikan — menunggu "
        "fixture A3 (contoh berkas asli per format)."
    )

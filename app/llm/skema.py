"""Skema ekstraksi — kontrak antara bahasa pengguna dan database.

Yang penting di sini bukan bentuk dataclass-nya, melainkan **`jenis` bertipe
`JenisTransaksi`, bukan `str`**. Pada uji sambungan pertama Groq mengembalikan
`jenis="penjualan"` — kosakata yang masuk akal bagi model tapi tidak pernah
cocok saat difilter. Dengan Enum, `bangun()` menolaknya dan menyebutkan pilihan
yang sah; kita tidak bergantung pada prompt untuk menjaga kosakata.

Enum-nya dipakai bersama model DB (`app/models/base.py`) — sengaja bukan salinan,
supaya menambah jenis transaksi tidak bisa lupa merambat ke lapisan ekstraksi.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.base import JenisTransaksi

__all__ = [
    "AksiKoreksi",
    "BarisTransaksi",
    "HasilCatat",
    "JenisTransaksi",
    "Koreksi",
    "instruksi_catat",
    "instruksi_koreksi",
]


@dataclass
class BarisTransaksi:
    """Satu peristiwa uang. `produk`/`qty`/`satuan` opsional — banyak kalimat
    warung memang tidak menyebutnya ("hari ini dapat 300rb")."""

    jenis: JenisTransaksi
    nominal: Decimal
    tanggal: date
    produk: str | None = None
    qty: Decimal | None = None
    satuan: str | None = None


@dataclass
class HasilCatat:
    """Satu kalimat bisa memuat beberapa transaksi ("laku 75rb, beli minyak 38rb")."""

    baris: list[BarisTransaksi] = field(default_factory=list)


_INSTRUKSI = """
Kamu membaca catatan lisan pemilik warung Indonesia dan mengubahnya jadi
transaksi. Tanggal acuan hari ini: {hari_ini}.

Arti setiap `jenis`:
- pemasukan   : uang masuk dari menjual barang/jasa.
- pengeluaran : belanja bahan atau barang dagangan (yang akan dijual lagi).
- operasional : biaya menjalankan usaha yang bukan barang dagangan.
                Termasuk: sewa/kontrakan, listrik/token, air, gas, transport,
                GAJI & UPAH karyawan, KEMASAN (plastik, karet, kertas nasi,
                kardus, label), pulsa, kebersihan, retribusi.
                Uji cepat: barangnya ikut dijual ke pembeli, atau habis dipakai
                menjalankan warung? Kalau habis dipakai -> operasional.
- prive       : uang usaha yang dipakai untuk keperluan pribadi/rumah tangga
                (belanja dapur rumah, jajan anak, bayar sekolah, arisan).
                Ini BUKAN pengeluaran usaha. Kalau ragu antara prive dan
                operasional, lihat siapa yang menikmati: rumah atau warung.

Uang keluar untuk membayar utang/setoran pinjaman, atau menyetor/menarik uang
dari bank, BUKAN salah satu di atas — itu memindahkan uang, bukan untung/rugi.
Perlakukan sebagai informasi yang kurang.

Kalau kalimat cuma bilang uang keluar tanpa menyebut untuk apa ("keluar 50rb",
"kepake 30rb"), `jenis`-nya tidak bisa dipastikan — itu informasi yang kurang.
Bedanya besar: bahan dagangan, biaya warung, dan uang pribadi jatuh ke tempat
berbeda di laporan. Menebak salah satu = merusak angka laba.

Nominal: angka polos, tanpa "Rp" dan tanpa pemisah ribuan.
DILARANG BERHITUNG. Nominal adalah uang yang benar-benar berpindah, persis
seperti yang diucapkan. Jangan pernah mengalikan jumlah dengan harga.
"laku 5 kotak risol 75rb" -> nominal 75000 (BUKAN 375000); 75rb itu totalnya.
Kalau yang disebut justru harga satuan ("risol 15rb sekotak, laku 5 kotak"),
totalnya tidak diucapkan -> itu informasi yang kurang, jangan dihitung sendiri.
Slang: "goceng"=5000, "ceban"=10000, "gopek"=500, "cepek"=100, "seceng"=1000,
"75rb"/"75k"=75000, "1,5jt"=1500000, "sejuta"=1000000.

Waktu: "tadi"/"hari ini"/"barusan" = tanggal acuan. "kemarin" = sehari sebelum
acuan. Kalau kalimat menyebut waktu yang tidak bisa dipastikan tanggalnya
("minggu lalu", "bulan kemarin"), itu informasi yang kurang.

Takaran: salin apa adanya dari kalimat. "setengah kilo" -> qty 0.5 satuan "kg".
"2 sisir" -> qty 2 satuan "sisir". Jangan mengonversi satuan.
Kalau takaran TIDAK diucapkan, kosongkan qty dan satuan. Jangan mengisi "1 ekor"
atau "1 takaran" hanya supaya kolomnya terisi — takaran karangan akan dipakai
menghitung modal per porsi dan membuat hasilnya salah.

Satu kalimat boleh berisi beberapa transaksi. Jangan menggabungkan dua
transaksi jadi satu, dan jangan memecah satu transaksi jadi dua.
""".strip()


class AksiKoreksi(str, enum.Enum):
    ubah = "ubah"
    batal = "batal"


@dataclass
class Koreksi:
    """Perubahan atas satu transaksi yang sudah tercatat.

    Field selain `aksi` hanya diisi bila memang **berubah**. Kosong berarti
    "biarkan seperti semula" — bukan "kosongkan". Membedakan keduanya penting:
    "harusnya 57rb" tidak boleh menghapus produk & takaran yang sudah benar.
    """

    aksi: AksiKoreksi
    nominal: Decimal | None = None
    jenis: JenisTransaksi | None = None
    tanggal: date | None = None
    produk: str | None = None
    qty: Decimal | None = None
    satuan: str | None = None


_INSTRUKSI_KOREKSI = """
Pemilik warung sedang membetulkan satu catatan yang sudah tersimpan.
Tanggal acuan hari ini: {hari_ini}.

Catatan yang sedang dibetulkan:
{transaksi}

Tentukan `aksi`:
- "batal" bila pengguna ingin catatan itu dihapus/dibatalkan seluruhnya
  ("hapus yang tadi", "batalkan", "itu salah, gak jadi", "bukan transaksi").
- "ubah" bila hanya sebagian yang keliru ("harusnya 57rb", "itu buat pribadi",
  "bukan kemarin, tapi hari ini").

ISI HANYA FIELD YANG BERUBAH. Field yang tidak disebut pengguna biarkan kosong —
kosong berarti "biarkan seperti semula", bukan "kosongkan". Contoh: untuk
"harusnya 57rb", isi `nominal` saja; jangan menyalin ulang produk atau takaran.

Arti `jenis` sama seperti saat mencatat:
pemasukan (uang masuk dari menjual) · pengeluaran (belanja barang dagangan) ·
operasional (biaya menjalankan warung: sewa, listrik, gas, upah, kemasan) ·
prive (uang usaha dipakai untuk keperluan pribadi/rumah).

DILARANG BERHITUNG. Nominal adalah angka yang diucapkan, bukan hasil perkalian.
Slang: "goceng"=5000, "ceban"=10000, "75rb"/"75k"=75000, "1,5jt"=1500000.

Kalau kalimatnya tidak jelas menyuruh mengubah apa, itu informasi yang kurang.
""".strip()


def instruksi_koreksi(hari_ini: date, ringkasan_transaksi: str) -> str:
    """Instruksi sistem untuk mengekstrak koreksi.

    `ringkasan_transaksi` dirender kode dari baris DB — bukan teks bebas dari
    pengguna — supaya isi buku tidak bisa disetir lewat kalimat masukan.
    """
    return _INSTRUKSI_KOREKSI.format(
        hari_ini=hari_ini.isoformat(), transaksi=ringkasan_transaksi
    )


def instruksi_catat(hari_ini: date) -> str:
    """Instruksi sistem untuk `ekstrak`.

    Tanggal acuan disuntik, tidak diambil dari jam server di dalam prompt —
    supaya evaluasi bisa direproduksi dan hasilnya tidak berubah tiap hari.
    """
    return _INSTRUKSI.format(hari_ini=hari_ini.isoformat())

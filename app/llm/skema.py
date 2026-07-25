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
    "AksiRouter",
    "BarisResepBahan",
    "BarisTransaksi",
    "HasilCatat",
    "HasilResep",
    "JawabHarga",
    "JenisTransaksi",
    "Koreksi",
    "PilihanAksi",
    "instruksi_catat",
    "instruksi_harga",
    "instruksi_koreksi",
    "instruksi_resep",
    "instruksi_router",
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


@dataclass
class BarisResepBahan:
    """Satu bahan dalam resep: takaran per sekali masak. **Tanpa uang** —
    harga bahan masuk lewat jalur terpisah (pembelian / tanya-jawab), bukan
    dari kalimat resep. Jadi skema ini bebas dari penjaga aturan #1."""

    nama: str
    qty: Decimal
    satuan: str | None = None


@dataclass
class HasilResep:
    """Resep terstruktur dari kalimat pemilik: sekali masak `yield_qty`
    `yield_satuan`, memakai `bahan`. `yield` wajib — tanpa "jadi berapa" modal
    per porsi tak bisa dibagi (info kurang, bukan ditebak)."""

    nama_produk: str
    yield_qty: Decimal
    yield_satuan: str | None = None
    bahan: list[BarisResepBahan] = field(default_factory=list)


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
    return _INSTRUKSI_KOREKSI.format(hari_ini=hari_ini.isoformat(), transaksi=ringkasan_transaksi)


def instruksi_catat(hari_ini: date) -> str:
    """Instruksi sistem untuk `ekstrak`.

    Tanggal acuan disuntik, tidak diambil dari jam server di dalam prompt —
    supaya evaluasi bisa direproduksi dan hasilnya tidak berubah tiap hari.
    """
    return _INSTRUKSI.format(hari_ini=hari_ini.isoformat())


_INSTRUKSI_RESEP = """
Pemilik warung Indonesia menceritakan RESEP sebuah produk yang ia BUAT sendiri
(bukan barang kulakan). Ubah jadi resep terstruktur. Tanggal acuan: {hari_ini}.

- `nama_produk`: nama barang jadinya ("risol", "kroket", "bolu").
- `yield_qty` + `yield_satuan`: sekali masak jadi berapa ("sekali bikin 10
  kotak" -> yield_qty 10, yield_satuan "kotak"). WAJIB. Kalau tidak disebut
  berapa hasil sekali masak, itu informasi yang kurang — jangan menebak 1.
- `bahan`: daftar bahan + takarannya. "tepung 1 kg" -> nama "tepung", qty 1,
  satuan "kg". "minyak setengah liter" -> qty 0.5, satuan "liter". "ayam
  sekilo" -> qty 1, satuan "kg".

DILARANG menyebut UANG/HARGA. Resep hanya bahan + takaran; harga bahan diurus
terpisah. Kalau pemilik menyebut harga ("keju sekilo 90rb"), ABAIKAN angka
harganya — cukup catat bahan "keju" dengan takarannya bila ada.

Takaran: salin apa adanya, JANGAN mengonversi satuan. Kalau sebuah bahan
takarannya tidak disebut, kosongkan qty & satuannya — jangan mengarang "1".
Slang takaran: "sekilo"=1 kg, "setengah kilo"/"seperempat kilo" -> 0.5 / 0.25
kg, "seons"/"1 ons"=1 ons.

Kalau kalimatnya bukan resep (tidak ada bahan, atau tidak ada barang jadi yang
dibuat), itu informasi yang kurang.
""".strip()


def instruksi_resep(hari_ini: date) -> str:
    """Instruksi sistem untuk mengekstrak resep (bebas-uang).

    Tanggal acuan disuntik demi reproduksibilitas, sama seperti `instruksi_catat`.
    """
    return _INSTRUKSI_RESEP.format(hari_ini=hari_ini.isoformat())


@dataclass
class JawabHarga:
    """Jawaban pemilik atas pertanyaan harga sebuah bahan.

    `nominal` = uang yang disebut; `qty` = berapa banyak satuan yang harga itu
    mencakupnya ("2 kilo 180rb" → nominal 180000, qty 2, satuan "kg"). Harga
    satuan = `nominal ÷ qty` **dihitung kode**, bukan model (aturan #1)."""

    nominal: Decimal
    qty: Decimal | None = None
    satuan: str | None = None


_INSTRUKSI_HARGA = """
Pemilik warung menjawab pertanyaan: berapa HARGA bahan "{bahan}"?
Tanggal acuan: {hari_ini}.

Tangkap:
- `nominal`: uang yang disebut, angka polos tanpa "Rp"/pemisah ribuan.
- `qty`: berapa banyak satuan yang harga itu mencakupnya. "sekilo 90rb" -> qty 1;
  "2 kilo 180rb" -> qty 2; "sekarung 25kg 300rb" -> qty 25 (satuan kg). Kalau
  tak jelas berapa banyak, kosongkan.
- `satuan`: satuan dari qty ("kg", "liter", "ons", "bungkus"). Salin apa adanya,
  jangan konversi.

DILARANG BERHITUNG. `nominal` adalah uang yang benar-benar diucapkan, bukan hasil
perkalian/pembagian. Harga per satuan dihitung sistem, bukan kamu.
Slang: "goceng"=5000, "ceban"=10000, "gopek"=500, "cepek"=100, "seceng"=1000,
"90rb"/"90k"=90000, "1,5jt"=1500000.

Kalau kalimatnya sama sekali tidak menyebut harga/uang untuk "{bahan}", itu bukan
jawaban harga — informasi yang kurang.
""".strip()


def instruksi_harga(bahan: str, hari_ini: date) -> str:
    """Instruksi sistem untuk mengekstrak jawaban harga sebuah bahan.

    `bahan` disuntik **kode** dari token kelanjutan (bukan teks bebas pengguna),
    jadi isi buku tak bisa disetir lewat kalimat masukan (aturan #6).
    """
    return _INSTRUKSI_HARGA.format(bahan=bahan, hari_ini=hari_ini.isoformat())


class AksiRouter(str, enum.Enum):
    """Ke mana kalimat bebas pengguna diarahkan. Enum tertutup — router hanya
    boleh memilih dari sini, tidak pernah mengarang aksi lain (keputusan.md
    2026-07-22: "Router intent bahasa-bebas")."""

    catat_transaksi = "catat_transaksi"
    tanya_untung = "tanya_untung"
    tanya_keuangan = "tanya_keuangan"
    atur_resep = "atur_resep"
    lihat_transaksi = "lihat_transaksi"


@dataclass
class PilihanAksi:
    aksi: AksiRouter


_INSTRUKSI_ROUTER = """
Pemilik warung Indonesia mengirim satu kalimat ke asisten pencatatan keuangan.
Tugasmu HANYA memilih `aksi` — TEPAT SATU dari lima label di bawah, tidak
pernah label lain.

- "catat_transaksi" bila kalimat menceritakan uang masuk/keluar yang perlu
  dicatat ("laku 5 kotak risol 75rb", "beli minyak 38rb", "ambil 60rb buat
  jajan anak").
- "tanya_untung" bila pengguna bertanya untung/modal/margin PER PRODUK
  ("untung risol berapa sih", "modal per kotaknya berapa", "produk mana yang
  paling untung").
- "tanya_keuangan" bila pengguna bertanya kondisi keuangan usaha SECARA
  UMUM (bukan per produk) — termasuk minta laporan/ringkasan/rekap tanpa
  rincian ("untung saya bulan ini berapa", "gimana sih keuangan saya",
  "rugi apa untung minggu ini", "omzet saya berapa", "laporan singkat",
  "rekap dong", "ringkasan keuangan").
- "atur_resep" bila pengguna MENYATAKAN resep/cara membuat sebuah produk —
  menyebut bahan-bahan yang dipakai untuk membuatnya ("resep risol: tepung
  sekilo, minyak setengah liter, ayam setengah kilo, sekali bikin 10 kotak",
  "bikin bolu pakai 4 telur, 1 kg tepung, jadi 20 potong", "cara buat kroket
  ..."). Ini BUKAN uang berpindah — jadi bukan "catat_transaksi". Kata kunci:
  "resep", "bikin ... pakai ...", "bahannya ...", "jadi ... porsi/kotak".
- "lihat_transaksi" bila pengguna ingin MELIHAT KEMBALI daftar catatan yang
  sudah masuk, satu per satu ("lihat catatan terakhir", "yang tadi udah kecatat
  apa aja", "tampilkan transaksi", "coba lihat catatanku", "riwayat dong").
  BEDAKAN dari "tanya_keuangan": "lihat_transaksi" minta DAFTAR ENTRI mentah
  (baris demi baris); "tanya_keuangan" minta RINGKASAN/REKAP angka gabungan
  (omzet, laba, untung). "lihat catatan" -> lihat_transaksi; "rekap untung
  bulan ini" -> tanya_keuangan.

PENTING — jangan minta detail tambahan:
- Periode/tanggal TIDAK PERNAH kamu perlukan. Sistem di luar prompt ini sudah
  otomatis memakai bulan berjalan kalau pengguna tidak menyebut periode.
  "laporan singkat" atau "gimana keuangan saya" sudah cukup jelas ->
  "tanya_keuangan", walau tanpa periode.
- Jangan pernah membalas dengan field selain `aksi` (tidak ada "periode",
  "jenis_laporan", atau semacamnya — skema hanya punya satu field: `aksi`).

Hanya akui tidak yakin (`_gagal`) kalau kalimatnya benar-benar tidak cocok
satu pun dari lima label (sapaan, obrolan di luar topik) atau bisa dibaca
mendua ANTARA dua label di atas. Ketiadaan detail seperti periode/tanggal
BUKAN alasan untuk tidak yakin.
""".strip()


def instruksi_router() -> str:
    """Instruksi sistem untuk mengklasifikasikan kalimat bebas ke `AksiRouter`.

    Tidak menyuntik data pengguna apa pun ke dalam prompt — klasifikasi murni
    dari kalimatnya sendiri, jadi instruksinya statis (ramah prompt caching,
    02-arsitektur.md §6a).
    """
    return _INSTRUKSI_ROUTER

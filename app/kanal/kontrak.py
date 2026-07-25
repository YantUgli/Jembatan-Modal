"""Kontrak render — seam tegas & ber-versi antara orchestrator dan kanal.

Ini yang selama ini belum ada: bentuk pesan/kartu yang jadi batas antara "kode
kita yang memilih tool & memanggil service" dan "adaptor yang menggambar" (UI
web sekarang, WhatsApp nanti). Orchestrator selalu mengembalikan `PesanKeluar` —
amplop ber-versi berisi daftar kartu — dan tiap adaptor tahu cara menggambar
tiap `tipe` kartu.

Aturan yang dijaga bentuk ini:
- **Angka tidak pernah dikarang** (aturan #1/#2). Kartu hanya membawa string yang
  sudah diformat service (`nominal_tampil`) + nilai mentahnya; tak ada aritmatika
  di sisi kanal. Bila data kurang, dipakai `KartuBelumDiketahui`, bukan angka nol.
- **Channel-agnostic** (arsitektur #2). Tiap kartu membawa `teks_alt`: render
  teks-polos secukupnya, supaya adaptor WhatsApp bisa mengirim kartu yang sama
  tanpa fork. Diisi otomatis di `__post_init__` bila pemanggil tak mengisinya.
- **Ber-versi sejak commit pertama.** `VERSI_KONTRAK` naik bila bentuk berubah
  tak-kompatibel; kanal boleh menolak versi yang tak dikenalnya.

⛔ Jangan impor model/SQLAlchemy/FastAPI di sini. Modul ini murni tipe data +
serialisasi, supaya bisa dipakai adaptor mana pun (dan diuji tanpa DB).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from enum import Enum

VERSI_KONTRAK = 4


class TipeKartu(str, Enum):
    sapaan = "sapaan"
    narasi = "narasi"
    konfirmasi = "konfirmasi"
    klarifikasi = "klarifikasi"
    untung = "untung"
    keuangan = "keuangan"
    resep = "resep"
    riwayat = "riwayat"
    belum_diketahui = "belum_diketahui"


# ── Kartu ────────────────────────────────────────────────────────────────────
# Tiap kartu = satu dataclass dengan field `tipe` (diskriminan) + `teks_alt`
# (fallback teks-polos untuk kanal non-visual). `__post_init__` mengisi `teks_alt`
# bila kosong, jadi pemanggil cukup mengisinya saat butuh bunyi khusus.


@dataclass
class KartuSapaan:
    """Layar pembuka: sapaan + ajakan mulai mencatat."""

    nama_usaha: str
    sub: str  # "Katering & Frozen Food · Bandung"
    salam: str  # "Selamat pagi"
    ajakan: str
    catatan_jujur: str = ""  # janji "angka tidak dikarang"
    teks_alt: str = ""
    tipe: str = TipeKartu.sapaan.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = f"{self.salam}, {self.nama_usaha}. {self.ajakan}".strip()


@dataclass
class KartuNarasi:
    """Gelembung teks dari asisten.

    `aman` = keluaran sudah lolos penjaga `Narasi.aman` (tak ada angka di luar
    fakta). Kartu narasi yang tidak aman **tidak boleh dibuat** — orchestrator
    menahannya di hulu; field ini ada agar kanal bisa menandai bila perlu.
    """

    teks: str
    aman: bool = True
    teks_alt: str = ""
    tipe: str = TipeKartu.narasi.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = self.teks


@dataclass
class PilihanKategori:
    """Satu chip kategori pada kartu konfirmasi (jalur koreksi jenis)."""

    nilai: str  # "prive" — nilai enum JenisTransaksi
    label: str  # "Prive"
    aktif: bool


@dataclass
class BarisKonfirmasi:
    """Satu transaksi tersimpan, siap digambar.

    `nominal_tampil` sudah diformat service (mis. "Rp75.000"); `nominal` menyimpan
    nilai mentah (Decimal-as-string) untuk keperluan non-tampilan. Sisi kanal
    **tidak** berhitung dari angka ini.
    """

    jenis: str  # nilai enum: "pemasukan"
    jenis_label: str  # badge: "Uang masuk"
    nominal_tampil: str
    nominal: str
    produk: str | None = None
    qty_tampil: str | None = None  # "5 kotak"
    transaksi_id: int | None = None
    kategori_pilihan: list[PilihanKategori] = field(default_factory=list)
    # Diisi hanya di kartu riwayat (baris lintas hari perlu tanggal); kartu
    # konfirmasi "baru saja" membiarkannya None.
    tanggal_tampil: str | None = None  # "24 Jul"


@dataclass
class KartuKonfirmasi:
    """"Tercatat ya, Bu" — hasil pencatatan, dirender dari template kode.

    `konfirmasi` datang apa adanya dari tool (bukan panggilan LLM kedua), jadi
    angka di dalamnya mustahil meleset dari yang tersimpan.
    """

    baris: list[BarisKonfirmasi]
    ids: list[int]
    konfirmasi: str
    teks_alt: str = ""
    tipe: str = TipeKartu.konfirmasi.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = self.konfirmasi


@dataclass
class KartuKlarifikasi:
    """Pertanyaan balik — jalur normal, bukan kegagalan. Tidak ada yang tersimpan."""

    pertanyaan: str
    yang_kurang: list[str] = field(default_factory=list)
    teks_alt: str = ""
    tipe: str = TipeKartu.klarifikasi.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = self.pertanyaan


@dataclass
class BarisUntung:
    """Satu produk pada kartu untung — **laba kotor dari bahan per porsi**.

    ⛔ Bukan "untung usaha" (aturan #9): ini parsial, alat keputusan harga, belum
    dikurangi biaya lain (gas, listrik, tenaga). Bila HPP belum bisa dihitung,
    `diketahui=False` dan angka-angkanya `None` — **bukan "Rp0"** (aturan #2).
    `sebab` & `yang_kurang` menerjemahkan `StatusHpp` ke bahasa warung.
    """

    nama: str
    jenis: str  # "produksi" | "reseller"
    diketahui: bool
    hpp_tampil: str | None = None
    satuan_hpp: str | None = None
    harga_jual_tampil: str | None = None
    laba_kotor_tampil: str | None = None
    sebab: str = ""  # kenapa belum diketahui, satu kalimat warung
    yang_kurang: list[str] = field(default_factory=list)


@dataclass
class KartuUntung:
    """Kartu untung/HPP — **laba kotor dari bahan per porsi**, per produk.

    ⛔ Aturan #9: kartu ini TIDAK pernah menyebut angkanya "untung usaha". Untung
    bersih usaha adalah angka lain (kartu keuangan), dan dua angka itu tidak
    pernah dilebur. `pesan` membawa kualifikasi itu; `cakupan_tampil` menampilkan
    berapa persen penjualan yang modalnya sudah terhitung (aturan #2).
    """

    pesan: str
    produk: list[BarisUntung] = field(default_factory=list)
    cakupan_tampil: str = ""  # "78%"
    status: str = "lengkap"  # lengkap | sebagian | belum_diketahui
    teks_alt: str = ""
    tipe: str = TipeKartu.untung.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            baris = [
                (
                    f"{b.nama}: {b.laba_kotor_tampil}/porsi (modal {b.hpp_tampil})"
                    if b.diketahui
                    else f"{b.nama}: belum diketahui — {b.sebab}"
                )
                for b in self.produk
            ]
            self.teks_alt = "\n".join([self.pesan, *baris]).strip()


@dataclass
class BarisPos:
    """Satu pos biaya terbesar pada kartu keuangan."""

    kategori: str
    jenis: str  # "pengeluaran" | "operasional"
    nominal_tampil: str


@dataclass
class KartuKeuangan:
    """Untung usaha periode — **angka utama** (aturan #9, keputusan "dua angka").

    Omzet − (belanja + operasional) = laba bersih. Cakupan biaya 100% menurut
    definisi; `prive` dikecualikan & dilaporкan terpisah. ⛔ Tidak memuat skor
    komposit apa pun. `cakupan_tampil` = berapa persen omzet yang HPP-nya
    terhitung — jujur soal seberapa dalam modal per-produk sudah tercatat.
    """

    periode_tampil: str
    omzet_tampil: str
    belanja_tampil: str
    operasional_tampil: str
    biaya_tampil: str
    laba_bersih_tampil: str
    untung: bool
    ada_data: bool
    cakupan_tampil: str  # "78%"
    prive_tampil: str | None = None
    rasio_prive_tampil: str | None = None
    pos_biaya: list[BarisPos] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)
    teks_alt: str = ""
    tipe: str = TipeKartu.keuangan.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            if not self.ada_data:
                self.teks_alt = f"{self.periode_tampil}: belum ada catatan."
            else:
                self.teks_alt = (
                    f"{self.periode_tampil} — untung usaha {self.laba_bersih_tampil} "
                    f"(omzet {self.omzet_tampil} − biaya {self.biaya_tampil})."
                )


@dataclass
class KartuResep:
    """Resep tercatat → **modal per porsi** (Pilar 4, jalur produksi).

    ⛔ Bukan "untung usaha" (aturan #9): ini modal bikin per porsi, alat
    keputusan harga. `modal_tampil` hanya terisi bila HPP `lengkap`; bila masih
    ada bahan tanpa harga, `status="belum"` + `bahan_perlu_harga` menyebut apa
    yang kurang — **bukan Rp0** (aturan #2). `konfirmasi` datang apa adanya dari
    service (template kode, bukan LLM kedua).

    `menunggu` = token kelanjutan tanya-jawab harga: `{product_id, bahan}` bahan
    yang harganya sedang diminta. Klien melampirkannya ke pesan berikutnya
    sebagai `konteks`; server memvalidasi ulang `product_id` milik tenant
    (aturan #6). `None` = tak ada yang ditanyakan.
    """

    product_id: int
    nama: str
    status: str  # "lengkap" | "belum"
    konfirmasi: str
    modal_tampil: str | None = None
    satuan_hpp: str | None = None
    bahan_perlu_harga: list[str] = field(default_factory=list)
    menunggu: dict | None = None  # {"product_id": int, "bahan": str}
    teks_alt: str = ""
    tipe: str = TipeKartu.resep.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = self.konfirmasi


@dataclass
class KartuRiwayat:
    """Daftar catatan terakhir — jalur baca "lihat transaksi terakhir".

    Baris memakai ulang `BarisKonfirmasi` (bawa `transaksi_id` + chip kategori),
    jadi tiap baris **bisa dibetulkan di tempat** lewat jalur `koreksi_kategori`
    yang sudah ada. `tanggal_tampil` per baris menandai kapan (daftar bisa
    lintas hari). ⛔ Tanpa aritmatika di sini (aturan #1): angka datang apa
    adanya dari baris tersimpan. Daftar kosong → `baris=[]` + `pesan` jujur,
    bukan baris karangan (aturan #2).
    """

    baris: list[BarisKonfirmasi]
    judul: str
    pesan: str
    teks_alt: str = ""
    tipe: str = TipeKartu.riwayat.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            baris = [
                " ".join(
                    x
                    for x in (
                        b.tanggal_tampil,
                        b.jenis_label,
                        b.nominal_tampil,
                        f"({b.produk})" if b.produk else None,
                    )
                    if x
                )
                for b in self.baris
            ]
            self.teks_alt = "\n".join([self.judul, *baris]).strip() if baris else self.pesan


@dataclass
class KartuBelumDiketahui:
    """Data kurang → mengaku tenang (aturan #2). Bukan pesan error."""

    judul: str
    alasan: str
    yang_kurang: list[str] = field(default_factory=list)
    teks_alt: str = ""
    tipe: str = TipeKartu.belum_diketahui.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            ekor = (" Yang kurang: " + ", ".join(self.yang_kurang)) if self.yang_kurang else ""
            self.teks_alt = f"{self.judul} — {self.alasan}{ekor}"


Kartu = (
    KartuSapaan
    | KartuNarasi
    | KartuKonfirmasi
    | KartuKlarifikasi
    | KartuUntung
    | KartuKeuangan
    | KartuResep
    | KartuRiwayat
    | KartuBelumDiketahui
)


# ── Amplop ───────────────────────────────────────────────────────────────────


@dataclass
class PesanKeluar:
    """Amplop ber-versi: nol atau lebih kartu, dalam urutan tampil."""

    kartu: list[Kartu]
    versi: int = VERSI_KONTRAK

    def ke_dict(self) -> dict:
        """Serialisasi JSON-safe. `asdict` merambati kartu & sub-dataclass.

        Semua nilai sudah tipe primitif (string/angka/bool/list) — tak ada
        `Decimal`/`Enum`/`date` yang perlu encoder khusus.
        """
        return {"versi": self.versi, "kartu": [asdict(k) for k in self.kartu]}


__all__ = [
    "VERSI_KONTRAK",
    "TipeKartu",
    "KartuSapaan",
    "KartuNarasi",
    "PilihanKategori",
    "BarisKonfirmasi",
    "KartuKonfirmasi",
    "KartuKlarifikasi",
    "BarisUntung",
    "KartuUntung",
    "BarisPos",
    "KartuKeuangan",
    "KartuResep",
    "KartuRiwayat",
    "KartuBelumDiketahui",
    "Kartu",
    "PesanKeluar",
]

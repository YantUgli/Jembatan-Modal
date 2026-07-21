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

VERSI_KONTRAK = 1


class TipeKartu(str, Enum):
    sapaan = "sapaan"
    narasi = "narasi"
    konfirmasi = "konfirmasi"
    klarifikasi = "klarifikasi"
    untung = "untung"
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
class KartuUntung:
    """Kartu untung/HPP.

    SLICE 1 = **stub jujur**: service HPP sudah matang tapi belum di-wire sebagai
    tool, jadi kartu ini mengaku "belum tersambung" alih-alih mengarang angka.
    Saat di-wire (slice berikutnya) field angka ditambah di sini, dengan
    kualifikasi wajib "laba kotor dari bahan" (bukan untung bersih usaha).
    """

    pesan: str
    status: str = "belum_tersambung"  # belum_tersambung → nanti: lengkap|belum_diketahui
    teks_alt: str = ""
    tipe: str = TipeKartu.untung.value

    def __post_init__(self) -> None:
        if not self.teks_alt:
            self.teks_alt = self.pesan


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
    "KartuUntung",
    "KartuBelumDiketahui",
    "Kartu",
    "PesanKeluar",
]

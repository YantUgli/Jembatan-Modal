"""Service laporan keuangan (Pilar 3) — seluruh angka dokumen, nol render.

Ini lapisan yang menyiapkan **satu-satunya keluaran produk ini yang dibaca orang
lain**: AO bank / petugas koperasi, bukan pemiliknya. Karena itu dua aturan
paling mengikat di repo bertemu di sini.

**Aturan #2 — tangga laba mengikuti basis kas, bukan HPP.** `04-rencana-kerja.md`
Tahap 4a menulis formula laporan sebagai *Omzet − HPP = Laba Kotor − Operasional
= Laba Bersih*. Formula itu hanya benar bila cakupan HPP 100%. Pada cakupan 78%
— kondisi normal, dan justru yang wajib ditampilkan — mengurangkan `hpp_total`
dari **seluruh** omzet berarti mengaku tahu modal untuk penjualan yang modalnya
belum diketahui: laba kotor karangan. Karena itu laporan memakai tangga yang
sudah diputuskan `keputusan.md` 2026-07-18 dan diimplementasikan
`services/laba.py`:

    Omzet − (Belanja + Operasional) = Laba Bersih      ← angka utama, cakupan 100%
    HPP & laba kotor                                    ← blok terpisah, menyebut
                                                          cakupannya sendiri
    rekonsiliasi_biaya                                  ← jembatan antara keduanya

**Aturan #9 — `fakta_penyalur` tanpa penilaian.** Yang masuk dokumen pembaca
penyalur hanya fakta yang bisa ditelusuri ke transaksi. ⛔ Tidak ada skor
komposit di modul ini, sekarang maupun setelah service skor lahir.

Konsekuensi kecil yang perlu disadari: **"bulan pencatatan konsisten" sengaja
tidak diberi ambang.** `02-arsitektur.md §4` menyebutnya, tapi menetapkan sendiri
"konsisten = ≥N hari" adalah penilaian berbaju angka — persis yang aturan #9
larang. Yang dilaporkan: hari tercatat per bulan, apa adanya. Pembacanya yang
menilai.

Deterministik, tanpa LLM (aturan #1). Isolasi tenant (aturan #6): tiap query
difilter `business_id`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, Transaction
from app.services.angka import _uang
from app.services.hpp import CakupanHpp, cakupan_hpp
from app.services.laba import (
    LabaPeriode,
    RekonsiliasiBiaya,
    hitung_laba_periode,
    rekonsiliasi_biaya,
)
from app.services.tanggal import (
    akhir_bulan,
    awal_bulan,
    bulan_kalender_terakhir,
    nama_bulan,
    periode_tampil,
)

__all__ = [
    "ArusKas",
    "BulanLaporan",
    "FaktaPenyalur",
    "Identitas",
    "RingkasanLaporan",
    "ringkas_laporan",
]

JUMLAH_BULAN_DEFAULT = 3

CATATAN_BULAN_BERJALAN = (
    "Bulan berjalan belum penuh — angkanya baru sampai tanggal potong di atas."
)


@dataclass
class Identitas:
    """Kop dokumen. Seluruhnya dari DB milik tenant, tak satu pun dari klien."""

    nama_usaha: str
    jenis_usaha: str | None
    lokasi: str | None
    nama_pemilik: str | None
    no_hp: str | None
    mulai_usaha: date | None


@dataclass
class BulanLaporan:
    """Satu baris tabel tren. `penuh=False` = bulan berjalan / terpotong rentang."""

    mulai: date
    selesai: date
    label: str  # "Jul 2026"
    penuh: bool
    hari_tercatat: int
    laba: LabaPeriode
    cakupan: CakupanHpp


@dataclass
class ArusKas:
    """Uang yang benar-benar bergerak — **prive ikut** sebagai uang keluar.

    Bedanya dengan laba bersih justru gunanya bagi pembaca penyalur: laba bersih
    menjawab "usahanya untung?", arus kas menjawab "uangnya ke mana?". Prive
    bukan biaya usaha (aturan #9) tapi ia betul-betul keluar dari laci.
    """

    uang_masuk: Decimal
    uang_keluar: Decimal  # biaya usaha + prive
    prive: Decimal
    sisa: Decimal


@dataclass
class FaktaPenyalur:
    """Fakta mentah terverifikasi (aturan #9). ⛔ Tanpa skor, tanpa penilaian.

    Tiap angka di sini bisa ditelusuri balik ke baris transaksi. Tidak ada
    ambang, tidak ada label "baik/kurang" — pembacanya punya model risikonya
    sendiri.
    """

    omzet_total: Decimal
    bulan_bercatatan: int  # bulan dalam periode laporan yang ada transaksinya
    bulan_berturut: int  # rentetan bulan bercatatan yang berakhir di bulan terakhir
    hari_tercatat: int  # total hari berbeda yang ada catatannya di periode ini
    cakupan_hpp_persen: Decimal
    rasio_prive_persen: Decimal | None


@dataclass
class RingkasanLaporan:
    identitas: Identitas
    mulai: date
    selesai: date
    periode_tampil: str
    bulan: list[BulanLaporan]
    total: LabaPeriode
    cakupan: CakupanHpp
    rekonsiliasi: RekonsiliasiBiaya
    arus_kas: ArusKas
    fakta: FaktaPenyalur
    catatan: list[str] = field(default_factory=list)


def _pecah_bulan(mulai: date, selesai: date) -> list[tuple[date, date]]:
    """Rentang → potongan per bulan kalender, dipotong di ujung-ujungnya."""
    potongan: list[tuple[date, date]] = []
    kursor = mulai
    while kursor <= selesai:
        batas = min(akhir_bulan(kursor), selesai)
        potongan.append((kursor, batas))
        kursor = date.fromordinal(akhir_bulan(kursor).toordinal() + 1)
    return potongan


def _tanggal_bercatatan(session: Session, business_id: int) -> list[date]:
    """Tanggal berbeda yang punya transaksi berlaku, terlama dulu (aturan #6).

    Satu query untuk seluruh riwayat: dipakai dua kali (hari tercatat per bulan
    di dalam periode, dan rentetan bulan yang boleh melampaui periode laporan).
    """
    return sorted(
        set(
            session.scalars(
                select(Transaction.tanggal).where(
                    Transaction.business_id == business_id,
                    Transaction.dibatalkan_pada.is_(None),  # buku append-only
                )
            ).all()
        )
    )


def _bulan_berturut(tanggal: list[date], sampai: date) -> int:
    """Rentetan bulan bercatatan yang berakhir di bulan `sampai`.

    Sengaja **tidak dibatasi periode laporan**: usaha yang sudah mencatat delapan
    bulan berturut-turut layak disebut delapan, bukan tiga. Bila bulan `sampai`
    sendiri belum ada catatannya, rentetannya nol — bukan diambil dari bulan
    sebelumnya, karena yang ditanya "sampai sekarang".
    """
    ada = {(t.year, t.month) for t in tanggal}
    kursor = awal_bulan(sampai)
    n = 0
    while (kursor.year, kursor.month) in ada:
        n += 1
        kursor = awal_bulan(date.fromordinal(kursor.toordinal() - 1))
    return n


def ringkas_laporan(
    session: Session,
    business: Business,
    hari_ini: date,
    mulai: date | None = None,
    selesai: date | None = None,
    jumlah_bulan: int = JUMLAH_BULAN_DEFAULT,
) -> RingkasanLaporan:
    """Seluruh angka satu laporan. `business` sudah diselesaikan server (aturan #6).

    Tanpa `mulai`/`selesai`: `jumlah_bulan` bulan kalender terakhir **termasuk
    bulan berjalan**, yang ditutup di `hari_ini` — laporan tak boleh menyiratkan
    punya data untuk hari yang belum terjadi.

    Bulan tanpa catatan tetap muncul sebagai baris nol bertanda. Bolong yang
    disembunyikan lebih berbahaya daripada bolong yang terlihat: pembaca yang
    tak melihatnya akan mengira periodenya memang serapat itu.
    """
    if mulai is None or selesai is None:
        rentang = bulan_kalender_terakhir(hari_ini, jumlah_bulan)
        mulai = mulai or rentang[0][0]
        selesai = selesai or rentang[-1][1]
    if selesai < mulai:
        raise ValueError("selesai tidak boleh sebelum mulai")

    tanggal = _tanggal_bercatatan(session, business.id)

    bulan: list[BulanLaporan] = []
    for awal, akhir in _pecah_bulan(mulai, selesai):
        hari = sum(1 for t in tanggal if awal <= t <= akhir)
        bulan.append(
            BulanLaporan(
                mulai=awal,
                selesai=akhir,
                label=nama_bulan(awal),
                penuh=(awal == awal_bulan(awal) and akhir == akhir_bulan(akhir)),
                hari_tercatat=hari,
                laba=hitung_laba_periode(session, business.id, awal, akhir),
                cakupan=cakupan_hpp(session, business.id, awal, akhir),
            )
        )

    # Total dihitung SEKALI untuk seluruh rentang, bukan menjumlahkan hasil per
    # bulan di Python: satu angka, satu asal-usul.
    total = hitung_laba_periode(session, business.id, mulai, selesai)
    cakupan = cakupan_hpp(session, business.id, mulai, selesai)
    rekon = rekonsiliasi_biaya(session, business.id, mulai, selesai)

    keluar = total.biaya_total + total.prive
    arus_kas = ArusKas(
        uang_masuk=total.omzet,
        uang_keluar=_uang(keluar),
        prive=total.prive,
        sisa=_uang(total.omzet - keluar),
    )

    hari_dalam_periode = sum(1 for t in tanggal if mulai <= t <= selesai)
    fakta = FaktaPenyalur(
        omzet_total=total.omzet,
        bulan_bercatatan=sum(1 for b in bulan if b.hari_tercatat > 0),
        bulan_berturut=_bulan_berturut(tanggal, selesai),
        hari_tercatat=hari_dalam_periode,
        cakupan_hpp_persen=cakupan.persen,
        rasio_prive_persen=total.rasio_prive,
    )

    catatan = list(total.catatan)
    if bulan and not bulan[-1].penuh:
        catatan.append(CATATAN_BULAN_BERJALAN)
    if any(b.hari_tercatat == 0 for b in bulan):
        catatan.append(
            "Ada bulan tanpa catatan sama sekali pada periode ini — ditampilkan "
            "sebagai nol, bukan dilewati."
        )

    return RingkasanLaporan(
        identitas=Identitas(
            nama_usaha=business.nama_usaha,
            jenis_usaha=business.jenis_usaha,
            lokasi=business.lokasi,
            nama_pemilik=business.user.nama if business.user is not None else None,
            no_hp=business.user.no_hp if business.user is not None else None,
            mulai_usaha=business.mulai_usaha,
        ),
        mulai=mulai,
        selesai=selesai,
        periode_tampil=periode_tampil(mulai, selesai),
        bulan=bulan,
        total=total,
        cakupan=cakupan,
        rekonsiliasi=rekon,
        arus_kas=arus_kas,
        fakta=fakta,
        catatan=catatan,
    )

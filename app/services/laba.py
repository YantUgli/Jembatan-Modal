"""Service laba periode & rekonsiliasi biaya (Pilar 4) — angka utama "untung jujur".

Deterministik, ber-unit-test. LLM tidak pernah masuk ke sini (prinsip #1).

Keputusan yang melahirkan modul ini: **dua angka, tidak pernah dilebur**
(keputusan.md 2026-07-18).

    1. laba periode   = Σ pemasukan − Σ (pengeluaran + operasional)
       └─ ANGKA UTAMA. Cakupan biaya 100% menurut definisi: tidak butuh resep,
          tidak butuh alokasi, tidak butuh tahu ini warteg atau laundry.

    2. HPP per unit   → `app/services/hpp.py`
       └─ alat keputusan harga/porsi per produk. Parsial secara sifat.
          ⛔ Tidak pernah dipresentasikan sebagai "untung usaha".

    3. rekonsiliasi   = pengeluaran − biaya terserap HPP
       └─ jembatan antara keduanya. Selisihnya BUKAN error — itu biaya yang
          tidak tertelusur ke produk manapun (gaji, sewa, penyusutan, gas).
          Menamainya terang-terangan = inti aturan #2.

`prive` bukan biaya usaha. Ia dikeluarkan dari perhitungan laba dan dilaporkan
terpisah sebagai fakta mentah (aturan #9).

Batas jujur yang harus ikut dinarasikan (lihat `CATATAN_BASIS_KAS`): ini basis
kas — belanja stok bulan ini yang baru laku bulan depan tetap tercatat bulan
ini. Untuk periode pendek angkanya bisa timpang; makin panjang periodenya makin
mendekati laba sebenarnya. Jangan diam-diam meratakannya — itu mengarang angka.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JenisTransaksi, Transaction
from app.services.angka import _dec, _uang
from app.services.hpp import cakupan_hpp

TANPA_KATEGORI = "{jenis} (tanpa rincian)"

CATATAN_BASIS_KAS = (
    "Hitungan ini basis kas: belanja yang barangnya baru laku periode berikutnya "
    "tetap masuk periode ini."
)


@dataclass
class PosBiaya:
    """Satu pos pengeluaran, dikelompokkan menurut `kategori_detail`."""

    kategori: str
    jenis: str  # pengeluaran | operasional
    nominal: Decimal


@dataclass
class LabaPeriode:
    """Angka utama. Cakupan biaya 100% — tidak ada yang dialokasikan."""

    mulai: date
    selesai: date
    omzet: Decimal
    belanja: Decimal          # jenis=pengeluaran (bahan/barang dagangan)
    operasional: Decimal      # jenis=operasional (sewa, listrik, gaji)
    biaya_total: Decimal      # belanja + operasional
    laba_bersih: Decimal      # omzet − biaya_total
    prive: Decimal            # BUKAN biaya usaha — dilaporkan terpisah
    rasio_prive: Decimal | None  # prive ÷ laba_bersih × 100, None bila laba ≤ 0
    pos_biaya: list[PosBiaya] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)

    @property
    def untung(self) -> bool:
        return self.laba_bersih > 0


@dataclass
class RekonsiliasiBiaya:
    """Jembatan antara laba periode dan HPP per unit.

    `di_luar_hpp` menjawab pertanyaan yang tidak bisa dijawab `cakupan_hpp()`:
    berapa banyak biaya nyata yang belum terlihat oleh HPP. Deterministik dan
    **tidak butuh pengetahuan industri** — sistem menemukan sendiri apa yang
    tidak diketahuinya, termasuk untuk jenis usaha yang belum pernah kita lihat.
    """

    biaya_total: Decimal
    terserap_hpp: Decimal
    di_luar_hpp: Decimal
    persen_terserap: Decimal              # 0..100, 1 desimal
    # Pos biaya terbesar periode ini — SELURUHNYA, bukan hanya yang di luar HPP.
    # Kita tidak bisa memetakan satu transaksi belanja ke penyerapan HPP, jadi
    # menyaringnya berarti mengarang. Namanya menyebut apa adanya (aturan #2).
    pos_biaya_terbesar: list[PosBiaya] = field(default_factory=list)
    catatan: list[str] = field(default_factory=list)


def _persen(pembilang: Decimal, penyebut: Decimal) -> Decimal:
    if penyebut <= 0:
        return Decimal("0.0")
    return (pembilang / penyebut * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def _pos_biaya(transaksi: list[Transaction]) -> list[PosBiaya]:
    """Kelompokkan pengeluaran per `kategori_detail`, terbesar dulu."""
    ember: dict[tuple[str, str], Decimal] = {}
    for t in transaksi:
        # Tanpa kategori, jenisnya sendiri lebih informatif daripada label kosong
        # — dan mencegah dua pos berbeda tampak seperti baris kembar.
        kunci = (t.kategori_detail or TANPA_KATEGORI.format(jenis=t.jenis.value), t.jenis.value)
        ember[kunci] = ember.get(kunci, Decimal("0")) + _dec(t.nominal)
    return sorted(
        (PosBiaya(kategori=k, jenis=j, nominal=_uang(n)) for (k, j), n in ember.items()),
        key=lambda p: p.nominal,
        reverse=True,
    )


def hitung_laba_periode(
    session: Session, business_id: int, mulai: date, selesai: date
) -> LabaPeriode:
    """Laba periode — angka utama, cakupan biaya 100%.

    `business_id` wajib (isolasi tenant, prinsip #6).
    """
    transaksi = session.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.tanggal >= mulai,
            Transaction.tanggal <= selesai,
            Transaction.dibatalkan_pada.is_(None),  # buku append-only
        )
    ).all()

    omzet = Decimal("0")
    belanja = Decimal("0")
    operasional = Decimal("0")
    prive = Decimal("0")
    biaya_transaksi: list[Transaction] = []

    for t in transaksi:
        nominal = _dec(t.nominal)
        if t.jenis is JenisTransaksi.pemasukan:
            omzet += nominal
        elif t.jenis is JenisTransaksi.pengeluaran:
            belanja += nominal
            biaya_transaksi.append(t)
        elif t.jenis is JenisTransaksi.operasional:
            operasional += nominal
            biaya_transaksi.append(t)
        elif t.jenis is JenisTransaksi.prive:
            prive += nominal  # bukan biaya usaha (aturan #9)

    biaya_total = belanja + operasional
    laba_bersih = omzet - biaya_total

    catatan: list[str] = []
    if not transaksi:
        catatan.append("Belum ada catatan pada periode ini.")
    else:
        catatan.append(CATATAN_BASIS_KAS)
    if prive > 0:
        catatan.append(
            "Prive (uang yang diambil untuk keperluan pribadi) tidak dihitung "
            "sebagai biaya usaha."
        )
    if laba_bersih < 0:
        catatan.append("Pengeluaran periode ini lebih besar daripada pemasukan.")

    return LabaPeriode(
        mulai=mulai,
        selesai=selesai,
        omzet=_uang(omzet),
        belanja=_uang(belanja),
        operasional=_uang(operasional),
        biaya_total=_uang(biaya_total),
        laba_bersih=_uang(laba_bersih),
        prive=_uang(prive),
        rasio_prive=_persen(prive, laba_bersih) if laba_bersih > 0 else None,
        pos_biaya=_pos_biaya(biaya_transaksi),
        catatan=catatan,
    )


def rekonsiliasi_biaya(
    session: Session, business_id: int, mulai: date, selesai: date, batas_pos: int = 5
) -> RekonsiliasiBiaya:
    """Berapa banyak biaya nyata yang BELUM terlihat oleh HPP.

    Ini pelengkap wajib `cakupan_hpp()`: cakupan omzet 100% tidak berarti
    cakupan biaya 100%. Tanpa angka ini, laporan bisa menyebut "lengkap" untuk
    HPP yang hanya memuat sebagian biaya.
    """
    laba = hitung_laba_periode(session, business_id, mulai, selesai)
    cakupan = cakupan_hpp(session, business_id, mulai, selesai)

    terserap = cakupan.hpp_total
    di_luar = laba.biaya_total - terserap

    catatan: list[str] = []
    if laba.biaya_total <= 0:
        catatan.append("Belum ada pengeluaran tercatat pada periode ini.")
    else:
        catatan.append(CATATAN_BASIS_KAS)
    if di_luar < 0:
        # HPP menyerap lebih besar dari belanja periode. Dua sebab yang sama-sama
        # masuk akal — sebutkan KEDUANYA, jangan pilih salah satu seolah pasti
        # (aturan #2), dan jangan dipoles jadi nol.
        catatan.append(
            "Bahan yang terpakai untuk penjualan periode ini lebih besar daripada "
            "belanja yang tercatat. Bisa jadi ada belanja yang belum dicatat, atau "
            "barangnya memang dibeli sebelum periode ini."
        )
    if laba.operasional > 0:
        catatan.append(
            "Biaya operasional (mis. sewa, listrik, gaji) tidak pernah masuk HPP "
            "per unit — HPP hanya menghitung bahan."
        )

    return RekonsiliasiBiaya(
        biaya_total=laba.biaya_total,
        terserap_hpp=terserap,
        di_luar_hpp=_uang(di_luar),
        persen_terserap=_persen(terserap, laba.biaya_total),
        pos_biaya_terbesar=laba.pos_biaya[:batas_pos],
        catatan=catatan,
    )

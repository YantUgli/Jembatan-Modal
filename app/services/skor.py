"""Skor Kesehatan Usaha (0–100) — **keluaran pengguna, bukan bukti penyalur**.

Empat komponen berbobot (`02-arsitektur.md` §4): konsistensi pencatatan 30,
margin laba 25, tren omzet 25, disiplin prive 20. Seluruhnya dihitung di sini,
deterministik & ber-unit-test; LLM tidak menyentuh satu angka pun (aturan #1).

⛔ **Aturan #9 — dua keluaran terpisah.** `skor_total` di modul ini adalah angka
**motivasi**. Ia tidak boleh masuk ke dokumen yang dibaca penyalur (laporan PDF,
proposal KUR) sebelum terkalibrasi `kur_outcomes` nyata; yang berangkat ke sana
adalah `FaktaPenyalur` di `app/services/laporan.py` — fakta mentah tanpa
penilaian. Menyodorkan "72/100" ke AO bank = mengarang otoritas yang belum kita
punya. Uji negatifnya ada di `tests/test_skor.py`.

**Periode = 30 hari bergulir**, bukan bulan berjalan (`docs/keputusan.md`
2026-07-27). Atas bulan berjalan, komponen konsistensi membaca "2 dari 3 hari"
pada tanggal 3 lalu bergeser sepanjang bulan — skor naik-turun karena kalender,
bukan karena perilaku pemilik.

**Komponen yang tak bisa dihitung tidak diberi nol.** Nol adalah penilaian buruk;
ketiadaan data bukan penilaian (aturan #2). Komponen itu berstatus
`belum_diketahui`, bobotnya keluar dari penyebut, dan sisanya dinormalisasi.
Bila tak ada satu pun komponen yang terhitung, `skor_total` = `None` — bukan 0.

**Margin laba sengaja TIDAK digerbangi cakupan HPP.** Sejak tangga laba menjadi
basis kas (keputusan 2026-07-26), `laba_bersih` punya cakupan biaya 100% menurut
definisi dan tak lagi bergantung HPP. Angka yang sama sudah kita tampilkan
percaya diri di `KartuKeuangan` dan di laporan PDF; menolak menskornya di sini
berarti produk yang sama tidak sepakat dengan dirinya sendiri. Cakupan HPP tetap
dibawa `HasilSkor` — sebagai **label kejelasan data**, bukan gerbang.

Isolasi tenant (aturan #6): tiap query difilter `business_id`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScoreSnapshot
from app.services.angka import persen, rupiah
from app.services.hpp import cakupan_hpp
from app.services.laba import hitung_laba_periode
from app.services.laporan import tanggal_bercatatan
from app.services.periode import Periode, periode_n_hari

__all__ = [
    "BOBOT",
    "HARI_SKOR",
    "LABEL",
    "HasilSimpanSkor",
    "HasilSkor",
    "Komponen",
    "StatusKomponen",
    "hitung_skor",
    "simpan_snapshot_skor",
    "snapshot_terakhir_skor",
]

# ── Kalibrasi awal ──────────────────────────────────────────────────────────
#
# ⚠️ Angka di blok ini adalah **tebakan berbaju angka** (§4). Yang berhak
# membetulkannya adalah `kur_outcomes` — hasil pengajuan nyata — bukan
# perdebatan internal. Sampai flywheel itu punya data, skor tidak boleh
# dihadapkan ke penyalur. Dikumpulkan di satu tempat supaya kalibrasi ulang
# nanti = mengubah konstanta, bukan membongkar kalkulasi.

HARI_SKOR = 30

BOBOT: dict[str, int] = {
    "konsistensi": 30,
    "margin": 25,
    "tren": 25,
    "prive": 20,
}

LABEL: dict[str, str] = {
    "konsistensi": "Rajin mencatat",
    "margin": "Sisa untung",
    "tren": "Arah omzet",
    "prive": "Disiplin ambilan pribadi",
}

MARGIN_PENUH = Decimal("20")  # margin ≥20% dari omzet = bobot penuh
TREN_NAIK = Decimal("10")  # omzet naik ≥10% = bobot penuh
TREN_TURUN_NOL = Decimal("-50")  # omzet turun ≥50% = nol
TREN_STABIL = Decimal("0.6")  # "stabil" = 60% bobot
PRIVE_PENUH = Decimal("50")  # prive ≤50% laba = bobot penuh
PRIVE_NOL = Decimal("100")  # prive ≥100% laba = nol


class StatusKomponen(str, enum.Enum):
    dihitung = "dihitung"
    belum_diketahui = "belum_diketahui"


@dataclass
class Komponen:
    """Satu komponen skor. `nilai` selalu 0..`bobot`, atau `None` bila tak terhitung.

    `bobot_efektif` = 0 untuk komponen yang tak terhitung — itulah mekanisme
    normalisasinya. `sebab` & `yang_kurang` menerjemahkan ketiadaan data ke
    bahasa warung, supaya pengguna tahu apa yang menaikkannya (§4: transparansi
    = motivasi).
    """

    kunci: str
    label: str
    bobot: int
    bobot_efektif: int
    nilai: int | None
    status: StatusKomponen
    sebab: str = ""
    rincian_tampil: str = ""
    yang_kurang: list[str] = field(default_factory=list)

    @property
    def diketahui(self) -> bool:
        return self.status is StatusKomponen.dihitung


@dataclass
class HasilSkor:
    """Skor + seluruh asal-usulnya. `skor_total` `None` = belum bisa dihitung."""

    periode: Periode
    skor_total: int | None
    komponen: list[Komponen]
    bobot_terpakai: int
    cakupan_hpp_persen: Decimal
    omzet: Decimal
    delta: int | None = None  # selisih terhadap snapshot terakhir, bila ada
    catatan: list[str] = field(default_factory=list)

    @property
    def diketahui(self) -> bool:
        return self.skor_total is not None

    def komponen_json(self) -> dict:
        """Bentuk yang disimpan di `score_snapshots.komponen` (kolom JSON).

        Sengaja menyimpan `bobot` & `status` juga, bukan cuma nilai: saat bobot
        dikalibrasi ulang nanti, snapshot lama harus tetap bisa dibaca dengan
        bobot yang berlaku **saat itu** — kalau tidak, riwayat progres berubah
        surut dan "naik 16 poin" jadi klaim yang tak bisa ditelusuri.
        """
        return {
            k.kunci: {
                "nilai": k.nilai,
                "bobot": k.bobot,
                "bobot_efektif": k.bobot_efektif,
                "status": k.status.value,
            }
            for k in self.komponen
        }


@dataclass
class HasilSimpanSkor:
    snapshot: ScoreSnapshot
    baru: bool  # False = skor tidak berubah, snapshot lama dipakai ulang


# ── Helper ──────────────────────────────────────────────────────────────────


def _persen_dari(pembilang: Decimal, penyebut: Decimal) -> Decimal | None:
    """Persentase bertanda, atau `None` bila penyebutnya tidak bermakna.

    ⛔ Beda sengaja dengan `laba._persen`, yang mengembalikan 0 saat penyebut ≤ 0.
    Di sini 0 berarti "dihitung dan hasilnya nol" — sebuah penilaian. Ketiadaan
    penyebut bukan penilaian, jadi ia harus bisa dibedakan (aturan #2).
    """
    if penyebut <= 0:
        return None
    return (pembilang / penyebut * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _skala(x: Decimal, rendah: Decimal, tinggi: Decimal, bobot: int) -> int:
    """Petakan `x` linear ke 0..`bobot`, dijepit di kedua ujung."""
    if x <= rendah:
        return 0
    if x >= tinggi:
        return bobot
    porsi = (x - rendah) / (tinggi - rendah) * Decimal(bobot)
    return int(porsi.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _belum(kunci: str, sebab: str, yang_kurang: list[str] | None = None) -> Komponen:
    return Komponen(
        kunci=kunci,
        label=LABEL[kunci],
        bobot=BOBOT[kunci],
        bobot_efektif=0,
        nilai=None,
        status=StatusKomponen.belum_diketahui,
        sebab=sebab,
        yang_kurang=yang_kurang or [],
    )


def _terhitung(kunci: str, nilai: int, rincian: str) -> Komponen:
    return Komponen(
        kunci=kunci,
        label=LABEL[kunci],
        bobot=BOBOT[kunci],
        bobot_efektif=BOBOT[kunci],
        nilai=nilai,
        status=StatusKomponen.dihitung,
        rincian_tampil=rincian,
    )


# ── Komponen ────────────────────────────────────────────────────────────────


def _konsistensi(session: Session, business_id: int, p: Periode) -> Komponen:
    """% hari dalam periode yang punya minimal satu catatan.

    **Penyebutnya umur usaha bila usaha lebih muda dari periodenya.** Usaha yang
    baru mencatat 5 hari dan mencatat kelimanya adalah usaha yang rajin — memberi
    5/30 akan menghukumnya untuk hari-hari yang belum pernah ada.
    """
    tanggal = tanggal_bercatatan(session, business_id)
    if not tanggal or tanggal[0] > p.selesai:
        return _belum(
            "konsistensi",
            "Belum ada catatan sama sekali di periode ini.",
            ["catatan transaksi"],
        )

    hari_periode = (p.selesai - p.mulai).days + 1
    umur = (p.selesai - tanggal[0]).days + 1
    penyebut = max(1, min(hari_periode, umur))
    ada = sum(1 for t in tanggal if p.mulai <= t <= p.selesai)

    nilai = _skala(Decimal(ada), Decimal(0), Decimal(penyebut), BOBOT["konsistensi"])
    ekor = " (usaha baru mulai mencatat)" if umur < hari_periode else ""
    return _terhitung("konsistensi", nilai, f"{ada} dari {penyebut} hari ada catatan{ekor}")


def _margin(omzet: Decimal, laba_bersih: Decimal) -> Komponen:
    """Laba bersih ÷ omzet. Tidak digerbangi cakupan HPP (keputusan 2026-07-26)."""
    rasio = _persen_dari(laba_bersih, omzet)
    if rasio is None:
        return _belum(
            "margin",
            "Belum ada penjualan tercatat di periode ini.",
            ["catatan penjualan"],
        )

    nilai = _skala(rasio, Decimal(0), MARGIN_PENUH, BOBOT["margin"])
    return _terhitung(
        "margin",
        nilai,
        f"Sisa {persen(rasio)} dari omzet {rupiah(omzet)}",
    )


def _tren(omzet: Decimal, omzet_lalu: Decimal) -> Komponen:
    """Omzet periode ini vs periode sebelum yang sama panjangnya."""
    delta = _persen_dari(omzet - omzet_lalu, omzet_lalu)
    if delta is None:
        return _belum(
            "tren",
            "Belum ada periode sebelumnya untuk dibandingkan.",
            ["catatan periode sebelumnya"],
        )

    bobot = BOBOT["tren"]
    stabil = int((Decimal(bobot) * TREN_STABIL).quantize(Decimal("1"), ROUND_HALF_UP))
    if delta >= TREN_NAIK:
        nilai, arah = bobot, "naik"
    elif delta > -TREN_NAIK:
        nilai, arah = stabil, "stabil"
    else:
        nilai = _skala(delta, TREN_TURUN_NOL, -TREN_NAIK, stabil)
        arah = "turun"

    return _terhitung(
        "tren",
        nilai,
        f"Omzet {rupiah(omzet)}, sebelumnya {rupiah(omzet_lalu)} ({arah} {persen(abs(delta))})",
    )


def _prive(laba_bersih: Decimal, prive: Decimal, rasio_prive: Decimal | None) -> Komponen:
    """Porsi ambilan pribadi terhadap laba.

    Laba ≤ 0 → `rasio_prive` memang `None` (`laba.py`): membandingkan ambilan
    dengan laba yang tidak ada tak menghasilkan penilaian apa pun, cuma angka
    yang tampak seperti penilaian.
    """
    if laba_bersih <= 0 or rasio_prive is None:
        return _belum(
            "prive",
            "Periode ini belum untung, jadi porsi ambilan pribadi belum bisa dibandingkan.",
            ["periode yang untung"],
        )

    # Turun: 50% → penuh, 100% → nol. `_skala` naik, jadi sumbunya dibalik.
    nilai = _skala(-rasio_prive, -PRIVE_NOL, -PRIVE_PENUH, BOBOT["prive"])
    return _terhitung(
        "prive",
        nilai,
        f"Ambilan pribadi {rupiah(prive)} = {persen(rasio_prive)} dari laba",
    )


# ── Skor ────────────────────────────────────────────────────────────────────


def hitung_skor(
    session: Session,
    business_id: int,
    hari_ini: date,
    mulai: date | None = None,
    selesai: date | None = None,
) -> HasilSkor:
    """Skor kesehatan usaha untuk sebuah periode (default 30 hari bergulir).

    `mulai`/`selesai` eksplisit dipakai apa adanya — periode pembanding tren
    mengambil rentang **sepanjang yang sama** tepat sebelumnya, supaya
    perbandingannya setara.
    """
    if mulai is not None and selesai is not None:
        p = Periode(mulai, selesai, "", "")
    else:
        p = periode_n_hari(HARI_SKOR, hari_ini)

    panjang = (p.selesai - p.mulai).days + 1
    selesai_lalu = p.mulai - timedelta(days=1)
    mulai_lalu = selesai_lalu - timedelta(days=panjang - 1)

    laba = hitung_laba_periode(session, business_id, p.mulai, p.selesai)
    laba_lalu = hitung_laba_periode(session, business_id, mulai_lalu, selesai_lalu)
    cakupan = cakupan_hpp(session, business_id, p.mulai, p.selesai)

    komponen = [
        _konsistensi(session, business_id, p),
        _margin(laba.omzet, laba.laba_bersih),
        _tren(laba.omzet, laba_lalu.omzet),
        _prive(laba.laba_bersih, laba.prive, laba.rasio_prive),
    ]

    bobot_terpakai = sum(k.bobot_efektif for k in komponen)
    if bobot_terpakai == 0:
        skor_total = None
    else:
        raih = sum(k.nilai or 0 for k in komponen)
        skor_total = int(
            (Decimal(raih) / Decimal(bobot_terpakai) * Decimal(100)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    catatan: list[str] = []
    belum = [k for k in komponen if not k.diketahui]
    if belum and skor_total is not None:
        catatan.append(
            "Skor dihitung dari bagian yang datanya sudah ada — "
            f"{len(belum)} dari {len(komponen)} bagian belum bisa dinilai."
        )
    if cakupan.omzet_total > 0 and cakupan.persen < 100:
        catatan.append(
            f"Modal per produk baru terhitung untuk {persen(cakupan.persen)} penjualan. "
            "Melengkapi resep & harga bahan membuat gambarannya lebih utuh."
        )

    return HasilSkor(
        periode=p,
        skor_total=skor_total,
        komponen=komponen,
        bobot_terpakai=bobot_terpakai,
        cakupan_hpp_persen=cakupan.persen,
        omzet=laba.omzet,
        delta=_delta(session, business_id, p, skor_total),
        catatan=catatan,
    )


# ── Snapshot (progres antar periode) ────────────────────────────────────────


def _kunci_periode(p: Periode) -> str:
    """Identitas periode sebuah snapshot: label + tanggal tutupnya.

    Tanggal tutup ikut karena label saja ("30_hari") berbunyi sama tiap hari —
    tanpanya dua snapshot dari minggu berbeda tak bisa dibedakan.
    """
    return f"{p.label or 'lain'}:{p.selesai.isoformat()}"


def snapshot_terakhir_skor(session: Session, business_id: int) -> ScoreSnapshot | None:
    stmt = (
        select(ScoreSnapshot)
        .where(ScoreSnapshot.business_id == business_id)  # aturan #6
        .order_by(ScoreSnapshot.created_at.desc(), ScoreSnapshot.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _delta(session: Session, business_id: int, p: Periode, skor_total: int | None) -> int | None:
    """Selisih terhadap snapshot terakhir dari periode yang **berbeda**.

    Snapshot dengan kunci periode yang sama adalah tulisan kita sendiri untuk
    periode ini; membandingkannya menghasilkan "naik 0 poin" yang tidak
    memberitahu apa pun. Tak ada pembanding → `None`, bukan 0 — nol berarti
    "diukur dan ternyata tetap".
    """
    if skor_total is None:
        return None
    terakhir = snapshot_terakhir_skor(session, business_id)
    if terakhir is None or terakhir.skor_total is None:
        return None
    if terakhir.periode == _kunci_periode(p):
        return None
    return skor_total - terakhir.skor_total


def simpan_snapshot_skor(session: Session, business_id: int, hasil: HasilSkor) -> HasilSimpanSkor:
    """Catat skor apa adanya ke `score_snapshots`.

    **Ditulis juga saat skor belum diketahui** — "belum bisa dihitung pada
    tanggal sekian" adalah riwayat yang sah, dan justru itu yang memperlihatkan
    perbaikan saat pengguna melengkapi datanya.

    **Dedup disengaja**, meniru `hpp.simpan_snapshot_hpp`: bila skor **dan**
    seluruh komponennya tidak berubah, baris lama dipakai ulang. Progres mencari
    *perubahan*; menulis baris identik tiap hari hanya mengubur sinyalnya. Karena
    itu fungsi ini aman dipanggil berulang.
    """
    terakhir = snapshot_terakhir_skor(session, business_id)
    komponen = hasil.komponen_json()
    if (
        terakhir is not None
        and terakhir.skor_total == hasil.skor_total
        and (terakhir.komponen or {}) == komponen
    ):
        return HasilSimpanSkor(snapshot=terakhir, baru=False)

    snapshot = ScoreSnapshot(
        business_id=business_id,
        skor_total=hasil.skor_total,
        komponen=komponen,
        periode=_kunci_periode(hasil.periode),
    )
    session.add(snapshot)
    session.flush()
    return HasilSimpanSkor(snapshot=snapshot, baru=True)

"""Service pencatatan transaksi (Pilar 1) — aksi bervolume tertinggi produk ini.

Deterministik: menerima baris yang **sudah** terekstraksi & terjaga
(`app/llm/ekstraksi.py`), menyimpannya, lalu merangkai kalimat konfirmasi.

⛔ **Konfirmasi dirender dari template kode, bukan panggilan LLM kedua.**
Alasannya biaya — pencatatan terjadi berkali-kali sehari per pengguna, dan
memanggil model untuk sekadar membacakan ulang apa yang baru saja disimpan
adalah pemborosan yang berlipat seiring jumlah pengguna. Efek sampingnya
kebetulan bagus: angka di konfirmasi mustahil meleset dari yang tersimpan,
karena keduanya berasal dari objek yang sama.

Isolasi tenant (aturan #6): `business_id` wajib dan selalu ditulis eksplisit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.skema import AksiKoreksi, BarisTransaksi, Koreksi
from app.models import JenisTransaksi, SumberInput, Transaction
from app.services.angka import _dec, _uang, rupiah
from app.services.entitas import adopsi_pembelian_yatim, cari_produk, resolusi_produk
from app.services.harga import catat_harga_jual_dari_penjualan

__all__ = [
    "HasilKoreksi",
    "HasilPencatatan",
    "daftar_transaksi_periode",
    "daftar_transaksi_terakhir",
    "ringkas_transaksi",
    "simpan_transaksi",
    "terapkan_koreksi",
    "transaksi_terakhir",
]

# Bahasa warung, bukan istilah akuntansi (non-goal: debit/kredit/jurnal).
_SEBUTAN = {
    JenisTransaksi.pemasukan: "Masuk",
    JenisTransaksi.pengeluaran: "Belanja",
    JenisTransaksi.operasional: "Biaya",
    JenisTransaksi.prive: "Dipakai pribadi",
}

_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


@dataclass
class HasilPencatatan:
    tersimpan: list[Transaction] = field(default_factory=list)
    konfirmasi: str = ""


def _tanggal_pendek(t: date) -> str:
    return f"{t.day} {_BULAN[t.month]}"


def _rincian(b: BarisTransaksi) -> str:
    """'5 kotak risol' — bagian yang mungkin kosong seluruhnya."""
    bagian = [
        str(x) for x in (
            _rapi_qty(b.qty) if b.qty is not None else None,
            b.satuan,
            b.produk,
        ) if x
    ]
    return " ".join(bagian)


def _rapi_qty(q: Decimal) -> str:
    d = _dec(q).normalize()
    if d == d.to_integral_value():
        d = d.to_integral_value()
    return f"{d:f}"


def simpan_transaksi(
    session: Session,
    business_id: int,
    baris: list[BarisTransaksi],
    raw_text: str,
    sumber: SumberInput = SumberInput.chat,
) -> HasilPencatatan:
    """Simpan transaksi hasil ekstraksi + rangkai konfirmasinya.

    `raw_text` disimpan apa adanya di tiap baris: kalau pengguna protes
    ("kok jadi segitu?"), kalimat aslinya harus masih ada untuk ditelusuri.
    """
    if not baris:
        return HasilPencatatan(konfirmasi="Belum ada yang dicatat.")

    tersimpan: list[Transaction] = []
    for b in baris:
        t = Transaction(
            business_id=business_id,
            jenis=b.jenis,
            nominal=_uang(_dec(b.nominal)),
            tanggal=b.tanggal,
            deskripsi=b.produk,
            qty=b.qty,
            satuan=b.satuan,
            sumber_input=sumber,
            raw_text=raw_text,
        )
        _tautkan_entitas(session, business_id, t, b)
        session.add(t)
        tersimpan.append(t)
    session.flush()

    return HasilPencatatan(tersimpan=tersimpan, konfirmasi=_konfirmasi(baris))


def _tautkan_entitas(
    session: Session, business_id: int, t: Transaction, b: BarisTransaksi
) -> None:
    """Sambungkan transaksi ke `Product` supaya HPP bisa membacanya (Pilar 1→4).

    Jalur reseller (keputusan pemilik): penjualan melahirkan/menautkan produk &
    menangkap harga jualnya; pembelian menautkan **hanya** ke produk yang sudah
    ada (kulakan barang yang memang dijual). Belanja tak dikenal dibiarkan
    `NULL` — mungkin bahan baku, yang routing-nya (`cost_item_id`) digarap slice
    berikutnya. Operasional & prive bukan barang, tak pernah ditautkan.
    """
    if not b.produk:
        return

    if b.jenis is JenisTransaksi.pemasukan:
        produk, baru = resolusi_produk(session, business_id, b.produk)
        t.product_id = produk.id
        if b.qty is not None and _dec(b.qty) > 0:
            harga_unit = _dec(b.nominal) / _dec(b.qty)
            catat_harga_jual_dari_penjualan(
                session, produk.id, business_id, harga_unit, b.tanggal
            )
        if baru:
            adopsi_pembelian_yatim(session, business_id, produk)
    elif b.jenis is JenisTransaksi.pengeluaran:
        produk = cari_produk(session, business_id, b.produk)
        if produk is not None:
            t.product_id = produk.id


def _konfirmasi(baris: list[BarisTransaksi]) -> str:
    garis = []
    for b in baris:
        potong = [_SEBUTAN[b.jenis], rupiah(_dec(b.nominal))]
        if rincian := _rincian(b):
            potong.append(f"({rincian})")
        potong.append(f"— {_tanggal_pendek(b.tanggal)}")
        garis.append("• " + " ".join(potong))

    kepala = "Sudah dicatat:" if len(baris) == 1 else f"Sudah dicatat {len(baris)}:"
    ekor = _ringkas_masuk_keluar(baris)
    return "\n".join([kepala, *garis] + ([ekor] if ekor else []))


# ── Koreksi: buku append-only ──────────────────────────────────────────────


@dataclass
class HasilKoreksi:
    dibatalkan: Transaction | None = None
    pengganti: Transaction | None = None
    konfirmasi: str = ""


def transaksi_terakhir(session: Session, business_id: int) -> Transaction | None:
    """Baris terakhir yang masih berlaku milik usaha ini.

    Isolasi tenant (aturan #6) ditegakkan di query, bukan diserahkan pemanggil.
    Baris yang sudah dibatalkan tidak pernah jadi sasaran koreksi berikutnya.
    """
    return session.scalars(
        select(Transaction)
        .where(
            Transaction.business_id == business_id,
            Transaction.dibatalkan_pada.is_(None),
        )
        .order_by(Transaction.id.desc())
        .limit(1)
    ).first()


def daftar_transaksi_terakhir(
    session: Session, business_id: int, batas: int = 5
) -> list[Transaction]:
    """`batas` baris terakhir yang masih berlaku milik usaha ini, terbaru dulu.

    Bentuk jamak dari `transaksi_terakhir` — untuk kartu riwayat "lihat catatan
    terakhir". Isolasi tenant (aturan #6) & penyaringan `dibatalkan_pada`
    ditegakkan di query, bukan diserahkan pemanggil: baris yang sudah dibatalkan
    tak pernah tampil, dan buku usaha lain tak pernah ikut terbaca.
    """
    return list(
        session.scalars(
            select(Transaction)
            .where(
                Transaction.business_id == business_id,
                Transaction.dibatalkan_pada.is_(None),
            )
            .order_by(Transaction.id.desc())
            .limit(batas)
        ).all()
    )


def daftar_transaksi_periode(
    session: Session, business_id: int, mulai: date, selesai: date, batas: int = 5
) -> list[Transaction]:
    """`batas` baris terakhir **di dalam rentang tanggal**, terbaru dulu.

    Kembaran berperiode dari `daftar_transaksi_terakhir` — untuk "lihat catatan
    bulan lalu". Isolasi tenant (aturan #6) & `dibatalkan_pada` disaring di
    query, sama seperti kembarannya: pembaca baru yang lupa menyaring tidak
    akan memunculkan error, cuma menghidupkan lagi baris yang sudah dibetulkan.

    Rentang **inklusif** di kedua ujung — sama dengan `hitung_laba_periode` dan
    `cakupan_hpp`, supaya daftar dan angka rekap tak pernah berbeda isi untuk
    periode yang sama.
    """
    return list(
        session.scalars(
            select(Transaction)
            .where(
                Transaction.business_id == business_id,
                Transaction.dibatalkan_pada.is_(None),
                Transaction.tanggal >= mulai,
                Transaction.tanggal <= selesai,
            )
            .order_by(Transaction.id.desc())
            .limit(batas)
        ).all()
    )


def ringkas_transaksi(t: Transaction) -> str:
    """Satu baris DB → kalimat yang bisa dibaca pengguna maupun model."""
    potong = [_SEBUTAN[t.jenis], rupiah(_dec(t.nominal))]
    rincian = " ".join(
        str(x) for x in (
            _rapi_qty(t.qty) if t.qty is not None else None, t.satuan, t.deskripsi
        ) if x
    )
    if rincian:
        potong.append(f"({rincian})")
    potong.append(f"— {_tanggal_pendek(t.tanggal)}")
    return " ".join(potong)


def terapkan_koreksi(
    session: Session,
    business_id: int,
    lama: Transaction,
    koreksi: Koreksi,
    raw_text: str,
) -> HasilKoreksi:
    """Batalkan `lama`; bila `ubah`, catat penggantinya sebagai baris baru.

    ⛔ Tidak pernah menimpa baris lama. Buku ini append-only
    (keputusan.md 2026-07-20): angka yang pernah dilihat pengguna harus tetap
    bisa ditemukan, dan koreksi yang menghapus jejaknya sendiri membuat
    perbedaan laporan mustahil ditelusuri.
    """
    if lama.business_id != business_id:  # sabuk pengaman aturan #6
        raise ValueError("Transaksi bukan milik usaha ini.")

    sebelum = ringkas_transaksi(lama)
    lama.dibatalkan_pada = datetime.now()

    if koreksi.aksi is AksiKoreksi.batal:
        session.flush()
        return HasilKoreksi(
            dibatalkan=lama,
            konfirmasi=f"Sudah dihapus:\n• {sebelum}",
        )

    baru = Transaction(
        business_id=business_id,
        # Kosong = biarkan seperti semula, BUKAN kosongkan.
        jenis=koreksi.jenis or lama.jenis,
        nominal=_uang(_dec(koreksi.nominal)) if koreksi.nominal is not None
        else lama.nominal,
        tanggal=koreksi.tanggal or lama.tanggal,
        deskripsi=koreksi.produk or lama.deskripsi,
        qty=koreksi.qty if koreksi.qty is not None else lama.qty,
        satuan=koreksi.satuan or lama.satuan,
        product_id=lama.product_id,
        cost_item_id=lama.cost_item_id,
        sumber_input=lama.sumber_input,
        raw_text=raw_text,
        koreksi_dari_id=lama.id,
    )
    session.add(baru)
    session.flush()

    return HasilKoreksi(
        dibatalkan=lama,
        pengganti=baru,
        konfirmasi="\n".join([
            "Sudah dibetulkan:",
            f"• {ringkas_transaksi(baru)}",
            f"Sebelumnya: {sebelum}",
        ]),
    )


def _ringkas_masuk_keluar(baris: list[BarisTransaksi]) -> str:
    """Ringkasan hanya ditampilkan bila memang meringkas sesuatu.

    ⛔ Ini BUKAN laba. Sengaja tidak ada pengurangan di sini: laba punya
    definisinya sendiri (`app/services/laba.py`, prive dikecualikan) dan
    menampilkan "masuk − keluar" di konfirmasi akan mengajari pengguna angka
    yang berbeda dari laporan bulanannya.
    """
    if len(baris) < 2:
        return ""
    masuk = sum((_dec(b.nominal) for b in baris if b.jenis is JenisTransaksi.pemasukan),
                Decimal(0))
    keluar = sum((_dec(b.nominal) for b in baris if b.jenis is not JenisTransaksi.pemasukan),
                 Decimal(0))
    bagian = []
    if masuk:
        bagian.append(f"masuk {rupiah(masuk)}")
    if keluar:
        bagian.append(f"keluar {rupiah(keluar)}")
    return "Total: " + ", ".join(bagian) if bagian else ""

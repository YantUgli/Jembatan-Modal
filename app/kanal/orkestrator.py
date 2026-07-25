"""Orchestrator deterministik tipis — memetakan tool/service ke kartu kontrak.

Slice 1 sengaja **tanpa** loop function-calling LLM: adapter yang ada hari ini
adalah permukaan dua-verba (`ekstrak`/`narasikan`). Router intent bahasa-bebas
(`tangani_pesan` → `catat_transaksi`/`tanya_untung`/`tanya_keuangan`) memakai
ulang `ekstrak()` yang sama lewat tool `pilih_aksi` — bukan loop function-calling
baru (keputusan.md 2026-07-22: "Router intent bahasa-bebas"). Di sini kode kita
yang membaca hasil klasifikasi lalu memilih tool, lalu membungkus hasilnya jadi
`PesanKeluar`.

Isolasi tenant (aturan #6): tiap fungsi menerima `business_id` dan setiap query
di sini difilter olehnya — input pengguna dianggap tak tepercaya.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.kontrak import (
    BarisKonfirmasi,
    BarisPos,
    BarisUntung,
    KartuKeuangan,
    KartuKlarifikasi,
    KartuKonfirmasi,
    KartuResep,
    KartuSapaan,
    KartuUntung,
    PesanKeluar,
    PilihanKategori,
)
from app.llm.kontrak import AdapterLLM
from app.llm.skema import AksiKoreksi, AksiRouter, Koreksi
from app.models import Business, JenisTransaksi, Transaction
from app.services.angka import _dec, _rapikan, _uang, rupiah
from app.services.catat import terapkan_koreksi
from app.services.hpp import (
    HasilHpp,
    KonteksHarga,
    StatusHpp,
    cakupan_hpp,
    hitung_hpp_semua,
)
from app.services.laba import hitung_laba_periode
from app.services.resep import HasilAturResep
from app.tools import (
    Klarifikasi,
    Tercatat,
    atur_resep_dari_teks,
    catat_transaksi,
    jawab_harga_bahan,
    pilih_aksi,
)

__all__ = [
    "KonteksTunggu",
    "tangani_pesan",
    "koreksi_kategori",
    "sapaan",
    "kartu_untung",
    "kartu_keuangan",
]


@dataclass
class KonteksTunggu:
    """Token kelanjutan tanya-jawab yang dibawa klien (lihat `KartuResep.menunggu`).

    ⛔ **Tak tepercaya** (aturan #6): `product_id` di sini berasal dari klien dan
    **wajib** divalidasi ulang milik `business_id` sebelum dipakai — dilakukan di
    `jawab_harga_bahan`, bukan diandaikan benar di sini.
    """

    jenis: str  # "harga_bahan"
    product_id: int
    bahan: str

# Badge jenis pada kartu (bahasa warung, bukan istilah akuntansi).
_JENIS_LABEL = {
    JenisTransaksi.pemasukan: "Uang masuk",
    JenisTransaksi.pengeluaran: "Belanja",
    JenisTransaksi.operasional: "Biaya",
    JenisTransaksi.prive: "Dipakai pribadi",
}

# Empat kategori untuk chip koreksi, dalam urutan tetap yang ditentukan kode.
_KATEGORI: list[tuple[JenisTransaksi, str]] = [
    (JenisTransaksi.pemasukan, "Pemasukan"),
    (JenisTransaksi.pengeluaran, "Pengeluaran"),
    (JenisTransaksi.operasional, "Operasional"),
    (JenisTransaksi.prive, "Prive"),
]


# ── Pencatatan ───────────────────────────────────────────────────────────────


def tangani_pesan(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
    konteks: KonteksTunggu | None = None,
) -> PesanKeluar:
    """Satu kalimat pengguna → kartu.

    Bila ada `konteks` tanya-jawab harga (klien menjawab "Harga X berapa?"),
    pesan dicoba dibaca sebagai **jawaban harga** dulu; berhasil → `KartuResep`
    dengan modal ter-update (atau bahan berikutnya yang ditanya). Bila pesannya
    ternyata bukan harga (pengguna ganti topik), ia **jatuh** ke alur normal —
    tak terjebak menunggu.

    Alur normal diarahkan lewat `pilih_aksi` (klasifikasi enum tertutup, bukan
    tool-calling — lihat docstring modul). `tanya_hpp` belum punya rute sendiri:
    dipetakan ke `kartu_untung` (margin per produk) sampai ada kartu HPP yang
    kontraknya benar-benar beda. Tak yakin/tak cocok → default pencatatan
    (Pilar 1), sama seperti perilaku sebelum router ini ada.
    """
    if konteks is not None and konteks.jenis == "harga_bahan":
        dijawab = jawab_harga_bahan(
            session, adapter, business_id, konteks.product_id, konteks.bahan, teks, hari_ini
        )
        if dijawab is not None:
            return PesanKeluar([_kartu_resep(dijawab)])
        # Bukan jawaban harga → teruskan ke alur normal (tak terjebak).

    aksi = pilih_aksi(adapter, teks)
    if aksi is AksiRouter.tanya_untung:
        mulai, selesai = _periode_bulan_berjalan(hari_ini)
        return kartu_untung(session, business_id, mulai, selesai)
    if aksi is AksiRouter.tanya_keuangan:
        mulai, selesai = _periode_bulan_berjalan(hari_ini)
        return kartu_keuangan(session, business_id, mulai, selesai)
    if aksi is AksiRouter.atur_resep:
        hasil_resep = atur_resep_dari_teks(session, adapter, business_id, teks, hari_ini)
        if isinstance(hasil_resep, Klarifikasi):
            return PesanKeluar(
                [KartuKlarifikasi(pertanyaan=hasil_resep.pertanyaan, yang_kurang=hasil_resep.yang_kurang)]
            )
        return PesanKeluar([_kartu_resep(hasil_resep)])

    hasil = catat_transaksi(session, adapter, business_id, teks, hari_ini)
    if isinstance(hasil, Klarifikasi):
        return PesanKeluar(
            [KartuKlarifikasi(pertanyaan=hasil.pertanyaan, yang_kurang=hasil.yang_kurang)]
        )
    return PesanKeluar([_kartu_konfirmasi(session, business_id, hasil)])


def _periode_bulan_berjalan(hari_ini: date) -> tuple[date, date]:
    """Awal bulan berjalan s/d hari ini — default yang sama dengan jalur chip
    (`_periode` di app/api/main.py) saat `mulai`/`selesai` tak disebut."""
    return hari_ini.replace(day=1), hari_ini


def koreksi_kategori(
    session: Session,
    business_id: int,
    transaksi_id: int,
    jenis: JenisTransaksi,
) -> PesanKeluar:
    """Ketuk chip kategori → betulkan jenis transaksi.

    Aksi terstruktur (bukan bahasa natural), jadi kita memanggil service
    `terapkan_koreksi` langsung tanpa melibatkan LLM — jenis sasarannya sudah
    pasti. Tetap append-only: baris lama ditandai batal, penggantinya baris baru
    (keputusan.md 2026-07-20).
    """
    lama = _ambil_milik(session, business_id, transaksi_id)
    if lama is None:
        return PesanKeluar(
            [KartuKlarifikasi(pertanyaan="Catatan itu tidak ketemu — mungkin sudah dibetulkan.")]
        )
    if lama.jenis is jenis:  # tidak berubah → cukup gambar ulang kartunya
        return PesanKeluar(
            [
                KartuKonfirmasi(
                    baris=[_baris(lama)],
                    ids=[lama.id],
                    konfirmasi="Kategorinya memang sudah itu, Bu.",
                )
            ]
        )

    terap = terapkan_koreksi(
        session,
        business_id,
        lama,
        Koreksi(aksi=AksiKoreksi.ubah, jenis=jenis),
        raw_text="(ketuk chip kategori)",
    )
    pengganti = terap.pengganti
    assert pengganti is not None  # aksi `ubah` selalu menghasilkan pengganti
    return PesanKeluar(
        [
            KartuKonfirmasi(
                baris=[_baris(pengganti)],
                ids=[pengganti.id],
                konfirmasi=terap.konfirmasi,
            )
        ]
    )


# ── Sapaan & stub ────────────────────────────────────────────────────────────


def sapaan(business: Business, salam: str = "Selamat datang") -> PesanKeluar:
    """Kartu pembuka, diturunkan dari data usaha (bukan hardcode di UI)."""
    sub = " · ".join(x for x in (business.jenis_usaha, business.lokasi) if x)
    return PesanKeluar(
        [
            KartuSapaan(
                nama_usaha=business.nama_usaha,
                sub=sub,
                salam=salam,
                ajakan=(
                    "Ada yang laku hari ini? Ceritakan saja seperti biasa — nanti saya "
                    "bantu catat dan hitung untungnya."
                ),
                catatan_jujur=(
                    "Angka Ibu tidak pernah saya karang. Kalau modalnya belum ketahuan, "
                    "saya bilang apa adanya — belum tahu."
                ),
            )
        ]
    )


# Terjemahan status HPP → satu kalimat bahasa warung (bukan istilah teknis).
# Dipakai saat modal per porsi belum bisa dihitung — aturan #2: mengaku, bukan
# mengarang angka nol.
_SEBAB_HPP = {
    StatusHpp.belum_ada_resep: "resepnya belum diatur",
    StatusHpp.harga_tidak_lengkap: "ada bahan yang harganya belum tercatat",
    StatusHpp.belum_ada_harga_beli: "belum ada catatan belanja barang ini",
    StatusHpp.satuan_tidak_cocok: "satuan takaran resep beda dengan satuan harganya",
    StatusHpp.subproduk_tidak_lengkap: "ada bahan setengah jadi yang belum lengkap",
    StatusHpp.resep_melingkar: "resepnya berputar memakai dirinya sendiri",
    StatusHpp.tipe_belum_didukung: "ada komponen biaya yang belum didukung",
}


def _persen(d) -> str:
    """0..100 (Decimal) → '78%' / '78.5%'. Bukan uang, jadi bukan rupiah()."""
    return f"{_rapikan(_dec(d))}%"


def _baris_untung(h: HasilHpp) -> BarisUntung:
    """`HasilHpp` service → baris kartu. Angka apa adanya; None tetap None.

    ⛔ Tidak ada aritmatika di sini (aturan #1) — semua angka sudah dihitung
    service; kita hanya memformat & memilih kata.
    """
    if h.status is StatusHpp.lengkap:
        return BarisUntung(
            nama=h.nama,
            jenis=h.jenis,
            diketahui=True,
            hpp_tampil=rupiah(h.hpp_per_unit) if h.hpp_per_unit is not None else None,
            satuan_hpp=h.satuan_hpp,
            harga_jual_tampil=(rupiah(h.harga_jual) if h.harga_jual is not None else None),
            laba_kotor_tampil=(
                rupiah(h.laba_kotor_per_unit) if h.laba_kotor_per_unit is not None else None
            ),
        )

    # Belum bisa dihitung: apa yang kurang diambil dari daftar konkret service
    # (nama bahan / bentrokan satuan), bukan dikarang.
    yang_kurang = list(h.bahan_kurang_harga) + list(h.satuan_bertabrakan)
    return BarisUntung(
        nama=h.nama,
        jenis=h.jenis,
        diketahui=False,
        harga_jual_tampil=rupiah(h.harga_jual) if h.harga_jual is not None else None,
        sebab=_SEBAB_HPP.get(h.status, "datanya belum lengkap"),
        yang_kurang=yang_kurang,
    )


def kartu_untung(
    session: Session,
    business_id: int,
    mulai: date,
    selesai: date,
    konteks: KonteksHarga | None = None,
) -> PesanKeluar:
    """Laba kotor **dari bahan** per porsi, per produk (Pilar 4).

    ⛔ Aturan #9: ini BUKAN untung usaha — itu angka lain (`kartu_keuangan`), dan
    keduanya tidak pernah dilebur. `cakupan` (aturan #2) menyertakan berapa persen
    penjualan yang modalnya sudah terhitung. Angka datang dari service HPP; kanal
    tidak berhitung.
    """
    hasil = hitung_hpp_semua(session, business_id, konteks)
    cak = cakupan_hpp(session, business_id, mulai, selesai)
    baris = [_baris_untung(h) for h in hasil]

    diketahui = sum(1 for b in baris if b.diketahui)
    if not baris:
        status = "belum_diketahui"
    elif diketahui == len(baris):
        status = "lengkap"
    elif diketahui == 0:
        status = "belum_diketahui"
    else:
        status = "sebagian"

    if not baris:
        pesan = (
            "Belum ada produk yang tercatat, jadi modal per porsi belum bisa "
            "dihitung. Begitu Ibu catat penjualan dengan nama barangnya, saya "
            "mulai hitung untung kotornya."
        )
    else:
        pesan = (
            "Ini untung kotor dari bahan per porsi — belum dikurangi biaya lain "
            "seperti gas, listrik, dan tenaga. Angka untung yang sudah dikurangi "
            "semua biaya ada di laporan singkat."
        )
        if cak.omzet_total > 0:
            pesan += f" Modal bahan sudah terhitung untuk {_persen(cak.persen)} penjualan."

    return PesanKeluar(
        [
            KartuUntung(
                pesan=pesan,
                produk=baris,
                cakupan_tampil=_persen(cak.persen) if cak.omzet_total > 0 else "",
                status=status,
            )
        ]
    )


def kartu_keuangan(session: Session, business_id: int, mulai: date, selesai: date) -> PesanKeluar:
    """Untung usaha periode — **angka utama** (aturan #9, keputusan "dua angka").

    Omzet − (belanja + operasional) = laba bersih; prive dikecualikan. Angka dari
    `hitung_laba_periode`; cakupan HPP disertakan (aturan #2). ⛔ Tanpa skor
    komposit. Catatan ditulis ulang di bahasa warung (bukan istilah "basis kas").
    """
    laba = hitung_laba_periode(session, business_id, mulai, selesai)
    cak = cakupan_hpp(session, business_id, mulai, selesai)

    ada_data = not (laba.omzet == 0 and laba.biaya_total == 0 and laba.prive == 0)

    catatan: list[str] = []
    if not ada_data:
        catatan.append(f"Belum ada catatan untuk {_periode(mulai, selesai)}.")
    else:
        # Terjemahan "basis kas" ke bahasa warung — jangan pakai jargonnya.
        catatan.append(
            "Hitungan ini apa adanya dari catatan: kalau ada belanja yang barangnya "
            "baru laku bulan depan, tetap ikut kehitung bulan ini."
        )
    if laba.prive > 0:
        catatan.append(
            "Uang yang Ibu ambil untuk keperluan pribadi tidak dihitung sebagai "
            "biaya usaha — dicatat terpisah."
        )
    if laba.laba_bersih < 0:
        catatan.append("Bulan ini pengeluaran lebih besar daripada pemasukan.")

    return PesanKeluar(
        [
            KartuKeuangan(
                periode_tampil=_periode(mulai, selesai),
                omzet_tampil=rupiah(laba.omzet),
                belanja_tampil=rupiah(laba.belanja),
                operasional_tampil=rupiah(laba.operasional),
                biaya_tampil=rupiah(laba.biaya_total),
                laba_bersih_tampil=rupiah(laba.laba_bersih),
                untung=laba.untung,
                ada_data=ada_data,
                cakupan_tampil=_persen(cak.persen) if cak.omzet_total > 0 else "",
                prive_tampil=rupiah(laba.prive) if laba.prive > 0 else None,
                rasio_prive_tampil=(
                    _persen(laba.rasio_prive) if laba.rasio_prive is not None else None
                ),
                pos_biaya=[
                    BarisPos(
                        kategori=p.kategori,
                        jenis=p.jenis,
                        nominal_tampil=rupiah(p.nominal),
                    )
                    for p in laba.pos_biaya[:5]
                ],
                catatan=catatan,
            )
        ]
    )


_BULAN = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _periode(mulai: date, selesai: date) -> str:
    """'1–21 Jul 2026', atau '18 Mei–21 Jul 2026' bila beda bulan."""
    if mulai.year == selesai.year and mulai.month == selesai.month:
        return f"{mulai.day}–{selesai.day} {_BULAN[selesai.month]} {selesai.year}"
    kiri = f"{mulai.day} {_BULAN[mulai.month]}"
    if mulai.year != selesai.year:
        kiri += f" {mulai.year}"
    return f"{kiri}–{selesai.day} {_BULAN[selesai.month]} {selesai.year}"


# ── Pembangun kartu ──────────────────────────────────────────────────────────


def _kartu_resep(hasil: HasilAturResep) -> KartuResep:
    """`HasilAturResep` service → kartu resep. Angka apa adanya (aturan #1) —
    tak ada aritmatika di sini; HPP sudah dihitung service.

    Bila masih ada bahan tanpa harga, `menunggu` menyimpan bahan **berikutnya**
    yang ditanya (satu per giliran) sebagai token kelanjutan; klien
    melampirkannya ke pesan jawaban. `product_id` di token divalidasi ulang
    server saat jawaban datang (aturan #6).
    """
    hpp = hasil.hpp
    lengkap = hpp.status is StatusHpp.lengkap and hpp.hpp_per_unit is not None
    menunggu = (
        {"product_id": hasil.product_id, "bahan": hasil.bahan_perlu_harga[0]}
        if not lengkap and hasil.bahan_perlu_harga
        else None
    )
    return KartuResep(
        product_id=hasil.product_id,
        nama=hasil.nama,
        status="lengkap" if lengkap else "belum",
        konfirmasi=hasil.konfirmasi,
        modal_tampil=rupiah(hpp.hpp_per_unit) if lengkap else None,
        satuan_hpp=hpp.satuan_hpp,
        bahan_perlu_harga=list(hasil.bahan_perlu_harga),
        menunggu=menunggu,
    )


def _kartu_konfirmasi(session: Session, business_id: int, hasil: Tercatat) -> KartuKonfirmasi:
    """Baca-balik transaksi yang baru dibuat → isi baris terstruktur.

    Dibaca ulang dari DB (difilter `business_id`) supaya angka di kartu berasal
    dari baris tersimpan, bukan dari teks pengguna.
    """
    rows = session.scalars(
        select(Transaction).where(
            Transaction.id.in_(hasil.ids),
            Transaction.business_id == business_id,
        )
    ).all()
    by_id = {r.id: r for r in rows}
    baris = [_baris(by_id[i]) for i in hasil.ids if i in by_id]
    return KartuKonfirmasi(baris=baris, ids=hasil.ids, konfirmasi=hasil.konfirmasi)


def _baris(t: Transaction) -> BarisKonfirmasi:
    return BarisKonfirmasi(
        jenis=t.jenis.value,
        jenis_label=_JENIS_LABEL[t.jenis],
        nominal_tampil=rupiah(_dec(t.nominal)),
        nominal=str(_uang(_dec(t.nominal))),
        produk=t.deskripsi,
        qty_tampil=_qty_tampil(t),
        transaksi_id=t.id,
        kategori_pilihan=[
            PilihanKategori(nilai=j.value, label=label, aktif=(t.jenis is j))
            for j, label in _KATEGORI
        ],
    )


def _qty_tampil(t: Transaction) -> str | None:
    """'5 kotak' dari qty+satuan; None bila takaran tak dicatat."""
    if t.qty is None:
        return None
    d = _dec(t.qty).normalize()
    if d == d.to_integral_value():
        d = d.to_integral_value()
    angka = f"{d:f}"
    return " ".join(x for x in (angka, t.satuan) if x)


def _ambil_milik(session: Session, business_id: int, transaksi_id: int) -> Transaction | None:
    """Ambil transaksi HANYA bila milik usaha ini & masih berlaku (aturan #6).

    Difilter di query, bukan diperiksa setelah diambil.
    """
    return session.scalars(
        select(Transaction).where(
            Transaction.id == transaksi_id,
            Transaction.business_id == business_id,
            Transaction.dibatalkan_pada.is_(None),
        )
    ).first()

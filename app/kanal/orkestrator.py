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

from app.impor import MAKS_BARIS, TerlaluBanyakBaris, tampak_tempelan
from app.kanal.kontrak import (
    BarisImpor,
    BarisKomponen,
    BarisKonfirmasi,
    BarisPos,
    BarisRingkas,
    BarisUntung,
    KartuBelumDiketahui,
    KartuDokumen,
    KartuImpor,
    KartuKeuangan,
    KartuKlarifikasi,
    KartuKonfirmasi,
    KartuPanduanKur,
    KartuResep,
    KartuRiwayat,
    KartuSapaan,
    KartuSkor,
    KartuUntung,
    PesanKeluar,
    PilihanKategori,
)
from app.llm.kontrak import AdapterLLM
from app.llm.skema import AksiKoreksi, AksiRouter, Koreksi
from app.models import Business, JenisTransaksi, Transaction
from app.services.angka import _dec, _uang, persen as _persen, rupiah
from app.services.catat import (
    daftar_transaksi_periode,
    daftar_transaksi_terakhir,
    terapkan_koreksi,
)
from app.services.hpp import (
    HasilHpp,
    KonteksHarga,
    StatusHpp,
    cakupan_hpp,
    hitung_hpp_semua,
    simpan_snapshot_semua,
)
from app.services.impor import (
    BarisTinjau,
    RingkasanTinjau,
    konfirmasi_impor,
    putuskan_baris,
    terima_yakin,
    tinjau_impor,
)
from app.services.laba import hitung_laba_periode
from app.services.panduan_kur import KonteksBunga, Penolakan, jawab_bunga_kur, jawab_panduan
from app.services.periode import Periode, baca_periode, menyebut_masa_depan
from app.services.resep import HasilAturResep
from app.services.skor import hitung_skor
from app.services.tanggal import periode_tampil as _periode
from app.services.tanggal import tgl_pendek as _tgl_pendek
from app.tools import (
    Klarifikasi,
    Tercatat,
    Terkoreksi,
    atur_resep_dari_teks,
    buat_laporan,
    catat_transaksi,
    impor_dari_teks,
    jawab_harga_bahan,
    koreksi_transaksi,
    pilih_aksi,
)

__all__ = [
    "KonteksTunggu",
    "tangani_pesan",
    "koreksi_kategori",
    "sapaan",
    "kartu_untung",
    "kartu_keuangan",
    "kartu_laporan",
    "kartu_riwayat",
    "kartu_skor",
    "kartu_impor_teks",
    "kartu_impor_tinjau",
    "kartu_impor_putuskan",
    "kartu_impor_terima_yakin",
    "kartu_impor_konfirmasi",
    "kartu_panduan_kur",
]


@dataclass
class KonteksTunggu:
    """Token kelanjutan yang dibawa klien — server tetap stateless.

    Dua jenis sejauh ini:
    - `"harga_bahan"` — jawaban atas "Harga X berapa?" (lihat `KartuResep.menunggu`);
      memakai `product_id` + `bahan`.
    - `"koreksi_sasaran"` — pengguna menunjuk baris tertentu di kartu riwayat
      ("Betulkan") lalu mengetik apa yang benar; memakai `transaksi_id`.

    ⛔ **Tak tepercaya** (aturan #6): id di sini berasal dari klien dan **wajib**
    divalidasi ulang milik `business_id` di query — dilakukan di
    `jawab_harga_bahan` / `koreksi_transaksi`, bukan diandaikan benar di sini.
    """

    jenis: str  # "harga_bahan" | "koreksi_sasaran"
    product_id: int | None = None
    bahan: str | None = None
    transaksi_id: int | None = None


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

    Bila `konteks` menunjuk baris tertentu ("Betulkan" di kartu riwayat), pesan
    dibaca sebagai **koreksi atas baris itu**; tak terbaca sebagai koreksi → ikut
    jatuh ke alur normal.

    **Tempelan banyak baris dibelokkan ke jalur draft impor** sebelum router
    dipanggil — lihat `_tempelan_ke_draft`.

    Alur normal diarahkan lewat `pilih_aksi` (klasifikasi enum tertutup, bukan
    tool-calling — lihat docstring modul). `tanya_hpp` belum punya rute sendiri:
    dipetakan ke `kartu_untung` (margin per produk) sampai ada kartu HPP yang
    kontraknya benar-benar beda. Tak yakin/tak cocok → default pencatatan
    (Pilar 1), sama seperti perilaku sebelum router ini ada.
    """
    if konteks is not None and konteks.jenis == "harga_bahan":
        if konteks.product_id is not None and konteks.bahan:
            dijawab = jawab_harga_bahan(
                session, adapter, business_id, konteks.product_id, konteks.bahan, teks, hari_ini
            )
            if dijawab is not None:
                return PesanKeluar([_kartu_resep(dijawab)])
        # Bukan jawaban harga → teruskan ke alur normal (tak terjebak).

    # Sasaran koreksi yang ditunjuk pengguna. Dicoba lebih dulu daripada router:
    # niatnya sudah eksplisit (ia mengetuk "Betulkan"), jadi kalimat sependek
    # "57rb" pun bermakna di sini padahal tak berarti apa-apa bagi router.
    tertunda: Klarifikasi | None = None
    if konteks is not None and konteks.jenis == "koreksi_sasaran" and konteks.transaksi_id:
        # Aturan #6: id dari klien divalidasi di query sebelum satu pun panggilan
        # model. Sasaran asing/sudah batal → berhenti di sini, jangan jatuh ke
        # alur normal — kalimat koreksi tak boleh berubah jadi catatan baru.
        sasaran = _ambil_milik(session, business_id, konteks.transaksi_id)
        if sasaran is None:
            return PesanKeluar(
                [
                    KartuKlarifikasi(
                        pertanyaan="Catatan itu tidak ketemu — mungkin sudah dibetulkan."
                    )
                ]
            )
        dikoreksi = koreksi_transaksi(session, adapter, business_id, teks, hari_ini, sasaran.id)
        if not isinstance(dikoreksi, Klarifikasi):
            return PesanKeluar([_kartu_koreksi(session, business_id, dikoreksi)])
        # Tak terbaca sebagai koreksi → alur normal (tak terjebak). Pertanyaan
        # baliknya disimpan supaya tidak memanggil model dua kali untuk hal sama.
        tertunda = dikoreksi

    # ⛔ Aturan #3, dan pagarnya harus berdiri DI SINI. Kotak chat adalah tempat
    # tempelan benar-benar terjadi: seseorang menempel satu halaman buku tulis
    # dari WhatsApp, router mengklasifikasinya `catat_transaksi`, lalu
    # `simpan_transaksi` menuliskan tiga puluh baris langsung ke buku. Itu impor
    # yang auto-commit tanpa pernah disebut impor — larangan yang hidup hanya di
    # tool `impor` akan dilewati begitu saja lewat pintu ini.
    if tampak_tempelan(teks):
        return _tempelan_ke_draft(session, adapter, business_id, teks, hari_ini)

    aksi = pilih_aksi(adapter, teks)

    # Periode dibaca **setelah** router, dan hanya untuk kalimat pertanyaan.
    # ⛔ Jangan pernah menariknya ke atas: di jalur pencatatan tanggal adalah
    # ISI transaksi ("kemarin jual bakso 400rb") dan sudah diurus ekstraksi —
    # membacanya sebagai kueri periode akan mengubah catatan jadi pertanyaan.
    if aksi in _AKSI_BERPERIODE:
        if menyebut_masa_depan(teks, hari_ini):
            return PesanKeluar([KartuKlarifikasi(pertanyaan=_TANYA_MASA_DEPAN)])
        p = baca_periode(teks, hari_ini)
        if aksi is AksiRouter.lihat_transaksi:
            return kartu_riwayat(session, business_id, periode=p)
        mulai, selesai = (p.mulai, p.selesai) if p else _periode_bulan_berjalan(hari_ini)
        label = p.label if p else "bulan_ini"
        if aksi is AksiRouter.tanya_untung:
            return kartu_untung(session, business_id, mulai, selesai, label=label)
        return kartu_keuangan(session, business_id, mulai, selesai, label=label)

    if aksi is AksiRouter.koreksi_transaksi:
        if tertunda is not None:
            return PesanKeluar(
                [KartuKlarifikasi(pertanyaan=tertunda.pertanyaan, yang_kurang=tertunda.yang_kurang)]
            )
        dikoreksi = koreksi_transaksi(session, adapter, business_id, teks, hari_ini)
        if isinstance(dikoreksi, Klarifikasi):
            return PesanKeluar(
                [
                    KartuKlarifikasi(
                        pertanyaan=dikoreksi.pertanyaan, yang_kurang=dikoreksi.yang_kurang
                    )
                ]
            )
        return PesanKeluar([_kartu_koreksi(session, business_id, dikoreksi)])
    if aksi is AksiRouter.atur_resep:
        hasil_resep = atur_resep_dari_teks(session, adapter, business_id, teks, hari_ini)
        if isinstance(hasil_resep, Klarifikasi):
            return PesanKeluar(
                [
                    KartuKlarifikasi(
                        pertanyaan=hasil_resep.pertanyaan, yang_kurang=hasil_resep.yang_kurang
                    )
                ]
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


# Tiga jalur yang menjawab **pertanyaan** — satu-satunya tempat periode boleh
# dibaca dari kalimat.
_AKSI_BERPERIODE = frozenset(
    {AksiRouter.tanya_untung, AksiRouter.tanya_keuangan, AksiRouter.lihat_transaksi}
)

# Kartu berisi nol untuk hari yang belum terjadi tampak seperti hasil hitungan,
# padahal tak ada yang dihitung — jadi bertanya balik, bukan menjawab (aturan #2).
_TANYA_MASA_DEPAN = (
    "Hari itu belum terjadi, jadi catatannya belum ada. "
    "Mau saya tampilkan bulan ini, bulan lalu, atau 3 bulan terakhir?"
)


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
                dibatalkan_id=lama.id,
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
    label: str = "",
) -> PesanKeluar:
    """Laba kotor **dari bahan** per porsi, per produk (Pilar 4).

    ⛔ Aturan #9: ini BUKAN untung usaha — itu angka lain (`kartu_keuangan`), dan
    keduanya tidak pernah dilebur. `cakupan` (aturan #2) menyertakan berapa persen
    penjualan yang modalnya sudah terhitung. Angka datang dari service HPP; kanal
    tidak berhitung.

    Tanpa `konteks`, harga jual yang dipakai adalah harga yang berlaku di
    **akhir periode**, bukan hari ini. `harga_jual_berlaku` jatuh ke `today()`
    bila tanggalnya kosong — jadi sebelum ini "untung bulan Juni" dihitung
    dengan harga jual hari ini, persis kelas kesalahan yang tabel
    `product_prices` (append-only, `berlaku_dari`) dibangun untuk mencegah.
    Konsekuensi jujurnya: produk yang harganya baru tercatat setelah periode itu
    jadi `belum_diketahui` untuk periode lampau — memang belum diketahui.
    """
    hasil = hitung_hpp_semua(session, business_id, konteks or KonteksHarga(tanggal=selesai))
    simpan_snapshot_semua(session, business_id)
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
                periode_tampil=_periode(mulai, selesai),
                periode_label=label,
                produk=baris,
                cakupan_tampil=_persen(cak.persen) if cak.omzet_total > 0 else "",
                status=status,
            )
        ]
    )


def kartu_keuangan(
    session: Session, business_id: int, mulai: date, selesai: date, label: str = ""
) -> PesanKeluar:
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
        # Kalimat ini dulu berbunyi "bulan ini" — benar selama kartu cuma bisa
        # menampilkan bulan berjalan. Begitu periodenya bisa apa saja, "bulan ini"
        # jadi keterangan yang salah tentang angka di sebelahnya.
        catatan.append(
            "Hitungan ini apa adanya dari catatan: kalau ada belanja yang barangnya "
            "baru laku belakangan, tetap ikut kehitung di periode ini."
        )
    if laba.prive > 0:
        catatan.append(
            "Uang yang Ibu ambil untuk keperluan pribadi tidak dihitung sebagai "
            "biaya usaha — dicatat terpisah."
        )
    if laba.laba_bersih < 0:
        catatan.append("Di periode ini pengeluaran lebih besar daripada pemasukan.")

    return PesanKeluar(
        [
            KartuKeuangan(
                periode_tampil=_periode(mulai, selesai),
                periode_label=label,
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


def kartu_laporan(
    session: Session,
    business: Business,
    hari_ini: date,
    mulai: date | None = None,
    selesai: date | None = None,
) -> PesanKeluar:
    """Buat laporan PDF → kartu tanda terima berisi tautan unduh (Pilar 3).

    Dijangkau lewat **aksi terstruktur** (tombol), bukan label router. Membuat
    dokumen adalah tindakan sengaja, bukan pertanyaan sambil lalu — dan kalimat
    seperti *"laporan singkat dong"* sudah lama berarti `tanya_keuangan`
    (kartu di layar). Menambahkan label router yang bersaing dengannya akan
    membuat pengguna kadang dapat PDF saat ia cuma ingin melihat angka.

    ⛔ Kartu ini tak pernah memuat skor komposit (aturan #9), dan **selalu**
    menyebut cakupan HPP (aturan #2) — pengguna tahu seberapa dalam angka yang
    akan dibaca penyalur sebelum membuka berkasnya.
    """
    hasil = buat_laporan(session, business, hari_ini, mulai=mulai, selesai=selesai)
    r = hasil.ringkasan
    ringkasan = [
        BarisRingkas(label="Omzet", nilai_tampil=rupiah(r.total.omzet)),
        BarisRingkas(label="Untung usaha", nilai_tampil=rupiah(r.total.laba_bersih)),
        BarisRingkas(
            label="Modal bahan terhitung",
            nilai_tampil=(
                _persen(r.cakupan.persen) if r.cakupan.omzet_total > 0 else "belum diketahui"
            ),
        ),
        BarisRingkas(label="Bulan tercatat", nilai_tampil=f"{r.fakta.bulan_bercatatan} bulan"),
    ]
    return PesanKeluar(
        [
            KartuDokumen(
                judul="Laporan keuangan",
                periode_tampil=r.periode_tampil,
                url_unduh=f"/api/dokumen/{hasil.document_id}",
                pesan=(
                    "Laporan Ibu sudah jadi. Isinya catatan apa adanya: omzet, "
                    "biaya, untung usaha, dan seberapa banyak modal bahan yang "
                    "sudah ketahuan."
                ),
                ringkasan=ringkasan,
                catatan=[
                    "Ini alat bantu persiapan, bukan jaminan pinjaman disetujui.",
                    "Angka yang belum ketahuan tidak saya karang — di laporan pun "
                    "ditulis apa adanya.",
                ],
            )
        ]
    )


def kartu_skor(
    session: Session,
    business_id: int,
    hari_ini: date,
    mulai: date | None = None,
    selesai: date | None = None,
    label: str = "",
) -> PesanKeluar:
    """Rapor usaha — skor komposit + rincian per komponen (Tahap 4b).

    ⛔ **Aturan #9:** keluaran pengguna. Kartu ini tidak pernah punya jalan ke
    laporan PDF / proposal KUR; yang berangkat ke sana `FaktaPenyalur`.

    Nol aritmatika di sini — seluruh angka datang jadi dari `hitung_skor`
    (aturan #1). Snapshot **sengaja tidak** ditulis di jalur baca ini: melihat
    rapor bukan peristiwa yang mengubah riwayat, dan menulis tiap kali kartu
    dibuka akan mengubur sinyal progres yang justru ingin ditampilkan.
    """
    hasil = hitung_skor(session, business_id, hari_ini, mulai=mulai, selesai=selesai)
    periode_tampil = _periode(hasil.periode.mulai, hasil.periode.selesai)

    if not hasil.diketahui:
        return PesanKeluar(
            [
                KartuBelumDiketahui(
                    judul=f"Rapor usaha — {periode_tampil}",
                    alasan=(
                        "Belum ada yang bisa dinilai untuk periode ini. Begitu Ibu "
                        "mulai mencatat penjualan dan belanja, rapornya langsung terisi."
                    ),
                    yang_kurang=sorted({k for komp in hasil.komponen for k in komp.yang_kurang}),
                )
            ]
        )

    return PesanKeluar(
        [
            KartuSkor(
                periode_tampil=periode_tampil,
                periode_label=label or hasil.periode.label,
                skor_tampil=f"{hasil.skor_total} dari 100",
                skor_total=hasil.skor_total,
                bobot_terpakai=hasil.bobot_terpakai,
                cakupan_tampil=(_persen(hasil.cakupan_hpp_persen) if hasil.omzet > 0 else ""),
                delta_tampil=_delta_tampil(hasil.delta),
                komponen=[
                    BarisKomponen(
                        kunci=k.kunci,
                        label=k.label,
                        bobot=k.bobot,
                        nilai=k.nilai,
                        status=k.status.value,
                        sebab=k.sebab,
                        rincian_tampil=k.rincian_tampil,
                        yang_kurang=k.yang_kurang,
                    )
                    for k in hasil.komponen
                ],
                catatan=[
                    *hasil.catatan,
                    "Nilai ini untuk Ibu sendiri — buat lihat kemajuan. Yang dibawa "
                    "ke bank tetap catatan apa adanya, bukan nilai ini.",
                ],
            )
        ]
    )


_DISCLAIMER_KUR = (
    "Ini panduan umum berdasarkan regulasi yang berlaku, bukan jaminan pengajuan "
    "KUR disetujui. Keputusan akhir tetap di bank/lembaga penyalur."
)


def kartu_panduan_kur(
    session: Session, konteks: KonteksBunga | None = None, *, topik: str = "bunga"
) -> PesanKeluar:
    """Panduan KUR — jawaban HANYA dari `panduan_entries` aktif (Tahap 4c, C1+C2).

    Aksi terstruktur (chip/form: `topik_kur` + slot per topik), bukan label
    router bahasa-bebas — sama seperti `kartu_skor` (keputusan.md 2026-07-22/
    2026-07-27): menambah label ke tujuh ke `AksiRouter` berisiko menggeser
    akurasi enam label yang sudah ada. **Status ekspor tidak pernah disimpulkan
    kode** (Lampiran A.4 rencana eksekusi) — ia datang sebagai input eksplisit
    dari pengguna, bukan tebakan dari kata "ekspor" di kalimat.

    `topik="bunga"` (default) bercabang kategori × sektor × ekspor lewat
    `konteks` (`KonteksBunga`). Topik lain (mis. `"agunan"`, keputusan.md
    2026-07-28 E2) tidak bercabang sama sekali — cukup `jawab_panduan`
    generik, `konteks` diabaikan. ⚠️ Agunan di sini **plafon-agnostik**: belum
    menjawab pertanyaan bernominal ("pinjam 200jt, butuh agunan?") — lihat
    docstring `app/seeds/panduan_kur_agunan.py` untuk follow-up bernama.

    ⛔ Aturan #1/#4: nol aritmatika/angka literal di sini. `jawab_bunga_kur`/
    `jawab_panduan` adalah satu-satunya jalan ke isi — entri `draft`/
    `superseded`/sumber tak-tepercaya sudah ditolak di lapisan guard sebelum
    sampai fungsi ini. Konteks kosong/parsial (topik bunga) selalu berujung
    `KartuKlarifikasi` yang meminta slot yang kurang (I6), tak pernah tebakan
    atau `bunga-overview` sebagai jawaban tarif final.
    """
    hasil = (
        jawab_bunga_kur(session, konteks or KonteksBunga())
        if topik == "bunga"
        else jawab_panduan(session, topik)
    )
    if isinstance(hasil, Penolakan):
        return PesanKeluar([KartuKlarifikasi(pertanyaan=hasil.alasan)])
    return PesanKeluar(
        [
            KartuPanduanKur(
                isi=hasil.isi,
                sumber_url=hasil.sumber_url,
                pasal_rujukan=hasil.pasal_rujukan,
                versi_regulasi=hasil.versi_regulasi,
                catatan=[_DISCLAIMER_KUR],
            )
        ]
    )


def _delta_tampil(delta: int | None) -> str | None:
    """Progres sejak rapor terakhir. `None` = belum ada pembanding, jangan
    ditulis "tetap" — itu klaim pengukuran yang tak pernah dilakukan."""
    if delta is None:
        return None
    if delta == 0:
        return "sama seperti rapor terakhir"
    arah = "naik" if delta > 0 else "turun"
    return f"{arah} {abs(delta)} poin sejak rapor terakhir"


def kartu_riwayat(
    session: Session, business_id: int, batas: int = 5, periode: Periode | None = None
) -> PesanKeluar:
    """Daftar `batas` catatan terakhir — jalur baca "lihat transaksi terakhir".

    Deterministik, tanpa LLM: router sudah mengklasifikasi intent; di sini murni
    baca (difilter `business_id` di query, aturan #6) lalu format tiap baris
    lewat `_baris` (yang dipakai bersama kartu konfirmasi). Kosong → pesan jujur,
    bukan baris karangan (aturan #2). Baris membawa `transaksi_id` + chip
    kategori → bisa dibetulkan di tempat lewat `koreksi_kategori`.

    `periode=None` sengaja berarti **tak berfilter**, bukan "bulan berjalan":
    memfilter secara diam-diam akan menyembunyikan baris yang selama ini
    terlihat, dan pengguna tak punya cara tahu ada yang hilang.
    """
    if periode is None:
        rows = daftar_transaksi_terakhir(session, business_id, batas)
    else:
        rows = daftar_transaksi_periode(session, business_id, periode.mulai, periode.selesai, batas)
    baris = [_baris(t) for t in rows]
    tampil = _periode(periode.mulai, periode.selesai) if periode else ""

    if not baris:
        pesan = (
            f"Belum ada catatan di {tampil}."
            if periode
            else "Belum ada catatan yang bisa ditampilkan. Begitu Ibu catat sesuatu, "
            "nanti muncul di sini."
        )
    else:
        pesan = "Ini catatan terakhir Ibu. Ketuk kategori kalau ada yang perlu dibetulkan."

    return PesanKeluar(
        [
            KartuRiwayat(
                baris=baris,
                judul=f"Catatan {periode.sebutan.lower()}" if periode else "Catatan terakhir",
                pesan=pesan,
                periode_tampil=tampil,
                periode_label=periode.label if periode else "",
            )
        ]
    )


# ── Impor (Pilar 2) ─────────────────────────────────────────────────────────
# Semua rute di bawah ini hanya membaca/menandai draft. Satu-satunya yang
# menyentuh `transactions` adalah `kartu_impor_konfirmasi`, dan ia meneruskan ke
# `konfirmasi_impor` yang cuma memindahkan baris bercentang (aturan #3).


def _tempelan_ke_draft(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
) -> PesanKeluar:
    """Tempelan banyak baris → draft impor, bukan pencatatan langsung."""
    try:
        return kartu_impor_teks(session, adapter, business_id, teks, hari_ini)
    except TerlaluBanyakBaris:
        return PesanKeluar(
            [
                KartuKlarifikasi(
                    pertanyaan=(
                        f"Catatannya panjang sekali — sekali kirim maksimal {MAKS_BARIS} "
                        "baris supaya masih enak diperiksa di HP. Boleh dikirim "
                        "sebagian dulu?"
                    ),
                    yang_kurang=["jumlah_baris"],
                )
            ]
        )


def kartu_impor_teks(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    teks: str,
    hari_ini: date,
) -> PesanKeluar:
    """Baca tempelan → kartu peninjau. ⛔ Nol transaksi tertulis."""
    hasil = impor_dari_teks(session, adapter, business_id, teks, hari_ini)
    return PesanKeluar([_kartu_impor(hasil.tinjau)])


def kartu_impor_tinjau(session: Session, business_id: int, import_id: int) -> PesanKeluar:
    return _bungkus_impor(tinjau_impor(session, business_id, import_id))


def kartu_impor_putuskan(
    session: Session, business_id: int, import_id: int, row_id: int, terima: bool
) -> PesanKeluar:
    """Centang/hapus centang satu baris, lalu gambar ulang kartunya."""
    return _bungkus_impor(putuskan_baris(session, business_id, import_id, row_id, terima))


def kartu_impor_terima_yakin(session: Session, business_id: int, import_id: int) -> PesanKeluar:
    return _bungkus_impor(terima_yakin(session, business_id, import_id))


def kartu_impor_konfirmasi(session: Session, business_id: int, import_id: int) -> PesanKeluar:
    """Simpan baris bercentang ke buku — satu-satunya pintu draft → transaksi."""
    return _bungkus_impor(konfirmasi_impor(session, business_id, import_id))


def _bungkus_impor(ringkas: RingkasanTinjau | None) -> PesanKeluar:
    """Draft tak ditemukan → kalimat jujur, bukan kartu kosong yang membingungkan.

    Aturan #6: service mengembalikan `None` untuk `import_id` milik usaha lain
    **maupun** yang tak ada — dua hal itu memang sengaja tak dibedakan di sini.
    """
    if ringkas is None:
        return PesanKeluar(
            [
                KartuKlarifikasi(
                    pertanyaan="Catatan yang mau ditinjau tidak ketemu. Coba kirim ulang catatannya ya."
                )
            ]
        )
    return PesanKeluar([_kartu_impor(ringkas)])


def _kartu_impor(r: RingkasanTinjau) -> KartuImpor:
    """`RingkasanTinjau` → kartu. Tanpa aritmatika (aturan #1): jumlah dihitung
    service, di sini hanya diformat dan dipilih katanya.
    """
    # Keadaan campur (sebagian sudah masuk, sebagian masih menunggu) harus punya
    # kalimatnya sendiri. Menjatuhkannya ke kalimat "belum ada yang masuk buku"
    # akan membuat kartu berbohong tentang apa yang sudah terjadi pada uang
    # pengguna — dan itu kelas kesalahan yang sama dengan mengarang angka.
    if r.jumlah_tersimpan and (r.jumlah_menunggu or r.jumlah_diterima):
        pesan = (
            f"Sudah masuk buku: {r.jumlah_tersimpan} catatan. "
            f"Masih ada {r.jumlah_menunggu + r.jumlah_diterima} baris yang belum "
            "tersimpan — periksa sisanya kalau mau dilanjutkan."
        )
    elif r.jumlah_tersimpan:
        pesan = (
            f"Sudah masuk buku: {r.jumlah_tersimpan} catatan. Kalau ada yang keliru, "
            "Ibu masih bisa membetulkannya lewat 'lihat catatan terakhir'."
        )
    elif r.jumlah_terbaca == 0:
        pesan = (
            "Belum ada baris yang terbaca sebagai catatan uang. Tidak ada yang saya "
            "simpan — boleh dikirim ulang dengan nominalnya ditulis?"
        )
    else:
        pesan = (
            f"Saya baca {r.jumlah_terbaca} catatan dari kiriman Ibu. "
            "Belum ada yang masuk buku — periksa dulu, centang yang benar, "
            "baru saya simpan."
        )

    catatan: list[str] = []
    if r.jumlah_ragu:
        catatan.append(
            f"{r.jumlah_ragu} baris tanggalnya tidak tertulis, jadi saya tandai. "
            "Tanggal yang keliru memindahkan untung ke bulan yang salah — "
            "itu sebabnya baris ini tidak ikut tercentang borongan."
        )
    if r.jumlah_gagal:
        catatan.append(
            f"{r.jumlah_gagal} baris tidak terbaca sebagai catatan uang. Saya biarkan "
            "tetap tampil supaya Ibu tahu, bukan saya buang diam-diam."
        )
    if not r.selesai:
        catatan.append("Tidak ada yang masuk buku sebelum Ibu menekan simpan.")

    return KartuImpor(
        import_id=r.import_id,
        judul="Periksa dulu sebelum disimpan",
        pesan=pesan,
        baris=[_baris_impor(b) for b in r.baris],
        jumlah=r.jumlah,
        jumlah_terbaca=r.jumlah_terbaca,
        jumlah_ragu=r.jumlah_ragu,
        jumlah_gagal=r.jumlah_gagal,
        jumlah_diterima=r.jumlah_diterima,
        jumlah_tersimpan=r.jumlah_tersimpan,
        jumlah_menunggu=r.jumlah_menunggu,
        selesai=r.selesai,
        catatan=catatan,
    )


def _baris_impor(b: BarisTinjau) -> BarisImpor:
    return BarisImpor(
        row_id=b.row_id,
        raw=b.raw,
        status=b.status,
        terbaca=b.terbaca,
        ragu=b.ragu,
        tersimpan=b.transaksi_id is not None,
        catatan=b.catatan,
        yang_kurang=list(b.yang_kurang),
        jenis=b.jenis.value if b.jenis is not None else None,
        jenis_label=_JENIS_LABEL[b.jenis] if b.jenis is not None else None,
        nominal_tampil=rupiah(b.nominal) if b.nominal is not None else None,
        tanggal_tampil=_tgl_pendek(b.tanggal) if b.tanggal is not None else None,
        produk=b.produk,
        qty_tampil=_qty_teks(b.qty, b.satuan),
    )


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


def _kartu_koreksi(session: Session, business_id: int, hasil: Terkoreksi) -> KartuKonfirmasi:
    """Hasil koreksi → kartu konfirmasi (bentuk yang sama dengan pencatatan).

    Buku append-only (keputusan.md 2026-07-20): `dibatalkan_id` adalah baris lama
    yang ditandai batal, `baris` adalah penggantinya. Aksi `batal` tidak punya
    pengganti → `baris` kosong; kartu tetap dibuat supaya pengguna melihat baris
    mana yang hilang, bukan diam-diam.
    """
    pengganti = (
        _ambil_milik(session, business_id, hasil.id_pengganti)
        if hasil.id_pengganti is not None
        else None
    )
    return KartuKonfirmasi(
        baris=[_baris(pengganti)] if pengganti is not None else [],
        ids=[pengganti.id] if pengganti is not None else [],
        konfirmasi=hasil.konfirmasi,
        dibatalkan_id=hasil.id_dibatalkan,
    )


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
        tanggal_tampil=_tgl_pendek(t.tanggal),
    )


def _qty_tampil(t: Transaction) -> str | None:
    """'5 kotak' dari baris tersimpan; None bila takaran tak dicatat."""
    return _qty_teks(t.qty, t.satuan)


def _qty_teks(qty, satuan: str | None) -> str | None:
    """'5 kotak' dari qty+satuan mana pun (baris tersimpan maupun draft impor).

    Dipakai bersama supaya takaran tidak berbunyi berbeda antara kartu
    konfirmasi dan kartu peninjau impor — pengguna melihat baris yang sama dua
    kali, sebelum dan sesudah disimpan.
    """
    if qty is None:
        return None
    d = _dec(qty).normalize()
    if d == d.to_integral_value():
        d = d.to_integral_value()
    return " ".join(x for x in (f"{d:f}", satuan) if x)


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

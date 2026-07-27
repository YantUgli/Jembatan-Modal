"""Sumbu waktu di kanal — kalimat berperiode → kartu periode yang benar.

Sebelum slice ini semua pertanyaan dijawab untuk bulan berjalan, tanpa tanda
apa pun bahwa pertanyaannya tidak dijawab. Yang dijaga di sini:

- kalimat berperiode benar-benar menggeser rentang yang dihitung;
- **setiap kartu berangka menyebut periodenya** (perluasan aturan #2 dari nilai
  ke konteks);
- ⛔ **regresi**: jalur pencatatan tak tersentuh — "kemarin jual bakso 400rb"
  tetap jadi catatan bertanggal kemarin, bukan kueri periode;
- harga jual yang dipakai = harga yang berlaku di akhir periode, bukan hari ini;
- riwayat tanpa periode tetap tak berfilter.

Jalur periode **tanpa LLM**: adapter hanya dipanggil `pilih_aksi` (dan
`catat_transaksi` di test regresi).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.kontrak import KartuKeuangan, KartuKlarifikasi, KartuRiwayat, KartuUntung
from app.kanal.orkestrator import tangani_pesan
from app.llm.palsu import AdapterPalsu
from app.models import Business, JenisProduk, JenisTransaksi, Transaction
from tests.conftest import buat_produk, buat_transaksi, set_harga_jual

HARI_INI = date(2026, 7, 23)
JUNI = (date(2026, 6, 1), date(2026, 6, 30))


def _tanya(session, business, teks: str, aksi: str):
    """Satu kalimat pertanyaan lewat orchestrator, router di-skrip."""
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": aksi}})
    return tangani_pesan(session, adapter, business.id, teks, HARI_INI)


def _jual(session, business, nominal, tanggal, **kw):
    return buat_transaksi(
        session, business, JenisTransaksi.pemasukan, Decimal(nominal), tanggal, **kw
    )


# ── Periode dari kalimat ────────────────────────────────────────────────────


def test_bulan_lalu_menghitung_bulan_lalu(session: Session, business: Business):
    _jual(session, business, 400000, date(2026, 6, 10))
    _jual(session, business, 75000, date(2026, 7, 10))

    kartu = _tanya(session, business, "untung saya bulan lalu berapa", "tanya_keuangan").kartu[0]

    assert isinstance(kartu, KartuKeuangan)
    # Omzet Juni saja — angka Juli tidak boleh ikut.
    assert kartu.omzet_tampil == "Rp400.000"
    assert kartu.periode_tampil == "1–30 Jun 2026"
    assert kartu.periode_label == "bulan_lalu"


def test_tanpa_frasa_periode_tetap_bulan_berjalan(session: Session, business: Business):
    _jual(session, business, 400000, date(2026, 6, 10))
    _jual(session, business, 75000, date(2026, 7, 10))

    kartu = _tanya(session, business, "gimana keuangan saya", "tanya_keuangan").kartu[0]

    assert isinstance(kartu, KartuKeuangan)
    assert kartu.omzet_tampil == "Rp75.000"
    assert kartu.periode_tampil == "1–23 Jul 2026"
    assert kartu.periode_label == "bulan_ini"


def test_nama_bulan_di_kalimat(session: Session, business: Business):
    _jual(session, business, 400000, date(2026, 6, 10))

    kartu = _tanya(session, business, "rekap juni dong", "tanya_keuangan").kartu[0]

    assert isinstance(kartu, KartuKeuangan)
    assert kartu.omzet_tampil == "Rp400.000"
    assert kartu.periode_label == "bulan:2026-06"


def test_kartu_untung_selalu_menyebut_periodenya(session: Session, business: Business):
    """Sampai VERSI 7 kartu ini memasang cakupan HPP — persentase yang cuma
    bermakna untuk satu rentang — tanpa pernah menyebut rentangnya."""
    kartu = _tanya(session, business, "untung risol berapa", "tanya_untung").kartu[0]

    assert isinstance(kartu, KartuUntung)
    assert kartu.periode_tampil == "1–23 Jul 2026"
    assert kartu.periode_tampil in kartu.teks_alt


# ── ⛔ Regresi: jalur pencatatan tak boleh tersentuh ─────────────────────────


def test_kalimat_catat_berkata_waktu_tetap_jadi_catatan(session: Session, business: Business):
    """"kemarin jual bakso 400rb" menyebut waktu, tapi di sini tanggal adalah
    ISI transaksi — bukan kueri periode. Kalau parser ditarik ke atas router,
    catatan berubah jadi pertanyaan dan uangnya tak pernah masuk buku."""
    teks = "kemarin jual bakso 400rb"
    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            {"aksi": "catat_transaksi"},
            {"baris": [{"jenis": "pemasukan", "nominal": "400000", "tanggal": "2026-07-22"}]},
        ]
    )
    tangani_pesan(session, adapter, business.id, teks, HARI_INI)

    rows = list(session.scalars(select(Transaction).where(Transaction.business_id == business.id)))
    assert len(rows) == 1
    assert rows[0].tanggal == date(2026, 7, 22)  # kemarin, bukan hari ini


# ── Masa depan ──────────────────────────────────────────────────────────────


def test_periode_masa_depan_ditanya_balik(session: Session, business: Business):
    """Kartu berisi nol untuk hari yang belum terjadi tampak seperti hasil
    hitungan, padahal tak ada yang dihitung (aturan #2)."""
    kartu = _tanya(session, business, "untung bulan depan berapa", "tanya_keuangan").kartu[0]

    assert isinstance(kartu, KartuKlarifikasi)


# ── Harga mengikuti akhir periode ───────────────────────────────────────────


def _nugget_beli_juni_harga_juli(session: Session, business: Business):
    """Beli Juni (modal ketahuan), harga jual baru berlaku 1 Juli."""
    nugget = buat_produk(session, business, "nugget", JenisProduk.reseller)
    set_harga_jual(session, nugget, Decimal("25000"), berlaku_dari=date(2026, 7, 1))
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, Decimal("40000"), date(2026, 6, 5),
        kategori_detail="nugget", product=nugget, qty=2, satuan="pak",
    )
    return nugget


def test_untung_periode_lampau_tak_memakai_harga_hari_ini(session: Session, business: Business):
    """`harga_jual_berlaku` jatuh ke `today()` bila tanggalnya kosong. Tanpa
    konteks akhir-periode, untung Juni dihitung dengan harga Juli — persis yang
    tabel harga bertanggal dibangun untuk mencegah."""
    _nugget_beli_juni_harga_juli(session, business)

    kartu = _tanya(session, business, "untung nugget bulan lalu berapa", "tanya_untung").kartu[0]

    assert isinstance(kartu, KartuUntung)
    baris = {b.nama: b for b in kartu.produk}["nugget"]
    assert baris.hpp_tampil == "Rp20.000"  # modal Juni memang sudah ketahuan
    assert baris.harga_jual_tampil is None  # harga jual Juni belum ada
    assert baris.laba_kotor_tampil is None  # ⛔ bukan "Rp5.000" dari harga Juli


def test_untung_periode_berjalan_memakai_harga_yang_berlaku(session: Session, business: Business):
    _nugget_beli_juni_harga_juli(session, business)

    kartu = _tanya(session, business, "untung nugget berapa", "tanya_untung").kartu[0]

    assert isinstance(kartu, KartuUntung)
    baris = {b.nama: b for b in kartu.produk}["nugget"]
    assert baris.diketahui is True
    assert baris.laba_kotor_tampil == "Rp5.000"  # 25.000 − (40.000 ÷ 2)


# ── Riwayat ─────────────────────────────────────────────────────────────────


def test_riwayat_tanpa_periode_tetap_tak_berfilter(session: Session, business: Business):
    """Memfilter diam-diam ke bulan berjalan akan menyembunyikan baris yang
    selama ini terlihat, dan pengguna tak punya cara tahu ada yang hilang."""
    lama = _jual(session, business, 400000, date(2026, 6, 10))
    baru = _jual(session, business, 75000, date(2026, 7, 10))

    kartu = _tanya(session, business, "riwayat dong", "lihat_transaksi").kartu[0]

    assert isinstance(kartu, KartuRiwayat)
    assert {b.transaksi_id for b in kartu.baris} == {lama.id, baru.id}
    assert kartu.periode_tampil == ""


def test_riwayat_berperiode_hanya_baris_periode_itu(session: Session, business: Business):
    lama = _jual(session, business, 400000, date(2026, 6, 10))
    _jual(session, business, 75000, date(2026, 7, 10))

    kartu = _tanya(session, business, "lihat catatan bulan lalu", "lihat_transaksi").kartu[0]

    assert isinstance(kartu, KartuRiwayat)
    assert [b.transaksi_id for b in kartu.baris] == [lama.id]
    assert kartu.periode_tampil == "1–30 Jun 2026"
    assert kartu.periode_label == "bulan_lalu"


def test_riwayat_berperiode_kosong_berkata_jujur(session: Session, business: Business):
    _jual(session, business, 75000, date(2026, 7, 10))

    kartu = _tanya(session, business, "lihat catatan bulan lalu", "lihat_transaksi").kartu[0]

    assert isinstance(kartu, KartuRiwayat)
    assert kartu.baris == []
    assert "1–30 Jun 2026" in kartu.pesan  # menyebut periode mana yang kosong

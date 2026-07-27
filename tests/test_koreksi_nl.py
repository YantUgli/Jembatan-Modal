"""Koreksi lewat kalimat bebas — jalur chat menuju `koreksi_transaksi`.

Sebelum slice ini tool koreksi sudah ada tapi tak terjangkau dari chat: kalimat
"eh salah, harusnya 57rb" jatuh ke pencatatan dan menambah transaksi kedua di
atas yang salah. Yang diuji di sini adalah **jalannya**, bukan ulang isi tool
(itu di `tests/test_tool_koreksi_transaksi.py`): router → tool → kartu, sasaran
dari kartu riwayat, dan pagar-pagar yang tidak boleh jebol saat menyambungnya.

Semua lewat `AdapterPalsu` terskrip. Bentuk **antrean** (list) dipakai bila satu
pesan memicu dua panggilan model (router lalu koreksi) — dict yang dikunci teks
akan menjawab keduanya dengan isi yang sama.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal.kontrak import TipeKartu
from app.kanal.orkestrator import KonteksTunggu, tangani_pesan
from app.llm.kontrak import Gagal
from app.llm.palsu import AdapterPalsu
from app.llm.skema import AksiRouter
from app.models import Business, JenisTransaksi, Transaction
from app.services.catat import daftar_transaksi_terakhir
from app.tools.pilih_aksi import pilih_aksi
from tests.conftest import buat_transaksi

TGL = date(2026, 7, 24)


def _catat(session, business, jenis, nominal, **kw) -> Transaction:
    return buat_transaksi(session, business, jenis, Decimal(nominal), TGL, **kw)


def _semua(session, business_id) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction).where(Transaction.business_id == business_id).order_by(Transaction.id)
        ).all()
    )


# ── Router ──────────────────────────────────────────────────────────────────


def test_router_kalimat_koreksi_ke_koreksi_transaksi(session: Session, business: Business):
    teks = "eh salah, harusnya 57rb"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "koreksi_transaksi"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.koreksi_transaksi


def test_router_kalimat_hapus_ke_koreksi_transaksi(session: Session, business: Business):
    teks = "hapus yang barusan"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "koreksi_transaksi"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.koreksi_transaksi


def test_router_kalimat_jual_baru_tetap_catat(session: Session, business: Business):
    """Garis batas yang paling menentukan: peristiwa uang BARU ≠ koreksi."""
    teks = "laku 5 kotak risol 75rb"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "catat_transaksi"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.catat_transaksi


# ── Koreksi lewat kalimat bebas (sasaran default = catatan terakhir) ─────────


def test_koreksi_nominal_dari_chat(session: Session, business: Business):
    lama = _catat(
        session, business, JenisTransaksi.pemasukan, 75000,
        qty=Decimal("5"), satuan="kotak",
    )
    lama.deskripsi = "risol"
    session.flush()

    adapter = AdapterPalsu(
        jawaban_ekstrak=[{"aksi": "koreksi_transaksi"}, {"aksi": "ubah", "nominal": "57000"}]
    )
    pesan = tangani_pesan(session, adapter, business.id, "eh salah, harusnya 57rb", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.konfirmasi.value
    assert kartu.dibatalkan_id == lama.id
    assert kartu.baris[0].nominal_tampil == "Rp57.000"

    # Append-only: yang lama ditandai batal, penggantinya baris baru.
    session.refresh(lama)
    assert lama.dibatalkan_pada is not None
    (pengganti,) = daftar_transaksi_terakhir(session, business.id)
    assert pengganti.nominal == Decimal("57000")
    assert pengganti.koreksi_dari_id == lama.id
    # Field yang tak disebut = "biarkan seperti semula", bukan "kosongkan".
    assert pengganti.deskripsi == "risol"
    assert pengganti.qty == Decimal("5")
    assert pengganti.satuan == "kotak"


def test_koreksi_batal_dari_chat(session: Session, business: Business):
    """Aksi `batal` tak punya pengganti — kartu tetap dibuat supaya pengguna
    melihat baris mana yang hilang, bukan diam-diam."""
    lama = _catat(session, business, JenisTransaksi.pengeluaran, 38000)

    adapter = AdapterPalsu(jawaban_ekstrak=[{"aksi": "koreksi_transaksi"}, {"aksi": "batal"}])
    pesan = tangani_pesan(session, adapter, business.id, "hapus yang barusan", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.konfirmasi.value
    assert kartu.baris == []
    assert kartu.ids == []
    assert kartu.dibatalkan_id == lama.id

    session.refresh(lama)
    assert lama.dibatalkan_pada is not None
    assert daftar_transaksi_terakhir(session, business.id) == []


def test_penjaga_nominal_hidup_di_jalur_koreksi(session: Session, business: Business):
    """Aturan #1 di sisi input: model tak boleh mengalikan sendiri lewat koreksi.

    "harusnya 3 kotak 20rb" → 60.000 tidak terbaca di kalimat; ditolak, bukan
    disimpan diam-diam.
    """
    lama = _catat(session, business, JenisTransaksi.pemasukan, 75000)

    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            {"aksi": "koreksi_transaksi"},
            {"aksi": "ubah", "nominal": "60000", "qty": "3", "satuan": "kotak"},
        ]
    )
    pesan = tangani_pesan(session, adapter, business.id, "harusnya 3 kotak 20rb", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value
    session.refresh(lama)
    assert lama.dibatalkan_pada is None  # tak ada yang tersentuh
    assert len(_semua(session, business.id)) == 1


def test_koreksi_tak_terbaca_bertanya_balik(session: Session, business: Business):
    lama = _catat(session, business, JenisTransaksi.pemasukan, 75000)

    adapter = AdapterPalsu(
        jawaban_ekstrak=[{"aksi": "koreksi_transaksi"}, Gagal(alasan="tidak jelas", mentah="{}")]
    )
    pesan = tangani_pesan(session, adapter, business.id, "itu tadi salah deh", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value
    session.refresh(lama)
    assert lama.dibatalkan_pada is None


# ── Sasaran ditunjuk dari kartu riwayat ─────────────────────────────────────


def test_koreksi_bersasaran_bukan_baris_terakhir(session: Session, business: Business):
    """Ketuk "Betulkan" di baris tengah → yang berubah baris itu, bukan yang
    terakhir (sasaran default). Router tak dipanggil: niatnya sudah eksplisit."""
    baris = [_catat(session, business, JenisTransaksi.pemasukan, 10000 * (i + 1)) for i in range(5)]
    sasaran = baris[2]

    adapter = AdapterPalsu(jawaban_ekstrak=[{"aksi": "ubah", "jenis": "prive"}])
    pesan = tangani_pesan(
        session, adapter, business.id, "itu buat pribadi", TGL,
        konteks=KonteksTunggu(jenis="koreksi_sasaran", transaksi_id=sasaran.id),
    )

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.konfirmasi.value
    assert kartu.dibatalkan_id == sasaran.id
    assert kartu.baris[0].jenis == JenisTransaksi.prive.value
    assert kartu.baris[0].nominal_tampil == "Rp30.000"  # nominal sasaran, bukan yang terakhir

    # Hanya satu panggilan model (koreksi) — router dilewati.
    assert [p.metode for p in adapter.panggilan] == ["ekstrak"]
    # Baris lain utuh.
    for lain in baris[:2] + baris[3:]:
        session.refresh(lain)
        assert lain.dibatalkan_pada is None


def test_sasaran_lintas_tenant_ditolak_tanpa_memanggil_model(
    session: Session, business: Business, tetangga: Business
):
    """Aturan #6: id dari klien tak tepercaya. Ditolak di query — sebelum satu
    pun panggilan model, dan tanpa jatuh ke alur normal (kalimat koreksi tak
    boleh berubah jadi catatan baru)."""
    milik = _catat(session, business, JenisTransaksi.pemasukan, 75000)

    adapter = AdapterPalsu(jawaban_ekstrak=[])
    pesan = tangani_pesan(
        session, adapter, tetangga.id, "harusnya 57rb", TGL,
        konteks=KonteksTunggu(jenis="koreksi_sasaran", transaksi_id=milik.id),
    )

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value
    assert adapter.panggilan == []
    assert _semua(session, tetangga.id) == []
    session.refresh(milik)
    assert milik.dibatalkan_pada is None


def test_konteks_sasaran_ganti_topik_jatuh_ke_alur_normal(session: Session, business: Business):
    """Pengguna mengetuk "Betulkan" lalu berganti pikiran & mencatat penjualan
    baru → tak terjebak menunggu; sasaran tetap utuh."""
    sasaran = _catat(session, business, JenisTransaksi.pemasukan, 75000)

    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            Gagal(alasan="bukan koreksi", mentah="{}"),  # koreksi tak terbaca
            {"aksi": "catat_transaksi"},  # router
            {  # pencatatan biasa
                "baris": [
                    {"jenis": "pengeluaran", "nominal": "38000", "produk": "minyak",
                     "tanggal": "2026-07-24"}
                ]
            },
        ]
    )
    pesan = tangani_pesan(
        session, adapter, business.id, "beli minyak 38rb", TGL,
        konteks=KonteksTunggu(jenis="koreksi_sasaran", transaksi_id=sasaran.id),
    )

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.konfirmasi.value
    assert kartu.dibatalkan_id is None  # pencatatan, bukan koreksi
    session.refresh(sasaran)
    assert sasaran.dibatalkan_pada is None
    assert len(_semua(session, business.id)) == 2


def test_konteks_sasaran_gagal_tak_dikoreksi_dua_kali(session: Session, business: Business):
    """Koreksi bersasaran tak terbaca, lalu router tetap bilang "koreksi" →
    pertanyaan balik yang sama dipakai ulang. ⛔ Jangan jatuh ke sasaran default:
    itu akan membetulkan baris yang **tidak** ditunjuk pengguna."""
    baris = [_catat(session, business, JenisTransaksi.pemasukan, 10000 * (i + 1)) for i in range(3)]
    sasaran = baris[0]

    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            Gagal(alasan="tidak jelas", mentah="{}"),  # koreksi bersasaran
            {"aksi": "koreksi_transaksi"},  # router
        ]
    )
    pesan = tangani_pesan(
        session, adapter, business.id, "itu salah", TGL,
        konteks=KonteksTunggu(jenis="koreksi_sasaran", transaksi_id=sasaran.id),
    )

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value
    assert len(adapter.panggilan) == 2  # tak ada panggilan koreksi ketiga
    for t in baris:
        session.refresh(t)
        assert t.dibatalkan_pada is None

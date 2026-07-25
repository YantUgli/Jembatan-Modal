"""`atur_resep` lewat chat — jalur bahasa-natural (Tahap 1).

Menguji saluran kalimat resep → `KartuResep` di level router + tool +
orchestrator, memakai `AdapterPalsu` terskrip (tanpa LLM nyata). Angka HPP
dihitung ulang independen di test, bukan disalin dari kode.

Urutan panggilan adapter di jalur `atur_resep` orchestrator: (1) `pilih_aksi`
(router → `PilihanAksi`), lalu (2) `ekstrak_resep` (→ `HasilResep`). Karena
`AdapterPalsu` dict di-key oleh teks masukan yang sama untuk kedua panggilan,
skenario end-to-end memakai bentuk ANTREAN (list) yang pop per urutan panggil.
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
from app.models import Business, CostItemPrice, JenisProduk, JenisTransaksi, Transaction
from app.services.entitas import cari_cost_item, cari_produk
from app.services.resep import HasilAturResep
from app.tools import Klarifikasi
from app.tools.pilih_aksi import pilih_aksi
from app.tools.resep import atur_resep_dari_teks, jawab_harga_bahan

TGL = date(2026, 6, 10)

_RESEP_RISOL = {
    "nama_produk": "risol",
    "yield_qty": 10,
    "yield_satuan": "kotak",
    "bahan": [
        {"nama": "tepung", "qty": 1, "satuan": "kg"},
        {"nama": "minyak", "qty": 0.5, "satuan": "liter"},
        {"nama": "ayam", "qty": 0.5, "satuan": "kg"},
    ],
}


def _beli(session, business, nama, nominal, qty, satuan, tanggal=TGL) -> Transaction:
    """Pembelian bahan (pengeluaran yatim ber-deskripsi = nama bahan)."""
    t = Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran,
        nominal=Decimal(nominal), tanggal=tanggal, deskripsi=nama,
        qty=Decimal(qty), satuan=satuan,
    )
    session.add(t)
    session.flush()
    return t


# ── Router ──────────────────────────────────────────────────────────────────


def test_router_kalimat_resep_ke_atur_resep(session: Session, business: Business):
    teks = "resep risol: tepung sekilo, minyak setengah liter, jadi 10 kotak"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "atur_resep"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.atur_resep


def test_router_kalimat_jual_tetap_catat(session: Session, business: Business):
    teks = "laku 5 kotak risol 75rb"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: {"aksi": "catat_transaksi"}})
    assert pilih_aksi(adapter, teks) is AksiRouter.catat_transaksi


# ── Tool ────────────────────────────────────────────────────────────────────


def test_tool_resep_lengkap_membuat_hasil(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")
    _beli(session, business, "minyak", 19000, 1, "liter")
    _beli(session, business, "ayam", 36000, 1, "kg")

    teks = "resep risol"
    adapter = AdapterPalsu(jawaban_ekstrak={teks: _RESEP_RISOL})
    res = atur_resep_dari_teks(session, adapter, business.id, teks, TGL)

    assert isinstance(res, HasilAturResep)
    # (1×13000 + 0.5×19000 + 0.5×36000) / 10 = 40500/10 = 4050.
    assert res.hpp.hpp_per_unit == Decimal("4050.00")
    assert cari_produk(session, business.id, "risol").jenis is JenisProduk.produksi


def test_tool_resep_tanpa_bahan_klarifikasi(session: Session, business: Business):
    teks = "resep risol enak banget"
    kosong = {"nama_produk": "risol", "yield_qty": 10, "yield_satuan": "kotak", "bahan": []}
    adapter = AdapterPalsu(jawaban_ekstrak={teks: kosong})
    res = atur_resep_dari_teks(session, adapter, business.id, teks, TGL)

    assert isinstance(res, Klarifikasi)
    # Tidak menyimpan resep separuh.
    assert cari_produk(session, business.id, "risol") is None


# ── Orchestrator end-to-end ─────────────────────────────────────────────────


def test_orkestrator_resep_lengkap_kartu_modal(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")
    _beli(session, business, "minyak", 19000, 1, "liter")
    _beli(session, business, "ayam", 36000, 1, "kg")

    adapter = AdapterPalsu(jawaban_ekstrak=[{"aksi": "atur_resep"}, _RESEP_RISOL])
    pesan = tangani_pesan(session, adapter, business.id, "resep risol begini", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.resep.value
    assert kartu.status == "lengkap"
    assert kartu.modal_tampil == "Rp4.050"
    assert kartu.satuan_hpp == "kotak"
    assert kartu.menunggu is None
    assert "Rp4.050" in kartu.konfirmasi


def test_orkestrator_bahan_tanpa_harga_jujur(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")  # keju tidak dibeli

    resep = {
        "nama_produk": "kroket",
        "yield_qty": 8,
        "yield_satuan": "kotak",
        "bahan": [
            {"nama": "tepung", "qty": 1, "satuan": "kg"},
            {"nama": "keju", "qty": 0.1, "satuan": "kg"},
        ],
    }
    adapter = AdapterPalsu(jawaban_ekstrak=[{"aksi": "atur_resep"}, resep])
    pesan = tangani_pesan(session, adapter, business.id, "resep kroket", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.resep.value
    assert kartu.status == "belum"
    assert kartu.modal_tampil is None  # tidak dikarang (aturan #2)
    assert kartu.bahan_perlu_harga == ["keju"]
    assert kartu.menunggu == {"product_id": kartu.product_id, "bahan": "keju"}


def test_orkestrator_resep_tak_lengkap_klarifikasi(session: Session, business: Business):
    kosong = {"nama_produk": "risol", "yield_qty": 10, "yield_satuan": "kotak", "bahan": []}
    adapter = AdapterPalsu(jawaban_ekstrak=[{"aksi": "atur_resep"}, kosong])
    pesan = tangani_pesan(session, adapter, business.id, "resep risol", TGL)

    (kartu,) = pesan.kartu
    assert kartu.tipe == TipeKartu.klarifikasi.value


# ── Tanya-jawab harga multi-turn (Tahap 2) ──────────────────────────────────

_RESEP_KROKET = {
    "nama_produk": "kroket",
    "yield_qty": 10,
    "yield_satuan": "kotak",
    "bahan": [
        {"nama": "tepung", "qty": 1, "satuan": "kg"},
        {"nama": "keju", "qty": 0.1, "satuan": "kg"},
    ],
}


def test_multiturn_jawab_harga_melengkapi(session: Session, business: Business):
    _beli(session, business, "tepung", 13000, 1, "kg")  # keju belum dibeli

    # Giliran 1: resep → kartu menunggu harga keju.
    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            {"aksi": "atur_resep"}, _RESEP_KROKET,          # giliran 1
            {"nominal": 90000, "qty": 1, "satuan": "kg"},   # giliran 2 (jawab harga)
        ]
    )
    p1 = tangani_pesan(session, adapter, business.id, "resep kroket", TGL)
    (k1,) = p1.kartu
    assert k1.status == "belum"
    assert k1.menunggu == {"product_id": k1.product_id, "bahan": "keju"}

    # Giliran 2: jawab "keju sekilo 90rb" dengan konteks → modal lengkap.
    konteks = KonteksTunggu(**k1.menunggu, jenis="harga_bahan")
    p2 = tangani_pesan(session, adapter, business.id, "keju sekilo 90rb", TGL, konteks)
    (k2,) = p2.kartu
    assert k2.tipe == TipeKartu.resep.value
    assert k2.status == "lengkap"
    # (1×13000 + 0.1×90000) / 10 = (13000 + 9000)/10 = 2200.
    assert k2.modal_tampil == "Rp2.200"
    assert k2.menunggu is None


def test_multiturn_qty_lebih_dari_satu_dibagi_kode(session: Session, business: Business):
    """"keju 2 kilo 180rb" → harga satuan 90rb/kg dihitung SERVICE (aturan #1)."""
    _beli(session, business, "tepung", 13000, 1, "kg")
    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            {"aksi": "atur_resep"}, _RESEP_KROKET,
            {"nominal": 180000, "qty": 2, "satuan": "kg"},
        ]
    )
    p1 = tangani_pesan(session, adapter, business.id, "resep kroket", TGL)
    (k1,) = p1.kartu
    konteks = KonteksTunggu(**k1.menunggu, jenis="harga_bahan")

    p2 = tangani_pesan(session, adapter, business.id, "keju 2 kilo 180rb", TGL, konteks)
    (k2,) = p2.kartu
    assert k2.status == "lengkap"
    assert k2.modal_tampil == "Rp2.200"  # 180000/2 = 90000/kg → sama


def test_jawab_harga_tenant_ditolak(
    session: Session, business: Business, tetangga: Business
):
    """Aturan #6: `product_id` di token milik usaha lain → ditolak, tak menulis."""
    # Resep milik `business` (punya bahan keju).
    adapter = AdapterPalsu(jawaban_ekstrak={"resep kroket": _RESEP_KROKET})
    res = atur_resep_dari_teks(session, adapter, business.id, "resep kroket", TGL)
    keju = cari_cost_item(session, business.id, "keju")

    # Tetangga mencoba menjawab harga untuk produk `business` (product_id-nya).
    penyerang = AdapterPalsu()  # tak boleh sampai memanggil ekstrak
    hasil = jawab_harga_bahan(
        session, penyerang, tetangga.id, res.product_id, "keju", "keju sekilo 90rb", TGL
    )
    assert hasil is None
    harga = session.scalars(
        select(CostItemPrice).where(CostItemPrice.cost_item_id == keju.id)
    ).all()
    assert harga == []  # tak ada harga tertulis lintas tenant


def test_multiturn_bukan_harga_jatuh_ke_alur_normal(session: Session, business: Business):
    """Konteks menunggu harga, tapi pengguna malah mencatat penjualan → tak
    terjebak: pesannya diteruskan ke pencatatan biasa."""
    _beli(session, business, "tepung", 13000, 1, "kg")
    adapter = AdapterPalsu(
        jawaban_ekstrak=[
            {"aksi": "atur_resep"}, _RESEP_KROKET,
            Gagal(alasan="bukan harga", yang_kurang=[]),  # jawab_harga_bahan → None
            {"aksi": "catat_transaksi"},                   # fall-through: router
            {"baris": [{"jenis": "pemasukan", "nominal": 50000, "tanggal": "2026-06-10"}]},
        ]
    )
    p1 = tangani_pesan(session, adapter, business.id, "resep kroket", TGL)
    (k1,) = p1.kartu
    konteks = KonteksTunggu(**k1.menunggu, jenis="harga_bahan")

    p2 = tangani_pesan(session, adapter, business.id, "dapat 50rb", TGL, konteks)
    (k2,) = p2.kartu
    assert k2.tipe == TipeKartu.konfirmasi.value  # tercatat sebagai transaksi

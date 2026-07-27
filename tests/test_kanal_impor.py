"""Impor di jalur chat — **pagar aturan #3 di tempat tempelan benar-benar terjadi.**

Berkas ini menguji satu lubang yang mudah tak terlihat: aturan "impor tidak
pernah auto-commit" bisa dilanggar tanpa pernah menyentuh kode impor sama sekali.
Pengguna menempel satu halaman buku tulis ke kotak chat, router
mengklasifikasinya `catat_transaksi`, dan `simpan_transaksi` menuliskan tiga
puluh baris langsung ke buku. Tak ada yang menyebutnya impor, tapi itu persis
impor yang auto-commit.

Karena itu belokannya ada di `tangani_pesan`, dan karena itu pula test-nya di
sini — bukan cuma di `test_impor.py` yang menguji alurnya kalau alur itu memang
dipanggil.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.impor import MAKS_BARIS
from app.kanal import (
    kartu_impor_konfirmasi,
    kartu_impor_putuskan,
    kartu_impor_terima_yakin,
    tangani_pesan,
)
from app.kanal.kontrak import VERSI_KONTRAK, TipeKartu
from app.llm.kontrak import Gagal
from app.llm.palsu import AdapterPalsu
from app.models import Business, Transaction

HARI_INI = date(2026, 7, 26)

BARIS_YAKIN = "12/7 laku 5 kotak risol, 75rb"
BARIS_RAGU = "beli minyak 38rb"
BARIS_GAGAL = "Catatan bulan ini"
TEMPELAN = f"{BARIS_YAKIN}\n{BARIS_RAGU}\n{BARIS_GAGAL}"


def _adapter() -> AdapterPalsu:
    """Jawaban per-BARIS. Kalau orchestrator menyuapkan seluruh tempelan sebagai
    satu teks, `AdapterPalsu` melempar — jadi skrip ini sendiri sudah menjadi
    asersi bahwa parsing terjadi per baris."""
    return AdapterPalsu(
        jawaban_ekstrak={
            BARIS_YAKIN: {
                "baris": [
                    {
                        "jenis": "pemasukan",
                        "nominal": 75_000,
                        "tanggal": "2026-07-12",
                        "produk": "risol",
                        "qty": 5,
                        "satuan": "kotak",
                    }
                ]
            },
            BARIS_RAGU: {
                "baris": [
                    {
                        "jenis": "pengeluaran",
                        "nominal": 38_000,
                        "tanggal": HARI_INI.isoformat(),
                    }
                ]
            },
            BARIS_GAGAL: Gagal(alasan="tak ada uang", yang_kurang=["nominal"]),
        }
    )


def _transaksi(session: Session) -> list[Transaction]:
    return list(session.scalars(select(Transaction)).all())


# ── Belokan tempelan ────────────────────────────────────────────────────────


def test_tempelan_lewat_chat_jadi_draft_bukan_transaksi(session: Session, business: Business):
    """⛔ Uji negatif utama aturan #3 di jalur yang paling mungkin dilewati."""
    keluar = tangani_pesan(session, _adapter(), business.id, TEMPELAN, HARI_INI)
    d = keluar.ke_dict()

    assert d["versi"] == VERSI_KONTRAK
    kartu = d["kartu"][0]
    assert kartu["tipe"] == TipeKartu.impor.value
    assert _transaksi(session) == []  # ← tak ada apa pun yang masuk buku


def test_tempelan_tidak_pernah_sampai_ke_router(session: Session, business: Business):
    """Router tak dipanggil untuk tempelan: belokannya deterministik (jumlah
    baris), jadi nol token terbuang dan nol peluang salah klasifikasi."""
    adapter = _adapter()
    tangani_pesan(session, adapter, business.id, TEMPELAN, HARI_INI)

    muatan = [p.muatan for p in adapter.panggilan]
    assert muatan == [BARIS_YAKIN, BARIS_RAGU, BARIS_GAGAL]
    assert TEMPELAN not in muatan  # seluruh blob tak pernah dikirim sebagai satu teks


def test_dua_baris_masih_pencatatan_biasa(session: Session, business: Business):
    """Regresi: chat normal tak boleh ikut terbelokkan. Dua baris masih lazim
    diketik tangan, jadi ia tetap pencatatan langsung."""
    teks = "laku risol 75rb\nbeli minyak 38rb"
    adapter = AdapterPalsu(
        jawaban_ekstrak={
            teks: {
                "baris": [
                    {"jenis": "pemasukan", "nominal": 75_000, "tanggal": "2026-07-26"},
                    {"jenis": "pengeluaran", "nominal": 38_000, "tanggal": "2026-07-26"},
                ]
            }
        }
    )

    keluar = tangani_pesan(session, adapter, business.id, teks, HARI_INI)
    assert keluar.kartu[0].tipe == TipeKartu.konfirmasi.value
    assert len(_transaksi(session)) == 2


def test_tempelan_kelewat_panjang_ditolak_dengan_kalimat_jujur(
    session: Session, business: Business
):
    adapter = AdapterPalsu(jawaban_ekstrak={})
    panjang = "\n".join(f"laku risol {i}rb" for i in range(MAKS_BARIS + 5))

    keluar = tangani_pesan(session, adapter, business.id, panjang, HARI_INI)
    kartu = keluar.kartu[0]

    assert kartu.tipe == TipeKartu.klarifikasi.value
    assert str(MAKS_BARIS) in kartu.pertanyaan
    assert _transaksi(session) == []
    assert adapter.panggilan == []  # ditolak sebelum satu pun token terpakai


# ── Isi kartu peninjau ──────────────────────────────────────────────────────


def test_kartu_mengaku_belum_menyimpan_apa_pun(session: Session, business: Business):
    kartu = tangani_pesan(session, _adapter(), business.id, TEMPELAN, HARI_INI).ke_dict()[
        "kartu"
    ][0]

    assert kartu["jumlah"] == 3
    assert kartu["jumlah_terbaca"] == 2
    assert kartu["jumlah_ragu"] == 1
    assert kartu["jumlah_gagal"] == 1
    assert kartu["jumlah_tersimpan"] == 0
    assert kartu["selesai"] is False
    assert "Belum ada yang masuk buku" in kartu["pesan"]
    assert any("sebelum Ibu menekan simpan" in c for c in kartu["catatan"])
    # Sebab baris ragu disebut, bukan cuma ditandai.
    assert any("bulan yang salah" in c for c in kartu["catatan"])


def test_baris_membawa_tulisan_asli_dan_tafsirnya(session: Session, business: Business):
    kartu = tangani_pesan(session, _adapter(), business.id, TEMPELAN, HARI_INI).ke_dict()[
        "kartu"
    ][0]
    baris = kartu["baris"]

    assert baris[0]["raw"] == BARIS_YAKIN  # tulisan asli selalu ikut
    assert baris[0]["nominal_tampil"] == "Rp75.000"
    assert baris[0]["jenis_label"] == "Uang masuk"
    assert baris[0]["tanggal_tampil"] == "12 Jul"
    assert baris[0]["qty_tampil"] == "5 kotak"
    assert baris[0]["ragu"] is False

    assert baris[1]["ragu"] is True and baris[1]["terbaca"] is True
    assert "tanggal" in baris[1]["catatan"].lower()

    assert baris[2]["terbaca"] is False
    assert baris[2]["nominal_tampil"] is None  # ⛔ bukan "Rp0" (aturan #2)
    assert baris[2]["raw"] == BARIS_GAGAL


# ── Alur penuh lewat kanal ──────────────────────────────────────────────────


def test_centang_borongan_lalu_simpan(session: Session, business: Business):
    kartu = tangani_pesan(session, _adapter(), business.id, TEMPELAN, HARI_INI).ke_dict()[
        "kartu"
    ][0]
    import_id = kartu["import_id"]

    dicentang = kartu_impor_terima_yakin(session, business.id, import_id).ke_dict()["kartu"][0]
    assert dicentang["jumlah_diterima"] == 1
    assert _transaksi(session) == []  # centang ≠ simpan

    disimpan = kartu_impor_konfirmasi(session, business.id, import_id).ke_dict()["kartu"][0]
    assert disimpan["jumlah_tersimpan"] == 1
    assert len(_transaksi(session)) == 1
    # Keadaan campur: satu sudah masuk, dua masih menunggu. Kartu harus menyebut
    # KEDUANYA — kalimat "belum ada yang masuk buku" di sini adalah kebohongan
    # tentang uang pengguna.
    assert "Sudah masuk buku: 1 catatan" in disimpan["pesan"]
    assert "2 baris yang belum tersimpan" in disimpan["pesan"]


def test_pesan_akhir_saat_semua_sudah_diputuskan(session: Session, business: Business):
    kartu = tangani_pesan(session, _adapter(), business.id, TEMPELAN, HARI_INI).ke_dict()[
        "kartu"
    ][0]
    import_id = kartu["import_id"]
    for b in kartu["baris"]:
        if not b["terbaca"] or b["ragu"]:
            kartu_impor_putuskan(session, business.id, import_id, b["row_id"], False)
    kartu_impor_terima_yakin(session, business.id, import_id)

    disimpan = kartu_impor_konfirmasi(session, business.id, import_id).ke_dict()["kartu"][0]
    assert disimpan["selesai"] is True
    assert "belum tersimpan" not in disimpan["pesan"]
    assert "Sudah masuk buku: 1 catatan" in disimpan["pesan"]


def test_impor_asing_dijawab_kalimat_bukan_kartu_kosong(
    session: Session, business: Business, tetangga: Business
):
    kartu = tangani_pesan(session, _adapter(), tetangga.id, TEMPELAN, HARI_INI).ke_dict()[
        "kartu"
    ][0]

    keluar = kartu_impor_konfirmasi(session, business.id, kartu["import_id"])
    assert keluar.kartu[0].tipe == TipeKartu.klarifikasi.value
    assert _transaksi(session) == []

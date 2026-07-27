"""Alur draft impor — **uji negatif aturan #3 adalah inti berkas ini.**

Impor tidak pernah auto-commit. Larangan itu tidak dijaga oleh niat baik
pemanggil; ia dijaga karena tak ada satu pun jalan dari `buat_draft` ke
`transactions` selain `konfirmasi_impor`, dan `konfirmasi_impor` hanya
memindahkan baris yang **statusnya `diterima`** — status yang cuma bisa lahir
dari ketukan pengguna.

Tiap test yang berjudul "tanpa menyentuh buku" menghitung `Transaction` secara
langsung. Itu asersi yang mahal ditulis dan murah dibaca, dan ia satu-satunya
yang benar-benar membuktikan janjinya: memeriksa status baris saja tidak cukup,
karena bug yang kita takutkan justru bug yang menulis transaksi *sambil*
membiarkan statusnya rapi.

Seluruh berkas ini **tanpa LLM**: draft disusun tangan lewat `BarisDraft`, jadi
yang diuji murni alur & isolasi tenant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.impor import GAGAL, RAGU, YAKIN, BarisDraft
from app.llm.skema import BarisTransaksi
from app.models import (
    Business,
    Import,
    ImportRow,
    JenisTransaksi,
    Product,
    StatusBarisImpor,
    StatusImpor,
    SumberInput,
    Transaction,
)
from app.services.impor import (
    TidakBisaDiterima,
    buat_draft,
    impor_terakhir,
    konfirmasi_impor,
    putuskan_baris,
    terima_yakin,
    tinjau_impor,
    transaksi_dari_impor,
)

HARI_INI = date(2026, 7, 26)


# ── Penyusun draft (tanpa model) ────────────────────────────────────────────


def _yakin(nominal: int, raw: str, *, produk: str | None = None, qty=None) -> BarisDraft:
    return BarisDraft(
        raw=raw,
        baris=BarisTransaksi(
            jenis=JenisTransaksi.pemasukan,
            nominal=Decimal(nominal),
            tanggal=date(2026, 7, 12),
            produk=produk,
            qty=Decimal(qty) if qty is not None else None,
            satuan="kotak" if qty is not None else None,
        ),
        keyakinan=YAKIN,
    )


def _ragu(nominal: int, raw: str) -> BarisDraft:
    return BarisDraft(
        raw=raw,
        baris=BarisTransaksi(
            jenis=JenisTransaksi.pengeluaran, nominal=Decimal(nominal), tanggal=HARI_INI
        ),
        keyakinan=RAGU,
        catatan="Tanggalnya tidak tertulis di baris ini.",
    )


def _gagal(raw: str) -> BarisDraft:
    return BarisDraft(
        raw=raw, keyakinan=GAGAL, catatan="Tidak terbaca.", yang_kurang=("nominal",)
    )


def _draft_campur(session: Session, business: Business) -> Import:
    """Satu impor berisi ketiga rupa baris — bentuk paling realistis."""
    return buat_draft(
        session,
        business.id,
        "teks",
        [
            _yakin(75_000, "12/7 laku risol 75rb", produk="risol", qty=5),
            _ragu(38_000, "beli minyak 38rb"),
            _gagal("Catatan Juli"),
        ],
    )


def _jumlah_transaksi(session: Session) -> int:
    """Seluruh tabel, bukan per-tenant: kalau ada yang bocor, kita mau tahu."""
    return len(list(session.scalars(select(Transaction)).all()))


# ── Draft tidak menyentuh buku ──────────────────────────────────────────────


def test_buat_draft_tidak_menulis_satu_pun_transaksi(session: Session, business: Business):
    impor = _draft_campur(session, business)

    assert _jumlah_transaksi(session) == 0
    assert impor.status is StatusImpor.draft
    rows = list(session.scalars(select(ImportRow).where(ImportRow.import_id == impor.id)).all())
    assert len(rows) == 3
    assert all(r.status is StatusBarisImpor.draft for r in rows)
    assert all(r.transaction_id is None for r in rows)
    assert impor.ringkasan == {"jumlah_baris": 3}


def test_tinjau_menghitung_terbaca_ragu_dan_gagal(session: Session, business: Business):
    impor = _draft_campur(session, business)
    r = tinjau_impor(session, business.id, impor.id)

    assert r is not None
    assert (r.jumlah, r.jumlah_terbaca, r.jumlah_ragu, r.jumlah_gagal) == (3, 2, 1, 1)
    assert r.jumlah_diterima == 0 and r.jumlah_tersimpan == 0
    assert r.jumlah_menunggu == 3
    assert not r.selesai
    # Baris mentah dibawa apa adanya — peninjau harus bisa melihat tulisannya.
    assert r.baris[0].raw == "12/7 laku risol 75rb"
    assert r.baris[1].catatan.startswith("Tanggalnya tidak tertulis")
    assert r.baris[2].yang_kurang == ["nominal"]


def test_mencentang_baris_tidak_menyentuh_buku(session: Session, business: Business):
    impor = _draft_campur(session, business)
    r = putuskan_baris(session, business.id, impor.id, _row_ids(session, impor)[0], True)

    assert r is not None
    assert r.jumlah_diterima == 1
    assert r.jumlah_tersimpan == 0
    assert _jumlah_transaksi(session) == 0  # ← janji aturan #3


def test_centang_bisa_dibatalkan_sebelum_disimpan(session: Session, business: Business):
    impor = _draft_campur(session, business)
    row_id = _row_ids(session, impor)[0]

    putuskan_baris(session, business.id, impor.id, row_id, True)
    r = putuskan_baris(session, business.id, impor.id, row_id, False)

    assert r is not None and r.jumlah_diterima == 0
    assert r.baris[0].status == StatusBarisImpor.ditolak.value
    assert _jumlah_transaksi(session) == 0


def test_baris_tak_terbaca_tidak_bisa_dicentang(session: Session, business: Business):
    """Tak ada angka yang bisa disimpan, jadi "terima" tak punya arti."""
    impor = _draft_campur(session, business)
    row_gagal = _row_ids(session, impor)[2]

    with pytest.raises(TidakBisaDiterima):
        putuskan_baris(session, business.id, impor.id, row_gagal, True)


# ── Aksi borongan tidak menyapu yang ragu ───────────────────────────────────


def test_terima_yakin_melewati_baris_ragu_dan_tak_menyimpan(
    session: Session, business: Business
):
    """Kalau aksi borongan ikut menyapu baris ragu, peninjauan jadi formalitas —
    dan formalitas adalah auto-commit dengan satu ketukan tambahan."""
    impor = _draft_campur(session, business)
    r = terima_yakin(session, business.id, impor.id)

    assert r is not None
    assert r.jumlah_diterima == 1  # hanya yang YAKIN
    assert r.baris[1].status == StatusBarisImpor.draft.value  # yang ragu tetap menunggu
    assert r.baris[2].status == StatusBarisImpor.draft.value  # yang gagal juga
    assert _jumlah_transaksi(session) == 0


def test_terima_yakin_tidak_menimpa_keputusan_pengguna(session: Session, business: Business):
    impor = _draft_campur(session, business)
    ids = _row_ids(session, impor)
    putuskan_baris(session, business.id, impor.id, ids[0], False)  # ditolak sadar

    r = terima_yakin(session, business.id, impor.id)
    assert r is not None
    assert r.baris[0].status == StatusBarisImpor.ditolak.value
    assert r.jumlah_diterima == 0


# ── Konfirmasi: satu-satunya pintu ──────────────────────────────────────────


def test_konfirmasi_hanya_memindahkan_yang_dicentang(session: Session, business: Business):
    impor = _draft_campur(session, business)
    ids = _row_ids(session, impor)
    putuskan_baris(session, business.id, impor.id, ids[0], True)

    r = konfirmasi_impor(session, business.id, impor.id)

    assert r is not None
    assert r.jumlah_tersimpan == 1
    assert _jumlah_transaksi(session) == 1
    # Yang ragu & yang gagal tetap di luar buku, tak tersapu ikut.
    assert r.baris[1].transaksi_id is None
    assert r.baris[2].transaksi_id is None
    # Masih ada yang menunggu → impor belum selesai, pengguna bisa kembali.
    assert r.status == StatusImpor.sebagian.value
    assert not r.selesai


def test_konfirmasi_tanpa_centang_menyimpan_nol(session: Session, business: Business):
    impor = _draft_campur(session, business)
    r = konfirmasi_impor(session, business.id, impor.id)

    assert r is not None and r.jumlah_tersimpan == 0
    assert _jumlah_transaksi(session) == 0


def test_konfirmasi_dua_kali_tidak_menggandakan(session: Session, business: Business):
    impor = _draft_campur(session, business)
    putuskan_baris(session, business.id, impor.id, _row_ids(session, impor)[0], True)

    konfirmasi_impor(session, business.id, impor.id)
    r = konfirmasi_impor(session, business.id, impor.id)

    assert r is not None and r.jumlah_tersimpan == 1
    assert _jumlah_transaksi(session) == 1


def test_semua_diputuskan_menjadikan_impor_selesai(session: Session, business: Business):
    impor = _draft_campur(session, business)
    ids = _row_ids(session, impor)
    putuskan_baris(session, business.id, impor.id, ids[0], True)
    putuskan_baris(session, business.id, impor.id, ids[1], True)
    putuskan_baris(session, business.id, impor.id, ids[2], False)

    r = konfirmasi_impor(session, business.id, impor.id)
    assert r is not None
    assert r.status == StatusImpor.selesai.value
    assert r.selesai
    assert r.jumlah_tersimpan == 2
    assert impor.ringkasan == {
        "jumlah_baris": 3,
        "tersimpan": 2,
        "ditolak": 1,
        "menunggu": 0,
    }


# ── Commit memakai ulang jalur chat ─────────────────────────────────────────


def test_transaksi_impor_ditandai_sumbernya_dan_menyimpan_baris_aslinya(
    session: Session, business: Business
):
    impor = _draft_campur(session, business)
    putuskan_baris(session, business.id, impor.id, _row_ids(session, impor)[0], True)
    konfirmasi_impor(session, business.id, impor.id)

    (t,) = transaksi_dari_impor(session, business.id, impor.id)
    assert t.sumber_input is SumberInput.impor
    assert t.raw_text == "12/7 laku risol 75rb"  # kalimat asli tetap bisa ditelusuri
    assert t.tanggal == date(2026, 7, 12)  # tanggal dari baris, bukan hari impor
    assert t.nominal == Decimal("75000.00")


def test_impor_menautkan_produk_seperti_jalur_chat(session: Session, business: Business):
    """Bukti tak ada jalur tulis kedua: penautan produk & umpan HPP ikut jalan,
    karena commit lewat `simpan_transaksi` yang sama dengan pencatatan chat."""
    impor = _draft_campur(session, business)
    putuskan_baris(session, business.id, impor.id, _row_ids(session, impor)[0], True)
    konfirmasi_impor(session, business.id, impor.id)

    (t,) = transaksi_dari_impor(session, business.id, impor.id)
    assert t.product_id is not None
    produk = session.get(Product, t.product_id)
    assert produk is not None
    assert produk.business_id == business.id
    assert produk.nama.lower() == "risol"


# ── Isolasi tenant (aturan #6) ──────────────────────────────────────────────


def test_draft_tetangga_tak_bisa_dibaca(session: Session, business: Business, tetangga: Business):
    impor = _draft_campur(session, tetangga)
    assert tinjau_impor(session, business.id, impor.id) is None


def test_draft_tetangga_tak_bisa_dicentang_maupun_disimpan(
    session: Session, business: Business, tetangga: Business
):
    """`import_rows` tak punya `business_id` sendiri — tanpa join ke `imports`,
    `import_id` dari klien cukup untuk menulis ke buku usaha lain."""
    impor = _draft_campur(session, tetangga)
    ids = _row_ids(session, impor)

    assert putuskan_baris(session, business.id, impor.id, ids[0], True) is None
    assert terima_yakin(session, business.id, impor.id) is None
    assert konfirmasi_impor(session, business.id, impor.id) is None
    assert _jumlah_transaksi(session) == 0


def test_row_id_dari_impor_lain_tak_bisa_dicentang(session: Session, business: Business):
    """Sepasang id yang tak cocok tak boleh saling menumpang otorisasi."""
    satu = _draft_campur(session, business)
    dua = _draft_campur(session, business)

    asing = _row_ids(session, dua)[0]
    assert putuskan_baris(session, business.id, satu.id, asing, True) is None


# ── Kelanjutan sesi ─────────────────────────────────────────────────────────


def test_impor_terakhir_menemukan_yang_masih_perlu_ditinjau(
    session: Session, business: Business
):
    impor = _draft_campur(session, business)
    ditemukan = impor_terakhir(session, business.id)
    assert ditemukan is not None and ditemukan.id == impor.id


def test_impor_yang_sudah_selesai_tak_muncul_lagi(session: Session, business: Business):
    impor = _draft_campur(session, business)
    for rid in _row_ids(session, impor):
        try:
            putuskan_baris(session, business.id, impor.id, rid, False)
        except TidakBisaDiterima:  # pragma: no cover — 'tolak' selalu boleh
            raise
    konfirmasi_impor(session, business.id, impor.id)

    assert impor_terakhir(session, business.id) is None


def test_impor_terakhir_tidak_melintasi_tenant(
    session: Session, business: Business, tetangga: Business
):
    _draft_campur(session, tetangga)
    assert impor_terakhir(session, business.id) is None


# ── Data rusak tidak jadi tebakan ───────────────────────────────────────────


def test_baris_dengan_parsed_rusak_tak_pernah_masuk_buku(
    session: Session, business: Business
):
    """Lebih baik satu baris hilang dari peninjauan daripada satu baris masuk
    dengan angka yang tak jelas asalnya (aturan #2)."""
    impor = _draft_campur(session, business)
    row_id = _row_ids(session, impor)[0]
    putuskan_baris(session, business.id, impor.id, row_id, True)

    row = session.get(ImportRow, row_id)
    assert row is not None
    row.parsed = {"baris": {"jenis": "pemasukan", "nominal": "bukan-angka"}}
    session.flush()

    r = konfirmasi_impor(session, business.id, impor.id)
    assert r is not None
    assert _jumlah_transaksi(session) == 0
    # Statusnya dikembalikan ke draft, bukan ditandai tersimpan.
    assert r.baris[0].status == StatusBarisImpor.draft.value


def _row_ids(session: Session, impor: Import) -> list[int]:
    return [
        r.id
        for r in session.scalars(
            select(ImportRow).where(ImportRow.import_id == impor.id).order_by(ImportRow.id)
        ).all()
    ]

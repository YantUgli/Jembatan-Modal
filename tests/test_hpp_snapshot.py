"""Unit test memo rekursi (P3) & snapshot HPP (P4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models import HppSnapshot, JenisProduk
from app.services import hpp as svc
from app.services.hpp import (
    StatusHpp,
    cakupan_hpp,
    hitung_hpp_produk,
    hitung_hpp_semua,
    riwayat_hpp,
    simpan_snapshot_hpp,
    simpan_snapshot_semua,
    snapshot_terakhir,
)
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga

HARI = date(2026, 6, 1)


# ── P3: memo rekursi ────────────────────────────────────────────────────────


def _diamond(session, business):
    """jadi → isi1 → adonan, dan jadi → isi2 → adonan. `adonan` dipakai 2 jalur."""
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 10_000, HARI, "kg")

    adonan = buat_produk(session, business, "adonan", JenisProduk.produksi)
    buat_resep(session, adonan, 10, [(tepung, 1, "kg")], yield_satuan="unit")

    isi1 = buat_produk(session, business, "isi1", JenisProduk.produksi)
    buat_resep(session, isi1, 1, [(adonan, 1, "unit")], yield_satuan="unit")
    isi2 = buat_produk(session, business, "isi2", JenisProduk.produksi)
    buat_resep(session, isi2, 1, [(adonan, 1, "unit")], yield_satuan="unit")

    jadi = buat_produk(session, business, "jadi", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, jadi, 1, [(isi1, 1, "unit"), (isi2, 1, "unit")], yield_satuan="unit")
    return jadi, adonan


def test_sub_produk_berulang_hanya_dihitung_sekali(session, business):
    jadi, adonan = _diamond(session, business)

    with patch.object(svc, "_hpp_produksi", wraps=svc._hpp_produksi) as mata:
        hasil = hitung_hpp_produk(session, jadi.id, business.id)

    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("2000.00")  # 2 × 1.000
    dihitung = [c.args[1].nama for c in mata.call_args_list]
    assert dihitung.count("adonan") == 1  # tanpa memo: 2×


def test_memo_dibagi_lintas_produk_di_hitung_semua(session, business):
    _diamond(session, business)

    with patch.object(svc, "_hpp_produksi", wraps=svc._hpp_produksi) as mata:
        hasil = hitung_hpp_semua(session, business.id)

    assert len(hasil) == 4
    dihitung = [c.args[1].nama for c in mata.call_args_list]
    # 4 produk, tiap produk tepat sekali — bukan sekali per jalur pemakaian
    assert sorted(dihitung) == ["adonan", "isi1", "isi2", "jadi"]


def test_memo_tidak_mengubah_hasil_produk_melingkar(session, business):
    """Hasil `resep_melingkar` sengaja tidak di-memo — pastikan tetap benar."""
    a = buat_produk(session, business, "A", JenisProduk.produksi, harga_jual=1_000)
    b = buat_produk(session, business, "B", JenisProduk.produksi)
    buat_resep(session, a, 1, [(b, 1, "unit")], yield_satuan="unit")
    buat_resep(session, b, 1, [(a, 1, "unit")], yield_satuan="unit")

    assert hitung_hpp_produk(session, a.id, business.id).status is StatusHpp.resep_melingkar
    assert hitung_hpp_produk(session, b.id, business.id).status is StatusHpp.resep_melingkar
    assert [h.status for h in hitung_hpp_semua(session, business.id)] == [
        StatusHpp.resep_melingkar,
        StatusHpp.resep_melingkar,
    ]


def test_cakupan_hpp_tetap_benar_dengan_memo(session, business):
    """Memo dipakai lintas transaksi — angkanya tidak boleh bergeser."""
    from app.models import JenisTransaksi

    from tests.conftest import buat_transaksi

    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 10_000, HARI, "kg")
    risol = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, risol, 10, [(tepung, 1, "kg")], yield_satuan="kotak")

    for _ in range(3):
        buat_transaksi(
            session, business, JenisTransaksi.pemasukan, 15_000, date(2026, 6, 10),
            product=risol, qty=1, satuan="kotak",
        )

    cak = cakupan_hpp(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert cak.omzet_tercakup == Decimal("45000.00")
    assert cak.hpp_total == Decimal("3000.00")  # 3 × 1.000
    assert cak.persen == Decimal("100.0")


def test_cakupan_abaikan_produk_usaha_lain(session, business, tetangga):
    """Transaksi menunjuk produk usaha lain → tidak pernah ikut terhitung."""
    from app.models import JenisTransaksi

    from tests.conftest import buat_transaksi

    punya_tetangga = buat_produk(session, tetangga, "punya orang", JenisProduk.produksi)
    buat_transaksi(
        session, business, JenisTransaksi.pemasukan, 50_000, date(2026, 6, 10),
        product=punya_tetangga, qty=1, satuan="kotak",
    )

    cak = cakupan_hpp(session, business.id, date(2026, 6, 1), date(2026, 6, 30))
    assert cak.omzet_total == Decimal("50000.00")
    assert cak.omzet_tercakup == Decimal("0.00")
    assert cak.penjualan_tanpa_produk == Decimal("50000.00")


# ── P4: snapshot ────────────────────────────────────────────────────────────


def _risol(session, business, harga=13_000):
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, harga, HARI, "kg")
    risol = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, risol, 10, [(tepung, 1, "kg")], yield_satuan="kotak")
    return risol, tepung


def test_snapshot_menyimpan_nilai_dan_rincian(session, business):
    risol, _ = _risol(session, business)

    hasil = simpan_snapshot_hpp(session, risol.id, business.id)

    assert hasil.baru is True
    assert hasil.snapshot.hpp_per_unit == Decimal("1300.00")
    assert hasil.snapshot.rincian["status"] == "lengkap"
    assert hasil.snapshot.rincian["satuan_hpp"] == "kotak"
    assert hasil.snapshot.rincian["komponen"][0]["nama"] == "tepung"


def test_snapshot_tidak_menulis_ulang_bila_tidak_berubah(session, business):
    risol, _ = _risol(session, business)

    pertama = simpan_snapshot_hpp(session, risol.id, business.id)
    kedua = simpan_snapshot_hpp(session, risol.id, business.id)

    assert pertama.baru is True
    assert kedua.baru is False
    assert kedua.snapshot.id == pertama.snapshot.id
    assert session.query(HppSnapshot).count() == 1


def test_snapshot_mencatat_saat_harga_bahan_berubah(session, business):
    """Inti margin-watch: perubahan harga bahan meninggalkan jejak."""
    risol, tepung = _risol(session, business)
    simpan_snapshot_hpp(session, risol.id, business.id)

    set_harga(session, tepung, 20_000, date(2026, 7, 1), "kg")  # bahan naik
    kedua = simpan_snapshot_hpp(session, risol.id, business.id)

    assert kedua.baru is True
    assert kedua.snapshot.hpp_per_unit == Decimal("2000.00")
    riwayat = riwayat_hpp(session, risol.id, business.id)
    assert [s.hpp_per_unit for s in riwayat] == [Decimal("2000.00"), Decimal("1300.00")]


def test_snapshot_ditulis_juga_saat_hpp_belum_diketahui(session, business):
    """"Belum diketahui karena X" adalah informasi historis yang sah."""
    p = buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20_000)

    hasil = simpan_snapshot_hpp(session, p.id, business.id)

    assert hasil.baru is True
    assert hasil.snapshot.hpp_per_unit is None
    assert hasil.snapshot.rincian["status"] == "belum_ada_resep"


def test_snapshot_mencatat_perpindahan_antar_status_belum_diketahui(session, business):
    """belum_ada_resep → harga_tidak_lengkap: dua-duanya HPP None, tapi beda cerita."""
    p = buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20_000)
    simpan_snapshot_hpp(session, p.id, business.id)

    coklat = buat_material(session, business, "coklat", "kg")  # sengaja tanpa harga
    buat_resep(session, p, 10, [(coklat, 1, "kg")], yield_satuan="kotak")
    kedua = simpan_snapshot_hpp(session, p.id, business.id)

    assert kedua.baru is True  # nilai sama-sama None, status berbeda → tetap dicatat
    assert kedua.snapshot.rincian["status"] == "harga_tidak_lengkap"
    assert session.query(HppSnapshot).count() == 2


def test_simpan_snapshot_semua(session, business):
    _risol(session, business)
    buat_produk(session, business, "brownies", JenisProduk.produksi, harga_jual=20_000)

    hasil = simpan_snapshot_semua(session, business.id)

    assert len(hasil) == 2
    assert all(h.baru for h in hasil)
    assert session.query(HppSnapshot).count() == 2
    # dipanggil lagi: tidak ada yang berubah, tidak ada baris baru
    assert not any(h.baru for h in simpan_snapshot_semua(session, business.id))
    assert session.query(HppSnapshot).count() == 2


def test_snapshot_isolasi_tenant(session, business, tetangga):
    p = buat_produk(session, tetangga, "punya orang", JenisProduk.produksi)

    with pytest.raises(ValueError):
        simpan_snapshot_hpp(session, p.id, business.id)
    with pytest.raises(ValueError):
        riwayat_hpp(session, p.id, business.id)


def test_snapshot_terakhir_kosong(session, business):
    risol, _ = _risol(session, business)
    assert snapshot_terakhir(session, risol.id) is None

"""Unit test memo rekursi (P3) & snapshot HPP (P4).

Bagian terakhir berkas ini menguji sesuatu yang berbeda dari bagian sebelumnya:
bukan *apakah* `simpan_snapshot_hpp` benar, melainkan **apakah ia benar-benar
dipanggil** dari jalur yang dipakai pengguna. Service yang benar tapi tak pernah
terpanggil tetap berarti tabelnya kosong selamanya — dan HPP lama tidak bisa
diisi mundur, karena yang tersimpan hanya harga terbaru.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.impor import YAKIN, BarisDraft
from app.kanal.orkestrator import kartu_untung
from app.llm.palsu import AdapterPalsu
from app.llm.skema import AksiKoreksi, BarisTransaksi, Koreksi
from app.models import HppSnapshot, JenisProduk, JenisTransaksi
from app.services import hpp as svc
from app.services.catat import simpan_transaksi, terapkan_koreksi
from app.services.entitas import cari_produk
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
from app.services.impor import buat_draft, konfirmasi_impor, terima_yakin
from app.services.resep import atur_resep
from app.tools.resep import jawab_harga_bahan
from tests.conftest import (
    buat_material,
    buat_produk,
    buat_resep,
    buat_transaksi,
    set_harga,
)

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


# ── P4: snapshot benar-benar tertulis di jalur nyata ────────────────────────
#
# Tiap test di bawah menghitung baris `hpp_snapshots` secara langsung. Memeriksa
# nilai kembalian service saja tidak cukup: bug yang kita takutkan justru bug
# yang mengembalikan HPP dengan rapi *sambil* tidak menulis jejaknya sama sekali.


def _snapshots(session, product_id: int | None = None) -> list[HppSnapshot]:
    """Seluruh tabel, bukan per-tenant: kalau ada yang bocor, kita mau tahu."""
    baris = session.query(HppSnapshot).order_by(HppSnapshot.id).all()
    return [s for s in baris if product_id is None or s.product_id == product_id]


def _beli(nominal, **kw) -> BarisTransaksi:
    return BarisTransaksi(
        jenis=JenisTransaksi.pengeluaran, nominal=Decimal(nominal), tanggal=HARI, **kw
    )


def _nugget(session, business):
    """Reseller: HPP-nya = harga beli terakhir, jadi tiap pembelian menggesernya."""
    return buat_produk(
        session, business, "nugget", JenisProduk.reseller,
        harga_jual=30_000, satuan_beli="pack", satuan_jual="pack",
    )


def test_pembelian_reseller_menulis_snapshot(session, business):
    nugget = _nugget(session, business)

    simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )

    (snap,) = _snapshots(session)
    assert snap.product_id == nugget.id
    assert snap.hpp_per_unit == Decimal("25000.00")  # 250.000 ÷ 10
    assert snap.rincian["status"] == "lengkap"


def test_pembelian_kedua_harga_berbeda_menambah_snapshot(session, business):
    """Inti kebocorannya: tanpa ini, harga beli lama hilang tanpa bekas."""
    _nugget(session, business)
    simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )

    simpan_transaksi(
        session, business.id,
        [
            BarisTransaksi(
                jenis=JenisTransaksi.pengeluaran, nominal=Decimal("300000"),
                tanggal=date(2026, 7, 1), produk="nugget",
                qty=Decimal("10"), satuan="pack",
            )
        ],
        "beli nugget 10 pack 300rb",
    )

    assert [s.hpp_per_unit for s in _snapshots(session)] == [
        Decimal("25000.00"),
        Decimal("30000.00"),
    ]


def test_pembelian_harga_sama_tidak_menggandakan_snapshot(session, business):
    """Dedup tetap berlaku di jalur nyata — margin-watch mencari *perubahan*."""
    _nugget(session, business)
    for _ in range(2):
        simpan_transaksi(
            session, business.id,
            [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
            "beli nugget 10 pack 250rb",
        )

    assert len(_snapshots(session)) == 1


def test_transaksi_tanpa_produk_tidak_menulis_snapshot(session, business):
    """Prive, operasional, dan belanja tak dikenal tak menggeser HPP siapa pun."""
    simpan_transaksi(
        session, business.id,
        [
            BarisTransaksi(
                jenis=JenisTransaksi.prive, nominal=Decimal("50000"), tanggal=HARI
            ),
            BarisTransaksi(
                jenis=JenisTransaksi.operasional, nominal=Decimal("20000"),
                tanggal=HARI, produk="listrik",
            ),
        ],
        "ambil 50rb buat belanja rumah, bayar listrik 20rb",
    )

    assert _snapshots(session) == []


def test_pembatalan_pembelian_menulis_snapshot(session, business):
    """Kembali ke "belum diketahui" pun jejak yang sah (aturan #2)."""
    _nugget(session, business)
    hasil = simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )
    (beli,) = hasil.tersimpan

    terapkan_koreksi(
        session, business.id, beli, Koreksi(aksi=AksiKoreksi.batal), raw_text="salah catat"
    )

    pertama, kedua = _snapshots(session)
    assert pertama.hpp_per_unit == Decimal("25000.00")
    assert kedua.hpp_per_unit is None
    assert kedua.rincian["status"] == "belum_ada_harga_beli"


def test_koreksi_nominal_pembelian_menulis_snapshot(session, business):
    _nugget(session, business)
    hasil = simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )
    (beli,) = hasil.tersimpan

    terapkan_koreksi(
        session, business.id, beli,
        Koreksi(aksi=AksiKoreksi.ubah, nominal=Decimal("200000")),
        raw_text="bukan 250rb, 200rb",
    )

    assert [s.hpp_per_unit for s in _snapshots(session)] == [
        Decimal("25000.00"),
        Decimal("20000.00"),
    ]


def test_atur_resep_menulis_snapshot(session, business):
    hasil = atur_resep(
        session, business.id, "risol", Decimal("10"), "kotak",
        [("tepung", Decimal("1"), "kg")], HARI,
        harga_bahan={"tepung": (Decimal("13000"), "kg")},
    )

    (snap,) = _snapshots(session)
    assert snap.product_id == hasil.product_id
    assert snap.hpp_per_unit == Decimal("1300.00")


def test_harga_bahan_menyusul_menulis_snapshot_produk_lain(session, business):
    """Harga bahan dipakai bersama — produk lain ikut tergeser, ikut tercatat.

    Ini yang membedakan `simpan_snapshot_semua` dari snapshot per-produk: tepung
    naik bukan cuma urusan produk yang sedang ditanyakan.
    """
    tepung = buat_material(session, business, "tepung", "kg")  # sengaja tanpa harga
    risol = buat_produk(session, business, "risol", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, risol, 10, [(tepung, 1, "kg")], yield_satuan="kotak")
    kroket = buat_produk(session, business, "kroket", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, kroket, 5, [(tepung, 1, "kg")], yield_satuan="kotak")

    simpan_snapshot_semua(session, business.id)  # garis dasar: dua-duanya "belum lengkap"
    assert len(_snapshots(session)) == 2

    teks = "tepung sekilo 13rb"
    adapter = AdapterPalsu(
        jawaban_ekstrak={teks: {"nominal": 13000, "qty": 1, "satuan": "kg"}}
    )
    jawab_harga_bahan(session, adapter, business.id, risol.id, "tepung", teks, HARI)

    assert _snapshots(session, risol.id)[-1].hpp_per_unit == Decimal("1300.00")
    assert _snapshots(session, kroket.id)[-1].hpp_per_unit == Decimal("2600.00")


def test_impor_dikonfirmasi_menulis_snapshot(session, business):
    """Jalur impor tercakup tanpa kode sendiri — ia lewat `simpan_transaksi`."""
    _nugget(session, business)
    impor = buat_draft(
        session, business.id, "teks",
        [
            BarisDraft(
                raw="beli nugget 10 pack 250rb",
                baris=_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack"),
                keyakinan=YAKIN,
            )
        ],
    )
    terima_yakin(session, business.id, impor.id)
    assert _snapshots(session) == []  # draft belum menyentuh apa pun (aturan #3)

    konfirmasi_impor(session, business.id, impor.id)

    (snap,) = _snapshots(session)
    assert snap.hpp_per_unit == Decimal("25000.00")


def test_jalur_baca_tidak_menulis_snapshot(session, business):
    """Pagar arsitektur: bertanya "untung berapa?" tak boleh menulis apa pun."""
    nugget = _nugget(session, business)
    buat_transaksi(
        session, business, JenisTransaksi.pengeluaran, 250_000, HARI,
        product=nugget, qty=Decimal("10"), satuan="pack",
    )

    kartu_untung(session, business.id, date(2026, 6, 1), date(2026, 6, 30))

    assert _snapshots(session) == []


def test_snapshot_jalur_nyata_tidak_bocor_antar_tenant(session, business, tetangga):
    """Aturan #6: menulis di satu usaha tak menyentuh snapshot usaha lain."""
    buat_produk(
        session, tetangga, "nugget", JenisProduk.reseller,
        satuan_beli="pack", satuan_jual="pack",
    )
    _nugget(session, business)

    simpan_transaksi(
        session, business.id,
        [_beli("250000", produk="nugget", qty=Decimal("10"), satuan="pack")],
        "beli nugget 10 pack 250rb",
    )

    milik_tetangga = cari_produk(session, tetangga.id, "nugget")
    assert _snapshots(session, milik_tetangga.id) == []
    assert len(_snapshots(session)) == 1

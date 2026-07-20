"""Unit test pencocokan satuan (P1).

Sebelum ini: harga tersimpan per "kg" tapi resep menakar "gram" menghasilkan HPP
yang meleset **1000×** sambil berstatus `lengkap`, tanpa satu pun catatan. Itu
bentuk paling murni dari melanggar aturan #2 — bukan menolak menjawab saat data
kurang, tapi menjawab dengan percaya diri saat datanya bertabrakan.

Sikap yang diambil: **bandingkan, jangan konversi.** Menebak bahwa "gram" berarti
1/1000 "kg" tetap menebak.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import JenisProduk, JenisTransaksi, SumberInput, Transaction
from app.services.hpp import StatusHpp, hitung_hpp_produk
from tests.conftest import buat_material, buat_produk, buat_resep, set_harga

HARI = date(2026, 6, 1)


# ── Bahan ───────────────────────────────────────────────────────────────────


def test_satuan_bahan_bertabrakan_menolak_menghitung(session, business):
    """Harga per kg, resep menakar gram → jangan hitung, jangan karang."""
    gula = buat_material(session, business, "gula", "kg")
    set_harga(session, gula, 17_000, HARI, "kg")
    kue = buat_produk(session, business, "kue", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, kue, 10, [(gula, 20, "gram")])

    hasil = hitung_hpp_produk(session, kue.id, business.id)

    assert hasil.status is StatusHpp.satuan_tidak_cocok
    assert hasil.hpp_per_unit is None          # dulu: 34.000,00 (1000× meleset)
    assert hasil.laba_kotor_per_unit is None
    assert len(hasil.satuan_bertabrakan) == 1
    assert "gula" in hasil.satuan_bertabrakan[0]
    assert "gram" in hasil.satuan_bertabrakan[0]
    assert "kg" in hasil.satuan_bertabrakan[0]
    assert any("Samakan dulu satuannya" in c for c in hasil.catatan)


def test_satuan_beda_huruf_besar_dan_spasi_tetap_dianggap_sama(session, business):
    """Normalisasi seminimal mungkin: hanya spasi & besar-kecil huruf."""
    tepung = buat_material(session, business, "tepung", "Kg")
    set_harga(session, tepung, 12_000, HARI, " KG ")
    p = buat_produk(session, business, "roti", JenisProduk.produksi, harga_jual=3_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.hpp_per_unit == Decimal("1200.00")


def test_satuan_tidak_tercatat_tidak_memblokir(session, business):
    """Kalau satuannya memang tidak diketahui, kita tidak bisa memverifikasi —
    jangan berpura-pura menemukan masalah."""
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 12_000, HARI, None)
    p = buat_produk(session, business, "roti", JenisProduk.produksi, harga_jual=3_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.status is StatusHpp.lengkap
    assert hasil.satuan_bertabrakan == []


def test_hanya_bahan_yang_bentrok_yang_dilaporkan(session, business):
    tepung = buat_material(session, business, "tepung", "kg")
    gula = buat_material(session, business, "gula", "kg")
    set_harga(session, tepung, 12_000, HARI, "kg")
    set_harga(session, gula, 17_000, HARI, "kg")
    p = buat_produk(session, business, "kue", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg"), (gula, 20, "gram")])

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert [s.split(" (")[0] for s in hasil.satuan_bertabrakan] == ["gula"]


# ── Sub-produk ──────────────────────────────────────────────────────────────


def test_satuan_sub_produk_harus_sama_dengan_yield_nya(session, business):
    """Resep induk memakai 'butir', tapi HPP sub-produk per 'porsi'."""
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 10_000, HARI, "kg")

    pentol = buat_produk(session, business, "pentol", JenisProduk.produksi)
    buat_resep(session, pentol, 130, [(tepung, 1, "kg")], yield_satuan="porsi")

    bakso = buat_produk(session, business, "bakso", JenisProduk.produksi, harga_jual=15_000)
    buat_resep(session, bakso, 1, [(pentol, 7, "butir")])

    hasil = hitung_hpp_produk(session, bakso.id, business.id)

    assert hasil.status is StatusHpp.satuan_tidak_cocok
    assert hasil.hpp_per_unit is None
    assert "pentol" in hasil.satuan_bertabrakan[0]
    assert "butir" in hasil.satuan_bertabrakan[0]
    assert "porsi" in hasil.satuan_bertabrakan[0]


def test_bentrok_di_dalam_sub_produk_menjalar_ke_induk(session, business):
    """Penyebab akar ikut naik — pengguna tahu persis apa yang harus dibetulkan."""
    gula = buat_material(session, business, "gula", "kg")
    set_harga(session, gula, 17_000, HARI, "kg")

    isi = buat_produk(session, business, "isi", JenisProduk.produksi)
    buat_resep(session, isi, 10, [(gula, 20, "gram")], yield_satuan="unit")

    jadi = buat_produk(session, business, "jadi", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, jadi, 1, [(isi, 2, "unit")])

    hasil = hitung_hpp_produk(session, jadi.id, business.id)

    assert hasil.status is StatusHpp.satuan_tidak_cocok
    assert hasil.hpp_per_unit is None
    assert "gula" in hasil.satuan_bertabrakan[0]  # bukan cuma "isi"


# ── satuan_hpp ──────────────────────────────────────────────────────────────


def test_satuan_hpp_produksi_dari_yield(session, business):
    tepung = buat_material(session, business, "tepung", "kg")
    set_harga(session, tepung, 12_000, HARI, "kg")
    p = buat_produk(session, business, "roti", JenisProduk.produksi, harga_jual=3_000)
    buat_resep(session, p, 10, [(tepung, 1, "kg")], yield_satuan="potong")

    hasil = hitung_hpp_produk(session, p.id, business.id)
    assert hasil.satuan_hpp == "potong"
    assert hasil.rincian_json()["satuan_hpp"] == "potong"


def test_satuan_hpp_reseller_dari_pembelian(session, business):
    nugget = buat_produk(session, business, "nugget", JenisProduk.reseller, harga_jual=30_000)
    session.add(Transaction(
        business_id=business.id, jenis=JenisTransaksi.pengeluaran, nominal=250_000,
        tanggal=HARI, sumber_input=SumberInput.manual,
        product_id=nugget.id, qty=10, satuan="pack",
    ))
    session.flush()

    hasil = hitung_hpp_produk(session, nugget.id, business.id)
    assert hasil.satuan_hpp == "pack"


def test_rincian_json_menyebut_satuan_bertabrakan(session, business):
    gula = buat_material(session, business, "gula", "kg")
    set_harga(session, gula, 17_000, HARI, "kg")
    p = buat_produk(session, business, "kue", JenisProduk.produksi, harga_jual=5_000)
    buat_resep(session, p, 10, [(gula, 20, "gram")])

    rincian = hitung_hpp_produk(session, p.id, business.id).rincian_json()
    assert rincian["status"] == "satuan_tidak_cocok"
    assert rincian["hpp_per_unit"] is None
    assert len(rincian["satuan_bertabrakan"]) == 1

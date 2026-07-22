"""Orchestrator kanal → kartu kontrak. Pakai AdapterPalsu (tanpa LLM nyata).

Fokus: bentuk kontrak stabil & ber-versi, angka datang dari DB (bukan dikarang),
isolasi tenant, dan append-only saat koreksi kategori.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kanal import koreksi_kategori, sapaan, tangani_pesan
from app.kanal.kontrak import VERSI_KONTRAK, TipeKartu
from app.llm.palsu import AdapterPalsu
from app.models import Business, JenisTransaksi, Transaction

HARI_INI = date(2026, 7, 21)


def _hasil_ekstrak(baris: list[dict]) -> dict:
    return {"baris": baris}


def test_catat_menghasilkan_kartu_konfirmasi_angka_dari_db(session: Session, business: Business):
    teks = "laku 5 kotak risol tadi, 75rb"
    adapter = AdapterPalsu(
        jawaban_ekstrak={
            teks: _hasil_ekstrak(
                [{"jenis": "pemasukan", "nominal": 75000, "tanggal": "2026-07-21",
                  "produk": "risol", "qty": 5, "satuan": "kotak"}]
            )
        }
    )

    keluar = tangani_pesan(session, adapter, business.id, teks, HARI_INI)
    d = keluar.ke_dict()

    assert d["versi"] == VERSI_KONTRAK
    assert len(d["kartu"]) == 1
    kartu = d["kartu"][0]
    assert kartu["tipe"] == TipeKartu.konfirmasi.value

    baris = kartu["baris"][0]
    # Angka diformat service, dan cocok dengan baris tersimpan di DB.
    tid = baris["transaksi_id"]
    row = session.get(Transaction, tid)
    assert row is not None and row.business_id == business.id
    assert baris["nominal_tampil"] == "Rp75.000"
    assert baris["nominal"] == "75000.00"
    assert baris["produk"] == "risol"
    assert baris["qty_tampil"] == "5 kotak"
    assert baris["jenis"] == "pemasukan"
    # Empat chip kategori, tepat satu aktif (yang tersimpan).
    aktif = [c for c in baris["kategori_pilihan"] if c["aktif"]]
    assert [c["nilai"] for c in baris["kategori_pilihan"]] == [
        "pemasukan", "pengeluaran", "operasional", "prive",
    ]
    assert len(aktif) == 1 and aktif[0]["nilai"] == "pemasukan"


def test_kalimat_ambigu_jadi_klarifikasi_tanpa_menyimpan(session: Session, business: Business):
    teks = "keluar 50rb"
    from app.llm.kontrak import Gagal

    adapter = AdapterPalsu(
        jawaban_ekstrak={teks: Gagal(alasan="jenis tidak jelas", yang_kurang=["jenis"])}
    )

    keluar = tangani_pesan(session, adapter, business.id, teks, HARI_INI)
    d = keluar.ke_dict()

    assert d["kartu"][0]["tipe"] == TipeKartu.klarifikasi.value
    # Tidak ada yang tersimpan.
    assert session.scalars(select(Transaction)).all() == []


def test_koreksi_kategori_append_only_dan_supersession(session: Session, business: Business):
    teks = "ambil 60rb buat jajan anak"
    adapter = AdapterPalsu(
        jawaban_ekstrak={
            teks: _hasil_ekstrak(
                [{"jenis": "pengeluaran", "nominal": 60000, "tanggal": "2026-07-21"}]
            )
        }
    )
    keluar = tangani_pesan(session, adapter, business.id, teks, HARI_INI)
    tid = keluar.ke_dict()["kartu"][0]["baris"][0]["transaksi_id"]

    # Ketuk chip "Prive" → betulkan jenis.
    hasil = koreksi_kategori(session, business.id, tid, JenisTransaksi.prive)
    baris = hasil.ke_dict()["kartu"][0]["baris"][0]
    assert baris["jenis"] == "prive"

    lama = session.get(Transaction, tid)
    baru = session.get(Transaction, baris["transaksi_id"])
    assert lama.dibatalkan_pada is not None  # append-only: lama ditandai batal
    assert baru.id != lama.id and baru.koreksi_dari_id == lama.id
    assert baru.jenis is JenisTransaksi.prive
    assert baru.nominal == lama.nominal  # nominal tak berubah, hanya jenisnya


def test_koreksi_kategori_isolasi_tenant(session: Session, business: Business, tetangga: Business):
    teks = "masuk 20rb"
    adapter = AdapterPalsu(
        jawaban_ekstrak={
            teks: _hasil_ekstrak([{"jenis": "pemasukan", "nominal": 20000, "tanggal": "2026-07-21"}])
        }
    )
    keluar = tangani_pesan(session, adapter, business.id, teks, HARI_INI)
    tid = keluar.ke_dict()["kartu"][0]["baris"][0]["transaksi_id"]

    # Tetangga tidak boleh mengoreksi transaksi usaha lain.
    hasil = koreksi_kategori(session, tetangga.id, tid, JenisTransaksi.prive)
    assert hasil.ke_dict()["kartu"][0]["tipe"] == TipeKartu.klarifikasi.value
    # Baris asli tak tersentuh.
    assert session.get(Transaction, tid).dibatalkan_pada is None


def test_sapaan_dari_data_usaha(session: Session, business: Business):
    business.jenis_usaha = "katering"
    business.lokasi = "Bandung"
    d = sapaan(business, salam="Selamat pagi").ke_dict()
    kartu = d["kartu"][0]
    assert kartu["tipe"] == TipeKartu.sapaan.value
    assert kartu["nama_usaha"] == business.nama_usaha
    assert kartu["sub"] == "katering · Bandung"
    assert kartu["teks_alt"]  # fallback teks-polos terisi untuk kanal non-visual

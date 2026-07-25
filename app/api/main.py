"""FastAPI `/chat` — permukaan HTTP tipis untuk slice pencatatan.

Alur: browser → (BFF Next.js) → sini → orchestrator → tool/service/DB → kartu.
Endpoint ini tak memuat logika bisnis; ia hanya membaca body, memilih aksi, dan
mengembalikan `PesanKeluar.ke_dict()`.

Isolasi tenant (aturan #6): `business_id` **diselesaikan di server** (dependency
`business_saat_ini`), tak pernah diterima dari klien. Slice 1 menambatkannya ke
usaha demo Bu Sari; auth nyata menyusul.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_scope
from app.kanal import (
    KonteksTunggu,
    kartu_keuangan,
    kartu_riwayat,
    kartu_untung,
    koreksi_kategori,
    sapaan,
    tangani_pesan,
)
from app.llm import AdapterLLM, AdapterOpenAIKompatibel
from app.models import Business, JenisTransaksi, User
from app.seeds.bu_sari import NO_HP

app = FastAPI(title="JembatanModal — API chat", version="0.1.0")

# BFF Next.js memanggil server-ke-server (tak butuh CORS), tapi selama dev UI
# kadang menembak langsung. Origin diambil dari env; default = dev lokal.
_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependencies ─────────────────────────────────────────────────────────────


def dapatkan_sesi() -> Iterator[Session]:
    """Sesi transaksional per-request: commit bila sukses, rollback bila error."""
    with session_scope() as session:
        yield session


def dapatkan_adapter() -> AdapterLLM:
    """Adapter LLM dari variabel lingkungan (provider-agnostic)."""
    return AdapterOpenAIKompatibel.dari_env()


def business_saat_ini(session: Session = Depends(dapatkan_sesi)) -> Business:
    """Usaha untuk request ini — diselesaikan server-side.

    Slice 1: usaha demo Bu Sari (seed). Kalau belum di-seed, 503 dengan petunjuk
    menjalankan seeder, bukan diam-diam memakai tenant lain.
    """
    biz = session.scalar(
        select(Business).join(User, Business.user_id == User.id).where(User.no_hp == NO_HP)
    )
    if biz is None:
        raise HTTPException(
            status_code=503,
            detail="Data demo belum ada. Jalankan: python -m app.seeds.bu_sari",
        )
    return biz


# ── Skema request ────────────────────────────────────────────────────────────


class KonteksMasuk(BaseModel):
    """Token kelanjutan tanya-jawab harga dari klien (lihat `KartuResep.menunggu`).

    ⛔ `product_id` tak tepercaya — divalidasi ulang milik tenant di orchestrator
    (aturan #6). `business_id` tetap diselesaikan server-side, tak dari sini.
    """

    jenis: str  # "harga_bahan"
    product_id: int
    bahan: str


class PesanMasuk(BaseModel):
    teks: str | None = None
    aksi: str | None = None  # koreksi_kategori | tanya_untung | tanya_keuangan | lihat_transaksi
    transaksi_id: int | None = None
    jenis: str | None = None  # nilai JenisTransaksi untuk koreksi_kategori
    # Periode opsional (ISO) untuk tanya_untung/tanya_keuangan; default bulan
    # berjalan diselesaikan server-side.
    mulai: date | None = None
    selesai: date | None = None
    # Token kelanjutan tanya-jawab harga bahan (tanya-jawab multi-turn).
    konteks: KonteksMasuk | None = None


def _periode(pesan: PesanMasuk, hari_ini: date) -> tuple[date, date]:
    """Periode laporan. Default = **bulan berjalan** (tanggal 1 s/d hari ini) —
    sejalan dengan cara pemilik warung berpikir "bulan ini" & irama laporan bank.
    Bisa dioverride lewat `mulai`/`selesai`.
    """
    mulai = pesan.mulai or hari_ini.replace(day=1)
    selesai = pesan.selesai or hari_ini
    return mulai, selesai


# ── Rute ─────────────────────────────────────────────────────────────────────


@app.get("/sehat")
def sehat() -> dict:
    return {"status": "ok"}


@app.get("/sesi")
def sesi(business: Business = Depends(business_saat_ini)) -> dict:
    """Kartu pembuka untuk memulai layar chat."""
    return sapaan(business).ke_dict()


@app.post("/chat")
def chat(
    pesan: PesanMasuk,
    session: Session = Depends(dapatkan_sesi),
    business: Business = Depends(business_saat_ini),
    adapter: AdapterLLM = Depends(dapatkan_adapter),
) -> dict:
    hari_ini = date.today()

    if pesan.aksi == "koreksi_kategori":
        if pesan.transaksi_id is None or pesan.jenis is None:
            raise HTTPException(422, "koreksi_kategori butuh transaksi_id dan jenis.")
        try:
            jenis = JenisTransaksi(pesan.jenis)
        except ValueError:
            raise HTTPException(422, f"jenis tidak dikenal: {pesan.jenis!r}") from None
        return koreksi_kategori(session, business.id, pesan.transaksi_id, jenis).ke_dict()

    if pesan.aksi == "tanya_untung":
        mulai, selesai = _periode(pesan, hari_ini)
        return kartu_untung(session, business.id, mulai, selesai).ke_dict()

    if pesan.aksi == "tanya_keuangan":
        mulai, selesai = _periode(pesan, hari_ini)
        return kartu_keuangan(session, business.id, mulai, selesai).ke_dict()

    if pesan.aksi == "lihat_transaksi":
        return kartu_riwayat(session, business.id).ke_dict()

    if pesan.teks and pesan.teks.strip():
        konteks = (
            KonteksTunggu(
                jenis=pesan.konteks.jenis,
                product_id=pesan.konteks.product_id,
                bahan=pesan.konteks.bahan,
            )
            if pesan.konteks is not None
            else None
        )
        return tangani_pesan(
            session, adapter, business.id, pesan.teks.strip(), hari_ini, konteks
        ).ke_dict()

    raise HTTPException(422, "Kirim `teks`, atau `aksi` yang didukung.")

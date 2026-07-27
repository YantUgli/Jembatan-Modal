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
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import dokumen_dir, session_ttl_hari
from app.db import session_scope
from app.kanal import (
    KonteksTunggu,
    kartu_impor_konfirmasi,
    kartu_impor_putuskan,
    kartu_impor_terima_yakin,
    kartu_impor_tinjau,
    kartu_keuangan,
    kartu_laporan,
    kartu_riwayat,
    kartu_skor,
    kartu_untung,
    koreksi_kategori,
    sapaan,
    tangani_pesan,
)
from app.laporan import PdfTidakTersedia
from app.llm import AdapterLLM, AdapterOpenAIKompatibel
from app.models import Business, Document, JenisTransaksi, User
from app.services.auth import (
    KredensialSalah,
    TerkunciSementara,
    buat_sesi,
    coba_masuk,
    hapus_sesi,
    resolusi_sesi,
)
from app.services.impor import TidakBisaDiterima
from app.services.periode import Periode, periode_dari_label

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


def _token_dari_header(authorization: str | None) -> str | None:
    """Ambil token dari `Authorization: Bearer <token>` yang diteruskan BFF.

    Klien browser tak pernah kirim ini langsung — token hidup di cookie httpOnly
    di sisi BFF, yang meneruskannya sebagai header ke FastAPI internal.
    """
    if not authorization:
        return None
    bagian = authorization.split(None, 1)
    if len(bagian) == 2 and bagian[0].lower() == "bearer":
        return bagian[1].strip() or None
    return None


def pengguna_saat_ini(
    session: Session = Depends(dapatkan_sesi),
    authorization: str | None = Header(default=None),
) -> User:
    """User pemilik sesi. Tak ada/kedaluwarsa → 401 (UI tampilkan layar masuk)."""
    user = resolusi_sesi(session, _token_dari_header(authorization))
    if user is None:
        raise HTTPException(401, "Sesi tidak sah atau sudah kedaluwarsa. Silakan masuk lagi.")
    return user


def business_saat_ini(
    session: Session = Depends(dapatkan_sesi),
    user: User = Depends(pengguna_saat_ini),
) -> Business:
    """Usaha untuk request ini — diselesaikan server-side dari sesi (aturan #6),
    tak pernah dari klien. Satu usaha per user (demo); ambil yang pertama.
    """
    biz = session.scalar(
        select(Business).where(Business.user_id == user.id).order_by(Business.id).limit(1)
    )
    if biz is None:
        raise HTTPException(409, "Akun ini belum punya usaha terdaftar.")
    return biz


# ── Skema request ────────────────────────────────────────────────────────────


class Kredensial(BaseModel):
    no_hp: str
    pin: str


class KonteksMasuk(BaseModel):
    """Token kelanjutan dari klien (lihat `KonteksTunggu` di orchestrator).

    `harga_bahan` memakai `product_id`+`bahan`; `koreksi_sasaran` memakai
    `transaksi_id`. Semuanya opsional di sini karena bentuknya beda per jenis —
    kelengkapan diperiksa di orchestrator.

    ⛔ Id di sini tak tepercaya — divalidasi ulang milik tenant di query
    (aturan #6). `business_id` tetap diselesaikan server-side, tak dari sini.
    """

    jenis: str  # "harga_bahan" | "koreksi_sasaran"
    product_id: int | None = None
    bahan: str | None = None
    transaksi_id: int | None = None


class PesanMasuk(BaseModel):
    teks: str | None = None
    # koreksi_kategori | tanya_untung | tanya_keuangan | tanya_skor |
    # lihat_transaksi | buat_laporan | impor_tinjau | impor_putuskan |
    # impor_terima_yakin | impor_konfirmasi
    aksi: str | None = None
    transaksi_id: int | None = None
    jenis: str | None = None  # nilai JenisTransaksi untuk koreksi_kategori
    # Peninjau impor (Pilar 2). ⛔ Tak tepercaya — keduanya divalidasi milik
    # tenant di dalam query service (aturan #6), tak pernah diandaikan benar.
    import_id: int | None = None
    row_id: int | None = None
    terima: bool | None = None
    # Periode opsional (ISO) untuk tanya_untung/tanya_keuangan; default bulan
    # berjalan diselesaikan server-side.
    mulai: date | None = None
    selesai: date | None = None
    # Label periode dari chip kartu ("bulan_lalu", "3_bulan", "bulan:2026-06").
    # Tanggalnya dihitung server dari label — klien tak pernah menghitung
    # kalender sendiri, jadi chip & kalimat tak bisa berbeda tafsir.
    periode: str | None = None
    # Token kelanjutan multi-turn: jawaban harga bahan, atau sasaran koreksi.
    konteks: KonteksMasuk | None = None


def _label_periode(pesan: PesanMasuk, hari_ini: date) -> Periode | None:
    """Label periode dari klien → rentang. Label asing → **422**.

    ⛔ Sengaja tidak jatuh diam-diam ke default: klien yang salah kirim akan
    mendapat jawaban periode lain yang tampak sah, dan tak ada yang tahu.
    """
    if pesan.periode is None:
        return None
    try:
        return periode_dari_label(pesan.periode, hari_ini)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def _periode(pesan: PesanMasuk, hari_ini: date) -> tuple[date, date, str]:
    """Periode kartu, urutan menang: `mulai`/`selesai` eksplisit → label
    `periode` → default **bulan berjalan** (tanggal 1 s/d hari ini; sejalan
    dengan cara pemilik warung berpikir "bulan ini" & irama laporan bank).

    Mengembalikan label juga, supaya kartu bisa menandai chip mana yang aktif.
    """
    p = _label_periode(pesan, hari_ini)
    if pesan.mulai or pesan.selesai:
        mulai = pesan.mulai or (p.mulai if p else hari_ini.replace(day=1))
        selesai = pesan.selesai or (p.selesai if p else hari_ini)
        return mulai, selesai, ""
    if p is not None:
        return p.mulai, p.selesai, p.label
    return hari_ini.replace(day=1), hari_ini, "bulan_ini"


# ── Rute ─────────────────────────────────────────────────────────────────────


@app.get("/sehat")
def sehat() -> dict:
    return {"status": "ok"}


@app.post("/masuk")
def masuk(kredensial: Kredensial, session: Session = Depends(dapatkan_sesi)) -> dict:
    """Login no.HP + PIN → token sesi. BFF menyimpan token ke cookie httpOnly;
    browser tak pernah melihatnya. Kredensial salah & terkunci sengaja dibedakan
    kodenya (401 vs 429) tapi tidak membocorkan no.HP mana yang terdaftar."""
    try:
        user = coba_masuk(session, kredensial.no_hp, kredensial.pin)
    except TerkunciSementara:
        raise HTTPException(429, "Terlalu banyak percobaan. Coba lagi sebentar.") from None
    except KredensialSalah:
        raise HTTPException(401, "No. HP atau PIN salah.") from None
    token = buat_sesi(session, user, ttl_hari=session_ttl_hari())
    return {"token": token, "nama": user.nama}


@app.post("/keluar", status_code=204)
def keluar(
    session: Session = Depends(dapatkan_sesi),
    authorization: str | None = Header(default=None),
) -> Response:
    """Cabut sesi (logout). Idempoten: token asing/tak ada → tetap 204."""
    hapus_sesi(session, _token_dari_header(authorization))
    return Response(status_code=204)


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
        mulai, selesai, label = _periode(pesan, hari_ini)
        return kartu_untung(session, business.id, mulai, selesai, label=label).ke_dict()

    if pesan.aksi == "tanya_keuangan":
        mulai, selesai, label = _periode(pesan, hari_ini)
        return kartu_keuangan(session, business.id, mulai, selesai, label=label).ke_dict()

    if pesan.aksi == "tanya_skor":
        # Aksi terstruktur, bukan label router: menambah label ke-7 ke
        # `AksiRouter` berisiko menggeser akurasi enam label yang sudah ada
        # (keputusan.md 2026-07-22). Naik ke router menyusul, setelah
        # `app.llm.evaluasi_router` mengukur dampaknya sendirian.
        p = _label_periode(pesan, hari_ini)
        return kartu_skor(
            session,
            business.id,
            hari_ini,
            mulai=pesan.mulai or (p.mulai if p else None),
            selesai=pesan.selesai or (p.selesai if p else None),
            label=p.label if p else "",
        ).ke_dict()

    if pesan.aksi == "lihat_transaksi":
        # Tanpa `periode` → daftar tak berfilter (perilaku default). Lihat
        # docstring `kartu_riwayat`: memfilter diam-diam menyembunyikan baris.
        return kartu_riwayat(
            session, business.id, periode=_label_periode(pesan, hari_ini)
        ).ke_dict()

    if pesan.aksi == "buat_laporan":
        # Default laporan = 3 bulan kalender terakhir (diselesaikan service), BUKAN
        # bulan berjalan seperti kartu di layar: laporan sepotong bulan tak berarti
        # apa-apa bagi pembacanya. `mulai`/`selesai` (atau label `periode`) tetap
        # bisa dikirim eksplisit — defaultnya yang sengaja beda.
        p = _label_periode(pesan, hari_ini)
        try:
            return kartu_laporan(
                session,
                business,
                hari_ini,
                mulai=pesan.mulai or (p.mulai if p else None),
                selesai=pesan.selesai or (p.selesai if p else None),
            ).ke_dict()
        except PdfTidakTersedia as e:
            raise HTTPException(503, str(e)) from e

    # ── Peninjau impor (Pilar 2) ──
    # Semua aksi terstruktur, tanpa LLM: niatnya sudah pasti (ketukan), dan
    # keputusan "baris ini benar" tidak boleh diperantarai model.
    if pesan.aksi and pesan.aksi.startswith("impor_"):
        if pesan.import_id is None:
            raise HTTPException(422, f"{pesan.aksi} butuh import_id.")

        if pesan.aksi == "impor_tinjau":
            return kartu_impor_tinjau(session, business.id, pesan.import_id).ke_dict()

        if pesan.aksi == "impor_putuskan":
            if pesan.row_id is None or pesan.terima is None:
                raise HTTPException(422, "impor_putuskan butuh row_id dan terima.")
            try:
                return kartu_impor_putuskan(
                    session, business.id, pesan.import_id, pesan.row_id, pesan.terima
                ).ke_dict()
            except TidakBisaDiterima as e:
                raise HTTPException(422, str(e)) from e

        if pesan.aksi == "impor_terima_yakin":
            return kartu_impor_terima_yakin(session, business.id, pesan.import_id).ke_dict()

        if pesan.aksi == "impor_konfirmasi":
            return kartu_impor_konfirmasi(session, business.id, pesan.import_id).ke_dict()

        raise HTTPException(422, f"aksi impor tidak dikenal: {pesan.aksi!r}")

    if pesan.teks and pesan.teks.strip():
        konteks = (
            KonteksTunggu(
                jenis=pesan.konteks.jenis,
                product_id=pesan.konteks.product_id,
                bahan=pesan.konteks.bahan,
                transaksi_id=pesan.konteks.transaksi_id,
            )
            if pesan.konteks is not None
            else None
        )
        return tangani_pesan(
            session, adapter, business.id, pesan.teks.strip(), hari_ini, konteks
        ).ke_dict()

    raise HTTPException(422, "Kirim `teks`, atau `aksi` yang didukung.")


@app.get("/dokumen/{dokumen_id}")
def unduh_dokumen(
    dokumen_id: int,
    session: Session = Depends(dapatkan_sesi),
    business: Business = Depends(business_saat_ini),
) -> FileResponse:
    """Unduh dokumen milik usaha ini.

    ⛔ Aturan #6: `business_id` masuk ke **query**, bukan diperiksa setelah baris
    diambil. Dokumen milik tenant lain dijawab **404, bukan 403** — 403
    mengonfirmasi bahwa dokumennya ada, dan siapa pemiliknya bukan urusan
    penanya.

    `file_path` di DB hanya nama berkas (lihat `app/tools/laporan.py`), jadi
    foldernya ditentukan server. Nama itu tetap di-`basename` sebelum dipakai:
    baris DB yang entah bagaimana memuat path tak boleh bisa menunjuk keluar
    folder dokumen.
    """
    dokumen = session.scalars(
        select(Document).where(
            Document.id == dokumen_id,
            Document.business_id == business.id,
        )
    ).first()
    if dokumen is None or not dokumen.file_path:
        raise HTTPException(404, "Dokumen tidak ditemukan.")

    berkas = dokumen_dir() / Path(dokumen.file_path).name
    if not berkas.is_file():
        raise HTTPException(404, "Berkas dokumen sudah tidak ada di server.")

    return FileResponse(
        berkas,
        media_type="application/pdf",
        filename=f"laporan-{dokumen.periode or dokumen.id}.pdf",
    )

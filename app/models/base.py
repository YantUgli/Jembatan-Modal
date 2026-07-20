"""Declarative base + tipe & enum bersama."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )


# ── Enum domain (Bahasa Indonesia — konvensi repo) ──────────────────────────
# Hanya enum yang benar-benar tertutup yang dijadikan Enum; sumber impor &
# topik panduan sengaja string bebas karena daftarnya tumbuh.


class JenisTransaksi(str, enum.Enum):
    pemasukan = "pemasukan"
    pengeluaran = "pengeluaran"
    operasional = "operasional"
    prive = "prive"


class SumberInput(str, enum.Enum):
    chat = "chat"
    impor = "impor"
    manual = "manual"


class JenisProduk(str, enum.Enum):
    reseller = "reseller"
    produksi = "produksi"


class TipeKomponen(str, enum.Enum):
    """Primitif biaya extensible. SEKARANG hanya `material` yang dipakai;
    `labor_time` & `overhead` adalah SLOT — enum menampungnya, kode belum.
    """

    material = "material"
    labor_time = "labor_time"
    overhead = "overhead"


class SumberHarga(str, enum.Enum):
    transaksi = "transaksi"
    ditanya = "ditanya"


class StatusImpor(str, enum.Enum):
    draft = "draft"
    sebagian = "sebagian"
    selesai = "selesai"
    batal = "batal"


class StatusBarisImpor(str, enum.Enum):
    draft = "draft"
    diterima = "diterima"
    ditolak = "ditolak"


class JenisDokumen(str, enum.Enum):
    laporan = "laporan"
    proposal_kur = "proposal_kur"


class HasilKur(str, enum.Enum):
    diajukan = "diajukan"
    lolos = "lolos"
    ditolak = "ditolak"

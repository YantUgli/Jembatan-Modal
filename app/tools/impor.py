"""Tool impor — menyambung parser (LLM) ke alur draft (DB).

Pembagian kerjanya sama dengan `catat_transaksi`: yang memanggil model ada di
lapisan parser, yang menyentuh database deterministik dan bisa diuji tanpa LLM.
Tool ini cuma menjahit keduanya, ditambah satu pemetaan sumber → parser.

⛔ Tool ini **tidak** punya jalan menuju `transactions`. Satu-satunya pintu ke
buku adalah `konfirmasi_impor`, dan pintu itu hanya membuka untuk baris yang
sudah dicentang pengguna (aturan #3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.impor.kontrak import Parser
from app.impor.teks import ParserTeks, TerlaluBanyakBaris
from app.llm.kontrak import AdapterLLM
from app.services.impor import RingkasanTinjau, buat_draft, tinjau_impor

__all__ = ["HasilImpor", "TerlaluBanyakBaris", "impor_dari_teks", "parser_untuk"]


@dataclass
class HasilImpor:
    """Draft yang baru dibuat + keadaan awalnya untuk digambar."""

    import_id: int
    tinjau: RingkasanTinjau


def parser_untuk(sumber: str, adapter: AdapterLLM) -> Parser:
    """Sumber → parser. Tempat satu-satunya yang perlu disentuh saat adaptor
    baru (foto, CSV, export platform) menyusul.
    """
    if sumber == ParserTeks.sumber:
        return ParserTeks(adapter)
    raise ValueError(f"Sumber impor belum didukung: {sumber!r}")


def impor_dari_teks(
    session: Session,
    adapter: AdapterLLM,
    business_id: int,
    muatan: str,
    hari_ini: date,
) -> HasilImpor:
    """Tempelan teks → draft tersimpan, siap ditinjau. Nol transaksi tertulis."""
    parser = parser_untuk(ParserTeks.sumber, adapter)
    draft = parser.parse(muatan, hari_ini)

    impor = buat_draft(session, business_id, parser.sumber, draft)
    tinjau = tinjau_impor(session, business_id, impor.id)
    assert tinjau is not None  # baru dibuat untuk business_id ini
    return HasilImpor(import_id=impor.id, tinjau=tinjau)

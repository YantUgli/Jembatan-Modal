"""Tool `buat_laporan` — pembungkus tipis: angka → HTML → PDF → `documents`.

Nol kalkulasi di sini (angkanya `app/services/laporan.py`), nol markup (itu
`app/laporan/html.py`). Yang khas tool ini cuma **efek sampingnya**: ia menulis
berkas ke disk dan satu baris ke `documents`.

Dua urutan yang disengaja:

1. Baris `documents` ditulis **setelah** PDF-nya benar-benar jadi. Baris yang
   menunjuk berkas tak-ada akan tampil sebagai dokumen yang bisa diunduh, lalu
   gagal saat diketuk — kegagalan yang muncul jauh dari sebabnya.
2. Yang disimpan di `file_path` hanya **nama berkas**, bukan path absolut.
   Foldernya ditentukan `config.dokumen_dir()` saat dibaca, jadi volume dokumen
   bisa dipindah tanpa migrasi data — dan tak ada path dari DB yang bisa
   menunjuk keluar folder itu.

Nama berkas memakai UUID, bukan nama usaha: nama berkas ikut terbaca di URL &
folder, dan nama usaha bukan sesuatu yang perlu bocor ke sana.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app import config
from app.laporan.html import render_html
from app.laporan.pdf import ke_pdf
from app.models import Business, Document, JenisDokumen
from app.services.laporan import (
    JUMLAH_BULAN_DEFAULT,
    RingkasanLaporan,
    ringkas_laporan,
)

__all__ = ["HasilLaporan", "buat_laporan"]


@dataclass
class HasilLaporan:
    document_id: int
    nama_berkas: str
    periode: str  # "2026-05-01..2026-07-26" — apa yang tersimpan di documents
    ringkasan: RingkasanLaporan


def buat_laporan(
    session: Session,
    business: Business,
    hari_ini: date,
    mulai: date | None = None,
    selesai: date | None = None,
    jumlah_bulan: int = JUMLAH_BULAN_DEFAULT,
) -> HasilLaporan:
    """Render laporan periode → PDF tersimpan + baris `documents`.

    `business` sudah diselesaikan server dari sesi (aturan #6); `business_id`
    tidak pernah datang dari klien. `PdfTidakTersedia` dibiarkan naik ke
    pemanggil — lapisan HTTP yang tahu cara mengatakannya kepada pengguna.
    """
    ringkasan = ringkas_laporan(
        session, business, hari_ini, mulai=mulai, selesai=selesai, jumlah_bulan=jumlah_bulan
    )
    html = render_html(ringkasan, dibuat_pada=hari_ini)

    nama_berkas = f"laporan-{uuid4().hex}.pdf"
    ke_pdf(html, config.dokumen_dir() / nama_berkas)

    periode = f"{ringkasan.mulai.isoformat()}..{ringkasan.selesai.isoformat()}"
    dokumen = Document(
        business_id=business.id,
        jenis=JenisDokumen.laporan,
        periode=periode,
        file_path=nama_berkas,
    )
    session.add(dokumen)
    session.flush()

    return HasilLaporan(
        document_id=dokumen.id,
        nama_berkas=nama_berkas,
        periode=periode,
        ringkasan=ringkasan,
    )

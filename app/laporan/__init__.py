"""Render laporan: `RingkasanLaporan` → HTML → PDF.

Sengaja dipisah dari `app/services/laporan.py` (yang memegang angkanya) dan dari
`app/kanal/` (yang menggambar kartu chat). Alasannya praktis: WeasyPrint butuh
pustaka sistem yang tidak selalu ada di mesin dev, jadi jalur HTML harus bisa
dijalankan & diuji tanpa menyentuh PDF sama sekali.
"""

from app.laporan.html import render_html
from app.laporan.pdf import PdfTidakTersedia, ke_pdf

__all__ = ["PdfTidakTersedia", "ke_pdf", "render_html"]

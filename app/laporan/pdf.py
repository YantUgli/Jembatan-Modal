"""HTML → PDF lewat WeasyPrint. Satu fungsi, sengaja setipis mungkin.

`import weasyprint` dilakukan **di dalam fungsi**, bukan di puncak modul. Bukan
gaya-gayaan: WeasyPrint menarik pustaka sistem (GTK/Pango/Cairo) yang sering tak
ada di mesin dev Windows. Impor di puncak modul akan membuat seluruh paket
`app.laporan` — termasuk jalur HTML yang tak butuh apa-apa — gagal diimpor, dan
test isi laporan ikut mati bersamanya.

Kegagalan yang mungkin terjadi diterjemahkan jadi `PdfTidakTersedia` dengan
pesan yang menyebut cara memperbaikinya, supaya pemanggil bisa menjawab 503 yang
menjelaskan alih-alih 500 yang misterius.
"""

from __future__ import annotations

from pathlib import Path


class PdfTidakTersedia(RuntimeError):
    """WeasyPrint tidak terpasang / pustaka sistemnya tidak lengkap."""


PESAN_BELUM_DIPASANG = (
    "Pembuatan PDF butuh WeasyPrint yang belum terpasang: "
    "`pipenv install --categories pdf`."
)

# Dua kegagalan yang terasa sama tapi obatnya beda — dan yang kedua inilah yang
# sebenarnya terjadi di mesin dev Windows: paket Python-nya terpasang, pustaka
# sistemnya tidak. Menyatukan pesannya membuat orang memasang ulang paket yang
# sudah ada, lalu bingung.
PESAN_PUSTAKA_SISTEM = (
    "WeasyPrint terpasang tapi pustaka sistemnya tidak lengkap (GTK/Pango/Cairo). "
    "Di Windows: pasang GTK runtime, lalu ulangi. Laporan tetap bisa diperiksa "
    "lewat `python -m app.laporan.pratinjau` (HTML)."
)


def ke_pdf(html: str, tujuan: Path) -> Path:
    """Tulis `html` sebagai PDF ke `tujuan`. Kembalikan path-nya.

    `base_url` diarahkan ke folder modul ini supaya rujukan relatif (kalau kelak
    ada logo/berkas aset) diselesaikan dari sana — bukan dari direktori kerja
    proses, yang bisa apa saja.
    """
    try:
        from weasyprint import HTML  # noqa: PLC0415 — lihat docstring modul
    except ImportError as e:
        raise PdfTidakTersedia(f"{PESAN_BELUM_DIPASANG} ({e})") from e
    except Exception as e:  # OSError dkk. dari pustaka sistem yang tak ketemu
        raise PdfTidakTersedia(f"{PESAN_PUSTAKA_SISTEM} ({e})") from e

    tujuan.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(Path(__file__).parent)).write_pdf(str(tujuan))
    return tujuan

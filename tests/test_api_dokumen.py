"""Jalur HTTP laporan: buat lewat aksi terstruktur, unduh dengan pagar tenant.

Test lapisan API pertama di repo ini, jadi dua hal ditetapkan di sini sebagai
pola untuk yang berikutnya:

- **`fastapi` di-skip kalau belum terpasang.** Janji repo ini: core (skema +
  service + test) bisa diinstal tanpa dependensi berat (`pyproject.toml` extras).
  Test yang mengimpor FastAPI tanpa syarat membatalkan janji itu.
- **Fungsi rute dipanggil langsung, bukan lewat `TestClient`.** `TestClient`
  menuntut klien HTTP tambahan hanya untuk melintasi loopback; yang perlu diuji
  di sini ada di dalam fungsinya — baris `documents` yang tertulis, `business_id`
  yang masuk ke query, dan status yang dipilih saat gagal. `HTTPException` bisa
  ditangkap apa adanya. Kalau kelak ada middleware/serialisasi yang perlu diuji
  ujung-ke-ujung, di situlah klien HTTP baru layak jadi dependensi.

`ke_pdf` dipalsukan: yang diuji efek samping & otorisasi, bukan WeasyPrint — yang
di mesin dev Windows memang belum bisa jalan (lihat `app/laporan/pdf.py`).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import Business, Document, JenisDokumen, JenisTransaksi
from tests.conftest import buat_transaksi

pytest.importorskip("fastapi", reason="lapisan API opsional (extras `api`)")

from fastapi import HTTPException  # noqa: E402

from app.api import main as api  # noqa: E402
from app.laporan.pdf import PdfTidakTersedia  # noqa: E402

HARI_INI = date(2026, 7, 26)


class _TanggalBeku(date):
    """`date` dengan `today()` dibekukan — laporan default bertumpu padanya."""

    @classmethod
    def today(cls) -> date:
        return HARI_INI


@pytest.fixture(autouse=True)
def lingkungan(tmp_path, monkeypatch):
    """Folder dokumen di tmp, PDF dipalsukan, tanggal dibekukan."""
    monkeypatch.setenv("DOKUMEN_DIR", str(tmp_path / "dokumen"))
    monkeypatch.setattr(api, "date", _TanggalBeku)

    def palsu_ke_pdf(html: str, tujuan):
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        tujuan.write_bytes(b"%PDF-1.4 (palsu untuk uji)")
        return tujuan

    monkeypatch.setattr("app.tools.laporan.ke_pdf", palsu_ke_pdf)


def _buat(session: Session, business: Business, **pesan) -> dict:
    """Panggil `/chat` dengan aksi buat_laporan. `adapter` tak dipakai jalur ini."""
    return api.chat(
        api.PesanMasuk(aksi="buat_laporan", **pesan),
        session=session,
        business=business,
        adapter=None,
    )


def test_buat_laporan_menyimpan_dokumen_dan_kartu_membawa_tautan(
    session: Session, business: Business
):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 7, 5))

    data = _buat(session, business)
    assert data["versi"] == 10

    kartu = data["kartu"][0]
    assert kartu["tipe"] == "dokumen"
    assert kartu["periode_tampil"] == "1 Mei–26 Jul 2026"
    assert kartu["url_unduh"].startswith("/api/dokumen/")
    # Disclaimer aturan #5 hidup di kartu juga, bukan cuma di dalam PDF.
    assert any("bukan jaminan" in c for c in kartu["catatan"])

    nilai = {b["label"]: b["nilai_tampil"] for b in kartu["ringkasan"]}
    assert nilai["Omzet"] == "Rp500.000"
    # Ada omzet tapi tak satu pun tertaut produk → **0%**, bukan "belum
    # diketahui". Bedanya penting: 0% adalah jawaban yang terukur ("tak ada
    # penjualan yang modalnya ketahuan"), sedangkan "belum diketahui" dipakai
    # saat pertanyaannya sendiri belum bisa dijawab — lihat test berikutnya.
    assert nilai["Modal bahan terhitung"] == "0%"


def test_tanpa_omzet_cakupan_mengaku_belum_diketahui(session: Session, business: Business):
    # Tanpa penjualan sama sekali, "0%" akan menyiratkan sudah dihitung dan
    # hasilnya nol. Yang benar: pertanyaannya belum punya penyebut (aturan #2).
    kartu = _buat(session, business)["kartu"][0]
    nilai = {b["label"]: b["nilai_tampil"] for b in kartu["ringkasan"]}
    assert nilai["Modal bahan terhitung"] == "belum diketahui"

    dokumen = session.query(Document).all()
    assert len(dokumen) == 1
    assert dokumen[0].business_id == business.id
    assert dokumen[0].periode == "2026-05-01..2026-07-26"
    # Yang tersimpan hanya nama berkas — foldernya ditentukan server saat dibaca.
    assert "/" not in dokumen[0].file_path
    assert "\\" not in dokumen[0].file_path


def test_unduh_dokumen_sendiri(session: Session, business: Business):
    _buat(session, business)
    dok = session.query(Document).one()

    res = api.unduh_dokumen(dok.id, session=session, business=business)
    assert res.media_type == "application/pdf"
    assert res.path.read_bytes().startswith(b"%PDF")
    # Nama unduhan menyebut periodenya, bukan UUID internal.
    assert "2026-05-01" in res.filename


def test_dokumen_tenant_lain_404_bukan_403(
    session: Session, business: Business, tetangga: Business
):
    """Dokumen milik usaha lain: tidak ditemukan, titik.

    403 akan mengonfirmasi bahwa dokumennya ada — dan siapa pemiliknya bukan
    urusan penanya (aturan #6).
    """
    asing = Document(
        business_id=tetangga.id, jenis=JenisDokumen.laporan, periode="x", file_path="asing.pdf"
    )
    session.add(asing)
    session.flush()

    with pytest.raises(HTTPException) as e:
        api.unduh_dokumen(asing.id, session=session, business=business)
    assert e.value.status_code == 404


def test_dokumen_tak_dikenal_404(session: Session, business: Business):
    with pytest.raises(HTTPException) as e:
        api.unduh_dokumen(999_999, session=session, business=business)
    assert e.value.status_code == 404


def test_berkas_hilang_dari_disk_404_bukan_500(session: Session, business: Business):
    dok = Document(
        business_id=business.id,
        jenis=JenisDokumen.laporan,
        periode="x",
        file_path="tidak-ada.pdf",
    )
    session.add(dok)
    session.flush()

    with pytest.raises(HTTPException) as e:
        api.unduh_dokumen(dok.id, session=session, business=business)
    assert e.value.status_code == 404


def test_pdf_tak_tersedia_jadi_503_yang_menjelaskan(
    session: Session, business: Business, monkeypatch
):
    def gagal(html, tujuan):
        raise PdfTidakTersedia("WeasyPrint terpasang tapi pustaka sistemnya tidak lengkap.")

    monkeypatch.setattr("app.tools.laporan.ke_pdf", gagal)

    with pytest.raises(HTTPException) as e:
        _buat(session, business)
    assert e.value.status_code == 503
    assert "pustaka sistem" in e.value.detail
    # Gagal render → jangan tinggalkan baris dokumen yang menunjuk berkas hantu.
    assert session.query(Document).all() == []


def test_periode_eksplisit_dihormati(session: Session, business: Business):
    data = _buat(session, business, mulai=date(2026, 6, 1), selesai=date(2026, 6, 30))
    assert data["kartu"][0]["periode_tampil"] == "1–30 Jun 2026"

"""Render HTML laporan — yang dijaga di sini adalah **janji**, bukan tata letak.

Tiga di antaranya adalah aturan repo yang kalau hilang tak akan terlihat sebagai
bug: disclaimer (aturan #5), cakupan HPP yang selalu tercantum (aturan #2), dan
tidak adanya skor komposit di dokumen yang dibaca penyalur (aturan #9).

Aturan #9 khususnya diuji **sekarang, saat mustahil dilanggar** — service skor
belum ada. Justru itu saat termurahnya: begitu `skor_pengguna` lahir, seseorang
akan tergoda "melengkapi" laporan dengan 72/100, dan test inilah yang berteriak.

Tanpa WeasyPrint: yang diuji HTML-nya. Jalur PDF cuma satu panggilan pustaka
pihak ketiga (`app/laporan/pdf.py`) dan tak memuat keputusan apa pun.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy.orm import Session

from app.laporan.html import render_html
from app.models import Business, JenisTransaksi
from app.services.laporan import ringkas_laporan
from tests.conftest import buat_transaksi

HARI_INI = date(2026, 7, 26)

# Isi sel tabel & judul bagian — di sanalah angka penilaian akan muncul kalau
# suatu hari menyelundup masuk. Catatan kaki sengaja TIDAK diperiksa: di sana
# kata "skor" muncul justru untuk menyangkalnya ("tanpa skor").
_SEL = re.compile(r"<(h1|h2|th|td)\b[^>]*>(.*?)</\1>", re.S | re.I)


def _render(session: Session, business: Business) -> str:
    return render_html(ringkas_laporan(session, business, HARI_INI), dibuat_pada=HARI_INI)


def _sel_teks(html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m.group(2)) for m in _SEL.finditer(html)]


def test_disclaimer_selalu_ada(session: Session, business: Business):
    html = _render(session, business)
    assert "bukan jaminan persetujuan" in html
    assert "bukan laporan keuangan teraudit" in html
    assert "Keputusan pemberian pembiayaan sepenuhnya ada pada lembaga penyalur" in html


def test_format_ditandai_belum_final(session: Session, business: Business):
    # Formatnya belum ditinjau analis kredit — dokumen mengaku sendiri, bukan
    # diam-diam tampil seperti sudah baku.
    assert "Format laporan v1" in _render(session, business)


def test_cakupan_hpp_tercantum(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 7, 5))
    html = _render(session, business)
    assert "Cakupan HPP" in html
    # Kalimat penjelasnya ikut, bukan cuma angkanya: persentase tanpa arti mudah
    # dibaca sebagai "sisanya nol".
    assert "tidak diperkirakan" in html


def test_tanpa_skor_di_sel_maupun_judul(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 7, 5))
    html = _render(session, business)

    for teks in _sel_teks(html):
        assert "skor" not in teks.casefold(), f"skor menyusup ke sel/judul: {teks!r}"
    assert re.search(r"\d+\s*/\s*100", html) is None
    assert "poin" not in html.casefold()
    # Dan penyangkalannya tetap tertulis untuk pembacanya.
    assert "tanpa skor" in html


def test_uang_negatif_tak_pernah_berbunyi_rp_minus(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 100_000, date(2026, 7, 5))
    buat_transaksi(session, business, JenisTransaksi.pengeluaran, 400_000, date(2026, 7, 6))
    html = _render(session, business)

    assert "Rp-" not in html  # 'Rp-300.000' terbaca seperti salah cetak
    assert "−Rp300.000" in html


def test_nama_usaha_tak_bisa_menyuntik_markup(session: Session, business: Business):
    business.nama_usaha = "<script>alert(1)</script>Warung"
    business.jenis_usaha = 'katering "spesial" & frozen'
    session.flush()
    html = _render(session, business)

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&amp;" in html


def test_kategori_biaya_dari_pengguna_ikut_di_escape(session: Session, business: Business):
    buat_transaksi(
        session, business, JenisTransaksi.operasional, 20_000, date(2026, 7, 5),
        kategori_detail="<b>gas</b>",
    )
    html = _render(session, business)
    assert "<b>gas</b>" not in html
    assert "&lt;b&gt;gas&lt;/b&gt;" in html


def test_bulan_bolong_ditandai_bukan_dihilangkan(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 7, 5))
    html = _render(session, business)

    assert "Mei 2026" in html and "Jun 2026" in html  # dua bulan kosong tetap ada
    assert 'class="kosong"' in html
    assert "bukan dilewati" in html


def test_bulan_berjalan_ditandai_belum_penuh(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 500_000, date(2026, 7, 5))
    html = _render(session, business)
    assert "Jul 2026 *" in html
    assert "belum penuh" in html


def test_mandiri_tanpa_aset_eksternal(session: Session, business: Business):
    # WeasyPrint tak boleh perlu mengunduh apa pun: CSS ter-inline, tanpa <link>,
    # tanpa <img> jauh. Berkasnya juga harus bisa dibuka apa adanya di browser.
    html = _render(session, business)
    assert "<link" not in html
    assert "http://" not in html and "https://" not in html
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html


def test_angka_diformat_rupiah_bukan_desimal_mentah(session: Session, business: Business):
    buat_transaksi(session, business, JenisTransaksi.pemasukan, 1_300_000, date(2026, 7, 5))
    html = _render(session, business)
    assert "Rp1.300.000" in html
    assert "1300000.00" not in html

"""`RingkasanLaporan` → HTML satu berkas (CSS ter-inline) siap dicetak.

⛔ **Tidak ada aritmatika di modul ini** (aturan #1). Semua angka sudah dihitung
`app/services/laporan.py`; di sini hanya memformat & memilih kata.

⚠️ **Setiap string dari pengguna wajib lewat `_e()`.** `nama_usaha`,
`kategori_detail`, dan nama produk semuanya diketik pengguna. Di chat ia teks
biasa; begitu masuk dokumen ia jadi markup — permukaan injeksi yang belum pernah
ada di repo ini sebelum laporan lahir. Satu pintu, dan ada test-nya.

Tanpa Jinja2: bagian dokumen ini tetap dan sedikit, jadi fungsi kecil murni
bergaya pembangun kartu di `app/kanal/orkestrator.py` sudah cukup — dan bisa
diuji tanpa memasang WeasyPrint.

**Register bahasanya beda dari chat, dan itu memang niatnya.** Pembaca dokumen
ini AO bank, jadi "Omzet", "Laba Bersih", dan "Prive" dipakai apa adanya. Yang
tetap dilarang (non-goal brief §4): debit, kredit, jurnal.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from app.services.angka import persen, rupiah
from app.services.laporan import BulanLaporan, RingkasanLaporan
from app.services.tanggal import tgl_pendek

BERKAS_CSS = Path(__file__).with_name("laporan.css")

# Aturan #5: setiap dokumen kredit membawa disclaimer. Tidak ada janji peluang
# lolos, dan tidak pernah dipendekkan "supaya rapi".
DISCLAIMER = (
    "Dokumen ini disusun otomatis dari catatan keuangan yang dimasukkan sendiri "
    "oleh pemilik usaha. Ia alat bantu persiapan pengajuan — <strong>bukan "
    "jaminan persetujuan</strong>, bukan laporan keuangan teraudit, dan bukan "
    "penilaian kelayakan kredit. Keputusan pemberian pembiayaan sepenuhnya ada "
    "pada lembaga penyalur."
)

CATATAN_FORMAT = (
    "Format laporan v1. Susunannya masih akan disesuaikan setelah ditinjau "
    "petugas analis kredit."
)


def _e(nilai: object) -> str:
    """Escape apa pun yang berasal dari data. Satu-satunya pintu ke markup."""
    return escape("" if nilai is None else str(nilai), quote=True)


def _baris_tabel(sel: list[str], *, kepala: bool = False, kelas: str = "") -> str:
    tag = "th" if kepala else "td"
    isi = "".join(f"<{tag}>{s}</{tag}>" for s in sel)
    atribut = f' class="{kelas}"' if kelas else ""
    return f"<tr{atribut}>{isi}</tr>"


def _tabel(kepala: list[str], baris: list[str], kelas: str = "") -> str:
    atribut = f' class="{kelas}"' if kelas else ""
    return (
        f"<table{atribut}><thead>{_baris_tabel(kepala, kepala=True)}</thead>"
        f"<tbody>{''.join(baris)}</tbody></table>"
    )


def _bagian(judul: str, isi: str, catatan: list[str] | None = None) -> str:
    ekor = "".join(f'<p class="catatan">{_e(c)}</p>' for c in (catatan or []))
    return f'<section><h2>{_e(judul)}</h2>{isi}{ekor}</section>'


def _identitas(r: RingkasanLaporan) -> str:
    i = r.identitas
    pasangan = [
        ("Nama usaha", i.nama_usaha),
        ("Bidang usaha", i.jenis_usaha),
        ("Lokasi", i.lokasi),
        ("Pemilik", i.nama_pemilik),
        ("No. HP", i.no_hp),
        ("Mulai usaha", i.mulai_usaha.isoformat() if i.mulai_usaha else None),
    ]
    baris = "".join(
        f"<div><dt>{_e(label)}</dt><dd>{_e(nilai)}</dd></div>"
        for label, nilai in pasangan
        if nilai
    )
    return f"<dl class='identitas'>{baris}</dl>"


def _baris_bulan(b: BulanLaporan) -> str:
    tanda = "" if b.penuh else " *"
    return _baris_tabel(
        [
            _e(b.label) + tanda,
            _e(b.hari_tercatat),
            rupiah(b.laba.omzet),
            rupiah(b.laba.biaya_total),
            rupiah(b.laba.laba_bersih),
            persen(b.cakupan.persen) if b.cakupan.omzet_total > 0 else "—",
        ],
        kelas="kosong" if b.hari_tercatat == 0 else "",
    )


def _tren(r: RingkasanLaporan) -> str:
    tabel = _tabel(
        ["Bulan", "Hari tercatat", "Omzet", "Biaya usaha", "Laba bersih", "Cakupan HPP"],
        [_baris_bulan(b) for b in r.bulan],
        kelas="angka",
    )
    catatan = []
    if any(not b.penuh for b in r.bulan):
        catatan.append("* bulan belum penuh — dihitung sampai tanggal potong periode.")
    if any(b.hari_tercatat == 0 for b in r.bulan):
        catatan.append(
            "Bulan tanpa catatan ditampilkan sebagai nol, bukan dilewati — supaya "
            "bolongnya terlihat."
        )
    return _bagian("Ringkasan per bulan", tabel, catatan)


def _laba_rugi(r: RingkasanLaporan) -> str:
    t = r.total
    baris = [
        _baris_tabel(["Omzet (uang masuk dari penjualan)", rupiah(t.omzet)]),
        _baris_tabel(["Belanja bahan / barang dagangan", "− " + rupiah(t.belanja)]),
        _baris_tabel(["Biaya operasional (sewa, listrik, gas, tenaga)", "− " + rupiah(t.operasional)]),
        _baris_tabel(["Laba bersih", rupiah(t.laba_bersih)], kelas="jumlah"),
    ]
    tabel = _tabel(["Pos", r.periode_tampil], baris, kelas="angka dua-kolom")

    # `t.catatan` sudah menjelaskan basis kas & prive bila relevan — jangan
    # mengulanginya di sini, cukup tunjuk ke mana prive dilaporkan.
    catatan = [*t.catatan, "Uang yang diambil pemilik dilaporkan terpisah di bagian Arus kas."]
    return _bagian("Laba-rugi periode", tabel, catatan)


def _arus_kas(r: RingkasanLaporan) -> str:
    a = r.arus_kas
    baris = [
        _baris_tabel(["Uang masuk", rupiah(a.uang_masuk)]),
        _baris_tabel(["Uang keluar (biaya usaha + prive)", "− " + rupiah(a.uang_keluar)]),
        _baris_tabel(["Di antaranya prive", rupiah(a.prive)], kelas="rincian"),
        _baris_tabel(["Sisa", rupiah(a.sisa)], kelas="jumlah"),
    ]
    return _bagian(
        "Arus kas",
        _tabel(["Pos", r.periode_tampil], baris, kelas="angka dua-kolom"),
        [
            "Berbeda dari laba bersih: di sini prive ikut dihitung sebagai uang "
            "keluar, karena uangnya memang keluar dari usaha."
        ],
    )


def _pos_biaya(r: RingkasanLaporan) -> str:
    pos = r.rekonsiliasi.pos_biaya_terbesar
    if not pos:
        return _bagian("Pos biaya terbesar", "<p>Belum ada pengeluaran tercatat pada periode ini.</p>")
    baris = [
        _baris_tabel([_e(p.kategori), _e(p.jenis), rupiah(p.nominal)]) for p in pos
    ]
    return _bagian(
        "Pos biaya terbesar",
        _tabel(["Kategori", "Jenis", "Nominal"], baris, kelas="angka"),
    )


def _cakupan(r: RingkasanLaporan) -> str:
    c, rek = r.cakupan, r.rekonsiliasi
    baris = [
        _baris_tabel(["Omzet periode", rupiah(c.omzet_total)]),
        _baris_tabel(["Omzet yang modalnya sudah terhitung", rupiah(c.omzet_tercakup)]),
        _baris_tabel(["Cakupan HPP", persen(c.persen)], kelas="jumlah"),
        _baris_tabel(["Modal bahan terserap HPP", rupiah(rek.terserap_hpp)]),
        _baris_tabel(["Biaya di luar HPP", rupiah(rek.di_luar_hpp)]),
    ]
    catatan = list(rek.catatan)
    catatan.append(
        "Cakupan HPP adalah bagian omzet yang modal bahannya benar-benar "
        "diketahui. Sisanya tidak diperkirakan — angka yang belum diketahui "
        "dibiarkan kosong, tidak dikarang."
    )
    if c.produk_tak_terhitung:
        catatan.append(
            "Produk yang modalnya belum bisa dihitung: "
            + ", ".join(sorted(c.produk_tak_terhitung))
            + "."
        )
    return _bagian(
        "Cakupan HPP & rekonsiliasi biaya",
        _tabel(["Pos", r.periode_tampil], baris, kelas="angka dua-kolom"),
        catatan,
    )


def _fakta(r: RingkasanLaporan) -> str:
    f = r.fakta
    baris = [
        _baris_tabel(["Omzet periode", rupiah(f.omzet_total)]),
        _baris_tabel(["Bulan bercatatan dalam periode", f"{f.bulan_bercatatan} dari {len(r.bulan)}"]),
        _baris_tabel(["Bulan mencatat berturut-turut", _e(f.bulan_berturut)]),
        _baris_tabel(["Hari tercatat dalam periode", _e(f.hari_tercatat)]),
        _baris_tabel(["Cakupan HPP", persen(f.cakupan_hpp_persen)]),
        _baris_tabel(
            [
                "Prive terhadap laba bersih",
                persen(f.rasio_prive_persen) if f.rasio_prive_persen is not None else "belum dapat dihitung",
            ]
        ),
    ]
    return _bagian(
        "Fakta ringkas",
        _tabel(["Fakta", "Nilai"], baris, kelas="angka dua-kolom"),
        [
            "Bagian ini sengaja hanya memuat fakta yang bisa ditelusuri ke "
            "catatan transaksi — tanpa skor dan tanpa penilaian kelayakan. "
            "Penilaian adalah wewenang pembaca dokumen ini.",
            "\"Berturut-turut\" dihitung apa adanya dari bulan yang ada "
            "catatannya; tidak ada ambang \"cukup konsisten\" yang kami tetapkan "
            "sendiri.",
        ],
    )


def render_html(r: RingkasanLaporan, dibuat_pada: date) -> str:
    """Satu berkas HTML mandiri (CSS ter-inline) — siap dibuka atau dicetak."""
    css = BERKAS_CSS.read_text(encoding="utf-8")
    judul = f"Laporan Keuangan — {r.identitas.nama_usaha}"

    isi = "".join(
        [
            "<header>",
            "<p class='label'>Laporan Keuangan Usaha</p>",
            f"<h1>{_e(r.identitas.nama_usaha)}</h1>",
            f"<p class='periode'>Periode {_e(r.periode_tampil)}</p>",
            _identitas(r),
            "</header>",
            _tren(r),
            _laba_rugi(r),
            _arus_kas(r),
            _pos_biaya(r),
            _cakupan(r),
            _fakta(r),
            f"<section class='disclaimer'><h2>Catatan penting</h2><p>{DISCLAIMER}</p></section>",
            "<footer>",
            f"<p>Dibuat {_e(tgl_pendek(dibuat_pada))} {_e(dibuat_pada.year)} "
            f"oleh JembatanModal. {_e(CATATAN_FORMAT)}</p>",
            "</footer>",
        ]
    )

    return (
        "<!DOCTYPE html>\n"
        f'<html lang="id"><head><meta charset="utf-8">'
        f"<title>{_e(judul)}</title><style>{css}</style></head>"
        f"<body>{isi}</body></html>"
    )

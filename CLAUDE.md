# JembatanModal — repo kode

## Apa ini

Backend + UI chat JembatanModal: asisten AI yang mengubah catatan keuangan harian
UMKM menjadi kejelasan untung-rugi yang jujur dan kesiapan mengakses modal formal.

**Perencanaan hidup di `docs/` repo ini** — baca sebelum mengubah arsitektur:
- Project brief (scope & non-goals) — [`docs/00-project-brief.md`](docs/00-project-brief.md)
- Arsitektur teknis — [`docs/02-arsitektur.md`](docs/02-arsitektur.md)
- Rencana kerja — [`docs/04-rencana-kerja.md`](docs/04-rencana-kerja.md)
- Log keputusan — [`docs/keputusan.md`](docs/keputusan.md)

> `docs/` adalah **satu-satunya salinan hidup**. Salinan lama di repo
> `jembatan-modal` terpisah berhenti 2026-07-17 dan **usang** — jangan menulis
> ke sana.

Produk ini **standalone**: punya datanya sendiri, tidak membaca database produk
lain. Platform lain (majoo, BukuWarung, WargaFinance) masuk **hanya** lewat jalur
impor pilar 2 sebagai sumber opsional.

**Scope = 4 pilar**, urutan garap **1+4 → 2 → 3**:
P1 pencatatan · P4 HPP · P2 impor data · P3 dokumen modal formal.

## Aturan yang tidak boleh dilanggar

1. **LLM tidak pernah menghitung angka.** Semua angka (total, laba, HPP, skor)
   dihitung service layer dari database — deterministik, ber-unit-test. LLM hanya
   (a) mengekstrak data terstruktur dari bahasa natural, (b) menarasikan hasil
   kalkulasi. Narasi hanya boleh menyebut angka yang ada di output tool.
   → Kalau kamu tergoda menaruh aritmatika di prompt, berhenti. Itu bug.

2. **Jangan pernah mengarang angka saat data kurang.** Resep kosong, bahan tanpa
   harga, penjualan tak terkenali → kembalikan *"belum diketahui"* + apa yang
   kurang. Estimasi diam-diam lebih berbahaya daripada mengaku tidak tahu.
   **Cakupan HPP wajib ditampilkan** di laporan & skor.

3. **Impor tidak pernah auto-commit.** Hasil parse masuk sebagai draft
   (`import_rows`), wajib ditinjau pengguna sebelum jadi `transactions`. Baris
   yang parser-nya ragu ditandai.

4. **Klaim regulasi wajib bersumber.** Persyaratan KUR/perizinan hanya boleh dari
   tabel `panduan_entries` (punya `sumber_url` + `tanggal_akses`) — bukan dari
   ingatan LLM. Tanpa sumber, jangan tampilkan.

5. **Setiap dokumen kredit membawa disclaimer**: alat bantu persiapan, bukan
   jaminan persetujuan. Tidak ada janji peluang lolos.

6. **Isolasi data per-tenant di setiap tool.** Tiap query difilter `business_id`.
   Ini sekaligus mitigasi prompt injection — anggap input pengguna tidak tepercaya.

7. **HPP = model komponen biaya yang extensible.** Tiap komponen bertipe
   `{material | labor_time | overhead}`. **Implementasi sekarang `material`-only** —
   tapi **jangan bikin skema bahan-saja**: pakai `cost_items` (+`tipe`),
   `cost_item_id`, bukan `ingredient_id`. Menambah tipe nanti ke enum = satu baris;
   menambahkannya ke skema bahan-saja setelah ada data = membongkar `recipes`,
   `recipe_items`, `hpp_snapshots`, dan semua kalkulasi di atasnya.
   ⛔ Slot ≠ izin: **jangan menulis kalkulasi atau tool untuk `labor_time`/
   `overhead`.** Jasa masih non-goal.

8. **Deteksi jenis usaha berbasis struktur biaya, bukan ukuran.** `products.jenis`
   (`reseller|produksi`) ditentukan oleh *apakah usaha mengubah bahan jadi produk
   lain* — bukan seberapa besar usahanya. Tukang ayam crispy kecil = **produksi**.
   → **Jangan pernah menawarkan wawancara resep ke reseller.** Kalau itu terjadi,
   deteksinya salah — dan pengguna merasa produk ini tidak mengerti usahanya.

9. **Skor: dua keluaran terpisah.** `skor_pengguna` (komposit + progres, untuk
   motivasi) vs `fakta_penyalur` (omzet, bulan konsisten, cakupan HPP %, rasio
   prive — **fakta mentah, tanpa penilaian**). ⛔ **Jangan pernah menaruh skor
   komposit di dokumen yang dibaca penyalur** (laporan PDF, proposal KUR) sebelum
   terkalibrasi data pengajuan nyata. Menyodorkan "72/100" ke AO bank = mengarang
   otoritas yang belum kita punya — perluasan aturan #1 ke *angka penilaian*.

## Non-goals (jangan dibangun)

- Menggantikan POS/ERP.
- Filing/mengurus perizinan ke badan berwenang — hanya memandu & menjelaskan.
- Memegang uang atau menyalurkan pinjaman.
- Istilah akuntansi teknis di UI (debit/kredit/jurnal) — bahasa warung saja.
- Mengunci impor ke satu format platform tertentu.
- **Sektor jasa (labor-time) — ditunda sadar, skema-ready.** Slot `labor_time`
  ada di skema; fiturnya tidak. Menaikkannya dari non-goal menunggu validasi.

## Stack

| | |
|---|---|
| Backend | FastAPI (Python), async |
| DB | SQLite (dev) → PostgreSQL (produksi), SQLAlchemy + Alembic |
| LLM | Lewat adapter internal — **provider-agnostic**. Jangan panggil SDK vendor langsung dari luar adapter. |
| PDF | WeasyPrint (HTML/CSS → PDF) |
| Impor | Vision model (foto) + parser teks/CSV di balik `parse(berkas) → list[BarisDraft]` |

## Perintah

**Manajemen dependensi = pipenv** (Pipfile / Pipfile.lock). Setup awal:

```bash
pipenv install --dev          # buat venv + pasang core + dev (dari lock)
pipenv install --categories api   # saat garap lapisan API/LLM
pipenv install --categories pdf   # saat garap ekspor PDF
```

Sehari-hari (`pipenv run <cmd>` = jalankan di dalam venv proyek):

```bash
pipenv run pytest                    # seluruh test
pipenv run pytest tests/test_hpp.py  # unit test HPP + degradasi
pipenv run alembic upgrade head      # terapkan migrasi (dev = SQLite di data/)
pipenv run alembic revision --autogenerate -m "pesan"   # migrasi baru
pipenv run python -m app.seeds.bu_sari   # seed data demo Bu Sari (idempoten)
pipenv run ruff check . ; pipenv run ruff format .       # lint + format
```

Menjalankan slice chat (dua proses — backend FastAPI + UI web; lihat `web/README.md`):

```bash
pipenv install --categories api                     # sekali: fastapi + uvicorn
pipenv run uvicorn app.api.main:app --port 8000     # API kanal: /sesi & /chat
cd web && npm install && npm run dev                # UI mobile http://localhost:3000 (BFF → :8000)
```

> `LLM_*` di `.env` hanya diperlukan jalur **pencatatan** (ekstraksi NL). Jalur
> `koreksi_kategori` (chip) & kartu untung (stub) tak memanggil LLM. FastAPI
> internal — browser hanya bicara dengan BFF Route Handler Next.js.

> Runtime deps datang dari paket lokal editable (`-e .`) → sumber kebenaran versi
> tetap `pyproject.toml`; Pipfile hanya menautkannya + dev tools. Extra `api`/`pdf`
> jadi **kategori** Pipfile, sengaja dipisah agar core (skema + service + test)
> bisa diinstal tanpa dependensi berat.
> `make` tidak dipakai (mesin dev Windows); `Makefile` tipis tersedia sebagai
> alias `pipenv run …` bila `make` ada. Dev di sini: `.venv` di dalam proyek
> (`PIPENV_VENV_IN_PROJECT=1`), Python 3.14 via `py`.

## Konvensi

- **Bahasa domain = Bahasa Indonesia.** Nama tool, kolom DB, dan istilah domain
  pakai Bahasa Indonesia (`catat_transaksi`, `hitung_hpp`, `nominal`, `prive`) —
  konsisten dengan dokumen perencanaan. Kode infrastruktur boleh Inggris.
- **Tools = kontrak.** Tiap tool punya skema input/output tegas & diuji per-tool.
- **Service layer memegang semua kalkulasi**; tool = pembungkus tipis di atasnya.
- **Konfirmasi pencatatan dirender dari template kode**, bukan panggilan LLM kedua
  (alasan biaya — ini aksi bervolume tertinggi).
- Test ditulis **bersama** fiturnya, bukan ditumpuk di akhir.
- **Pesan commit selalu dalam Bahasa Inggris**, walau kode/domain pakai Bahasa
  Indonesia — konvensi repo Git standar. **Jangan pernah menyertakan trailer
  `Co-Authored-By: Claude ...`** di commit manapun di repo ini.

## Cara kerja yang diharapkan

- **Satu vertical slice per sesi** — kecil, jalan end-to-end, ada test, bisa
  diverifikasi. Jangan membangun fondasi berbulan-bulan tanpa yang bisa dicoba.
- Sebelum menambah tool/kolom baru: cek apakah brief & arsitektur sudah
  mencakupnya. Kalau belum, **bahas dulu** — jangan improvisasi skema.
- Kalau ada pertentangan antara dokumen perencanaan dan kode, **sebutkan**;
  jangan diam-diam memilih salah satu.
- Keputusan strategis dicatat balik ke [`docs/keputusan.md`](docs/keputusan.md),
  dengan alasan + tanggal.

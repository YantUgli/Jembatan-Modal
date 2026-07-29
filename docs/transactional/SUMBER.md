# SUMBER & STATUS VERIFIKASI FIXTURE

Legenda status:
- ✅ **TERVERIFIKASI** — struktur/kolom didasarkan pada dokumentasi resmi, sampel publik, atau statement nyata.
- 🟡 **DIREKONSTRUKSI** — bentuk file disusun dari struktur nyata yang terverifikasi, TETAPI header/delimiter CSV persis dari aplikasi belum ada sampel publik. Wajib divalidasi terhadap file asli sebelum dipakai sebagai ground truth di CI.

> Catatan penting: file rekening koran bank asli hampir semuanya di balik login, jadi tidak ada
> URL yang bisa mengunduh file CSV mentah tanpa autentikasi. Yang publik adalah *parser*/dokumentasi
> struktur, bukan file itu sendiri.

---

## 01_bca_mutasi_klikbca.csv — ✅ TERVERIFIKASI (struktur)
- Encoding: latin-1 | Line ending: **CR-only (`\r`)** | Tanpa BOM | Delimiter: koma
- 4 baris metadata + 1 baris kosong sebelum header. Apostrof prefix pada tanggal/cabang. Angka di-quote. Tanggal `DD/MM` tanpa tahun. Flag `DB`/`CR` di kolom terpisah.
- Sumber struktur (parser publik yang memproses output KlikBCA):
  - https://github.com/kadekjayak/bca-parser
  - https://github.com/gazlab/mklikbca-parser
  - https://github.com/hexters/script-mutasi-bca
- Catatan format CSV terbaru (bukan XLSX): dokumentasi Moota tentang "Download Mutasi" BCA.

## 02_bri_estatement_brimo.csv — 🟡 DIREKONSTRUKSI
- Encoding: UTF-8 | Line ending: CRLF | Delimiter: koma
- Kolom `Debet`/`Kredit` TERPISAH (perhatikan ejaan "Debet"). Tanggal `DD/MM/YY HH:MM:SS`. Baris nol `0.00` untuk sisi yang tak terpakai.
- Struktur kolom diverifikasi dari statement BRI nyata; header CSV BRImo belum ada sampel publik.
- Referensi ekspor: BRImo → Mutasi → e-Statement (PDF/CSV, hingga 5 tahun). Akun resmi @BANKBRI_ID.

## 03_mandiri_estatement_livin.csv — 🟡 DIREKONSTRUKSI
- Encoding: UTF-8 | Line ending: CRLF | Delimiter: **titik-koma (`;`)**
- SATU kolom `Nominal Transaksi` **bertanda** (minus = debit). Tanggal ISO `YYYY-MM-DD`. Ada baris FOOTER ringkasan (Saldo Awal/Total Kredit/Total Debit/Saldo Akhir) yang BUKAN transaksi.
- Struktur diverifikasi dari statement Mandiri nyata; header Excel Livin native belum ada sampel publik. PDF Livin dilindungi password (tgl lahir `DDMMYYYY`).

## 04_bni_estatement_REKONSTRUKSI.csv — 🟡 DIREKONSTRUKSI (PDF-first)
- BNI umumnya menyediakan PDF; opsi CSV disebut ada (mobile banking → Mutasi → e-Statement → PDF/CSV) tapi tidak ada sampel kolom publik.
- Perlakukan sebagai PDF-first sampai ada file CSV asli.

## 05_midtrans_transaction_report.csv — ✅ TERVERIFIKASI
- Encoding: UTF-8 | Line ending: CRLF | Delimiter: koma
- **Kolom dinamis** (dipilih via checkbox). Parser HARUS berbasis NAMA kolom, bukan posisi (anjuran resmi Midtrans: kolom baru ditambah di akhir). Arah dana lewat `Transaction Status` (settlement/refund/cancel). Payout report terpisah = 7zip berpassword.
- Sumber resmi:
  - https://docs.midtrans.com/docs/midtrans-dashboard-usage
  - https://docs.midtrans.com/reference/charge-transactions-1

## 06_gobiz_gofood_merchant.csv — ✅ TERVERIFIKASI (adanya ekspor)
- Encoding: UTF-8 | CRLF | koma. Kolom via centang. Penjualan kotor vs bersih (setelah komisi) + status settlement.
- Sumber: GoFood Merchant Portal → Transaksi → Download laporan CSV/Excel (link ke email, berlaku 7 hari).
  - https://gofoodmerchant.co.id/biztips/topics/manajemen-operasional/

## 07_kledo_import_TEMPLATE_TARGET.csv — ✅ TERVERIFIKASI (skema TARGET/INPUT)
- Ini template TUJUAN import Kledo, BUKAN ekspor bank. Berguna sebagai model transaksi tujuan pemetaan.
- Kolom pemasukan/pengeluaran terpisah. Encoding UTF-8, koma.
- Sumber: Kledo → Kas & Bank → Setting → Import Bank Statement Manual (unduh template dari sistem).

## 08_mekari_jurnal_import_TEMPLATE_TARGET.csv — ✅ TERVERIFIKASI (skema TARGET)
- Kolom **`Received`** (kredit/uang MASUK) dan **`Spent`** (debit/uang KELUAR) — semantik terbalik dari intuisi bank Indonesia. Sumber kebingungan umum.
- Sumber: Mekari Jurnal → Kas & Bank → Import Bank Statement → Download File Template.

## 09_ovo_settlement_dariPDF.csv — ✅ TERVERIFIKASI (isi), PDF-first
- **PDF/email-first** (bukan CSV yang bisa diunduh mandiri). File ini = representasi CSV dari isi PDF.
- JEBAKAN LOCALE: angka gaya Indonesia — **titik ribuan, koma desimal** (`17.201,91`), kebalikan bank. Delimiter `;` agar koma desimal tidak bentrok.
- MDR 0,7% + PPN (kategori UKE/UME/UBE). Sumber: FAQ Merchant OVO — https://www.ovo.id/faqmerchant

## 10_moka_pos_transactions.csv — ✅ TERVERIFIKASI (adanya ekspor)
- Encoding UTF-8 | CRLF | koma. Dua jenis ekspor: Export Transactions (ringkas) vs Export Item Details (rinci). Akses backoffice dibatasi ~2 tahun terakhir.
- Sumber: Moka backoffice → REPORTS → Sales → Export.
  - https://help.mokapos.com/s/article/Reporting-Transaction-Update?language=in

---

## Sumber yang HANYA PDF / belum ada CSV publik (untuk strategi impor)
- **BNI** — CSV disebut ada, tapi praktiknya PDF resmi berlogo. PDF-first.
- **OVO Merchant** — laporan settlement via email harian, bentuk PDF.
- **DANA / DANA Bisnis** — statement/riwayat via app dalam PDF.
- **BukuWarung** — laporan keuangan dibagikan/diunduh sebagai PDF/Excel dari app; skema kolom CSV persis belum ada sampel publik.
- **Shopee Seller (My Income)** — ekspor **XLSX-only** (bukan CSV native). Satu order bisa multi-baris; fee dipotong dari escrow.
- **QRIS settlement** — format tergantung aggregator/PJP (tidak ada standar tunggal). CSV/Excel/PDF.

## Prioritas pemakaian fixture
1. Paling aman dipakai langsung: **BCA (01)** & **Midtrans (05)** — struktur terverifikasi kuat.
2. Skema TARGET pemetaan: **Kledo (07)** & **Mekari Jurnal (08)**.
3. Perlu validasi file asli sebelum jadi ground truth CI: **BRI (02)**, **Mandiri (03)**, **BNI (04)**.

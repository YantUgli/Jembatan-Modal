# Arsitektur Teknis — JembatanModal

## 1. Gambaran Besar

Pola intinya: **AI agent dengan tools**. Satu LLM menjadi "resepsionis" yang memahami maksud pengguna, lalu memanggil tool yang tepat. Semua logika bisnis dan kalkulasi angka hidup di tools (kode Python deterministik), bukan di LLM.

```
┌─────────────────────────────────────────────────────────────────┐
│  KANAL (channel layer — bisa ditukar/ditambah)                  │
│  MVP: UI chat web mobile-first      Roadmap: WhatsApp, suara    │
└────────────────────────┬────────────────────────────────────────┘
                         │ pesan masuk/keluar (format seragam)
┌────────────────────────▼────────────────────────────────────────┐
│  BACKEND — FastAPI                                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  AGENT ORCHESTRATOR                                        │ │
│  │  LLM via adapter (function calling) + riwayat percakapan   │ │
│  │  "memahami maksud → panggil tool → narasikan hasil"        │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ LLM ADAPTER — satu interface internal; provider      │  │ │
│  │  │ (Gemini / Claude / Llama / dst.) tinggal ditukar     │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                    │
│  ┌──────────────────────────▼─────────────────────────────────┐ │
│  │  TOOLS (dikelompokkan per pilar — lihat project brief §3)  │ │
│  │                                                             │ │
│  │  P1  catat_transaksi · koreksi_transaksi · tanya_keuangan   │ │
│  │  P4  atur_resep · hitung_hpp · tanya_hpp      ← prioritas   │ │
│  │  P2  impor_data · tinjau_impor · konfirmasi_impor           │ │
│  │  P3  buat_laporan · hitung_skor_kesehatan ·                 │ │
│  │      susun_dokumen_kur · panduan_perizinan                  │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                    │
│  ┌──────────────────────────▼─────────────────────────────────┐ │
│  │  SERVICE LAYER (kalkulasi deterministik, validasi)         │ │
│  │  transaksi · hpp · laporan · skor · impor · dokumen        │ │
│  └──────────────────────────┬─────────────────────────────────┘ │
│                             │                                    │
│    ┌──────────────┬─────────┼──────────┬──────────────────┐     │
│  ┌─▼───────────┐ ┌▼────────────┐ ┌─────▼───────┐ ┌────────▼───┐│
│  │ Database    │ │ PDF Gen     │ │ Object      │ │ Parser     ││
│  │ (SQLite →   │ │ (WeasyPrint)│ │ storage     │ │ impor (P2) ││
│  │ PostgreSQL) │ └─────────────┘ │ PDF & unggah│ │ vision/CSV ││
│  └─────────────┘                 └─────────────┘ └────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

> **Kemandirian data.** JembatanModal **memiliki datanya sendiri** — tidak ada
> dependensi baca ke database produk lain. WargaFinance (atau platform mana pun)
> masuk **hanya lewat jalur impor pilar 2**, sebagai salah satu sumber opsional.
> Konsekuensinya: produk tetap berfungsi penuh untuk pengguna yang belum pernah
> memakai produk apa pun. (Keputusan 2026-07-17 "Standalone" — lihat [../keputusan.md](../keputusan.md).)

### Prinsip arsitektur

1. **LLM tidak pernah berhitung.** Semua angka (total, laba, skor) dihitung service layer dari database. LLM hanya (a) mengekstrak data terstruktur dari bahasa natural, dan (b) menarasikan hasil kalkulasi. Ini mitigasi utama halusinasi.
2. **Channel-agnostic.** Agent menerima/mengirim pesan dalam format internal seragam. UI web chat hanyalah salah satu adaptor; adaptor WhatsApp (Cloud API) tinggal dicolok tanpa mengubah inti.
3. **Provider-agnostic.** Orchestrator memanggil LLM hanya lewat satu interface internal (`kirim_ke_llm(riwayat, tools) → teks | panggilan_tool`). Format request/response tiap vendor hidup di satu file adapter — ganti provider (mis. dari free tier satu vendor ke vendor lain) = ganti satu adapter, bukan menulis ulang inti. Semua penyedia besar (Gemini, Claude, OpenAI, Llama via Groq/Together, DeepSeek) mendukung pola function calling yang sama.
4. **Tools = kontrak yang jelas.** Tiap tool punya skema input/output tegas, sehingga perilaku agent bisa diuji per-tool — dan suite ujinya sekaligus menjadi benchmark pemilihan provider (lihat §7).

## 2. Komponen & Alasan Pemilihan

| Komponen | Pilihan | Alasan |
|----------|---------|--------|
| Backend framework | **FastAPI** (Python) | Async cocok untuk panggilan LLM API; ekosistem Python kuat untuk PDF & data; sudah dikuasai developer |
| LLM | **Ditentukan lewat benchmark** — kandidat: Gemini (free tier AI Studio), Claude, Llama (Groq/Together), DeepSeek | Diakses lewat LLM adapter (provider-agnostic). Kriteria pemilihan: (1) akurasi ekstraksi Bahasa Indonesia informal pada suite uji §7, (2) keandalan function calling, (3) biaya/kuota gratis. Kuota & harga diverifikasi ke halaman resmi provider saat memutuskan |
| Database | **SQLite** (awal) → **PostgreSQL** (produksi) | SQLite tanpa setup saat pengembangan awal; skema dirancang agar migrasi ke Postgres mulus (via SQLAlchemy) |
| Parser impor (P2) | **Vision model** (foto/screenshot) + parser teks/CSV, di balik satu interface `parse(berkas) → list[BarisDraft]` | Menambah sumber baru = menambah adaptor, tanpa menyentuh inti (§3b). Vision lewat LLM adapter yang sama agar provider tetap bisa ditukar |
| ORM & migrasi | **SQLAlchemy + Alembic** | Standar de-facto, mendukung dua database di atas |
| PDF | **WeasyPrint** (HTML/CSS → PDF) | Layout laporan dirancang sebagai template HTML — mudah diiterasi, hasil profesional |
| Riwayat percakapan | Tabel `messages` di DB | Konteks percakapan per-pengguna untuk multi-turn (wawancara KUR butuh ini) |
| Autentikasi (awal) | Login sederhana berbasis nomor HP + OTP dummy/PIN | Cukup untuk pengembangan awal; produksi pakai OTP WhatsApp/SMS sungguhan |
| STT (input suara) | Nanti — bukan lingkup awal | Arsitektur kanal sudah menyiapkannya (pesan suara = adaptor input lain) |

## 3. Desain Tools untuk Agent

| Pilar | Tool | Input (dari LLM) | Proses (deterministik) | Output ke LLM |
|---|------|------------------|------------------------|----------------|
| P1 | `catat_transaksi` | jenis, nominal, deskripsi, kategori, tanggal | Validasi → simpan ke DB | Konfirmasi + saldo ringkas |
| P1 | `koreksi_transaksi` | id/rujukan ("yang tadi"), field yang diubah | Validasi → update, simpan jejak | Konfirmasi perubahan |
| P1 | `tanya_keuangan` | periode, jenis pertanyaan | Query agregat (omzet, laba, top item) | Angka hasil query untuk dinarasikan |
| **P4** | `atur_resep` | nama produk, yield, daftar bahan + takaran | Simpan resep/BOM; tandai bahan yang harganya belum diketahui | Resep tersimpan + daftar bahan yang masih perlu harga |
| **P4** | `hitung_hpp` | produk (opsional; default semua) | Hitung HPP/unit dari resep × harga bahan (§4a) | HPP/unit, laba kotor/unit, asal tiap angka |
| **P4** | `tanya_hpp` | produk, periode | Query HPP + margin per produk | Angka untuk dinarasikan ("per kotak untung Rp…") |
| **P2** | `impor_data` | rujukan file yang diunggah, tipe sumber | Parse (vision/CSV) → simpan sebagai **draft**, **tidak** langsung jadi transaksi | Ringkasan draft: N baris terbaca, M perlu dikonfirmasi |
| **P2** | `tinjau_impor` | import_id, filter | Ambil baris draft untuk ditampilkan/dikoreksi | Daftar baris + tanda yang meragukan |
| **P2** | `konfirmasi_impor` | import_id, baris yang disetujui | Commit draft → `transactions` (`sumber_input='impor'`) | Jumlah transaksi masuk |
| P3 | `buat_laporan` | periode, jenis laporan | Hitung laba-rugi/arus kas → render template HTML → PDF | URL file PDF + ringkasan angka |
| P3 | `hitung_skor_kesehatan` | — | Hitung komponen skor dari DB | Skor total + rincian per komponen |
| P3 | `susun_dokumen_kur` | hasil wawancara (terstruktur) | Gabung data wawancara + laporan keuangan → render proposal PDF + checklist | URL dokumen + checklist |
| P3 | `panduan_perizinan` | jenis usaha, pertanyaan | Ambil dari **basis panduan terkurasi** (bersumber + tanggal) — bukan hasil ingatan LLM | Langkah + syarat + sumber & tanggal |

> `panduan_perizinan` sengaja berbentuk tool, bukan pengetahuan LLM. Aturan
> perizinan berubah dan salah info = pembunuh kepercayaan. LLM hanya boleh
> menarasikan isi basis panduan yang kita kurasi dan beri tanggal.

Alur contoh — *"tadi laku 5 risol 75 ribu"*:

```
Pengguna → Agent: LLM mengekstrak {jenis: pemasukan, nominal: 75000,
deskripsi: "risol 5 kotak", kategori: penjualan} → panggil catat_transaksi
→ service menyimpan ke DB → tool mengembalikan konfirmasi →
LLM menarasikan: "✅ Tercatat ya Bu, pemasukan Rp75.000 dari 5 kotak risol."
```

## 3a. Metodologi HPP (Pilar 4) — jantung "untung jujur"

Tanpa HPP, laba-rugi hanya "uang masuk − uang keluar" — itu **bukan untung
bersih**, dan laporan yang dibangun di atasnya menyesatkan. Pilar 4 membuat
angka di semua pilar lain jujur.

### Implikasi yang mengubah pilar 1

HPP mustahil dihitung kalau transaksi cuma berisi nominal + deskripsi bebas.
**Transaksi harus tertaut ke produk/bahan beserta kuantitasnya:**

```
"laku 5 kotak risol 75rb"   → pemasukan,  product_id=risol,    qty=5
"beli minyak 2 liter 38rb"  → pengeluaran, cost_item_id=minyak, qty=2, satuan=liter
                              (tipe='material')
                              └─► sekaligus memperbarui harga minyak = Rp19.000/liter
```

Konsekuensinya: ekstraksi pilar 1 harus **mengenali produk & takaran**, bukan
sekadar nominal. Ini menaikkan bobot pilar 1 — dan alasan kenapa 1+4 digarap bersama.

### Satu primitif biaya, banyak kasus khusus

Reseller dan produsen **bukan dua model** — keduanya kasus khusus dari satu
model. HPP = **kumpulan komponen biaya**, tiap komponen bertipe
`{material | labor_time | overhead}`:

| Segmen | Komponen yang terpakai | Status implementasi |
|---|---|---|
| **Reseller** (tukang sayur, toko obat) | `material` = harga beli terakhir | ✅ sekarang |
| **Produksi** (Bu Sari, ayam crispy) | `material` × takaran ÷ yield | ✅ sekarang |
| **Jasa** (salon, laundry) | `labor_time` × tarif + `material` (consumable) | ⏸️ slot disiapkan, tidak diimplementasi |
| **Bengkel / servis HP** | `material` (parts) + `labor_time` | ⏸️ slot disiapkan |
| **Cafe/resto** | `material` + `labor_time` + `overhead` per porsi | ⏸️ slot disiapkan |

> **Batas keras — jangan dilanggar.** *Rancang* skema agar `labor_time` dan
> `overhead` bisa masuk; **implementasikan hanya `material` sekarang.** Tujuannya
> menghindari skema bahan-saja yang menyandera migrasi nanti — **bukan** membangun
> fitur jasa hari ini. Jasa tetap non-goal
> ([00-project-brief.md §4](00-project-brief.md)). Kalau ada yang mulai menulis
> tool wawancara tarif jasa, itu sudah melewati batas.

Kenapa ini asuransi yang murah: menambahkan tipe komponen ke skema yang sudah
memilikinya = satu baris enum. Menambahkannya ke skema `ingredients`-saja =
membongkar `recipes`, `recipe_items`, `hpp_snapshots`, dan semua kalkulasi di
atasnya, **setelah** ada data produksi. Biaya sekarang mendekati nol; biaya nanti
tidak.

**Formula yang berlaku sekarang** (material-only — bentuk umum di atas menyusut
ke ini persis):

```
HPP_per_unit(reseller)  = harga_beli_terakhir
HPP_per_unit(produksi)  = Σ(qty_bahanᵢ × harga_satuanᵢ) ÷ yield_qty
laba_kotor_per_unit     = harga_jual − HPP_per_unit
HPP_total(periode)      = Σ(qty_terjual_produk × HPP_per_unit_produk)
```

Bentuk umum yang dituju (belum diimplementasi, ditulis agar skema tidak menutupnya):

```
HPP_per_unit = Σ(komponenᵢ.qty × komponenᵢ.harga_satuan) ÷ yield_qty
               dengan komponenᵢ.tipe ∈ {material, labor_time, overhead}
```

### Deteksi jenis usaha: berbasis struktur biaya, bukan ukuran

`products.jenis` (`reseller|produksi`) **bukan sekadar kolom** — ia penanda
segmen, dan salah menebaknya berarti mengajukan pertanyaan yang salah ke pengguna.

Aturannya: **klasifikasi berdasarkan apakah usaha mengubah bahan jadi produk
lain**, bukan berdasarkan ukurannya. *Tukang ayam crispy baru mulai* =
**produksi** (ayam + tepung + minyak → potongan crispy), walau usahanya kecil
sekali. *Toko obat kecil* = **reseller**, walau terdengar "lebih formal".

Konsekuensi ke perilaku agent: **reseller tidak pernah ditawari wawancara
resep.** Menanyakan "sekali bikin jadi berapa?" ke tukang sayur adalah tanda
deteksinya salah — dan pengalaman yang membuat pengguna merasa produk ini tidak
mengerti usahanya.

> *Wrinkle* yang dicatat tapi **bukan garapan sekarang**: sebagian reseller punya
> kerutan khusus — toko obat punya kedaluwarsa & regulasi, kelontong punya stok
> mati. Dicatat agar tidak terlupa, tidak untuk didesain sekarang.

Contoh: 1 resep risol → yield 10 kotak; bahan = tepung 1kg (Rp12.000) + minyak
0,5L (Rp9.500) + ayam 0,5kg (Rp18.000) → total Rp39.500 ÷ 10 = **HPP Rp3.950/kotak**.
Harga jual Rp15.000 → laba kotor Rp11.050/kotak.

### Dari mana harga bahan datang

1. **Otomatis dari transaksi pembelian** (utama) — tiap pengeluaran bahan dengan
   qty + satuan menghasilkan harga satuan bertanggal. Inilah kenapa pilar 1 & 4
   saling mengunci.
2. **Ditanyakan** saat resep dibuat, bila bahan belum pernah tercatat dibeli.

**Harga mana yang dipakai:** *harga beli terakhir* — deterministik, sederhana,
responsif terhadap kenaikan harga. (Trade-off: rata-rata tertimbang lebih halus
tapi lebih sulit dijelaskan ke pengguna; "bahan naik → HPP naik" jauh lebih mudah
dipahami. Bisa ditinjau ulang nanti.)

### Peran GenAI di sini

LLM **mewawancarai resep secara ngobrol** — bukan form BOM:

> "Bu, sekali bikin risol jadi berapa kotak?" → *"10 kotak"*
> "Pakai bahan apa saja & berapa banyak?" → *"tepung sekilo, minyak setengah liter, ayam setengah kilo"*
> "Minyak sudah saya tahu harganya dari belanja kemarin (Rp19.000/liter). Tepung sama ayam belum — sekilo berapa?"

LLM mengekstrak & bertanya. **Perhitungannya tetap di service layer.**

### Wajib gagal dengan jujur (degradasi)

HPP tidak boleh dikarang saat data kurang:

| Kondisi | Perilaku |
|---|---|
| Produk belum punya resep | HPP = *belum diketahui*; produk tidak masuk hitungan laba kotor |
| Bahan belum ada harganya | HPP = *belum lengkap* + daftar bahan yang kurang |
| Penjualan tak terkenali produknya | Tidak dipaksa masuk HPP |
| Harga bahan terakhir sudah lama | HPP tetap dihitung + **tanggal harga ditampilkan** |

Laporan & skor **selalu menampilkan cakupan HPP** ("HPP tercakup untuk 78% omzet
periode ini") — pengguna tahu persis seberapa bisa dipercaya angkanya. Ini
konsisten dengan prinsip #1: lebih baik mengaku tidak tahu daripada mengarang.

### Penahapan

1. **Tahap 1** — reseller (harga beli terakhir) + produksi dengan resep & harga ditanya manual.
2. **Tahap 2** — harga bahan otomatis tertaut dari transaksi pembelian.
3. **Tahap 3** — HPP bergerak: notifikasi saat kenaikan harga bahan menggerus margin.

## 3b. Alur Impor Data (Pilar 2)

Menyelesaikan masalah **cold-start**: pengguna baru = data kosong = skor & laporan
tak berguna berminggu-minggu.

```
Unggah (foto buku / screenshot / CSV / export platform)
   │
   ▼  parser: vision model (foto) | parser teks (CSV/export)
Baris DRAFT  ──►  ditinjau & dikoreksi pengguna  ──►  commit ke transactions
   │                                                    (sumber_input='impor')
   └─► TIDAK PERNAH langsung jadi transaksi
```

**Aturan keras: impor tidak pernah auto-commit.** Salah parse yang langsung masuk
= pembukuan tercemar diam-diam, dan pengguna tidak punya cara tahu. Draft +
tinjau wajib — ini perluasan prinsip "konfirmasi tiap pencatatan" ke skala massal.
Baris yang parser-nya ragu ditandai eksplisit agar ditinjau duluan.

**Sumber bersifat plugin**, bukan hardcode ke satu platform:

| Sumber | Parser | Catatan |
|---|---|---|
| Foto buku tulis / nota | vision model | Paling relevan untuk segmen mikro |
| Screenshot chat / catatan HP | vision model | |
| CSV / spreadsheet | parser teks + LLM pemetaan kolom | Kolom bebas → dipetakan ke skema kita |
| Export platform (majoo, BukuWarung, **WargaFinance**, dst.) | adaptor per-format | **Salah satu sumber, bukan patokan** — tiap format = satu adaptor kecil |

Visi ekspansi: menambah bentuk laporan = menambah adaptor, **tanpa** menyentuh
inti. Karena itu antarmuka parser dibuat seragam:
`parse(berkas) → list[BarisDraft]`.

## 4. Metodologi Skor Kesehatan Usaha (0–100)

Dihitung **sepenuhnya di service layer** — LLM hanya menarasikan hasilnya.

### Dua keluaran terpisah — jangan campur

Skor memikul dua peran yang bertabrakan: **memotivasi pengguna** dan **menjadi
bukti ke penyalur**. Ambangnya masih kalibrasi awal (tebakan berbaju angka), jadi
satu keluaran tidak bisa melayani keduanya dengan jujur. Pisahkan di level API,
bukan cuma di level UI:

| Keluaran | Isi | Sifat |
|---|---|---|
| **`skor_pengguna`** | Skor komposit 0–100, rincian komponen, progres/streak, cakupan HPP | Motivasi. Boleh kasar, boleh berubah saat kalibrasi ulang |
| **`fakta_penyalur`** | **Hanya fakta mentah terverifikasi**: omzet per periode, jumlah bulan pencatatan konsisten, cakupan HPP %, rasio prive terhadap laba. **Tanpa skor komposit, tanpa penilaian** | Fakta yang bisa ditelusuri ke transaksi |

> **Aturan keras:** **skor komposit tidak pernah masuk ke dokumen yang dibaca
> penyalur** (laporan PDF, proposal KUR) sebelum terkalibrasi data pengajuan
> nyata. Menyodorkan "72/100" ke AO bank = mengarang otoritas yang belum kita
> punya; bank punya model risikonya sendiri. Ini perluasan langsung prinsip #1 —
> "angka tidak dikarang" berlaku juga untuk *angka penilaian*, bukan cuma
> aritmatika.

### Flywheel kalibrasi

Ambang skor tidak akan pernah benar lewat perdebatan internal. Yang
mengkalibrasinya adalah data hasil:

```
pengajuan KUR lewat aplikasi → dilacak hasilnya (lolos | ditolak | plafon cair)
        └─► kur_outcomes ─► kalibrasi ulang bobot & ambang komponen skor
                            └─► setelah cukup data: skor layak dihadapkan penyalur
```

Tanpa flywheel ini, skor selamanya tetap tebakan — dan selamanya tidak boleh
dihadapkan ke penyalur. Konsumsi datanya ada di [03-roadmap.md](03-roadmap.md) H4;
yang dibangun sekarang cuma **pencatatan hasilnya**, bukan kalibrasinya.

| Komponen | Bobot | Cara hitung (per periode 30 hari) |
|----------|-------|-----------------------------------|
| Konsistensi pencatatan | 30 | % hari dengan minimal 1 transaksi tercatat |
| Margin laba | 25 | Laba bersih / omzet, dipetakan ke skala 0–25 (margin ≥20% = penuh) |
| Tren omzet | 25 | Perbandingan omzet periode berjalan vs sebelumnya (naik = penuh, stabil = sebagian, turun = rendah) |
| Disiplin prive | 20 | Rasio penarikan pribadi terhadap laba (prive ≤50% laba = penuh) |

Catatan desain:
- **Bergantung pada HPP (§3a).** Komponen *margin laba* baru bermakna kalau laba bersih dihitung setelah HPP. Bila cakupan HPP rendah, komponen ini **ditandai "belum bisa dihitung"** dan bobotnya dinormalisasi — jangan pernah menyajikan margin dari "uang masuk − uang keluar" seolah itu margin sesungguhnya.
- Ambang batas di atas adalah **kalibrasi awal** — disempurnakan saat validasi dengan pelaku UMKM dan (idealnya) masukan praktisi pembiayaan mikro.
- Rincian per-komponen selalu ditampilkan: pengguna tahu persis kenapa skornya 58, dan apa yang menaikkannya. Transparansi = kepercayaan + motivasi.
- Skor disimpan sebagai snapshot berkala sehingga progresnya bisa ditampilkan ("naik 16 poin dalam 2 bulan" — kalimat kuat dalam proposal KUR).

## 5. Skema Data Inti

```
── Inti ─────────────────────────────────────────────────────────────
users            : id, nama, no_hp, created_at
businesses       : id, user_id, nama_usaha, jenis_usaha, lokasi, mulai_usaha
transactions     : id, business_id, jenis (pemasukan|pengeluaran|operasional|prive),
                   nominal, deskripsi, kategori_detail, tanggal, sumber_input
                   (chat|impor|manual), raw_text,
                   ── tautan untuk HPP (P4), semuanya nullable ──
                   product_id     (pemasukan / pembelian barang reseller)
                   cost_item_id   (pembelian bahan — kelak juga komponen biaya
                                   lain; lihat blok Pilar 4 di bawah)
                   qty, satuan
messages         : id, business_id, role (user|assistant), content, created_at

── Pilar 4: HPP (model komponen biaya) ──────────────────────────────
products         : id, business_id, nama, jenis (reseller|produksi),
                   harga_jual, created_at
                   └─ `jenis` = penanda segmen; ditentukan struktur biaya,
                      bukan ukuran usaha (§3a)

cost_items       : id, business_id, tipe (material|labor_time|overhead),
                   nama, satuan_baku
                   └─ generalisasi `ingredients`. SEKARANG hanya baris
                      tipe='material' yang dibuat & dipakai; dua tipe lain
                      adalah SLOT — enum sudah menampungnya, kode belum.
cost_item_prices : id, cost_item_id, harga_satuan, satuan, tanggal,
                   sumber (transaksi|ditanya), transaction_id (nullable)
                   └─ append-only, bertanggal. Untuk labor_time nanti,
                      "harga_satuan" = tarif per jam — bentuknya sudah muat.
recipes          : id, product_id, yield_qty, yield_satuan, updated_at
                   └─ tetap dipakai produksi; untuk jasa nanti yield=1 layanan
recipe_items     : id, recipe_id, cost_item_id, qty, satuan
                   └─ tidak lagi terikat "ingredient"; komponen apa pun muat
hpp_snapshots    : id, product_id, hpp_per_unit, rincian (JSON: asal tiap angka
                   + tanggal harga dipakai + tipe tiap komponen), created_at

── Pilar 2: Impor ───────────────────────────────────────────────────
imports          : id, business_id, sumber (foto|csv|export_majoo|export_wf|…),
                   file_path, status (draft|sebagian|selesai|batal),
                   ringkasan (JSON), created_at
import_rows      : id, import_id, raw, parsed (JSON), keyakinan (0–1),
                   status (draft|diterima|ditolak), transaction_id (nullable)

── Pilar 3: Dokumen & panduan ───────────────────────────────────────
score_snapshots  : id, business_id, skor_total, komponen (JSON), periode, created_at
                   └─ skor_total = keluaran PENGGUNA saja (§4). Yang masuk
                      dokumen penyalur adalah fakta mentah, bukan kolom ini.
documents        : id, business_id, jenis (laporan|proposal_kur), periode,
                   file_path, created_at
kur_interviews   : id, business_id, jawaban (JSON), status, created_at
kur_outcomes     : id, business_id, document_id, hasil (diajukan|lolos|ditolak),
                   plafon_cair (nullable), alasan_penolakan (nullable),
                   tanggal, created_at
                   └─ bahan bakar flywheel kalibrasi (§4). Yang dibangun sekarang
                      hanya PENCATATAN hasilnya; kalibrasinya menunggu data cukup.
panduan_entries  : id, topik (kur|nib|izin_usaha|badan_hukum|…), jenis_usaha,
                   isi, sumber_url, tanggal_akses, berlaku_sampai (nullable)
```

Catatan desain:
- **`raw_text`** — input asli pengguna disimpan agar kesalahan ekstraksi LLM bisa diaudit & dikoreksi.
- **`cost_item_prices` append-only** — harga bertanggal, tidak ditimpa. HPP bisa dijelaskan ("pakai harga minyak per 12 Juli") dan ditelusuri mundur.
- **`cost_items.tipe` sengaja enum sejak awal** — walau hanya `material` yang diimplementasi. Ini titik di mana skema menolak menyandera dirinya sendiri: menambah `labor_time` nanti = satu baris enum + kalkulasi baru, bukan pembongkaran (§3a).
- **`hpp_snapshots.rincian`** — menyimpan asal tiap angka. Tanpa ini, HPP jadi kotak hitam dan melanggar prinsip transparansi.
- **`import_rows.keyakinan`** — dipakai untuk menandai baris yang perlu ditinjau duluan.
- **`panduan_entries.sumber_url` + `tanggal_akses` wajib** — aturan emas repo: klaim regulasi tak boleh tanpa sumber & tanggal. `berlaku_sampai` menandai panduan yang perlu ditinjau ulang.

## 6. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| LLM salah ekstrak nominal/kategori | Pembukuan salah → laporan salah | Konfirmasi tiap pencatatan + perintah koreksi via chat ("eh salah, itu 57 ribu") + `raw_text` tersimpan |
| Halusinasi angka di narasi | Pengguna salah ambil keputusan | Semua angka dari kalkulasi; narasi LLM dibatasi hanya boleh menyebut angka yang ada di output tool |
| Privasi data keuangan | Data sensitif bocor | Enkripsi at-rest & in-transit, data per-tenant terisolasi, tidak dipakai melatih model, kebijakan retensi jelas |
| Ekspektasi berlebihan soal KUR | Pengguna kecewa/dirugikan | Disclaimer eksplisit di setiap dokumen: alat bantu persiapan, bukan jaminan persetujuan; tidak ada janji angka peluang lolos |
| Biaya LLM API membengkak | Tidak sustainable | Lihat §6a Strategi Biaya LLM: routing model murah/mahal per tugas, prompt caching, windowing riwayat, konfirmasi via template |
| Ketergantungan vendor LLM (free tier habis, harga naik, layanan berubah) | Produk macet / biaya melonjak | LLM adapter (prinsip arsitektur #3) — migrasi provider = satu file; suite uji §7 portabel sebagai benchmark ulang saat pindah |
| Ketergantungan koneksi internet | Pengguna sinyal lemah gagal mencatat | UI ringan; antrean pesan saat offline (roadmap PWA); jawaban singkat hemat data |
| **Impor salah parse masuk diam-diam** | Pembukuan tercemar tanpa pengguna sadar → semua laporan & skor salah | **Draft + tinjau wajib, tidak pernah auto-commit** (§3b); baris ragu ditandai; `import_rows.raw` disimpan untuk audit |
| **Resep/takaran diisi asal → HPP salah** | "Untung jujur" justru jadi bohong yang meyakinkan | Tampilkan asal tiap angka (`hpp_snapshots.rincian`); konfirmasi resep saat dibuat; sajikan HPP sebagai *perkiraan* dengan tanggal harga |
| **Cakupan HPP rendah tapi laporan tampak utuh** | Pengguna kira laba bersihnya akurat padahal separuh omzet tak ber-HPP | Cakupan HPP **selalu** ditampilkan di laporan & skor ("tercakup 78% omzet"); komponen skor terkait ditandai "belum bisa dihitung" bila cakupan di bawah ambang |
| **Harga bahan basi** | HPP meleset saat harga naik | `cost_item_prices` bertanggal; tanggal harga ditampilkan; roadmap: **margin-watch** — peringatan proaktif saat harga naik menggerus margin (sekaligus mesin retensi utama, [01-konsep-produk.md §4](01-konsep-produk.md)) |
| **Skor komposit dipakai sebagai otoritas sebelum terkalibrasi** | Penyalur salah percaya / produk mengarang wewenang yang belum dimiliki | Skor **dua keluaran** (§4): komposit hanya ke pengguna; ke penyalur **fakta mentah saja** sampai flywheel kalibrasi berputar |
| **Deteksi jenis usaha salah** | Reseller diwawancarai resep → produk terasa tidak mengerti usahanya; produsen tidak pernah dapat HPP | Klasifikasi berbasis struktur biaya (§3a), bukan ukuran; pengguna bisa mengoreksi lewat chat; keputusan deteksi tersimpan & dapat diaudit lewat `raw_text` |
| **Biaya vision model untuk impor foto** | Impor jadi mahal per pengguna | Vision hanya dipanggil saat unggah (bukan per pesan); satu panggilan per berkas, bukan per baris; batasi resolusi & ukuran; lihat §6a |

## 6a. Strategi Biaya LLM

Prinsip-prinsip ini lintas-vendor — berlaku siapa pun providernya. Urut dari dampak terbesar:

1. **Routing model per tugas.** Ekstraksi `catat_transaksi` / `tanya_keuangan` (±90% trafik) pakai model kecil/murah (atau free tier); narasi skor & percakapan pakai model menengah; wawancara + drafting proposal KUR (jarang, bernilai tinggi) boleh pakai model terbaik. Adapter menerima parameter model per panggilan.
2. **Konfirmasi pencatatan via template, bukan inferensi kedua.** Alur tool-use normal = 2 panggilan model (ekstrak → narasikan). Untuk `catat_transaksi`, konfirmasi ("✅ Tercatat: …") dirender dari template di kode — memangkas ±separuh biaya aksi tervolume-tertinggi. Narasi LLM dipakai hanya untuk jawaban yang butuh bahasa (skor, insight, laporan).
3. **Windowing riwayat percakapan.** Jangan kirim tabel `messages` mentah. Pencatatan cukup 2–4 pesan terakhir; wawancara KUR memakai state terstruktur di `kur_interviews` (ringkasan jawaban sejauh ini + pertanyaan terakhir), sehingga konteks konstan, tidak membengkak seiring panjang chat.
4. **Ramah prompt caching.** Semua provider besar punya mekanisme caching prefix (nama & mekanismenya beda-beda). Aturannya sama: system prompt & urutan definisi tools dibekukan; konten yang berubah (tanggal hari ini untuk parsing "tadi/kemarin", konteks per-pengguna) ditaruh di pesan user — **bukan** di system prompt — supaya prefix bisa di-cache dan di-share lintas request.
5. **Vision dipakai hemat (pilar 2).** Vision adalah panggilan termahal per token. Aturannya: dipanggil **hanya saat unggah**, satu panggilan per berkas (bukan per baris), resolusi & ukuran dibatasi di klien sebelum dikirim. Impor adalah aksi jarang & bernilai tinggi (sekali di onboarding) — boleh pakai model bagus, asal tidak masuk jalur per-pesan.
6. **Jumlah tools bertambah → prompt membengkak.** Dengan 13 tools, definisi tools ikut terkirim tiap panggilan. Bila terasa: kelompokkan tools per konteks (mis. tools resep hanya diekspos saat sesi `atur_resep` berjalan) alih-alih mengirim semuanya sekaligus. **Catatan:** pengelompokan tools per jenis usaha (tools resep tidak diekspos ke reseller) bukan sekadar hemat biaya — itu **syarat kebenaran perilaku**, turunan dari "kedalaman adaptif lewat deteksi" (§3a, [00-project-brief.md §6](00-project-brief.md)). Penghematan tokennya kebetulan ikut.

## 7. Verifikasi (saat implementasi)

1. **Per-tool**: unit test service layer (kalkulasi laporan, skor) dengan data fixture.
2. **HPP (P4)**: unit test formula dengan fixture — reseller, produksi, dan **semua jalur degradasi** (resep kosong, bahan tanpa harga, penjualan tak terkenali produk, cakupan parsial). Uji juga: HPP berubah ketika harga bahan naik, dan `rincian` benar-benar menyebutkan asal tiap angka.
3. **Ekstraksi LLM**: suite kalimat uji Bahasa Indonesia informal ("laku 5 risol 75rb", "bli minyak 38ribu", "ambil buat anak 50k") → bandingkan hasil ekstraksi dengan ekspektasi. **Termasuk ekstraksi produk & takaran** ("5 kotak", "2 liter", "setengah kilo") — tanpa ini HPP tidak jalan. Suite ini dipakai ganda sebagai **benchmark pemilihan provider**: jalankan 30–50 kalimat yang sama ke 2–3 kandidat (lewat adapter masing-masing), pilih berdasarkan akurasi — bukan asumsi.
4. **Impor (P2)**: uji tiap adaptor parser dengan berkas contoh (foto buku, CSV berkolom aneh, export platform). **Uji negatif wajib**: berkas berantakan/tak terbaca → tidak boleh ada baris yang lolos ke `transactions` tanpa persetujuan.
5. **End-to-end**: skenario Bu Sari (lihat dokumen konsep §3) dijalankan penuh — dari pencatatan hari pertama sampai dokumen KUR keluar — dengan data demo yang bisa di-seed.
6. **PDF**: render laporan & proposal dari data seed, periksa manual format dan kebenaran angka — termasuk baris HPP & cakupannya.

# Rencana Kerja — JembatanModal

> **Frame:** produk jangka panjang, standalone. Scope = 4 pilar
> ([00-project-brief.md](00-project-brief.md) §3), urutan garap **1+4 → 2 → 3**.
> Desain teknis: [02-arsitektur.md](02-arsitektur.md).
>
> **Premis yang terkunci** ([../keputusan.md](../keputusan.md)):
> - Kode hidup di **folder/repo terpisah** — bukan extend WargaFinance.
> - JembatanModal **punya datanya sendiri**; WargaFinance masuk hanya sebagai
>   salah satu sumber impor opsional di pilar 2.
> - IDCamp = tonggak validasi, **bukan** pembatas scope. Tidak ada tugas di
>   dokumen ini yang mundur dari deadline lomba.
>
> ⏱️ Durasi sengaja tidak diisi — ini bukan pacuan tenggat.

---

## Cara mengerjakan

**Satu vertical slice per sesi.** Tiap slice: kecil, jalan end-to-end, bisa
diverifikasi, punya test. Jangan menumpuk fondasi berbulan-bulan sebelum ada
yang bisa dicoba. Urutan di bawah disusun agar tiap slice menghasilkan sesuatu
yang benar-benar bisa dipakai.

---

## Tahap 0 — Validasi *(paralel, jangan memblokir kode)*

Murah tapi menentukan. Hasilnya menyempurnakan Tahap 3 & 4, bukan menahannya.

- [ ] Wawancara 5–10 pelaku UMKM: bagaimana mereka mencatat sekarang; **apakah mereka tahu untung bersihnya** (uji premis pilar 4); pernahkah mencoba/ingin mengajukan KUR & apa yang menghentikan.
- [ ] **Uji premis inti** (brief §2 klaster #2): apakah ketiadaan laporan benar-benar penghambat akses KUR — konfirmasi dari sisi pelaku **dan** sisi penyalur.
- [ ] Ngobrol dengan 1–2 AO bank / petugas koperasi / pendamping KUR: format laporan yang benar-benar dilihat, alasan umum penolakan.
- [ ] Tunjukkan mockup alur chat → amati apakah paham tanpa dijelaskan.
- [ ] Kumpulkan **persyaratan KUR & perizinan dari sumber resmi** (kur.ekon.go.id, OSS, bank penyalur) → isi `panduan_entries` lengkap `sumber_url` + `tanggal_akses`. **Jangan pernah dikarang LLM.**
- [ ] Kumpulkan **contoh berkas impor nyata** (foto buku tulis, screenshot, export platform) — jadi fixture uji Tahap 3 & 5.
- [ ] Buat `docs/sumber-data.md` — semua statistik pasar berstatus belum-final sampai ini ada.

### Utang validasi dari penajaman target (2026-07-17)

Empat asumsi baru yang lahir dari analisis mekanika produk, **bukan** dari
lapangan. Semuanya masih hipotesis sampai diuji:

- [ ] **⚠️ Apakah riwayat QRIS + konsistensi pencatatan benar-benar mengubah kepercayaan penyalur — atau mereka tetap minta rekening koran?** *Tanyakan langsung ke AO bank.* **Ini premis paling menentukan**: ia yang menentukan apakah pilar 2 punya tujuan verifikasi ([03-roadmap.md](03-roadmap.md) H2) atau cuma onboarding, dan apakah adaptor QRIS naik prioritas (Tahap 3).
- [ ] **Apakah produsen (Bu Sari) mau membayar success-fee saat modal cair?** Uji bentuk harga per-nilai vs langganan.
- [ ] **Apakah cafe mau langganan analitik food-cost?** Uji apakah segmen atas punya bentuk harga sendiri.
- [ ] **Apakah aha moment jasa (*"waktumu punya harga, dan selama ini kamu berikan gratis"*) benar bernilai bagi pelaku mikro jasa?** Harus lolos sebelum jasa dinaikkan dari non-goal ([00-project-brief.md §4](00-project-brief.md)).
- [ ] **Uji balik premis "nilai menumpuk di tengah"** ([00-project-brief.md §5](00-project-brief.md)): apakah reseller/ultra-mikro ternyata *tetap* mau membayar untuk sekadar "catatan rapi"? Kalau ya, dua sumbu itu perlu ditinjau ulang.

## Tahap 1 — Fondasi Teknis

- [ ] Setup project FastAPI: struktur folder, config, SQLAlchemy + Alembic, lint/format, CI dasar.
- [ ] **CLAUDE.md repo kode** — salin dari [../CLAUDE-jembatan-modal.md](../CLAUDE-jembatan-modal.md), sesuaikan perintah nyata.
- [ ] Implementasi skema inti ([02-arsitektur.md §5](02-arsitektur.md)) — termasuk tautan HPP di `transactions` (`product_id`, `cost_item_id`, `qty`, `satuan`) **sejak awal**; menambahkannya belakangan = migrasi menyakitkan.
- [ ] **Skema komponen biaya yang extensible sejak migrasi pertama**: `cost_items.tipe` sebagai enum `{material|labor_time|overhead}`, `recipe_items` menunjuk `cost_item_id` (bukan `ingredient_id`). **Hanya `material` yang diimplementasi & diuji sekarang** — dua tipe lain adalah slot kosong. Jangan bikin skema bahan-saja ([02-arsitektur.md §3a](02-arsitektur.md)). ⛔ Jangan pula menulis kalkulasi/tool untuk `labor_time` — itu melewati batas.
- [ ] **Seeder data demo** (±2 bulan transaksi Bu Sari — lengkap dengan produk, resep & pembelian bahan) — dibuat awal karena semua fitur lain butuh data untuk diuji.
- [ ] LLM adapter: `kirim_ke_llm(riwayat, tools, model)` + implementasi 2–3 provider kandidat.
- [ ] **Benchmark provider** pakai suite ekstraksi (Tahap 5) → pilih berdasarkan akurasi + biaya, bukan asumsi.
- [ ] Agent orchestrator: loop function-calling, registry tools, format pesan internal seragam (channel-agnostic).
- [ ] Riwayat percakapan + **strategi windowing** — putuskan sebelum wawancara multi-turn dibangun.
- [ ] Auth sederhana (no. HP + PIN).

## Tahap 2 — Pilar 1 + 4 *(prioritas: "aha moment")*

Target akhir tahap: **pengguna tahu untung bersih per produk yang jujur.**

### 2a. Pencatatan (P1)
- [ ] Tool `catat_transaksi` — validasi → simpan, simpan `raw_text`.
- [ ] **Ekstraksi produk & takaran** ("5 kotak", "2 liter", "setengah kilo") → isi `product_id`/`cost_item_id` + `qty` + `satuan`. **Tanpa ini pilar 4 tidak jalan.**
- [ ] **Deteksi jenis usaha berbasis struktur biaya** → isi `products.jenis` (`reseller|produksi`). Aturannya: apakah usaha *mengubah bahan jadi produk lain* — bukan seberapa besar usahanya (tukang ayam crispy kecil = **produksi**). Pengguna bisa mengoreksi lewat chat.
- [ ] Multi-transaksi dalam satu pesan ("laku 5 risol 75rb, terus beli minyak 38rb").
- [ ] `lihat_transaksi_terakhir` + `koreksi_transaksi` / `hapus_transaksi` — mitigasi utama salah ekstrak, bukan fitur opsional.
- [ ] Konfirmasi pencatatan **via template kode**, bukan panggilan LLM kedua ([02-arsitektur.md §6a](02-arsitektur.md)).
- [ ] Tool `tanya_keuangan` (omzet, laba, top item per periode).

### 2b. HPP (P4)
- [ ] Service HPP: formula reseller & produksi ([02-arsitektur.md §3a](02-arsitektur.md)) — deterministik, unit-tested.
- [ ] `atur_resep` — wawancara resep secara ngobrol (yield + bahan + takaran); tandai bahan yang harganya belum diketahui lalu tanyakan. **Hanya diekspos ke usaha ber-`jenis=produksi`** — reseller tidak pernah ditanya resep ([02-arsitektur.md §3a](02-arsitektur.md)).
- [ ] Harga bahan otomatis dari transaksi pembelian → `cost_item_prices` (append-only, bertanggal). Ini sekaligus **fondasi retensi** (margin-watch di H4) — bukan cuma jejak audit.
- [ ] `hitung_hpp` + `tanya_hpp` — kembalikan HPP/unit, laba kotor/unit, **dan asal tiap angka** (`hpp_snapshots.rincian`).
- [ ] **Semua jalur degradasi** ([02-arsitektur.md §3a](02-arsitektur.md)): resep kosong, bahan tanpa harga, penjualan tak terkenali → *"belum diketahui"*, **jangan dikarang**.
- [ ] **Cakupan HPP** dihitung & ditampilkan ("tercakup 78% omzet") — dipakai laporan & skor.

## Tahap 3 — Pilar 2 (Impor)

> **Dua tujuan, bukan satu:** (a) memotong cold-start, (b) **membuat laporan
> dapat dipercaya** lewat sumber objektif yang sulit dikarang
> ([03-roadmap.md](03-roadmap.md) H2). Tujuan (b) mengubah *urutan* adaptor —
> tapi hanya kalau premisnya lolos Tahap 0.

- [ ] Interface parser seragam: `parse(berkas) → list[BarisDraft]`.
- [ ] Alur draft: unggah → parse → `import_rows` (draft) → `tinjau_impor` → `konfirmasi_impor` → commit.
- [ ] **Aturan keras: tidak pernah auto-commit.** Uji negatif wajib (Tahap 5).
- [ ] Adaptor #1 — **foto buku tulis / screenshot** (vision). Paling relevan untuk segmen mikro; dahulukan.
- [ ] Adaptor #2 — CSV/spreadsheet dengan pemetaan kolom bebas via LLM.
- [ ] Adaptor #3 — export platform (majoo / BukuWarung / **WargaFinance**) — satu adaptor per format, **bukan** patokan arsitektur.
- [ ] 🎲 **Adaptor QRIS / e-wallet — kandidat prioritas, KONDISIONAL.** Kalau AO bank di Tahap 0 mengonfirmasi bahwa riwayat QRIS mengubah kepercayaan mereka, adaptor ini **naik ke atas** (mungkin mendahului #2 dan #3) karena ia satu-satunya sumber yang membuat laporan *terverifikasi*, bukan self-report. Kalau premisnya gugur, ia turun jadi adaptor biasa. **Jangan jadwalkan sebelum Tahap 0 menjawab.**
- [ ] Penanda keyakinan per baris → yang ragu ditinjau duluan.

## Tahap 4 — Pilar 3 (Dokumen & Panduan)

### 4a. Laporan standar bank
- [ ] Service laba-rugi (**Omzet − HPP = Laba Kotor − Operasional = Laba Bersih**) & arus kas — deterministik, unit-tested.
- [ ] Template HTML → PDF via WeasyPrint; format divalidasi ke masukan AO (Tahap 0).
- [ ] Tool `buat_laporan` + penyimpanan file + URL unduh. **Cakupan HPP tercantum di laporan.**

### 4b. Skor Kesehatan Usaha
- [ ] Implementasi komponen skor ([02-arsitektur.md §4](02-arsitektur.md)).
- [ ] **Edge case sekarang, bukan nanti**: laba negatif, periode pertama tanpa pembanding, data < 30 hari, **cakupan HPP rendah** → komponen "belum dapat dihitung" + normalisasi bobot.
- [ ] Skor parsial sejak hari pertama + label kejelasan data.
- [ ] Snapshot berkala + tampilan progres ("naik X poin").
- [ ] `hitung_skor_kesehatan` + narasi LLM — **hanya boleh menyebut angka dari output tool**.
- [ ] **Dua keluaran terpisah di level API** ([02-arsitektur.md §4](02-arsitektur.md)): `skor_pengguna` (komposit + progres, untuk motivasi) vs `fakta_penyalur` (omzet, bulan konsisten, cakupan HPP %, rasio prive — **fakta mentah, tanpa skor**). ⛔ **Skor komposit tidak boleh masuk laporan/proposal yang dibaca penyalur** sebelum terkalibrasi data nyata.
- [ ] **Catat hasil pengajuan** → `kur_outcomes` (lolos/ditolak/plafon cair). Yang dibangun sekarang **hanya pencatatannya**; kalibrasinya menunggu data cukup (H4). Tanpa mulai mencatat sekarang, flywheel tidak pernah punya bahan bakar.

### 4c. Asisten KUR & panduan formal
- [ ] Alur wawancara multi-turn (state di `kur_interviews`).
- [ ] `susun_dokumen_kur`: wawancara + laporan → proposal PDF + checklist (dari `panduan_entries`, bertanggal).
- [ ] `panduan_perizinan` — baca dari `panduan_entries`; **memandu & menjelaskan saja**, tidak filing (brief §4 non-goals).
- [ ] Disclaimer eksplisit di tiap dokumen: alat bantu persiapan, bukan jaminan persetujuan.

### 4d. UI Chat
- [ ] UI chat mobile-first (satu jendela, hemat bandwidth).
- [ ] Render di dalam chat: konfirmasi pencatatan, kartu HPP/margin, kartu skor, peninjau impor, link unduh PDF.

## Tahap 5 — Kualitas & Verifikasi *(dicicil per fitur, bukan ditumpuk)*

- [ ] Unit test service layer: laporan, skor, **HPP + semua degradasi**, dengan fixture.
- [ ] Suite uji ekstraksi: kalimat informal + **produk/takaran** → target akurasi ditetapkan. Dipakai ganda sebagai benchmark provider.
- [ ] **Uji deteksi jenis usaha** — kasus batas yang sengaja menjebak proksi ukuran: *"jualan ayam crispy"* (produksi) vs *"jualan ayam potong"* (reseller); usaha kecil yang memproduksi; usaha terdengar-besar yang cuma menjual ulang. **Uji negatif: reseller tidak boleh pernah dipicu wawancara resep.**
- [ ] Uji parser impor per adaptor pakai berkas nyata (Tahap 0). **Uji negatif: berkas berantakan tidak boleh lolos ke `transactions` tanpa persetujuan.**
- [ ] E2E skenario Bu Sari: catat → resep → HPP → untung bersih → skor → PDF → wawancara KUR → dokumen keluar, tanpa sentuhan manual.
- [ ] Review manual PDF: format, kebenaran angka, cakupan HPP, identitas usaha.
- [ ] Isolasi data per-tenant di semua tool (sekaligus mitigasi prompt injection).
- [ ] Uji di HP murah / koneksi lambat.

---

## Urutan & paralelisme

```
Tahap 1 (fondasi) ─► Tahap 2 (P1+P4) ─► Tahap 3 (P2) ─► Tahap 4 (P3) ─► rilis terbatas
Tahap 0 (validasi) ─── paralel ──────────┘
   ├─► masukan AO      → format laporan (4a)
   ├─► syarat KUR/izin → panduan_entries (4c)
   └─► berkas nyata    → fixture impor (Tahap 3 & 5)
Tahap 5 (test) ─── dicicil bersama tiap tahap ───
```

- **Tahap 2 adalah jantungnya.** Kalau harus berhenti di satu titik, berhentilah setelah Tahap 2 — di situ produk sudah punya nilai nyata: *"akhirnya saya tahu untung bersih saya."*
- Tahap 3 & 4 bisa ditukar urutannya bila validasi menunjukkan dokumen lebih mendesak daripada onboarding.
- **Tidak ada tahap yang menunggu keputusan strategis lagi** — gate extend-vs-baru sudah tertutup.

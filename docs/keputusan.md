# Keputusan — JembatanModal

> Log keputusan strategis (append-only). Entri terbaru di atas.
> Format: **tanggal — judul** · Konteks · Keputusan · Alasan · Konsekuensi.

---

## 2026-07-22 — `docs/` repo kode jadi rumah resmi dokumen perencanaan

- **Konteks:** CLAUDE.md menyatakan "perencanaan hidup di repo terpisah" dengan
  pointer placeholder `⟨tautan/path⟩`, padahal salinan **hidup** (brief,
  arsitektur, rencana kerja, dan `keputusan.md` dengan entri terbaru) sudah lama
  menumpuk di `docs/` repo kode. Salinan di repo `jembatan-modal` terpisah
  berhenti 2026-07-17 dan basi. Kontradiksi ini berulang bikin bingung "menulis
  keputusan ke mana".

- **Keputusan:** `docs/` di repo kode adalah **satu-satunya salinan hidup** dan
  rumah resmi dokumen perencanaan. CLAUDE.md diperbarui: pointer placeholder
  diganti path `docs/…` nyata, framing "repo terpisah" dibuang, dan aturan
  "keputusan strategis dicatat ke `keputusan.md`" menunjuk eksplisit ke
  `docs/keputusan.md`. Salinan lama di repo terpisah ditandai usang (jangan
  ditulis).

- **Alasan:** satu sumber kebenaran yang cocok dengan kenyataan kerja; menutup
  celah drift/basi yang sudah dua kali menggigit. Memindahkan dokumen ke repo
  terpisah (opsi lain) menghormati niat dua-repo awal tapi menuntut sinkronisasi
  lintas-repo manual yang justru sumber masalahnya.

- **Konsekuensi:** kontributor menulis keputusan & merevisi perencanaan langsung
  di `docs/`. Repo `jembatan-modal` terpisah tidak lagi otoritatif untuk
  perencanaan; kalau mau, isinya bisa dibersihkan/di-arsip terpisah (di luar
  lingkup perubahan ini).



- **Konteks:** entri **"Situs portofolio statis hidup di `/site`"** (di bawah,
  tanggal sama) memarkir landing + demo sebagai bundle export Claude Design yang
  tidak di-unbundle, dengan konsekuensi source of truth tetap di Claude Design
  dan koreksi copy wajib disinkronkan balik ke sana. Bundle itu ±1 MB, buram
  (markup sebagai string JSON, React + font ter-embed), tak bisa di-review/di-diff
  dengan wajar, dan setiap perbaikan kecil menuntut re-export manual.

- **Keputusan:** landing + demo **diimplementasikan ulang sebagai aplikasi
  Next.js** (App Router, TypeScript, `output: 'export'` → HTML statis), rute `/`
  (landing) dan `/demo`. Bundle export dijadikan **referensi desain** lalu
  **dihapus dari tree**. Ini **men-supersede** entri "tidak-unbundle" tsb —
  khususnya butir 1 (*source of truth di Claude Design*) dan butir 3 (*tidak
  di-unbundle*):
  1. **Source of truth desain kini = kode di `/site` repo ini**, bukan Claude
     Design. Design token dipusatkan sebagai CSS variable
     ([site/app/globals.css](../site/app/globals.css)); font lewat
     `next/font/google` (Plus Jakarta Sans + IBM Plex Mono, di-self-host saat
     build); styling CSS Modules; dependency minimal (hanya Next/React).
  2. Copy yang dipakai = **versi ter-koreksi** dari bundle (18 berkas uji; kartu
     untung per produk sudah tersambung ke chat; hanya wawancara resep yang
     belum) — bukan export asli Claude Design.
  3. Animasi timeline hero & seluruh perilaku demo ter-skrip di-port setia
     (tombol saran → kartu hardcoded, chip kategori bisa dikoreksi lewat state
     lokal, kalimat bebas dijawab jujur "belum diproses"); **nol panggilan API**,
     menghormati `prefers-reduced-motion`, dan tetap utuh tanpa JavaScript.

- **Alasan:** kode Next.js bisa di-review, di-diff, di-lint, dan di-type-check —
  hilang sudah gumpalan ~1 MB yang buram. Static export menjaga deploy tetap
  tanpa server. Kesetaraan visual dengan bundle diverifikasi lewat screenshot
  berdampingan (landing + demo) sebelum bundle dihapus. Logika keamanan
  iframe/postMessage yang jadi alasan "tidak di-unbundle" tidak lagi relevan:
  runtime bundler itu ikut hilang bersama bundle-nya.

- **Konsekuensi:** source-of-truth copy & markup **pindah ke repo ini**, sehingga
  **sinkronisasi balik ke Claude Design (temuan/konsekuensi sesi sebelumnya) tidak
  lagi diperlukan** — koreksi cukup diedit di kode. `site/index.html` &
  `site/demo.html` dihapus; `site/README.md` ditulis ulang (cara dev/build/export
  + catatan sejarah); `site/.gitignore` menutup `node_modules`/`.next`/`out`.
  Toolchain JS di `site/` sengaja terpisah dari tooling Python di root (tidak
  menyentuh pipenv/pytest/ruff/alembic). Meta verifikasi Dicoding
  (`dicoding:email`) disematkan lewat `metadata.other` di tiap halaman → muncul di
  HTML `out/` statis. Tautan putus `[../keputusan.md]` pada perubahan uncommitted
  di [02-arsitektur.md](02-arsitektur.md) §1 dibetulkan jadi `[keputusan.md]`;
  kembarannya di baris committed (§ "Standalone") sengaja **tidak** disentuh dan
  dilaporkan terpisah.



- **Konteks:** dua artefak Claude Design selesai — landing page portofolio dan
  demo chat ter-skrip. Keduanya bundle self-contained (runtime unpacker, React
  ter-embed, font ter-base64; ±500 KB/berkas, tanpa panggilan jaringan) dan
  butuh tempat di repo kode tanpa tercampur backend (`app/`) atau UI produk
  (`web/`).

- **Keputusan:** keduanya hidup di **`/site`** (`index.html` = landing,
  `demo.html` = demo) sebagai **artefak statis portofolio**.
  1. **Source of truth desain tetap di Claude Design** — berkas di repo adalah
     artefak build; edit kecil boleh langsung di template bundle, perubahan
     besar lewat Claude Design + re-export ([site/README.md](../site/README.md)
     mendaftar penyimpangan lokal yang wajib diterapkan ulang).
  2. **Demo ter-skrip ≠ UI chat produk** — bukan cikal bakal Tahap 4d
     ([04-rencana-kerja.md](04-rencana-kerja.md)); UI produk tetap digarap di
     `web/`.
  3. Bundle **tidak di-unbundle** (font/React tidak dipisah) — runtime bundler
     memuat logika keamanan iframe/postMessage yang tidak boleh dirusak; ±1 MB
     sekali commit dinilai wajar.
  4. Copy landing dikoreksi saat integrasi agar jujur terhadap kode per tanggal
     ini: 18 (bukan 17) berkas pengujian, dan kartu untung per produk **sudah**
     tersambung ke chat (`tanya_untung` → `kartu_untung()` →
     `hitung_hpp_semua()`) — yang belum tersambung adalah wawancara resep.

- **Alasan:** folder terpisah membuat batas tegas dengan aplikasi (tidak
  di-serve FastAPI, tidak ikut artefak deploy backend) dan `index.html` +
  `demo.html` flat paling ramah static hosting maupun dibuka langsung dari
  berkas. Koreksi copy mengikuti aturan produk sendiri: klaim yang tidak sesuai
  kode tidak boleh dipajang.

- **Konsekuensi:** `/site` di-deploy terpisah (unggah folder apa adanya);
  perbaikan copy perlu disinkronkan balik ke Claude Design agar export
  berikutnya tidak menghidupkan lagi klaim usang; label status di landing
  menjadi ikut kedaluwarsa tiap kali fitur baru menyeberang dari "rencana" ke
  "teruji" — perlu dicek setiap re-export.

## 2026-07-22 — Router intent bahasa-bebas: pakai ulang `ekstrak()`, bukan verba tool-calling baru

- **Konteks:** `tanya_untung`/`tanya_keuangan` hanya bisa dipicu chip terstruktur;
  kalimat bebas ("untung saya bulan ini berapa?") jatuh ke jalur `catat_transaksi`.
  `orkestrator.py` sudah menandai ini sebagai utang desain, dan `02-arsitektur.md`
  §1 membayangkan penyelesaiannya lewat "function calling" generik — bertentangan
  dengan filosofi `kontrak.py` yang sengaja membatasi adapter ke dua verba
  (`ekstrak`/`narasikan`) demi provider-agnostic.

- **Keputusan:** router intent **tidak** menambah verba baru ke `AdapterLLM`. Ia
  memakai ulang `ekstrak()` dengan skema baru — `PilihanAksi{aksi: AksiRouter}`,
  `AksiRouter` enum tertutup (`catat_transaksi`/`tanya_untung`/`tanya_keuangan`) —
  persis pola `Koreksi`/`instruksi_koreksi` yang sudah ada. `tanya_hpp` dipetakan
  ke rute `tanya_untung` untuk sekarang; belum ada kartu HPP yang kontraknya
  benar-benar beda.

- **Alasan:** klasifikasi ke enum tertutup secara struktural adalah ekstraksi
  (bahasa → data terstruktur), bukan LLM memutuskan langkah — orchestrator tetap
  yang membaca hasilnya dan memilih fungsi. Nol perubahan ke `AdapterLLM`/suite
  konformansinya berarti nol biaya tambahan saat provider ditukar. Regex/keyword
  ditolak karena variasi bahasa informal terlalu luas dan gagalnya senyap;
  menunda ke chip-only selamanya ditolak karena kebutuhannya sudah eksplisit di
  rencana kerja Tahap 2a.

- **Konsekuensi:** `app/llm/skema.py` bertambah `AksiRouter`/`PilihanAksi`/
  `instruksi_router`; `app/tools/pilih_aksi.py` baru; `tangani_pesan` di
  `orkestrator.py` dapat langkah routing sebelum fallback `catat_transaksi`
  (fallback = perilaku hari ini, tak berubah). `main.py`'s dispatch chip
  (`aksi == "tanya_untung"` dst.) tidak disentuh. Ekstraksi periode dari kalimat
  bebas ("bulan lalu") **tidak** termasuk — periode default = bulan berjalan,
  sama seperti jalur chip. ⚠ `docs/02-arsitektur.md` §1 perlu direvisi terpisah —
  diagram/teksnya masih menjanjikan agent loop function-calling generik yang
  `kontrak.py` sengaja tidak akan bangun; entri ini tidak mencabut kontradiksi
  itu, hanya menandainya.

---

## 2026-07-20 — Buku transaksi append-only: koreksi tidak pernah menimpa

- **Konteks:** tool `koreksi_transaksi` dibangun karena tanpa itu setiap salah
  catat jadi permanen. Pilihan implementasinya ada dua: `UPDATE` di tempat
  (murah, tanpa migrasi) atau membatalkan baris lama lalu mencatat penggantinya.

- **Keputusan:** **append-only.** `transactions` dapat dua kolom:
  `dibatalkan_pada` (timestamp) dan `koreksi_dari_id` (menunjuk baris yang
  digantikan). Koreksi = tandai yang lama + `INSERT` yang baru. Tidak ada
  `UPDATE` nominal/jenis/tanggal, dan tidak ada `DELETE`.

- **Alasan:** produk ini menyiapkan pengguna menghadapi penyalur modal. Buku yang
  diam-diam menulis ulang dirinya sendiri tidak bisa menjelaskan **mengapa**
  angka bulan lalu berbeda dari yang pernah dilihat pengguna — dan "kok laporan
  saya berubah?" adalah pertanyaan yang harus punya jawaban, bukan dugaan.
  Biayanya satu kolom; harga menghilangkan jejaknya jauh lebih mahal.
  Efek samping yang bagus: rantai koreksi beruntun (#1→#2→#3) terbaca utuh.

- **Konsekuensi (mengikat, mudah dilanggar diam-diam):** setiap query yang
  menjumlah uang **wajib** menyaring `dibatalkan_pada IS NULL`. Saat ini ada
  tiga pembaca — `laba.hitung_laba_periode`, `hpp._hpp_reseller` (harga beli
  terakhir), `hpp.cakupan_hpp` (omzet) — dan ketiganya sudah disaring + diuji.
  ⛔ Pembaca baru yang lupa menyaring tidak akan memunculkan error apa pun:
  angka yang sudah dibetulkan pengguna hidup lagi tanpa suara. Tes
  `test_pembelian_yang_dibatalkan_tidak_dipakai_sebagai_harga_hpp` ada khusus
  untuk menjaga pembaca yang paling mudah terlupakan.

---

## 2026-07-19 — Repacking bukan transformasi: susut & konversi punya jalur reseller

- **Konteks:** implementasi faktor kehilangan memunculkan pertanyaan yang
  menyentuh aturan #8. Kasus toko kelontong (beras 1 sak → dijual literan, susut
  2,5%) sementara dimodelkan sebagai produk `produksi` dengan resep, karena hanya
  jalur resep yang punya *yield* dan faktor kehilangan. Tapi itu berarti tukang
  beras akan terdeteksi sebagai produsen — persis kegagalan yang aturan #8 ingin
  cegah.

- **Keputusan:**
  1. **Mayoritas tukang beras = `reseller`.** Mereka menjual ulang beras yang
     secara produk identik dengan yang dibeli (beras = beras).
  2. **Perubahan kemasan, merek, atau satuan bukan transformasi.** Sak → literan/
     kiloan, maupun repack ke merek toko sendiri, **tidak** memindahkan produk ke
     jalur resep.
  3. **Susut & konversi satuan ditangani di jalur reseller tersendiri**, bukan
     lewat `atur_resep`.
  4. **Transformasi sejati tetap masuk jalur produksi** — mis. penggilingan padi
     (gabah → beras). Ini minoritas, dan satu-satunya varian tukang beras yang
     boleh ditanyai resep.

- **Alasan:** aturan #8 menguji *apakah usaha mengubah bahan jadi produk lain*,
  bukan apakah bentuk fisiknya berubah. Beras yang dipindah dari sak ke liter
  tetap beras; gabah yang digiling jadi beras bukan lagi gabah. Menjadikan
  repacking sebagai "produksi" akan membuat produk ini menawarkan wawancara resep
  ke toko kelontong — dan pengguna langsung merasa produk ini tidak mengerti
  usahanya (aturan #8 menyebutnya eksplisit sebagai sinyal deteksi yang salah).

- **Konsekuensi:**
  - `products` mendapat kolom jalur reseller: `satuan_beli`, `satuan_jual`,
    `isi_per_satuan_beli`, `faktor_kehilangan`. HPP reseller jadi
    `harga_beli_per_satuan_beli ÷ (isi_per_satuan_beli × (1 − faktor_kehilangan))`.
  - `faktor_kehilangan` kini hidup di **dua** tempat dengan cakupan berbeda:
    `recipes` (kehilangan saat produksi) dan `products` (susut saat pengeceran).
    Bukan duplikasi — dua peristiwa berbeda.
  - Satuan pembelian dibandingkan dengan `products.satuan_beli`; beda → status
    `satuan_tidak_cocok`, konsisten dengan keputusan "bandingkan, jangan konversi"
    di bawah. Tanpa ini, pengguna yang kadang beli per sak dan kadang per kg akan
    mendapat konversi yang salah diam-diam.
  - `atur_resep` **tetap tidak boleh** diekspos ke `jenis=reseller`. Yang perlu
    ditanyakan ke reseller adalah *isi per kemasan* dan *susut*, bukan resep.

## 2026-07-19 — Satuan: bandingkan, jangan konversi

- **Konteks:** ditemukan saat review mandiri. Harga tersimpan per `kg` sementara
  resep menakar `gram` menghasilkan HPP **1000× meleset** dan tetap berstatus
  `lengkap`, tanpa satu pun catatan — `recipe_items.satuan` dan
  `cost_item_prices.satuan` disimpan berdampingan lalu tidak pernah dibandingkan.
  Cacat ini ada sejak service HPP pertama, bukan bawaan sub-produk.

- **Keputusan:** satuan pemakaian dibandingkan dengan satuan harga (dan, untuk
  sub-produk, dengan `recipes.yield_satuan`). Bila berbeda → status baru
  `satuan_tidak_cocok`, **HPP tidak dihitung**, pasangan yang bertabrakan
  disebutkan. Normalisasi dibatasi pada spasi & besar-kecil huruf saja.

  ⛔ **Tidak ada konversi otomatis dan tidak ada tabel sinonim.** "kilogram" tidak
  dianggap sama dengan "kg"; "gram" tidak diubah jadi 1/1000 kg.

- **Alasan:** menebak maksud pengguna dari string satuan adalah mengarang angka
  lewat pintu belakang (aturan #2). Tabel konversi diam-diam adalah bug
  berikutnya yang menunggu — ia benar 95% kali dan salah besar 5% sisanya, tanpa
  ada yang tahu kapan. Menolak menghitung sambil menunjuk persis apa yang
  bertabrakan jauh lebih murah daripada angka percaya diri yang salah.
  Bila konversi dibutuhkan nanti, ia harus **eksplisit, bersumber, dan diuji
  tersendiri** — bukan diselipkan ke dalam normalisasi.

- **Konsekuensi:**
  - `HasilHpp` bertambah `satuan_hpp` (satuan yang berlaku bagi `hpp_per_unit`)
    dan `satuan_bertabrakan`; keduanya masuk `rincian_json()`.
  - Bentrok di dalam sub-produk menjalar ke induk dengan **penyebab akarnya**,
    bukan sekadar nama sub-produknya.
  - Saat pilar 1 digarap, `catat_transaksi` & `atur_resep` harus mendorong
    satuan yang konsisten sejak input — memeriksa di hilir itu jaring pengaman,
    bukan solusi.
  - `RekonsiliasiBiaya.pos_terbesar_di_luar_hpp` diganti nama jadi
    `pos_biaya_terbesar`: isinya seluruh pos biaya, bukan hanya yang di luar HPP.
    Menyaringnya mustahil (satu transaksi belanja tidak bisa dipetakan ke
    penyerapan HPP), jadi yang diperbaiki adalah **namanya**.

## 2026-07-18 — Dua angka: laba periode ≠ HPP per unit

- **Konteks:** analisis 9 kasus UMKM nyata ([05-analisis-9-kasus-hpp.md](05-analisis-9-kasus-hpp.md))
  membuka lubang yang tidak terlihat dari desain: `cakupan_hpp()` mengukur
  **cakupan omzet**, bukan **cakupan biaya**. Warteg yang semua penjualannya
  tertaut produk melihat cakupan **100%** padahal HPP-nya hanya memuat 60% biaya
  nyata — status `lengkap`, laba kelebihan ±36%. Model `material`-only menyerap
  hanya 11% biaya laundry, 35% hidroponik, 60% warteg. Melanggar semangat aturan
  #2 lewat pintu belakang: yang "lengkap" cuma sisi bahannya.

- **Keputusan:** produk melaporkan **dua angka yang berbeda peran**, tidak
  pernah dilebur:
  1. **Laba periode** = Σ pemasukan − Σ (pengeluaran + operasional). Angka utama,
     selalu tampil. **Cakupan biaya 100% menurut definisi** — tanpa resep, tanpa
     alokasi, tanpa perlu tahu jenis usahanya. `prive` dikeluarkan dari biaya dan
     dilaporkan terpisah (aturan #9).
  2. **HPP & laba kotor per unit** — alat keputusan harga/porsi per produk.
     Parsial secara sifat, **wajib berlabel cakupannya**, tidak pernah
     dipresentasikan sebagai "untung usaha".
  3. **Rekonsiliasi biaya** menjembatani keduanya: `pengeluaran − terserap HPP =
     biaya yang tidak tertelusur ke produk`, beserta pos-pos terbesarnya.

  Turunannya, urutan garap pilar 4 lanjutan: (a) laba periode + rekonsiliasi,
  (b) **sub-produk** (`recipe_items` boleh menunjuk produk), (c) **faktor
  kehilangan** (satu angka untuk susut/reject/waste/gagal panen), (d) **harga
  jual majemuk** (kanal/grade/tier). **Cara-menempel biaya** (`per_batch`,
  `per_periode`, `persen_harga_jual`) **ditunda**.

- **Alasan:** pertanyaan "apakah saya untung" tidak butuh HPP sama sekali —
  seluruh kecemasan cakupan lahir karena angka kedua dipaksa mengerjakan tugas
  angka pertama. Laba periode menutup lubang itu **lebih baik** daripada
  menambah cara-menempel (100% vs 71% untuk warteg), tanpa migrasi, dan berlaku
  untuk kasus kesepuluh yang belum pernah kita lihat.

  Bukti terkuat: **kesembilan dokumen kasus itu sudah memisahkan dua lapis ini
  sendiri**, ditulis independen tanpa saling tahu — warteg (*HPP dapur* vs
  *biaya operasional per porsi*), bakso (*bahan+overhead* vs *TK* vs *laba bersih
  owner*), hidroponik (dua HPP: dengan & tanpa upah), laundry (variabel vs
  tetap). Struktur dua lapis adalah bentuk asli cara pemilik usaha kecil
  berpikir; model kita mencerminkannya, bukan meratakannya.

  `per_periode` ditunda karena ia **jalan masuk overhead**. Membangunnya selagi
  jasa masih non-goal berarti menaruh godaan memasukkan sewa & gaji di tengah
  kode, demi presisi pada angka yang justru bukan angka utama. Bangun nanti,
  bersama validasi jasa dan alasannya.

- **Konsekuensi:**
  - Service baru `app/services/laba.py` (deterministik, tanpa LLM, tanpa migrasi).
  - `cakupan_hpp()` **tidak lagi berdiri sendiri** sebagai indikator kepercayaan —
    ia selalu didampingi rekonsiliasi biaya di laporan & skor.
  - Laporan/narasi tidak boleh menyebut HPP per unit sebagai "untung". Batas ini
    perlu ditegakkan saat pilar 1 & 3 digarap.
  - Tiga kasus (laundry, hidroponik, sebagian fashion online) akan menunjukkan
    cakupan HPP rendah **secara benar** — itu sinyal batas produk, bukan bug.
  - Aturan #7 **tidak diubah**: `labor_time`/`overhead` tetap slot tanpa kalkulasi.

- **Utang validasi:** narasi dua angka berisiko terasa mengelak — pemilik bakso
  bertanya *"untung berapa per mangkok"* dan dijawab laba periode. Angkanya
  benar; taruhannya di **bahasa**, dan baru teruji saat pilar 1 hidup.

## 2026-07-17 — Penajaman target & primitif biaya

> Satu entri, tujuh sub-keputusan yang saling mengunci. Semuanya **low-regret**:
> mengubah cara berpikir & bentuk skema, **tidak** mengunci keputusan pasar.
> Keputusan pasar yang muncul dalam diskusi yang sama (model harga, siapa yang
> membayar) **sengaja tidak dikunci** — lihat "Yang TIDAK diputuskan" di bawah.

- **Konteks:** analisis mekanika produk (bukan data lapangan) menunjukkan bahwa
  framing segmen lama — tangga ukuran ultra-mikro → Bu Sari → cafe — tidak
  menjelaskan ke mana nilai produk sebenarnya mengalir. Penelusuran ulang
  memunculkan tujuh hal yang bisa dikunci sekarang tanpa menyandera apa pun.

- **Keputusan:**

  1. **Target disaring dua sumbu, bukan ukuran usaha.** Sumbu A: apakah usaha
     *mengubah bahan jadi produk lain* (biaya pokok tersembunyi). Sumbu B:
     apakah ada rencana modal konkret ~3–6 bulan. **Target inti = produsen barang
     skala rumahan yang memenuhi A dan B.** Ukuran usaha hanyalah proksi kasar
     yang berkorelasi — dan menyesatkan bila dipakai sendirian: *tukang ayam
     crispy baru mulai* = **produsen**, walau kecil. Tangga ukuran turun pangkat
     jadi **peta jangkauan sekunder**, bukan target.

  2. **Satu primitif biaya: `{material | labor_time | overhead}`.** Reseller,
     produsen, jasa, bengkel, cafe semuanya **kasus khusus dari satu model** HPP
     = kumpulan komponen biaya bertipe. **Skema dirancang menampung ketiganya;
     hanya `material` diimplementasi sekarang.** `ingredients` → `cost_items`
     (+kolom `tipe`), `recipe_items.ingredient_id` → `cost_item_id`,
     `transactions.ingredient_id` → `cost_item_id`.

  3. **Sektor jasa: penundaan sadar, skema-ready.** Sebelumnya jasa tersingkir
     *diam-diam lewat bentuk skema*. Sekarang eksplisit: **non-goal implementasi**,
     **tapi skema tidak menutup pintunya** (lihat #2).

  4. **Positioning: luas di dalam, sempit di depan.** Arsitektur boleh luas (satu
     spine, banyak jenis usaha); yang **dijual** tetap sempit — produsen rumahan
     yang mau naik kelas. Kedalaman menyesuaikan lewat **deteksi**, bukan menu:
     reseller tidak pernah ditanya resep.

  5. **Pilar 2 punya dua tujuan** (framing saja): (a) memotong cold-start —
     framing lama; (b) **membuat laporan dapat dipercaya**, karena laporan yang
     seluruh angkanya diketik sendiri = bukti lemah bagi penyalur. Prinsip yang
     dikunci: **data terverifikasi > self-report.**

  6. **Skor dipecah dua keluaran + flywheel kalibrasi.** Ke pengguna: skor
     komposit, progres, streak — motivasi, boleh kasar. Ke penyalur: **hanya
     fakta mentah terverifikasi**, tanpa skor komposit. **Skor komposit tidak
     pernah dihadapkan ke penyalur sebelum terkalibrasi data pengajuan nyata.**
     Hasil tiap pengajuan dicatat (`kur_outcomes`) → itulah yang mengkalibrasi.

  7. **Retensi-via-HPP naik jadi rasional kelas satu.** Payoff KUR sekali → ada
     tebing churn tepat di momen pengguna paling puas. Mesin retensi utamanya:
     harga bahan bergejolak → margin berubah terus → "tahu untung" jadi kebutuhan
     **berulang**. Turunannya *margin-watch*. Ini **status rasional**, bukan
     jadwal — implementasinya tetap H4 dan tidak boleh mendahului HPP di H1.

- **Alasan:** ketujuhnya low-regret. #1/#3/#4 mengubah *cara berpikir* dan bisa
  direvisi kalau lapangan membantah. #2/#6 adalah **asuransi skema**: menambah
  tipe komponen ke enum yang sudah ada = satu baris; menambahkannya ke skema
  bahan-saja setelah ada data produksi = membongkar `recipes`, `recipe_items`,
  `hpp_snapshots`, dan semua kalkulasi di atasnya. Biaya sekarang ≈ nol, biaya
  nanti tidak. #5/#7 tidak menjadwalkan apa pun — cuma menamai peran yang selama
  ini tidak tertulis. Yang benar-benar mahal bila salah (harga, siapa bayar)
  justru **tidak** dikunci.

- **Konsekuensi:**
  - [docs/00-project-brief.md](docs/00-project-brief.md) §1 (positioning sempit),
    §4 (non-goal jasa skema-ready), §5 (**ditulis ulang**: dua sumbu), §6 (dua
    prinsip baru: pagar etis penyalur, kedalaman adaptif), §7 (dua keputusan
    terbuka baru).
  - [docs/02-arsitektur.md](docs/02-arsitektur.md) berubah paling banyak: §3a
    (primitif biaya + deteksi jenis usaha), §4 (skor dua keluaran + flywheel),
    §5 (`cost_items`, `cost_item_prices`, `kur_outcomes`), §6 (tiga risiko baru).
  - [docs/01-konsep-produk.md](docs/01-konsep-produk.md) §2 (spine + kedalaman
    adaptif), Pilar 2 (verifikasi ⚠️), Pilar 4 (primitif biaya), §3b (skor pecah
    dua), §4 (deteksi + retensi), §5 (dua prinsip baru).
  - [docs/03-roadmap.md](docs/03-roadmap.md) H1 (janji retensi), H2 (verifikasi
    ⚠️ + mulai catat `kur_outcomes`), H4 (margin-watch, flywheel, pagar etis).
  - [docs/04-rencana-kerja.md](docs/04-rencana-kerja.md) Tahap 0 (5 item validasi
    baru), Tahap 1 (slot komponen biaya), Tahap 2 (deteksi jenis usaha), Tahap 3
    (adaptor QRIS kondisional), Tahap 4b (dua keluaran + `kur_outcomes`), Tahap 5
    (uji deteksi).
  - [CLAUDE-jembatan-modal.md](CLAUDE-jembatan-modal.md) + `CLAUDE.md` repo kode:
    tiga prinsip operasional baru agar sesi ngoding mematuhinya.
  - **Kontradiksi yang tercabut:** [docs/03-roadmap.md](docs/03-roadmap.md) H4
    sebelumnya menulis model keberlanjutan seolah sudah diputuskan ("gratis untuk
    pencatatan & skor, berbayar/komisi pada dokumen atau kemitraan penyalur").
    Itu **mengunci taruhan pasar tanpa entri keputusan** dan kini dicabut jadi
    "belum dikunci". Juga: catatan basi di brief §7/§8 bahwa roadmap "masih
    berbingkai IDCamp" — sudah tidak sesuai isi file, dicabut.

- **Yang TIDAK diputuskan (sengaja — jangan dibaca sebagai keputusan):**
  - **Model harga.** Hipotesis bentuk per segmen (gratis / success-fee /
    langganan analitik) hanya hipotesis. → [docs/00-project-brief.md](docs/00-project-brief.md) §7 + Tahap 0.
  - **Siapa yang membayar** (pengguna vs penyalur). *Default kerja*: pengguna
    bayar per-nilai, penyalur = kanal distribusi & verifikasi, bukan pembeli lead.
    **Default ≠ keputusan.** → §7 + Tahap 0.
  - Yang **dikunci** dari topik itu hanyalah **pagar etisnya** (prinsip, bukan
    pengaturan bisnis): dibayar untuk **lead jujur terkualifikasi**, bukan **lead
    yang lolos** — karena begitu komisi bergantung pada persetujuan, insentif
    bergeser ke volume pengajuan dan dorongan berikutnya adalah memoles laporan.
    Itu mengkhianati "angka tidak pernah dikarang".

- **Utang validasi yang lahir dari entri ini** (semua ⚠️ hipotesis, bukan fakta —
  [docs/04-rencana-kerja.md](docs/04-rencana-kerja.md) Tahap 0):
  1. Apakah QRIS + konsistensi pencatatan **benar-benar** mengubah kepercayaan
     penyalur? *(premis paling menentukan — menyangga #5 dan prioritas adaptor QRIS)*
  2. Apakah produsen mau membayar success-fee saat modal cair?
  3. Apakah cafe mau langganan analitik food-cost?
  4. Apakah aha moment jasa (*"waktumu punya harga"*) bernilai? *(menyangga #3)*
  5. Apakah "nilai menumpuk di tengah" benar — atau reseller tetap mau bayar
     untuk catatan rapi? *(menyangga #1)*

## 2026-07-17 — Standalone: repo terpisah & data milik sendiri

- **Konteks:** gate "extend vs repo baru" ([04-rencana-kerja.md](docs/04-rencana-kerja.md)
  Tahap A1 versi lama) memblokir penulisan kode. Terungkap juga **kontradiksi**
  antar-dokumen: brief menaruh pencatatan sebagai "spine universal" (menyiratkan
  data sendiri), sementara rencana-kerja berpremis "layer bankable di atas
  WargaFinance" dengan tugas *"skip pencatatan bila pakai data WargaFinance"*.
- **Keputusan:** JembatanModal **standalone**.
  1. Kode hidup di **folder/repo terpisah** (disusun sendiri oleh pemilik).
  2. Produk **memiliki skema & data transaksinya sendiri** — tidak ada dependensi
     baca ke database produk lain.
  3. **WargaFinance masuk hanya lewat jalur impor pilar 2**, sebagai salah satu
     sumber opsional — setara dengan majoo, BukuWarung, foto buku tulis, atau CSV.
- **Alasan:** konsisten dengan scope 4-pilar (pilar 1 = spine universal) dan
  dengan jangkauan tangga sampai ultra-mikro — produk harus berfungsi penuh untuk
  pengguna yang belum pernah memakai produk apa pun. Menumpang skema orang juga
  akan menyandera desain HPP (pilar 4), yang justru prioritas utama.
- **Konsekuensi:**
  - Gate extend-vs-baru **tertutup** — tidak ada lagi yang memblokir kode.
  - Pilar 1 digarap penuh (tidak di-skip); ekstraksi harus mengenali **produk &
    takaran**, bukan sekadar nominal — prasyarat HPP.
  - [02-arsitektur.md](docs/02-arsitektur.md) & [04-rencana-kerja.md](docs/04-rencana-kerja.md)
    diperbarui: premis WargaFinance dicabut, pilar 2 & 4 didesain.
  - Butuh CLAUDE.md tersendiri di repo kode — muatannya disiapkan di
    [CLAUDE-jembatan-modal.md](CLAUDE-jembatan-modal.md), disalin ke folder kode
    saat eksekusi. **Tidak** menggantikan [../CLAUDE.md](../CLAUDE.md).

## 2026-07-17 — Deprioritas lomba IDCamp: produk-first

- **Konteks:** dokumen perencanaan awal ([03-roadmap.md](docs/03-roadmap.md),
  [04-rencana-kerja.md](docs/04-rencana-kerja.md)) berbingkai submission IDCamp —
  scope Fase 1 = "MVP hackathon", banyak keputusan mundur dari deadline lomba.
- **Keputusan:** frame utama digeser ke **pengembangan produk jangka panjang**.
  IDCamp Developer Challenge 2026 diperlakukan sebagai **tonggak validasi**,
  bukan pembatas scope.
- **Alasan:** memaksimalkan nilai produk tanpa terkurung batasan lomba;
  scope 4-pilar (lihat entri di bawah) lebih besar dari sekadar demo hackathon.
- **Konsekuensi:** roadmap & rencana-kerja perlu diselaraskan ulang ke frame
  produk (tindak lanjut). [00-project-brief.md](docs/00-project-brief.md) menjadi
  pintu masuk scope yang baru.

## 2026-07-17 — Kunci scope: empat pilar sebagai satu kesatuan

- **Konteks:** diskusi mempersempit "menjalar ke keseluruhan UMKM" menjadi scope
  yang fokus namun tetap punya jalur ekspansi (tangga mikro → cafe).
- **Keputusan:** scope produk = **empat pilar yang saling mengunci**, dengan
  urutan garap **1+4 → 2 → 3**:
  1. Pencatatan harian (spine universal)
  2. Upload data laporan — AI baca catatan yang sudah ada (**bukan** dikunci ke
     satu format platform; majoo dsb. hanya salah satu input); visi: makin banyak
     bentuk laporan bisa diekstrak
  3. Persiapan dokumen modal formal (KUR + **memandu** perizinan/badan hukum —
     memandu & menjelaskan, tidak filing)
  4. Extract HPP → untung bersih/cashflow yang jujur (prioritas bersama pilar 1)
- **Alasan:** pilar 1+4 = "aha moment" (untung bersih jujur, sering mengejutkan)
  & universal lintas segmen; pilar 3 = payoff yang dijual; pilar 2 = akselerator
  onboarding + daya tarik. Fokus pada satu spine data yang bisa "menjalar" ke atas
  lewat HPP/food-cost, alih-alih melayani seluruh spektrum UMKM serentak (pola
  kegagalan yang tercatat di [../docs/analisis-scm-network.md](../docs/analisis-scm-network.md)).
- **Konsekuensi:** non-goals dikunci (tidak menggantikan POS, tidak filing izin,
  tidak memegang uang, tidak mengunci format upload) — lihat
  [00-project-brief.md](docs/00-project-brief.md) §4. Kedalaman HPP untuk produsen
  (BOM/resep) menjadi item desain yang belum selesai.
- **Masih terbuka:** keputusan **extend vs repo baru** belum diambil dan tetap
  memblokir penulisan kode fitur; premis "unbankable karena tak ada laporan"
  belum tervalidasi.

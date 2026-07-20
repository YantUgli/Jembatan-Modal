# Konsep Produk — JembatanModal

> Dokumen ini memperdalam **latar, persona, dan diferensiasi**. Untuk scope,
> non-goals, dan prioritas → [00-project-brief.md](00-project-brief.md).
> Struktur solusi di §2 mengikuti **4 pilar** yang dikunci di
> [../keputusan.md](../keputusan.md) (2026-07-17).

## 1. Latar Belakang

> ⚠️ **Angka di paragraf ini belum diverifikasi ke sumber primer.** Berasal dari
> materi brief publik; berstatus **belum-final** sampai `docs/sumber-data.md`
> ada (aturan emas repo — lihat [../../docs/konteks-umkm-indonesia.md](../../docs/konteks-umkm-indonesia.md)).
> Jangan dipakai di materi pitch sebelum diverifikasi.

Indonesia memiliki lebih dari **64 juta pelaku UMKM** ⚠️ yang menyumbang **60% PDB nasional** ⚠️ dan menjadi penyerap utama tenaga kerja. Namun transformasi digital belum menyentuh mayoritas dari mereka — hanya **12%** ⚠️ yang berhasil mengintegrasikan teknologi ke operasional bisnisnya. Bukan karena tidak mau, melainkan karena solusi yang ada terlalu rumit, terlalu mahal, atau tidak dirancang dengan memahami realita lapangan.

Realita lapangan itu kira-kira begini: pencatatan di buku tulis (kalau sempat), nota belanja yang hilang, uang usaha bercampur uang dapur, dan di akhir bulan tidak tahu persisnya untung berapa.

### Masalah yang lebih dalam: unbankable

Di balik masalah pencatatan ada konsekuensi struktural yang jarang digarap: **UMKM tidak bisa mengakses modal formal.** Saat pelaku usaha ingin mengajukan KUR atau kredit ke bank/koperasi, syarat pertamanya adalah bukti kesehatan usaha — laporan keuangan, riwayat omzet, pemisahan keuangan usaha dan pribadi. Mayoritas UMKM tidak memilikinya, sehingga:

- Pengajuan ditolak atau tidak pernah diajukan sama sekali karena pelaku usaha merasa "pasti tidak lolos".
- Usaha yang sebenarnya sehat dan layak modal tetap dinilai berisiko tinggi oleh lembaga keuangan.
- Pelaku usaha lari ke pinjaman informal berbunga tinggi, yang justru menggerus usaha.

> ⚠️ *Asumsi yang perlu diverifikasi dengan data saat validasi: proporsi UMKM yang gagal/enggan mengajukan KUR karena ketiadaan laporan keuangan. Angka di bagian ini selain yang berasal dari brief IDCamp adalah hipotesis lapangan, bukan statistik resmi.*

**Job-to-be-done produk ini bukan "membantu mencatat", melainkan "membuat usahaku layak mendapat modal".** Pencatatan hanyalah jalannya.

## 2. Solusi

**JembatanModal** adalah asisten AI berbahasa Indonesia dalam satu jendela chat. Pengguna tidak melihat modul atau form — mereka cukup mengobrol, dan AI yang memahami maksudnya.

### Tangga nilai

```
Level 1: MENCATAT    "apa yang terjadi di bisnisku?"   → P1  (P2 mempercepat)
Level 2: MEMAHAMI    "apa artinya angka-angka ini?"    → P4 → P3
Level 3: MENASIHATI  "apa yang harus saya lakukan?"    → P3
Level 4: BERTINDAK   "kerjakan untukku"                → P3
```

Aplikasi pembukuan yang ada berhenti di level 1–2. JembatanModal dirancang sampai level 4.

### Satu spine, kedalaman adaptif

Empat pilar itu **bukan** empat modul yang dipilih dari menu. Yang ada cuma satu
spine — **pencatatan** — dan kedalamannya menyesuaikan jenis usaha:

| Yang terdeteksi | Yang dimunculkan |
|---|---|
| Reseller (tukang sayur, kelontong) | Catat + untung. **Tidak pernah ditanya resep** — HPP-nya sudah = harga beli terakhir |
| Produsen (Bu Sari, ayam crispy) | Catat + **wawancara resep** → HPP tersembunyi dibongkar |
| Punya catatan lama | Ditawari impor (pilar 2) |

**Adaptasi digerakkan deteksi, bukan menu.** Pengguna tidak pernah memilih "mode
reseller" — AI yang menyimpulkan dari cara mereka bicara soal usahanya. Ini
konsekuensi langsung dari prinsip *satu pintu masuk* (§5 #5): begitu pengguna
harus memilih modul, produk ini kalah oleh aplikasi form-based yang sudah ada.

> **Luas di dalam, sempit di depan.** Spine-nya sengaja dirancang luas — cukup
> untuk menampung reseller, produsen, dan (nanti) jasa. Tapi yang **dijual**
> tetap sempit: produsen rumahan yang mau naik kelas
> ([00-project-brief.md §1](00-project-brief.md)). Menjual keluasan =
> "aplikasi serba bisa" = tidak punya alasan untuk dipilih.

**Empat pilar sebagai satu kesatuan** — urutan garap **1+4 → 2 → 3**
([00-project-brief.md §3](00-project-brief.md)):

### Pilar 1 — Pencatatan via obrolan

Pengguna mengetik (nanti: berbicara) dengan bahasa sehari-hari:

> "tadi laku 5 kotak risol 75 ribu"
> "beli minyak 2 liter 38rb buat dagang"
> "ambil 50 ribu buat jajan anak"

AI mengekstrak dan mengkategorikan otomatis ke empat kategori: **pemasukan, pengeluaran (bahan/kulakan), operasional, dan pribadi (prive)**. Kategori prive penting — pemisahan uang usaha vs pribadi adalah salah satu indikator utama kesehatan usaha di mata bank. Setiap pencatatan dikonfirmasi singkat ("✅ Tercatat: pemasukan Rp75.000 — risol 5 kotak") agar pengguna bisa mengoreksi jika AI salah paham.

**Yang diekstrak bukan hanya nominal.** AI juga mengenali **produk & takaran** —
`"laku 5 kotak risol 75rb"` → produk *risol*, qty *5*; `"beli minyak 2 liter 38rb"`
→ bahan *minyak*, qty *2 liter* (sekaligus memberi tahu harga minyak Rp19.000/liter).
Tanpa tautan produk/bahan + kuantitas ini, **HPP mustahil dihitung** — inilah
alasan teknis pilar 1 & 4 saling mengunci ([02-arsitektur.md §3a](02-arsitektur.md)).

### Pilar 4 — Extract HPP: "sebenarnya untung berapa?"

Prioritas bersama pilar 1, dan **jantung kejujuran produk**. Tanpa HPP, laba-rugi
hanya "uang masuk − uang keluar" — itu bukan untung bersih, dan semua laporan di
atasnya menyesatkan.

Banyak pelaku mikro berjualan tiap hari tanpa tahu untung bersih, modal, dan biaya
secara terperinci. AI membantu membongkarnya lewat **wawancara santai, bukan form**:

> "Bu, sekali bikin risol jadi berapa kotak?" — *"10 kotak"*
> "Pakai bahan apa saja & berapa?" — *"tepung sekilo, minyak setengah liter, ayam setengah kilo"*
> "Minyak sudah saya tahu harganya dari belanja kemarin (Rp19.000/liter). Tepung sama ayam belum — sekilo berapa?"

Hasilnya: **HPP Rp3.950/kotak**, harga jual Rp15.000 → laba kotor Rp11.050/kotak.
Untuk reseller (tukang sayur) jauh lebih sederhana: HPP = harga beli terakhir.

### Satu model biaya, bukan satu model per segmen

Reseller dan produsen tampak seperti dua kasus berbeda, padahal keduanya **kasus
khusus dari satu model**: HPP = **kumpulan komponen biaya**, tiap komponen
bertipe `{material | labor_time | overhead}`.

| Segmen | HPP tersusun dari |
|---|---|
| Reseller | material: harga beli terakhir |
| Produsen | Σ(material × harga) ÷ yield |
| Jasa (salon, laundry) | labor_time × tarif + consumable per pakai |
| Bengkel / servis HP | material (parts) + labor_time — hibrida |
| Cafe/resto | material + labor per porsi + overhead per porsi |

**Yang dikerjakan sekarang hanya `material`.** Tapi model biayanya dirancang agar
`labor_time` dan `overhead` bisa masuk **tanpa migrasi menyakitkan** — sehingga
jasa dan cafe jatuh nyaris gratis nanti, tanpa modul terpisah
([02-arsitektur.md §3a](02-arsitektur.md)). Ini asuransi skema, **bukan** izin
membangun fitur jasa hari ini; jasa tetap non-goal
([00-project-brief.md §4](00-project-brief.md)).

Simetri yang menarik: aha moment jasa **nyata tapi beda bentuk** — bukan *"biaya
bahanmu tersembunyi"* melainkan *"waktumu punya harga, dan selama ini kamu
berikan gratis"*. Pelaku mikro jasa hampir selalu tidak menghitung upah dirinya
sendiri. ⚠️ Ini **hipotesis**, belum diuji ke pelaku jasa — dan harus lolos
Tahap 0 sebelum jasa dinaikkan dari non-goal.

Dua prinsip yang tidak bisa ditawar:
- **Asal tiap angka selalu ditampilkan** ("pakai harga minyak per 12 Juli") — HPP tidak boleh jadi kotak hitam.
- **Kalau data kurang, ngaku** — resep kosong atau bahan tanpa harga → *"belum diketahui"*, bukan tebakan. Laporan selalu menyebut **cakupan HPP** ("tercakup 78% omzet").

### Pilar 2 — Impor data: onboarding cepat **dan** bukti yang dipercaya

Pilar 2 melayani **dua tujuan**, bukan satu:

**(a) Memotong cold-start.** Pengguna baru = data kosong = skor & laporan tak
berguna berminggu-minggu. **AI membaca catatan yang sudah ada, apa pun
bentuknya** — foto buku tulis, screenshot chat, spreadsheet, sampai export
platform (majoo, BukuWarung, WargaFinance, dst.).

**(b) Membuat laporan dapat dipercaya.** Ini peran yang sama pentingnya dan
sebelumnya tidak tertulis. Laporan yang **seluruh angkanya diketik sendiri oleh
pengguna** adalah bukti lemah bagi penyalur — justru itu alasan bank meminta
rekening koran, bukan buku tulis. Maka sumber data yang **objektif dan sulit
dikarang** punya nilai berbeda dari sekadar mempercepat: **riwayat QRIS /
e-wallet, mutasi mobile banking, payout marketplace/ojek online.**

> ⚠️ **Hipotesis yang menentukan, belum diuji:** bahwa riwayat QRIS + konsistensi
> pencatatan benar-benar **mengubah kepercayaan penyalur** — atau apakah mereka
> tetap meminta rekening koran apa pun yang kita sodorkan. Kalau premis ini
> gugur, seluruh framing (b) ikut gugur. Ditanyakan langsung ke AO bank di
> Tahap 0 ([04-rencana-kerja.md](04-rencana-kerja.md)). **Prioritas adaptor QRIS
> bersifat kondisional pada jawaban itu** — belum dijadwalkan.

Prinsip yang mendasarinya, terlepas dari hasil validasi: **data terverifikasi >
self-report.**

Sengaja **tidak dikunci ke format platform tertentu**: mayoritas segmen mikro tidak
punya data platform — yang mereka punya foto buku tulis. Format platform hanyalah
*salah satu* adaptor. Visi ekspansinya: makin banyak bentuk laporan bisa diekstrak
seiring waktu, cukup dengan menambah adaptor.

**Aturan keras: impor tidak pernah langsung jadi transaksi.** Hasil parse masuk
sebagai draft untuk ditinjau pengguna. Salah parse yang masuk diam-diam =
pembukuan tercemar tanpa pengguna sadar.

### Pilar 3 — Dari kejelasan ke modal formal

Payoff-nya. Terdiri dari empat kemampuan yang saling menyambung:

#### 3a. Laporan keuangan standar bank

Dari data transaksi + HPP (pilar 4), sistem menyusun:

- **Laporan laba-rugi sederhana** — **Omzet − HPP = Laba Kotor − Biaya Operasional = Laba Bersih**, per bulan. Baris HPP inilah yang membedakannya dari sekadar rekap kas.
- **Arus kas sederhana** (kas masuk, kas keluar, saldo)
- Ekspor **PDF rapi** dengan format yang familier bagi petugas bank/koperasi — lengkap dengan identitas usaha, periode, dan **cakupan HPP** agar pembaca tahu seberapa lengkap datanya

Pengguna cukup minta: "buatkan laporan bulan Mei" → PDF siap diunduh/dibagikan.

#### 3b. Skor Kesehatan Usaha

Skor **0–100** yang dihitung **secara deterministik** (bukan oleh LLM) dari rasio-rasio data:

- Konsistensi pencatatan (seberapa rutin transaksi dicatat)
- Margin laba (laba bersih / omzet)
- Tren omzet (naik/stabil/turun antar periode)
- Disiplin pemisahan keuangan (rasio prive terhadap laba)

AI kemudian **menarasikan** skor itu dalam bahasa sehari-hari: apa yang sudah bagus, apa yang menahan skor, dan langkah konkret untuk memperbaikinya ("Margin Ibu sehat, tapi pencatatan bolong 12 hari bulan ini — bank melihat ini sebagai usaha yang tidak tertib administrasi").

Skor ini menjadi *gamifikasi yang bermakna*: pengguna termotivasi mencatat rutin karena ada tujuan nyata — skor naik = makin layak kredit.

**Dua keluaran yang harus dipisah tegas.** Skor sedang memikul dua peran yang
bertabrakan — memotivasi pengguna **dan** menjadi bukti ke penyalur — padahal
ambangnya masih tebakan awal. Satu angka tidak bisa melakukan keduanya dengan
jujur:

| Ke siapa | Yang disajikan | Boleh berubah? |
|---|---|---|
| **Pengguna** | Skor komposit, progres, streak, cakupan HPP — bahasa motivasi | Ya. Boleh kasar, boleh dikalibrasi ulang |
| **Penyalur** | **Hanya fakta mentah terverifikasi**: omzet, jumlah bulan pencatatan konsisten, cakupan HPP %, rasio prive | Tidak. Ini fakta, bukan penilaian |

**Skor komposit tidak pernah dihadapkan ke penyalur sebelum terkalibrasi data
pengajuan nyata.** Menyodorkan "72/100" ke AO bank berarti mengarang otoritas
yang belum kita punya — bank punya model risiko sendiri, dan skor kita saat ini
adalah tebakan berbaju angka. Yang boleh kita klaim cuma fakta yang bisa
ditelusuri.

**Flywheel kalibrasi.** Tiap pengajuan KUR yang lewat aplikasi dilacak hasilnya
(lolos / ditolak / plafon yang cair). Data itulah — bukan intuisi — yang lama-lama
mengkalibrasi ambang skor. Artinya skor baru layak dihadapkan ke penyalur setelah
flywheel ini berputar cukup lama ([03-roadmap.md](03-roadmap.md) H4).

#### 3c. Asisten Pengajuan KUR

Saat pengguna siap ("aku mau ajukan KUR"), AI melakukan **wawancara santai**: lama usaha berjalan, bentuk usaha, kebutuhan modal dan peruntukannya, aset yang dimiliki. Jawaban digabung dengan data keuangan yang sudah ada, lalu AI menghasilkan:

1. **Draf proposal pengajuan kredit** — profil usaha, ringkasan keuangan, rencana penggunaan dana, proyeksi sederhana
2. **Checklist dokumen** yang harus disiapkan (KTP, KK, surat keterangan usaha, dll.) sesuai persyaratan umum KUR
3. **Lampiran laporan keuangan** dari fitur 2

Disclaimer selalu disertakan: dokumen ini **alat bantu persiapan**, bukan jaminan persetujuan — keputusan tetap di lembaga penyalur.

#### 3d. Panduan perizinan & badan hukum

Barrier terbesar menuju modal formal sering **bukan dokumen — tapi rasa takut**.
Bu Sari tidak pernah mengajukan KUR karena *"ribet, pasti ditolak"*. Hal yang sama
berlaku untuk NIB, izin usaha, dan badan hukum: dipersepsikan menakutkan, padahal
langkahnya bisa dijelaskan.

AI menjelaskan langkah, syarat, dan urutannya dalam bahasa sehari-hari — sehingga
pengguna tahu bahwa ini **tidak semenakutkan yang dibayangkan**.

**Batas tegas:** ini **memandu & menjelaskan saja**. JembatanModal **tidak**
mengurus atau mengajukan izin ke badan berwenang ([00-project-brief.md §4](00-project-brief.md)).
Semua isi panduan berasal dari **basis terkurasi yang bersumber + bertanggal**,
bukan dari ingatan LLM — aturan perizinan berubah, dan salah info di sini
menghancurkan kepercayaan.

## 3. Persona & User Journey

**Bu Sari, 41 tahun — usaha katering & frozen food rumahan, Bandung.**
Omzet ±Rp9 juta/bulan. Pesanan via WhatsApp. Pencatatan di buku tulis, sering bolong. Ingin beli freezer kedua dan menambah stok, butuh modal ±Rp15 juta. Tidak pernah mengajukan KUR karena "ribet, pasti ditolak, nggak punya pembukuan".

| Minggu | Yang dilakukan Bu Sari | Yang terjadi di JembatanModal |
|--------|------------------------|-------------------------------|
| 1 | **Memotret buku tulisnya** yang berisi catatan sebulan terakhir | *(P2)* AI membaca & mengusulkan draft → Bu Sari meninjau sekilas → data langsung hidup, tak perlu menunggu berminggu-minggu |
| 1 | Mulai mencatat lewat chat tiap habis transaksi, 30 detik saja | *(P1)* Data terkumpul & terkategori rapi — **beserta produk dan takarannya** |
| 2 | Ditanya AI: "sekali bikin risol jadi berapa kotak, bahannya apa saja?" | *(P4)* Resep tersimpan → **HPP Rp3.950/kotak** terhitung dari harga bahan belanjaannya sendiri |
| 2 | Tanya "untungku minggu ini berapa?" | **Momen kaget:** untung bersih ternyata jauh di bawah dugaannya — karena selama ini ia mengira omzet = untung |
| 4 | Lihat Skor Kesehatan Usaha: 58/100 | *(P3)* AI menjelaskan: margin bagus, tapi pencatatan belum konsisten & prive terlalu besar |
| 8 | Skor naik ke 74. Minta laporan 2 bulan | PDF laba-rugi & arus kas 2 bulan siap |
| 9 | "Aku mau ajukan KUR 15 juta buat freezer" | AI wawancara → draf proposal + checklist dokumen + lampiran laporan |
| 10 | Datang ke bank membawa dokumen lengkap | Bu Sari datang bukan sebagai "pedagang tanpa pembukuan", tapi pemilik usaha dengan laporan 2 bulan dan proposal jelas |

## 4. Diferensiasi

| | Aplikasi pembukuan form-based (BukuWarung, BukuKas, dsb.) | ERP/akuntansi (Accurate, Jurnal) | **JembatanModal** |
|---|---|---|---|
| Cara input | Form, pilih kategori manual | Form kompleks, butuh paham akuntansi | Obrolan bahasa sehari-hari |
| Kurva belajar | Sedang | Tinggi | Hampir nol |
| Cara mulai | Isi dari nol | Isi dari nol / impor teknis | **Foto buku tulis yang sudah ada** (P2) |
| HPP | Manual, kalau ada | Butuh setup BOM formal | **Diwawancarai secara ngobrol** (P4) |
| Level nilai | Mencatat + grafik | Mencatat + laporan | Mencatat → **tahu untung sesungguhnya** → menasihati → **bertindak (dokumen KUR)** |
| Tujuan akhir bagi pengguna | "Catatanku rapi" | "Pembukuanku benar" | **"Usahaku layak dapat modal"** |

### Kenapa harus Generative AI?

1. **Parsing bahasa natural** — "laku 5 risol 75rb tadi siang" menjadi data terstruktur **berikut produk & takarannya**; mustahil dengan rule-based, trivial dengan LLM.
2. **Membaca data berantakan** *(P2)* — foto buku tulis, screenshot, spreadsheet berkolom sembarang → data terstruktur. Inilah yang membuat "impor apa pun bentuknya" realistis.
3. **Mendeteksi jenis usaha dari struktur biayanya** — dari cara pengguna bicara soal usahanya, AI menyimpulkan apakah dia *mengubah bahan jadi produk lain* (produsen) atau *menjual ulang* (reseller). Inilah yang membuat "kedalaman adaptif tanpa menu" (§2) mungkin. Rule-based akan gagal di sini: "jualan ayam" bisa berarti reseller ayam potong **atau** produsen ayam crispy — yang membedakan cuma konteks bahasa.
4. **Wawancara adaptif** — menyusun resep/BOM *(P4)* dan asisten KUR *(P3)* menyesuaikan pertanyaan dengan jawaban sebelumnya, seperti konsultan sungguhan.
5. **Narasi yang dipersonalisasi** — penjelasan skor dan laporan dalam bahasa yang pas untuk pengguna non-teknis, bukan template kaku.
6. **Drafting dokumen** — menyusun proposal yang koheren dari data terstruktur + hasil wawancara.

> Perhatikan pola: **LLM dipakai untuk memahami dan menarasikan — tidak pernah untuk menghitung.** Semua angka (HPP, laba, skor) lahir dari kalkulasi deterministik.

### Kenapa pengguna bertahan setelah modalnya cair

Ada tebing churn yang built-in di produk ini: **payoff-nya sekali.** KUR cair →
tujuan tercapai → buat apa lagi buka aplikasi? Dan churn itu datang tepat di
momen pengguna paling puas.

Mesin retensi utamanya bukan gamifikasi, tapi **HPP di bawah harga bahan yang
bergejolak.** Harga minyak, ayam, tepung, cabai bergerak tiap bulan — artinya
margin produsen **berubah terus tanpa mereka sadari**. "Tahu untung" karena itu
bukan kebutuhan sekali, tapi kebutuhan **berulang**. Inilah alasan pilar 4 layak
disebut jantung produk bukan cuma karena kejujurannya, tapi karena daya tahannya.

Turunannya:
- **Margin-watch** — saat harga bahan kunci bergeser melewati ambang, AI menyapa
  duluan ("Bu, ayam naik Rp4.000/kg minggu ini — margin risol Ibu turun dari 73%
  ke 66%"). Ini versi ringan dari CFO proaktif, dan **buah langsung dari HPP**.
  Bergantung penuh pada HPP H1 — tidak bisa mendahuluinya.
- **Skor sebagai lintasan**, bukan angka sesaat — "naik 16 poin dalam 2 bulan"
  adalah cerita, dan cerita menahan orang.
- **Graduasi plafon** — modal formal bukan sekali seumur hidup; pengajuan kedua
  dengan riwayat lebih tebal adalah kelanjutan alami, bukan pengguna baru.

Retensi-via-HPP adalah **rasional kelas satu produk ini**, bukan fitur yang
menunggu di horizon jauh. Yang ditunda adalah *implementasinya*
([03-roadmap.md](03-roadmap.md)), bukan tempatnya dalam alasan produk ini ada.

## 5. Prinsip Desain

1. **Tanpa istilah teknis** — tidak ada "debit/kredit/jurnal"; semuanya bahasa warung.
2. **Bahasa Indonesia sehari-hari** — termasuk toleran terhadap singkatan, angka informal ("75rb", "1,5jt").
3. **Mobile-first & hemat bandwidth** — UI ringan, berfungsi di HP murah dan sinyal lemah.
4. **Angka tidak pernah dikarang** — semua angka (total, skor, laporan) hasil kalkulasi dari database; LLM hanya memahami input dan menarasikan output.
5. **Satu pintu masuk** — semua kemampuan diakses dari satu jendela chat; tidak ada menu yang harus dipelajari.
6. **Kepercayaan dulu** — konfirmasi tiap pencatatan, transparansi cara skor dihitung, disclaimer jelas pada dokumen kredit.
7. **Kedalaman adaptif lewat deteksi, bukan menu** (§2) — jenis usaha disimpulkan dari **struktur biayanya**, bukan ditebak dari ukurannya, lalu hanya pilar yang relevan yang muncul. Reseller tidak pernah ditanya resep. Kalau pengguna sampai harus memilih mode, prinsip #5 sudah bocor.
8. **Sempit di depan, luas di dalam** — spine boleh menampung banyak jenis usaha; yang dijual tetap satu segmen yang tajam ([00-project-brief.md §1](00-project-brief.md)).

# Project Brief — JembatanModal

> Pintu masuk dokumen. Menjawab **"apa yang dibangun & sampai mana batasnya"**.
> Dokumen hidup — di-update saat scope berubah. Keputusan yang membentuk brief
> ini dicatat di [../keputusan.md](../keputusan.md).
>
> **Frame:** produk jangka panjang. IDCamp Developer Challenge 2026 adalah
> *tonggak validasi*, **bukan** pembatas scope. (Lihat [keputusan 2026-07-17](../keputusan.md).)

---

## 1. Satu kalimat

JembatanModal adalah asisten AI berbahasa Indonesia yang mengubah catatan
keuangan harian UMKM menjadi **kejelasan untung-rugi yang jujur** dan
**kesiapan mengakses modal formal** — dari satu jendela obrolan.

> **Disiplin positioning: luas di dalam, sempit di depan.** Arsitektur boleh
> luas (satu spine pencatatan yang menampung banyak jenis usaha — §5,
> [02-arsitektur.md §3a](02-arsitektur.md)); **positioning harus sempit**.
> Yang dijual dengan lantang adalah **produsen rumahan yang mau naik kelas**,
> bukan "aplikasi serba bisa untuk semua UMKM". Menjual keluasan akan melanggar
> prinsip *satu pintu masuk, tanpa menu* (§6) dan membuat produk kehilangan
> alasan untuk dipilih.

## 2. Masalah yang diserang

Tiga klaster, dari yang paling universal ke paling struktural:

1. **Kabur soal uang sendiri.** Pelaku usaha berjualan tiap hari tapi tak tahu
   untung bersih, modal, dan biaya secara terperinci. Uang usaha bercampur uang
   pribadi. *(Universal — dari tukang sayur sampai cafe.)*
2. **Unbankable.** Tanpa laporan keuangan & pemisahan keuangan, usaha yang
   sebenarnya sehat tetap dinilai berisiko oleh bank/koperasi → lari ke pinjaman
   informal berbunga tinggi. *(⚠️ Hipotesis lapangan — proporsi UMKM yang gagal/
   enggan mengajukan KUR karena ketiadaan laporan **belum tervalidasi**; lihat
   [03-roadmap.md](03-roadmap.md) Fase 0.)*
3. **Takut pada yang formal.** KUR dan perizinan dipersepsikan "ribet, pasti
   ditolak, menakutkan" — barrier-nya **psikologis**, bukan sekadar dokumen.

> Yang **di luar jangkauan produk digital** (dan sengaja tidak diklaim):
> infrastruktur, iklim usaha, penetapan suku bunga, penerbitan izin. Produk ini
> menyiapkan & memandu, bukan menuntaskan ranah kebijakan.

## 3. Scope — empat pilar sebagai satu kesatuan

Keempatnya saling mengunci: pencatatan memberi data, HPP membuatnya jujur,
upload mempercepat, dokumen adalah payoff-nya. **Urutan garap: 1+4 → 2 → 3.**

| # | Pilar | Apa | Batas |
|---|-------|-----|-------|
| **1** | **Pencatatan harian** | Catat transaksi via obrolan bahasa sehari-hari; kategori otomatis (pemasukan, bahan/kulakan, operasional, prive). | Spine universal. Konfirmasi tiap catat agar bisa dikoreksi. |
| **4** | **Extract HPP → cashflow jujur** | AI membantu menghitung HPP/modal per produk (via tanya resep/BOM secara ngobrol untuk produsen; harga beli untuk reseller) → untung bersih & biaya yang benar. | Kedalaman berbeda per jenis usaha; mulai dari kasus sederhana. Semua angka hasil kalkulasi, bukan karangan LLM. |
| **2** | **Upload data laporan** | AI membaca catatan yang **sudah ada** untuk inisiasi/memperkaya data — foto buku tulis, screenshot chat, spreadsheet, hingga export platform. Visi: makin banyak bentuk laporan yang bisa diekstrak seiring waktu. | **Bukan** dikunci ke satu format platform (mis. majoo hanya salah satu input, bukan patokan) — kalau dikunci ke format platform besar, justru meleset dari segmen mikro. |
| **3** | **Persiapan dokumen modal formal** | Dari data + wawancara: draf proposal KUR, checklist dokumen, laporan lampiran. Diperluas ke **memandu perizinan/badan hukum** — menjelaskan bahwa langkahnya tidak semenakutkan yang dibayangkan. | **Memandu & menjelaskan saja** — tidak filing, tidak mengurus ke badan perizinan. Info regulasi wajib bersumber + tanggal + disclaimer. |

Prioritas **1+4** karena di situ letak "aha moment": catat gampang → tahu untung
bersih sesungguhnya (sering mengejutkan). Pilar **3** adalah payoff yang dijual.

## 4. Non-goals (yang SENGAJA tidak dikerjakan)

- ❌ **Bukan** menggantikan POS/ERP — pelengkap, bukan pesaing.
- ❌ **Tidak** memfiling/mengurus perizinan ke badan berwenang — hanya memandu.
- ❌ **Tidak** memegang uang, menyalurkan pinjaman, atau menjamin persetujuan
  kredit — keputusan tetap di lembaga penyalur.
- ❌ **Tidak** menjadi aplikasi akuntansi ber-istilah teknis (debit/kredit/jurnal).
- ❌ **Tidak** mengunci upload ke satu format platform tertentu.
- ❌ Angka apa pun (skor, laporan, HPP) **tidak** dikarang LLM — LLM hanya
  memahami input & menarasikan output kalkulasi.
- ⏸️ **Sektor jasa (salon, laundry, jahit) belum digarap — tapi skemanya tidak
  ditutup.** HPP jasa tersusun dari *waktu kerja*, bukan bahan; formula
  `Σ(bahan × harga) ÷ yield` tidak berlaku untuk mereka. Sampai sekarang jasa
  tersingkir **diam-diam lewat bentuk skema** — itu diubah jadi **penundaan
  sadar**: implementasi material-only dulu, tapi model biaya dirancang agar
  `labor_time` bisa masuk tanpa migrasi menyakitkan
  ([02-arsitektur.md §3a](02-arsitektur.md)). Menaikkannya dari non-goal
  menunggu validasi Tahap 0 ([04-rencana-kerja.md](04-rencana-kerja.md)).

## 5. Persona & segmen — dua sumbu, bukan tangga ukuran

Target inti **tidak** disaring oleh ukuran usaha. Ia disaring oleh dua sumbu:

| Sumbu | Pertanyaan | Kenapa menentukan |
|---|---|---|
| **A — biaya pokok tersembunyi** | Apakah usaha ini *mengubah bahan jadi produk lain*? | Kalau ya, HPP-nya tidak kelihatan tanpa dihitung → pilar 4 punya sesuatu untuk dibongkar, dan "aha moment" jadi kejutan sungguhan |
| **B — rencana modal konkret** | Ada kebutuhan modal spesifik dalam ~3–6 bulan? | Tanpa ini pilar 3 — payoff yang dijual — tidak punya daya tarik |

**Target inti = produsen barang skala rumahan yang memenuhi A dan B.** Bu Sari
memenuhi keduanya; itulah alasan dia beachhead, bukan karena ukurannya.

**Ukuran usaha hanyalah proksi kasar** yang kebetulan berkorelasi — dan proksi
yang menyesatkan kalau dipakai sendirian. Contoh penajam: *tukang ayam crispy
baru mulai* adalah **produsen** (ayam + tepung + minyak → potongan crispy; HPP
tersembunyi), **bukan** reseller — walau usahanya kecil sekali. Sebaliknya toko
obat kecil adalah reseller. **Klasifikasi jenis usaha karena itu harus berbasis
struktur biaya, bukan tebakan ukuran** ([02-arsitektur.md §3a](02-arsitektur.md)).

### Nilai menumpuk di tengah, tidak menyebar rata

```
                     sumbu A        sumbu B
                  (HPP tersembunyi) (butuh modal)
Ultra-mikro         ✗ lemah          ~ lemah      → pilar 4 runtuh jadi pilar 1
  (tukang sayur)                                    (HPP = harga beli terakhir)
Produsen rumahan    ✓ kuat           ✓ kuat       → 4 pilar menyala semua ★
  (Bu Sari, ayam crispy)
Cafe / kecil-menengah ✓ kuat         ✗ lemah      → sering sudah bankable /
                                                    sudah punya POS
```

Ini mengoreksi framing tangga yang lama: ultra-mikro **bukan** pintu masuk yang
kuat lewat pilar 1+4, karena bagi reseller HPP = harga beli terakhir — angka yang
baru saja mereka ketik sendiri. Yang tersisa untuk mereka adalah "catatan rapi",
dan itu sudah dilayani gratis oleh pemain lain.

**Jangkauan sebagai tangga tetap berlaku sebagai peta ekspansi sekunder** —
spine data + model biaya yang sama memang memungkinkan "menjalar" ke ultra-mikro
(layer catat) dan ke cafe (food-cost lebih dalam). Tapi itu **jangkauan**, bukan
**target**. **Menjangkau ≠ memonetisasi.**

> ⚠️ **Hipotesis, bukan fakta:** klaim bahwa nilai menumpuk di tengah lahir dari
> analisis mekanika produk, **belum** dari lapangan. Tahap 0
> ([04-rencana-kerja.md](04-rencana-kerja.md)) harus mengujinya — termasuk
> kemungkinan bahwa reseller ternyata *tetap* mau membayar untuk "catatan rapi".

## 6. Prinsip kunci

1. **Angka tidak pernah dikarang** — semua dari database/kalkulasi deterministik.
2. **Bahasa warung** — tanpa istilah teknis; toleran singkatan & angka informal.
3. **Satu pintu masuk** — semua kemampuan dari satu jendela chat.
4. **Mobile-first, hemat bandwidth** — jalan di HP murah & sinyal lemah.
5. **Kepercayaan dulu** — konfirmasi tiap catat, transparansi cara skor dihitung,
   disclaimer jelas pada dokumen kredit & panduan regulasi.
6. **GenAI dipakai di tempat yang tepat** — parsing bahasa natural, membaca data
   berantakan (pilar 2), wawancara adaptif (resep untuk HPP, KUR), drafting
   dokumen. **Bukan** untuk menghitung angka.
7. **Dibayar untuk lead jujur terkualifikasi, bukan untuk lead yang lolos.**
   Pagar etis terhadap sisi penyalur. Begitu penyalur membayar *per-pengajuan-
   yang-disetujui*, insentif produk bergeser diam-diam dari kesehatan pengguna
   ke volume pengajuan — dan dorongan berikutnya adalah membuat laporan tampak
   lebih bagus daripada kenyataan. Itu mengkhianati prinsip #1. Prinsip ini
   mengikat **apa pun** model bisnis yang nanti dipilih (§7).
8. **Kedalaman adaptif, satu spine.** Produk mendeteksi jenis usaha lalu hanya
   memunculkan pilar yang relevan — reseller tidak pernah ditanya resep, produsen
   diwawancarai. Adaptasi digerakkan **deteksi**, bukan menu yang harus dipilih
   pengguna (turunan dari prinsip #3).

## 7. Keputusan terbuka / blocker

- ✅ **Extend vs repo baru — TERKUNCI (2026-07-17):** standalone, kode di
  folder/repo terpisah, data milik sendiri; WargaFinance hanya salah satu sumber
  impor pilar 2. Tidak ada lagi yang memblokir penulisan kode.
  ([../keputusan.md](../keputusan.md))
- ✅ **Kedalaman HPP untuk produsen — SUDAH DIDESAIN:** resep/BOM, sumber harga
  bahan, dan jalur degradasi di [02-arsitektur.md §3a](02-arsitektur.md).
  Implikasi penting: transaksi harus tertaut ke produk/bahan + kuantitas, jadi
  pilar 1 ikut menebal.
- ⚠️ **Premis unbankable** (klaster masalah #2) belum tervalidasi — Tahap 0
  [04-rencana-kerja.md](04-rencana-kerja.md) harus mengonfirmasinya sebelum
  dianggap fakta.
- ⚠️ **Kalibrasi ambang skor** masih tebakan awal — perlu masukan praktisi
  pembiayaan mikro. Sampai terkalibrasi data pengajuan nyata, **skor komposit
  tidak dihadapkan ke penyalur** ([02-arsitektur.md §4](02-arsitektur.md)).
- 🎲 **Model harga — TERBUKA, sengaja belum dikunci.** Nilai produk *runcing*
  (menumpuk di momen modal cair), bukan rata sepanjang bulan — jadi langganan
  pukul-rata kemungkinan salah bentuk. Hipotesis bentuk per segmen: reseller/
  ultra-mikro → **gratis**; produsen → **per-dokumen / success-fee saat cair**;
  cafe → **langganan analitik** (nilainya memang berulang). Ketiganya **belum
  diuji** — Tahap 0 ([04-rencana-kerja.md](04-rencana-kerja.md)) yang menjawab.
  Mengunci ini dini itu mahal dan sulit dibalik.
- 🎲 **Siapa yang membayar — TERBUKA.** Dua jalur melahirkan produk yang berbeda:
  (a) **pengguna bayar per-nilai**, atau (b) **penyalur bayar** untuk aliran
  pemohon tersaring. *Default kerja* (bukan keputusan): pengguna bayar per-nilai;
  penyalur diperlakukan sebagai **kanal distribusi & verifikasi, bukan pembeli
  lead**. Pagar etisnya sudah dikunci sebagai prinsip (§6 #7); yang terbuka
  adalah pengaturan bisnisnya.
- 📄 **`docs/sumber-data.md` belum ada** — semua statistik pasar masih berstatus
  belum-final sampai tersedia.
- ✅ **Penyelarasan roadmap ke frame produk-first — SELESAI.** [03-roadmap.md](03-roadmap.md)
  kini berhorizon H1–H4 tanpa tenggat, dan [04-rencana-kerja.md](04-rencana-kerja.md)
  berTahap 0–5; keduanya sudah memperlakukan IDCamp sebagai tonggak validasi
  opsional. *(Catatan basi "masih berbingkai IDCamp / Fase 1 MVP Hackathon"
  dicabut 2026-07-17 — sudah tidak sesuai isi file.)*

## 8. Hubungan dengan dokumen lain

- [01-konsep-produk.md](01-konsep-produk.md) — latar, persona, diferensiasi (detail).
- [02-arsitektur.md](02-arsitektur.md) — desain teknis, skema, model biaya, skor.
- [03-roadmap.md](03-roadmap.md) — horizon H1–H4: produk ini menjadi apa.
- [04-rencana-kerja.md](04-rencana-kerja.md) — Tahap 0–5: tugas untuk H1 & H2.

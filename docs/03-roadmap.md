# Roadmap — JembatanModal

> **Horizon produk jangka panjang.** Dokumen ini menjawab *"produk ini menjadi apa
> seiring waktu"*. Untuk *"tugas apa yang dikerjakan sekarang"* → [04-rencana-kerja.md](04-rencana-kerja.md).
> Scope & batas → [00-project-brief.md](00-project-brief.md).
>
> Frame: **produk jangka panjang, standalone**. IDCamp = tonggak validasi
> opsional, **bukan** pembatas scope ([../keputusan.md](../keputusan.md), 2026-07-17).
>
> ⏱️ Tanpa tanggal. Horizon berpindah karena **sinyal**, bukan karena tenggat.

---

## Pembagian kerja dengan rencana-kerja

```
03-roadmap.md (file ini)   →  H1 · H2 · H3 · H4   — horizon: produk jadi apa
04-rencana-kerja.md        →  Tahap 0–5           — tugas untuk H1 & H2
```

Rencana-kerja saat ini mencakup **H1 + H2**. H3 & H4 sengaja belum dipecah jadi
tugas — memecahnya sekarang = perencanaan spekulatif di atas asumsi yang belum
teruji.

---

## H1 — Untung yang jujur *(pilar 1 + 4)*

**Pertanyaan yang dijawab produk:** *"Sebenarnya saya untung berapa?"*

- Pencatatan via obrolan, lengkap dengan **produk & takaran**.
- HPP: resep/BOM secara ngobrol, harga bahan dari transaksi pembelian.
- Untung bersih & margin per produk — dengan **cakupan HPP** yang jujur.
- Koreksi via chat; semua angka deterministik & ber-unit-test.
- **Deteksi jenis usaha** dari struktur biayanya — reseller tidak pernah ditanya resep.
- Model biaya `{material|labor_time|overhead}` **dirancang**, `material` **diimplementasi**.

**Sinyal untuk lanjut:** pengguna uji coba mengalami momen *"oh, ternyata untung saya segini"* — dan angkanya mereka percaya.

> Ini **inti produk**. Kalau harus berhenti di satu titik, berhentilah di sini —
> H1 sudah punya nilai nyata yang berdiri sendiri.

> **Janji yang dimulai di sini, bukan tugas H1:** HPP adalah **mesin retensi**
> produk ini. Harga bahan bergejolak → margin berubah tiap bulan → "tahu untung"
> jadi kebutuhan **berulang**, bukan sekali. Itulah yang kelak melawan tebing
> churn pasca-KUR (H4 *margin-watch*). Disebut sejak sini supaya H1 dibangun
> dengan sadar bahwa `cost_item_prices` bertanggal itu **fondasi retensi**, bukan
> sekadar jejak audit. ([01-konsep-produk.md §4](01-konsep-produk.md))

## H2 — Cepat berguna & berbuah dokumen *(pilar 2 + 3)*

**Pertanyaan:** *"Bagaimana saya mulai tanpa menunggu berbulan-bulan, dan apa hasilnya?"*

- Impor data (foto buku tulis, screenshot, CSV, export platform) → draft → tinjau → data. Mengatasi cold-start.
- Laporan standar bank (Omzet − HPP = Laba Kotor − Operasional = Laba Bersih) → PDF.
- Skor Kesehatan Usaha + narasi & saran perbaikan — **keluaran pengguna saja**; yang masuk dokumen penyalur adalah **fakta mentah**, bukan skor komposit ([02-arsitektur.md §4](02-arsitektur.md)).
- Asisten KUR: wawancara → proposal + checklist. **Hasil pengajuan dicatat** (`kur_outcomes`) — bahan bakar flywheel kalibrasi di H4.
- Panduan perizinan/badan hukum — **memandu & menjelaskan**, dari basis terkurasi bersumber.

### Impor punya dua tujuan, bukan satu

Selain memotong cold-start, impor adalah **tulang punggung verifikasi**: laporan
yang seluruh angkanya diketik sendiri pengguna adalah bukti lemah bagi penyalur —
justru itu alasan bank meminta rekening koran. Sumber yang **objektif dan sulit
dikarang** (riwayat QRIS/e-wallet, mutasi mobile banking, payout marketplace)
karena itu punya nilai yang berbeda jenis dari foto buku tulis.

> ⚠️ **Belum tervalidasi:** apakah QRIS + konsistensi pencatatan benar-benar
> mengubah kepercayaan penyalur, atau mereka tetap minta rekening koran. **Urutan
> adaptor impor karena itu belum ditetapkan** — prioritas QRIS bersifat
> *kondisional* pada jawaban AO bank di Tahap 0
> ([04-rencana-kerja.md](04-rencana-kerja.md)). Kalau premis ini gugur, tujuan (b)
> ikut gugur dan H2 kembali murni soal onboarding.

**Sinyal untuk lanjut:** dokumen yang dihasilkan dinilai layak oleh AO bank/koperasi, dan pengguna berani membawanya.

## H3 — Menemui pengguna di tempatnya

**Pertanyaan:** *"Kenapa saya harus buka aplikasi?"*

- **Adaptor WhatsApp** (Cloud API) — semua fitur cukup dengan chat ke satu nomor. Arsitektur channel-agnostic sejak H1 membuat ini penambahan adaptor, bukan penulisan ulang. Approval Meta diurus lebih awal karena memakan waktu.
- **Input suara** — pesan suara → STT → alur ekstraksi yang sama. Penting bagi yang lebih nyaman bicara daripada mengetik.
- **Foto nota/struk** — vision mengekstrak transaksi belanja; memakai jalur parser yang sama dengan pilar 2.
- **PWA + antrean offline** untuk wilayah sinyal lemah.
- Pilot 20–50 UMKM nyata. Ukur: retensi pencatatan mingguan, cakupan HPP, laporan diekspor, dokumen dihasilkan.

**Sinyal untuk lanjut:** retensi pencatatan bertahan tanpa dorongan manual.

## H4 — Dari alat menjadi jembatan sungguhan

**Pertanyaan:** *"Apakah modalnya benar-benar cair?"*

- **CFO proaktif — dimulai dari `margin-watch`.** AI menyapa duluan saat harga bahan kunci bergeser melewati ambang ("ayam naik Rp4.000/kg — margin risol turun dari 73% ke 66%"). Ini **buah langsung dari HPP H1** dan **mesin retensi utama** melawan tebing churn pasca-KUR ([01-konsep-produk.md §4](01-konsep-produk.md)) — bukan sekadar fitur tambahan. Menyusul: pengingat mencatat, deteksi piutang macet, prediksi arus kas.
  > **Ketergantungan keras:** margin-watch mustahil tanpa HPP + `cost_item_prices` bertanggal dari H1. Jangan pernah menjadwalkannya mendahului H1.
- **Skor dikalibrasi data nyata — flywheel berputar.** `kur_outcomes` yang dikumpulkan sejak H2 (lolos/ditolak/plafon cair) menjadi bahan kalibrasi ulang bobot & ambang komponen. **Hanya setelah ini** skor komposit boleh dipertimbangkan untuk dihadapkan ke penyalur; sebelumnya yang dikirim cuma fakta mentah ([02-arsitektur.md §4](02-arsitektur.md)).
- **Kemitraan lembaga penyalur** — jajaki bank penyalur KUR/BPR/koperasi/fintech lending agar laporan & **fakta terverifikasi** diakui sebagai dokumen pendukung. Di sinilah "jembatan" tersambung di kedua ujungnya.
  > **Pagar etis mengikat di sini** ([00-project-brief.md §6](00-project-brief.md)): dibayar untuk **lead jujur terkualifikasi**, bukan **lead yang lolos**. Begitu skema komisi bergantung pada persetujuan, insentif bergeser ke volume pengajuan dan dorongan berikutnya adalah memoles laporan — mengkhianati "angka tidak pernah dikarang".
- **Graduasi plafon** — modal formal bukan sekali seumur hidup. Pengajuan kedua dengan riwayat lebih tebal adalah kelanjutan alami, bukan pengguna baru; ini bagian dari jawaban retensi.
- **Menjalar di tangga segmen** — turun ke ultra-mikro (layer catat), naik ke cafe (food-cost lebih dalam), dan **membuka `labor_time`** untuk jasa/bengkel bila validasi mendukung ([00-project-brief.md §4](00-project-brief.md)). Slot skemanya sudah disiapkan sejak H1 ([02-arsitektur.md §3a](02-arsitektur.md)) — di sinilah bunganya dipetik. Ingat: **tangga = jangkauan, bukan target** ([00-project-brief.md §5](00-project-brief.md)).
- Model keberlanjutan: **belum dikunci** — bentuk harga & siapa-yang-bayar masih keputusan terbuka ([00-project-brief.md §7](00-project-brief.md)), menunggu Tahap 0. Yang sudah pasti cuma pagar etisnya.

---

## Ringkasan

| Horizon | Fokus | Sinyal keberhasilan |
|---------|-------|---------------------|
| **H1** | Untung jujur (P1+P4) — deteksi jenis usaha, model biaya material-only | Pengguna percaya angka untung bersihnya |
| **H2** | Onboarding cepat + **verifikasi** + dokumen (P2+P3); mulai catat `kur_outcomes` | Dokumen dinilai layak oleh sisi penyalur |
| **H3** | WhatsApp, suara, foto nota, pilot | Retensi pencatatan bertahan |
| **H4** | Margin-watch, flywheel kalibrasi, kemitraan penyalur | Dokumen dipakai dalam pengajuan nyata |

**Benang retensi lintas horizon:** HPP (H1) → harga bertanggal (H1) →
margin-watch (H4). Retensi bukan fitur H4; ia **konsekuensi** dari cara H1
dibangun.

**Validasi berjalan paralel di semua horizon** — bukan fase tersendiri. Lihat [04-rencana-kerja.md](04-rencana-kerja.md) Tahap 0.

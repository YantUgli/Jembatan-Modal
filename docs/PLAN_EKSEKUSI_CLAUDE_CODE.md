# Plan Eksekusi — Claude Code

> **Untuk agen yang mengeksekusi.** Dokumen ini adalah instruksi kerja, bukan ringkasan.
> Tujuannya: kamu bisa mengeksekusi tugas berikutnya tanpa menebak dan tanpa perlu
> memverifikasi ulang teks regulasi. Semua fakta hukum yang sudah diverifikasi manusia
> ada di **Lampiran A** — perlakukan sebagai sumber kebenaran (source of truth) dan jangan
> ubah tanpa persetujuan eksplisit.
>
> **Baca urutan ini:** §0 (kontrak kerja) → §1 (status) → §2 (quick start) → tugas per §.
> Setiap tugas punya **Precondition**, **Langkah**, **File**, dan **Definition of Done (DoD)**
> yang bisa dites. Jangan tandai selesai sebelum perintah verifikasi di DoD lolos.

---

## 0. Kontrak kerja (aturan main untuk agen)

1. **Jangan menebak angka atau nomor pasal.** Semua tarif, plafon, dan `pasal_rujukan`
   sudah dikunci di **Lampiran A**. Jika sebuah tugas menuntut angka yang **tidak ada** di
   Lampiran A, **berhenti dan tanya** — jangan mengarang. Jika ketentuan yang dibutuhkan
   berada di luar Lampiran A (mis. syarat calon penerima, restrukturisasi/suplesi, pola
   linkage, format lampiran pelaporan), **baca teks asli di `docs/regulasi/2026PemenkoEkon001.pdf`**
   (lihat Lampiran B) — jangan mengarang dan jangan menyimpulkan dari ingatan.
2. **Dahulukan kebocoran, bukan yang terbesar.** Bug kehilangan-data (§3, `simpan_snapshot_hpp`)
   dieksekusi lebih dulu daripada fitur bernilai tinggi. Yang tertunda masih ada besok; yang
   bocor hilang permanen.
3. **Test mendarat di commit yang sama dengan kode yang diujinya.** Terutama guard 4c dan
   router 4c — dilarang "menyusul test nanti".
4. **Satu tugas = satu commit yang lolos DoD.** Jangan menggabung tugas lintas-§ dalam satu
   commit. Pesan commit menyebut ID tugas (mis. `B1: wire simpan_snapshot_hpp ke jalur produksi`).
5. **Jalankan test suite penuh sebelum menandai tugas selesai.** DoD yang menyebut perintah
   `pytest ...` harus benar-benar dijalankan, bukan diasumsikan.
6. **Jangan turunkan prioritas snapshot HPP** hanya karena bobotnya kecil (~5%). Itu bug, bukan fitur.

---

## 1. Status komponen (per hari ini)

Perubahan penting sejak ringkasan terakhir: **verifikasi A1 (teks Permenko 1/2026) sudah SELESAI.**
Tarif per jenis KUR, nomor pasal, dan `sumber_url` final sudah terkonfirmasi (lihat Lampiran A).
Konsekuensinya: **gerbang verifikasi pertama untuk 4c sudah lolos** — entri `draft` sekarang layak
dinaikkan ke `aktif`, dan router 4c menjadi layak dibangun.

| Komponen | Status | Catatan |
|---|---|---|
| P1 pencatatan | ✅ ~100% | — |
| P4 HPP | ⚠️ ~95% | **`simpan_snapshot_hpp` belum dipanggil di jalur nyata → kebocoran data (§3, B1)** |
| P3 laporan penyalur (4a) + skor usaha (4b) | ✅ ~90% | label router `tanya_skor` belum di-wire (§4, B2) |
| P2 impor | 🚧 ~35% | pipa unggah/CSV generik belum ada (§5, B3) |
| panduan_entries (skema) | ✅ selesai | field lengkap + status `draft` |
| Entri bunga KUR (seed) | 🟡 → siap naik `aktif` | **A1 sudah verified → eksekusi §6 (D1)** |
| Guard 4c | ✅ dibangun & teruji (18 test) | belum di-wire ke router (§7, C1) |
| P3 asisten KUR (4c / router) | 🟢 siap dibangun | dulu ditunda; **sekarang unblocked** (§7, C2) |
| kur_outcomes | 🟡 FK ada | mekanisme capture & cold-start belum diputuskan (§8, non-kode) |

---

## 2. Quick start (mulai di sini)

Eksekusi berurutan. Trek kode bisa jalan solo tanpa menunggu apa pun:

```
1. §3  B1  — simpan_snapshot_hpp ke jalur produksi   [DAHULUKAN: bug data-loss]
2. §4  B2  — label router tanya_skor                  [kecil, menuntaskan 4b]
3. §6  D1  — naikkan entri bunga KUR draft → aktif    [A1 sudah verified]
4. §7  C1  — wire guard 4c ke router                  [prasyarat C2]
5. §7  C2  — bangun router 4c (asisten KUR)           [guard+test di commit yang sama]
6. §5  B3  — unggah berkas + parser CSV generik       [tahan pemetaan format sampai fixture]
```

> Urutan D1 sebelum C2 itu wajib: router 4c yang dibangun sebelum ada entri `aktif` hanya
> menghasilkan fitur yang selalu menolak. D1 yang membuat C2 bermakna.

---

## 3. B1 — `simpan_snapshot_hpp` di jalur produksi  ⏰ DAHULUKAN

**Kenapa duluan:** bug kehilangan-data. Snapshot yang tak tersimpan hilang permanen begitu
produksi jalan. Sudah ditandai berkali-kali, belum tersentuh.

**Precondition:** tidak ada.

**Langkah:**
1. Telusuri definisi `simpan_snapshot_hpp` dan seluruh pemanggilnya
   (`grep -rn "simpan_snapshot_hpp" app/`).
2. Identifikasi jalur produksi P4 HPP tempat snapshot **seharusnya** dipanggil (titik commit
   perhitungan HPP final, bukan hanya jalur test lama).
3. Pasang panggilan `simpan_snapshot_hpp` di jalur nyata itu, dengan penanganan error yang
   tidak menelan kegagalan diam-diam (gagal simpan harus terlihat/tercatat, bukan lewat begitu saja).
4. Tulis test integrasi yang menjalankan jalur produksi end-to-end lalu **mengassert baris
   snapshot benar-benar ada di storage** — bukan sekadar memverifikasi fungsi dipanggil (mock).

**File:** jalur perhitungan HPP (P4) + modul snapshot; test integrasi baru.

**DoD (harus lolos):**
- [ ] `grep -rn "simpan_snapshot_hpp" app/` menunjukkan panggilan di jalur produksi, bukan hanya di test.
- [ ] Ada test integrasi baru yang **membaca kembali snapshot dari storage** setelah alur produksi.
- [ ] `pytest tests/ -k snapshot -q` hijau, dan test baru gagal bila panggilan produksi dihapus
      (buktikan test-nya benar-benar mengunci perilaku, bukan lolos kosong).

---

## 4. B2 — Label router `tanya_skor`

**Kenapa:** kecil; menuntaskan 4b jadi terjangkau end-to-end.

**Precondition:** tidak ada.

**Langkah:**
1. Temukan tabel/enum intent router (tempat label seperti `tanya_hpp`, `catat_transaksi`, dst. didaftarkan).
2. Tambah label `tanya_skor` dan petakan ke handler skor usaha 4b yang sudah ada.
3. Tambah contoh utterance/rute + test yang memastikan input skor ter-route ke handler yang benar.

**File:** modul router intent + test router.

**DoD:**
- [ ] Input contoh "berapa skor usaha saya" (dan variasi) ter-route ke handler 4b.
- [ ] `pytest tests/ -k router -q` hijau, termasuk case `tanya_skor` baru.

---

## 5. B3 — Unggah berkas + parser CSV generik

**Kenapa:** cakupan terbesar (P2 ~35%). **Tapi** dibangun sampai batas generik saja.

**Precondition:** tidak ada untuk pipa generik. **Pemetaan spesifik-format DITAHAN** sampai
fixture asli (A3) tersedia — bila dipaksakan berdasar format asumsi, risikonya rework saat
bentuk berkas asli ternyata beda.

**Langkah (bangun sekarang):**
1. Mekanisme unggah berkas + penanganan berkas (validasi tipe, ukuran, penyimpanan sementara).
2. Parser CSV **defensif**: deteksi encoding, deteksi pemisah kolom, deteksi baris header.
3. **Angka Rupiah gaya Indonesia** — ini jebakan klasik: titik = pemisah ribuan, koma = desimal
   (`1.250.000,50` → `1250000.50`). Tulis util parsing angka terpisah + test tabel kasus.

**Langkah (TAHAN — jangan kerjakan sampai A3):**
- Pemetaan kolom spesifik per format (rekening koran bank, ekspor QRIS/e-wallet, CSV pembukuan,
  foto tulis tangan). Sisakan sebagai antarmuka/strategy kosong berkomentar `# TODO: butuh fixture A3`.

**File:** modul impor (unggah + parser) + util angka Rupiah + test.

**DoD:**
- [ ] Unggah CSV generik menghasilkan baris ter-parse dengan header terdeteksi otomatis.
- [ ] Util angka Rupiah lolos test tabel: `1.000` → 1000, `1.250.000,50` → 1250000.50,
      `2500` → 2500, string kosong/invalid → error/None yang terdefinisi (bukan crash).
- [ ] Titik masuk pemetaan-format ada tapi eksplisit ditandai menunggu fixture (tidak
      mengimplementasi asumsi format).

---

## 6. D1 — Naikkan entri bunga KUR `draft → aktif`

**Kenapa sekarang bisa:** A1 selesai. Ini gerbang pertama dari dua gerbang KUR, dan sekarang lolos.

**Precondition:** **§7 C1 (guard wired) TIDAK diperlukan untuk D1**, tapi C2 (router) **tidak boleh
melayani user** sebelum D1 selesai. D1 dulu, baru C2 bermakna.

**Langkah:**
1. Ganti/isi tiap entri seed di `panduan_entries` memakai **Lampiran A** sebagai sumber:
   `pasal_rujukan`, `sumber_url`, `versi_regulasi`, tarif, plafon, aturan frekuensi.
2. **Pecah entri per `jenis_kur × sektor`, BUKAN per sektor saja.** Lihat koreksi di Lampiran A —
   Mikro non-ekspor (6→7%, maks 2 akad) berbeda dari Kecil non-ekspor (6→7→8→9%). Menyeragamkan
   keduanya adalah kesalahan yang guard 4c dirancang untuk menangkap.
3. Set `status = aktif`, `versi_regulasi = "Permenko 1/2026"`,
   `sumber_url = "https://peraturan.bpk.go.id/Details/342969/permenko-perekonomian-no-1-tahun-2026"`.
4. Jalankan guard 4c terhadap entri baru (18 test yang sudah ada) untuk memastikan entri lolos
   pemeriksaan `draft`/`superseded`/`tingkat_sumber`.

**File:** seed/migrasi `panduan_entries`.

**DoD:**
- [ ] Setiap entri punya `pasal_rujukan` yang cocok dengan Lampiran A (tidak ada placeholder/None).
- [ ] Ada entri terpisah untuk **Mikro non-ekspor** dan **Kecil non-ekspor** dengan jenjang tarif
      yang benar (bukan disamakan).
- [ ] `sumber_url` = URL Details BPK (bukan link Download yang rapuh).
- [ ] Guard 4c menerima entri (`pytest tests/ -k guard -q` hijau terhadap data aktif baru).

---

## 7. Trek C — Asisten KUR (4c)

### C1 — Wire guard 4c ke router

**Precondition:** tidak ada (guard sudah dibangun & 18 test lolos). Ini prasyarat #1 di DoD router.

**Langkah:**
1. Panggil guard (`app/services/panduan_kur.py`) di jalur router **sebelum** jawaban KUR apa pun
   dikembalikan ke user.
2. Pastikan guard menolak entri `draft`/`superseded`/sumber tak-tepercaya, dan meloloskan `aktif`.

**File:** router 4c + `app/services/panduan_kur.py` (integrasi).

**DoD:**
- [ ] Tidak ada jalur jawaban KUR yang melewati guard.
- [ ] Test: jawaban KUR atas entri `draft` diblokir; atas entri `aktif` diteruskan.

### C2 — Bangun router 4c (asisten KUR)

**Precondition:** **D1 selesai** (ada entri `aktif`) **dan C1 selesai** (guard wired). Jika salah
satu belum, JANGAN mulai C2 — hasilnya cuma fitur yang selalu menolak.

**Langkah:**
1. Bangun handler yang menjawab pertanyaan bunga/plafon/agunan KUR **hanya** dari `panduan_entries`
   yang `aktif` (jangan hardcode angka; ambil dari data).
2. Wajib lewat guard C1. Jawaban wajib menyertakan `pasal_rujukan` + `sumber_url` dari entri.
3. **Jangan pernah menjawab "6% flat / tanpa batas frekuensi" secara generik.** Itu benar hanya
   untuk Produksi + perdagangan ekspor. Perdagangan non-ekspor berjenjang (lihat Lampiran A).
4. "Ekspor" **bukan atribut yang diasumsikan** — di regulasi harus dibuktikan dokumen ekspor.
   Handler tidak boleh menyimpulkan status ekspor sendiri; perlakukan sebagai input yang harus disediakan.
5. Test end-to-end: pertanyaan per jenis KUR × sektor mengembalikan tarif yang cocok Lampiran A,
   beserta pasal + sumber. **Test mendarat di commit yang sama dengan router.**

**File:** router 4c + handler asisten KUR + test end-to-end.

**DoD:**
- [ ] Semua jawaban KUR bersumber dari entri `aktif`, bukan literal di kode.
- [ ] Tiap jawaban menyertakan `pasal_rujukan` + `sumber_url`.
- [ ] Test menutup: Super Mikro 3%, Mikro produksi/ekspor 6%, Mikro non-ekspor 6→7% (maks 2 akad),
      Kecil produksi/ekspor 6%, Kecil non-ekspor 6→7→8→9%, Khusus 6%, PMI 6% — cocok Lampiran A.
- [ ] Pertanyaan tanpa bukti ekspor tidak dijawab sebagai "ekspor".
- [ ] `pytest tests/ -q` seluruhnya hijau; test router + guard ada di commit yang sama.

---

## 8. Non-kode (dijalankan paralel oleh manusia, bukan agen)

Item ini bukan tugas agen, dicantumkan agar konteks lengkap. Jangan blokir trek kode karenanya.

- **kur_outcomes:** desain mekanisme capture outcome (follow-up user / via AO) + prior cold-start.
  Ayam-telur: tak ada outcome sebelum orang pakai & melapor. Yang bisa diputuskan sekarang adalah
  **cara menangkap**-nya, bukan datanya.
- **Kontak AO bank (A2):** lead time terpanjang — validasi apakah skor 4b selaras dengan penilaian bank.
- **Fixture impor (A3):** kumpulkan satu sampel asli (dianonimkan) per format → membuka pemetaan §5 B3.
- **Disclaimer & privasi (UU PDP):** panduan KUR bersinggungan nasihat finansial; impor rekening
  koran menyentuh data keuangan pribadi. Putuskan awal, jauh lebih murah daripada ditambal pra-rilis.

---

## 9. Guardrail — yang JANGAN dilakukan

- ❌ Jangan hardcode tarif/plafon di router. Ambil dari `panduan_entries` yang `aktif`.
- ❌ Jangan menyeragamkan jenjang non-ekspor Mikro dan Kecil (lihat koreksi Lampiran A).
- ❌ Jangan menjawab KUR secara generik "6% flat / bebas frekuensi".
- ❌ Jangan menyimpulkan status "ekspor" sendiri — butuh bukti dokumen.
- ❌ Jangan membangun router C2 sebelum D1 (entri `aktif`) selesai.
- ❌ Jangan menunda test guard/router ke commit berikutnya.
- ❌ Jangan mengimplementasi pemetaan format impor berdasar asumsi (tunggu fixture A3).
- ❌ Jangan menelan kegagalan `simpan_snapshot_hpp` diam-diam.
- ❌ Jangan pakai link `Download/...pdf` sebagai `sumber_url` (rapuh); pakai URL `Details/...`.

---

## Lampiran A — Data regulasi terverifikasi (SOURCE OF TRUTH)

> Diverifikasi manusia langsung dari teks PDF salinan resmi. **Jangan ubah tanpa persetujuan.**
> Regulasi payung: **Permenko 1/2026**, berlaku **13 Januari 2026**, Berita Negara 2026 Nomor 17.
> Status di JDIH BPK: **Berlaku**. Mencabut Permenko 1/2022.
>
> `sumber_url` kanonik:
> `https://peraturan.bpk.go.id/Details/342969/permenko-perekonomian-no-1-tahun-2026`

### A.1 Tarif Suku Bunga/Marjin per jenis KUR × sektor

| Jenis KUR | Kondisi | Tarif efektif/tahun | Pasal |
|---|---|---|---|
| Super Mikro | tanpa membedakan sektor | 3% | Pasal 30 |
| Mikro | Produksi / perdagangan **ekspor** | 6% | Pasal 37 (1) a |
| Mikro | Perdagangan **non-ekspor**, akad ke-1 | 6% | Pasal 37 (1) b.1 |
| Mikro | Perdagangan **non-ekspor**, akad ke-2 | 7% | Pasal 37 (1) b.2 |
| Kecil | Produksi / perdagangan **ekspor** | 6% | Pasal 44 (1) a |
| Kecil | Perdagangan **non-ekspor**, akad ke-1 | 6% | Pasal 44 (1) b.1 |
| Kecil | Perdagangan **non-ekspor**, akad ke-2 | 7% | Pasal 44 (1) b.2 |
| Kecil | Perdagangan **non-ekspor**, akad ke-3 | 8% | Pasal 44 (1) b.3 |
| Kecil | Perdagangan **non-ekspor**, akad ke-4 | 9% | Pasal 44 (1) b.4 |
| Khusus | flat | 6% | Pasal 51 (1) |
| Penempatan PMI | flat | 6% | Pasal 58 (1) |

### A.2 ⚠️ KOREKSI load-bearing

Catatan lama menulis "perdagangan non-ekspor tetap berjenjang 6→7→8→9%". **Itu benar HANYA
untuk KUR Kecil.** Untuk **KUR Mikro** non-ekspor, jenjangnya cuma **6→7%** dan **dibatasi 2 akad**
(Pasal 36 (3) b + Pasal 37 (1) b). Menyeragamkan keduanya = kesalahan. Entri harus dipecah per
`jenis_kur × sektor`.

### A.3 Larangan agunan (DUA pasal terpisah)

| Ketentuan | Isi | Pasal |
|---|---|---|
| Larangan | Plafon ≤ Rp100 juta: Penyalur **tidak boleh** mensyaratkan agunan tambahan | Pasal 20 (1) |
| Pengecualian | Petani tebu rakyat & KUR khusus pertanian dgn offtaker avalis (untuk >Rp100jt) | Pasal 20 (2) |
| Sanksi | Bila dilanggar: Subsidi Bunga/Marjin **tidak dibayarkan** | Pasal 21 (1) |
| Pengembalian | Bila subsidi sudah diterima: **dikembalikan ke kas negara** | Pasal 21 (2) |

### A.4 Definisi sektor

- **Sektor Produksi** — definisi eksplisit **Pasal 1 angka 2**: kegiatan ekonomi yang menghasilkan
  barang/jasa **di luar sektor perdagangan**. Daftar sektor prioritas: **Pasal 24 (2)**.
- **Perdagangan berorientasi ekspor** — **tidak ada definisi pasal tersendiri.** Bersifat pembuktian:
  dibuktikan Penerima KUR dengan **dokumen proses ekspor dari kementerian/instansi terkait**
  (Mikro: Pasal 36 (3) a; Kecil: Pasal 43 (3) a; Khusus: Pasal 50 (3) a). **Bukan atribut yang boleh diasumsikan.**

### A.5 Frekuensi & akumulasi akad

| Jenis / sektor | Frekuensi | Akumulasi | Pasal |
|---|---|---|---|
| Super mikro | tanpa batas | tanpa batas | Pasal 29 (3) |
| Mikro produksi/ekspor | tanpa batas | tanpa batas | Pasal 36 (3) a |
| Mikro non-ekspor | **maks 2 akad** | tanpa batas | Pasal 36 (3) b |
| Kecil produksi/ekspor | tanpa batas | tanpa batas | Pasal 43 (3) a |
| Kecil non-ekspor | tak dibatasi | **maks Rp500jt (termasuk dari KUR mikro)** | Pasal 43 (3) b |

### A.6 Plafon per jenis KUR

| Jenis KUR | Plafon per akad | Pasal |
|---|---|---|
| Super Mikro | ≤ Rp10 juta | Pasal 29 (1) |
| Mikro | > Rp10 juta s.d. Rp100 juta | Pasal 36 (1) |
| Kecil | > Rp100 juta s.d. Rp500 juta | Pasal 43 (1) |
| Khusus | ≤ Rp500 juta | Pasal 50 (1) |
| Penempatan PMI | ≤ Rp100 juta | Pasal 57 (1) |

### A.7 Suku bunga graduasi/naik kelas (lapisan tambahan di atas tabel dasar)

- Graduasi **Super Mikro → Mikro**: akad awal Mikro diperlakukan sebagai **akad pertama** →
  tarif per Pasal 37 (1) a atau b.1 — **Pasal 37 (2)**.
- Graduasi **Super Mikro → Kecil**: akad awal Kecil = akad pertama Kecil → Pasal 44 (1) a atau b.1
  — **Pasal 44 (2)**.
- Graduasi **Mikro → Kecil**:
  - Produksi/ekspor: 6% — **Pasal 44 (3) a**.
  - Non-ekspor: **1% lebih tinggi dari marjin terakhir di KUR mikro** — **Pasal 44 (3) b**;
    akad berikutnya +1% tiap akad, **maks 9%** — **Pasal 44 (4)**.
- Non-ekspor kembali ke **produksi/ekspor**: turun ke 6% — **Pasal 44 (5)**.

---

## Lampiran B — Referensi artefak yang sudah ada

- `docs/regulasi/2026PemenkoEkon001.pdf` — **teks asli lengkap** Permenko 1/2026 (salinan resmi,
  Berita Negara 2026 Nomor 17). Bukan sumber utama — **Lampiran A tetap yang utama** untuk fakta
  yang sudah dikunci. Ini jaring pengaman: baca hanya bila butuh ketentuan yang tidak tercakup
  Lampiran A (lihat §0 aturan 1). Jangan salin ulang angka dari sini ke `panduan_entries` tanpa
  mencocokkan dengan Lampiran A; bila keduanya berbeda, **berhenti dan tanya manusia** — jangan
  putuskan sendiri mana yang benar.
- `docs/checklist-verifikasi-bunga-kur.md` — checklist gerbang verifikasi (A1). **Sudah tuntas.**
- `SPEC_GUARD_4C.md` — spesifikasi guard.
- `app/services/panduan_kur.py` — implementasi guard 4c (18 test, lolos). Belum di-wire (§7 C1).

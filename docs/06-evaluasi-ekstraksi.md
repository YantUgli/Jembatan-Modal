# Evaluasi ekstraksi — Groq `llama-3.3-70b-versatile`

Dijalankan 2026-07-19 terhadap `evaluasi/ekstraksi.json` (40 kasus, tanggal acuan
dipatok 2026-06-10 agar bisa direproduksi).

    pipenv run python -m app.llm.evaluasi [--saring <id>] [--ulang N]

## Hasil jalan pertama (prompt awal)

| ukuran | hasil |
|---|---|
| inti (jenis + nominal + tanggal) | 35/40 = **88%** |
| rinci (produk + qty + satuan) | 32/40 = 80% |
| tahu-diri (harus `Gagal`) | 8/10 |

Dipisah dua angka dengan sengaja: salah di **inti** berarti angka laporan salah;
salah di **rinci** cuma membuat HPP kurang lengkap, laba periode tetap benar.

## Yang ditemukan

**1. Model berhitung sendiri — pelanggaran aturan #1 di lapisan input.**
"laku 5 kotak risol 75rb" → nominal **375.000** (5 × 75rb) alih-alih 75.000.
Aturan #1 selama ini kita tegakkan di sisi *narasi* (`angka_asing`). Ternyata
lubangnya ada di sisi *ekstraksi*: angka hasil kalkulasi model masuk ke database
sebagai fakta, dan setelah itu setiap laporan di atasnya salah tanpa jejak.
Penjaga narasi tidak akan pernah menangkapnya — angkanya memang "ada di fakta".

**2. Model mengarang takaran.** "kemarin beli ayam 200rb" → `qty=1, satuan=ekor`.
"beli sayur buat masak di rumah 60rb" → `qty=1, satuan=takaran`. Tidak ada
takaran yang diucapkan. Karangan ini akan dipakai menghitung modal per porsi.

**3. Batas kategori operasional kabur.** Kemasan (plastik, karet), gas, dan upah
karyawan dijawab `pengeluaran` — padahal bukan barang dagangan. Akibatnya HPP
dan laba sama-sama meleset ke arah berlawanan.

**4. Uang keluar tanpa tujuan ditebak.** "keluar 50rb" → `pengeluaran`, padahal
bisa bahan, biaya warung, atau prive.

## Perbaikan yang diterapkan

Prompt (`app/llm/skema.py`): larangan berhitung yang eksplisit + contoh
tandingannya; larangan mengisi takaran yang tidak diucapkan; daftar operasional
diperjelas + uji cepat "ikut dijual atau habis dipakai?"; setoran/tarikan bank
disamakan dengan cicilan utang (memindahkan uang, bukan untung-rugi).

Penilai (`app/llm/evaluasi.py`) — dua koreksi terhadap penilaian saya sendiri:
- `produk` dilonggarkan. `produk='listrik'` untuk "bayar listrik" tidak merugikan
  siapa pun; menghukumnya cuma menghasilkan angka yang terlihat buruk tanpa
  sebab.
- Daftar baris **kosong** untuk kalimat seperti "hari ini rame banget" tidak lagi
  dihitung sebagai menebak. Itu bentuk lain dari mengaku tidak tahu.

## Jalan kedua — belum tuntas (kuota harian habis)

26 dari 40 kasus sempat jalan sebelum Groq menolak: **TPD 100.000 token/hari**,
satu evaluasi penuh ±60.000. Artinya **maksimal satu setengah evaluasi per hari**
di tier gratis — ini membatasi ritme kerja, bukan cuma angka di dokumentasi.

Yang **membaik**: perkalian di "laku 5 kotak risol 75rb" hilang; gaji karyawan →
`operasional`; sewa lapak tidak lagi berqty karangan.

Yang **memburuk** — dan ini pelajarannya:
- "jual 2,5 kg ayam 90rb" → **225.000** (2,5 × 90rb). Perkalian yang sama muncul
  lagi di kalimat lain. Larangan eksplisit menutup contoh yang disebut, bukan
  perilakunya.
- "laku 3 lusin 180rb" → qty & satuan dikosongkan, padahal **diucapkan**.
  Larangan mengarang takaran ditarik terlalu jauh.
- Kemasan & gas tetap `pengeluaran` walau daftarnya sudah eksplisit.

Prompt di ukuran model ini berperilaku seperti jungkat-jungkit: menekan satu
sisi mengangkat sisi lain. Itu sinyal bahwa perbaikan berikutnya **bukan**
kalimat prompt yang lebih panjang.

## Qwen `qwen3.6-flash` — 2026-07-19/20

Pindah provider Groq → Qwen: **nol baris kode berubah**, hanya tiga baris `.env`.
Klaim provider-agnostic terbukti pada provider kedua yang sungguhan.

| ukuran | Groq llama-3.3-70b | Qwen qwen3.6-flash |
|---|---|---|
| inti | 88% | **98%** |
| rinci | 80% | **100%** |
| tahu-diri | 8/10 | **10/10** |

Jalan pertama Qwen 40/40 mutlak — dan itu **tidak dipercaya**: prompt baru saja
dikeraskan di atas kasus-kasus ini setelah melihat Groq gagal, jadi ada bau
overfitting, dan satu jalan tidak mengukur kestabilan. Uji `--ulang 3`
menurunkannya ke 98%, dengan dua kasus goyah. Skor sekarang memakai **jalan
terburuk** tiap kasus: pengguna mengetik sekali, "pernah benar" tak berarti.

**Goyah #1 — `multi-jual-beli` (4/5 benar).** "beli minyak 38rb" kadang
`pengeluaran`, kadang `operasional`. Suhu sudah 0.0 dan tetap goyah. Sebagian
memang ambiguitas nyata: minyak goreng untuk dagangan vs minyak untuk kompor.
Kategori `jenis` adalah field yang paling menentukan laba — ini risiko yang
harus ditangani produk (konfirmasi ke pengguna), bukan diharapkan hilang.

**Goyah #2 — `waktu-tadi-pagi` (sudah hilang setelah diperbaiki).** Model mengisi
`satuan: ""` alih-alih
menghilangkan field-nya. Ini **bukan** kelemahan model melainkan celah kontrak:
`bangun()` menerima string kosong sebagai nilai sah. Di database `''` tampak
seperti data padahal bukan, dan setiap pemeriksaan "belum diketahui" akan
melewatinya diam-diam — persis jenis kebocoran yang aturan #2 ada untuk
mencegah. Diperbaiki: string kosong/spasi → `None` bila opsional, ditolak bila
wajib.

**Jalan pemastian setelah perbaikan** (`--ulang 3`, penilaian jalan terburuk):
inti 39/40 = 98%, rinci **40/40 = 100%**, tahu-diri 10/10. Kegoyahan `satuan: ""`
hilang sepenuhnya — dan kali ini 100% rinci bertahan di jalan terburuk, bukan
angka rapuh dari satu jalan. Sisa satu kasus goyah: `multi-jual-beli` (2/3),
ambiguitas "minyak" di atas.

### Bug infrastruktur yang tertangkap oleh evaluasi ini

- **Pemuat `.env` first-wins.** `.env` dengan dua blok provider menghasilkan
  `base_url` provider lama + `api_key` provider baru → 401 yang menuduh kunci,
  padahal berkasnya yang dibaca terbalik. Sekarang last-wins (seperti dotenv).
- **`TimeoutError` saat membaca jawaban tidak terbungkus `URLError`**, jadi lolos
  dari penangkap dan mematikan evaluasi 120 permintaan dengan stack trace.
  Sekarang diperlakukan sebagai gangguan sesaat dan diulang.

## Langkah berikutnya

1. **Pindahkan larangan berhitung dari prompt ke kode.** Aturan #1 mengatakan
   LLM tidak pernah menghitung; menaruh jaminannya di prompt sama dengan
   berharap. Kalau kalimat memuat qty dan nominal, dan `nominal == qty × angka
   lain yang ada di kalimat`, itu terdeteksi secara deterministik → tolak.
   Ini penjaga sisi-input yang sepadan dengan `angka_asing` di sisi keluaran.
2. **Bandingkan Qwen** pada set yang sama sebelum menambah kalimat prompt lagi.
   Kategori (#3) dan takaran (#2) berbau keterbatasan ukuran model.
3. Tambah kasus untuk yang belum tersentuh: harga satuan disebut tapi total
   tidak, kalimat campur bahasa daerah, angka bertitik ("15.000").

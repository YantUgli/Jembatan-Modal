# Keputusan — JembatanModal

> Log keputusan strategis (append-only). Entri terbaru di atas.
> Format: **tanggal — judul** · Konteks · Keputusan · Alasan · Konsekuensi.

---

## 2026-07-28 — Topik agunan KUR: entri kedua yang seed langsung aktif — pengecualian, bukan preseden (E2)

- **Konteks:** `docs/plan-lanjutan.md` §E2 minta topik `agunan` ditambah ke asisten
  KUR, memakai data yang sudah terverifikasi manusia (Lampiran A.3
  `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`, dicocokkan ke
  `docs/regulasi/2026PemenkoEkon001.pdf`): larangan agunan tambahan untuk plafon
  ≤Rp100 juta (Pasal 20 (1)), pengecualian petani tebu/KUR khusus pertanian
  (Pasal 20 (2)), dan sanksi subsidi tak dibayar/dikembalikan bila dilanggar
  (Pasal 21 (1)/(2)). Ini entri KUR **kedua** (setelah bunga, D1 2026-07-28) yang
  masuk `panduan_entries` — dan kedua-duanya melewati gerbang `draft` langsung ke
  `aktif`, yang bisa salah dibaca sebagai "begini caranya menambah topik KUR".

- **Keputusan:**
  1. `app/seeds/panduan_kur_agunan.py` (baru) — satu entri overview
     (`pertanyaan_kanonik="Apakah KUR butuh agunan tambahan?"`), `status=aktif`
     langsung, `pasal_rujukan="Pasal 20 (1); Pasal 20 (2); Pasal 21 (1); Pasal 21 (2)"`,
     `sumber_url` sama dengan bunga (regulasi payung sama, Permenko 1/2026). Upsert
     per `pertanyaan_kanonik`, pola identik `panduan_kur_bunga.seed()`.
  2. `kartu_panduan_kur` (`app/kanal/orkestrator.py`) diperluas menerima
     `topik: str = "bunga"` (keyword-only, kompatibel mundur — pemanggil lama yang
     hanya mengoper `konteks` tak berubah perilakunya). Topik `agunan` tidak
     bercabang kategori/sektor/ekspor sama sekali — langsung `jawab_panduan(session,
     "agunan")` generik, `konteks` diabaikan.
  3. `PesanMasuk` (`app/api/main.py`) dapat slot baru `topik_kur: str | None = None`
     (default `"bunga"`). Nilai di luar `_TOPIK_KUR_DIKENAL = {"bunga", "agunan"}` →
     422 — pola yang sama dengan `jenis_kur`/`sektor_usaha`, tak pernah jatuh diam-diam
     ke topik default. **Ini slot eksplisit baru, bukan label `AksiRouter` baru** —
     konsisten dengan keputusan 2026-07-22/2026-07-27/2026-07-28 (tanya_kur).
  4. ⚠️ **Sengaja plafon-agnostik.** Entri ini menjawab aturan agunan secara umum,
     bukan pertanyaan bernominal ("saya mau pinjam 200 juta, butuh agunan tidak?").
     Menjawabnya butuh guard membaca nominal plafon dari input pengguna dan
     membandingkannya ke ambang Rp100 juta — **belum dibangun**. Follow-up bernama:
     **F2 — jawaban agunan plafon-kondisional**, ditahan sampai ada slot eksplisit
     nominal plafon (bukan diekstrak dari kalimat bebas, mengikuti pola yang sama
     dengan `berorientasi_ekspor`) dan keputusan bagaimana ambang dibandingkan tanpa
     LLM melakukan aritmatika (aturan #1).
  5. **`status=aktif` langsung untuk topik `agunan` adalah pengecualian spesifik ke
     data ini, BUKAN preseden umum.** Topik KUR berikutnya (mis. plafon per jenis
     KUR, syarat calon penerima, restrukturisasi) **tetap default lewat gerbang
     `draft` → verifikasi manusia → `aktif`** (pola 2026-07-27: `StatusPanduan.draft`
     + checklist verifikasi), **kecuali** datanya sudah diverifikasi manusia dengan
     cara yang sama persis seperti bunga & agunan di sini (dicocokkan ke Lampiran A
     rencana eksekusi **dan** teks resmi PDF). Gerbang draft→aktif itu
     load-bearing (aturan #4) — tidak boleh tergerus jadi kebiasaan "seed langsung
     aktif karena yang sebelumnya begitu".

- **Alasan:** butir 1-3 mengikuti pola guard generik yang sudah ada
  (`jawab_panduan`) dan pola slot eksplisit `tanya_kur` yang sudah divalidasi
  (2026-07-28 C1+C2) — agunan tidak butuh dataclass konteks baru karena aturannya
  tidak bercabang kategori/sektor, hanya bercabang plafon (butir 4 justru
  menandai cabang itu sebagai belum digarap, bukan diam-diam diabaikan). Butir 5
  eksplisit karena tanpa penanda ini, sesi berikutnya bisa membaca "bunga & agunan
  langsung aktif" sebagai kebiasaan yang sah, padahal keduanya aktif **karena**
  sudah lolos verifikasi manusia ganda (Lampiran A + PDF resmi) — bukan karena
  jalur cepatnya nyaman. Melonggarkan gerbang draft→aktif secara diam-diam persis
  jenis erosi yang aturan #4 dirancang mencegah.

- **Konsekuensi:**
  - `pytest tests/test_seed_panduan_kur_agunan.py tests/test_kanal_panduan_kur.py
    tests/test_panduan_kur.py -q` hijau — termasuk regresi eksplisit bahwa
    `tanya_kur` tanpa `topik_kur` tetap berperilaku seperti sebelum E2 (default
    bunga).
  - `KartuPanduanKur`/`VERSI_KONTRAK` tidak berubah — kartu agunan memakai bentuk
    kartu yang sama dengan bunga, tak ada field baru.
  - F2 (agunan plafon-kondisional) dicatat sebagai item terbuka di
    `docs/plan-lanjutan.md` bagian "Ditahan", bukan tenggelam sebagai catatan kaki.

---

## 2026-07-28 — Impor CSV generik berhenti di struktur, bukan sampai transaksi (B3)

- **Konteks:** P2 impor (~35%) hanya punya adaptor teks tempelan. Rencana
  eksekusi §5 B3 minta pipa unggah CSV generik dibangun sekarang, tapi
  pemetaan kolom spesifik per format (rekening koran bank, ekspor QRIS/
  e-wallet, CSV pembukuan) **ditahan** sampai ada fixture asli (A3) — kalau
  dipaksakan dari asumsi bentuk berkas, risikonya rework total begitu bentuk
  aslinya ternyata beda.

- **Keputusan:** `app/impor/csv_generik.py` dibangun sampai batas **struktur**
  saja: `baca_csv_generik` memvalidasi berkas (ekstensi `.csv`, ukuran ≤5MB,
  isi tidak kosong), mendeteksi encoding (`utf-8-sig`→`utf-8`→`cp1252`→
  `latin-1` sebagai jaring terakhir yang tak pernah gagal), mendeteksi
  pemisah kolom (`csv.Sniffer` + fallback hitung-konsistensi), dan mendeteksi
  baris header (`csv.Sniffer.has_header` + fallback asumsikan-ada-header).
  Titik pemetaan kolom→`BarisTransaksi` ada sebagai `petakan_baris_generik`
  yang sengaja melempar `NotImplementedError` menyebut fixture A3 — bukan
  diam-diam menebak. `angka_rupiah()` (`app/services/angka.py`) ditambahkan
  terpisah: parser angka gaya Indonesia (titik=ribuan, koma=desimal) yang
  dibutuhkan begitu pemetaan kolom akhirnya ditulis.
  Wiring ke endpoint HTTP unggah (`UploadFile`) **belum** dibuat — butuh
  dependency baru `python-multipart` yang belum terpasang; ini murni lapisan
  layanan (`baca_csv_generik(nama_berkas, data: bytes)`) yang teruji tanpa
  FastAPI sama sekali.

- **Alasan:** Struktur berkas (encoding/pemisah/header) tidak butuh tahu
  formatnya — itu bisa dibangun & diuji sekarang dengan percaya diri. Memetakan
  kolom BUTUH tahu formatnya, dan setiap sumber (bank/e-wallet/pembukuan
  manual) punya kolom yang beda tempat & beda nama. `docs/02-arsitektur.md`
  membayangkan pemetaan ini lewat LLM (kolom bebas → skema kita), bukan aturan
  hardcode per-platform — tapi menulis logika itu pun dari asumsi berisiko
  sama seperti menulis aturan hardcode dari asumsi: keduanya bisa salah kalau
  fixture aslinya ternyata beda bentuk.

- **Konsekuensi:**
  - `pytest tests/test_impor_csv_generik.py tests/test_angka_rupiah.py -q`
    hijau (32 test) — termasuk kasus encoding non-UTF-8, pemisah `;`/tab,
    baris tanpa header, baris ragged, dan tabel kasus angka Rupiah lengkap.
  - `parser_untuk()` (`app/tools/impor.py`) **belum** menerima sumber `"csv"`
    — CSV belum bisa masuk ke alur draft/`import_rows` sampai
    `petakan_baris_generik` diimplementasikan pasca-A3.
  - Endpoint HTTP unggah menyusul terpisah begitu ada konsumen nyata
    (pemetaan) untuk hasilnya — membangunnya sekarang hanya akan jadi
    permukaan API yang menganggur.

---

## 2026-07-28 — Asisten KUR (4c) slice pertama: `tanya_kur` aksi terstruktur, guard wired (C1+C2)

- **Konteks:** D1 (di bawah) menaikkan entri bunga KUR ke `aktif`, jadi router
  4c yang menjawabnya jadi bermakna untuk pertama kali. Belum ada satu jalur
  pun (router, tool, endpoint) yang memanggil `jawab_bunga_kur` — guard aturan
  #4 (`app/services/panduan_kur.py`) sudah teruji sendirian sejak 2026-07-27
  tapi tidak terhubung ke pengguna sama sekali.

- **Keputusan:** Dibangun sebagai **aksi terstruktur** `tanya_kur` di `/chat`
  (`app/api/main.py`) — persis pola `tanya_skor` (2026-07-22/2026-07-27), BUKAN
  label baru di `AksiRouter`. Klien mengirim `jenis_kur`/`sektor_usaha`/
  `berorientasi_ekspor` sebagai slot eksplisit (mirip chip), bukan kalimat
  bebas yang diekstrak LLM. Orkestrator dapat fungsi baru `kartu_panduan_kur`
  yang memanggil `jawab_bunga_kur` (satu-satunya jalan ke isi) lalu memetakan
  `Penolakan` → `KartuKlarifikasi` atau `JawabanTerkutip` → kartu baru
  `KartuPanduanKur` (`app/kanal/kontrak.py`, `VERSI_KONTRAK` 9→10).

- **Alasan:** Menambah label ketujuh ke `AksiRouter` mengulang risiko yang
  sudah dua kali dicatat (2026-07-22 untuk router intent bahasa-bebas,
  2026-07-27 untuk `tanya_skor`) — prompt "jungkat-jungkit" akurasi di ukuran
  model ini belum diukur untuk domain KUR sama sekali, dan `04-rencana-kerja.md`
  §4c sendiri menempatkan ekstraksi bahasa-bebas (wawancara multi-turn,
  `kur_interviews`) sebagai pekerjaan **terpisah** dari slice ini — membangun
  keduanya sekaligus akan mencampur dua keputusan yang belum siap diukur
  sendiri-sendiri. Slot eksplisit juga menegakkan aturan A.4 rencana eksekusi
  secara struktural: `berorientasi_ekspor` **tidak bisa** disimpulkan kode
  karena field-nya memang harus diisi eksplisit oleh klien — tak ada kode yang
  membaca kata "ekspor" dari kalimat dan menebak niat penggunanya.

- **Konsekuensi:**
  - `pytest tests/test_kanal_panduan_kur.py -q` (17 test) mengunci: guard
    menolak draft (C1), tiap kombinasi jenis KUR × sektor menjawab tarif
    Lampiran A dengan `pasal_rujukan` + `sumber_url` (C2), konteks kosong/
    parsial selalu klarifikasi, disclaimer selalu ada.
  - `VERSI_KONTRAK` naik ke 10 — tiga test lain yang mengunci angka versi
    literal (`test_kanal_untung_keuangan.py`, `test_api_dokumen.py`,
    `test_api_impor.py`) diperbarui mengikuti.
  - Alur wawancara multi-turn (`kur_interviews`), `susun_dokumen_kur`, dan
    `panduan_perizinan` (04-rencana-kerja.md §4c) **belum** digarap — slice ini
    murni Q&A tarif dari `panduan_entries`, bukan penyusunan dokumen KUR.
  - Topik `agunan` (Pasal 20/21) belum punya entri sama sekali; guard/handler
    di sini hanya menjangkau topik `bunga`.

---

## 2026-07-28 — Bunga KUR draft → aktif; `KategoriKur` pecah Mikro/Kecil (D1)

- **Konteks:** Verifikasi A1 (teks Permenko 1/2026, `docs/regulasi/2026PemenkoEkon001.pdf`)
  selesai — nomor pasal, tarif, dan `sumber_url` final terkonfirmasi manusia
  (lihat rencana eksekusi Lampiran A). Ini gerbang pertama dari dua gerbang
  yang menahan asisten KUR (4c): entri `panduan_entries` topik `bunga` boleh
  naik dari `draft` ke `aktif`.

- **Keputusan:** Seed `app/seeds/panduan_kur_bunga.py` ditulis ulang dari 4
  entri jadi 8 — dipecah per **jenis KUR × sektor**, bukan sektor saja.
  `KategoriKur` di `app/services/panduan_kur.py` pecah `mikro_kecil` (satu
  nilai gabungan) jadi `mikro`/`kecil` terpisah, plus `khusus`/`pmi` baru.
  Semua 8 entri `status=aktif`, `sumber_url` = URL `Details/...` BPK (bukan
  placeholder). Seed diubah dari "skip bila versi sudah ada" jadi upsert per
  `pertanyaan_kanonik`, supaya database yang sudah kadung menyimpan draft lama
  ikut ter-upgrade saat seed dijalankan ulang, bukan diam-diam dilewati.

- **Alasan:** Draft lama menulis "perdagangan non-ekspor tetap berjenjang
  6-7-8-9%" sebagai aturan umum Mikro **dan** Kecil. Teks resmi membedakan:
  KUR Mikro non-ekspor berjenjang 6%→7% dan dibatasi **maksimal 2 akad**
  (Pasal 37 (1) b + Pasal 36 (3) b); KUR Kecil non-ekspor berjenjang
  6→7→8→9% dengan akumulasi plafon maksimal Rp500 juta (Pasal 44 (1) b +
  Pasal 43 (3) b). Menyeragamkan keduanya di satu entri/kategori enum akan
  memberi pengguna KUR Mikro info batas akad yang salah (Kecil tak dibatasi
  frekuensi, hanya akumulasi plafon) — persis kesalahan yang guard 4c
  (`_layak_jawab`/`pilih_jawaban`) dirancang untuk dicegah di lapisan
  kelayakan, tapi tidak bisa dicegah bila datanya sendiri sudah salah pecah.
  Khusus dan PMI ditambahkan karena keduanya ada di Lampiran A tapi belum
  punya entri sama sekali di seed lama.

- **Konsekuensi:**
  - `pytest tests/test_panduan_kur.py tests/test_seed_panduan_kur_bunga.py -q`
    hijau (33 test) — termasuk test baru yang mengunci Mikro≠Kecil non-ekspor
    dan Khusus/PMI tak butuh sektor.
  - Topik `agunan` (larangan agunan tambahan Pasal 20, sanksi Pasal 21) belum
    digarap di slice ini — di luar cakupan "bunga" yang diminta D1.
  - Router 4c (§7 rencana eksekusi) sekarang **unblocked**: ada entri `aktif`
    untuk dikutip. Belum dibangun — itu tugas terpisah (C1/C2).
  - `docs/checklist-verifikasi-bunga-kur.md` diperbarui jadi catatan riwayat
    (checklist tercentang), bukan lagi daftar kerja terbuka.

---

## 2026-07-27 — Guard aturan #4 (`app/services/panduan_kur.py`), sebelum router 4c ditulis

- **Konteks:** `SPEC_GUARD_4C.md` (dokumen kontrak dari pengguna) meminta guard
  eksplisit — titik tunggal yang memutuskan apakah sebuah `panduan_entries`
  layak dipakai menjawab pengguna — didesain & diuji **sebelum** baris kode
  router 4c pertama ditulis, supaya penegakan aturan #4 tidak bisa "menyusul"
  dan bocor lewat celah baru. 4c sendiri (`susun_dokumen_kur`,
  `panduan_perizinan`, wawancara multi-turn) masih sepenuhnya `[ ]` di
  `docs/04-rencana-kerja.md` Tahap 4c — belum ada router, tool, atau
  orchestrator yang memanggil guard ini.
- **Keputusan:**
  1. Guard generik (`pilih_jawaban`/`jawab_panduan`): entri layak-jawab
     hanya bila `status=aktif` **dan** `tingkat_sumber ∈ {resmi_regulasi,
     resmi_bank}` **dan** `sumber_url` terisi. Tak ada kandidat layak →
     `Penolakan` (string kode/template, bukan generasi LLM) — tidak pernah
     turun ke kandidat tak-layak yang paling mirip. Satu-satunya jalan ke
     `JawabanTerkutip` (union type, bukan string bebas) adalah fungsi ini —
     mencegah jalur bypass yang lewat guard.
  2. Guard topik bunga (`jawab_bunga_kur` + `KonteksBunga`): sebelum kategori
     (Super Mikro / Mikro-Kecil), lalu sektor (produksi/perdagangan), lalu
     orientasi ekspor diketahui, guard menolak dengan permintaan klarifikasi
     — tidak pernah mengutip `bunga-overview` sebagai jawaban final. Routing
     ke entri spesifik memakai `pertanyaan_kanonik` yang sama persis dengan
     yang di-seed `app/seeds/panduan_kur_bunga.py` (konstanta diekspor dari
     sana — satu-satunya sumber kebenaran teksnya, bukan disalin ulang).
  3. 12 test di `tests/test_panduan_kur.py`, dipetakan langsung ke invariant
     I1–I7 & acceptance criteria AC1–AC11 di `SPEC_GUARD_4C.md` §6 (nama test
     mengikuti tabel itu). Termasuk sentinel `test_guard_tanpa_jalur_bypass`
     (I1) dan skenario adversarial yang memakai **state DB nyata**: keempat
     entri bunga hasil `panduan_kur_bunga.seed()` masih `status=draft` hari
     ini, jadi guard menolak walau konteks sektor lengkap — bukti langsung
     bahwa belum ada jalur "menyerah lalu menjawab saja".
- **Alasan:** `SPEC_GUARD_4C.md` §7 eksplisit — guard menegakkan *kelayakan*
  entri, bukan *kebenaran faktual*-nya (itu tetap tugas manusia lewat
  `docs/checklist-verifikasi-bunga-kur.md`). Menulis & menguji guard sebagai
  unit terpisah dari router memungkinkan kontraknya diverifikasi sekarang,
  sebelum ada tekanan untuk "sementara" melewatinya saat router akhirnya
  digarap.
- **Konsekuensi:** file baru `app/services/panduan_kur.py`,
  `tests/test_panduan_kur.py`; `app/seeds/panduan_kur_bunga.py` diperluas
  (konstanta `PERTANYAAN_*` diekspor, isi tak berubah). Tidak ada perubahan
  skema/migrasi — guard murni service-layer di atas `panduan_entries` yang
  sudah ada. Guard ini **belum tersambung ke jalur produksi mana pun** (belum
  ada tool/router KUR yang memanggilnya) — itu menyusul saat 4c digarap
  sungguhan, dan `SPEC_GUARD_4C.md` §8 mensyaratkan guard + router + testnya
  mendarat di commit yang sama saat itu terjadi. Juga membetulkan
  `import sqlalchemy as sa` yang tak terpakai di migrasi
  `d60152fe10b2` (luput dari `ruff check` sesi sebelumnya).

---

## 2026-07-27 — `StatusPanduan.draft` + seed draft bunga KUR (belum boleh dijawab)

- **Konteks:** lanjutan keputusan di bawah ini (perluasan skema
  `panduan_entries`). Draf isi bunga KUR (4 entri: overview/dispatcher +
  3 spesifik-sektor — super mikro, produksi/ekspor, perdagangan non-ekspor)
  disusun dari riset sekunder yang sama, **belum** dari pasal Permenko 1/2026
  langsung. `StatusPanduan` saat itu cuma `aktif|superseded` — tak ada tempat
  menyimpan "isi ada, tapi belum dicek ke pasal resmi" selain `aktif` (salah,
  karena aturan #4 mewajibkan hanya entri terverifikasi yang boleh menjawab)
  atau tidak menyimpannya sama sekali (hilang, padahal riset ini bahan kerja
  nyata untuk verifikasi manual berikutnya).

- **Keputusan:**
  1. Tambah `StatusPanduan.draft` — pola identik `StatusImpor.draft` &
     `StatusBarisImpor.draft` yang sudah ada (isi tersimpan, guard menolak
     menjawab dari status ini persis seperti `tingkat_sumber=lainnya`).
     Migrasi `d60152fe10b2`: no-op di SQLite (enum tersimpan VARCHAR tanpa
     CHECK constraint — autogenerate tak mendeteksi diff), tapi
     `ALTER TYPE ... ADD VALUE` eksplisit untuk Postgres (target produksi).
     Downgrade Postgres sengaja tak didukung (butuh rebuild tipe penuh; belum
     ada database produksi nyata yang butuh ini).
  2. Empat entri draft di-seed via `app/seeds/panduan_kur_bunga.py`
     (`topik="bunga"`, `status=draft`, `tingkat_sumber=resmi_regulasi`,
     `sumber_url` masih placeholder). Checklist promosi draft→aktif per entri
     ada di `docs/checklist-verifikasi-bunga-kur.md`.

- **Alasan:** menyimpan riset sekunder sebagai `draft` (bukan `aktif` atau
  dibuang) membuatnya jadi bahan kerja terstruktur untuk verifikasi manual
  berikutnya, sambil skema tetap menegakkan aturan #4 secara struktural — tak
  ada jalur bagi entri belum-terverifikasi untuk "bocor" ke jawaban pengguna
  begitu guard service-layer ditulis di 4c.

- **Konsekuensi:**
  - `app/models/base.py` (`StatusPanduan.draft`), migrasi
    `d60152fe10b2_tambah_status_draft_ke_panduan_entries.py`,
    `app/seeds/panduan_kur_bunga.py` (baru), `docs/checklist-verifikasi-bunga-kur.md`
    (baru), `tests/test_panduan_entries.py` +
    `tests/test_seed_panduan_kur_bunga.py` (baru).
  - `panduan_entries` sekarang punya 4 baris, semuanya `status=draft` — masih
    nol baris `aktif`. Guard service-layer aturan #4 tetap belum ditulis (lih.
    keputusan di bawah, poin 4) — menunggu 4c.

---

## 2026-07-27 — `panduan_entries` diperluas sebelum 4c digarap (asuransi skema)

- **Konteks:** cross-check terhadap `panduan_entries` & fitur "asisten KUR (4c)"
  (dipicu dokumen investigasi eksternal soal fakta KUR usang) menemukan bahwa
  **4c belum digarap sama sekali** — `04-rencana-kerja.md` §4c seluruhnya
  `[ ]`, `git log --all` tak pernah menyentuh kode KUR, dan `PanduanEntry` cuma
  model ORM kosong tanpa tool/router/seed. `KurOutcome` juga tak punya tautan
  ke `panduan_entries` sama sekali. Karena fiturnya belum ada, audit "temuan vs
  perbaikan" jadi kurang relevan — momen yang tepat justru mengunci skema
  sebelum baris kode 4c pertama ditulis, pola yang sama dengan keputusan
  2026-07-17 (primitif biaya).

  Validasi web (WebSearch/WebFetch) mengonfirmasi regulasi payung: Permenko
  1/2026 berlaku 13 Januari 2026, mencabut rezim sebelumnya. Tapi bunga "flat
  6%" tampaknya **bersyarat sektor** (produksi & perdagangan ekspor) — sumber
  sekunder soal perdagangan non-ekspor (KUR Kecil) berbeda-beda, sebagian
  menyebut skema berjenjang 6→9% masih berlaku untuk segmen itu. **Belum
  dikonfirmasi ke teks pasal resmi** — lih. pertanyaan terbuka di bawah.

- **Keputusan:**
  1. `panduan_entries` diperluas ke skema target: `pertanyaan_kanonik`,
     `tingkat_sumber` (enum `resmi_regulasi|resmi_bank|lainnya`, WAJIB),
     `versi_regulasi`, `pasal_rujukan`, `tanggal_berlaku`, `tanggal_tinjau`
     (menggantikan `berlaku_sampai` — nama lama ambigu antara "kapan regulasi
     kadaluarsa" dan "kapan tim wajib mengecek ulang"; disepakati satu makna:
     kapan wajib ditinjau), `status` (enum `aktif|superseded`, default
     `aktif`), `digantikan_oleh` (self-FK, nullable). `topik` **tetap** String
     bebas — konvensi repo (`base.py`) sengaja tidak meng-enum-kan field yang
     daftarnya tumbuh, dan itu tidak dicabut oleh keputusan ini.
  2. `kur_outcomes.panduan_entry_id` (nullable FK → `panduan_entries.id`)
     ditambahkan — menutup gap "outcome tak bisa ditelusuri ke panduan yang
     berlaku saat pengajuan terjadi", prasyarat kalibrasi per-versi-regulasi.
  3. Entri `superseded` **tidak pernah dihapus** — hanya `status` berubah +
     `digantikan_oleh` diisi. Ini bahan audit & kalibrasi `kur_outcomes`
     historis dengan aturan yang berlaku saat pengajuan itu terjadi.
  4. Guard aturan #4 (`status=aktif AND tingkat_sumber∈{resmi_regulasi,
     resmi_bank}`) **belum ditulis di service layer** — menunggu tool
     `panduan_perizinan`/`susun_dokumen_kur` sungguhan dibangun di 4c, supaya
     guard lahir bersama tool-nya sejak baris pertama, bukan ditambal setelah
     ada celah (pola yang sama dengan pelajaran `dibatalkan_pada` yang lupa
     disaring — 2026-07-20).

- **Alasan:** menambah field ke skema yang belum punya data = migrasi gratis;
  menambahkannya setelah 4c berjalan & `panduan_entries` sudah terisi berarti
  migrasi data + jendela waktu di mana aturan #4 bisa dilanggar tanpa kolom
  untuk menegakkannya (`status`/`tingkat_sumber` tak ada = tak ada yang bisa
  difilter). Ini murni perluasan pola "asuransi skema" yang sudah dipakai untuk
  primitif biaya (`cost_items.tipe`) — biaya sekarang mendekati nol, biaya
  nanti tidak.

- **Konsekuensi:**
  - Migrasi `4f88fdf0a67e_perluas_panduan_entries_dan_tautkan_kur_.py` +
    `app/models/entities.py` (`PanduanEntry`, `KurOutcome`), `app/models/base.py`
    (`TingkatSumber`, `StatusPanduan`), `tests/test_panduan_entries.py`
    (skema saja — belum ada service/tool untuk diuji end-to-end).
  - `app/tools/`, `app/kanal/`, seed **tidak disentuh** — 4c tetap menunggu
    gilirannya di urutan roadmap 1+4→2→3.
  - **Belum ada satu baris data pun** di `panduan_entries` — mengisinya
    menunggu verifikasi manual ke teks pasal Permenko 1/2026 (JDIH:
    `peraturan.go.id`/`jdih.setkab.go.id`), bukan ringkasan media manapun
    termasuk hasil riset sesi ini.

- **Pertanyaan terbuka:** apakah bunga flat 6% benar-benar bersyarat sektor
  (produksi/ekspor) sementara perdagangan non-ekspor KUR Kecil tetap berjenjang
  6→9% — sumber sekunder yang ditemukan saling berbeda. Siapa yang membaca
  pasal resminya sebelum `panduan_entries` diisi data KUR pertama?

---

## 2026-07-27 — Skor: margin tidak digerbangi cakupan HPP, dan periodenya 30 hari bergulir

- **Konteks:** slice Skor Kesehatan Usaha (Tahap 4b) — celah kode terakhir di H2
  yang tidak terhalang Tahap 0. Saat hendak menuliskan komponen skor, dua pasal
  [02-arsitektur.md](02-arsitektur.md) §4 ternyata sudah tidak sinkron dengan
  keputusan-keputusan yang lahir sesudahnya.

- **Keputusan:**
  1. **Komponen *margin laba* dihitung dari `laba_bersih ÷ omzet` dan TIDAK
     digerbangi cakupan HPP.** Pasal §4 yang menyuruh menandainya "belum bisa
     dihitung" saat cakupan HPP rendah **dicabut**.
  2. **Periode skor = 30 hari bergulir** sampai hari ini; pembanding tren = 30
     hari sebelumnya. Bukan bulan berjalan.
  3. **Normalisasi bobot** untuk komponen yang memang tak terhitung (omzet nol,
     tak ada periode pembanding, laba ≤ 0 sehingga rasio prive tak terdefinisi):
     `skor = Σ nilai ÷ Σ bobot_efektif × 100`. Σ bobot efektif nol → skor
     **`None`** + kartu "belum diketahui", bukan angka 0.
  4. **Konsistensi pencatatan memakai umur usaha sebagai penyebut** bila usaha
     lebih muda dari 30 hari.
  5. Skor dijangkau lewat **aksi terstruktur** `tanya_skor` (chip di kartu
     keuangan), bukan label router — `AksiRouter` tidak disentuh di slice ini.

- **Alasan:** butir 1 karena pasal §4 ditulis **sebelum** keputusan 2026-07-26
  mencabut formula "Omzet − HPP = Laba Kotor". Setelah pencabutan itu tangga laba
  adalah basis kas dengan **cakupan biaya 100% menurut definisi** — `laba_bersih`
  tidak lagi mengandung komponen yang bergantung pada HPP, jadi premis gerbangnya
  hilang. Kekhawatiran asli §4 ("jangan sajikan uang masuk − uang keluar seolah
  margin sesungguhnya") tetap sah, tapi jawabannya bukan gerbang: angka itu
  **sudah** kita tampilkan percaya diri di `KartuKeuangan` dan di laporan PDF yang
  dibawa ke bank. Menolak menskornya di kartu ketiga berarti produk yang sama
  tidak sepakat dengan dirinya sendiri — dan pengguna tanpa resep sama sekali akan
  kehilangan 25 bobot karena hal yang tak ada hubungannya dengan disiplin
  keuangannya. Cakupan HPP tetap dibawa kartu skor sebagai **label kejelasan
  data**, sejalan aturan #2, hanya saja perannya konteks, bukan gerbang.
  Butir 2 & 4 karena bulan berjalan menghukum pengguna oleh kalender: pada tanggal
  3, "% hari bercatatan" membaca 2 dari 3 dan angkanya bergeser sepanjang bulan
  tanpa perubahan perilaku apa pun — persis kelas angka menyesatkan yang aturan #2
  larang. Butir 3 karena memberi nilai 0 pada komponen yang **tak terhitung**
  adalah mengarang penilaian buruk dari ketiadaan data (aturan #2 diterapkan pada
  angka penilaian, sama seperti aturan #9). Butir 5 karena menaikkan `AksiRouter`
  6→7 label berisiko menggeser akurasi label yang sudah ada — keputusan 2026-07-22
  mencatat prompt "jungkat-jungkit" di ukuran model ini. Memisahkannya ke slice
  sendiri membuat dampaknya bisa diukur sendirian lewat `evaluasi/router.json`.

- **Konsekuensi:**
  - `skor_total` tetap **keluaran pengguna saja** (aturan #9). Uji negatif
    terpasang: `ringkas_laporan` & HTML laporan tidak boleh memuatnya.
  - Kartu skor menyebut periodenya (invarian 2026-07-27) dan membawa rincian per
    komponen — termasuk yang berstatus belum diketahui, supaya pengguna tahu
    persis apa yang menaikkannya.
  - Label periode `30_hari` ditambahkan ke `periode_dari_label()`; kosakata
    **parser kalimat tidak disentuh** — chip mengirim balik labelnya sendiri.
  - Ambang (margin ≥20% penuh, prive ≤50% penuh) tetap kalibrasi awal. Yang
    membetulkannya adalah `kur_outcomes`, bukan perdebatan internal — dan itu
    belum ada. Sampai saat itu skor tidak boleh dihadapkan ke penyalur.

---

## 2026-07-27 — Sumbu waktu: periode dibaca kode, dan kartu wajib menyebut periodenya

- **Konteks:** sampai slice ini seluruh produk hanya bisa menjawab satu periode,
  bulan berjalan. *"untung bulan lalu berapa"* dijawab dengan angka bulan ini,
  tanpa pesan salah dan tanpa tanda — kartunya tampak yakin. Dua hal memperbesar
  taruhannya: `KartuUntung` memasang **cakupan HPP tanpa pernah menyebut
  rentangnya**, dan slice impor baru saja membuat data bulan-bulan lampau mudah
  masuk — data yang tak terlihat sama sekali dari chat.

- **Keputusan:**
  1. **Periode dibaca parser kode (`app/services/periode.py`), bukan LLM.**
     Kosakata tertutup: hari ini · kemarin · minggu ini/lalu · bulan ini/lalu ·
     nama bulan (+tahun opsional) · N bulan terakhir · tahun ini. LLM tak
     ditambahi tugas; prompt router **tidak disentuh**.
  2. **Invarian baru: kartu berangka wajib menyebut periodenya.**
     `periode_tampil` jadi field **wajib** di `KartuUntung`; `KartuRiwayat`
     membawanya bila berfilter. Kontrak render naik **VERSI 7→8**.
  3. **Harga jual mengikuti akhir periode**, bukan hari ini —
     `kartu_untung` mengoper `KonteksHarga(tanggal=selesai)` bila pemanggil tak
     menyebut konteks.
  4. **Riwayat tanpa periode tetap tak berfilter** (N terakhir keseluruhan);
     hanya kalimat/chip berperiode yang memfilternya.
  5. **Frasa masa depan dijawab pertanyaan balik**, bukan kartu berisi nol.
  6. **Label periode dari klien yang tak dikenal → 422**, tak pernah jatuh
     diam-diam ke default.
  7. Parser dipanggil **setelah** router dan **hanya** untuk tiga label
     pertanyaan (`tanya_untung`, `tanya_keuangan`, `lihat_transaksi`).

- **Alasan:** butir 1 karena prompt router hari ini justru berbunyi *"Periode
  /tanggal TIDAK PERNAH kamu perlukan"*, dan menambah field kedua ke
  `PilihanAksi` berisiko menggeser akurasi label — di ukuran model ini prompt
  jungkat-jungkit (`06-evaluasi-ekstraksi.md`). Kosakata waktu warung kecil dan
  tertutup, jadi regex + aritmatika kalender menyelesaikannya dengan nol token,
  nol latensi, dan bisa diuji habis. Butir 2 adalah **aturan #2 diperluas dari
  nilai ke konteks**: persentase cakupan tanpa rentangnya adalah setengah angka,
  dan justru karena parser pasti melewatkan parafrase ("dua bulan belakangan",
  "sejak lebaran"), periode yang tertulis di kartu adalah **syarat kelayakan**
  butir 1 — salah baca jadi terlihat pengguna dan bisa dibetulkan satu ketukan,
  bukan diam-diam salah. Butir 3 karena `harga_jual_berlaku` jatuh ke `today()`
  bila tanggalnya kosong, jadi untung Juni selama ini dihitung dengan harga jual
  hari ini — persis kelas kesalahan yang tabel `product_prices` (append-only,
  `berlaku_dari`) dibangun untuk mencegah. Butir 4 karena memfilter default ke
  bulan berjalan akan menyembunyikan baris yang selama ini terlihat, dan pengguna
  tak punya cara tahu ada yang hilang. Butir 5 & 6 satu keluarga: nol yang tampak
  seperti hasil hitungan, dan jawaban periode-lain yang tampak sah, sama-sama
  salah yang tak terlihat siapa pun. Butir 7 karena di jalur pencatatan tanggal
  adalah **isi transaksi** ("kemarin jual bakso 400rb") dan sudah diurus
  ekstraksi; membacanya sebagai kueri periode akan mengubah catatan jadi
  pertanyaan.

- **Konsekuensi:**
  - Frasa di luar kosakata jatuh ke bulan berjalan — **sama seperti sebelum slice
    ini**, jadi tak ada kemunduran; yang berubah, periodenya sekarang tertulis.
    Perluasan kosakata menunggu data pemakaian nyata, bukan tebakan kita.
  - Produk yang harganya baru tercatat setelah periode yang ditanya kini tampil
    **tanpa laba** untuk periode lampau (modal tetap tampil). Itu jujur: harga
    jualnya memang belum ada saat itu.
  - Kalimat catatan kartu keuangan yang berbunyi "bulan ini" ditulis ulang jadi
    "di periode ini" — keterangan yang benar hanya selama periodenya cuma satu.
  - Jalur LLM untuk periode tetap terbuka: ia bisa ditumpuk **di atas** parser
    ini kalau kelak terbukti kurang, tanpa membongkarnya — dan pada saat itu
    `evaluasi/router.json` sudah jadi jaring regresinya.

---

## 2026-07-26 — Impor: pagar "tidak pernah auto-commit" dipasang di kotak chat

- **Konteks:** slice fondasi Pilar 2. Yang digarap alurnya
  (`parse → import_rows → tinjau → konfirmasi`), bukan koleksi parser-nya —
  supaya sumber berikutnya cukup menambah satu adaptor. Saat menyambungkannya,
  ketahuan aturan #3 bisa dilanggar **tanpa menyentuh kode impor sama sekali**:
  pengguna menempel satu halaman buku tulis ke kotak chat, router
  mengklasifikasinya `catat_transaksi`, dan `simpan_transaksi` menulis tiga puluh
  baris langsung ke buku. Tak ada yang menyebutnya impor, tapi itu persis impor
  yang auto-commit.

- **Keputusan:**
  1. **Belokan tempelan ada di `tangani_pesan`, bukan hanya di tool impor.**
     Pesan dengan **≥3 baris berisi** dibelokkan ke jalur draft sebelum router
     dipanggil. Deterministik (hitung baris), jadi nol token dan nol peluang
     salah klasifikasi. Dua baris masih dianggap ketikan tangan.
  2. **Adaptor #1 = tempelan teks, bukan foto** — menyimpang dari urutan Tahap 3,
     dan alasannya dicatat: fixture berkas nyata masih utang Tahap 0, jadi uji
     vision hari ini menguji gambar karangan sendiri. Foto masuk ke slot `Parser`
     yang sama tanpa mengubah alur.
  3. **Keyakinan baris dihitung kode, bukan dilaporkan model.** Skema ekstraksi
     tak punya field keyakinan dan `bangun()` menolak field asing — model tak
     punya slot untuk menilai dirinya sendiri. Sebab utama "ragu": **tanggal yang
     tidak tertulis**.
  4. **Aksi borongan tak pernah menyentuh baris ragu.** "Centang yang sudah
     jelas" melewati baris ragu & tak terbaca; keduanya harus diketuk satu per
     satu.
  5. **Baris tak terbaca tetap ditampilkan**, tak dibuang diam-diam, dan tak bisa
     dicentang.
  6. **Commit lewat `simpan_transaksi` yang sama dengan jalur chat**, hanya
     `sumber_input=impor` yang beda.
  7. Komposer chat jadi **textarea**; kontrak render naik **VERSI 6→7**
     (`KartuImpor` + `BarisImpor`).

- **Alasan:** butir 1 karena larangan yang hidup di satu modul akan dilewati oleh
  pintu lain di gedung yang sama — pagar harus berdiri di tempat perbuatannya
  terjadi, dan tempat itu adalah kotak chat. Butir 3 adalah aturan #1 diterapkan
  pada **angka penilaian**, perluasan yang sama dengan larangan skor komposit
  (aturan #9): keyakinan yang dilaporkan model adalah tebakan berbaju wibawa.
  Butir 4 karena aksi borongan yang ikut menyapu baris ragu mengubah peninjauan
  jadi formalitas — dan formalitas adalah auto-commit dengan satu ketukan
  tambahan. Butir 6 supaya tak lahir jalur tulis kedua yang perlahan menyimpang
  dari yang pertama (penautan produk & umpan HPP ikut jalan gratis).
  Sebab "tanggal tidak tertulis" (butir 3) dipilih karena di jalur chat
  membiarkan tanggal jatuh ke hari ini hampir selalu benar, sedangkan di jalur
  impor ia memindahkan halaman buku bulan Juni ke bulan Juli — menggeser setiap
  laporan di atasnya tanpa ada yang salah tampak.

- **Konsekuensi:**
  - **Satu baris = satu panggilan ekstraksi.** Mahal secara nominal, sengaja:
    impor jarang & sengaja (bukan aksi harian), satu baris busuk tak boleh
    membunuh 29 baris sehat, dan penjaga `periksa_nominal` jadi tepat sasaran.
    Obatnya kelak = chunking dengan jatuh-balik per-baris, **tanpa** mengubah
    kontrak `Parser`.
  - Tempelan dibatasi **60 baris**, ditolak (bukan dipotong) bila lewat —
    peninjauan yang mustahil dilakukan di layar HP adalah peninjauan yang akan
    dilewati.
  - `import_rows` tak punya `business_id`, jadi setiap query barisnya **men-join
    `imports`** (aturan #6). Tanpa itu, `import_id` dari klien cukup untuk
    menulis ke buku usaha lain.
  - `import_rows.parsed` menampung `catatan` & `yang_kurang` — keduanya memang
    hasil parse, dan menumpangkannya menghindari migrasi kolom untuk data yang
    bentuknya masih akan berubah saat adaptor lain menyusul. **Tanpa migrasi.**
  - Komposer `<input>` → `<textarea>` bukan kosmetik: browser membuang newline
    saat menempel ke input satu baris, jadi tanpa perubahan ini jalur impor
    mustahil terpicu dari browser.

---

## 2026-07-26 — Laporan bank: tangga basis kas, bukan formula "Omzet − HPP"

- **Konteks:** slice pertama H2 = laporan PDF, keluaran pertama produk ini yang
  **dibaca orang lain** (AO bank/koperasi), bukan pemiliknya. Rencana kerja
  Tahap 4a menuliskan formulanya sebagai *Omzet − HPP = Laba Kotor − Operasional
  = Laba Bersih*. Begitu ditulis sebagai kode, formula itu tabrakan dengan aturan
  #2: ia hanya benar bila cakupan HPP 100%, padahal cakupan parsial adalah
  **kondisi normal** — dan justru angka yang wajib ditampilkan.

- **Keputusan:**
  1. **Tangga utama laporan = basis kas:** `Omzet − (Belanja + Operasional) =
     Laba Bersih`, memakai `hitung_laba_periode` yang sudah ada. HPP & laba kotor
     jadi **blok terpisah** yang menyebut cakupannya sendiri, dijembatani
     `rekonsiliasi_biaya`. Kalimat formula di Tahap 4a **direvisi**, bukan
     dipatuhi diam-diam.
  2. **"Bulan pencatatan konsisten" tidak diberi ambang.** `02-arsitektur.md §4`
     memintanya sebagai fakta penyalur; yang dilaporkan adalah **hari tercatat
     per bulan** + rentetan bulan bercatatan, apa adanya.
  3. **Laporan punya register bahasanya sendiri.** "Omzet", "Laba Bersih",
     "Prive" dipakai apa adanya karena pembacanya AO — non-goal "bahasa warung
     saja" berlaku untuk **UI chat**. Yang tetap dilarang: debit/kredit/jurnal.
  4. **Laporan dijangkau lewat aksi terstruktur (tombol), bukan label router.**
  5. Kontrak render naik **VERSI 5→6**: `KartuDokumen` + `BarisRingkas`.

- **Alasan:** butir 1 adalah aturan #2 diterapkan pada aritmatika yang tampak
  tak berbahaya. Mengurangkan `hpp_total` (modal untuk 78% penjualan) dari
  **seluruh** omzet menghasilkan "Laba Kotor" yang sebagian dikarang — dan
  dikarang di dokumen yang dibawa ke bank. Basis kas punya sifat yang tak dimiliki
  jalur HPP: **cakupan biayanya 100% menurut definisi**. Ini juga sekadar
  memperluas keputusan 2026-07-18 ("dua angka") ke dokumen: yang tak boleh
  dilebur di layar juga tak boleh dilebur di kertas.
  Butir 2 karena menetapkan sendiri "konsisten = ≥N hari" adalah **penilaian
  berbaju angka** — hal yang sama yang aturan #9 larang untuk skor komposit.
  Kami tak punya kalibrasi untuk ambang itu; AO punya kriterianya sendiri.
  Butir 4 karena `evaluasi/router.json` sudah memetakan *"laporan singkat dong"*
  → `tanya_keuangan`. Label `buat_laporan` akan bersaing langsung dengannya, dan
  pelajaran `06-evaluasi-ekstraksi.md` berlaku. Membuat dokumen pun **tindakan
  sengaja**, bukan pertanyaan sambil lalu: tombol lebih tepat, nol ambiguitas,
  nol token.

- **Konsekuensi:** `app/services/laporan.py` (angka, multi-bulan,
  `fakta_penyalur`), `app/laporan/` (HTML + CSS cetak + PDF + pratinjau),
  `app/tools/laporan.py` (simpan berkas & `documents`), `KartuDokumen`,
  `POST /chat {aksi:"buat_laporan"}`, `GET /dokumen/{id}`, tombol di kartu
  keuangan + proxy unduhan BFF. **Tanpa migrasi** — `documents` sudah ada.
  Turunan yang ikut diputuskan:
  - PDF di-impor **lazy**; WeasyPrint butuh GTK/Pango yang tak ada di mesin dev
    Windows, jadi isi laporan **diuji tanpa PDF** dan diperiksa mata lewat
    `python -m app.laporan.pratinjau`. Gagal render → **503 berpesan**, bukan 500.
  - `rupiah()` kini menulis negatif sebagai `−Rp1.500`, bukan `Rp-1.500`.
    'Rp-' di dokumen analis kredit terbaca seperti salah cetak.
  - Uji negatif aturan #9 dipasang **sekarang**, saat mustahil dilanggar: tak ada
    "skor" di sel/judul laporan & tak ada pola `NN/100`. Begitu `skor_pengguna`
    lahir, test itulah yang menahan tangan.
  - Data pengguna masuk markup untuk pertama kalinya → `html.escape` di satu
    pintu (`app/laporan/html.py:_e`), dengan test injeksi.
  - ⚠️ **Format masih v1 dan mengaku demikian di kaki dokumen.** Ia belum pernah
    dilihat AO bank (Tahap 0). Isinya fakta, jadi revisi pasca-tinjauan
    seharusnya kosmetik — seluruh tata letak ada di `app/laporan/laporan.css`.

## 2026-07-26 — Koreksi lewat kalimat bebas: ragu antara catat & koreksi → mengaku tidak yakin

- **Konteks:** `koreksi_transaksi` sudah lengkap & teruji sejak 2026-07-20, tapi
  tak terjangkau dari chat — `AksiRouter` cuma punya 5 label dan fallback-nya
  pencatatan. Akibatnya *"eh salah, harusnya 57rb"* bukan sekadar fitur yang
  belum ada: ia **menambah transaksi hantu Rp57.000** di atas baris yang salah.
  Menyambungkannya berarti menambah label ke-6, dan label itu punya sifat yang
  tak dimiliki lima label lain — **ia menulis ke baris yang sudah ada**.

- **Keputusan:**
  1. Label ke-6 `koreksi_transaksi` masuk ke `AksiRouter`. Garis batasnya
     terhadap `catat_transaksi` ditulis eksplisit di prompt (penanda "harusnya",
     "bukan", "salah", "hapus", "yang tadi").
  2. **Saat ragu ANTARA `catat_transaksi` dan `koreksi_transaksi`, router wajib
     `_gagal`** — yang berarti jatuh ke pencatatan. Ini satu-satunya pasangan
     label yang diberi aturan ragu tersendiri.
  3. Sasaran koreksi bisa ditunjuk pengguna dari kartu riwayat lewat token
     konteks yang dibawa klien (pola `KonteksTunggu` yang sudah ada) — dan
     sasaran asing/tak ditemukan **berhenti di situ**, tidak jatuh ke alur
     normal.
  4. Kontrak render naik **VERSI 4→5**: `KartuKonfirmasi` bertambah
     `dibatalkan_id`.

- **Alasan:** dua arah kesalahan router tidak sama beratnya, tapi keduanya buruk
  dengan cara berbeda. Salah baca catatan baru sebagai koreksi = **membatalkan
  baris yang benar**; salah baca koreksi sebagai catatan = **transaksi hantu**.
  Buku append-only membuat keduanya bisa dibalik, tapi hanya yang kedua yang
  langsung terlihat pengguna di kartu konfirmasi. Karena itu default saat ragu
  dipilih ke arah yang lebih kelihatan, bukan yang lebih senyap — perluasan
  aturan #2 (mengaku tidak tahu) ke keputusan *routing*, bukan cuma ke angka.
  Butir 3 memakai pagar yang sama: kalau id sasaran tak sah, kalimat koreksi
  **tidak boleh** berubah jadi catatan baru hanya karena jalur koreksinya buntu.
  `dibatalkan_id` ada karena buku append-only punya konsekuensi UI yang selama
  ini ditanggung diam-diam: daftar riwayat yang sudah tergambar tak tahu baris
  mana yang mati, sehingga catatan yang sudah dibetulkan tetap terlihat hidup di
  layar. Server yang tahu, jadi server yang memberi tahu — bukan klien menebak.

- **Konsekuensi:** `app/llm/skema.py` (+1 label, prompt router 6 label),
  `orkestrator.py` (`KonteksTunggu` jadi dua jenis, `_kartu_koreksi`),
  `main.py` (`KonteksMasuk` opsional per jenis), web (tombol "Betulkan" per baris
  riwayat + penanda "sedang membetulkan" yang selalu punya jalan keluar).
  **Tanpa migrasi** — kolomnya sudah ada sejak `12e4f362ee11`.
  Set evaluasi baru `evaluasi/router.json` + `app/llm/evaluasi_router.py`:
  separuh isinya kasus label **lama** sebagai pengaman regresi, karena pelajaran
  `docs/06-evaluasi-ekstraksi.md` — di ukuran model ini menambal satu label bisa
  merusak label lain. Kalau itu terjadi, jalan keluarnya menurunkan kasusnya ke
  `_gagal`, **bukan** memaksa prompt.
  ⚠️ Gelembung konfirmasi lama di layar sengaja **tidak** diperbarui saat baris
  di dalamnya dikoreksi — itu catatan percakapan saat itu; yang diperbarui hanya
  kartu riwayat (daftar berjalan).

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

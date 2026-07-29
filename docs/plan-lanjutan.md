# Plan Lanjutan — sesi berikutnya

> Ditulis 2026-07-28, setelah B1/B2 (diverifikasi sudah ada), D1, C1+C2, B3 selesai
> (`bc7c4db`, `b3c8fde`, `3f2922b` di atas `c0c26ae`). **Rencana, bukan eksekusi** —
> jangan mulai ngoding dari dokumen ini sebelum direview & disetujui.

## Otoritas & sumber

Urutan otoritas dipakai menyusun dokumen ini (sesuai instruksi kerja):

1. **`docs/keputusan.md`** — menang atas segalanya kalau ada pertentangan.
2. `docs/02-arsitektur.md` / `docs/04-rencana-kerja.md` — desain & checklist hidup.
3. **`docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`** — plan lama, **sebagian sudah dieksekusi**
   (lihat commit di atas). Diperlakukan sebagai **konteks historis**, bukan daftar
   tugas yang masih berlaku — **kecuali Lampiran A**-nya: itu data regulasi KUR yang
   sudah **diverifikasi manusia** langsung dari `docs/regulasi/2026PemenkoEkon001.pdf`,
   dan masih jadi sumber kebenaran yang sah untuk fakta yang belum diimplementasi
   (mis. agunan, §E2 di bawah). ✅ Sudah ter-commit terpisah (Gerbang 0,
   `aecd81e`) sebelum E2 disentuh.

Tidak ada pertentangan antara `keputusan.md` dan `PLAN_EKSEKUSI_CLAUDE_CODE.md` yang
ditemukan saat menyusun rencana ini — plan lama sudah menuliskan sendiri statusnya
sebagai "sebagian dieksekusi", dan bagian yang tersisa (§8 non-kode, Lampiran A/B)
konsisten dengan keputusan yang tercatat.

## State saat ini (diverifikasi lewat kode + test, bukan checklist)

- P1 (catat_transaksi, koreksi_transaksi, multi-transaksi, ekstraksi produk & takaran)
  — **sudah ada & teruji** (`app/tools/catat_transaksi.py`,
  `tests/test_tool_catat_transaksi.py`, `tests/test_llm_kontrak.py`). ⚠️ Checklist
  `docs/04-rencana-kerja.md` Tahap 2a menandai beberapa item ini `[ ]` — **stale**,
  bukan gap nyata. Tidak dijadikan tugas di sini; hanya dicatat supaya tidak
  mengira ada pekerjaan yang sebenarnya sudah selesai.
- P4 HPP — snapshot sudah ter-wire (`simpan_snapshot_hpp` di `atur_resep`,
  `rangkai_hasil`, `kartu_untung`).
- P3 4b (skor) — kartu & guard aturan #9 lengkap, **tapi `simpan_snapshot_skor`
  nol pemanggil produksi** → lihat §E1.
- P3 4c (KUR) — topik `bunga` lengkap (guard+router+8 entri aktif). Topik `agunan`
  **belum ada sama sekali** → lihat §E2. Wawancara multi-turn (`kur_interviews`),
  `susun_dokumen_kur`, `panduan_perizinan` belum digarap.
- P2 impor — CSV berhenti di struktur (`baca_csv_generik`), pemetaan kolom &
  endpoint unggah **tetap ditahan** (lihat bagian "Ditahan" di bawah) — precondition
  (fixture A3 nyata) belum terpenuhi.
- Test suite: 315 lolos (`pipenv run pytest -q`), `ruff check .` bersih.

---

## E1 — Catat snapshot skor secara berkala

**Status: SELESAI (2026-07-28)** — lihat `docs/keputusan.md` 2026-07-28
("Snapshot skor harian dipicu lazy di `/sesi`"). Jawaban pertanyaan hulu:
riwayat dipakai untuk **grafik tren** (drift kalender = sinyal, bukan noise),
pemicu = **lazy-daily di `GET /sesi`**, tanpa pre-check "sudah ada snapshot
hari ini" (dedup nilai-identik `simpan_snapshot_skor` sudah cukup). Implementasi:
`app/api/main.py` (`sesi()` dapat parameter `session`, memanggil `hitung_skor`
+ `simpan_snapshot_skor`), `tests/test_api_sesi.py` (baru, 5 test). Sisa
dokumen di bawah ini (opsi A/B/C) dibiarkan sebagai catatan riwayat kenapa
opsi lain tidak dipilih — bukan tugas terbuka lagi.

### Precondition (historis — sudah terpenuhi)
Pilih titik pemicu (lihat "Opsi" di bawah) — **jangan mulai coding sebelum ini
dipilih**, karena pilihan menentukan file yang disentuh.

### Konteks
`simpan_snapshot_skor` (`app/services/skor.py:426`) sudah ditulis & diuji
(dedup identik dengan `simpan_snapshot_hpp`), tapi **nol pemanggil di jalur
produksi** — dicatat eksplisit sebagai gap terbuka di
`docs/04-rencana-kerja.md` baris 120. `kartu_skor` (jalur baca, dipanggil tiap
`tanya_skor`) **sengaja tidak** memanggilnya — docstring-nya
(`app/kanal/orkestrator.py:614-617`) menjelaskan kenapa: menulis snapshot tiap
kali kartu dibuka akan membanjiri riwayat dengan snapshot periode-bergeser
(skor 30-hari-bergulir berubah kunci periodenya tiap hari meski tak ada
transaksi baru), mengubur sinyal delta yang berarti. Ini **beda** dari HPP:
HPP hanya berubah saat resep/harga berubah (event jelas: `atur_resep`), skor
bisa "berubah" murni karena kalender bergeser tanpa pengguna berbuat apa pun.
Karena itu skor butuh pemicu **periodik**, bukan pemicu per-tulisan seperti
HPP — dan repo ini **belum punya infra scheduler/cron** apa pun.

### Opsi pemicu (pilih satu — lihat pertanyaan di akhir dokumen)
- **A. Lazy-daily di `/sesi`**: saat endpoint `/sesi` dipanggil (dibuka sekali
  per kunjungan), cek apakah sudah ada snapshot untuk kunci periode hari ini;
  kalau belum, hitung & simpan. Tanpa proses baru, tapi menaruh efek samping
  tulis di endpoint yang sebelumnya murni baca.
- **B. Lazy-daily di `/chat`**: sama seperti A, tapi dipicu di request pertama
  `/chat` per business per hari (lebih sering terpanggil daripada `/sesi`,
  tapi jalur yang sudah menulis hal lain juga).
- **C. Proses terjadwal terpisah** (cron/APScheduler dipanggil harian):
  paling bersih secara pemisahan tanggung jawab, tapi menambah komponen
  infrastruktur baru yang belum ada presedennya di repo ini.

### Langkah (setelah opsi dipilih)
1. Pasang pemanggilan `simpan_snapshot_skor` di titik yang dipilih, dengan
   `business_id` yang sama dengan yang dipakai `hitung_skor`.
2. Test integrasi: jalankan jalur produksi (bukan panggil fungsi snapshot
   langsung) lalu **baca ulang dari storage** (`ScoreSnapshot` via
   `snapshot_terakhir_skor`) — pola sama dengan test `simpan_snapshot_hpp`
   (`tests/test_resep.py::test_atur_resep_menulis_snapshot_hpp`).
3. Test negatif: memanggil dua kali dalam kunci periode yang sama tidak
   menghasilkan baris kedua (dedup) — kunci `_kunci_periode` sudah menangani
   ini, tinggal diuji dari jalur produksi baru.

### File
Tergantung opsi: `app/api/main.py` (opsi A/B) + `app/services/skor.py`
(tidak berubah, tinggal dipanggil) + test integrasi baru
(`tests/test_skor.py` atau file baru `tests/test_skor_snapshot_produksi.py`).

### Definition of Done
- [ ] `grep -rn "simpan_snapshot_skor" app/` menunjukkan pemanggilan di luar test.
- [ ] Test integrasi baru membaca kembali snapshot dari storage setelah jalur
      produksi (bukan mock).
- [ ] Test dedup: dua pemanggilan berturutan dalam periode yang sama →
      tetap satu baris.
- [ ] `pytest tests/ -k skor -q` hijau.
- [ ] `pytest tests/ -q` seluruhnya hijau.

---

## E2 — Topik `agunan` di panduan KUR

**Status: SELESAI (2026-07-28)** — lihat `docs/keputusan.md` 2026-07-28
("Topik agunan KUR..."). `app/seeds/panduan_kur_agunan.py`,
`kartu_panduan_kur(..., topik=...)`, `PesanMasuk.topik_kur` + validasi 422.
Follow-up bernama (F2, jawaban plafon-kondisional) **selesai 2026-07-29** —
lihat bagian "F2" di bawah dan `docs/keputusan.md` 2026-07-29. Sisa dokumen
di bawah ini dibiarkan apa adanya sebagai catatan desain, bukan tugas
terbuka lagi.

### Precondition
Tidak ada yang menghalangi mulai — data sudah terverifikasi (Lampiran A.3,
`docs/PLAN_EKSEKUSI_CLAUDE_CODE.md`, dua pasal terpisah: larangan Pasal 20 +
sanksi Pasal 21). **Jangan tambah/ubah angka pasal** di luar yang tercantum
di Lampiran A.3 — kalau butuh detail lain (mis. prosedur pengecualian petani
tebu), baca `docs/regulasi/2026PemenkoEkon001.pdf` langsung, jangan
menyimpulkan dari ingatan.

### Konteks
`app/services/panduan_kur.py` sudah punya guard **generik** lintas-topik
(`jawab_panduan(session, topik, pertanyaan_kanonik=None)` — tidak spesifik
bunga), jadi topik baru **tidak butuh dataclass konteks baru** seperti
`KonteksBunga`: aturan agunan tidak bercabang kategori/sektor/ekspor, hanya
bercabang plafon (≤Rp100jt vs pengecualian petani tebu/KUR khusus pertanian
untuk >Rp100jt) — cukup 1-2 entri datar, mirip pola `bunga-overview`.

Data (Lampiran A.3, sudah terverifikasi):

| Ketentuan | Isi | Pasal |
|---|---|---|
| Larangan | Plafon ≤ Rp100 juta: penyalur tidak boleh mensyaratkan agunan tambahan | Pasal 20 (1) |
| Pengecualian | Petani tebu rakyat & KUR khusus pertanian dgn offtaker avalis (>Rp100jt) | Pasal 20 (2) |
| Sanksi | Bila dilanggar: subsidi bunga/marjin tidak dibayarkan | Pasal 21 (1) |
| Pengembalian | Bila subsidi sudah diterima: dikembalikan ke kas negara | Pasal 21 (2) |

### Desain yang diusulkan (review saat plan disetujui, bukan pertanyaan terbuka)
Perluas aksi `tanya_kur` yang sudah ada dengan slot eksplisit baru
`topik: str = "bunga"` (bukan aksi baru `tanya_kur_agunan`) — konsisten dengan
pola "slot eksplisit, bukan ekstraksi bahasa bebas" yang sudah dipakai untuk
`jenis_kur`/`sektor_usaha`/`berorientasi_ekspor`. `kartu_panduan_kur` di
orkestrator bercabang: `topik == "bunga"` → jalur `KonteksBunga` yang sudah
ada; `topik == "agunan"` → panggil `jawab_panduan(session, "agunan")`
langsung (tanpa konteks tambahan, karena tidak ada cabang kategori/sektor).

### Langkah
1. Seed baru `app/seeds/panduan_kur_agunan.py` (pola sama persis dengan
   `panduan_kur_bunga.py`: upsert per `pertanyaan_kanonik`, `status=aktif`
   langsung — data sudah terverifikasi sejak awal, tidak perlu tahap `draft`).
   Minimal 1 entri (`pertanyaan_kanonik="Apakah KUR butuh agunan tambahan?"`)
   merangkum keempat baris tabel di atas dengan `pasal_rujukan="Pasal 20;
   Pasal 21"`.
2. `app/api/main.py`: tambah `topik_kur: str | None = None` (default
   `"bunga"` bila kosong, untuk kompatibel mundur) ke `PesanMasuk`; validasi
   nilai tak dikenal → 422.
3. `app/kanal/orkestrator.py`: `kartu_panduan_kur` menerima parameter topik
   (atau dua fungsi kecil dipanggil dari `main.py` — pilih yang lebih rapi
   saat implementasi), bercabang ke `jawab_panduan` untuk topik non-bunga.
4. Test: entri agunan menjawab dengan `pasal_rujukan` + `sumber_url`
   terisi; entri belum di-seed → `Penolakan` (bukan kartu kosong); topik
   asing → 422.

### File
`app/seeds/panduan_kur_agunan.py` (baru), `app/services/panduan_kur.py`
(tidak wajib berubah — `jawab_panduan` sudah cukup generik), `app/kanal/orkestrator.py`,
`app/kanal/kontrak.py` (kemungkinan tidak perlu — `KartuPanduanKur` sudah
generik topik apa pun), `app/api/main.py`, `tests/test_panduan_kur.py` +
`tests/test_kanal_panduan_kur.py` (tambahan, bukan file baru).

### Definition of Done
- [ ] `pytest tests/test_panduan_kur.py tests/test_kanal_panduan_kur.py -q` hijau,
      termasuk kasus topik `agunan` baru.
- [ ] Jawaban agunan menyertakan `pasal_rujukan` (Pasal 20/21) + `sumber_url`
      BPK yang sama dengan bunga (regulasi payung sama).
- [ ] Topik `tanya_kur` tanpa `topik_kur` eksplisit tetap berperilaku seperti
      sebelumnya (default bunga) — test regresi tak berubah.
- [ ] `pytest tests/ -q` seluruhnya hijau.

---

## F2 — Jawaban agunan KUR plafon-kondisional

**Status: SELESAI (2026-07-29)** — lihat `docs/keputusan.md` 2026-07-29
("Jawaban agunan KUR plafon-kondisional"). `KonteksAgunan` +
`jawab_agunan_kur` (`app/services/panduan_kur.py`), tiga entri baru di
`app/seeds/panduan_kur_agunan.py` (entri overview lama dipensiunkan ke
`superseded`), dispatch tiga arah di `kartu_panduan_kur`
(`app/kanal/orkestrator.py`), `PesanMasuk.plafon_diajukan` +
`.sektor_pertanian_khusus` (`app/api/main.py`). BREAKING CHANGE disengaja:
`topik_kur="agunan"` tanpa `plafon_diajukan` sekarang minta klarifikasi,
bukan lagi jawaban overview plafon-agnostik lama — lihat entri
`docs/keputusan.md` untuk detail dan alasan.

---

## Ditahan (precondition belum terpenuhi — jangan mulai)

Ini bukan tugas untuk sesi berikutnya; dicatat ulang di sini supaya tidak
tergoda mulai duluan karena "kelihatan mudah setelah B3".

- **Pemetaan kolom CSV → transaksi** (`petakan_baris_generik`,
  `app/impor/csv_generik.py`) — precondition: fixture A3 (contoh berkas impor
  nyata per format) belum ada. Tetap `NotImplementedError`.
- **Endpoint HTTP unggah CSV** — precondition: pemetaan kolom di atas harus
  ada dulu (tak ada gunanya endpoint tanpa konsumen), plus dependency
  `python-multipart` belum terpasang.
- **`kur_outcomes` — mekanisme capture hasil pengajuan** — precondition:
  keputusan manusia soal *cara menangkap* (follow-up ke pengguna? lewat AO?)
  belum ada (`PLAN_EKSEKUSI_CLAUDE_CODE.md` §8). Ini bukan keputusan yang
  agen boleh improvisasi — schema (`kur_outcomes.panduan_entry_id`) sudah
  siap menampung begitu mekanismenya diputuskan manusia.
- **Wawancara KUR multi-turn (`kur_interviews`)** — belum di-scope sama
  sekali (lihat §F1 di bawah untuk usulan awal, sengaja tidak ditulis sebagai
  tugas penuh).

## Dicatat, bukan tugas — kandidat untuk sesi setelah ini

- **F1 — Wawancara KUR multi-turn, slice pertama.** `04-rencana-kerja.md`
  §4c menempatkan ini setelah slice `tanya_kur` (yang baru selesai). Sengaja
  **tidak** ditulis sebagai tugas ber-DoD di sini karena scope-nya masih
  lebar (state machine di `kur_interviews`, strategi windowing per
  §6a arsitektur, batas dengan slot eksplisit `tanya_kur` yang sudah ada).
  Perlu sesi diskusi scoping tersendiri sebelum ditulis sebagai tugas —
  CLAUDE.md eksplisit minta ini dibahas dulu, bukan diimprovisasi.
- **Narasi LLM di atas kartu skor** — `04-rencana-kerja.md` baris 122 sudah
  mencatat ini sengaja ditunda (kartu sudah menjelaskan dirinya sendiri lewat
  rincian komponen; panggilan LLM kedua belum jelas nilai tambahnya). Tidak
  diusulkan berubah di sini.

---

## Pertanyaan yang sudah dijawab (riwayat)

Ketiga pertanyaan di draf awal dokumen ini sudah dijawab & dieksekusi
2026-07-28:

1. **E1 pemicu** — lazy-daily di `/sesi` (dipilih atas `/chat` dan proses
   terjadwal terpisah setelah pertanyaan hulu "untuk apa riwayat ini dipakai"
   dijawab: grafik tren). Lihat `docs/keputusan.md`.
2. **E1 & E2 sebagai dua commit terpisah** — dikerjakan berurutan E2 dulu
   (tak ada pertanyaan desain terbuka) lalu E1 (`e3cc4d0` lalu commit E1
   berikutnya), bukan digabung.
3. **Gerbang 0** — `docs/PLAN_EKSEKUSI_CLAUDE_CODE.md` +
   `docs/regulasi/2026PemenkoEkon001.pdf` di-`git add` sebagai commit
   tersendiri (`aecd81e`) sebelum E2 disentuh, persis karena E2 bergantung
   pada data terverifikasi di dalamnya.

Tidak ada pertanyaan terbuka baru dari E1/E2 selain follow-up bernama F2
(lihat "Ditahan" di atas) dan kandidat F1 (belum di-scope, lihat di atas).

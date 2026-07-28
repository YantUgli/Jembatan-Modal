# Checklist verifikasi — bunga KUR (`panduan_entries`, topik `bunga`)

> **Status: SELESAI (2026-07-28).** Delapan entri di `app/seeds/panduan_kur_bunga.py`
> sudah diverifikasi langsung ke teks `docs/regulasi/2026PemenkoEkon001.pdf` dan
> dipromosikan ke `status=aktif`. Riwayat di bawah ini dipertahankan sebagai jejak
> audit — lihat `docs/keputusan.md` (2026-07-28) untuk keputusan promosinya.

## Kenapa awalnya draft, bukan langsung aktif

Isi keempat entri awal (`bunga-overview`, `bunga-super-mikro`,
`bunga-produksi-ekspor`, `bunga-perdagangan-nonekspor`) disusun dari riset
sekunder (media, ringkasan hukum pihak ketiga, satu halaman resmi Kemenko
Perekonomian) — **belum** dari membaca pasal Permenko 1/2026 langsung. Nomor
pasal berbeda antar sumber sekunder (mis. kandidat Pasal 37 vs 44 untuk tarif
produksi/ekspor) — tanda jelas sumber sekunder saling tidak sepakat dan wajib
dicek ke teks asli.

## Hasil verifikasi (A1, 2026-07-28)

Dicocokkan ke teks resmi. Perubahan struktural terpenting: **Mikro dan Kecil
dipecah jadi kategori terpisah** (dulu digabung `mikro_kecil`) karena jenjang
non-ekspor keduanya berbeda:

- [x] Tarif tiap entri dicek sama persis dengan pasal (lihat Lampiran A
      rencana eksekusi untuk tabel lengkap per jenis KUR × sektor).
- [x] `pasal_rujukan` diisi nomor pasal + ayat final (bukan tebakan
      antar-sumber) — lihat `app/seeds/panduan_kur_bunga.py`.
- [x] `sumber_url` diganti URL `Details/...` resmi BPK (bukan placeholder,
      bukan link `Download/...pdf` yang rapuh).
- [x] Sektor produksi = Pasal 1 angka 2 (kegiatan ekonomi penghasil barang/jasa
      di luar sektor perdagangan). Perdagangan berorientasi ekspor **tidak**
      punya definisi pasal tersendiri — bersifat pembuktian dokumen (Pasal
      36 (3) a Mikro / 43 (3) a Kecil), bukan atribut yang boleh diasumsikan.
- [x] Akad keempat 9% dikonfirmasi **khusus KUR Kecil** (Pasal 44 (1) b.4).
      KUR Mikro non-ekspor berhenti di akad kedua (7%, Pasal 37 (1) b.2),
      dibatasi maksimal 2 akad (Pasal 36 (3) b) — **bukan** 6-7-8-9% seperti
      Kecil. Ini koreksi load-bearing terhadap catatan lama yang menyeragamkan
      keduanya.
- [x] Dua kategori tambahan yang belum ada di draft awal: **Khusus** (6% flat,
      Pasal 51 (1)) dan **Penempatan PMI** (6% flat, Pasal 58 (1)).
- [x] Status seluruh 8 entri dipromosikan ke `aktif`.

## Catatan tambahan

- Klaim "tanpa batas frekuensi" pada entri produksi/ekspor **khusus** segmen
  itu (Mikro maupun Kecil) — jangan pernah disalin ke entri non-ekspor sebagai
  berlaku universal.
- `pasal_rujukan` untuk agunan (Pasal 20 (1)-(2), sanksi Pasal 21 (1)-(2)) ada
  di Lampiran A rencana eksekusi — belum masuk `panduan_entries` (topik
  `bunga` saja yang tergarap di slice ini); topik `agunan` menyusul terpisah
  bila dibutuhkan.
- Router 4c (belum dibangun — lihat §7 rencana eksekusi) untuk pertanyaan
  bunga generik tetap wajib bertanya balik (jenis KUR? sektor? ekspor? akad ke
  berapa?) lalu mengutip entri spesifik yang cocok — guard (`_pertanyaan_bunga`
  di `app/services/panduan_kur.py`) sudah menegakkan ini: konteks kosong/
  parsial selalu ditolak dengan klarifikasi, tak pernah jatuh ke
  `bunga-overview` sebagai jawaban tarif final.

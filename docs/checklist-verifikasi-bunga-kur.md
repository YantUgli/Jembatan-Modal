# Checklist verifikasi — bunga KUR (`panduan_entries`, topik `bunga`)

> Empat entri terkait ada di `app/seeds/panduan_kur_bunga.py`, ter-seed dengan
> `status=draft` — **tidak boleh dipakai menjawab pengguna** sampai daftar di
> bawah ini tercentang semua dan status dipromosikan ke `aktif` (lihat aturan
> #4 di `CLAUDE.md` dan docstring `PanduanEntry`).

## Kenapa draft, bukan langsung aktif

Isi keempat entri disusun dari riset sekunder (media, ringkasan hukum pihak
ketiga, satu halaman resmi Kemenko Perekonomian) — **belum** dari membaca
pasal Permenko 1/2026 langsung. Nomor pasal berbeda antar sumber sekunder
(mis. kandidat Pasal 37 vs 44 untuk tarif produksi/ekspor) — tanda jelas
sumber sekunder saling tidak sepakat dan wajib dicek ke teks asli.

## Untuk **tiap** entri (`bunga-overview`, `bunga-super-mikro`,
## `bunga-produksi-ekspor`, `bunga-perdagangan-nonekspor`)

Buka salinan resmi Permenko 1/2026 di `peraturan.bpk.go.id` (atau JDIH
Kemenko), lalu:

- [ ] Konfirmasi angka tarif di `isi` sama persis dengan pasal.
- [ ] Isi `pasal_rujukan` dengan nomor pasal + ayat yang benar (bukan tebakan
      antar-sumber).
- [ ] Ganti `sumber_url` placeholder dengan URL dokumen resmi final.
- [ ] Konfirmasi cakupan "sektor produksi" & definisi "perdagangan
      berorientasi ekspor" sesuai teks (apakah Permenko 1/2026 memakai
      definisi sektor produksi = sektor non-perdagangan yang menambah
      barang/jasa, sama seperti asumsi yang dipakai menulis `isi`).
- [ ] Konfirmasi akad keempat 9% memang khusus KUR Kecil (bukan juga Mikro).
- [ ] Setelah semua tercentang untuk entri ini: ubah `status` jadi `aktif`.

## Catatan tambahan

- Klaim "tanpa batas frekuensi" pada `bunga-produksi-ekspor` **khusus** segmen
  itu — jangan pernah disalin ke entri lain sebagai berlaku universal.
- `pasal_rujukan` untuk agunan (larangan agunan tambahan ≤ Rp100 juta, plus
  kewajiban pengembalian subsidi bila dilanggar) juga masih perlu dikonfirmasi
  nomornya — di luar cakupan bunga, tapi masuk dokumen resmi yang sama, jadi
  sekalian saja saat membuka dokumennya.
- Router 4c (belum dibangun) sebaiknya, untuk pertanyaan bunga generik,
  bertanya balik (sektor? ekspor? plafon? akad ke berapa?) lalu mengutip
  entri spesifik yang cocok — bukan langsung mengutip `bunga-overview` sebagai
  jawaban final.

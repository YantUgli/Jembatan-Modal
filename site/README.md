# site/ — Situs portofolio JembatanModal

Landing page + demo chat ter-skrip untuk keperluan portofolio, dibangun dengan
**Next.js (App Router, TypeScript) sebagai static export**. **Bukan bagian dari
aplikasi** — tidak di-serve FastAPI, tidak menyentuh database, dan demo di sini
**bukan** cikal bakal UI chat produk (itu Tahap 4d, hidup di `web/`).

| Rute | Berkas | Isi |
|---|---|---|
| `/` | `app/page.tsx` | Landing page portofolio (hero + animasi timeline chat) |
| `/demo` | `app/demo/page.tsx` | Demo chat ter-skrip (kartu hardcoded, koreksi chip = state lokal React, **nol panggilan jaringan**) |

## Menjalankan

Butuh Node ≥ 20 (dikembangkan di Node 24). Toolchain JS ini terpisah penuh dari
tooling Python di root repo — tidak menyentuh pipenv/pytest/ruff/alembic.

```bash
cd site
npm install          # sekali
npm run dev          # dev server → http://localhost:3000
npm run build        # produksi + static export → ./out
npx eslint .         # lint
```

`npm run build` menghasilkan HTML statis di `out/` (`output: 'export'` di
[next.config.mjs](next.config.mjs)). Deploy = unggah isi `out/` apa adanya ke
static hosting mana pun; tidak butuh server Node saat runtime.

Preview hasil build:

```bash
python -m http.server -d out 8080   # → http://localhost:8080
```

## Struktur

- `app/globals.css` — **design token** (palet, radius, bayangan) sebagai CSS
  variable di satu tempat. Warna utama hijau `#2f7a5b`, aksen amber `#c97b2c`.
- `app/layout.tsx` — root layout, `lang="id"`, font via `next/font/google`
  (Plus Jakarta Sans + IBM Plex Mono, di-self-host saat build), metadata dasar.
- `app/page.tsx` + `app/page.module.css` — landing.
- `app/demo/page.tsx` + `app/demo/demo.module.css` — demo.
- `components/HeroChat.tsx` — animasi timeline chat di hero (client). Satu ronde
  penuh lalu berulang; menghormati `prefers-reduced-motion` (tampil penuh, tanpa
  loop) dan tetap utuh tanpa JavaScript.
- `components/ChatDemo.tsx` — logika demo ter-skrip (client): tombol saran →
  kartu hardcoded, chip kategori bisa dikoreksi lewat state lokal, kalimat bebas
  dijawab jujur ("belum diproses karena tidak ada server di baliknya"). **Tanpa
  panggilan API.**
- `components/Logo.tsx` — lambang JembatanModal (parametris per ukuran).

Angka pada kartu demo & hero adalah **data contoh Bu Sari yang di-hardcode** demi
tampilan; produk sungguhan menghitungnya di service layer. Konsisten dengan
aturan #1 repo: halaman ini tidak menghitung apa pun.

## Meta verifikasi Dicoding

Kedua halaman menyematkan `<meta name="dicoding:email" ...>` lewat
`metadata.other` di masing-masing `page.tsx`, sehingga muncul di HTML statis
hasil `out/` (Dicoding membaca HTML, bukan hasil injeksi client-side).

## Catatan sejarah

Desain awal dirujuk dari export Claude Design (dua bundle self-contained yang
sempat ter-commit sebagai `index.html` / `demo.html`). Sejak port ke Next.js ini,
**sumber kebenaran desain adalah kode di folder ini**, bukan lagi Claude Design;
bundle lama sudah dihapus dari tree. Lihat entri `docs/keputusan.md` bertanggal
2026-07-22 (Next.js) yang men-supersede entri "tidak-unbundle" hari yang sama.

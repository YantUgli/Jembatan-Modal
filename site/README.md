# site/ — Situs portofolio statis

Landing page + demo chat ter-skrip untuk keperluan portofolio. **Bukan bagian
dari aplikasi** — tidak di-serve FastAPI, tidak menyentuh database, dan demo di
sini **bukan** cikal bakal UI chat produk (itu Tahap 4d, hidup di `web/`).

| Berkas | Isi |
|---|---|
| `index.html` | Landing page portofolio |
| `demo.html` | Demo chat ter-skrip (kartu hardcoded, koreksi chip = state lokal React, **nol panggilan jaringan**) |

## Format berkas: bundle export Claude Design

Kedua berkas HTML **bukan HTML polos**, melainkan bundle self-contained hasil
export Claude Design (±500 KB/berkas): runtime unpacker JS, React + ReactDOM
production ter-embed, 24 font woff2 ter-base64, dan markup halaman sebagai
string JSON di dalam tag `<script type="__bundler/template">`. Butuh JavaScript
aktif untuk render. Runtime bundler punya logika keamanan iframe/postMessage —
**jangan diutak-atik**.

## Source of truth & cara mengedit

Source of truth desain ada di **Claude Design**; berkas di folder ini adalah
**artefak build**.

- **Perubahan kecil** (teks, link): boleh diedit langsung pada string template
  bundle. Ingat string itu ter-encode JSON — jaga escape (`\"`, `\n`,
  `</...>`), dan jangan pernah memunculkan literal `</script>` di dalamnya.
- **Perubahan besar** (layout, section, komponen): lakukan di Claude Design lalu
  re-export ke sini.

### Penyimpangan lokal dari export (wajib diterapkan ulang saat re-export)

1. Link silang antarhalaman: `JembatanModal Demo.html` → `demo.html`,
   `JembatanModal Landing.html` → `index.html`.
2. `<title>` luar (fase loading) + `<title>` & `<meta name="description">` di
   head template — export aslinya hanya berjudul "Bundled Page".
3. Perbaikan copy landing agar sesuai kode per 2026-07-22:
   - "Tujuh belas berkas pengujian" → "Delapan belas" (`tests/` kini 18 berkas).
   - Klaim "hitungan modal belum tersambung ke jendela chat" dikoreksi: kartu
     untung per produk **sudah** tampil di chat (`tanya_untung` →
     `kartu_untung()` → `hitung_hpp_semua()`); yang belum tersambung adalah
     **wawancara resep** lewat percakapan.

   Idealnya poin 3 disinkronkan balik ke Claude Design agar export berikutnya
   tidak menghidupkan lagi klaim usang.

## Preview lokal

Buka langsung di browser (dobel-klik `index.html`), atau:

```bash
python -m http.server -d site 8080   # → http://localhost:8080
```

Deploy = unggah folder ini apa adanya ke static hosting mana pun.

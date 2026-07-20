# JembatanModal — repo kode

Asisten AI yang mengubah catatan keuangan harian UMKM jadi kejelasan untung-rugi
yang jujur dan kesiapan mengakses modal formal. Lihat [CLAUDE.md](CLAUDE.md) untuk
aturan yang tidak boleh dilanggar, dan [`docs/`](docs/) untuk perencanaan.

## Status

Fondasi + jantung HPP (Pilar 4). Yang sudah jalan & teruji:

- **Skema data inti** ke-4 pilar ([docs/02-arsitektur.md §5](docs/02-arsitektur.md)),
  dengan model komponen biaya extensible (`cost_items.tipe ∈
  {material|labor_time|overhead}`) — hanya `material` yang diimplementasi.
- **Service HPP deterministik** (`app/services/hpp.py`): reseller (harga beli
  terakhir) & produksi (Σ bahan ÷ yield), plus **semua jalur degradasi jujur**
  (resep kosong, bahan tanpa harga, penjualan tak terkenali, komponen
  non-material) dan **cakupan HPP** ("tercakup 94% omzet").
- **Seeder Bu Sari** (`app/seeds/bu_sari.py`): ±2 bulan transaksi, produk, resep,
  harga bahan bertanggal.
- **Migrasi Alembic** awal + **13 unit test** (`tests/test_hpp.py`).

Belum digarap: adapter LLM, orchestrator, tools (`catat_transaksi`, dll.), API
FastAPI, impor (P2), laporan/skor/dokumen (P3). Urutan garap **1+4 → 2 → 3**
([docs/04-rencana-kerja.md](docs/04-rencana-kerja.md)).

## Mulai cepat

Manajemen dependensi pakai **pipenv**:

```bash
pipenv install --dev                      # buat venv + pasang deps
pipenv run pytest                         # 13 passed
pipenv run alembic upgrade head
pipenv run python -m app.seeds.bu_sari
```

Perintah lengkap: [CLAUDE.md §Perintah](CLAUDE.md).

## Prinsip yang menstruktur kode

- **LLM tidak pernah berhitung** — tiap angka lahir di service layer, ber-unit-test.
- **Jangan mengarang angka saat data kurang** — kembalikan *"belum diketahui"* +
  apa yang kurang; cakupan HPP selalu ditampilkan.
- **Isolasi per-tenant** — tiap query difilter `business_id`.

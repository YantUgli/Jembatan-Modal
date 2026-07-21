# JembatanModal — UI chat (web)

Adaptor kanal **web** untuk JembatanModal. Satu jendela chat mobile-first yang
digambar dari **kontrak render** (`app/kanal/kontrak.py`) — bukan HTML terikat
kanal. Adaptor WhatsApp nanti berbagi kontrak & orchestrator yang sama.

- **Stack:** Next.js (App Router) + TypeScript, CSS tulis-tangan (token desain),
  tanpa UI kit. Bundle awal ~105 kB.
- **Topologi:** Browser → **BFF** (`app/api/*` Route Handler) → **FastAPI**
  internal (`app.api.main`) → orchestrator → tool/service/DB. FastAPI tak
  terekspos ke publik; browser hanya bicara dengan BFF.

## Jalankan (dua proses)

**1. Backend FastAPI** (dari root repo Python):

```bash
pipenv install --categories api          # sekali: fastapi + uvicorn
pipenv run alembic upgrade head          # siapkan skema (dev = SQLite)
pipenv run python -m app.seeds.bu_sari   # data demo Bu Sari (idempoten)
LLM_API_KEY=... LLM_BASE_URL=... LLM_MODEL=... \
  pipenv run uvicorn app.api.main:app --port 8000
```

> `LLM_*` hanya diperlukan untuk jalur **pencatatan** (ekstraksi bahasa natural).
> Jalur `koreksi_kategori` (ketuk chip) dan kartu untung (stub) tak memanggil LLM.

**2. Frontend** (dari `web/`):

```bash
cp .env.local.example .env.local   # set FASTAPI_URL bila bukan :8000
npm install
npm run dev                        # http://localhost:3000
```

## Verifikasi cepat

```bash
curl localhost:3000/api/sesi                                   # kartu sapaan
curl -XPOST localhost:3000/api/chat -H 'content-type: application/json' \
     -d '{"aksi":"tanya_untung"}'                              # kartu untung (stub)
```

## Yang jujur soal slice ini

- **Pencatatan** (`{teks}`) di-wire penuh: `catat_transaksi` → `kartu_konfirmasi`.
- **Koreksi kategori** (chip) di-wire: append-only, menghormati `koreksi_dari_id`.
- **Kartu untung/HPP** = **stub "belum tersambung"** — nol angka dikarang. Service
  HPP sudah matang; menyambungkannya adalah slice berikutnya.

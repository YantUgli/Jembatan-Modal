// Klien memanggil BFF-nya sendiri (/api/*), bukan FastAPI langsung — backend
// Python tak pernah tersentuh browser.

import type { ChatBody, PesanKeluar } from "./kontrak";

// Error ber-status supaya pemanggil bisa membedakan 401 (belum/kedaluwarsa
// login → tampilkan layar masuk) dari kegagalan lain.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function detailDari(res: Response): Promise<string> {
  let detail = `HTTP ${res.status}`;
  try {
    const j = await res.json();
    if (j?.detail) detail = String(j.detail);
  } catch {
    /* body bukan JSON — biarkan detail apa adanya */
  }
  return detail;
}

async function bacaKontrak(res: Response): Promise<PesanKeluar> {
  if (!res.ok) throw new ApiError(res.status, await detailDari(res));
  return (await res.json()) as PesanKeluar;
}

export async function ambilSesi(): Promise<PesanKeluar> {
  return bacaKontrak(await fetch("/api/sesi", { cache: "no-store" }));
}

export async function kirimChat(body: ChatBody): Promise<PesanKeluar> {
  return bacaKontrak(
    await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    }),
  );
}

export async function masuk(no_hp: string, pin: string): Promise<void> {
  const res = await fetch("/api/masuk", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ no_hp, pin }),
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(res.status, await detailDari(res));
}

export async function keluar(): Promise<void> {
  await fetch("/api/keluar", { method: "POST", cache: "no-store" });
}

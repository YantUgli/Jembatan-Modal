// Klien memanggil BFF-nya sendiri (/api/*), bukan FastAPI langsung — backend
// Python tak pernah tersentuh browser.

import type { ChatBody, PesanKeluar } from "./kontrak";

async function bacaKontrak(res: Response): Promise<PesanKeluar> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = String(j.detail);
    } catch {
      /* body bukan JSON — biarkan detail apa adanya */
    }
    throw new Error(detail);
  }
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

// BFF: teruskan GET /sesi (kartu pembuka) ke FastAPI internal. Sesi dibawa
// lewat cookie httpOnly → diteruskan sebagai header Bearer. Tanpa cookie /
// upstream 401 → diteruskan apa adanya (UI tampilkan layar masuk).
import { NextResponse } from "next/server";

import { BASE, headerAuth } from "@/lib/bff";

export const dynamic = "force-dynamic";

export async function GET(req: Request): Promise<NextResponse> {
  try {
    const upstream = await fetch(`${BASE}/sesi`, {
      headers: headerAuth(req),
      cache: "no-store",
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Tidak bisa menghubungi layanan." }, { status: 502 });
  }
}

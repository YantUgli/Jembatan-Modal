// BFF: teruskan POST /chat ke FastAPI internal. Sesi/auth & isolasi origin
// ditangani di sisi server; browser tak pernah tahu URL backend. Token sesi
// dibawa cookie httpOnly → diteruskan sebagai header Bearer.
import { NextResponse } from "next/server";

import { BASE, headerAuth } from "@/lib/bff";

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<NextResponse> {
  const body = await req.text();
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...headerAuth(req),
  };
  try {
    const upstream = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Tidak bisa menghubungi layanan. Coba lagi sebentar." },
      { status: 502 },
    );
  }
}

// BFF: teruskan POST /chat ke FastAPI internal. Sesi/auth & isolasi origin
// ditangani di sisi server; browser tak pernah tahu URL backend.
import { NextResponse } from "next/server";

const BASE = process.env.FASTAPI_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<NextResponse> {
  const body = await req.text();
  try {
    const upstream = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
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

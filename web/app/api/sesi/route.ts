// BFF: teruskan GET /sesi (kartu pembuka) ke FastAPI internal.
import { NextResponse } from "next/server";

const BASE = process.env.FASTAPI_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  try {
    const upstream = await fetch(`${BASE}/sesi`, { cache: "no-store" });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Tidak bisa menghubungi layanan." },
      { status: 502 },
    );
  }
}

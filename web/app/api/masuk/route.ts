// BFF: login. Teruskan kredensial ke FastAPI `/masuk`; kalau sukses, simpan
// token ke cookie httpOnly (browser TAK PERNAH melihat token via JS) dan balas
// body tanpa token. Request berikutnya cukup membawa cookie itu.
import { NextResponse } from "next/server";

import { BASE, NAMA_COOKIE } from "@/lib/bff";

const SECURE = ["1", "true", "yes"].includes((process.env.COOKIE_SECURE ?? "").toLowerCase());

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<NextResponse> {
  const body = await req.text();
  try {
    const upstream = await fetch(`${BASE}/masuk`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      cache: "no-store",
    });
    if (!upstream.ok) {
      const text = await upstream.text();
      return new NextResponse(text, {
        status: upstream.status,
        headers: { "content-type": "application/json" },
      });
    }
    const data = (await upstream.json()) as { token?: string; [k: string]: unknown };
    const { token, ...aman } = data;
    const res = NextResponse.json(aman);
    if (token) {
      res.cookies.set(NAMA_COOKIE, token, {
        httpOnly: true,
        sameSite: "lax",
        secure: SECURE,
        path: "/",
        maxAge: 60 * 60 * 24 * 30,
      });
    }
    return res;
  } catch {
    return NextResponse.json(
      { detail: "Tidak bisa menghubungi layanan. Coba lagi sebentar." },
      { status: 502 },
    );
  }
}

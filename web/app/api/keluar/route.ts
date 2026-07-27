// BFF: logout. Cabut sesi di FastAPI lalu hapus cookie. Idempoten — tanpa
// cookie pun tetap membalas 204 & menghapus.
import { NextResponse } from "next/server";

import { BASE, NAMA_COOKIE, ambilToken } from "@/lib/bff";

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<NextResponse> {
  const token = ambilToken(req);
  try {
    if (token) {
      await fetch(`${BASE}/keluar`, {
        method: "POST",
        headers: { authorization: `Bearer ${token}` },
        cache: "no-store",
      });
    }
  } catch {
    /* koneksi backend gagal — cookie tetap kita hapus di bawah */
  }
  const res = new NextResponse(null, { status: 204 });
  res.cookies.set(NAMA_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}

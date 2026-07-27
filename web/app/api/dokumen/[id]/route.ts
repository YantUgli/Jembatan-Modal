// BFF: unduhan dokumen (laporan PDF). Berkasnya di-pipe dari FastAPI internal —
// browser tetap tak pernah bicara langsung ke backend, dan URL FastAPI tak
// pernah bocor ke halaman.
//
// Otorisasinya milik server: FastAPI yang memfilter `business_id` di query dan
// menjawab 404 untuk dokumen tenant lain (aturan #6). Rute ini sengaja TIDAK
// menambah pemeriksaan sendiri — dua tempat memutuskan izin = dua tempat yang
// bisa berbeda pendapat. Di sini hanya `id` dipastikan berupa angka, supaya
// path apa pun yang diketik di URL tak pernah sampai ke backend.
import { NextResponse } from "next/server";

import { BASE, headerAuth } from "@/lib/bff";

export const dynamic = "force-dynamic";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  const { id } = await params;
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: "Dokumen tidak ditemukan." }, { status: 404 });
  }

  try {
    const upstream = await fetch(`${BASE}/dokumen/${id}`, {
      headers: headerAuth(req),
      cache: "no-store",
    });
    if (!upstream.ok) {
      const text = await upstream.text();
      return new NextResponse(text, {
        status: upstream.status,
        headers: { "content-type": "application/json" },
      });
    }
    // Teruskan apa adanya, termasuk nama berkas yang diusulkan backend.
    const teruskan = new Headers();
    for (const k of ["content-type", "content-disposition", "content-length"]) {
      const v = upstream.headers.get(k);
      if (v) teruskan.set(k, v);
    }
    return new NextResponse(upstream.body, { status: 200, headers: teruskan });
  } catch {
    return NextResponse.json(
      { detail: "Tidak bisa menghubungi layanan. Coba lagi sebentar." },
      { status: 502 },
    );
  }
}

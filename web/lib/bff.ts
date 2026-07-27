// Helper bersama Route Handler (BFF). Hanya dipakai di sisi server — jangan
// diimpor dari komponen klien.
//
// Ada karena token sesi hidup di cookie httpOnly: browser tak pernah melihatnya
// dan tak pernah bicara ke FastAPI. Tiap rute BFF harus membaca cookie itu lalu
// meneruskannya sebagai header Bearer. Empat rute menyalin fungsi yang sama
// adalah empat tempat yang bisa menyimpang; nama cookie-nya khususnya cuma boleh
// hidup di satu tempat.

export const BASE = process.env.FASTAPI_URL ?? "http://127.0.0.1:8000";

export const NAMA_COOKIE = "sesi";

export function ambilToken(req: Request): string | undefined {
  const raw = req.headers.get("cookie") ?? "";
  for (const bagian of raw.split(";")) {
    const [k, ...v] = bagian.trim().split("=");
    if (k === NAMA_COOKIE) return decodeURIComponent(v.join("="));
  }
  return undefined;
}

/** Header Authorization bila ada sesi; objek kosong bila tidak (upstream → 401). */
export function headerAuth(req: Request): Record<string, string> {
  const token = ambilToken(req);
  return token ? { authorization: `Bearer ${token}` } : {};
}

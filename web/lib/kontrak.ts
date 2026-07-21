// Cermin TypeScript dari kontrak render Python (`app/kanal/kontrak.py`).
// Satu-satunya sumber kebenaran bentuk tetap di Python; berkas ini menyalin
// bentuknya agar UI bertipe. Bila `VERSI_KONTRAK` naik, sesuaikan di sini.

export const VERSI_KONTRAK = 1;

export type TipeKartu =
  | "sapaan"
  | "narasi"
  | "konfirmasi"
  | "klarifikasi"
  | "untung"
  | "belum_diketahui";

export interface KartuSapaan {
  tipe: "sapaan";
  nama_usaha: string;
  sub: string;
  salam: string;
  ajakan: string;
  catatan_jujur: string;
  teks_alt: string;
}

export interface KartuNarasi {
  tipe: "narasi";
  teks: string;
  aman: boolean;
  teks_alt: string;
}

export interface PilihanKategori {
  nilai: string;
  label: string;
  aktif: boolean;
}

export interface BarisKonfirmasi {
  jenis: string;
  jenis_label: string;
  nominal_tampil: string;
  nominal: string;
  produk: string | null;
  qty_tampil: string | null;
  transaksi_id: number | null;
  kategori_pilihan: PilihanKategori[];
}

export interface KartuKonfirmasi {
  tipe: "konfirmasi";
  baris: BarisKonfirmasi[];
  ids: number[];
  konfirmasi: string;
  teks_alt: string;
}

export interface KartuKlarifikasi {
  tipe: "klarifikasi";
  pertanyaan: string;
  yang_kurang: string[];
  teks_alt: string;
}

export interface KartuUntung {
  tipe: "untung";
  pesan: string;
  status: string;
  teks_alt: string;
}

export interface KartuBelumDiketahui {
  tipe: "belum_diketahui";
  judul: string;
  alasan: string;
  yang_kurang: string[];
  teks_alt: string;
}

export type Kartu =
  | KartuSapaan
  | KartuNarasi
  | KartuKonfirmasi
  | KartuKlarifikasi
  | KartuUntung
  | KartuBelumDiketahui;

export interface PesanKeluar {
  versi: number;
  kartu: Kartu[];
}

// Body yang diterima BFF `/api/chat`.
export type ChatBody =
  | { teks: string }
  | { aksi: "tanya_untung" }
  | { aksi: "koreksi_kategori"; transaksi_id: number; jenis: string };

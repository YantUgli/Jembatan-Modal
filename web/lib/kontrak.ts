// Cermin TypeScript dari kontrak render Python (`app/kanal/kontrak.py`).
// Satu-satunya sumber kebenaran bentuk tetap di Python; berkas ini menyalin
// bentuknya agar UI bertipe. Bila `VERSI_KONTRAK` naik, sesuaikan di sini.

export const VERSI_KONTRAK = 4;

export type TipeKartu =
  | "sapaan"
  | "narasi"
  | "konfirmasi"
  | "klarifikasi"
  | "untung"
  | "keuangan"
  | "resep"
  | "riwayat"
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
  tanggal_tampil?: string | null; // "24 Jul" — hanya di kartu riwayat
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

export interface BarisUntung {
  nama: string;
  jenis: string; // "produksi" | "reseller"
  diketahui: boolean;
  hpp_tampil: string | null;
  satuan_hpp: string | null;
  harga_jual_tampil: string | null;
  laba_kotor_tampil: string | null;
  sebab: string;
  yang_kurang: string[];
}

export interface KartuUntung {
  tipe: "untung";
  pesan: string;
  produk: BarisUntung[];
  cakupan_tampil: string; // "78%"
  status: string; // lengkap | sebagian | belum_diketahui
  teks_alt: string;
}

export interface BarisPos {
  kategori: string;
  jenis: string; // "pengeluaran" | "operasional"
  nominal_tampil: string;
}

export interface KartuKeuangan {
  tipe: "keuangan";
  periode_tampil: string;
  omzet_tampil: string;
  belanja_tampil: string;
  operasional_tampil: string;
  biaya_tampil: string;
  laba_bersih_tampil: string;
  untung: boolean;
  ada_data: boolean;
  cakupan_tampil: string; // "78%"
  prive_tampil: string | null;
  rasio_prive_tampil: string | null;
  pos_biaya: BarisPos[];
  catatan: string[];
  teks_alt: string;
}

export interface MenungguHarga {
  product_id: number;
  bahan: string;
}

export interface KartuResep {
  tipe: "resep";
  product_id: number;
  nama: string;
  status: string; // "lengkap" | "belum"
  konfirmasi: string;
  modal_tampil: string | null;
  satuan_hpp: string | null;
  bahan_perlu_harga: string[];
  menunggu: MenungguHarga | null;
  teks_alt: string;
}

export interface KartuRiwayat {
  tipe: "riwayat";
  baris: BarisKonfirmasi[];
  judul: string;
  pesan: string;
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
  | KartuKeuangan
  | KartuResep
  | KartuRiwayat
  | KartuBelumDiketahui;

export interface PesanKeluar {
  versi: number;
  kartu: Kartu[];
}

// Token kelanjutan tanya-jawab harga: dibawa klien dari `KartuResep.menunggu`
// ke pesan jawaban berikutnya. Server memvalidasi ulang `product_id` milik
// tenant (aturan #6) — klien tak tepercaya.
export interface KonteksTunggu {
  jenis: "harga_bahan";
  product_id: number;
  bahan: string;
}

// Body yang diterima BFF `/api/chat`.
export type ChatBody =
  | { teks: string; konteks?: KonteksTunggu }
  | { aksi: "tanya_untung" }
  | { aksi: "tanya_keuangan" }
  | { aksi: "lihat_transaksi" }
  | { aksi: "koreksi_kategori"; transaksi_id: number; jenis: string };

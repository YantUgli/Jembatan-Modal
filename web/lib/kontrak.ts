// Cermin TypeScript dari kontrak render Python (`app/kanal/kontrak.py`).
// Satu-satunya sumber kebenaran bentuk tetap di Python; berkas ini menyalin
// bentuknya agar UI bertipe. Bila `VERSI_KONTRAK` naik, sesuaikan di sini.

export const VERSI_KONTRAK = 8;

export type TipeKartu =
  | "sapaan"
  | "narasi"
  | "konfirmasi"
  | "klarifikasi"
  | "untung"
  | "keuangan"
  | "resep"
  | "riwayat"
  | "dokumen"
  | "impor"
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
  // Jalur koreksi: baris lama yang ditandai batal (buku append-only). Dipakai
  // untuk mengganti/menghapus baris itu di kartu riwayat yang sudah tergambar.
  // `baris` kosong + `dibatalkan_id` terisi = dihapus tanpa pengganti.
  dibatalkan_id?: number | null;
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
  // Wajib sejak VERSI 8: cakupan HPP cuma bermakna untuk satu rentang tanggal,
  // dan harga jual yang dipakai mengikuti akhir periode.
  periode_tampil: string;
  produk: BarisUntung[];
  cakupan_tampil: string; // "78%"
  status: string; // lengkap | sebagian | belum_diketahui
  periode_label: string; // bentuk mesin; menandai chip mana yang aktif
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
  periode_label: string;
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
  // Kosong = daftar tak berfilter (N terakhir keseluruhan), bukan bulan berjalan.
  periode_tampil: string;
  periode_label: string;
  teks_alt: string;
}

export interface BarisRingkas {
  label: string;
  nilai_tampil: string;
}

export interface KartuDokumen {
  tipe: "dokumen";
  judul: string;
  periode_tampil: string;
  url_unduh: string; // rute BFF, bukan URL FastAPI — browser tak pernah ke sana
  pesan: string;
  ringkasan: BarisRingkas[];
  catatan: string[];
  teks_alt: string;
}

export interface BarisImpor {
  row_id: number;
  raw: string; // tulisan asli pengguna — selalu digambar
  status: string; // draft | diterima | ditolak
  terbaca: boolean;
  ragu: boolean;
  tersimpan: boolean;
  catatan: string;
  yang_kurang: string[];
  jenis: string | null;
  jenis_label: string | null;
  nominal_tampil: string | null; // null = tak terbaca, BUKAN "Rp0"
  tanggal_tampil: string | null;
  produk: string | null;
  qty_tampil: string | null;
}

// Peninjau impor. `jumlah_tersimpan === 0` berarti benar-benar belum ada yang
// masuk buku — UI tidak boleh menggambarnya seolah sudah tersimpan (aturan #3).
export interface KartuImpor {
  tipe: "impor";
  import_id: number;
  judul: string;
  pesan: string;
  baris: BarisImpor[];
  jumlah: number;
  jumlah_terbaca: number;
  jumlah_ragu: number;
  jumlah_gagal: number;
  jumlah_diterima: number;
  jumlah_tersimpan: number;
  jumlah_menunggu: number;
  selesai: boolean;
  catatan: string[];
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
  | KartuDokumen
  | KartuImpor
  | KartuBelumDiketahui;

export interface PesanKeluar {
  versi: number;
  kartu: Kartu[];
}

// Token kelanjutan yang dibawa klien ke pesan berikutnya:
// - "harga_bahan" — jawaban atas "Harga X berapa?" (dari `KartuResep.menunggu`);
// - "koreksi_sasaran" — baris riwayat yang ditunjuk lewat tombol "Betulkan".
// Server memvalidasi ulang id-nya milik tenant (aturan #6) — klien tak tepercaya.
export type KonteksTunggu =
  | { jenis: "harga_bahan"; product_id: number; bahan: string }
  | { jenis: "koreksi_sasaran"; transaksi_id: number };

// Body yang diterima BFF `/api/chat`.
export type ChatBody =
  | { teks: string; konteks?: KonteksTunggu }
  // `periode` = label dari chip kartu ("bulan_lalu", "3_bulan", "bulan:2026-06").
  // Klien tak pernah menghitung kalender sendiri: tanggalnya diselesaikan server
  // dari label yang sama yang dipakai jalur kalimat, jadi chip & kalimat tak bisa
  // berbeda tafsir. Label asing dijawab 422, bukan diam-diam default.
  | { aksi: "tanya_untung"; periode?: string }
  | { aksi: "tanya_keuangan"; periode?: string }
  | { aksi: "lihat_transaksi"; periode?: string }
  // Laporan dijangkau lewat aksi terstruktur, bukan kalimat: "laporan singkat
  // dong" sudah berarti `tanya_keuangan` (kartu di layar), dan membuat PDF
  // adalah tindakan sengaja.
  | { aksi: "buat_laporan" }
  | { aksi: "koreksi_kategori"; transaksi_id: number; jenis: string }
  // Peninjau impor. Tempelan banyak baris masuk lewat `teks` biasa — server yang
  // membelokkannya ke jalur draft, supaya tak ada cara mengirim tempelan yang
  // melewati peninjauan (aturan #3).
  | { aksi: "impor_tinjau"; import_id: number }
  | { aksi: "impor_putuskan"; import_id: number; row_id: number; terima: boolean }
  | { aksi: "impor_terima_yakin"; import_id: number }
  | { aksi: "impor_konfirmasi"; import_id: number };

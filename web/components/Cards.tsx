// Komponen kartu — tiap satu membaca SATU bentuk data kontrak. Presentasional:
// tak ada fetch, tak ada aritmatika. Angka datang apa adanya dari kontrak.
import type {
  BarisImpor,
  BarisKonfirmasi,
  BarisUntung,
  KartuBelumDiketahui,
  KartuDokumen,
  KartuImpor,
  KartuKeuangan,
  KartuKlarifikasi,
  KartuKonfirmasi,
  KartuNarasi,
  KartuResep,
  KartuRiwayat,
  KartuSkor,
  KartuUntung,
} from "@/lib/kontrak";
import { Mark } from "./Brand";

export function NarasiView({ kartu }: { kartu: KartuNarasi }) {
  return (
    <div className="bubble-bot">
      <Mark className="avatar" />
      <div className="teks">{kartu.teks}</div>
    </div>
  );
}

function BarisView({
  baris,
  onKoreksi,
  onBetulkan,
  ditunjuk = false,
  sibuk,
}: {
  baris: BarisKonfirmasi;
  onKoreksi: (transaksiId: number, jenis: string) => void;
  // Ada hanya di daftar riwayat: menunjuk baris ini sebagai sasaran koreksi
  // bebas (nominal/tanggal/hapus), di luar yang bisa dicapai chip kategori.
  onBetulkan?: (transaksiId: number) => void;
  ditunjuk?: boolean;
  sibuk: boolean;
}) {
  const rincian = [baris.produk, baris.qty_tampil].filter(Boolean).join(" · ");
  return (
    <div className={ditunjuk ? "baris-ditunjuk" : undefined}>
      <div className="nominal-blok">
        <span className="badge">{baris.jenis_label}</span>
        {baris.tanggal_tampil && <span className="baris-tgl">{baris.tanggal_tampil}</span>}
        {onBetulkan && baris.transaksi_id != null && (
          <button
            className="betulkan"
            type="button"
            disabled={sibuk}
            onClick={() => onBetulkan(baris.transaksi_id as number)}
          >
            Betulkan
          </button>
        )}
        <div className="nominal">{baris.nominal_tampil}</div>
        {rincian && <div className="rincian">{rincian}</div>}
      </div>
      <div className="chips-label">Jenisnya — ketuk kalau keliru</div>
      <div className="chips">
        {baris.kategori_pilihan.map((c) => (
          <button
            key={c.nilai}
            className={`chip${c.aktif ? " aktif" : ""}`}
            disabled={sibuk || c.aktif || baris.transaksi_id == null}
            onClick={() =>
              baris.transaksi_id != null && onKoreksi(baris.transaksi_id, c.nilai)
            }
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function KonfirmasiView({
  kartu,
  onKoreksi,
  sibuk,
}: {
  kartu: KartuKonfirmasi;
  onKoreksi: (transaksiId: number, jenis: string) => void;
  sibuk: boolean;
}) {
  // Tiga bunyi dari satu bentuk: pencatatan baru, koreksi (ada penggantinya),
  // dan pembatalan (tak ada baris tersisa — tampilkan kalimat konfirmasi dari
  // server supaya pengguna melihat apa yang hilang, bukan kartu kosong).
  const dikoreksi = kartu.dibatalkan_id != null;
  const dibatalkan = dikoreksi && kartu.baris.length === 0;
  return (
    <div className="kartu">
      <div className="k-head">
        {!dibatalkan && <div className="k-check" aria-hidden />}
        <span className="label">
          {dibatalkan ? "Sudah dihapus" : dikoreksi ? "Sudah dibetulkan" : "Tercatat ya, Bu"}
        </span>
      </div>
      {dibatalkan ? (
        <p className="kartu-catatan">{kartu.konfirmasi}</p>
      ) : (
        kartu.baris.map((b, i) => (
          <div key={b.transaksi_id ?? i}>
            {i > 0 && <div className="baris-pisah" />}
            <BarisView baris={b} onKoreksi={onKoreksi} sibuk={sibuk} />
          </div>
        ))
      )}
    </div>
  );
}

// Chip periode. Labelnya dikirim apa adanya ke server, yang menghitung
// tanggalnya — klien tak pernah berhitung kalender sendiri, jadi chip dan
// kalimat ("untung bulan lalu berapa") tak bisa berbeda tafsir.
const PERIODE: { label: string; teks: string }[] = [
  { label: "bulan_ini", teks: "Bulan ini" },
  { label: "bulan_lalu", teks: "Bulan lalu" },
  { label: "3_bulan", teks: "3 bulan" },
];

function PeriodeChips({
  aktif,
  onPilih,
  sibuk,
  semua,
}: {
  aktif: string;
  onPilih: (label: string) => void;
  sibuk: boolean;
  // Chip "Terakhir" (tanpa periode) — hanya untuk riwayat, yang defaultnya
  // memang tak berfilter. Tanpa ini pengguna tak punya jalan kembali.
  semua?: boolean;
}) {
  const daftar = semua ? [{ label: "", teks: "Terakhir" }, ...PERIODE] : PERIODE;
  return (
    <div className="periode-chips" role="group" aria-label="Pilih periode">
      {daftar.map((p) => (
        <button
          key={p.label || "semua"}
          type="button"
          className={`periode-chip${p.label === aktif ? " aktif" : ""}`}
          disabled={sibuk || p.label === aktif}
          aria-pressed={p.label === aktif}
          onClick={() => onPilih(p.label)}
        >
          {p.teks}
        </button>
      ))}
    </div>
  );
}

export function RiwayatView({
  kartu,
  onKoreksi,
  onBetulkan,
  onPeriode,
  ditunjuk,
  sibuk,
}: {
  kartu: KartuRiwayat;
  onKoreksi: (transaksiId: number, jenis: string) => void;
  onBetulkan: (transaksiId: number) => void;
  onPeriode?: (label: string) => void;
  ditunjuk: number | null;
  sibuk: boolean;
}) {
  // Daftar catatan terakhir — baris memakai ulang BarisView, jadi tiap baris
  // bisa dibetulkan kategorinya di tempat (jalur koreksi_kategori) atau ditunjuk
  // untuk koreksi bebas lewat kalimat. Kosong → pesan jujur, bukan baris palsu
  // (aturan #2).
  return (
    <div className="kartu">
      <div className="k-head">
        <span className="label">{kartu.judul}</span>
        {kartu.periode_tampil && <span className="keu-periode">{kartu.periode_tampil}</span>}
      </div>
      {kartu.baris.length > 0 ? (
        kartu.baris.map((b, i) => (
          <div key={b.transaksi_id ?? i}>
            {i > 0 && <div className="baris-pisah" />}
            <BarisView
              baris={b}
              onKoreksi={onKoreksi}
              onBetulkan={onBetulkan}
              ditunjuk={b.transaksi_id != null && b.transaksi_id === ditunjuk}
              sibuk={sibuk}
            />
          </div>
        ))
      ) : (
        <div className="belum-kotak" style={{ marginTop: 12 }}>
          <div className="belum-nilai">belum ada catatan</div>
        </div>
      )}
      <p className="kartu-catatan">{kartu.pesan}</p>
      {onPeriode && (
        <PeriodeChips aktif={kartu.periode_label} onPilih={onPeriode} sibuk={sibuk} semua />
      )}
    </div>
  );
}

export function KlarifikasiView({ kartu }: { kartu: KartuKlarifikasi }) {
  return (
    <div className="kartu-amber">
      <div className="amber-head">
        <div className="amber-dot" aria-hidden />
        <span className="label">Boleh dilengkapi dulu</span>
      </div>
      <p className="amber-teks">{kartu.pertanyaan}</p>
    </div>
  );
}

export function BelumDiketahuiView({ kartu }: { kartu: KartuBelumDiketahui }) {
  return (
    <div className="kartu-amber">
      <div className="amber-head">
        <div className="amber-dot" aria-hidden />
        <span className="label">Belum bisa dipastikan, Bu</span>
      </div>
      <div className="belum-kotak">
        <div className="belum-kap">{kartu.judul}</div>
        <div className="belum-nilai">belum diketahui</div>
      </div>
      <p className="amber-teks">{kartu.alasan}</p>
      {kartu.yang_kurang.length > 0 && (
        <div className="kurang">
          {kartu.yang_kurang.map((k) => (
            <span key={k}>{k}</span>
          ))}
        </div>
      )}
    </div>
  );
}

const JENIS_LABEL: Record<string, string> = {
  produksi: "diolah",
  reseller: "kulakan",
};

function BarisUntungView({ b }: { b: BarisUntung }) {
  if (b.diketahui) {
    return (
      <div className="u-row">
        <div className="u-kepala">
          <span className="u-nama">{b.nama}</span>
          <span className="u-badge">{JENIS_LABEL[b.jenis] ?? b.jenis}</span>
        </div>
        <div className="u-laba">
          {b.laba_kotor_tampil}
          <span className="u-porsi"> / porsi</span>
        </div>
        <div className="u-modal">
          modal bahan {b.hpp_tampil}
          {b.harga_jual_tampil ? ` · jual ${b.harga_jual_tampil}` : ""}
        </div>
      </div>
    );
  }
  // Belum diketahui → jujur, bukan angka (aturan #2).
  return (
    <div className="u-row u-row-kurang">
      <div className="u-kepala">
        <span className="u-nama">{b.nama}</span>
        <span className="u-badge">{JENIS_LABEL[b.jenis] ?? b.jenis}</span>
      </div>
      <div className="u-belum">belum diketahui</div>
      <div className="u-sebab">{b.sebab}</div>
      {b.yang_kurang.length > 0 && (
        <div className="kurang">
          {b.yang_kurang.map((k) => (
            <span key={k}>{k}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function UntungView({
  kartu,
  onPeriode,
  sibuk = false,
}: {
  kartu: KartuUntung;
  onPeriode?: (label: string) => void;
  sibuk?: boolean;
}) {
  // Kualifikasi "laba kotor dari bahan" ditonjolkan; ⛔ tak pernah dilabeli
  // "untung usaha" (itu kartu keuangan). Angka datang apa adanya dari kontrak.
  // Periode digambar sejak VERSI 8: cakupan di bawah & harga jual yang dipakai
  // keduanya bergantung rentang ini.
  return (
    <div className="kartu">
      <div className="keu-head">
        <span className="untung-kap">Untung kotor dari bahan · per porsi</span>
        <span className="keu-periode">{kartu.periode_tampil}</span>
      </div>
      {kartu.produk.length > 0 ? (
        <div className="untung-list">
          {kartu.produk.map((b) => (
            <BarisUntungView key={b.nama} b={b} />
          ))}
        </div>
      ) : (
        <div className="belum-kotak" style={{ marginTop: 12 }}>
          <div className="belum-nilai">belum ada produk</div>
        </div>
      )}
      {kartu.cakupan_tampil && (
        <span className="untung-pill">
          Modal terhitung untuk {kartu.cakupan_tampil} penjualan
        </span>
      )}
      <p className="kartu-catatan">{kartu.pesan}</p>
      {onPeriode && (
        <PeriodeChips aktif={kartu.periode_label} onPilih={onPeriode} sibuk={sibuk} />
      )}
    </div>
  );
}

export function ResepView({ kartu }: { kartu: KartuResep }) {
  // Modal per porsi (⛔ bukan "untung usaha" — aturan #9). Bila belum lengkap,
  // jujur menyebut bahan yang harganya kurang & bertanya (aturan #2).
  if (kartu.status === "lengkap") {
    return (
      <div className="kartu">
        <div className="k-head">
          <div className="k-check" aria-hidden />
          <span className="label">Resep tercatat</span>
        </div>
        <div className="resep-nama">{kartu.nama}</div>
        <div className="resep-modal">
          {kartu.modal_tampil}
          <span className="u-porsi"> / {kartu.satuan_hpp ?? "porsi"} modal bikin</span>
        </div>
        <p className="kartu-catatan">{kartu.konfirmasi}</p>
      </div>
    );
  }
  return (
    <div className="kartu-amber">
      <div className="amber-head">
        <div className="amber-dot" aria-hidden />
        <span className="label">Resep tercatat — modal belum lengkap</span>
      </div>
      <div className="resep-nama">{kartu.nama}</div>
      <p className="amber-teks">{kartu.konfirmasi}</p>
      {kartu.bahan_perlu_harga.length > 0 && (
        <div className="kurang">
          {kartu.bahan_perlu_harga.map((b) => (
            <span key={b}>{b}</span>
          ))}
        </div>
      )}
      {kartu.menunggu && (
        <p className="amber-teks">
          Harga {kartu.menunggu.bahan} berapa, Bu? Balas saja, misalnya “
          {kartu.menunggu.bahan} sekilo 20rb”.
        </p>
      )}
    </div>
  );
}

export function KeuanganView({
  kartu,
  onBuatLaporan,
  onLihatSkor,
  onPeriode,
  sibuk = false,
}: {
  kartu: KartuKeuangan;
  // Tombol laporan hanya muncul kalau pemanggil menyediakan aksinya. Sengaja
  // tombol, bukan kalimat: "laporan singkat dong" sudah berarti kartu ini.
  onBuatLaporan?: () => void;
  // Rapor usaha — jalan masuk `tanya_skor`. Alasan yang sama dengan laporan:
  // aksi terstruktur, bukan label router.
  onLihatSkor?: () => void;
  onPeriode?: (label: string) => void;
  sibuk?: boolean;
}) {
  if (!kartu.ada_data) {
    return (
      <div className="kartu-amber">
        <div className="amber-head">
          <div className="amber-dot" aria-hidden />
          <span className="label">Laporan singkat</span>
        </div>
        <p className="amber-teks">Belum ada catatan untuk {kartu.periode_tampil}.</p>
        {/* Periode kosong justru saat chip paling dibutuhkan — jangan
            sembunyikan jalan keluarnya di kartu yang tak berdata. */}
        {onPeriode && (
          <PeriodeChips aktif={kartu.periode_label} onPilih={onPeriode} sibuk={sibuk} />
        )}
      </div>
    );
  }
  return (
    <div className="kartu">
      <div className="keu-head">
        <span className="keu-kap">Untung usaha</span>
        <span className="keu-periode">{kartu.periode_tampil}</span>
      </div>
      <div className={`keu-laba${kartu.untung ? "" : " rugi"}`}>
        {kartu.laba_bersih_tampil}
      </div>
      <div className="keu-rumus">
        omzet {kartu.omzet_tampil} − biaya {kartu.biaya_tampil}
      </div>

      <div className="keu-grid">
        <div>
          <div className="keu-lab">Pemasukan</div>
          <div className="keu-val">{kartu.omzet_tampil}</div>
        </div>
        <div>
          <div className="keu-lab">Belanja barang</div>
          <div className="keu-val">{kartu.belanja_tampil}</div>
        </div>
        <div>
          <div className="keu-lab">Biaya warung</div>
          <div className="keu-val">{kartu.operasional_tampil}</div>
        </div>
        {kartu.prive_tampil && (
          <div>
            <div className="keu-lab">Dipakai pribadi</div>
            <div className="keu-val keu-prive">
              {kartu.prive_tampil}
              {kartu.rasio_prive_tampil ? ` (${kartu.rasio_prive_tampil})` : ""}
            </div>
          </div>
        )}
      </div>

      {kartu.cakupan_tampil && (
        <span className="untung-pill">
          Modal bahan terhitung untuk {kartu.cakupan_tampil} penjualan
        </span>
      )}

      {kartu.pos_biaya.length > 0 && (
        <div className="keu-pos">
          <div className="keu-pos-kap">Pengeluaran terbesar</div>
          {kartu.pos_biaya.map((p, i) => (
            <div className="keu-pos-row" key={`${p.kategori}-${i}`}>
              <span>{p.kategori}</span>
              <span>{p.nominal_tampil}</span>
            </div>
          ))}
        </div>
      )}

      {kartu.catatan.map((c, i) => (
        <p className="kartu-catatan" key={i}>
          {c}
        </p>
      ))}

      {onPeriode && (
        <PeriodeChips aktif={kartu.periode_label} onPilih={onPeriode} sibuk={sibuk} />
      )}

      {onLihatSkor && (
        <button className="btn-kartu btn-halus" type="button" disabled={sibuk} onClick={onLihatSkor}>
          Lihat rapor usaha
        </button>
      )}

      {onBuatLaporan && (
        <button className="btn-kartu" type="button" disabled={sibuk} onClick={onBuatLaporan}>
          {sibuk ? "Menyiapkan laporan…" : "Buat laporan PDF"}
        </button>
      )}
    </div>
  );
}

// Rapor usaha. ⛔ Aturan #9: kartu ini untuk PENGGUNA. Angkanya tak pernah
// dibawa ke laporan PDF / proposal KUR — jangan pernah menyalin `skor_total`
// ke permukaan yang dibaca penyalur.
export function SkorView({
  kartu,
  onPeriode,
  sibuk = false,
}: {
  kartu: KartuSkor;
  onPeriode?: (label: string) => void;
  sibuk?: boolean;
}) {
  return (
    <div className="kartu">
      <div className="keu-head">
        <span className="keu-kap">Rapor usaha</span>
        <span className="keu-periode">{kartu.periode_tampil}</span>
      </div>

      <div className="skor-angka">{kartu.skor_tampil}</div>
      {kartu.delta_tampil && <div className="skor-delta">{kartu.delta_tampil}</div>}

      <div className="skor-komponen">
        {kartu.komponen.map((k) => (
          <div className="skor-row" key={k.kunci}>
            <div className="skor-row-head">
              <span className="skor-lab">{k.label}</span>
              {/* `nilai === null` ≠ 0: yang satu belum dinilai, yang satu
                  dinilai nol. Menggambarnya sama = mengarang penilaian. */}
              <span className={`skor-nilai${k.nilai === null ? " belum" : ""}`}>
                {k.nilai === null ? "belum dinilai" : `${k.nilai}/${k.bobot}`}
              </span>
            </div>
            {k.nilai === null ? (
              <div className="skor-bar-kosong" aria-hidden />
            ) : (
              <div className="skor-bar" aria-hidden>
                <span style={{ width: `${Math.round((k.nilai / k.bobot) * 100)}%` }} />
              </div>
            )}
            <p className="skor-sebab">{k.nilai === null ? k.sebab : k.rincian_tampil}</p>
          </div>
        ))}
      </div>

      {kartu.cakupan_tampil && (
        <span className="untung-pill">
          Modal bahan terhitung untuk {kartu.cakupan_tampil} penjualan
        </span>
      )}

      {kartu.catatan.map((c, i) => (
        <p className="kartu-catatan" key={i}>
          {c}
        </p>
      ))}

      {onPeriode && (
        <PeriodeChips aktif={kartu.periode_label} onPilih={onPeriode} sibuk={sibuk} />
      )}
    </div>
  );
}

function BarisImporView({
  b,
  onPutuskan,
  sibuk,
}: {
  b: BarisImpor;
  onPutuskan: (rowId: number, terima: boolean) => void;
  sibuk: boolean;
}) {
  // Tulisan asli SELALU digambar, di atas tafsir kami. Tanpa itu, "meninjau"
  // hanya berarti mempercayai kami dua kali.
  const rincian = [b.produk, b.qty_tampil].filter(Boolean).join(" · ");
  const kelas = b.tersimpan
    ? "imp-row imp-tersimpan"
    : b.status === "diterima"
      ? "imp-row imp-dicentang"
      : b.status === "ditolak"
        ? "imp-row imp-ditolak"
        : "imp-row";

  return (
    <div className={kelas}>
      <div className="imp-raw">{b.raw}</div>

      {b.terbaca ? (
        <div className="imp-tafsir">
          <span className="badge">{b.jenis_label}</span>
          {b.tanggal_tampil && <span className="baris-tgl">{b.tanggal_tampil}</span>}
          <div className="nominal">{b.nominal_tampil}</div>
          {rincian && <div className="rincian">{rincian}</div>}
        </div>
      ) : (
        // ⛔ Tak terbaca → tak ada angka sama sekali (aturan #2), bukan "Rp0".
        <div className="imp-tafsir">
          <div className="belum-nilai">tidak terbaca</div>
        </div>
      )}

      {b.catatan && (
        <p className={b.ragu || !b.terbaca ? "imp-catatan imp-tanda" : "imp-catatan"}>
          {b.catatan}
        </p>
      )}

      {b.tersimpan ? (
        <div className="imp-status">Sudah masuk buku</div>
      ) : (
        <div className="chips">
          <button
            className={`chip${b.status === "diterima" ? " aktif" : ""}`}
            type="button"
            // Baris tak terbaca tak bisa dicentang: tak ada yang bisa disimpan.
            disabled={sibuk || !b.terbaca}
            onClick={() => onPutuskan(b.row_id, true)}
          >
            Benar
          </button>
          <button
            className={`chip${b.status === "ditolak" ? " aktif" : ""}`}
            type="button"
            disabled={sibuk}
            onClick={() => onPutuskan(b.row_id, false)}
          >
            Lewati
          </button>
        </div>
      )}
    </div>
  );
}

export function ImporView({
  kartu,
  onPutuskan,
  onTerimaYakin,
  onKonfirmasi,
  sibuk = false,
}: {
  kartu: KartuImpor;
  onPutuskan: (rowId: number, terima: boolean) => void;
  onTerimaYakin: () => void;
  onKonfirmasi: () => void;
  sibuk?: boolean;
}) {
  // Peninjau impor (aturan #3). Selama `jumlah_tersimpan === 0` kartu ini TIDAK
  // boleh terbaca seperti konfirmasi pencatatan — karena itu ia amber, bukan
  // hijau bercentang: tak ada apa pun yang sudah masuk buku.
  const adaYangBisaDisimpan = kartu.jumlah_diterima > 0;
  const bisaBorongan = kartu.jumlah_menunggu > 0 && kartu.jumlah_terbaca > kartu.jumlah_ragu;

  return (
    <div className={kartu.jumlah_tersimpan > 0 ? "kartu" : "kartu-amber"}>
      <div className={kartu.jumlah_tersimpan > 0 ? "k-head" : "amber-head"}>
        {kartu.jumlah_tersimpan > 0 ? (
          <div className="k-check" aria-hidden />
        ) : (
          <div className="amber-dot" aria-hidden />
        )}
        <span className="label">{kartu.judul}</span>
      </div>

      <p className={kartu.jumlah_tersimpan > 0 ? "kartu-teks" : "amber-teks"}>{kartu.pesan}</p>

      <div className="imp-list">
        {kartu.baris.map((b) => (
          <BarisImporView key={b.row_id} b={b} onPutuskan={onPutuskan} sibuk={sibuk} />
        ))}
      </div>

      {!kartu.selesai && (
        <div className="imp-aksi">
          {bisaBorongan && (
            <button className="btn-kartu btn-halus" type="button" disabled={sibuk} onClick={onTerimaYakin}>
              Centang yang sudah jelas
            </button>
          )}
          <button
            className="btn-kartu"
            type="button"
            disabled={sibuk || !adaYangBisaDisimpan}
            onClick={onKonfirmasi}
          >
            {sibuk
              ? "Menyimpan…"
              : adaYangBisaDisimpan
                ? `Simpan ${kartu.jumlah_diterima} catatan`
                : "Centang dulu yang benar"}
          </button>
        </div>
      )}

      {kartu.catatan.map((c, i) => (
        <p className="kartu-catatan" key={i}>
          {c}
        </p>
      ))}
    </div>
  );
}

export function DokumenView({ kartu }: { kartu: KartuDokumen }) {
  return (
    <div className="kartu">
      <div className="keu-head">
        <span className="keu-kap">{kartu.judul}</span>
        <span className="keu-periode">{kartu.periode_tampil}</span>
      </div>
      <p className="kartu-teks">{kartu.pesan}</p>

      {kartu.ringkasan.length > 0 && (
        <div className="keu-grid">
          {kartu.ringkasan.map((b) => (
            <div key={b.label}>
              <div className="keu-lab">{b.label}</div>
              <div className="keu-val">{b.nilai_tampil}</div>
            </div>
          ))}
        </div>
      )}

      {/* Unduhan lewat rute BFF; `download` supaya HP langsung menyimpannya
          alih-alih membuka penampil PDF bawaan yang kadang tak punya tombol simpan. */}
      <a className="btn-kartu" href={kartu.url_unduh} download>
        Unduh laporan (PDF)
      </a>

      {kartu.catatan.map((c, i) => (
        <p className="kartu-catatan" key={i}>
          {c}
        </p>
      ))}
    </div>
  );
}

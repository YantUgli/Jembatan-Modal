// Komponen kartu — tiap satu membaca SATU bentuk data kontrak. Presentasional:
// tak ada fetch, tak ada aritmatika. Angka datang apa adanya dari kontrak.
import type {
  BarisKonfirmasi,
  KartuBelumDiketahui,
  KartuKlarifikasi,
  KartuKonfirmasi,
  KartuNarasi,
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
  sibuk,
}: {
  baris: BarisKonfirmasi;
  onKoreksi: (transaksiId: number, jenis: string) => void;
  sibuk: boolean;
}) {
  const rincian = [baris.produk, baris.qty_tampil].filter(Boolean).join(" · ");
  return (
    <div>
      <div className="nominal-blok">
        <span className="badge">{baris.jenis_label}</span>
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
  return (
    <div className="kartu">
      <div className="k-head">
        <div className="k-check" aria-hidden />
        <span className="label">Tercatat ya, Bu</span>
      </div>
      {kartu.baris.map((b, i) => (
        <div key={b.transaksi_id ?? i}>
          {i > 0 && <div className="baris-pisah" />}
          <BarisView baris={b} onKoreksi={onKoreksi} sibuk={sibuk} />
        </div>
      ))}
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

export function UntungView({ kartu }: { kartu: KartuUntung }) {
  // Stub jujur. Framing yang benar sudah tertanam untuk saat di-wire: kualifikasi
  // "laba kotor dari bahan" ditonjolkan, tak ada angka besar yang menyesatkan.
  return (
    <div className="kartu-amber">
      <div className="untung-kap">Untung dari bahan</div>
      <div className="belum-kotak" style={{ marginTop: 10 }}>
        <div className="belum-kap">Laba kotor per porsi</div>
        <div className="belum-nilai">belum tersambung</div>
      </div>
      <p className="amber-teks">{kartu.pesan}</p>
      <span className="untung-pill">Nanti: laba kotor dari bahan, bukan untung bersih</span>
    </div>
  );
}

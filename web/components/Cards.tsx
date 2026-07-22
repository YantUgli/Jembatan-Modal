// Komponen kartu — tiap satu membaca SATU bentuk data kontrak. Presentasional:
// tak ada fetch, tak ada aritmatika. Angka datang apa adanya dari kontrak.
import type {
  BarisKonfirmasi,
  BarisUntung,
  KartuBelumDiketahui,
  KartuKeuangan,
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

export function UntungView({ kartu }: { kartu: KartuUntung }) {
  // Kualifikasi "laba kotor dari bahan" ditonjolkan; ⛔ tak pernah dilabeli
  // "untung usaha" (itu kartu keuangan). Angka datang apa adanya dari kontrak.
  return (
    <div className="kartu">
      <div className="untung-kap">Untung kotor dari bahan · per porsi</div>
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
    </div>
  );
}

export function KeuanganView({ kartu }: { kartu: KartuKeuangan }) {
  if (!kartu.ada_data) {
    return (
      <div className="kartu-amber">
        <div className="amber-head">
          <div className="amber-dot" aria-hidden />
          <span className="label">Laporan singkat</span>
        </div>
        <p className="amber-teks">Belum ada catatan untuk {kartu.periode_tampil}.</p>
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
    </div>
  );
}

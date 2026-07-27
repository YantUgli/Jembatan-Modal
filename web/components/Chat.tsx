"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ambilSesi, ApiError, keluar, kirimChat, masuk } from "@/lib/api";
import type {
  BarisKonfirmasi,
  ChatBody,
  Kartu,
  KartuSapaan,
  KonteksTunggu,
  PesanKeluar,
} from "@/lib/kontrak";
import { Mark } from "./Brand";
import {
  BelumDiketahuiView,
  DokumenView,
  ImporView,
  KeuanganView,
  SkorView,
  KlarifikasiView,
  KonfirmasiView,
  NarasiView,
  ResepView,
  RiwayatView,
  UntungView,
} from "./Cards";

// Setelah tiap balasan: bila kartu terakhir adalah resep yang menunggu harga
// bahan, bawa token itu ke pesan berikutnya (tanya-jawab multi-turn). Kartu
// lain → tak ada yang ditunggu (pengguna ganti topik → bersihkan).
function menungguDari(kartu: Kartu[]): KonteksTunggu | null {
  for (let i = kartu.length - 1; i >= 0; i--) {
    const k = kartu[i];
    if (k.tipe === "resep") {
      return k.menunggu
        ? { jenis: "harga_bahan", product_id: k.menunggu.product_id, bahan: k.menunggu.bahan }
        : null;
    }
  }
  return null;
}

type Item =
  | { id: number; kind: "user"; teks: string }
  | { id: number; kind: "kartu"; kartu: Kartu };

// Buku transaksi append-only: koreksi/pembatalan membuat baris lama tak berlaku.
// Daftar riwayat yang sudah tergambar diperbarui di tempat supaya catatan yang
// sudah dibetulkan tak terlihat hidup di layar. Gelembung konfirmasi lama
// sengaja dibiarkan — itu catatan percakapan saat itu, bukan daftar berjalan.
function perbaruiRiwayat(
  items: Item[],
  dibatalkanId: number,
  pengganti: BarisKonfirmasi | undefined,
): Item[] {
  return items.map((it) => {
    if (it.kind !== "kartu" || it.kartu.tipe !== "riwayat") return it;
    if (!it.kartu.baris.some((b) => b.transaksi_id === dibatalkanId)) return it;
    const baris = pengganti
      ? it.kartu.baris.map((b) =>
          b.transaksi_id === dibatalkanId
            ? { ...pengganti, tanggal_tampil: pengganti.tanggal_tampil ?? b.tanggal_tampil }
            : b,
        )
      : it.kartu.baris.filter((b) => b.transaksi_id !== dibatalkanId);
    return { ...it, kartu: { ...it.kartu, baris } };
  });
}

// Sebutan chip periode, dipakai untuk menulis gelembung pengguna saat chip
// diketuk — supaya percakapannya terbaca seperti kalimat yang ia ucapkan.
const SEBUTAN_PERIODE: Record<string, string> = {
  "": "Terakhir",
  bulan_ini: "Bulan ini",
  bulan_lalu: "Bulan lalu",
  "3_bulan": "3 bulan terakhir",
};

const JUDUL_AKSI: Record<string, string> = {
  tanya_untung: "Untung per porsi",
  tanya_keuangan: "Laporan singkat",
  lihat_transaksi: "Catatan",
  tanya_skor: "Rapor usaha",
};

const SUGGESTIONS: {
  label: string;
  teks?: string;
  untung?: boolean;
  keuangan?: boolean;
  riwayat?: boolean;
}[] = [
  { label: "laku 5 kotak risol, 75rb", teks: "laku 5 kotak risol tadi, 75rb" },
  { label: "beli minyak 2 liter 38rb", teks: "beli minyak goreng 2 liter 38rb" },
  { label: "Untung per porsi?", untung: true },
  { label: "Laporan singkat", keuangan: true },
  { label: "Catatan terakhir", riwayat: true },
  // Lewat `teks` biasa, bukan chip: yang diuji di sini justru jalur kalimat —
  // periode dibaca dari kata-katanya sendiri.
  { label: "Untung bulan lalu?", teks: "untung saya bulan lalu berapa" },
  {
    // Tempelan banyak baris → jalur draft impor. Sengaja dikirim lewat `teks`
    // biasa, sama seperti pengguna menempel dari WhatsApp: tak ada aksi khusus
    // yang bisa melewati peninjauan (aturan #3).
    label: "Tempel catatan buku",
    teks: "12/7 laku 5 kotak risol, 75rb\nbeli minyak 38rb\n13/7 bayar gas 22rb",
  },
];

export default function Chat() {
  const [auth, setAuth] = useState<"memuat" | "masuk" | "siap">("memuat");
  const [screen, setScreen] = useState<"pembuka" | "chat">("pembuka");
  const [sapaan, setSapaan] = useState<KartuSapaan | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [typing, setTyping] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [draft, setDraft] = useState("");
  const [menunggu, setMenunggu] = useState<KonteksTunggu | null>(null);
  const idRef = useRef(0);
  const threadRef = useRef<HTMLDivElement>(null);
  const komposerRef = useRef<HTMLTextAreaElement>(null);

  const nextId = () => ++idRef.current;

  // Kartu pembuka datang dari kontrak (/sesi), bukan hardcode di UI. 401 =
  // belum/kedaluwarsa login → tampilkan layar masuk; error lain → biarkan
  // fallback statis (mis. backend sedang mati) tapi tetap izinkan lanjut.
  const muatSesi = useCallback(() => {
    setAuth("memuat");
    ambilSesi()
      .then((p: PesanKeluar) => {
        const s = p.kartu.find((k) => k.tipe === "sapaan") as KartuSapaan | undefined;
        if (s) setSapaan(s);
        setAuth("siap");
      })
      .catch((e) => {
        setAuth(e instanceof ApiError && e.status === 401 ? "masuk" : "siap");
      });
  }, []);

  useEffect(() => {
    muatSesi();
  }, [muatSesi]);

  // Sesi kedaluwarsa di tengah pemakaian → balik ke layar masuk, bersihkan.
  const bersihkanKeMasuk = useCallback(() => {
    setItems([]);
    setMenunggu(null);
    setSapaan(null);
    setScreen("pembuka");
    setAuth("masuk");
  }, []);

  const keluarSesi = useCallback(async () => {
    try {
      await keluar();
    } catch {
      /* koneksi gagal — tetap perlakukan sebagai keluar di klien */
    }
    bersihkanKeMasuk();
  }, [bersihkanKeMasuk]);

  const sesiHabis = useCallback(
    (e: unknown): boolean => {
      if (e instanceof ApiError && e.status === 401) {
        bersihkanKeMasuk();
        return true;
      }
      return false;
    },
    [bersihkanKeMasuk],
  );

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items, typing]);

  // Textarea tak tumbuh sendiri. Tanpa ini, tempelan 20 baris muncul di kotak
  // satu baris — teknisnya jalan, tapi pengguna tak bisa melihat apa yang ia
  // kirim. Tingginya dibatasi `max-height` di CSS, jadi percakapan tak terdorong
  // keluar layar.
  useEffect(() => {
    const el = komposerRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  const pushKartu = useCallback((kartu: Kartu[]) => {
    setItems((prev) => [
      ...prev,
      ...kartu.map((k) => ({ id: nextId(), kind: "kartu" as const, kartu: k })),
    ]);
  }, []);

  const errorTenang = useCallback(
    (pesan: string) =>
      pushKartu([
        {
          tipe: "narasi",
          teks: pesan,
          aman: true,
          teks_alt: pesan,
        },
      ]),
    [pushKartu],
  );

  const kirimTeks = useCallback(
    async (teks: string) => {
      const t = teks.trim();
      if (!t || sibuk) return;
      setItems((prev) => [...prev, { id: nextId(), kind: "user", teks: t }]);
      setDraft("");
      setSibuk(true);
      setTyping(true);
      try {
        const p = await kirimChat(menunggu ? { teks: t, konteks: menunggu } : { teks: t });
        pushKartu(p.kartu);
        // Koreksi lewat kalimat: baris yang dibatalkan diperbarui di daftar yang
        // sudah tergambar (server yang memberi tahu id-nya, bukan tebakan klien).
        const k = p.kartu[0];
        if (k && k.tipe === "konfirmasi" && k.dibatalkan_id != null) {
          const id = k.dibatalkan_id;
          setItems((prev) => perbaruiRiwayat(prev, id, k.baris[0]));
        }
        setMenunggu(menungguDari(p.kartu));
      } catch (e) {
        if (sesiHabis(e)) return;
        errorTenang(
          e instanceof Error && e.message
            ? `Maaf, belum bisa diproses: ${e.message}`
            : "Maaf, lagi ada gangguan. Coba lagi sebentar ya.",
        );
      } finally {
        setTyping(false);
        setSibuk(false);
      }
    },
    [sibuk, menunggu, pushKartu, errorTenang, sesiHabis],
  );

  // Aksi query (tombol, bukan NL): dorong bubble pengguna lalu render kartunya.
  // `buat_laporan` ikut di sini — membuat dokumen adalah tindakan sengaja, jadi
  // jalannya tombol, bukan kalimat yang harus ditebak router.
  const tanyaAksi = useCallback(
    async (
      aksi:
        | "tanya_untung"
        | "tanya_keuangan"
        | "lihat_transaksi"
        | "tanya_skor"
        | "buat_laporan",
      label: string,
      // Label periode dari chip. Dikirim apa adanya; tanggalnya dihitung server
      // (label asing dijawab 422, jadi tak ada jalan diam-diam salah periode).
      periode?: string,
    ) => {
      if (sibuk) return;
      setMenunggu(null); // aksi tombol = ganti topik, bukan jawaban harga
      setItems((prev) => [...prev, { id: nextId(), kind: "user", teks: label }]);
      setSibuk(true);
      setTyping(true);
      try {
        const p = await kirimChat(
          aksi === "buat_laporan" ? { aksi } : { aksi, ...(periode ? { periode } : {}) },
        );
        pushKartu(p.kartu);
      } catch (e) {
        if (sesiHabis(e)) return;
        // Pesan backend diteruskan bila ada: kegagalan pembuatan PDF punya sebab
        // yang bisa ditindaklanjuti (mis. WeasyPrint belum terpasang), dan
        // menelannya jadi "ada gangguan" membuatnya tak bisa dilacak.
        errorTenang(
          e instanceof ApiError && e.message
            ? `Maaf, belum bisa diproses: ${e.message}`
            : "Maaf, lagi ada gangguan. Coba lagi sebentar ya.",
        );
      } finally {
        setTyping(false);
        setSibuk(false);
      }
    },
    [sibuk, pushKartu, errorTenang, sesiHabis],
  );

  // Ketuk chip periode di kartu → tanya ulang aksi yang sama untuk periode lain.
  // Kartu lama sengaja dibiarkan di layar: ia catatan percakapan saat itu, dan
  // dua kartu berdampingan justru memperlihatkan bedanya antar-periode.
  const tanyaPeriode = useCallback(
    (
      aksi: "tanya_untung" | "tanya_keuangan" | "lihat_transaksi" | "tanya_skor",
      periode: string,
    ) => {
      const kapan = SEBUTAN_PERIODE[periode] ?? "Terakhir";
      tanyaAksi(aksi, `${JUDUL_AKSI[aksi]} · ${kapan}`, periode || undefined);
    },
    [tanyaAksi],
  );

  // Ketuk chip kategori → koreksi. Kartu konfirmasi diperbarui di tempat; untuk
  // kartu riwayat, hanya baris yang dikoreksi yang diganti (append-only → baris
  // pengganti ber-id baru), daftar lainnya tetap.
  const koreksi = useCallback(
    async (itemId: number, transaksiId: number, jenis: string) => {
      if (sibuk) return;
      setSibuk(true);
      try {
        const p = await kirimChat({ aksi: "koreksi_kategori", transaksi_id: transaksiId, jenis });
        const baru = p.kartu[0];
        if (!baru) return;
        if (baru.tipe !== "konfirmasi") {
          pushKartu([baru]);
          return;
        }
        const pengganti = baru.baris[0];
        setItems((prev) =>
          perbaruiRiwayat(prev, transaksiId, pengganti).map((it) =>
            it.id === itemId && it.kind === "kartu" && it.kartu.tipe === "konfirmasi"
              ? { ...it, kartu: baru }
              : it,
          ),
        );
      } catch (e) {
        if (sesiHabis(e)) return;
        errorTenang("Koreksi belum tersimpan — koneksi bermasalah. Coba lagi ya.");
      } finally {
        setSibuk(false);
      }
    },
    [sibuk, pushKartu, errorTenang, sesiHabis],
  );

  // Aksi peninjau impor. Kartunya diperbarui DI TEMPAT, bukan ditumpuk salinan
  // baru: peninjauan adalah satu papan kerja yang berubah, dan menumpuk salinan
  // membuat pengguna tak tahu papan mana yang berlaku — di layar yang memutuskan
  // apa yang masuk buku, itu berbahaya, bukan cuma berantakan.
  const aksiImpor = useCallback(
    async (itemId: number, body: ChatBody) => {
      if (sibuk) return;
      setSibuk(true);
      try {
        const p = await kirimChat(body);
        const baru = p.kartu[0];
        if (!baru) return;
        if (baru.tipe !== "impor") {
          // Draft tak ketemu (mis. sesi lain) → kartu klarifikasi, tampilkan apa adanya.
          pushKartu([baru]);
          return;
        }
        setItems((prev) =>
          prev.map((it) =>
            it.id === itemId && it.kind === "kartu" && it.kartu.tipe === "impor"
              ? { ...it, kartu: baru }
              : it,
          ),
        );
      } catch (e) {
        if (sesiHabis(e)) return;
        errorTenang(
          e instanceof ApiError && e.message
            ? `Maaf, belum bisa diproses: ${e.message}`
            : "Maaf, lagi ada gangguan. Coba lagi sebentar ya.",
        );
      } finally {
        setSibuk(false);
      }
    },
    [sibuk, pushKartu, errorTenang, sesiHabis],
  );

  // Ketuk "Betulkan" pada satu baris riwayat → baris itu jadi sasaran koreksi
  // untuk pesan berikutnya. Cuma menandai; tak ada yang tersimpan sampai
  // pengguna mengetik apa yang benar.
  const mintaBetulkan = useCallback((transaksiId: number) => {
    setMenunggu({ jenis: "koreksi_sasaran", transaksi_id: transaksiId });
  }, []);

  const mulai = useCallback(() => {
    setScreen("chat");
    const salam = sapaan
      ? `${sapaan.salam}, ${sapaan.nama_usaha.split(" ").slice(-2).join(" ")}. ${sapaan.ajakan}`
      : "Selamat datang. Ada yang laku hari ini? Ceritakan saja seperti biasa — nanti saya catat.";
    pushKartu([{ tipe: "narasi", teks: salam, aman: true, teks_alt: salam }]);
  }, [sapaan, pushKartu]);

  if (auth === "memuat") return <Splash />;
  if (auth === "masuk") return <Masuk onBerhasil={muatSesi} />;

  if (screen === "pembuka") return <Pembuka sapaan={sapaan} onMulai={mulai} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <header className="chat-head">
        <Mark />
        <div style={{ minWidth: 0 }}>
          <div className="judul">{sapaan?.nama_usaha ?? "JembatanModal"}</div>
          <div className="status">
            <span className="dot" />
            siap mencatat
          </div>
        </div>
        <button className="keluar-link" onClick={keluarSesi} type="button">
          Keluar
        </button>
      </header>

      <div className="thread" ref={threadRef}>
        {items.map((it) => (
          <div className="item" key={it.id}>
            {it.kind === "user" ? (
              <div className="bubble-user">
                <div>{it.teks}</div>
              </div>
            ) : (
              <KartuView
                kartu={it.kartu}
                itemId={it.id}
                onKoreksi={koreksi}
                onBetulkan={mintaBetulkan}
                onBuatLaporan={() => tanyaAksi("buat_laporan", "Buat laporan PDF")}
                onLihatSkor={() => tanyaAksi("tanya_skor", "Lihat rapor usaha")}
                onPeriode={tanyaPeriode}
                onImpor={(body) => aksiImpor(it.id, body)}
                ditunjuk={menunggu?.jenis === "koreksi_sasaran" ? menunggu.transaksi_id : null}
                sibuk={sibuk}
              />
            )}
          </div>
        ))}
        {typing && (
          <div className="item bubble-bot">
            <Mark className="avatar" />
            <div className="typing">
              <i />
              <i />
              <i />
            </div>
          </div>
        )}
      </div>

      <div className="komposer">
        {menunggu?.jenis === "koreksi_sasaran" && (
          <div className="menunggu-koreksi">
            <span>Membetulkan catatan itu — tulis yang benar, misalnya “harusnya 57rb”.</span>
            <button type="button" onClick={() => setMenunggu(null)} aria-label="Batal betulkan">
              Batal
            </button>
          </div>
        )}
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.label}
              className="sugg"
              disabled={sibuk}
              onClick={() =>
                s.untung
                  ? tanyaAksi("tanya_untung", s.label)
                  : s.keuangan
                    ? tanyaAksi("tanya_keuangan", s.label)
                    : s.riwayat
                      ? tanyaAksi("lihat_transaksi", s.label)
                      : kirimTeks(s.teks!)
              }
            >
              {s.label}
            </button>
          ))}
        </div>
        <form
          className="komposer-baris"
          onSubmit={(e) => {
            e.preventDefault();
            kirimTeks(draft);
          }}
        >
          {/* Textarea, bukan <input>: browser MEMBUANG newline saat menempel ke
              input satu baris, jadi tempelan buku tulis akan tiba di server
              sebagai satu kalimat panjang — dan jalur draft impor (aturan #3)
              tak akan pernah terpicu. Enter mengirim; Shift+Enter baris baru. */}
          <textarea
            ref={komposerRef}
            className="input input-multi"
            placeholder="Tulis catatan Ibu…"
            value={draft}
            rows={1}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                kirimTeks(draft);
              }
            }}
            enterKeyHint="send"
            aria-label="Tulis catatan"
          />
          <button className="kirim" type="submit" disabled={sibuk || !draft.trim()} aria-label="Kirim" />
        </form>
      </div>
    </div>
  );
}

function KartuView({
  kartu,
  itemId,
  onKoreksi,
  onBetulkan,
  onBuatLaporan,
  onLihatSkor,
  onPeriode,
  onImpor,
  ditunjuk,
  sibuk,
}: {
  kartu: Kartu;
  itemId: number;
  onKoreksi: (itemId: number, transaksiId: number, jenis: string) => void;
  onBetulkan: (transaksiId: number) => void;
  onBuatLaporan: () => void;
  onLihatSkor: () => void;
  onPeriode: (
    aksi: "tanya_untung" | "tanya_keuangan" | "lihat_transaksi" | "tanya_skor",
    periode: string,
  ) => void;
  onImpor: (body: ChatBody) => void;
  ditunjuk: number | null;
  sibuk: boolean;
}) {
  switch (kartu.tipe) {
    case "narasi":
      return <NarasiView kartu={kartu} />;
    case "konfirmasi":
      return (
        <KonfirmasiView
          kartu={kartu}
          sibuk={sibuk}
          onKoreksi={(tid, jenis) => onKoreksi(itemId, tid, jenis)}
        />
      );
    case "klarifikasi":
      return <KlarifikasiView kartu={kartu} />;
    case "belum_diketahui":
      return <BelumDiketahuiView kartu={kartu} />;
    case "untung":
      return (
        <UntungView
          kartu={kartu}
          sibuk={sibuk}
          onPeriode={(p) => onPeriode("tanya_untung", p)}
        />
      );
    case "keuangan":
      return (
        <KeuanganView
          kartu={kartu}
          onBuatLaporan={onBuatLaporan}
          onLihatSkor={onLihatSkor}
          onPeriode={(p) => onPeriode("tanya_keuangan", p)}
          sibuk={sibuk}
        />
      );
    case "skor":
      return (
        <SkorView kartu={kartu} sibuk={sibuk} onPeriode={(p) => onPeriode("tanya_skor", p)} />
      );
    case "dokumen":
      return <DokumenView kartu={kartu} />;
    case "impor":
      return (
        <ImporView
          kartu={kartu}
          sibuk={sibuk}
          onPutuskan={(rowId, terima) =>
            onImpor({
              aksi: "impor_putuskan",
              import_id: kartu.import_id,
              row_id: rowId,
              terima,
            })
          }
          onTerimaYakin={() =>
            onImpor({ aksi: "impor_terima_yakin", import_id: kartu.import_id })
          }
          onKonfirmasi={() =>
            onImpor({ aksi: "impor_konfirmasi", import_id: kartu.import_id })
          }
        />
      );
    case "resep":
      return <ResepView kartu={kartu} />;
    case "riwayat":
      return (
        <RiwayatView
          kartu={kartu}
          sibuk={sibuk}
          onKoreksi={(tid, jenis) => onKoreksi(itemId, tid, jenis)}
          onBetulkan={onBetulkan}
          onPeriode={(p) => onPeriode("lihat_transaksi", p)}
          ditunjuk={ditunjuk}
        />
      );
    default:
      return null;
  }
}

function Splash() {
  return (
    <div className="pembuka">
      <div className="glow" />
      <div className="pembuka-brand">
        <Mark />
        <span className="wordmark">JembatanModal</span>
      </div>
      <div className="pembuka-tengah">
        <div className="sub-usaha">Memuat…</div>
      </div>
    </div>
  );
}

function Masuk({ onBerhasil }: { onBerhasil: () => void }) {
  const [noHp, setNoHp] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);

  const kirim = async () => {
    if (sibuk || !noHp.trim() || pin.length < 6) return;
    setError(null);
    setSibuk(true);
    try {
      await masuk(noHp.trim(), pin);
      onBerhasil(); // memuat ulang /sesi → lanjut ke Pembuka
    } catch (e) {
      setError(
        e instanceof Error && e.message ? e.message : "Gagal masuk. Coba lagi sebentar ya.",
      );
      setSibuk(false);
    }
  };

  return (
    <div className="pembuka">
      <div className="glow" />
      <div className="pembuka-brand">
        <Mark />
        <span className="wordmark">JembatanModal</span>
      </div>

      <div className="pembuka-tengah">
        <div className="salam">Masuk dulu, yuk</div>
        <div className="sub-usaha">Pakai no. HP dan PIN Ibu.</div>
      </div>

      <form
        className="masuk-form"
        onSubmit={(e) => {
          e.preventDefault();
          kirim();
        }}
      >
        <input
          className="input"
          inputMode="numeric"
          autoComplete="username"
          placeholder="No. HP"
          value={noHp}
          onChange={(e) => setNoHp(e.target.value.replace(/\s/g, ""))}
          aria-label="Nomor HP"
        />
        <input
          className="input"
          type="password"
          inputMode="numeric"
          autoComplete="current-password"
          maxLength={6}
          placeholder="PIN 6 digit"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 6))}
          aria-label="PIN 6 digit"
        />
        {error && (
          <div className="masuk-error" role="alert">
            {error}
          </div>
        )}
        <button
          className="btn-primary"
          type="submit"
          disabled={sibuk || !noHp.trim() || pin.length < 6}
        >
          {sibuk ? "Memeriksa…" : "Masuk"}
        </button>
      </form>
    </div>
  );
}

function Pembuka({ sapaan, onMulai }: { sapaan: KartuSapaan | null; onMulai: () => void }) {
  const nama = sapaan?.nama_usaha ?? "Warung Ibu";
  const salam = sapaan?.salam ?? "Selamat datang";
  const sub = sapaan?.sub ?? "";
  const ajakan =
    sapaan?.ajakan ??
    "Ada yang laku hari ini? Ceritakan saja seperti biasa — nanti saya bantu catat dan hitung untungnya.";
  const honest =
    sapaan?.catatan_jujur ??
    "Angka Ibu tidak pernah saya karang. Kalau modalnya belum ketahuan, saya bilang apa adanya — belum tahu.";

  return (
    <div className="pembuka">
      <div className="glow" />
      <div className="pembuka-brand">
        <Mark />
        <span className="wordmark">JembatanModal</span>
      </div>

      <div className="pembuka-tengah">
        <div className="salam">{salam},</div>
        <div className="nama-usaha">{nama}</div>
        {sub && <div className="sub-usaha">{sub}</div>}
      </div>

      <div className="ajakan-kartu">{ajakan}</div>

      <button className="btn-primary" onClick={onMulai}>
        Mulai catat
      </button>

      <div className="honest">
        <div className="titik" />
        <p>{honest}</p>
      </div>
    </div>
  );
}

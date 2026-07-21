"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ambilSesi, kirimChat } from "@/lib/api";
import type { Kartu, KartuSapaan, PesanKeluar } from "@/lib/kontrak";
import { Mark } from "./Brand";
import {
  BelumDiketahuiView,
  KlarifikasiView,
  KonfirmasiView,
  NarasiView,
  UntungView,
} from "./Cards";

type Item =
  | { id: number; kind: "user"; teks: string }
  | { id: number; kind: "kartu"; kartu: Kartu };

const SUGGESTIONS: { label: string; teks?: string; untung?: boolean }[] = [
  { label: "laku 5 kotak risol, 75rb", teks: "laku 5 kotak risol tadi, 75rb" },
  { label: "beli minyak 2 liter 38rb", teks: "beli minyak goreng 2 liter 38rb" },
  { label: "Untung risol berapa?", untung: true },
];

export default function Chat() {
  const [screen, setScreen] = useState<"pembuka" | "chat">("pembuka");
  const [sapaan, setSapaan] = useState<KartuSapaan | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [typing, setTyping] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [draft, setDraft] = useState("");
  const idRef = useRef(0);
  const threadRef = useRef<HTMLDivElement>(null);

  const nextId = () => ++idRef.current;

  // Kartu pembuka datang dari kontrak (/sesi), bukan hardcode di UI.
  useEffect(() => {
    ambilSesi()
      .then((p: PesanKeluar) => {
        const s = p.kartu.find((k) => k.tipe === "sapaan") as KartuSapaan | undefined;
        if (s) setSapaan(s);
      })
      .catch(() => {
        /* biarkan fallback statis tampil */
      });
  }, []);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items, typing]);

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
        const p = await kirimChat({ teks: t });
        pushKartu(p.kartu);
      } catch (e) {
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
    [sibuk, pushKartu, errorTenang],
  );

  const tanyaUntung = useCallback(async () => {
    if (sibuk) return;
    setItems((prev) => [...prev, { id: nextId(), kind: "user", teks: "Untung risol berapa?" }]);
    setSibuk(true);
    setTyping(true);
    try {
      const p = await kirimChat({ aksi: "tanya_untung" });
      pushKartu(p.kartu);
    } catch {
      errorTenang("Maaf, lagi ada gangguan. Coba lagi sebentar ya.");
    } finally {
      setTyping(false);
      setSibuk(false);
    }
  }, [sibuk, pushKartu, errorTenang]);

  // Ketuk chip kategori → koreksi. Kartu konfirmasi diperbarui di tempat.
  const koreksi = useCallback(
    async (itemId: number, transaksiId: number, jenis: string) => {
      if (sibuk) return;
      setSibuk(true);
      try {
        const p = await kirimChat({ aksi: "koreksi_kategori", transaksi_id: transaksiId, jenis });
        const baru = p.kartu[0];
        if (baru && baru.tipe === "konfirmasi") {
          setItems((prev) =>
            prev.map((it) =>
              it.id === itemId && it.kind === "kartu" ? { ...it, kartu: baru } : it,
            ),
          );
        } else if (baru) {
          pushKartu([baru]);
        }
      } catch {
        errorTenang("Koreksi belum tersimpan — koneksi bermasalah. Coba lagi ya.");
      } finally {
        setSibuk(false);
      }
    },
    [sibuk, pushKartu, errorTenang],
  );

  const mulai = useCallback(() => {
    setScreen("chat");
    const salam = sapaan
      ? `${sapaan.salam}, ${sapaan.nama_usaha.split(" ").slice(-2).join(" ")}. ${sapaan.ajakan}`
      : "Selamat datang. Ada yang laku hari ini? Ceritakan saja seperti biasa — nanti saya catat.";
    pushKartu([{ tipe: "narasi", teks: salam, aman: true, teks_alt: salam }]);
  }, [sapaan, pushKartu]);

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
        <div className="hari">Hari ini</div>
      </header>

      <div className="thread" ref={threadRef}>
        {items.map((it) => (
          <div className="item" key={it.id}>
            {it.kind === "user" ? (
              <div className="bubble-user">
                <div>{it.teks}</div>
              </div>
            ) : (
              <KartuView kartu={it.kartu} itemId={it.id} onKoreksi={koreksi} sibuk={sibuk} />
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
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.label}
              className="sugg"
              disabled={sibuk}
              onClick={() => (s.untung ? tanyaUntung() : kirimTeks(s.teks!))}
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
          <input
            className="input"
            placeholder="Tulis catatan Ibu…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
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
  sibuk,
}: {
  kartu: Kartu;
  itemId: number;
  onKoreksi: (itemId: number, transaksiId: number, jenis: string) => void;
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
      return <UntungView kartu={kartu} />;
    default:
      return null;
  }
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

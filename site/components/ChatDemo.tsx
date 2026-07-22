"use client";

import { useEffect, useRef, useState } from "react";
import Logo from "./Logo";
import s from "../app/demo/demo.module.css";

// Kategori & label — persis seperti DCLogic pada export Claude Design.
const KATEGORI = [
  { nilai: "pemasukan", label: "Pemasukan" },
  { nilai: "pengeluaran", label: "Belanja barang" },
  { nilai: "operasional", label: "Biaya warung" },
  { nilai: "prive", label: "Pribadi" },
] as const;

type Jenis = (typeof KATEGORI)[number]["nilai"];
const LABEL: Record<Jenis, string> = {
  pemasukan: "Pemasukan",
  pengeluaran: "Belanja barang",
  operasional: "Biaya warung",
  prive: "Pribadi",
};

type Item = {
  id: number;
  kind: "user" | "narasi" | "konfirmasi" | "untung" | "keuangan";
  teks?: string;
  jenis?: Jenis;
  jenisLabel?: string;
  nominal?: string;
  rincian?: string;
};
type KartuBaru = Omit<Item, "id">;

export default function ChatDemo() {
  const [screen, setScreen] = useState<"pembuka" | "chat">("pembuka");
  const [items, setItems] = useState<Item[]>([]);
  const [typing, setTyping] = useState(false);
  const [draft, setDraft] = useState("");

  const idRef = useRef(0);
  const busyRef = useRef(false);
  const threadRef = useRef<HTMLDivElement>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Auto-scroll ke bawah tiap ada pesan / indikator mengetik baru.
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items, typing, screen]);

  // Bersihkan timer yang tertunda saat komponen dilepas.
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const push = (item: KartuBaru) =>
    setItems((prev) => [...prev, { id: ++idRef.current, ...item }]);

  const balas = (item: KartuBaru, tunda = 850) => {
    setTyping(true);
    busyRef.current = true;
    const t = setTimeout(() => {
      setTyping(false);
      busyRef.current = false;
      push(item);
    }, tunda);
    timers.current.push(t);
  };

  const kirimSaran = (teks: string, kartu: KartuBaru) => {
    if (busyRef.current) return;
    push({ kind: "user", teks });
    balas(kartu);
  };

  const koreksi = (itemId: number, nilai: Jenis) =>
    setItems((prev) =>
      prev.map((it) =>
        it.id === itemId
          ? { ...it, jenis: nilai, jenisLabel: LABEL[nilai] }
          : it,
      ),
    );

  const kirimBebas = () => {
    const t = draft.trim();
    if (!t || busyRef.current) return;
    setDraft("");
    push({ kind: "user", teks: t });
    balas({
      kind: "narasi",
      teks: "Pada demo ini kalimat bebas belum diproses, karena tidak ada server di baliknya. Silakan coba tombol saran di bawah untuk melihat alur aslinya.",
    });
  };

  const mulai = () => {
    setScreen("chat");
    balas(
      {
        kind: "narasi",
        teks: "Selamat datang, Bu Sari. Ada yang laku hari ini? Ceritakan saja seperti biasa, nanti saya catat.",
      },
      500,
    );
  };

  if (screen === "pembuka") {
    return (
      <div className={s.pembuka}>
        <div className={s.pembukaGlow} />
        <div className={s.pembukaBrand}>
          <Logo size={30} />
          <span className={s.pembukaBrandName}>JembatanModal</span>
        </div>
        <div className={s.pembukaHero}>
          <div className={s.pembukaGreet}>Selamat pagi,</div>
          <div className={s.pembukaName}>Warung Bu Sari</div>
          <div className={s.pembukaMeta}>
            Katering &amp; frozen food rumahan · Bandung
          </div>
        </div>
        <div className={s.pembukaCard}>
          Ada yang laku hari ini? Ceritakan saja seperti biasa, nanti saya bantu
          catat dan hitung untungnya.
        </div>
        <button className={s.pembukaCta} onClick={mulai}>
          Mulai catat
        </button>
        <div className={s.pembukaFine}>
          <div />
          <p>
            Angka Ibu tidak pernah saya karang. Kalau modalnya belum ketahuan,
            saya bilang apa adanya — belum tahu.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <header className={s.chatHead}>
        <Logo size={34} />
        <div style={{ minWidth: 0 }}>
          <div className={s.chatHeadName}>Warung Bu Sari</div>
          <div className={s.chatHeadStatus}>
            <span />
            siap mencatat
          </div>
        </div>
        <div className={s.chatHeadTag}>Demo</div>
      </header>

      <div ref={threadRef} className={s.thread}>
        {items.map((it) => (
          <div key={it.id} className={s.item}>
            {it.kind === "user" && (
              <div className={s.userRow}>
                <div className={s.userBubble}>{it.teks}</div>
              </div>
            )}
            {it.kind === "narasi" && (
              <div className={s.narasi}>
                <div className={s.avatar}>
                  <Logo size={26} />
                </div>
                <div className={s.narasiText}>{it.teks}</div>
              </div>
            )}
            {it.kind === "konfirmasi" && (
              <div className={s.card}>
                <div className={s.konfHead}>
                  <div className={s.konfTick}>
                    <span className={s.tickGlyph} />
                  </div>
                  <span className={s.konfTitle}>Tercatat ya, Bu</span>
                </div>
                <div className={s.konfPanel}>
                  <span className={s.tagIn}>{it.jenisLabel}</span>
                  <div className={s.konfNominal}>{it.nominal}</div>
                  <div className={s.konfDetail}>{it.rincian}</div>
                </div>
                <div className={s.konfHint}>Jenisnya — ketuk kalau keliru</div>
                <div className={s.chips}>
                  {KATEGORI.map((k) => {
                    const aktif = k.nilai === it.jenis;
                    return (
                      <button
                        key={k.nilai}
                        className={`${s.chip} ${aktif ? s.chipActive : ""}`}
                        onClick={() => koreksi(it.id, k.nilai)}
                      >
                        {k.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {it.kind === "untung" && (
              <div className={s.card}>
                <div className={s.untungLabel}>
                  Untung kotor dari bahan · per porsi
                </div>
                <div className={s.untungList}>
                  <div className={s.untungRow}>
                    <div className={s.untungRowHead}>
                      <span className={s.untungName}>Risol</span>
                      <span className={s.untungBadge}>diolah</span>
                    </div>
                    <div className={s.untungValue}>
                      Rp11.050
                      <span className={s.untungUnit}> / kotak</span>
                    </div>
                    <div className={s.untungSub}>
                      modal bahan Rp3.950 · jual Rp15.000
                    </div>
                  </div>
                  <div className={s.untungRowUnknown}>
                    <div className={s.untungRowHead}>
                      <span className={s.untungName}>Nugget ayam</span>
                      <span className={s.untungBadge}>diolah</span>
                    </div>
                    <div className={s.untungUnknownValue}>belum diketahui</div>
                    <div className={s.untungUnknownSub}>
                      Resepnya belum tercatat.
                    </div>
                  </div>
                </div>
                <span className={s.coverage}>
                  Modal terhitung untuk 78% penjualan
                </span>
                <p className={s.cardFine}>
                  Ini untung kotor dari bahan, bukan untung usaha. Biaya
                  listrik, gas, dan lainnya belum termasuk.
                </p>
              </div>
            )}
            {it.kind === "keuangan" && (
              <div className={s.card}>
                <div className={s.keuHead}>
                  <span className={s.keuLabel}>Untung usaha</span>
                  <span className={s.keuPeriod}>Juli 2026</span>
                </div>
                <div className={s.keuValue}>Rp1.080.000</div>
                <div className={s.keuSub}>
                  omzet Rp2.150.000 − biaya Rp1.070.000
                </div>
                <div className={s.keuGrid}>
                  <div>
                    <div className={s.keuCellLabel}>Pemasukan</div>
                    <div className={s.keuCellValue}>Rp2.150.000</div>
                  </div>
                  <div>
                    <div className={s.keuCellLabel}>Belanja barang</div>
                    <div className={s.keuCellValue}>Rp830.000</div>
                  </div>
                  <div>
                    <div className={s.keuCellLabel}>Biaya warung</div>
                    <div className={s.keuCellValue}>Rp240.000</div>
                  </div>
                  <div>
                    <div className={s.keuCellLabel}>Dipakai pribadi</div>
                    <div className={`${s.keuCellValue} ${s.keuCellValueAmber}`}>
                      Rp150.000 (14%)
                    </div>
                  </div>
                </div>
                <span className={s.coverage}>
                  Modal bahan terhitung untuk 78% penjualan
                </span>
                <p className={s.cardFine}>Angka demo dari data contoh Bu Sari.</p>
              </div>
            )}
          </div>
        ))}
        {typing && (
          <div className={s.typing}>
            <div className={s.avatar}>
              <Logo size={26} />
            </div>
            <div className={s.typingBubble}>
              <i />
              <i />
              <i />
            </div>
          </div>
        )}
      </div>

      <div className={s.composer}>
        <div className={s.suggestRow}>
          <button
            className={s.suggest}
            disabled={typing}
            onClick={() =>
              kirimSaran("laku 5 kotak risol tadi, 75rb", {
                kind: "konfirmasi",
                jenis: "pemasukan",
                jenisLabel: "Pemasukan",
                nominal: "Rp75.000",
                rincian: "risol · 5 kotak",
              })
            }
          >
            laku 5 kotak risol, 75rb
          </button>
          <button
            className={s.suggest}
            disabled={typing}
            onClick={() =>
              kirimSaran("beli minyak goreng 2 liter 38rb", {
                kind: "konfirmasi",
                jenis: "pengeluaran",
                jenisLabel: "Belanja barang",
                nominal: "Rp38.000",
                rincian: "minyak goreng · 2 liter",
              })
            }
          >
            beli minyak 2 liter 38rb
          </button>
          <button
            className={s.suggest}
            disabled={typing}
            onClick={() => kirimSaran("Untung per porsi?", { kind: "untung" })}
          >
            Untung per porsi?
          </button>
          <button
            className={s.suggest}
            disabled={typing}
            onClick={() => kirimSaran("Laporan singkat", { kind: "keuangan" })}
          >
            Laporan singkat
          </button>
        </div>
        <div className={s.inputRow}>
          <input
            className={s.input}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") kirimBebas();
            }}
            placeholder="Tulis catatan di sini…"
            aria-label="Tulis catatan"
          />
          <button className={s.send} aria-label="Kirim" onClick={kirimBebas}>
            <span className={s.sendGlyph} />
          </button>
        </div>
      </div>
    </>
  );
}

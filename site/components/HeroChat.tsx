"use client";

import { useEffect, useRef, useState } from "react";
import Logo from "./Logo";
import s from "../app/page.module.css";

// Timeline demo hero: user → mengetik → kartu, satu ronde penuh, lalu ulang.
// [tunda ms, tahap] — persis seperti DCLogic pada export Claude Design.
const URUTAN: [number, number][] = [
  [600, 1], // gelembung user 1
  [700, 2], // mengetik
  [1400, 3], // kartu konfirmasi
  [1900, 4], // gelembung "laporan singkat"
  [700, 5], // mengetik
  [1400, 6], // kartu keuangan
  [1900, 7], // gelembung "untungku minggu ini"
  [700, 8], // mengetik
  [1400, 9], // kartu amber
  [5600, 0], // jeda baca, lalu ulang
];

function Typing() {
  return (
    <div className={s.typing}>
      <div className={s.typingBubble}>
        <i />
        <i />
        <i />
      </div>
    </div>
  );
}

export default function HeroChat() {
  // Mulai dari tahap penuh (9) agar tanpa-JS / prefers-reduced-motion tetap utuh.
  const [tahap, setTahap] = useState(9);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const kurangiGerak = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (kurangiGerak) return; // biarkan tampil penuh, tanpa loop.

    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const maju = () => {
      const [tunda, t] = URUTAN[i];
      timer = setTimeout(() => {
        setTahap(t);
        requestAnimationFrame(() => {
          const el = threadRef.current;
          if (el)
            el.scrollTo({
              top: el.scrollHeight,
              behavior: t === 0 ? "auto" : "smooth",
            });
        });
        i = (i + 1) % URUTAN.length;
        maju();
      }, tunda);
    };
    // Mulai lewat rAF (bukan synchronous di badan efek): bersihkan tampilan
    // penuh (fallback tanpa-JS) ke tahap 0, lalu jalankan timeline.
    const mulai = requestAnimationFrame(() => {
      setTahap(0);
      maju();
    });
    return () => {
      cancelAnimationFrame(mulai);
      clearTimeout(timer);
    };
  }, []);

  const v = {
    s1: tahap >= 1,
    ngetik1: tahap === 2,
    s2: tahap >= 3,
    s3: tahap >= 4,
    ngetik2: tahap === 5,
    s4: tahap >= 6,
    s5: tahap >= 7,
    ngetik3: tahap === 8,
    s6: tahap >= 9,
  };

  return (
    <div className={s.heroChat}>
      <div className={s.heroChatHead}>
        <Logo size={26} />
        <span className={s.heroChatName}>JembatanModal</span>
        <span className={s.heroChatStatus}>
          <i />
          siap mencatat
        </span>
      </div>
      <div ref={threadRef} className={s.heroThread}>
        {v.s1 && (
          <div className={`${s.userRow} ${s.appear}`}>
            <div className={s.userBubble}>tadi laku 5 kotak risol 75rb</div>
          </div>
        )}
        {v.ngetik1 && <Typing />}
        {v.s2 && (
          <div className={`${s.confirmCard} ${s.appear}`}>
            <div className={s.confirmHead}>
              <div className={s.confirmTick}>
                <span className={s.tickGlyph} />
              </div>
              <span className={s.confirmTitle}>Tercatat ya, Bu</span>
            </div>
            <div className={s.confirmPanel}>
              <span className={s.tagIn}>Pemasukan</span>
              <div className={s.bigNum}>Rp75.000</div>
              <div className={s.confirmDetail}>risol · 5 kotak</div>
            </div>
            <div className={s.chipRow}>
              <span className={`${s.chip} ${s.chipActive}`}>Pemasukan</span>
              <span className={s.chip}>Belanja barang</span>
              <span className={s.chip}>Pribadi</span>
            </div>
          </div>
        )}
        {v.s3 && (
          <div className={`${s.userRow} ${s.appear}`}>
            <div className={s.userBubble}>laporan singkat dong</div>
          </div>
        )}
        {v.ngetik2 && <Typing />}
        {v.s4 && (
          <div className={`${s.moneyCard} ${s.appear}`}>
            <div className={s.moneyHead}>
              <span className={s.moneyLabel}>Untung usaha</span>
              <span className={s.moneyPeriod}>Juli 2026</span>
            </div>
            <div className={s.moneyValue}>Rp1.080.000</div>
            <div className={s.moneySub}>
              omzet Rp2.150.000 − biaya Rp1.070.000
            </div>
            <span className={s.coveragePill}>
              Modal bahan terhitung untuk 78% penjualan
            </span>
          </div>
        )}
        {v.s5 && (
          <div className={`${s.userRow} ${s.appear}`}>
            <div className={s.userBubble}>untungku minggu ini berapa?</div>
          </div>
        )}
        {v.ngetik3 && <Typing />}
        {v.s6 && (
          <div className={`${s.unknownCard} ${s.appear}`}>
            <div className={s.unknownHead}>
              <div className={s.unknownIcon}>
                <span />
              </div>
              <span className={s.unknownTitle}>Belum bisa dipastikan, Bu</span>
            </div>
            <div className={s.unknownBox}>
              <div className={s.unknownBoxLabel}>Untung bersih minggu ini</div>
              <div className={s.unknownBoxValue}>belum diketahui</div>
            </div>
            <p className={s.unknownBody}>
              Modal risol belum lengkap karena harga tepung belum tercatat.
              Boleh saya tanyakan resepnya sebentar?
            </p>
          </div>
        )}
      </div>
      <p className={s.heroFoot}>
        Cuplikan dari antarmuka produk. Jawaban jujur, bukan tebakan.{" "}
        <a href="/demo/">Coba sendiri →</a>
      </p>
    </div>
  );
}

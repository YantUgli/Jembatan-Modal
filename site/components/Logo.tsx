import type { CSSProperties } from "react";

// Ukuran batang per ukuran kotak logo (mengikuti export Claude Design).
const BARS: Record<number, [number, number]> = {
  22: [10, 7],
  26: [12, 8],
  28: [13, 8],
  30: [14, 9],
  34: [15, 10],
};

type Props = {
  /** Panjang sisi kotak logo dalam px. */
  size?: number;
  /** Radius sudut; default menyesuaikan ukuran. */
  radius?: number;
};

/** Lambang JembatanModal: kotak hijau dengan tiga garis (buku terbuka). */
export default function Logo({ size = 30, radius }: Props) {
  const [wLong, wShort] = BARS[size] ?? [
    Math.round(size * 0.46),
    Math.round(size * 0.3),
  ];
  const box: CSSProperties = {
    width: size,
    height: size,
    borderRadius: radius ?? (size >= 30 ? 9 : 8),
    background: "var(--green)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2.5,
    flex: "none",
  };
  const bar = (w: number, alpha: number): CSSProperties => ({
    display: "block",
    width: w,
    height: 2,
    borderRadius: 2,
    background: `rgba(var(--white-rgb), ${alpha})`,
  });
  return (
    <div style={box} aria-hidden="true">
      <span style={bar(wLong, 0.9)} />
      <span style={bar(wLong, 0.55)} />
      <span style={bar(wShort, 0.9)} />
    </div>
  );
}

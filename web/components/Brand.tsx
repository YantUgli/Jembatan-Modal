// Ikon tiga-bar hijau — dipakai di header & avatar. Murni CSS, tanpa aset.
export function Mark({ className }: { className?: string }) {
  return (
    <div className={`mark${className ? " " + className : ""}`} aria-hidden>
      <span />
      <span />
      <span />
    </div>
  );
}

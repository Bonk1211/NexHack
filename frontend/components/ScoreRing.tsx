// Inclusion-score ring (composite, DERIVED §16), shown on the dark hero band. Thin amber
// stroke on a near-black track; animates 0 → value once on load, unless reduced-motion.
"use client";

import { useEffect, useState } from "react";

export function ScoreRing({ value, size = 132 }: { value: number; size?: number }) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));

  // Animate from 0 on mount; honor prefers-reduced-motion.
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [shown, setShown] = useState(reduced ? clamped : 0);
  useEffect(() => {
    if (reduced) return;
    const t = requestAnimationFrame(() => setShown(clamped));
    return () => cancelAnimationFrame(t);
  }, [clamped, reduced]);

  const offset = c * (1 - shown);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#2c2c2e" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#d97a2b"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: reduced ? "none" : "stroke-dashoffset 800ms ease-out" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="font-display text-[44px] leading-none tabular-nums text-[#f5f5f7]">
          {Math.round(clamped * 100)}
        </span>
        <span className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-on-dark-dim">
          Score
        </span>
      </div>
    </div>
  );
}

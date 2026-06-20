"use client";

export const DEMO_PALETTE = [
  "#4a6fa5",
  "#d97a2b",
  "#4a8c6e",
  "#b56076",
  "#7b68c8",
  "#9b8160",
];

function polarToCartesian(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, R: number, r: number, start: number, end: number) {
  const o1 = polarToCartesian(cx, cy, R, start);
  const o2 = polarToCartesian(cx, cy, R, end);
  const i1 = polarToCartesian(cx, cy, r, end);
  const i2 = polarToCartesian(cx, cy, r, start);
  const large = end - start > 180 ? 1 : 0;
  return `M ${o1.x} ${o1.y} A ${R} ${R} 0 ${large} 1 ${o2.x} ${o2.y} L ${i1.x} ${i1.y} A ${r} ${r} 0 ${large} 0 ${i2.x} ${i2.y} Z`;
}

export interface DonutSegment {
  id: string;
  label: string;
  percentage: number;
}

export function DonutChart({
  segments,
  size = 160,
}: {
  segments: DonutSegment[];
  size?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const R = size / 2 - 4;
  const r = R - 30;
  const gap = segments.length > 1 ? 3 : 0;
  const perSegment = segments.length > 0 ? 360 / segments.length : 360;

  if (segments.length === 0) {
    return (
      <svg width={size} height={size}>
        <circle
          cx={cx}
          cy={cy}
          r={(R + r) / 2}
          fill="none"
          stroke="rgba(0,0,0,0.08)"
          strokeWidth={R - r}
          strokeDasharray="5 4"
        />
      </svg>
    );
  }

  if (segments.length === 1) {
    return (
      <svg width={size} height={size}>
        <circle
          cx={cx}
          cy={cy}
          r={(R + r) / 2}
          fill="none"
          stroke={DEMO_PALETTE[0]}
          strokeWidth={R - r}
          opacity={0.88}
        />
      </svg>
    );
  }

  return (
    <svg width={size} height={size}>
      {segments.map((seg, i) => {
        const startDeg = i * perSegment + gap / 2;
        const endDeg = (i + 1) * perSegment - gap / 2;
        return (
          <path
            key={seg.id}
            d={arcPath(cx, cy, R, r, startDeg, endDeg)}
            fill={DEMO_PALETTE[i % DEMO_PALETTE.length]}
            opacity={0.88}
          />
        );
      })}
    </svg>
  );
}

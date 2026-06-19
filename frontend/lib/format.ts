// Small pure helpers — no dependencies, safe on server or client.

/** "3h ago", "2d ago", "just now" from an ISO string. */
export function relativeTime(iso?: string): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  if (diff < 0) return "just now";
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  return `${mo}mo ago`;
}

/** 0..1 → integer 0..100. */
export function scorePct(score?: number): number {
  if (score == null) return 0;
  return Math.round(score * 100);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function hashSeed(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

/**
 * Deterministic, offline figurine: a soft two-tone gradient disc with the
 * persona's initials. Muted hues to stay inside the calm palette. Returns an
 * SVG data-URI so it swaps in exactly like a generated image would.
 */
export function generateFigurine(seed: string, name: string): string {
  const h = hashSeed(seed);
  const hue = h % 360;
  const c1 = `hsl(${hue} 32% 78%)`;
  const c2 = `hsl(${(hue + 36) % 360} 30% 64%)`;
  const text = initials(name);
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'>
<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0' stop-color='${c1}'/><stop offset='1' stop-color='${c2}'/>
</linearGradient></defs>
<rect width='120' height='120' rx='60' fill='url(#g)'/>
<circle cx='60' cy='48' r='20' fill='rgba(255,255,255,0.55)'/>
<rect x='28' y='74' width='64' height='40' rx='20' fill='rgba(255,255,255,0.45)'/>
<text x='60' y='66' font-family='Georgia, serif' font-size='30' fill='rgba(40,40,42,0.65)' text-anchor='middle' dominant-baseline='middle'>${text}</text>
</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

/** Human-readable one-liner derived from a persona's behavior sliders. */
export function behaviorSentence(p: {
  name: string;
  techSavviness: number;
  patience: number;
  behaviorProfile: { dwellMultiplier: number; hesitationProb: number; giveupThresholdS: number };
}): string {
  const tech =
    p.techSavviness < 0.34 ? "is unfamiliar with digital forms" : p.techSavviness < 0.67 ? "is moderately confident online" : "navigates interfaces fluently";
  const pace = p.behaviorProfile.dwellMultiplier > 1.6 ? "reads slowly" : p.behaviorProfile.dwellMultiplier > 1.1 ? "takes their time" : "moves quickly";
  const patience =
    p.patience < 0.34 ? `gives up after ~${Math.round(p.behaviorProfile.giveupThresholdS)}s of friction` : p.patience < 0.67 ? "tolerates some confusion before leaving" : "perseveres through obstacles";
  const hesitate = p.behaviorProfile.hesitationProb > 0.5 ? ", hesitating often" : "";
  return `${p.name} ${tech}, ${pace}${hesitate}, and ${patience}.`;
}

/** Short behavior chips for cards. */
export function behaviorChips(p: { patience: number; techSavviness: number; disabilities: string[] }): string[] {
  const chips: string[] = [];
  if (p.patience < 0.34) chips.push("low patience");
  if (p.techSavviness < 0.34) chips.push("low tech");
  else if (p.techSavviness > 0.75) chips.push("power user");
  for (const d of p.disabilities.slice(0, 2)) chips.push(d);
  return chips.slice(0, 3);
}

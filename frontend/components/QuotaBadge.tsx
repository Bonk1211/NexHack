"use client";

import { useEffect, useState } from "react";
import { getQuota, type Quota } from "@/lib/live";

function barColor(pct: number): string {
  if (pct >= 0.95) return "bg-blocked";
  if (pct >= 0.8) return "bg-friction";
  return "bg-ok";
}

/** Customer-facing plan usage — "43 / 500 runs" + a thin progress bar. Replaces
 * the internal token/cost figures (§SaaS revamp): this is the number a customer
 * on a subscribed plan actually cares about. `compact` renders for the dark
 * Sidebar footer; the default renders as a full card for the Dashboard tab. */
export function QuotaBadge({ compact = false }: { compact?: boolean }) {
  const [quota, setQuota] = useState<Quota | null>(null);

  useEffect(() => {
    getQuota().then(setQuota).catch(() => setQuota(null));
  }, []);

  if (!quota) return null;
  const pct = quota.limit > 0 ? Math.min(quota.used / quota.limit, 1) : 0;
  const color = barColor(pct);
  const remaining = quota.limit - quota.used;

  if (compact) {
    return (
      <div>
        <div className="flex items-baseline justify-between text-[11px] text-on-dark-dim">
          <span>Plan usage</span>
          <span className="tabular-nums">{quota.used} / {quota.limit}</span>
        </div>
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.08]">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct * 100}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-primary">Plan usage</h3>
        <span className="text-[12px] tabular-nums text-secondary">
          {quota.used} / {quota.limit} runs
        </span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-field">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct * 100}%` }} />
      </div>
      <p className="mt-3 text-[12px] text-secondary">
        {remaining > 0
          ? `${remaining} runs remaining this billing cycle.`
          : "You've used all included runs this cycle."}
      </p>
      <button
        type="button"
        className="mt-4 rounded-lg bg-brand px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
      >
        Upgrade plan
      </button>
    </div>
  );
}

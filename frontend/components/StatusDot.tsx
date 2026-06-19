"use client";

import type { Severity } from "@/lib/types";

const STATUS_COLOR: Record<Severity, string> = {
  ok: "#1d8a4e",
  friction: "#b25e00",
  blocked: "#c8362f",
};

export function StatusDot({ status, size = 8 }: { status: Severity; size?: number }) {
  return (
    <span
      className="inline-block shrink-0 rounded-full"
      style={{ width: size, height: size, background: STATUS_COLOR[status] }}
    />
  );
}

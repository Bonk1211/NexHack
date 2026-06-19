// Prioritized remediation list — what to fix, who owns it, how bad it is.
// Sorted P0 -> P3 so the highest-severity exclusion leads.
import type { RemediationItem, Severity } from "@/lib/api";
import { severityColor } from "@/lib/format";

const SEV_ORDER: Record<Exclude<Severity, null>, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };

function rank(sev: Severity): number {
  return sev ? SEV_ORDER[sev] : 99;
}

export default function Remediation({ items }: { items: RemediationItem[] }) {
  const sorted = [...items].sort((a, b) => rank(a.severity) - rank(b.severity));
  return (
    <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
      {sorted.map((item, i) => {
        const c = severityColor(item.severity);
        return (
          <li
            key={`${item.criterion}-${i}`}
            style={{
              border: "1px solid #1c2231",
              borderRadius: 10,
              padding: 14,
              background: "#11151f",
              display: "flex",
              gap: 12,
              alignItems: "flex-start",
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 700,
                padding: "3px 9px",
                borderRadius: 6,
                background: c.bg,
                color: c.fg,
                flexShrink: 0,
              }}
            >
              {item.severity ?? "—"}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "#e2e8f0", fontSize: 14 }}>{item.issue}</div>
              <div style={{ marginTop: 4, fontSize: 12, color: "#94a3b8", display: "flex", gap: 12, flexWrap: "wrap" }}>
                <span>
                  WCAG <code style={{ color: "#cbd5e1" }}>{item.criterion}</code>
                </span>
                <span
                  style={{
                    color: "#7dd3fc",
                    background: "#0c2733",
                    padding: "1px 7px",
                    borderRadius: 999,
                    fontWeight: 600,
                  }}
                >
                  {item.owner}
                </span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

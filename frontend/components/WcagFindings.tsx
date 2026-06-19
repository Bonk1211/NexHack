// TRUSTED stream (§16) — per-criterion WCAG conformance, straight from axe-core +
// a11y signals. Shown on its own so a compliance officer can rely on it WITHOUT
// trusting the persona simulation. Kept visually distinct from the indicative panels.
import type { Conformance } from "@/lib/api";

// Short human labels for the criteria we surface in the demo.
const CRITERION_LABELS: Record<string, string> = {
  "1.4.3": "Contrast (Minimum)",
  "4.1.2": "Name, Role, Value",
  "1.3.1": "Info & Relationships",
};

export default function WcagFindings({
  conformance,
}: {
  conformance: Record<string, Conformance>;
}) {
  const rows = Object.entries(conformance);
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr style={{ textAlign: "left", color: "#64748b", fontSize: 12 }}>
          <th style={{ padding: "8px 10px", fontWeight: 600 }}>Criterion</th>
          <th style={{ padding: "8px 10px", fontWeight: 600 }}>Guideline</th>
          <th style={{ padding: "8px 10px", fontWeight: 600, textAlign: "right" }}>Result</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([crit, result]) => {
          const pass = result === "pass";
          return (
            <tr key={crit} style={{ borderTop: "1px solid #1c2231" }}>
              <td style={{ padding: "10px", fontWeight: 600, color: "#e2e8f0" }}>
                <code>{crit}</code>
              </td>
              <td style={{ padding: "10px", color: "#94a3b8" }}>
                {CRITERION_LABELS[crit] ?? "—"}
              </td>
              <td style={{ padding: "10px", textAlign: "right" }}>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: 0.4,
                    padding: "3px 10px",
                    borderRadius: 6,
                    background: pass ? "#14532d" : "#7f1d1d",
                    color: pass ? "#bbf7d0" : "#fecaca",
                  }}
                >
                  {result}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

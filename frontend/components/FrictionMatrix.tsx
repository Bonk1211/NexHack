// THE HERO ARTIFACT (§14, FR-3.3) — the persona × step friction matrix.
// The diff is the point: the SAME step is green for control and red for a
// protected persona. We make that contrast unmissable.
import type { Matrix, MatrixCell } from "@/lib/api";
import { personaLabel, statusFill } from "@/lib/format";

function Cell({ cell }: { cell: MatrixCell | undefined }) {
  if (!cell) {
    return (
      <td style={{ padding: 6, textAlign: "center", color: "#475569" }}>—</td>
    );
  }
  const isNa = cell.status === "na";
  const fill = statusFill(cell.status);
  return (
    <td style={{ padding: 6 }}>
      <div
        style={{
          borderRadius: 8,
          minHeight: 56,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 2,
          background: isNa ? "#161b27" : fill,
          // hatch the na cells so "never reached" reads differently from a status
          backgroundImage: isNa
            ? "repeating-linear-gradient(45deg, #232a3a 0 6px, #161b27 6px 12px)"
            : undefined,
          color: isNa ? "#64748b" : "#fff",
          border: `1px solid ${isNa ? "#232a3a" : "rgba(0,0,0,0.25)"}`,
          fontWeight: 700,
          fontSize: 13,
        }}
        title={`status: ${cell.status}${cell.dwell_s != null ? ` · dwell ${cell.dwell_s}s` : ""}`}
      >
        <span style={{ textTransform: "uppercase", letterSpacing: 0.5 }}>
          {isNa ? "n/a" : cell.status}
        </span>
        {cell.dwell_s != null && (
          <span style={{ fontSize: 11, fontWeight: 500, opacity: 0.92 }}>
            {cell.dwell_s.toFixed(1)}s
          </span>
        )}
      </div>
    </td>
  );
}

function Legend() {
  const items: { label: string; swatch: React.CSSProperties }[] = [
    { label: "pass", swatch: { background: statusFill("green") } },
    { label: "friction", swatch: { background: statusFill("amber") } },
    { label: "blocked", swatch: { background: statusFill("red") } },
    {
      label: "never reached",
      swatch: {
        background: "#161b27",
        backgroundImage:
          "repeating-linear-gradient(45deg, #232a3a 0 6px, #161b27 6px 12px)",
      },
    },
  ];
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 12 }}>
      {items.map((it) => (
        <div key={it.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#94a3b8" }}>
          <span style={{ width: 14, height: 14, borderRadius: 4, display: "inline-block", ...it.swatch }} />
          {it.label}
        </div>
      ))}
    </div>
  );
}

export default function FrictionMatrix({ matrix }: { matrix: Matrix }) {
  const personas = Object.keys(matrix.rows);
  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "separate", borderSpacing: 0, width: "100%", minWidth: 420 }}>
          <thead>
            <tr>
              <th
                style={{
                  textAlign: "left",
                  padding: "6px 10px",
                  fontSize: 12,
                  color: "#64748b",
                  fontWeight: 600,
                }}
              >
                Persona \ Step
              </th>
              {matrix.steps.map((s) => (
                <th
                  key={s}
                  style={{
                    padding: "6px 6px",
                    fontSize: 13,
                    color: "#cbd5e1",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {personas.map((p) => {
              const isControl = p === "control";
              return (
                <tr key={p}>
                  <td
                    style={{
                      padding: "6px 10px",
                      fontSize: 13,
                      fontWeight: isControl ? 500 : 600,
                      color: isControl ? "#94a3b8" : "#e2e8f0",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {personaLabel(p)}
                  </td>
                  {matrix.steps.map((s) => (
                    <Cell key={s} cell={matrix.rows[p]?.[s]} />
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Legend />
    </div>
  );
}

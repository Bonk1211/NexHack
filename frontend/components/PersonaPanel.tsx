// Persona wall (§14) — one card per persona. This is the INDICATIVE stream (§16):
// behavioral/completion verdicts from persona simulation, explicitly labeled.
import type { Persona } from "@/lib/api";
import { personaLabel, severityColor } from "@/lib/format";

function VerdictBadge({ verdict }: { verdict: Persona["verdict"] }) {
  const blocked = verdict === "blocked";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: 0.3,
        textTransform: "uppercase",
        padding: "3px 9px",
        borderRadius: 999,
        background: blocked ? "#7f1d1d" : "#14532d",
        color: blocked ? "#fecaca" : "#bbf7d0",
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: blocked ? "#ef4444" : "#22c55e",
        }}
      />
      {verdict}
    </span>
  );
}

function SeverityChip({ severity }: { severity: Persona["severity"] }) {
  if (!severity) return null;
  const c = severityColor(severity);
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        padding: "2px 7px",
        borderRadius: 6,
        background: c.bg,
        color: c.fg,
      }}
    >
      {severity}
    </span>
  );
}

function PersonaCard({ persona }: { persona: Persona }) {
  const blocked = persona.verdict === "blocked";
  const scorePct = Math.round(persona.inclusion_score * 100);
  return (
    <div
      style={{
        border: `1px solid ${blocked ? "#5b2330" : "#232838"}`,
        borderLeft: `3px solid ${blocked ? "#ef4444" : "#22c55e"}`,
        borderRadius: 10,
        padding: 16,
        background: "#11151f",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <div style={{ fontWeight: 600, fontSize: 15 }}>{personaLabel(persona.persona)}</div>
        <SeverityChip severity={persona.severity} />
      </div>

      <VerdictBadge verdict={persona.verdict} />

      {persona.blocked_at && (
        <div style={{ fontSize: 13, color: "#fca5a5" }}>
          Blocked at <code style={{ color: "#fecaca" }}>{persona.blocked_at}</code>
        </div>
      )}

      {persona.wcag_failures.length > 0 && (
        <div style={{ fontSize: 12, color: "#94a3b8" }}>
          Tripped WCAG:{" "}
          {persona.wcag_failures.map((c) => (
            <code key={c} style={{ color: "#cbd5e1", marginRight: 6 }}>
              {c}
            </code>
          ))}
        </div>
      )}

      {/* per-persona inclusion score (INDICATIVE) */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94a3b8" }}>
          <span>Inclusion score</span>
          <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{scorePct}</span>
        </div>
        <div style={{ height: 6, borderRadius: 999, background: "#1e2434", marginTop: 4, overflow: "hidden" }}>
          <div
            style={{
              width: `${scorePct}%`,
              height: "100%",
              background: blocked ? "#ef4444" : "#22c55e",
            }}
          />
        </div>
      </div>

      <div style={{ fontSize: 11, color: "#64748b", fontStyle: "italic" }}>{persona.behavioral_note}</div>
    </div>
  );
}

export default function PersonaPanel({ personas }: { personas: Persona[] }) {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
        gap: 12,
      }}
    >
      {personas.map((p) => (
        <PersonaCard key={p.persona} persona={p} />
      ))}
    </section>
  );
}

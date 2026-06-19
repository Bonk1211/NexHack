// InclusionScope dashboard (§14 demo surface). Composes the persona wall,
// the friction matrix (hero), empathy replay (centerpiece), the trusted WCAG
// stream and the indicative persona stream side by side (§16), and remediation.
//
// Loads a live run via ?run=<id> when present; otherwise renders SAMPLE_PACK so
// the surface always renders for the demo, with or without a backend.
import { getRun, SAMPLE_PACK, type PackResult } from "@/lib/api";
import PersonaPanel from "@/components/PersonaPanel";
import FrictionMatrix from "@/components/FrictionMatrix";
import EmpathyReplay from "@/components/EmpathyReplay";
import WcagFindings from "@/components/WcagFindings";
import Remediation from "@/components/Remediation";
import { personaLabel } from "@/lib/format";

async function loadPack(runId?: string): Promise<{ pack: PackResult; live: boolean }> {
  if (runId) {
    try {
      return { pack: await getRun(runId), live: true };
    } catch {
      // fall through to the sample pack so the demo never shows a blank screen
    }
  }
  return { pack: SAMPLE_PACK, live: false };
}

// One-line "who are we excluding" rollup (§14) derived from the pack.
function excludingLine(pack: PackResult): string | null {
  const blocked = pack.personas.filter((p) => p.verdict === "blocked");
  if (blocked.length === 0) return null;
  const where = blocked.find((p) => p.blocked_at)?.blocked_at;
  const names = blocked.map((p) => personaLabel(p.persona)).join(", ");
  return `This app silently blocks ${names}${where ? ` at ${where}` : ""}.`;
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ run?: string }>;
}) {
  const { run } = await searchParams;
  const { pack, live } = await loadPack(run);
  const scorePct = Math.round(pack.inclusion_score * 100);
  const rollup = excludingLine(pack);

  return (
    <main style={{ padding: "32px 28px", maxWidth: 1180, margin: "0 auto" }}>
      {/* Header: app name + inclusion score */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 8,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: 26, letterSpacing: -0.5 }}>InclusionScope</h1>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 999,
                background: live ? "#052e2b" : "#1e2434",
                color: live ? "#5eead4" : "#94a3b8",
                border: `1px solid ${live ? "#134e4a" : "#2a3142"}`,
              }}
            >
              {live ? "LIVE RUN" : "SAMPLE"}
            </span>
          </div>
          <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 14 }}>
            {pack.app} · run {new Date(pack.run_at).toUTCString()}
          </p>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase", color: "var(--faint)" }}>
            Composite inclusion score
          </div>
          <div
            style={{
              fontSize: 40,
              fontWeight: 800,
              lineHeight: 1,
              color: scorePct >= 80 ? "#22c55e" : scorePct >= 50 ? "#f59e0b" : "#ef4444",
            }}
          >
            {scorePct}
            <span style={{ fontSize: 18, color: "var(--faint)", fontWeight: 600 }}> / 100</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--faint)", marginTop: 2 }}>
            derived · weights w1·behavioral + w2·wcag + w3·llm
          </div>
        </div>
      </header>

      {/* "Who are we excluding" rollup — the business line (§14) */}
      {rollup && (
        <div
          style={{
            background: "#1a0f12",
            border: "1px solid #5b2330",
            borderLeft: "3px solid #ef4444",
            borderRadius: 12,
            padding: "14px 18px",
            margin: "18px 0 28px",
            fontSize: 16,
            fontWeight: 600,
            color: "#fecaca",
          }}
        >
          {rollup}
        </div>
      )}

      {/* HERO — the friction matrix diff (§14, FR-3.3) */}
      <section className="is-card" style={{ marginBottom: 24 }}>
        <p className="is-eyebrow">The diff is the hero</p>
        <h2 className="is-h2">Friction matrix — persona × step</h2>
        <FrictionMatrix matrix={pack.matrix} />
      </section>

      {/* CENTERPIECE — empathy replay */}
      <section className="is-card" style={{ marginBottom: 24 }}>
        <p className="is-eyebrow">Centerpiece</p>
        <h2 className="is-h2">Empathy replay — see the screen through the persona&apos;s eyes</h2>
        <EmpathyReplay />
      </section>

      {/* TRUSTED vs INDICATIVE split (§16) */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(280px, 1fr) minmax(280px, 1.4fr)",
          gap: 20,
          marginBottom: 24,
          alignItems: "start",
        }}
      >
        <div className="is-card">
          <span className="is-tag is-tag--trusted">Trusted — WCAG conformance</span>
          <h2 className="is-h2" style={{ marginTop: 12 }}>
            Machine-verifiable findings
          </h2>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "-8px 0 12px" }}>
            Straight from axe-core + a11y signals. Reliable without trusting the simulation.
          </p>
          <WcagFindings conformance={pack.wcag_conformance} />
        </div>

        <div className="is-card">
          <span className="is-tag is-tag--indicative">Indicative — persona simulation</span>
          <h2 className="is-h2" style={{ marginTop: 12 }}>
            Persona wall
          </h2>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "-8px 0 12px" }}>
            Behavioral / completion verdicts. Signal, not a compliance guarantee.
          </p>
          <PersonaPanel personas={pack.personas} />
        </div>
      </section>

      {/* Remediation */}
      <section className="is-card">
        <p className="is-eyebrow">Prioritized</p>
        <h2 className="is-h2">Remediation</h2>
        <Remediation items={pack.remediation} />
      </section>
    </main>
  );
}

// Typed data contract for the InclusionScope evidence pack (§14 demo surface,
// §16 two-stream discipline). The backend exposes GET {NEXT_PUBLIC_API_BASE}/runs/{run_id}
// returning a PackResult. SAMPLE_PACK lets the dashboard render with no live backend.

export type MatrixStatus = "green" | "amber" | "red" | "na";
export type Severity = "P0" | "P1" | "P2" | "P3" | null;
export type Verdict = "completed" | "blocked";
export type Conformance = "pass" | "fail";

export interface MatrixCell {
  status: MatrixStatus;
  dwell_s: number | null;
}

export interface Matrix {
  steps: string[];
  // persona id -> step id -> cell
  rows: Record<string, Record<string, MatrixCell>>;
}

export interface Persona {
  persona: string;
  verdict: Verdict;
  severity: Severity;
  blocked_at: string | null;
  // TRUSTED criteria this persona tripped (cross-links into wcag_conformance).
  wcag_failures: string[];
  // Always labeled indicative — persona simulation, not a compliance guarantee (§16).
  behavioral_note: string;
  inclusion_score: number;
}

export interface RemediationItem {
  criterion: string;
  issue: string;
  owner: string;
  severity: Severity;
}

export interface PackResult {
  app: string;
  run_at: string;
  inclusion_score: number;
  // TRUSTED stream — per-criterion WCAG conformance, reportable on its own (§16).
  wcag_conformance: Record<string, Conformance>;
  matrix: Matrix;
  // INDICATIVE stream — per-persona behavioral verdicts (§16).
  personas: Persona[];
  remediation: RemediationItem[];
}

// Default pack so the UI always renders for the demo, even with no backend.
export const SAMPLE_PACK: PackResult = {
  app: "DemoBank",
  run_at: "2026-06-19T00:00:00Z",
  inclusion_score: 0.62,
  wcag_conformance: { "1.4.3": "fail", "4.1.2": "fail", "1.3.1": "pass" },
  matrix: {
    steps: ["otp", "submit"],
    rows: {
      control: {
        otp: { status: "green", dwell_s: 3.2 },
        submit: { status: "green", dwell_s: 1.1 },
      },
      oku_visual: {
        otp: { status: "red", dwell_s: 4.0 },
        submit: { status: "na", dwell_s: null },
      },
    },
  },
  personas: [
    {
      persona: "control",
      verdict: "completed",
      severity: null,
      blocked_at: null,
      wcag_failures: [],
      behavioral_note: "indicative — persona-simulation signal",
      inclusion_score: 0.95,
    },
    {
      persona: "oku_visual",
      verdict: "blocked",
      severity: "P0",
      blocked_at: "otp",
      wcag_failures: ["4.1.2"],
      behavioral_note: "indicative — persona-simulation signal",
      inclusion_score: 0.3,
    },
  ],
  remediation: [
    {
      criterion: "4.1.2",
      issue: "Control missing accessible name/role/value",
      owner: "@content",
      severity: "P0",
    },
  ],
};

// Fetch a run's evidence pack from the backend. Throws on non-2xx so callers
// can fall back to SAMPLE_PACK for the demo.
export async function getRun(runId: string): Promise<PackResult> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const res = await fetch(`${base}/runs/${runId}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`getRun ${runId} failed: ${res.status}`);
  }
  return (await res.json()) as PackResult;
}

// Typed fixtures — the demo dataset. Mutated in-memory by lib/api.ts so the
// app feels live within a session. 8 personas, 2 projects, completed runs, and
// a deterministic live-run script (see lib/sse.ts).

import { generateFigurine } from "./format";
import type {
  FrictionMatrix,
  Persona,
  PersonaResult,
  Project,
  Repo,
  RunDetail,
  RunSummary,
  Severity,
} from "./types";

export const FLOW_STEPS = ["Sign in", "OTP verify", "ID upload", "Details form", "Confirm"];

function fig(id: string, name: string) {
  return generateFigurine(id, name);
}

// ── 8 personas ───────────────────────────────────────────────
export const personas: Persona[] = [
  {
    id: "p-mei",
    name: "Aunty Mei",
    label: "OKU — visual (low-vision)",
    ageBand: "65+",
    techSavviness: 0.18,
    patience: 0.22,
    language: "Cantonese",
    disabilities: ["screen reader", "low vision"],
    behaviorProfile: { dwellMultiplier: 2.4, hesitationProb: 0.7, readingSpeedWpm: 90, giveupThresholdS: 25, retryLimit: 2 },
    figurineUrl: fig("p-mei", "Aunty Mei"),
    figurineStatus: "ready",
  },
  {
    id: "p-david",
    name: "David Lim",
    label: "Power user",
    ageBand: "25–34",
    techSavviness: 0.95,
    patience: 0.8,
    language: "English",
    disabilities: [],
    behaviorProfile: { dwellMultiplier: 0.7, hesitationProb: 0.1, readingSpeedWpm: 260, giveupThresholdS: 90, retryLimit: 5 },
    figurineUrl: fig("p-david", "David Lim"),
    figurineStatus: "ready",
  },
  {
    id: "p-siti",
    name: "Siti Nurhaliza",
    label: "Elderly — first-time digital",
    ageBand: "55–64",
    techSavviness: 0.3,
    patience: 0.5,
    language: "Bahasa Melayu",
    disabilities: [],
    behaviorProfile: { dwellMultiplier: 1.9, hesitationProb: 0.55, readingSpeedWpm: 120, giveupThresholdS: 45, retryLimit: 3 },
    figurineUrl: fig("p-siti", "Siti Nurhaliza"),
    figurineStatus: "ready",
  },
  {
    id: "p-raj",
    name: "Raj Kumar",
    label: "Colour-blind (deuteranopia)",
    ageBand: "35–44",
    techSavviness: 0.7,
    patience: 0.65,
    language: "English",
    disabilities: ["colour vision"],
    behaviorProfile: { dwellMultiplier: 1.0, hesitationProb: 0.2, readingSpeedWpm: 220, giveupThresholdS: 70, retryLimit: 4 },
    figurineUrl: fig("p-raj", "Raj Kumar"),
    figurineStatus: "ready",
  },
  {
    id: "p-grace",
    name: "Grace Tan",
    label: "Motor — keyboard-only",
    ageBand: "45–54",
    techSavviness: 0.6,
    patience: 0.45,
    language: "English",
    disabilities: ["keyboard only", "motor"],
    behaviorProfile: { dwellMultiplier: 1.5, hesitationProb: 0.35, readingSpeedWpm: 200, giveupThresholdS: 50, retryLimit: 3 },
    figurineUrl: fig("p-grace", "Grace Tan"),
    figurineStatus: "ready",
  },
  {
    id: "p-tom",
    name: "Tom Wright",
    label: "Cognitive — dyslexia",
    ageBand: "18–24",
    techSavviness: 0.55,
    patience: 0.4,
    language: "English",
    disabilities: ["dyslexia"],
    behaviorProfile: { dwellMultiplier: 1.7, hesitationProb: 0.5, readingSpeedWpm: 110, giveupThresholdS: 40, retryLimit: 3 },
    figurineUrl: fig("p-tom", "Tom Wright"),
    figurineStatus: "ready",
  },
  {
    id: "p-lina",
    name: "Lina Abdullah",
    label: "Non-native speaker (BM primary)",
    ageBand: "25–34",
    techSavviness: 0.5,
    patience: 0.55,
    language: "Bahasa Melayu",
    disabilities: [],
    behaviorProfile: { dwellMultiplier: 1.4, hesitationProb: 0.45, readingSpeedWpm: 140, giveupThresholdS: 55, retryLimit: 3 },
    figurineStatus: "generating",
  },
  {
    id: "p-ahmad",
    name: "Ahmad Faizal",
    label: "Average user — mobile",
    ageBand: "35–44",
    techSavviness: 0.65,
    patience: 0.6,
    language: "English",
    disabilities: [],
    behaviorProfile: { dwellMultiplier: 1.1, hesitationProb: 0.25, readingSpeedWpm: 210, giveupThresholdS: 65, retryLimit: 4 },
    figurineStatus: "none",
  },
];

const byId = (id: string): Persona => personas.find((p) => p.id === id)!;

// ── projects + repos ─────────────────────────────────────────
const now = Date.now();
const ago = (ms: number) => new Date(now - ms).toISOString();
const H = 3_600_000;
const D = 86_400_000;

export const projects: Project[] = [
  { id: "proj-mydigital", name: "MyDigital ID Onboarding", description: "National e-ID sign-up & verification flow.", personaCount: 6, latestScore: 0.62, lastRunAt: ago(2 * H) },
  { id: "proj-finbank", name: "FinBank Account Opening", description: "Retail bank digital account opening.", personaCount: 4, latestScore: 0.81, lastRunAt: ago(2 * D) },
];

export const repos: Repo[] = [
  { id: "repo-mydigital", projectId: "proj-mydigital", name: "mydigital-web (staging)", stagingUrl: "https://staging.mydigital.gov.my", viewport: "desktop", personaIds: ["p-mei", "p-david", "p-siti", "p-raj", "p-grace", "p-tom"] },
  { id: "repo-finbank", projectId: "proj-finbank", name: "finbank-onboarding (staging)", stagingUrl: "https://staging.finbank.com", viewport: "mobile", personaIds: ["p-david", "p-raj", "p-lina", "p-ahmad"] },
];

// ── matrix builder: derive friction matrix from persona results ──
function buildMatrix(results: PersonaResult[]): FrictionMatrix {
  return {
    steps: FLOW_STEPS,
    rows: results.map((r) => {
      const blockIdx = r.blockedAt ? FLOW_STEPS.indexOf(r.blockedAt) : -1;
      return {
        personaId: r.personaId,
        cells: FLOW_STEPS.map((stepName, i) => {
          const step = r.steps.find((s) => s.stepName === stepName);
          if (blockIdx >= 0 && i >= blockIdx) {
            return { stepName, status: "blocked" as Severity, dwellMs: null };
          }
          return { stepName, status: step?.status ?? "ok", dwellMs: step?.dwellMs ?? 0 };
        }),
      };
    }),
  };
}

type StepSpec = [Severity, number];
function result(personaId: string, confusionScore: number, blockedAt: string | undefined, steps: Record<string, StepSpec>): PersonaResult {
  const persona = byId(personaId);
  const reached = Object.entries(steps).map(([stepName, [status, dwellMs]]) => ({ stepName, status, dwellMs }));
  const completed = !blockedAt;
  const status: Severity = blockedAt ? "blocked" : reached.some((s) => s.status === "friction") ? "friction" : "ok";
  return { personaId, persona, confusionScore, status, blockedAt, completed, steps: reached };
}

// ── completed run for MyDigital (the headline report) ──
const mydigitalResults: PersonaResult[] = [
  result("p-mei", 0.86, "ID upload", { "Sign in": ["ok", 6200], "OTP verify": ["friction", 18400] }),
  result("p-siti", 0.54, undefined, { "Sign in": ["friction", 11800], "OTP verify": ["friction", 16200], "ID upload": ["ok", 9100], "Details form": ["friction", 24600], Confirm: ["ok", 7300] }),
  result("p-grace", 0.49, undefined, { "Sign in": ["ok", 5200], "OTP verify": ["ok", 7400], "ID upload": ["friction", 16800], "Details form": ["friction", 19200], Confirm: ["ok", 8100] }),
  result("p-tom", 0.41, undefined, { "Sign in": ["ok", 5600], "OTP verify": ["friction", 17600], "ID upload": ["ok", 8200], "Details form": ["friction", 14100], Confirm: ["ok", 6400] }),
  result("p-david", 0.08, undefined, { "Sign in": ["ok", 2100], "OTP verify": ["ok", 3000], "ID upload": ["ok", 2600], "Details form": ["ok", 4200], Confirm: ["ok", 1900] }),
  result("p-raj", 0.16, undefined, { "Sign in": ["ok", 3400], "OTP verify": ["ok", 4100], "ID upload": ["ok", 3800], "Details form": ["ok", 6200], Confirm: ["ok", 2700] }),
];

const finbankResults: PersonaResult[] = [
  result("p-david", 0.07, undefined, { "Sign in": ["ok", 2000], "OTP verify": ["ok", 2800], "ID upload": ["ok", 2400], "Details form": ["ok", 3900], Confirm: ["ok", 1800] }),
  result("p-raj", 0.14, undefined, { "Sign in": ["ok", 3100], "OTP verify": ["ok", 3700], "ID upload": ["ok", 3500], "Details form": ["ok", 5400], Confirm: ["ok", 2500] }),
  result("p-lina", 0.38, undefined, { "Sign in": ["ok", 5800], "OTP verify": ["friction", 12200], "ID upload": ["ok", 6900], "Details form": ["friction", 13400], Confirm: ["ok", 5100] }),
  result("p-ahmad", 0.21, undefined, { "Sign in": ["ok", 4200], "OTP verify": ["ok", 5100], "ID upload": ["friction", 11800], "Details form": ["ok", 6700], Confirm: ["ok", 3900] }),
];

function makeRun(id: string, projectId: string, mode: "sequential" | "parallel", createdAt: string, overallScore: number, results: PersonaResult[]): RunDetail {
  return { id, projectId, mode, status: "completed", createdAt, overallScore, personaResults: results, frictionMatrix: buildMatrix(results) };
}

export const runs: Record<string, RunDetail> = {
  "run-mydigital-1001": makeRun("run-mydigital-1001", "proj-mydigital", "sequential", ago(2 * H), 0.62, mydigitalResults),
  "run-mydigital-1000": makeRun("run-mydigital-1000", "proj-mydigital", "parallel", ago(2 * D), 0.58, mydigitalResults),
  "run-mydigital-0999": makeRun("run-mydigital-0999", "proj-mydigital", "sequential", ago(5 * D), 0.55, mydigitalResults),
  "run-finbank-2001": makeRun("run-finbank-2001", "proj-finbank", "parallel", ago(2 * D), 0.81, finbankResults),
};

function blockedCount(r: RunDetail): number {
  return r.personaResults.filter((p) => p.status === "blocked").length;
}

export const runSummaries: Record<string, RunSummary[]> = {
  "proj-mydigital": [
    { id: "run-mydigital-1001", projectId: "proj-mydigital", mode: "sequential", createdAt: ago(2 * H), overallScore: 0.62, blockedCount: 1 },
    { id: "run-mydigital-1000", projectId: "proj-mydigital", mode: "parallel", createdAt: ago(2 * D), overallScore: 0.58, blockedCount: 1 },
    { id: "run-mydigital-0999", projectId: "proj-mydigital", mode: "sequential", createdAt: ago(5 * D), overallScore: 0.55, blockedCount: 1 },
  ],
  "proj-finbank": [{ id: "run-finbank-2001", projectId: "proj-finbank", mode: "parallel", createdAt: ago(2 * D), overallScore: 0.81, blockedCount: 0 }],
};

export const latestRunByProject: Record<string, string> = {
  "proj-mydigital": "run-mydigital-1001",
  "proj-finbank": "run-finbank-2001",
};

export { blockedCount, mydigitalResults };

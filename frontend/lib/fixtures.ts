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
    identity: { name: "Aunty Mei", label: "OKU — visual (low-vision)", ageBand: "65+", language: "Cantonese", techSavviness: 0.18, disabilities: ["screen reader", "low vision"] },
    behavior: { dwellMultiplier: 2.4, giveupThresholdS: 25, misinterpretProb: 0.65 },
    figurineUrl: fig("p-mei", "Aunty Mei"),
    figurineStatus: "ready",
  },
  {
    id: "p-david",
    identity: { name: "David Lim", label: "Power user", ageBand: "25–34", language: "English", techSavviness: 0.95, disabilities: [] },
    behavior: { dwellMultiplier: 0.7, giveupThresholdS: 90, misinterpretProb: 0.05 },
    figurineUrl: fig("p-david", "David Lim"),
    figurineStatus: "ready",
  },
  {
    id: "p-siti",
    identity: { name: "Siti Nurhaliza", label: "Elderly — first-time digital", ageBand: "55–64", language: "Bahasa Melayu", techSavviness: 0.3, disabilities: [] },
    behavior: { dwellMultiplier: 1.9, giveupThresholdS: 45, misinterpretProb: 0.5 },
    figurineUrl: fig("p-siti", "Siti Nurhaliza"),
    figurineStatus: "ready",
  },
  {
    id: "p-raj",
    identity: { name: "Raj Kumar", label: "Colour-blind (deuteranopia)", ageBand: "35–44", language: "English", techSavviness: 0.7, disabilities: ["colour vision"] },
    behavior: { dwellMultiplier: 1.0, giveupThresholdS: 70, misinterpretProb: 0.15 },
    figurineUrl: fig("p-raj", "Raj Kumar"),
    figurineStatus: "ready",
  },
  {
    id: "p-grace",
    identity: { name: "Grace Tan", label: "Motor — keyboard-only", ageBand: "45–54", language: "English", techSavviness: 0.6, disabilities: ["keyboard only", "motor"] },
    behavior: { dwellMultiplier: 1.5, giveupThresholdS: 50, misinterpretProb: 0.2 },
    figurineUrl: fig("p-grace", "Grace Tan"),
    figurineStatus: "ready",
  },
  {
    id: "p-tom",
    identity: { name: "Tom Wright", label: "Cognitive — dyslexia", ageBand: "18–24", language: "English", techSavviness: 0.55, disabilities: ["dyslexia"] },
    behavior: { dwellMultiplier: 1.7, giveupThresholdS: 40, misinterpretProb: 0.45 },
    figurineUrl: fig("p-tom", "Tom Wright"),
    figurineStatus: "ready",
  },
  {
    id: "p-lina",
    identity: { name: "Lina Abdullah", label: "Non-native speaker (BM primary)", ageBand: "25–34", language: "Bahasa Melayu", techSavviness: 0.5, disabilities: [] },
    behavior: { dwellMultiplier: 1.4, giveupThresholdS: 55, misinterpretProb: 0.4 },
    figurineStatus: "generating",
  },
  {
    id: "p-ahmad",
    identity: { name: "Ahmad Faizal", label: "Average user — mobile", ageBand: "35–44", language: "English", techSavviness: 0.65, disabilities: [] },
    behavior: { dwellMultiplier: 1.1, giveupThresholdS: 65, misinterpretProb: 0.2 },
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
  { id: "proj-mydigital", name: "MyDigital ID Onboarding", description: "National e-ID sign-up & verification flow.", repoUrl: "https://github.com/mydigital/mydigital-web", stagingUrl: "https://staging.mydigital.gov.my", personaCount: 6, latestScore: 0.62, lastRunAt: ago(2 * H) },
  { id: "proj-finbank", name: "FinBank Account Opening", description: "Retail bank digital account opening.", repoUrl: "https://github.com/finbank/onboarding", stagingUrl: "https://staging.finbank.com", personaCount: 4, latestScore: 0.81, lastRunAt: ago(2 * D) },
];

export const repos: Repo[] = [
  { id: "repo-mydigital", projectId: "proj-mydigital", name: "mydigital-web (staging)", stagingUrl: "https://staging.mydigital.gov.my", repoUrl: "https://github.com/mydigital/mydigital-web", viewport: "desktop", personaIds: ["p-mei", "p-david", "p-siti", "p-raj", "p-grace", "p-tom"] },
  { id: "repo-finbank", projectId: "proj-finbank", name: "finbank-onboarding (staging)", stagingUrl: "https://staging.finbank.com", repoUrl: "https://github.com/finbank/onboarding", viewport: "mobile", personaIds: ["p-david", "p-raj", "p-lina", "p-ahmad"] },
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

type StepSpec = { status: Severity; dwellMs: number; innerMonologue: string; confusionLevel: number; understandability: number };
function result(personaId: string, confusionScore: number, blockedAt: string | undefined, steps: Record<string, StepSpec>): PersonaResult {
  const persona = byId(personaId);
  const reached = Object.entries(steps).map(([stepName, s]) => ({
    stepName, status: s.status, dwellMs: s.dwellMs,
    innerMonologue: s.innerMonologue, confusionLevel: s.confusionLevel, understandability: s.understandability,
  }));
  const completed = !blockedAt;
  const status: Severity = blockedAt ? "blocked" : reached.some((s) => s.status === "friction") ? "friction" : "ok";
  return { personaId, persona, confusionScore, status, blockedAt, completed, steps: reached };
}

// ── completed run for MyDigital (the headline report) ──
const mydigitalResults: PersonaResult[] = [
  result("p-mei", 0.86, "ID upload", {
    "Sign in": { status: "ok", dwellMs: 6200, innerMonologue: "Okay, I found the login box. The text is a bit small but I can make it out.", confusionLevel: 0.15, understandability: 0.78 },
    "OTP verify": { status: "friction", dwellMs: 18400, innerMonologue: "A code was sent... where? I can't tell which number it was sent to. The text is too faint.", confusionLevel: 0.52, understandability: 0.42 },
  }),
  result("p-siti", 0.54, undefined, {
    "Sign in": { status: "friction", dwellMs: 11800, innerMonologue: "I see the form but I'm not sure if I should use my email or phone number. Let me try email.", confusionLevel: 0.28, understandability: 0.55 },
    "OTP verify": { status: "friction", dwellMs: 16200, innerMonologue: "The code arrived but I'm not sure which phone it went to. Let me check both.", confusionLevel: 0.42, understandability: 0.48 },
    "ID upload": { status: "ok", dwellMs: 9100, innerMonologue: "It wants my MyKad. I have it here — let me take a photo.", confusionLevel: 0.2, understandability: 0.82 },
    "Details form": { status: "friction", dwellMs: 24600, innerMonologue: "The date field won't accept what I typed. I'm not sure of the format it wants.", confusionLevel: 0.55, understandability: 0.38 },
    "Confirm": { status: "ok", dwellMs: 7300, innerMonologue: "That was a lot of steps but it says I'm done. I hope I did it right.", confusionLevel: 0.35, understandability: 0.72 },
  }),
  result("p-grace", 0.49, undefined, {
    "Sign in": { status: "ok", dwellMs: 5200, innerMonologue: "Login form looks straightforward. Tab to email, type, tab to password.", confusionLevel: 0.1, understandability: 0.88 },
    "OTP verify": { status: "ok", dwellMs: 7400, innerMonologue: "Got the code. Tab to the input field and type it in.", confusionLevel: 0.12, understandability: 0.85 },
    "ID upload": { status: "friction", dwellMs: 16800, innerMonologue: "The upload button is tiny — I keep tabbing past it. The focus order seems off.", confusionLevel: 0.38, understandability: 0.52 },
    "Details form": { status: "friction", dwellMs: 19200, innerMonologue: "These form fields are cramped. Hard to tell which label goes with which input by keyboard alone.", confusionLevel: 0.45, understandability: 0.45 },
    "Confirm": { status: "ok", dwellMs: 8100, innerMonologue: "Done. The confirmation page is clear enough.", confusionLevel: 0.2, understandability: 0.8 },
  }),
  result("p-tom", 0.41, undefined, {
    "Sign in": { status: "ok", dwellMs: 5600, innerMonologue: "Login page. I can see the fields. The instructions are short — that helps.", confusionLevel: 0.12, understandability: 0.82 },
    "OTP verify": { status: "friction", dwellMs: 17600, innerMonologue: "The OTP screen has a lot of dense text. I'm re-reading to understand what to do.", confusionLevel: 0.38, understandability: 0.4 },
    "ID upload": { status: "ok", dwellMs: 8200, innerMonologue: "Upload page is simple enough. Big button, clear instruction.", confusionLevel: 0.15, understandability: 0.78 },
    "Details form": { status: "friction", dwellMs: 14100, innerMonologue: "So many fields, all bunched together. The words are running together for me.", confusionLevel: 0.42, understandability: 0.35 },
    "Confirm": { status: "ok", dwellMs: 6400, innerMonologue: "Finished. The green tick is reassuring.", confusionLevel: 0.18, understandability: 0.85 },
  }),
  result("p-david", 0.08, undefined, {
    "Sign in": { status: "ok", dwellMs: 2100, innerMonologue: "Standard login. Email, password, submit.", confusionLevel: 0.05, understandability: 0.95 },
    "OTP verify": { status: "ok", dwellMs: 3000, innerMonologue: "OTP arrived, four digits. Clear which number it was sent to.", confusionLevel: 0.08, understandability: 0.92 },
    "ID upload": { status: "ok", dwellMs: 2600, innerMonologue: "Drag-and-drop upload area. Clean interface.", confusionLevel: 0.06, understandability: 0.94 },
    "Details form": { status: "ok", dwellMs: 4200, innerMonologue: "Standard KYC fields. All clearly labeled.", confusionLevel: 0.1, understandability: 0.9 },
    "Confirm": { status: "ok", dwellMs: 1900, innerMonologue: "Confirmation screen. All done.", confusionLevel: 0.04, understandability: 0.96 },
  }),
  result("p-raj", 0.16, undefined, {
    "Sign in": { status: "ok", dwellMs: 3400, innerMonologue: "Login page loads fine. Colours look a bit washed out but readable.", confusionLevel: 0.08, understandability: 0.9 },
    "OTP verify": { status: "ok", dwellMs: 4100, innerMonologue: "Code arrived. The green confirmation text is hard to distinguish from grey, but I can read it.", confusionLevel: 0.15, understandability: 0.82 },
    "ID upload": { status: "ok", dwellMs: 3800, innerMonologue: "Upload area is clear. The dashed border is visible enough.", confusionLevel: 0.1, understandability: 0.88 },
    "Details form": { status: "ok", dwellMs: 6200, innerMonologue: "Form fields are fine. The error states might be hard to spot if they rely on colour alone.", confusionLevel: 0.18, understandability: 0.78 },
    "Confirm": { status: "ok", dwellMs: 2700, innerMonologue: "Done. The success icon shape helps since the green is ambiguous for me.", confusionLevel: 0.12, understandability: 0.85 },
  }),
];

const finbankResults: PersonaResult[] = [
  result("p-david", 0.07, undefined, {
    "Sign in": { status: "ok", dwellMs: 2000, innerMonologue: "Clean login. No issues.", confusionLevel: 0.04, understandability: 0.96 },
    "OTP verify": { status: "ok", dwellMs: 2800, innerMonologue: "OTP clear and quick.", confusionLevel: 0.06, understandability: 0.94 },
    "ID upload": { status: "ok", dwellMs: 2400, innerMonologue: "Upload is straightforward.", confusionLevel: 0.05, understandability: 0.95 },
    "Details form": { status: "ok", dwellMs: 3900, innerMonologue: "Standard fields, clearly labeled.", confusionLevel: 0.08, understandability: 0.92 },
    "Confirm": { status: "ok", dwellMs: 1800, innerMonologue: "Done.", confusionLevel: 0.03, understandability: 0.97 },
  }),
  result("p-raj", 0.14, undefined, {
    "Sign in": { status: "ok", dwellMs: 3100, innerMonologue: "Login looks fine. Text is readable.", confusionLevel: 0.06, understandability: 0.92 },
    "OTP verify": { status: "ok", dwellMs: 3700, innerMonologue: "Code arrived. Status text is a bit ambiguous in colour but legible.", confusionLevel: 0.12, understandability: 0.85 },
    "ID upload": { status: "ok", dwellMs: 3500, innerMonologue: "Upload area clearly outlined.", confusionLevel: 0.08, understandability: 0.9 },
    "Details form": { status: "ok", dwellMs: 5400, innerMonologue: "Form is fine. Would prefer icons over colour for required fields.", confusionLevel: 0.16, understandability: 0.8 },
    "Confirm": { status: "ok", dwellMs: 2500, innerMonologue: "Success page is clear with the checkmark shape.", confusionLevel: 0.1, understandability: 0.88 },
  }),
  result("p-lina", 0.38, undefined, {
    "Sign in": { status: "ok", dwellMs: 5800, innerMonologue: "I can read most of this. Some words are unfamiliar but the layout helps.", confusionLevel: 0.15, understandability: 0.72 },
    "OTP verify": { status: "friction", dwellMs: 12200, innerMonologue: "The message says 'verification' but I'm not sure what 'OTP' stands for. Let me look around.", confusionLevel: 0.42, understandability: 0.45 },
    "ID upload": { status: "ok", dwellMs: 6900, innerMonologue: "The upload icon makes it clear even if I don't know every word.", confusionLevel: 0.18, understandability: 0.75 },
    "Details form": { status: "friction", dwellMs: 13400, innerMonologue: "Some field labels use terms I don't recognise. 'Beneficial ownership' — what does that mean?", confusionLevel: 0.48, understandability: 0.38 },
    "Confirm": { status: "ok", dwellMs: 5100, innerMonologue: "The green tick tells me I'm done even if I didn't understand everything.", confusionLevel: 0.22, understandability: 0.68 },
  }),
  result("p-ahmad", 0.21, undefined, {
    "Sign in": { status: "ok", dwellMs: 4200, innerMonologue: "Login is standard. No problems on mobile.", confusionLevel: 0.08, understandability: 0.9 },
    "OTP verify": { status: "ok", dwellMs: 5100, innerMonologue: "Code came through. Easy to enter on mobile.", confusionLevel: 0.1, understandability: 0.88 },
    "ID upload": { status: "friction", dwellMs: 11800, innerMonologue: "The upload button is quite small on my phone screen. Took a few taps to hit it.", confusionLevel: 0.32, understandability: 0.58 },
    "Details form": { status: "ok", dwellMs: 6700, innerMonologue: "Fields are a bit tight but manageable.", confusionLevel: 0.15, understandability: 0.78 },
    "Confirm": { status: "ok", dwellMs: 3900, innerMonologue: "All submitted. Clear confirmation.", confusionLevel: 0.08, understandability: 0.92 },
  }),
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

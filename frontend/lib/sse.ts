import type { RunEvent, Severity } from "./types";
import { FLOW_STEPS } from "./fixtures";

interface ScriptStep {
  personaId: string;
  stepIdx: number;
  stepName: string;
  status: Severity;
  dwellMs: number;
  confusionScore: number;
  delayMs: number;
}

interface ScriptDone {
  personaId: string;
  confusionScore: number;
  completed: boolean;
  blockedAt?: string;
  delayMs: number;
}

interface ScriptEnd {
  overallScore: number;
  delayMs: number;
}

type ScriptEntry =
  | ({ type: "persona_step" } & ScriptStep)
  | ({ type: "persona_done" } & ScriptDone)
  | ({ type: "run_done" } & ScriptEnd);

const SCRIPT: ScriptEntry[] = [
  { type: "persona_step", personaId: "p-david", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 2100, confusionScore: 0.02, delayMs: 800 },
  { type: "persona_step", personaId: "p-david", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 3000, confusionScore: 0.04, delayMs: 1200 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 3400, confusionScore: 0.03, delayMs: 600 },
  { type: "persona_step", personaId: "p-david", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 2600, confusionScore: 0.05, delayMs: 1000 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 4100, confusionScore: 0.06, delayMs: 800 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 6200, confusionScore: 0.15, delayMs: 1200 },
  { type: "persona_step", personaId: "p-david", stepIdx: 3, stepName: "Details form", status: "ok", dwellMs: 4200, confusionScore: 0.06, delayMs: 900 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 0, stepName: "Sign in", status: "friction", dwellMs: 11800, confusionScore: 0.22, delayMs: 1000 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 3800, confusionScore: 0.08, delayMs: 700 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 18400, confusionScore: 0.52, delayMs: 1500 },
  { type: "persona_step", personaId: "p-david", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 1900, confusionScore: 0.08, delayMs: 600 },
  { type: "persona_done", personaId: "p-david", confusionScore: 0.08, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 16200, confusionScore: 0.38, delayMs: 1200 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 3, stepName: "Details form", status: "ok", dwellMs: 6200, confusionScore: 0.1, delayMs: 800 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 5200, confusionScore: 0.08, delayMs: 700 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 2, stepName: "ID upload", status: "blocked", dwellMs: 0, confusionScore: 0.86, delayMs: 2000 },
  { type: "persona_done", personaId: "p-mei", confusionScore: 0.86, completed: false, blockedAt: "ID upload", delayMs: 500 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 5600, confusionScore: 0.1, delayMs: 800 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 2700, confusionScore: 0.16, delayMs: 600 },
  { type: "persona_done", personaId: "p-raj", confusionScore: 0.16, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 9100, confusionScore: 0.35, delayMs: 900 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 7400, confusionScore: 0.12, delayMs: 700 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 17600, confusionScore: 0.28, delayMs: 1200 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 24600, confusionScore: 0.48, delayMs: 1400 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 2, stepName: "ID upload", status: "friction", dwellMs: 16800, confusionScore: 0.25, delayMs: 1000 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 8200, confusionScore: 0.3, delayMs: 800 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 7300, confusionScore: 0.54, delayMs: 700 },
  { type: "persona_done", personaId: "p-siti", confusionScore: 0.54, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 19200, confusionScore: 0.38, delayMs: 1100 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 14100, confusionScore: 0.36, delayMs: 900 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 8100, confusionScore: 0.49, delayMs: 700 },
  { type: "persona_done", personaId: "p-grace", confusionScore: 0.49, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 6400, confusionScore: 0.41, delayMs: 600 },
  { type: "persona_done", personaId: "p-tom", confusionScore: 0.41, completed: true, delayMs: 300 },
  { type: "run_done", overallScore: 0.62, delayMs: 500 },
];

export type EventCallback = (event: RunEvent) => void;

export function subscribeToRun(
  _runId: string,
  onEvent: EventCallback,
  onDone: () => void,
): () => void {
  let cancelled = false;
  let timeouts: ReturnType<typeof setTimeout>[] = [];

  let cumulative = 0;
  for (const entry of SCRIPT) {
    cumulative += entry.delayMs;
    const t = setTimeout(() => {
      if (cancelled) return;
      const { delayMs: _, ...data } = entry;
      onEvent(data as RunEvent);
    }, cumulative);
    timeouts.push(t);
  }

  const doneTimeout = setTimeout(() => {
    if (!cancelled) onDone();
  }, cumulative + 200);
  timeouts.push(doneTimeout);

  return () => {
    cancelled = true;
    timeouts.forEach(clearTimeout);
    timeouts = [];
  };
}

export { FLOW_STEPS };

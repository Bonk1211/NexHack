import type { RunEvent, Severity } from "./types";
import { FLOW_STEPS } from "./fixtures";

interface ScriptStep {
  personaId: string;
  stepIdx: number;
  stepName: string;
  status: Severity;
  dwellMs: number;
  confusionScore: number;
  innerMonologue: string;
  confusionLevel: number;
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
  { type: "persona_step", personaId: "p-david", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 2100, confusionScore: 0.02, innerMonologue: "Standard login. Email, password, submit.", confusionLevel: 0.05, delayMs: 800 },
  { type: "persona_step", personaId: "p-david", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 3000, confusionScore: 0.04, innerMonologue: "OTP arrived, four digits. Clear which number it was sent to.", confusionLevel: 0.08, delayMs: 1200 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 3400, confusionScore: 0.03, innerMonologue: "Login page loads fine. Colours look a bit washed out but readable.", confusionLevel: 0.08, delayMs: 600 },
  { type: "persona_step", personaId: "p-david", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 2600, confusionScore: 0.05, innerMonologue: "Drag-and-drop upload area. Clean interface.", confusionLevel: 0.06, delayMs: 1000 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 4100, confusionScore: 0.06, innerMonologue: "Code arrived. The green confirmation text is hard to distinguish from grey, but I can read it.", confusionLevel: 0.15, delayMs: 800 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 6200, confusionScore: 0.15, innerMonologue: "Okay, I found the login box. The text is a bit small but I can make it out.", confusionLevel: 0.15, delayMs: 1200 },
  { type: "persona_step", personaId: "p-david", stepIdx: 3, stepName: "Details form", status: "ok", dwellMs: 4200, confusionScore: 0.06, innerMonologue: "Standard KYC fields. All clearly labeled.", confusionLevel: 0.1, delayMs: 900 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 0, stepName: "Sign in", status: "friction", dwellMs: 11800, confusionScore: 0.22, innerMonologue: "I see the form but I'm not sure if I should use my email or phone number. Let me try email.", confusionLevel: 0.28, delayMs: 1000 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 3800, confusionScore: 0.08, innerMonologue: "Upload area is clear. The dashed border is visible enough.", confusionLevel: 0.1, delayMs: 700 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 18400, confusionScore: 0.52, innerMonologue: "A code was sent... where? I can't tell which number it was sent to. The text is too faint.", confusionLevel: 0.52, delayMs: 1500 },
  { type: "persona_step", personaId: "p-david", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 1900, confusionScore: 0.08, innerMonologue: "Confirmation screen. All done.", confusionLevel: 0.04, delayMs: 600 },
  { type: "persona_done", personaId: "p-david", confusionScore: 0.08, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 16200, confusionScore: 0.38, innerMonologue: "The code arrived but I'm not sure which phone it went to. Let me check both.", confusionLevel: 0.42, delayMs: 1200 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 3, stepName: "Details form", status: "ok", dwellMs: 6200, confusionScore: 0.1, innerMonologue: "Form fields are fine. The error states might be hard to spot if they rely on colour alone.", confusionLevel: 0.18, delayMs: 800 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 5200, confusionScore: 0.08, innerMonologue: "Login form looks straightforward. Tab to email, type, tab to password.", confusionLevel: 0.1, delayMs: 700 },
  { type: "persona_step", personaId: "p-mei", stepIdx: 2, stepName: "ID upload", status: "blocked", dwellMs: 0, confusionScore: 0.86, innerMonologue: "It wants my 'MyKad'. Is that the same as my IC number? I've tried twice. I don't know what else to do. I'll stop here.", confusionLevel: 0.92, delayMs: 2000 },
  { type: "persona_done", personaId: "p-mei", confusionScore: 0.86, completed: false, blockedAt: "ID upload", delayMs: 500 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 0, stepName: "Sign in", status: "ok", dwellMs: 5600, confusionScore: 0.1, innerMonologue: "Login page. I can see the fields. The instructions are short — that helps.", confusionLevel: 0.12, delayMs: 800 },
  { type: "persona_step", personaId: "p-raj", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 2700, confusionScore: 0.16, innerMonologue: "Done. The success icon shape helps since the green is ambiguous for me.", confusionLevel: 0.12, delayMs: 600 },
  { type: "persona_done", personaId: "p-raj", confusionScore: 0.16, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 9100, confusionScore: 0.35, innerMonologue: "It wants my MyKad. I have it here — let me take a photo.", confusionLevel: 0.2, delayMs: 900 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 1, stepName: "OTP verify", status: "ok", dwellMs: 7400, confusionScore: 0.12, innerMonologue: "Got the code. Tab to the input field and type it in.", confusionLevel: 0.12, delayMs: 700 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 1, stepName: "OTP verify", status: "friction", dwellMs: 17600, confusionScore: 0.28, innerMonologue: "The OTP screen has a lot of dense text. I'm re-reading to understand what to do.", confusionLevel: 0.38, delayMs: 1200 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 24600, confusionScore: 0.48, innerMonologue: "The date field won't accept what I typed. I'm not sure of the format it wants.", confusionLevel: 0.55, delayMs: 1400 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 2, stepName: "ID upload", status: "friction", dwellMs: 16800, confusionScore: 0.25, innerMonologue: "The upload button is tiny — I keep tabbing past it. The focus order seems off.", confusionLevel: 0.38, delayMs: 1000 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 2, stepName: "ID upload", status: "ok", dwellMs: 8200, confusionScore: 0.3, innerMonologue: "Upload page is simple enough. Big button, clear instruction.", confusionLevel: 0.15, delayMs: 800 },
  { type: "persona_step", personaId: "p-siti", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 7300, confusionScore: 0.54, innerMonologue: "That was a lot of steps but it says I'm done. I hope I did it right.", confusionLevel: 0.35, delayMs: 700 },
  { type: "persona_done", personaId: "p-siti", confusionScore: 0.54, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 19200, confusionScore: 0.38, innerMonologue: "These form fields are cramped. Hard to tell which label goes with which input by keyboard alone.", confusionLevel: 0.45, delayMs: 1100 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 3, stepName: "Details form", status: "friction", dwellMs: 14100, confusionScore: 0.36, innerMonologue: "So many fields, all bunched together. The words are running together for me.", confusionLevel: 0.42, delayMs: 900 },
  { type: "persona_step", personaId: "p-grace", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 8100, confusionScore: 0.49, innerMonologue: "Done. The confirmation page is clear enough.", confusionLevel: 0.2, delayMs: 700 },
  { type: "persona_done", personaId: "p-grace", confusionScore: 0.49, completed: true, delayMs: 300 },
  { type: "persona_step", personaId: "p-tom", stepIdx: 4, stepName: "Confirm", status: "ok", dwellMs: 6400, confusionScore: 0.41, innerMonologue: "Finished. The green tick is reassuring.", confusionLevel: 0.18, delayMs: 600 },
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

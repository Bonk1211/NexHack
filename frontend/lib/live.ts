// Live backend client (FR-1.1–1.4). Unlike lib/api.ts (fixture mock), these call
// the real FastAPI agent: it loads the target in a mobile-emulated viewport, drives
// the flow per persona via the accessibility tree + vision-LLM fallback, captures a
// screenshot every step, and runs ≥3 personas over the same flow.

export const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/** Prefix server-relative screenshot paths (/artifacts/…) with the API host. */
export function mediaUrl(ref: string | null): string | null {
  if (!ref) return null;
  if (ref.startsWith("http://") || ref.startsWith("https://")) return ref;
  return `${BASE_URL}${ref}`;
}

export interface PersonaOption {
  stem: string;
  name: string;
  disabilities: string[];
  language?: string;
}

export interface ReplayFrame {
  step_idx: number;
  step_key: string;
  status: "green" | "amber" | "red" | "na";
  dwell_s: number | null;
  screenshot_url: string | null;
  caption: string;
}

export interface ReplayClip {
  lenses: string[];
  frames: ReplayFrame[];
}

export interface PersonaResult {
  persona: string;
  verdict: string;
  severity: string | null;
  blocked_at: string | null;
  wcag_failures: string[];
  inclusion_score: number;
}

export interface MatrixCell {
  status: "green" | "amber" | "red" | "na";
  dwell_s: number | null;
}

export interface Pack {
  app: string;
  inclusion_score: number;
  wcag_conformance: Record<string, string>;
  matrix: { steps: string[]; rows: Record<string, Record<string, MatrixCell>> };
  personas: PersonaResult[];
  remediation: { criterion: string; issue: string; owner: string; severity: string | null }[];
  replay: Record<string, ReplayClip>;
  synthesis?: { rollup: string; narrative: string; key_exclusions: string[] };
}

export interface RunResponse {
  run_id: string;
  pack: Pack;
  usage?: UsageSummary;
}

export interface UsageModelBreakdown {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  pricing_applied: boolean;
}

export interface UsageSummary {
  currency: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost: number;
  pricing_applied: boolean;
  models: UsageModelBreakdown[];
}

export async function getPersonas(): Promise<PersonaOption[]> {
  const res = await fetch(`${BASE_URL}/personas`);
  if (!res.ok) throw new Error(`GET /personas failed: ${res.status}`);
  return res.json();
}

export async function startRun(input: {
  appName: string;
  targetUrl: string;
  personaNames: string[];
}): Promise<RunResponse> {
  const res = await fetch(`${BASE_URL}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      app_name: input.appName,
      target_url: input.targetUrl,
      persona_names: input.personaNames,
    }),
  });
  if (!res.ok) throw new Error(`POST /runs failed: ${res.status}`);
  return res.json();
}

// ── Live streaming (SSE) — every LangGraph node as it runs ──────────────
export type NodeOutput = Record<string, unknown>;

export type StreamEvent =
  | { type: "node"; scope: "run"; node: string; personas?: string[]; output?: NodeOutput }
  | {
      type: "node";
      scope: "persona";
      persona: string;
      node: "observe" | "comprehend" | "decide";
      step_idx?: number;
      screenshot_url?: string | null;
      confusion?: number;
      dwell_s?: number;
      output?: NodeOutput;
    }
  | { type: "persona_start"; persona: string; idx: number; label: string }
  | {
      type: "step";
      persona: string;
      step_idx: number;
      step_key: string;
      status: "green" | "amber" | "red";
      confusion: number;
      dwell_s: number;
      screenshot_url: string | null;
      output?: NodeOutput;
    }
  | { type: "persona_done"; persona: string; verdict: string; severity: string | null; blocked_at: string | null }
  | { type: "frame"; persona: string; data: string } // base64 JPEG of the live browser
  | { type: "usage"; summary: UsageSummary }
  | { type: "final"; run_id: string; pack: Pack; usage?: UsageSummary }
  | { type: "error"; message: string };

/** Open an SSE run; calls onEvent for each event. Returns the EventSource (caller closes it). */
export function streamRun(
  input: { appName: string; targetUrl: string; personaNames: string[]; mode?: "sequential" | "parallel" },
  onEvent: (e: StreamEvent) => void,
): EventSource {
  const qs = new URLSearchParams({
    app_name: input.appName,
    target_url: input.targetUrl,
    persona_names: input.personaNames.join(","),
    mode: input.mode ?? "sequential",
  });
  const es = new EventSource(`${BASE_URL}/runs/stream?${qs.toString()}`);
  es.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data) as StreamEvent);
    } catch {
      /* ignore keep-alives / malformed frames */
    }
  };
  return es;
}

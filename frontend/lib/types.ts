// Core domain types — a faithful mirror of the FastAPI contracts in
// docs/prd/frontend-plan.md. Keeping these exact means swapping the mock
// client in lib/api.ts for real `fetch()` calls is a one-line change.

export type Severity = "ok" | "friction" | "blocked";
export type RunStatus = "pending" | "running" | "completed" | "failed";
export type RunMode = "sequential" | "parallel";
export type FigurineStatus = "none" | "generating" | "ready" | "failed";
export type Viewport = "desktop" | "tablet" | "mobile";

export interface BehaviorProfile {
  dwellMultiplier: number; // 0.5..3   — how long they linger per step
  hesitationProb: number; // 0..1     — chance of pausing/second-guessing
  readingSpeedWpm: number; // words per minute
  giveupThresholdS: number; // seconds before abandoning a step
  retryLimit: number; // attempts before blocked
}

export interface Persona {
  id: string;
  name: string;
  label: string; // e.g. "OKU — visual (low-vision)"
  ageBand: string;
  techSavviness: number; // 0..1
  patience: number; // 0..1
  language: string;
  disabilities: string[];
  behaviorProfile: BehaviorProfile;
  figurineUrl?: string;
  figurineStatus: FigurineStatus;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  personaCount: number;
  latestScore?: number; // 0..1
  lastRunAt?: string; // ISO-8601
}

export interface Repo {
  id: string;
  projectId: string;
  name: string;
  stagingUrl: string;
  viewport: Viewport;
  personaIds: string[];
}

export interface ProjectDetail extends Project {
  repos: Repo[];
  latestRun?: RunDetail;
}

export interface PersonaStepResult {
  stepName: string;
  status: Severity;
  dwellMs: number;
}

export interface PersonaResult {
  personaId: string;
  persona: Persona;
  confusionScore: number; // 0..1, higher = more confused
  status: Severity; // worst step status
  blockedAt?: string; // step name where they halted
  completed: boolean;
  steps: PersonaStepResult[];
}

export interface MatrixCell {
  stepName: string;
  status: Severity;
  dwellMs: number | null; // null once a persona is blocked
}

export interface FrictionMatrix {
  steps: string[];
  rows: { personaId: string; cells: MatrixCell[] }[];
}

export interface RunDetail {
  id: string;
  projectId: string;
  mode: RunMode;
  status: RunStatus;
  createdAt: string;
  overallScore: number; // 0..1
  personaResults: PersonaResult[];
  frictionMatrix: FrictionMatrix;
}

export interface RunSummary {
  id: string;
  projectId: string;
  mode: RunMode;
  createdAt: string;
  overallScore: number;
  blockedCount: number;
}

// ── SSE event payloads (GET /runs/:id/stream) ──
export interface PersonaStepEvent {
  type: "persona_step";
  personaId: string;
  stepIdx: number;
  stepName: string;
  status: Severity;
  dwellMs: number;
  confusionScore: number; // running per-lane confusion
}

export interface PersonaDoneEvent {
  type: "persona_done";
  personaId: string;
  confusionScore: number;
  completed: boolean;
  blockedAt?: string;
}

export interface RunDoneEvent {
  type: "run_done";
  overallScore: number;
}

export type RunEvent = PersonaStepEvent | PersonaDoneEvent | RunDoneEvent;

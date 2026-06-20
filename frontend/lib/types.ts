// Core domain types — a faithful mirror of the FastAPI contracts in
// docs/prd/frontend-plan.md. Keeping these exact means swapping the mock
// client in lib/api.ts for real `fetch()` calls is a one-line change.

export type Severity = "ok" | "friction" | "blocked";
export type RunStatus = "pending" | "running" | "completed" | "failed";
export type RunMode = "sequential" | "parallel";
export type FigurineStatus = "none" | "generating" | "ready" | "failed";
export type Viewport = "desktop" | "tablet" | "mobile";

export interface FlowStep {
  key: string;
  action: "fill" | "click" | "view";
  role: string;
  name: string;
  value: string;
  critical: boolean;
}

// TODO(cohort-sampling): BehaviorValue is currently always a plain number.
// When cohort mode is enabled, each field can become { mean, spread } to seed
// N personas from the same demographic with varied parameters.
export type BehaviorValue = number | { mean: number; spread: number };

export function resolveValue(v: BehaviorValue): number {
  return typeof v === "number" ? v : v.mean;
}

export interface PersonaIdentity {
  name: string;
  label: string;
  ageBand: string;
  language: string;
  techSavviness: number;
  disabilities: string[];
}

export interface PersonaBehavior {
  dwellMultiplier: BehaviorValue;
  giveupThresholdS: BehaviorValue;
  misinterpretProb: BehaviorValue;
}

export interface Persona {
  id: string;
  identity: PersonaIdentity;
  behavior: PersonaBehavior;
  figurineUrl?: string;
  figurineStatus: FigurineStatus;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  repoUrl?: string;
  stagingUrl?: string;
  personaCount: number;
  latestScore?: number; // 0..1
  lastRunAt?: string; // ISO-8601
}

export interface DemographicSegment {
  id: string;
  label: string;
  description?: string;
  percentage: number; // computed evenly server-side
}

export interface PersonaSuggestion {
  type: "existing" | "new";
  // existing
  persona_id?: string;
  // new
  name?: string;
  label?: string;
  age_band?: string;
  language?: string;
  disabilities?: string[];
  tech_savviness?: number;
  dwell_multiplier?: number;
  giveup_threshold_s?: number;
  misinterpret_prob?: number;
  // both
  match_segment: string;
  match_reason: string;
  match_detail?: string;
}

export interface Repo {
  id: string;
  projectId: string;
  name: string;
  stagingUrl: string;
  repoUrl?: string;
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
  innerMonologue: string;
  confusionLevel: number;
  understandability: number;
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

// ── Per-project aggregated dashboard (dashboard spec §5) ──
// Cost is operational metadata only (§16): never feeds the inclusion score.
export interface UsageModel {
  model: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cost: number;
  pricingApplied: boolean;
}

export interface RunUsage {
  currency: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cost: number;
  pricingApplied: boolean;
  models: UsageModel[];
}

// One point per run, oldest → newest, for trend charts.
export interface RunTrendPoint {
  runId: string;
  createdAt: string;
  overallScore: number; // composite (DERIVED)
  blockedCount: number; // INDICATIVE
  wcagPassRate: number; // 0..1 TRUSTED
  totalTokens: number;
  cost: number;
}

export interface PersonaReliability {
  personaId: string;
  name: string;
  runsCount: number;
  blockedCount: number; // across runs
  blockRate: number; // 0..1, blockedCount / runsCount
  lastStatus: Severity;
}

export interface ActionItem {
  runId: string;
  personaId: string;
  personaName: string;
  severity: "P0" | "P1" | "P2" | "P3";
  blockedAt: string; // step key
  wcagCriterion?: string; // from trusted stream when available
  owner?: string; // routed owning area (§13 remediation)
}

export interface ProjectDashboard {
  projectId: string;
  runsCount: number;
  latestScore?: number;
  // headline cards
  totalTokens: number;
  totalCost: number;
  currency: string;
  pricingApplied: boolean;
  // sections
  trend: RunTrendPoint[];
  personaReliability: PersonaReliability[];
  usageByModel: UsageModel[]; // summed across runs
  actions: ActionItem[]; // open P0/P1, sorted by severity then recency
}

// ── SSE event payloads (GET /runs/:id/stream) ──
export interface PersonaStepEvent {
  type: "persona_step";
  personaId: string;
  stepIdx: number;
  stepName: string;
  status: Severity;
  dwellMs: number;
  confusionScore: number;
  innerMonologue: string;
  confusionLevel: number;
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

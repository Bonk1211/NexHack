import type {
  Project,
  ProjectDetail,
  Persona,
  Repo,
  RunDetail,
  RunSummary,
  RunMode,
  Viewport,
  FigurineStatus,
  ProjectDashboard,
  RunTrendPoint,
  PersonaReliability,
  UsageModel,
  ActionItem,
  Severity,
} from "./types";
import {
  projects as fixtureProjects,
  personas as fixturePersonas,
  repos as fixtureRepos,
  runs as fixtureRuns,
  runSummaries,
  latestRunByProject,
} from "./fixtures";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function delay(ms?: number): Promise<void> {
  const t = ms ?? 200 + Math.random() * 300;
  return new Promise((r) => setTimeout(r, t));
}

const db = {
  projects: [...fixtureProjects],
  personas: [...fixturePersonas],
  repos: [...fixtureRepos],
  runs: { ...fixtureRuns },
  runSummaries: { ...runSummaries },
  latestRunByProject: { ...latestRunByProject },
  nextId: 100,
};

function uid(prefix: string) {
  return `${prefix}-${++db.nextId}`;
}

// ── Projects ──────────────────────────────────────────────────
export async function getProjects(): Promise<Project[]> {
  await delay();
  return db.projects.map((p) => ({ ...p }));
}

export async function createProject(input: {
  name: string;
  description?: string;
}): Promise<Project> {
  await delay();
  const p: Project = {
    id: uid("proj"),
    name: input.name,
    description: input.description,
    personaCount: 0,
  };
  db.projects.push(p);
  return { ...p };
}

export async function getProject(id: string): Promise<ProjectDetail> {
  await delay();
  const p = db.projects.find((x) => x.id === id);
  if (!p) throw new Error(`Project ${id} not found`);
  const projectRepos = db.repos.filter((r) => r.projectId === id);
  const latestRunId = db.latestRunByProject[id];
  const latestRun = latestRunId ? db.runs[latestRunId] : undefined;
  return { ...p, repos: projectRepos.map((r) => ({ ...r })), latestRun: latestRun ? { ...latestRun } : undefined };
}

export async function deleteProject(id: string): Promise<void> {
  await delay();
  db.projects = db.projects.filter((p) => p.id !== id);
  db.repos = db.repos.filter((r) => r.projectId !== id);
}

// ── Repos ─────────────────────────────────────────────────────
export async function createRepo(
  projectId: string,
  input: { name: string; stagingUrl: string; viewport: Viewport },
): Promise<Repo> {
  await delay();
  const r: Repo = {
    id: uid("repo"),
    projectId,
    name: input.name,
    stagingUrl: input.stagingUrl,
    viewport: input.viewport,
    personaIds: [],
  };
  db.repos.push(r);
  return { ...r };
}

export async function getRepo(id: string): Promise<Repo> {
  await delay();
  const r = db.repos.find((x) => x.id === id);
  if (!r) throw new Error(`Repo ${id} not found`);
  return { ...r };
}

export async function linkPersona(repoId: string, personaId: string): Promise<void> {
  await delay();
  const r = db.repos.find((x) => x.id === repoId);
  if (r && !r.personaIds.includes(personaId)) r.personaIds.push(personaId);
}

export async function unlinkPersona(repoId: string, personaId: string): Promise<void> {
  await delay();
  const r = db.repos.find((x) => x.id === repoId);
  if (r) r.personaIds = r.personaIds.filter((id) => id !== personaId);
}

// ── Personas ──────────────────────────────────────────────────
export async function getPersonas(): Promise<Persona[]> {
  const res = await fetch(`${BASE_URL}/personas`);
  if (!res.ok) throw new Error(`GET /personas failed: ${res.status}`);
  const rows: Persona[] = await res.json();
  const { generateFigurine: gen } = await import("./format");
  // Use real figurine URL from DB if ready, otherwise fall back to SVG placeholder
  return rows.map((p) => ({
    ...p,
    figurineUrl: p.figurineUrl ?? gen(p.id, p.identity.name),
  }));
}

export async function createPersona(input: Partial<Persona> & { identity: Partial<Persona["identity"]> & { name: string } }): Promise<Persona> {
  const res = await fetch(`${BASE_URL}/personas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identity: input.identity, behavior: input.behavior }),
  });
  if (!res.ok) throw new Error(`POST /personas failed: ${res.status}`);
  const p: Persona = await res.json();
  const { generateFigurine: gen } = await import("./format");
  return { ...p, figurineUrl: p.figurineUrl ?? gen(p.id, p.identity.name) };
}

export async function getPersona(id: string): Promise<Persona> {
  const res = await fetch(`${BASE_URL}/personas/${id}`);
  if (!res.ok) throw new Error(`GET /personas/${id} failed: ${res.status}`);
  const p: Persona = await res.json();
  const { generateFigurine: gen } = await import("./format");
  return { ...p, figurineUrl: p.figurineUrl ?? gen(p.id, p.identity.name) };
}

export async function updatePersona(id: string, patch: Partial<Persona>): Promise<Persona> {
  const res = await fetch(`${BASE_URL}/personas/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identity: patch.identity, behavior: patch.behavior }),
  });
  if (!res.ok) throw new Error(`PUT /personas/${id} failed: ${res.status}`);
  const p: Persona = await res.json();
  const { generateFigurine: gen } = await import("./format");
  return { ...p, figurineUrl: p.figurineUrl ?? gen(p.id, p.identity.name) };
}

export async function deletePersona(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/personas/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /personas/${id} failed: ${res.status}`);
}

export async function generateFigurine(id: string): Promise<{ status: FigurineStatus }> {
  const res = await fetch(`${BASE_URL}/personas/${id}/figurine`, { method: "POST" });
  if (!res.ok) throw new Error(`POST /personas/${id}/figurine failed: ${res.status}`);
  return res.json();
}

export async function pollFigurine(
  id: string,
): Promise<{ status: FigurineStatus; url?: string }> {
  const res = await fetch(`${BASE_URL}/personas/${id}/figurine`);
  if (!res.ok) return { status: "failed" };
  return res.json();
}

// ── Runs ──────────────────────────────────────────────────────
export async function startRun(
  repoId: string,
  mode: RunMode,
): Promise<{ runId: string }> {
  await delay();
  const runId = uid("run");
  const repo = db.repos.find((r) => r.id === repoId);
  if (!repo) throw new Error(`Repo ${repoId} not found`);
  return { runId };
}

export async function getProjectRuns(projectId: string): Promise<RunSummary[]> {
  await delay();
  return (db.runSummaries[projectId] ?? []).map((r) => ({ ...r }));
}

export async function getRun(runId: string): Promise<RunDetail> {
  await delay();
  const r = db.runs[runId];
  if (!r) throw new Error(`Run ${runId} not found`);
  return { ...r };
}

// ── Dashboard ─────────────────────────────────────────────────
// Per-project aggregated dashboard (spec §5). Mock-friendly like the rest of this
// file: aggregates the in-memory fixtures so the tab is populated in the demo.
// To go live, swap the body for `fetch(`${BASE_URL}/projects/${projectId}/dashboard`)`
// — the backend already returns this exact shape (camelCase). Token/cost figures
// here are a deterministic demo stand-in (real numbers come from the persisted runs).

// DeepSeek V4 pricing, USD per 1K tokens — mirrors backend/app/config.py llm_pricing.
const DEEPSEEK_PRICING = {
  "deepseek-v4-flash": { prompt: 0.00014, completion: 0.00028 },
  "deepseek-v4-pro": { prompt: 0.00174, completion: 0.00348 },
} as const;

// Stable per-run usage derived from run content (no Math.random — SSR-safe).
function mockRunUsage(run: RunDetail): { models: UsageModel[]; totalTokens: number; cost: number } {
  const steps = run.personaResults.reduce((n, p) => n + p.steps.length, 0);
  const f = DEEPSEEK_PRICING["deepseek-v4-flash"];
  const pr = DEEPSEEK_PRICING["deepseek-v4-pro"];
  // per-step vision (flash) + once-per-run synthesis (pro)
  const flash = { prompt: steps * 360, completion: steps * 130 };
  const pro = { prompt: 2400 + run.personaResults.length * 200, completion: 900 };
  const model = (name: string, prompt: number, completion: number, price: { prompt: number; completion: number }): UsageModel => ({
    model: name,
    promptTokens: prompt,
    completionTokens: completion,
    totalTokens: prompt + completion,
    cost: (prompt / 1000) * price.prompt + (completion / 1000) * price.completion,
    pricingApplied: true,
  });
  const models = [
    model("deepseek-v4-flash", flash.prompt, flash.completion, f),
    model("deepseek-v4-pro", pro.prompt, pro.completion, pr),
  ];
  return {
    models,
    totalTokens: models.reduce((n, m) => n + m.totalTokens, 0),
    cost: models.reduce((n, m) => n + m.cost, 0),
  };
}

// Trusted-stream stand-in: WCAG pass rate ≈ fraction of non-blocked steps (§16).
function mockWcagPassRate(run: RunDetail): number {
  let pass = 0;
  let total = 0;
  for (const p of run.personaResults) {
    for (const s of p.steps) {
      total += 1;
      if (s.status === "ok") pass += 1;
    }
  }
  return total ? pass / total : 0;
}

function severityFor(p: RunDetail["personaResults"][number]): ActionItem["severity"] {
  return p.confusionScore >= 0.7 ? "P0" : p.confusionScore >= 0.45 ? "P1" : "P2";
}

export async function getProjectDashboard(projectId: string): Promise<ProjectDashboard> {
  await delay();
  const summaries = db.runSummaries[projectId] ?? [];
  const runDetails = summaries
    .map((s) => db.runs[s.id])
    .filter((r): r is RunDetail => Boolean(r));

  // oldest → newest for trend charts
  const ordered = [...runDetails].sort(
    (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );

  const usageByRun = new Map(ordered.map((r) => [r.id, mockRunUsage(r)]));

  const trend: RunTrendPoint[] = ordered.map((r) => {
    const u = usageByRun.get(r.id)!;
    return {
      runId: r.id,
      createdAt: r.createdAt,
      overallScore: r.overallScore,
      blockedCount: r.personaResults.filter((p) => p.status === "blocked").length,
      wcagPassRate: mockWcagPassRate(r),
      totalTokens: u.totalTokens,
      cost: u.cost,
    };
  });

  // persona reliability across all project runs
  const relMap = new Map<string, PersonaReliability & { _lastAt: number }>();
  for (const r of ordered) {
    const at = new Date(r.createdAt).getTime();
    for (const p of r.personaResults) {
      const cur =
        relMap.get(p.personaId) ??
        ({ personaId: p.personaId, name: p.persona.identity.name, runsCount: 0, blockedCount: 0, blockRate: 0, lastStatus: "ok" as Severity, _lastAt: -1 });
      cur.runsCount += 1;
      if (p.status === "blocked") cur.blockedCount += 1;
      if (at >= cur._lastAt) {
        cur._lastAt = at;
        cur.lastStatus = p.status;
      }
      relMap.set(p.personaId, cur);
    }
  }
  const personaReliability: PersonaReliability[] = [...relMap.values()]
    .map(({ _lastAt, ...rest }) => ({ ...rest, blockRate: rest.runsCount ? rest.blockedCount / rest.runsCount : 0 }))
    .sort((a, b) => b.blockRate - a.blockRate);

  // usage summed by model across runs
  const modelMap = new Map<string, UsageModel>();
  for (const u of usageByRun.values()) {
    for (const m of u.models) {
      const cur =
        modelMap.get(m.model) ??
        ({ model: m.model, promptTokens: 0, completionTokens: 0, totalTokens: 0, cost: 0, pricingApplied: true });
      cur.promptTokens += m.promptTokens;
      cur.completionTokens += m.completionTokens;
      cur.totalTokens += m.totalTokens;
      cur.cost += m.cost;
      modelMap.set(m.model, cur);
    }
  }
  const usageByModel = [...modelMap.values()].sort((a, b) => b.totalTokens - a.totalTokens);

  // action queue: open blocks, P0→P3 then most recent
  const sevRank: Record<ActionItem["severity"], number> = { P0: 0, P1: 1, P2: 2, P3: 3 };
  const actions: ActionItem[] = ordered
    .flatMap((r) =>
      r.personaResults
        .filter((p) => p.status === "blocked")
        .map((p) => ({
          runId: r.id,
          personaId: p.personaId,
          personaName: p.persona.identity.name,
          severity: severityFor(p),
          blockedAt: p.blockedAt ?? "",
          owner: p.persona.identity.disabilities[0],
          _at: new Date(r.createdAt).getTime(),
        })),
    )
    .filter((a) => a.severity === "P0" || a.severity === "P1")
    .sort((a, b) => sevRank[a.severity] - sevRank[b.severity] || b._at - a._at)
    .map(({ _at, ...rest }) => rest);

  const totalTokens = [...usageByRun.values()].reduce((n, u) => n + u.totalTokens, 0);
  const totalCost = [...usageByRun.values()].reduce((n, u) => n + u.cost, 0);
  const latest = ordered[ordered.length - 1];

  return {
    projectId,
    runsCount: ordered.length,
    latestScore: latest?.overallScore,
    totalTokens,
    totalCost,
    currency: "USD",
    pricingApplied: ordered.length > 0,
    trend,
    personaReliability,
    usageByModel,
    actions,
  };
}

export { BASE_URL };

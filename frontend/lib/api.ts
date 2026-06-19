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
  await delay();
  return db.personas.map((p) => ({ ...p }));
}

export async function createPersona(input: Partial<Persona> & { name: string }): Promise<Persona> {
  await delay();
  const p: Persona = {
    id: uid("p"),
    name: input.name,
    label: input.label ?? "",
    ageBand: input.ageBand ?? "25–34",
    techSavviness: input.techSavviness ?? 0.5,
    patience: input.patience ?? 0.5,
    language: input.language ?? "English",
    disabilities: input.disabilities ?? [],
    behaviorProfile: input.behaviorProfile ?? {
      dwellMultiplier: 1,
      hesitationProb: 0.3,
      readingSpeedWpm: 200,
      giveupThresholdS: 60,
      retryLimit: 3,
    },
    figurineStatus: "none",
  };
  db.personas.push(p);
  return { ...p };
}

export async function getPersona(id: string): Promise<Persona> {
  await delay();
  const p = db.personas.find((x) => x.id === id);
  if (!p) throw new Error(`Persona ${id} not found`);
  return { ...p };
}

export async function updatePersona(id: string, patch: Partial<Persona>): Promise<Persona> {
  await delay();
  const idx = db.personas.findIndex((x) => x.id === id);
  if (idx < 0) throw new Error(`Persona ${id} not found`);
  db.personas[idx] = { ...db.personas[idx], ...patch };
  return { ...db.personas[idx] };
}

export async function deletePersona(id: string): Promise<void> {
  await delay();
  db.personas = db.personas.filter((p) => p.id !== id);
}

export async function generateFigurine(id: string): Promise<{ status: FigurineStatus }> {
  await delay(100);
  const p = db.personas.find((x) => x.id === id);
  if (p) p.figurineStatus = "generating";
  return { status: "generating" };
}

export async function pollFigurine(
  id: string,
): Promise<{ status: FigurineStatus; url?: string }> {
  await delay(800);
  const p = db.personas.find((x) => x.id === id);
  if (!p) return { status: "failed" };
  if (p.figurineStatus === "generating") {
    const { generateFigurine: gen } = await import("./format");
    p.figurineUrl = gen(p.id, p.name);
    p.figurineStatus = "ready";
  }
  return { status: p.figurineStatus, url: p.figurineUrl };
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

export { BASE_URL };

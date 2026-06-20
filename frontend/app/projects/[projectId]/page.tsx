"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getProject,
  getProjectRuns,
  getPersonas,
  getProjectDashboard,
  startRun,
  linkPersona,
  unlinkPersona,
} from "@/lib/api";
import { listRuns, type RunHistoryItem } from "@/lib/live";
import type {
  ProjectDetail,
  RunSummary,
  Persona,
  RunMode,
  ProjectDashboard,
} from "@/lib/types";

// Map a Supabase-backed run-history row to the UI's RunSummary shape.
function toRunSummary(projectId: string, r: RunHistoryItem): RunSummary {
  return {
    id: r.id,
    projectId,
    mode: (r.mode as RunMode) ?? "sequential",
    createdAt: r.created_at,
    overallScore: r.inclusion_score ?? 0,
    blockedCount: r.blocked_count,
  };
}
import { relativeTime, scorePct } from "@/lib/format";
import { ScoreRing } from "@/components/ScoreRing";
import { PersonaWall } from "@/components/PersonaWall";
import { FrictionMatrix } from "@/components/FrictionMatrix";
import AssessmentRunner from "@/components/AssessmentRunner";
import { RunLog } from "@/components/RunLog";
import { StatusDot } from "@/components/StatusDot";

type Tab = "overview" | "dashboard" | "personas" | "runs";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const [tab, setTab] = useState<Tab>("overview");

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allPersonas, setAllPersonas] = useState<Persona[]>([]);
  const [dashboard, setDashboard] = useState<ProjectDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [runMode, setRunMode] = useState<RunMode>("sequential");
  const [showRunner, setShowRunner] = useState(false);
  const [startingRun, setStartingRun] = useState(false);
  const [showPersonaModal, setShowPersonaModal] = useState(false);
  // Fixture runs, kept as a fallback for when Supabase has no real runs yet.
  const fixtureRunsRef = useRef<RunSummary[]>([]);

  // Prefer Supabase-persisted runs (keyed by app name); fall back to fixtures.
  async function loadRuns(appName: string, fallback: RunSummary[]) {
    try {
      const live = await listRuns(appName);
      setRuns(live.length ? live.map((r) => toRunSummary(projectId, r)) : fallback);
    } catch {
      setRuns(fallback);
    }
  }

  useEffect(() => {
    Promise.all([
      getProject(projectId),
      getProjectRuns(projectId),
      getPersonas(),
      getProjectDashboard(projectId),
    ]).then(async ([p, r, personas, dash]) => {
      setProject(p);
      setAllPersonas(personas);
      setDashboard(dash);
      fixtureRunsRef.current = r;
      await loadRuns(p.name, r);
      setLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // The acceptance test IS the live agent assessment (FR-1.1–1.4): reveal the runner
  // in the runs tab, directly above run history.
  function handleStartRun() {
    setShowRunner(true);
    setTab("runs");
  }

  // Pull in any newly persisted run (e.g. after hiding the runner post-assessment).
  function refreshRuns() {
    if (project) loadRuns(project.name, fixtureRunsRef.current);
  }

  if (loading) {
    return (
      <div className="px-10 py-10">
        <div className="h-8 w-48 shimmer rounded-lg" />
        <div className="mt-6 h-[400px] card shimmer" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="px-10 py-10">
        <p className="text-secondary">Project not found.</p>
      </div>
    );
  }

  const linkedPersonaIds = project.repos.flatMap((r) => r.personaIds);
  const linkedPersonas = allPersonas.filter((p) => linkedPersonaIds.includes(p.id));
  const personaNames: Record<string, string> = {};
  allPersonas.forEach((p) => {
    personaNames[p.id] = p.identity.name;
  });

  return (
    <div>
      <div className="flex items-center justify-between border-b border-hairline px-10 py-4">
        <div className="flex items-center gap-2 text-[13px] text-secondary">
          <Link href="/" className="text-brand no-underline hover:underline">
            Home
          </Link>
          <span>/</span>
          <span className="text-primary">{project.name}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-field p-1">
            <button
              type="button"
              onClick={() => setRunMode("sequential")}
              className={`rounded-md px-3 py-1 text-[12px] font-medium transition-colors ${
                runMode === "sequential" ? "bg-card text-primary shadow-sm" : "text-secondary"
              }`}
            >
              Sequential
            </button>
            <button
              type="button"
              onClick={() => setRunMode("parallel")}
              className={`rounded-md px-3 py-1 text-[12px] font-medium transition-colors ${
                runMode === "parallel" ? "bg-card text-primary shadow-sm" : "text-secondary"
              }`}
            >
              Parallel
            </button>
          </div>
          <button
            type="button"
            onClick={handleStartRun}
            className="rounded-xl bg-brand px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
          >
            ▶ Run acceptance test
          </button>
        </div>
      </div>

      <div className="border-b border-hairline px-10">
        <div className="flex gap-6">
          {(["overview", "dashboard", "personas", "runs"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`relative py-3 text-[14px] font-medium capitalize transition-colors ${
                tab === t ? "text-primary" : "text-secondary hover:text-primary"
              }`}
            >
              {t}
              {tab === t && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand" />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="px-10 py-8">
        {tab === "overview" && (
          <OverviewTab project={project} personaNames={personaNames} />
        )}
        {tab === "dashboard" && (
          <DashboardTab dashboard={dashboard} projectId={projectId} />
        )}
        {tab === "personas" && (
          <PersonasTab
            linkedPersonas={linkedPersonas}
            allPersonas={allPersonas}
            repoId={project.repos[0]?.id}
            onRefresh={() => {
              getProject(projectId).then(setProject);
            }}
          />
        )}
        {tab === "runs" && (
          <RunsTab
            runs={runs}
            projectId={projectId}
            showRunner={showRunner}
            onHide={() => {
              setShowRunner(false);
              refreshRuns();
            }}
            appName={project.name}
            mode={runMode}
          />
        )}
      </div>
    </div>
  );
}

function OverviewTab({
  project,
  personaNames,
}: {
  project: ProjectDetail;
  personaNames: Record<string, string>;
}) {
  const run = project.latestRun;
  if (!run) {
    return (
      <div className="py-12 text-center text-secondary">
        No runs yet. Start an acceptance test to see results here.
      </div>
    );
  }

  const blockedPersonas = run.personaResults.filter((p) => p.status === "blocked");
  const atRiskNames = blockedPersonas.map((p) => p.persona.identity.name).join(", ");

  return (
    <div>
      <div className="rise rounded-[20px] bg-anchor p-10">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-on-dark-dim">
              InclusionScope
            </div>
            <h2 className="mt-2 font-display text-[28px] text-on-dark">
              {project.name} (staging)
            </h2>
            <p className="mt-1 text-[14px] text-on-dark-dim">
              {run.personaResults.length} personas
            </p>
            {atRiskNames && (
              <p className="mt-3 text-[14px] text-on-dark-dim">
                At risk:{" "}
                <span className="font-medium text-[#ff6b60]">{atRiskNames}</span>
              </p>
            )}
          </div>
          <ScoreRing value={run.overallScore} size={132} />
        </div>
      </div>

      <PersonaWall results={run.personaResults} />

      <FrictionMatrix matrix={run.frictionMatrix} personaNames={personaNames} />

      <RunLog results={run.personaResults} />
    </div>
  );
}

function PersonasTab({
  linkedPersonas,
  allPersonas,
  repoId,
  onRefresh,
}: {
  linkedPersonas: Persona[];
  allPersonas: Persona[];
  repoId?: string;
  onRefresh: () => void;
}) {
  const [showModal, setShowModal] = useState(false);

  async function handleUnlink(personaId: string) {
    if (!repoId) return;
    await unlinkPersona(repoId, personaId);
    onRefresh();
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="section-label">Linked personas</h2>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="rounded-lg bg-brand px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
        >
          Add from library
        </button>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-4">
        {linkedPersonas.map((p, i) => (
          <div key={p.id} className="rise" style={{ animationDelay: `${i * 30}ms` }}>
            <div className="card p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 overflow-hidden rounded-full bg-field">
                    {p.figurineUrl && (
                      <img src={p.figurineUrl} alt={p.identity.name} className="h-10 w-10 rounded-full" />
                    )}
                  </div>
                  <div>
                    <div className="font-display text-[15px] text-primary">{p.identity.name}</div>
                    <div className="text-[12px] text-tertiary">{p.identity.label}</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleUnlink(p.id)}
                  className="text-[12px] text-secondary hover:text-blocked"
                >
                  Unlink
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <AddPersonaModal
          allPersonas={allPersonas}
          linkedIds={linkedPersonas.map((p) => p.id)}
          repoId={repoId}
          onClose={() => setShowModal(false)}
          onAdded={() => {
            setShowModal(false);
            onRefresh();
          }}
        />
      )}
    </div>
  );
}

function AddPersonaModal({
  allPersonas,
  linkedIds,
  repoId,
  onClose,
  onAdded,
}: {
  allPersonas: Persona[];
  linkedIds: string[];
  repoId?: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const available = allPersonas.filter((p) => !linkedIds.includes(p.id));

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function handleAdd() {
    if (!repoId) return;
    setSaving(true);
    for (const id of selected) {
      await linkPersona(repoId, id);
    }
    onAdded();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[480px] rounded-[20px] bg-card p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-display text-[20px] text-primary">Add personas</h3>
          <button type="button" onClick={onClose} className="text-[14px] text-secondary hover:text-primary">
            Close
          </button>
        </div>
        <div className="mt-4 max-h-[320px] overflow-y-auto">
          {available.length === 0 ? (
            <p className="py-8 text-center text-[14px] text-secondary">All personas are already linked.</p>
          ) : (
            available.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => toggle(p.id)}
                className={`flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors ${
                  selected.includes(p.id) ? "bg-brand/10" : "hover:bg-field"
                }`}
              >
                <div className="h-8 w-8 overflow-hidden rounded-full bg-field">
                  {p.figurineUrl && (
                    <img src={p.figurineUrl} alt={p.identity.name} className="h-8 w-8 rounded-full" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="text-[14px] font-medium text-primary">{p.identity.name}</div>
                  <div className="text-[12px] text-tertiary">{p.identity.label}</div>
                </div>
                {selected.includes(p.id) && (
                  <span className="text-brand text-[14px]">✓</span>
                )}
              </button>
            ))
          )}
        </div>
        <button
          type="button"
          onClick={handleAdd}
          disabled={saving || selected.length === 0}
          className="mt-4 w-full rounded-xl bg-brand py-3 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Adding..." : `Add ${selected.length} persona${selected.length !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  );
}

function RunsTab({
  runs,
  projectId,
  showRunner,
  onHide,
  appName,
  mode,
}: {
  runs: RunSummary[];
  projectId: string;
  showRunner: boolean;
  onHide: () => void;
  appName: string;
  mode: RunMode;
}) {
  return (
    <div>
      {showRunner && (
        <div className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="section-label">Acceptance test — live agent run</h2>
            <button
              type="button"
              onClick={onHide}
              className="text-[12px] text-secondary hover:text-primary"
            >
              Hide
            </button>
          </div>
          <AssessmentRunner defaultAppName={appName} mode={mode} />
        </div>
      )}
      <h2 className="section-label">Run history</h2>
      <div className="mt-5">
        {runs.length === 0 ? (
          <p className="py-8 text-center text-[14px] text-secondary">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map((r, i) => (
              <Link
                key={r.id}
                href={`/projects/${projectId}/runs/${r.id}`}
                className="rise card flex items-center justify-between p-4 no-underline transition-all duration-200 hover:-translate-y-0.5"
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <div className="flex items-center gap-4">
                  <div className="text-[14px] font-medium text-primary">{r.id}</div>
                  <span className="rounded-full bg-field px-2.5 py-0.5 text-[11px] font-medium capitalize text-secondary">
                    {r.mode}
                  </span>
                </div>
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] text-secondary">Score</span>
                    <span className="text-[14px] font-semibold tabular-nums text-primary">
                      {scorePct(r.overallScore)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] text-secondary">Blocked</span>
                    <span className={`text-[14px] font-semibold tabular-nums ${r.blockedCount > 0 ? "text-blocked" : "text-ok"}`}>
                      {r.blockedCount}
                    </span>
                  </div>
                  <span className="text-[12px] text-tertiary">{relativeTime(r.createdAt)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Dashboard tab (spec §6) ────────────────────────────────────
// Aggregated, multi-run view per project. Two-stream discipline (§16) preserved:
// WCAG trend is TRUSTED, persona/score trends are INDICATIVE/DERIVED, cost is
// operational metadata and never feeds the score.

const SEV_CHIP: Record<string, string> = {
  P0: "bg-blocked/12 text-blocked",
  P1: "bg-[#b25e00]/12 text-[#b25e00]",
  P2: "bg-[#b25e00]/10 text-[#9a6a00]",
  P3: "bg-field text-secondary",
};

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

function fmtCost(n: number, currency: string, applied: boolean): string {
  const v = currency === "USD" ? `$${n < 1 ? n.toFixed(4) : n.toFixed(2)}` : `${n.toFixed(4)} ${currency}`;
  return applied ? v : `${v} est.`;
}

function Delta({ curr, prev, pct = false }: { curr: number; prev?: number; pct?: boolean }) {
  if (prev == null) return null;
  const d = curr - prev;
  if (Math.abs(d) < 1e-9) return <span className="text-[12px] text-tertiary">±0</span>;
  const up = d > 0;
  const mag = pct ? `${Math.abs(Math.round(d * 100))}` : `${Math.abs(d).toFixed(2)}`;
  return (
    <span className={`text-[12px] font-medium ${up ? "text-ok" : "text-blocked"}`}>
      {up ? "▲" : "▼"} {mag}
    </span>
  );
}

function KpiCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-tertiary">{label}</div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

// Score line + blocked bars over runs (DERIVED + INDICATIVE).
function ScoreBlockChart({ trend }: { trend: ProjectDashboard["trend"] }) {
  const W = 320;
  const H = 96;
  const pad = 10;
  const n = trend.length;
  const maxBlocked = Math.max(1, ...trend.map((t) => t.blockedCount));
  const x = (i: number) => (n <= 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1));
  const yScore = (s: number) => H - pad - s * (H - 2 * pad);
  const line = trend.map((t, i) => `${x(i)},${yScore(t.overallScore)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-28 w-full" preserveAspectRatio="none">
      {trend.map((t, i) => {
        const bh = (t.blockedCount / maxBlocked) * (H - 2 * pad);
        const bw = Math.min(18, (W - 2 * pad) / Math.max(n, 1) - 6);
        return (
          <rect key={t.runId} x={x(i) - bw / 2} y={H - pad - bh} width={bw} height={bh} rx={2} fill="#c8362f" opacity={0.18} />
        );
      })}
      <polyline points={line} fill="none" stroke="#d97a2b" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {trend.map((t, i) => (
        <circle key={t.runId} cx={x(i)} cy={yScore(t.overallScore)} r={3} fill="#d97a2b" />
      ))}
    </svg>
  );
}

// Single-series line in a fixed [min,max] domain.
function LineChart({ values, color, min = 0, max = 1 }: { values: number[]; color: string; min?: number; max?: number }) {
  const W = 320;
  const H = 96;
  const pad = 10;
  const n = values.length;
  const span = max - min || 1;
  const x = (i: number) => (n <= 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1));
  const y = (v: number) => H - pad - ((v - min) / span) * (H - 2 * pad);
  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-28 w-full" preserveAspectRatio="none">
      <polyline points={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {values.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={color} />
      ))}
    </svg>
  );
}

function ChartCard({ title, badge, hasData, children }: { title: string; badge?: string; hasData: boolean; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2">
        <h3 className="text-[13px] font-semibold text-primary">{title}</h3>
        {badge && (
          <span className="rounded-full bg-ok/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ok">
            {badge}
          </span>
        )}
      </div>
      <div className="mt-4">
        {hasData ? (
          children
        ) : (
          <p className="py-8 text-center text-[13px] text-tertiary">Needs ≥2 runs to chart a trend.</p>
        )}
      </div>
    </div>
  );
}

function DashboardTab({ dashboard, projectId }: { dashboard: ProjectDashboard | null; projectId: string }) {
  if (!dashboard || dashboard.runsCount === 0) {
    return (
      <div className="py-12 text-center text-secondary">
        No runs yet. Start an acceptance test — the dashboard aggregates across runs once data exists.
      </div>
    );
  }

  const { trend, personaReliability, usageByModel, actions } = dashboard;
  const last = trend[trend.length - 1];
  const prev = trend.length >= 2 ? trend[trend.length - 2] : undefined;
  const openP0 = actions.filter((a) => a.severity === "P0").length;
  const multiRun = trend.length >= 2;

  return (
    <div className="space-y-8">
      {/* Row A — KPI cards */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Inclusion score">
          <div className="flex items-end gap-2">
            <span className="font-display text-[34px] leading-none tabular-nums text-primary">{scorePct(last.overallScore)}</span>
            <Delta curr={last.overallScore} prev={prev?.overallScore} pct />
          </div>
          <div className="mt-1 text-[11px] text-tertiary">latest of {dashboard.runsCount} runs · DERIVED</div>
        </KpiCard>

        <KpiCard label="WCAG pass rate">
          <div className="flex items-end gap-2">
            <span className="font-display text-[34px] leading-none tabular-nums text-primary">{scorePct(last.wcagPassRate)}%</span>
            <Delta curr={last.wcagPassRate} prev={prev?.wcagPassRate} pct />
          </div>
          <div className="mt-1">
            <span className="rounded-full bg-ok/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ok">Trusted</span>
          </div>
        </KpiCard>

        <KpiCard label="Open P0 blocks">
          <span className={`font-display text-[34px] leading-none tabular-nums ${openP0 > 0 ? "text-blocked" : "text-ok"}`}>{openP0}</span>
          <div className="mt-1 text-[11px] text-tertiary">{actions.length} open action{actions.length !== 1 ? "s" : ""}</div>
        </KpiCard>

        <KpiCard label="LLM cost">
          <div className="font-display text-[28px] leading-none tabular-nums text-primary">
            {fmtCost(dashboard.totalCost, dashboard.currency, dashboard.pricingApplied)}
          </div>
          <div className="mt-1 text-[11px] text-tertiary">{fmtTokens(dashboard.totalTokens)} tokens · across runs</div>
        </KpiCard>
      </div>

      {/* Row B — trends */}
      <div className="grid grid-cols-2 gap-4">
        <ChartCard title="Score & blocks over runs" hasData={multiRun}>
          <ScoreBlockChart trend={trend} />
          <div className="mt-2 flex items-center gap-4 text-[11px] text-tertiary">
            <span className="flex items-center gap-1"><span className="inline-block h-[2px] w-3 bg-[#d97a2b]" /> score</span>
            <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm bg-blocked/20" /> blocked</span>
          </div>
        </ChartCard>
        <ChartCard title="WCAG pass-rate trend" badge="Trusted" hasData={multiRun}>
          <LineChart values={trend.map((t) => t.wcagPassRate)} color="#1d8a4e" />
        </ChartCard>
      </div>

      {/* Row C — cost efficiency */}
      <div className="grid grid-cols-2 gap-4">
        <ChartCard title="Cost & tokens per run" hasData={multiRun}>
          <LineChart values={trend.map((t) => t.cost)} color="#6b7280" min={0} max={Math.max(...trend.map((t) => t.cost), 0.0001)} />
          <div className="mt-2 text-[11px] text-tertiary">
            {trend.map((t) => fmtTokens(t.totalTokens)).join(" → ")} tokens/run
          </div>
        </ChartCard>
        <div className="card p-5">
          <h3 className="text-[13px] font-semibold text-primary">Usage by model</h3>
          <div className="mt-1 text-[11px] text-tertiary">DeepSeek V4 today · table survives a model swap</div>
          <table className="mt-3 w-full text-[12px]">
            <thead>
              <tr className="text-left text-tertiary">
                <th className="pb-2 font-medium">Model</th>
                <th className="pb-2 text-right font-medium">Prompt</th>
                <th className="pb-2 text-right font-medium">Compl.</th>
                <th className="pb-2 text-right font-medium">Total</th>
                <th className="pb-2 text-right font-medium">Cost</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {usageByModel.map((m) => (
                <tr key={m.model} className="border-t border-hairline">
                  <td className="py-2 text-primary">{m.model}</td>
                  <td className="py-2 text-right text-secondary">{fmtTokens(m.promptTokens)}</td>
                  <td className="py-2 text-right text-secondary">{fmtTokens(m.completionTokens)}</td>
                  <td className="py-2 text-right text-secondary">{fmtTokens(m.totalTokens)}</td>
                  <td className="py-2 text-right text-secondary">{fmtCost(m.cost, dashboard.currency, m.pricingApplied)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Row D — persona reliability */}
      <div className="card p-5">
        <div className="flex items-center gap-2">
          <h3 className="text-[13px] font-semibold text-primary">Persona reliability</h3>
          <span className="rounded-full bg-field px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-secondary">Indicative</span>
        </div>
        <table className="mt-3 w-full text-[13px]">
          <thead>
            <tr className="text-left text-tertiary text-[12px]">
              <th className="pb-2 font-medium">Persona</th>
              <th className="pb-2 text-right font-medium">Runs</th>
              <th className="pb-2 text-right font-medium">Blocked</th>
              <th className="pb-2 font-medium">Block rate</th>
              <th className="pb-2 text-right font-medium">Last</th>
            </tr>
          </thead>
          <tbody>
            {personaReliability.map((p) => (
              <tr key={p.personaId} className="border-t border-hairline">
                <td className="py-2.5 font-medium text-primary">{p.name}</td>
                <td className="py-2.5 text-right tabular-nums text-secondary">{p.runsCount}</td>
                <td className="py-2.5 text-right tabular-nums text-secondary">{p.blockedCount}</td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-field">
                      <div className="h-full rounded-full bg-blocked" style={{ width: `${Math.round(p.blockRate * 100)}%` }} />
                    </div>
                    <span className="tabular-nums text-[12px] text-secondary">{Math.round(p.blockRate * 100)}%</span>
                  </div>
                </td>
                <td className="py-2.5">
                  <div className="flex items-center justify-end gap-1.5">
                    <StatusDot status={p.lastStatus} />
                    <span className="text-[12px] capitalize text-secondary">{p.lastStatus}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Row E — action queue */}
      <div className="card p-5">
        <h3 className="text-[13px] font-semibold text-primary">Action queue</h3>
        <div className="mt-1 text-[11px] text-tertiary">Open P0/P1 blocks · P0 → P3, most recent first</div>
        <div className="mt-3 space-y-2">
          {actions.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-ok">No open P0/P1 blocks. 🎉</p>
          ) : (
            actions.map((a, i) => (
              <Link
                key={`${a.runId}-${a.personaId}-${i}`}
                href={`/projects/${projectId}/runs/${a.runId}`}
                className="flex items-center justify-between rounded-lg border border-hairline p-3 no-underline transition-colors hover:bg-field"
              >
                <div className="flex items-center gap-3">
                  <span className={`rounded-md px-2 py-0.5 text-[11px] font-bold ${SEV_CHIP[a.severity] ?? SEV_CHIP.P3}`}>{a.severity}</span>
                  <span className="text-[13px] font-medium text-primary">{a.personaName}</span>
                  <span className="text-[12px] text-secondary">blocked at <span className="text-primary">{a.blockedAt || "—"}</span></span>
                  {a.wcagCriterion && <span className="text-[11px] text-tertiary">WCAG {a.wcagCriterion}</span>}
                </div>
                {a.owner && <span className="text-[11px] text-tertiary">→ {a.owner}</span>}
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

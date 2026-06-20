"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getProject,
  getProjectRuns,
  getPersonas,
  startRun,
  linkPersona,
  unlinkPersona,
} from "@/lib/api";
import { listRuns, type RunHistoryItem } from "@/lib/live";
import type { ProjectDetail, RunSummary, Persona, RunMode } from "@/lib/types";

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

type Tab = "overview" | "personas" | "runs";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const [tab, setTab] = useState<Tab>("overview");

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allPersonas, setAllPersonas] = useState<Persona[]>([]);
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
    ]).then(async ([p, r, personas]) => {
      setProject(p);
      setAllPersonas(personas);
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
          {(["overview", "personas", "runs"] as Tab[]).map((t) => (
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

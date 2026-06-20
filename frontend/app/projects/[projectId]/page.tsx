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
  linkPersonaToApp,
  unlinkPersonaFromApp,
  getLinkedPersonas,
  getFlowSteps,
  updateFlowSteps,
  getDemographics,
  addDemographic,
  deleteDemographic,
  suggestPersonas,
  createPersona,
} from "@/lib/api";
import { DonutChart, DEMO_PALETTE } from "@/components/DonutChart";
import type { DemographicSegment, PersonaSuggestion } from "@/lib/types";
import { listRuns, type RunHistoryItem } from "@/lib/live";
import type {
  ProjectDetail,
  RunSummary,
  Persona,
  RunMode,
  ProjectDashboard,
  FlowStep,
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
import { PhonePreview } from "@/components/PhonePreview";
import { FlowEditor } from "@/components/FlowEditor";

type Tab = "overview" | "dashboard" | "personas" | "runs";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const [tab, setTab] = useState<Tab>("overview");

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allPersonas, setAllPersonas] = useState<Persona[]>([]);
  const [linkedPersonaIds, setLinkedPersonaIds] = useState<string[]>([]);
  const [flowSteps, setFlowSteps] = useState<FlowStep[]>([]);
  const [showFlowEditor, setShowFlowEditor] = useState(false);
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
      getLinkedPersonas(projectId),
      getFlowSteps(projectId),
    ]).then(async ([p, r, personas, dash, linkedIds, flow]) => {
      setProject(p);
      setAllPersonas(personas);
      setLinkedPersonaIds(linkedIds);
      setFlowSteps(flow);
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

  const linkedPersonas = allPersonas.filter((p) => linkedPersonaIds.includes(p.id));

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
          <OverviewTab
            project={project}
            runs={runs}
            flowSteps={flowSteps}
            onEditFlow={() => setShowFlowEditor(true)}
          />
        )}
        {tab === "dashboard" && (
          <DashboardTab dashboard={dashboard} projectId={projectId} />
        )}
        {tab === "personas" && (
          <PersonasTab
            linkedPersonas={linkedPersonas}
            allPersonas={allPersonas}
            appId={projectId}
            onRefresh={async () => {
              const [p, linkedIds] = await Promise.all([
                getProject(projectId),
                getLinkedPersonas(projectId),
              ]);
              setProject(p);
              setLinkedPersonaIds(linkedIds);
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
            stagingUrl={project.stagingUrl}
            linkedPersonas={linkedPersonas}
            mode={runMode}
          />
        )}
      </div>

      {showFlowEditor && (
        <FlowEditor
          steps={flowSteps}
          onSave={async (steps) => {
            await updateFlowSteps(projectId, steps);
            setFlowSteps(steps);
            setShowFlowEditor(false);
          }}
          onClose={() => setShowFlowEditor(false)}
        />
      )}
    </div>
  );
}

function OverviewTab({
  project,
  runs,
  flowSteps,
  onEditFlow,
}: {
  project: ProjectDetail;
  runs: RunSummary[];
  flowSteps: FlowStep[];
  onEditFlow: () => void;
}) {
  const [segments, setSegments] = useState<DemographicSegment[]>([]);
  const [showAddDemo, setShowAddDemo] = useState(false);

  useEffect(() => {
    getDemographics(project.id).then(setSegments).catch(() => {});
  }, [project.id]);

  async function handleAddDemo(label: string, description: string) {
    const updated = await addDemographic(project.id, label, description || undefined);
    setSegments(updated);
    setShowAddDemo(false);
  }

  async function handleDeleteDemo(demoId: string) {
    const updated = await deleteDemographic(project.id, demoId);
    setSegments(updated);
  }

  const [latestCommit, setLatestCommit] = useState<{
    message: string;
    author: string;
    date: string;
    sha: string;
  } | null>(null);

  useEffect(() => {
    if (!project.repoUrl) return;
    const match = project.repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    if (!match) return;
    const [, owner, repo] = match;
    fetch(`https://api.github.com/repos/${owner}/${repo}/commits?per_page=1`)
      .then((res) => res.json())
      .then((commits) => {
        if (commits.length > 0) {
          const c = commits[0];
          setLatestCommit({
            message: c.commit.message.split("\n")[0],
            author: c.commit.author.name,
            date: c.commit.author.date,
            sha: c.sha.slice(0, 7),
          });
        }
      })
      .catch(() => {});
  }, [project.repoUrl]);

  const latestRun = runs[0];
  const prevRun = runs[1];
  const trend = latestRun && prevRun ? latestRun.overallScore - prevRun.overallScore : null;

  return (
    <div className="grid grid-cols-[1fr_auto] gap-6">
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-6">
          <div className="card p-6">
            <h3 className="section-label mb-4">Project</h3>
            <div className="space-y-3">
              <div>
                <div className="text-[12px] text-tertiary">Name</div>
                <div className="text-[15px] font-medium text-primary">{project.name}</div>
              </div>
              {project.description && (
                <div>
                  <div className="text-[12px] text-tertiary">Description</div>
                  <div className="text-[14px] text-secondary">{project.description}</div>
                </div>
              )}
              {project.repoUrl && (
                <div>
                  <div className="text-[12px] text-tertiary">Repository</div>
                  <a
                    href={project.repoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[14px] text-brand hover:underline"
                  >
                    {project.repoUrl.replace("https://github.com/", "")}
                  </a>
                </div>
              )}
              {project.stagingUrl && (
                <div>
                  <div className="text-[12px] text-tertiary">Staging</div>
                  <a
                    href={project.stagingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[14px] text-brand hover:underline"
                  >
                    {project.stagingUrl}
                  </a>
                </div>
              )}
            </div>
          </div>

          <div className="card p-6">
            <h3 className="section-label mb-4">Health</h3>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[12px] text-tertiary">Latest score</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-[32px] font-semibold tabular-nums text-primary">
                    {latestRun ? scorePct(latestRun.overallScore) : "—"}
                  </span>
                  {trend !== null && (
                    <span className={`text-[14px] font-medium ${trend > 0 ? "text-ok" : trend < 0 ? "text-blocked" : "text-tertiary"}`}>
                      {trend > 0 ? "▲" : trend < 0 ? "▼" : "—"} {Math.abs(Math.round(trend * 100))}%
                    </span>
                  )}
                </div>
              </div>
              {latestRun && <ScoreRing value={latestRun.overallScore} size={80} />}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <div className="text-[12px] text-tertiary">Total runs</div>
                <div className="text-[20px] font-semibold tabular-nums text-primary">{runs.length}</div>
              </div>
              <div>
                <div className="text-[12px] text-tertiary">Last run</div>
                <div className="text-[14px] text-secondary">{latestRun ? relativeTime(latestRun.createdAt) : "—"}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="mb-5 flex items-center justify-between">
            <h3 className="section-label">Target audience</h3>
            <button
              type="button"
              onClick={() => setShowAddDemo(true)}
              className="flex items-center gap-1.5 rounded-lg bg-field px-3 py-1.5 text-[12px] font-medium text-secondary transition-colors hover:text-primary"
            >
              <span className="text-[16px] leading-none">+</span> Add segment
            </button>
          </div>

          {segments.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-6">
              <DonutChart segments={[]} size={140} />
              <p className="text-[13px] text-tertiary">
                No segments yet — add your first target audience.
              </p>
            </div>
          ) : (
            <div className="flex gap-6">
              <div className="shrink-0">
                <DonutChart segments={segments} size={160} />
              </div>
              <div className="flex-1 space-y-3">
                {segments.map((seg, i) => (
                  <div key={seg.id} className="flex items-start gap-2.5">
                    <span
                      className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: DEMO_PALETTE[i % DEMO_PALETTE.length] }}
                    />
                    <div className="group/seg relative min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-[13px] font-medium text-primary">{seg.label}</span>
                        <span className="shrink-0 text-[12px] tabular-nums text-tertiary">{seg.percentage}%</span>
                      </div>
                      {seg.description && (
                        <p className="mt-0.5 line-clamp-2 cursor-default text-[12px] text-secondary">
                          {seg.description}
                        </p>
                      )}
                      {/* Floating full-text tooltip */}
                      {seg.description && (
                        <div className="pointer-events-none absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-hairline bg-card p-4 opacity-0 shadow-xl transition-opacity duration-150 group-hover/seg:opacity-100">
                          <p className="text-[12px] font-medium text-primary">{seg.label}</p>
                          <p className="mt-1.5 text-[12px] leading-relaxed text-secondary">{seg.description}</p>
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteDemo(seg.id)}
                      className="shrink-0 text-[16px] leading-none text-tertiary transition-colors hover:text-blocked"
                      aria-label="Remove segment"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {showAddDemo && (
          <AddDemographicModal
            onClose={() => setShowAddDemo(false)}
            onAdd={handleAddDemo}
          />
        )}

        {latestCommit && (
          <div className="card p-6">
            <h3 className="section-label mb-4">Latest commit</h3>
            <div className="flex items-start gap-3">
              <div className="mt-1 h-8 w-8 shrink-0 rounded-full bg-field" />
              <div className="min-w-0 flex-1">
                <div className="text-[14px] font-medium text-primary">{latestCommit.message}</div>
                <div className="mt-1 flex items-center gap-3 text-[12px] text-tertiary">
                  <span>{latestCommit.author}</span>
                  <span>•</span>
                  <span>{relativeTime(latestCommit.date)}</span>
                  <span>•</span>
                  <code className="rounded bg-field px-1.5 py-0.5 text-[11px]">{latestCommit.sha}</code>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <h3 className="section-label">Flow steps</h3>
            <button
              type="button"
              onClick={onEditFlow}
              className="flex items-center gap-1.5 rounded-lg bg-field px-3 py-1.5 text-[12px] font-medium text-secondary transition-colors hover:text-primary"
            >
              {flowSteps.length > 0 ? "Edit" : "Configure"}
            </button>
          </div>
          {flowSteps.length === 0 ? (
            <p className="mt-3 text-[13px] text-tertiary">
              No flow steps configured. The default flow (otp → submit) will be used.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {flowSteps.map((step, idx) => (
                <div key={idx} className="flex items-center gap-3 rounded-lg bg-field p-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand/10 text-[11px] font-semibold text-brand">
                    {idx + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-medium text-primary">{step.key}</span>
                      <span className="rounded bg-card px-1.5 py-0.5 text-[10px] font-medium uppercase text-secondary">
                        {step.action}
                      </span>
                      {step.critical && (
                        <span className="rounded bg-blocked/10 px-1.5 py-0.5 text-[10px] font-medium text-blocked">
                          critical
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-[11px] text-tertiary">
                      {step.role}{step.name ? ` "${step.name}"` : ""}{step.action === "fill" && step.value ? ` → ${step.value}` : ""}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {project.stagingUrl && (
        <div className="card p-6">
          <h3 className="section-label mb-4">Preview</h3>
          <div className="flex justify-center">
            <PhonePreview url={project.stagingUrl} />
          </div>
        </div>
      )}
    </div>
  );
}

function AddDemographicModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (label: string, description: string) => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim()) return;
    setSaving(true);
    await onAdd(label.trim(), description.trim());
    setSaving(false);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-md p-7 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-display text-[22px] text-primary">Add target audience</h2>
        <p className="mt-1 text-[13px] text-secondary">Describe one demographic segment for this project.</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.06em] text-tertiary">
              Headline <span className="normal-case tracking-normal font-normal">(5–6 words)</span>
            </label>
            <input
              type="text"
              value={label}
              maxLength={60}
              onChange={(e) => setLabel(e.target.value)}
              className="input"
              placeholder="Senior Malaysians, Low-Tech, Visual"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.06em] text-tertiary">
              Description <span className="normal-case tracking-normal font-normal">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input min-h-[80px] resize-none"
              placeholder="Primarily 55+ from rural Malaysia, Bahasa Melayu speakers, low digital literacy, some with visual impairments."
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-[13px] text-secondary transition-colors hover:text-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !label.trim()}
              className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Adding..." : "Add segment"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PersonasTab({
  linkedPersonas,
  allPersonas,
  appId,
  onRefresh,
}: {
  linkedPersonas: Persona[];
  allPersonas: Persona[];
  appId: string;
  onRefresh: () => void;
}) {
  const [showModal, setShowModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [suggestions, setSuggestions] = useState<PersonaSuggestion[] | null>(null);

  async function handleUnlink(personaId: string) {
    await unlinkPersonaFromApp(appId, personaId);
    onRefresh();
  }

  async function handleGenerate() {
    setGenerating(true);
    setSuggestions(null);
    const results = await suggestPersonas(appId);
    setSuggestions(results);
    setGenerating(false);
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="section-label">Linked personas</h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 rounded-lg border border-accent px-3 py-1.5 text-[13px] font-medium text-accent transition-colors hover:bg-accent hover:text-white disabled:opacity-50"
          >
            {generating ? (
              <>
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                Analysing…
              </>
            ) : (
              <>✦ Generate</>
            )}
          </button>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="rounded-lg bg-field px-3 py-1.5 text-[13px] font-medium text-secondary transition-colors hover:text-primary"
          >
            Add from library
          </button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-4 items-stretch gap-4">
        {linkedPersonas.map((p, i) => (
          <div
            key={p.id}
            className="group/card rise relative z-0 h-full hover:z-10"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <div className="card flex h-full flex-col p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-field">
                    {p.figurineUrl && (
                      <img src={p.figurineUrl} alt={p.identity.name} className="h-10 w-10 rounded-full object-cover" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-display text-[15px] text-primary">{p.identity.name}</div>
                    <div className="line-clamp-2 text-[12px] text-tertiary">{p.identity.label}</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleUnlink(p.id)}
                  className="ml-2 shrink-0 text-[12px] text-secondary hover:text-blocked"
                >
                  Unlink
                </button>
              </div>
            </div>
            {/* Tooltip outside the card div — positioned relative to the outer wrapper */}
            {p.identity.label && (
              <div className="pointer-events-none absolute left-0 top-full z-50 mt-2 w-64 rounded-xl border border-hairline bg-card p-3 opacity-0 shadow-xl transition-opacity duration-150 group-hover/card:opacity-100">
                <p className="text-[11px] font-medium text-primary">{p.identity.name}</p>
                <p className="mt-1 text-[12px] leading-relaxed text-secondary">{p.identity.label}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {suggestions !== null && (
        <SuggestionsPanel
          suggestions={suggestions}
          allPersonas={allPersonas}
          linkedIds={linkedPersonas.map((p) => p.id)}
          appId={appId}
          onClose={() => setSuggestions(null)}
          onDone={() => {
            setSuggestions(null);
            onRefresh();
          }}
        />
      )}

      {showModal && (
        <AddPersonaModal
          allPersonas={allPersonas}
          linkedIds={linkedPersonas.map((p) => p.id)}
          appId={appId}
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

function SuggestionsPanel({
  suggestions,
  allPersonas,
  linkedIds,
  appId,
  onClose,
  onDone,
}: {
  suggestions: PersonaSuggestion[];
  allPersonas: Persona[];
  linkedIds: string[];
  appId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(suggestions.map((_, i) => i))
  );
  const [saving, setSaving] = useState(false);

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  }

  async function handleAdd() {
    setSaving(true);
    for (const i of selected) {
      const s = suggestions[i];
      if (s.type === "existing" && s.persona_id) {
        if (!linkedIds.includes(s.persona_id)) {
          await linkPersonaToApp(appId, s.persona_id).catch(() => {});
        }
      } else if (s.type === "new" && s.name) {
        const p = await createPersona({
          identity: {
            name: s.name,
            label: s.label ?? "",
            ageBand: s.age_band ?? "25–34",
            language: s.language ?? "English",
            disabilities: s.disabilities ?? [],
            techSavviness: s.tech_savviness ?? 0.5,
          },
          behavior: {
            dwellMultiplier: s.dwell_multiplier ?? 1.0,
            giveupThresholdS: s.giveup_threshold_s ?? 60,
            misinterpretProb: s.misinterpret_prob ?? 0.2,
          },
        }).catch(() => null);
        if (p) await linkPersonaToApp(appId, p.id).catch(() => {});
      }
    }
    setSaving(false);
    onDone();
  }

  if (suggestions.length === 0) {
    return (
      <div className="mt-6 card p-8 text-center">
        <p className="text-[14px] text-secondary">No suggestions returned. Try adding target audience segments first.</p>
        <button type="button" onClick={onClose} className="mt-4 text-[13px] text-brand hover:underline">Dismiss</button>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-medium text-primary">AI suggested personas</h3>
          <p className="text-[12px] text-tertiary">Based on your target audience — select which to add</p>
        </div>
        <button type="button" onClick={onClose} className="text-[13px] text-secondary hover:text-primary">Dismiss</button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {suggestions.map((s, i) => {
          const existing = s.type === "existing"
            ? allPersonas.find((p) => p.id === s.persona_id || p.id === s.persona_id)
            : null;
          const isSelected = selected.has(i);
          const alreadyLinked = s.type === "existing" && s.persona_id && linkedIds.includes(s.persona_id);

          return (
            <button
              key={i}
              type="button"
              onClick={() => !alreadyLinked && toggle(i)}
              className={`card relative p-5 text-left transition-all ${
                alreadyLinked
                  ? "opacity-50 cursor-not-allowed"
                  : isSelected
                  ? "ring-2 ring-accent"
                  : "hover:shadow-md"
              }`}
            >
              {/* Type badge */}
              <div className="mb-3 flex items-center justify-between">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  alreadyLinked
                    ? "bg-field text-tertiary"
                    : s.type === "existing"
                    ? "bg-tint-ok text-ok"
                    : "bg-tint-friction text-friction"
                }`}>
                  {alreadyLinked ? "Already linked" : s.type === "existing" ? "In library" : "New"}
                </span>
                {!alreadyLinked && (
                  <span className={`h-4 w-4 rounded border-2 transition-colors ${
                    isSelected ? "border-accent bg-accent" : "border-hairline"
                  }`}>
                    {isSelected && <span className="flex h-full items-center justify-center text-[9px] text-white">✓</span>}
                  </span>
                )}
              </div>

              {/* Avatar + name */}
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-field">
                  {existing?.figurineUrl ? (
                    <img src={existing.figurineUrl} alt="" className="h-10 w-10 rounded-full object-cover" />
                  ) : (
                    <div className="flex h-10 w-10 items-center justify-center text-[18px] text-tertiary">
                      {s.type === "new" ? "?" : "?"}
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="truncate font-display text-[15px] text-primary">
                    {existing?.identity.name ?? s.name}
                  </div>
                  <div className="truncate text-[11px] text-tertiary">
                    {existing?.identity.label ?? s.label}
                  </div>
                </div>
              </div>

              {/* Traits */}
              <div className="mt-3 flex flex-wrap gap-1">
                {[
                  existing?.identity.ageBand ?? s.age_band,
                  existing?.identity.language ?? s.language,
                  ...(existing?.identity.disabilities ?? s.disabilities ?? []),
                ].filter(Boolean).map((t) => (
                  <span key={t} className="rounded-full bg-field px-2 py-0.5 text-[11px] text-secondary">{t}</span>
                ))}
              </div>

              {/* Segment + reason */}
              <div className="mt-3 border-t border-hairline pt-3">
                <span className="text-[11px] font-medium text-accent">{s.match_segment}</span>
                <div className="mt-2">
                  <span className="section-label" style={{ fontSize: 10 }}>Reasoning</span>
                  <p className="mt-1 text-[11px] italic text-tertiary">{s.match_reason}</p>
                  {s.match_detail && (
                    <p className="mt-1 text-[11px] text-secondary">{s.match_detail}</p>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() =>
            setSelected(
              selected.size === suggestions.length
                ? new Set()
                : new Set(suggestions.map((_, i) => i))
            )
          }
          className="text-[13px] text-secondary hover:text-primary"
        >
          {selected.size === suggestions.length ? "Deselect all" : "Select all"}
        </button>
        <button
          type="button"
          onClick={handleAdd}
          disabled={saving || selected.size === 0}
          className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? "Adding…" : `Add selected (${selected.size})`}
        </button>
      </div>
    </div>
  );
}

function AddPersonaModal({
  allPersonas,
  linkedIds,
  appId,
  onClose,
  onAdded,
}: {
  allPersonas: Persona[];
  linkedIds: string[];
  appId: string;
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
    setSaving(true);
    for (const id of selected) {
      await linkPersonaToApp(appId, id);
    }
    onAdded();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[85vh] w-[480px] flex-col rounded-[20px] bg-card p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between">
          <h3 className="font-display text-[20px] text-primary">Add personas</h3>
          <button type="button" onClick={onClose} className="text-[14px] text-secondary hover:text-primary">
            Close
          </button>
        </div>
        <div className="mt-4 flex-1 overflow-y-auto">
          {available.length === 0 ? (
            <p className="py-8 text-center text-[14px] text-secondary">All personas are already linked.</p>
          ) : (
            available.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => toggle(p.id)}
                className={`flex w-full items-start gap-3 rounded-lg p-3 text-left transition-colors ${
                  selected.includes(p.id) ? "bg-brand/10" : "hover:bg-field"
                }`}
              >
                <div className="mt-0.5 h-8 w-8 shrink-0 overflow-hidden rounded-full bg-field">
                  {p.figurineUrl && (
                    <img src={p.figurineUrl} alt={p.identity.name} className="h-8 w-8 rounded-full object-cover" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14px] font-medium text-primary">{p.identity.name}</div>
                  <div className="group/label relative">
                    <div className="text-[12px] text-tertiary">{p.identity.label}</div>
                    {p.identity.label && p.identity.label.length > 40 && (
                      <div className="pointer-events-none absolute left-0 top-full z-50 mt-1.5 w-72 rounded-xl border border-hairline bg-card p-3 opacity-0 shadow-xl transition-opacity duration-150 group-hover/label:opacity-100">
                        <p className="text-[12px] leading-relaxed text-secondary">{p.identity.label}</p>
                      </div>
                    )}
                  </div>
                </div>
                {selected.includes(p.id) && (
                  <span className="shrink-0 text-[14px] text-brand">✓</span>
                )}
              </button>
            ))
          )}
        </div>
        <button
          type="button"
          onClick={handleAdd}
          disabled={saving || selected.length === 0}
          className="mt-4 w-full shrink-0 rounded-xl bg-brand py-3 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
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
  stagingUrl,
  linkedPersonas,
  mode,
}: {
  runs: RunSummary[];
  projectId: string;
  showRunner: boolean;
  onHide: () => void;
  appName: string;
  stagingUrl?: string;
  linkedPersonas: Persona[];
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
          <AssessmentRunner
            defaultAppName={appName}
            defaultTarget={stagingUrl}
            linkedPersonas={linkedPersonas}
            mode={mode}
          />
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

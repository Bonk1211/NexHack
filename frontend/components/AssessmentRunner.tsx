"use client";

import { useEffect, useRef, useState } from "react";
import {
  getPersonas,
  streamRun,
  mediaUrl,
  type PersonaOption,
  type Pack,
  type ReplayFrame,
  type StreamEvent,
  type UsageSummary,
} from "@/lib/live";

const DEFAULT_TARGET = "http://localhost:8000/fixture/index.html";

// Map an empathy-replay lens (§14) to the CSS filter that renders the screen
// "through the persona's lens" over the captured frame.
const LENS_FILTER: Record<string, string> = {
  low_vision_blur: "blur(2.2px)",
  contrast: "contrast(0.55) brightness(1.05)",
  daltonize: "grayscale(0.4) hue-rotate(40deg)",
  tap_target_overlay: "saturate(1.4)",
  caption_cue: "none",
  reading_load: "none",
};

const STATUS_COLOR: Record<string, string> = {
  green: "text-ok",
  amber: "text-friction",
  red: "text-blocked",
  na: "text-tertiary",
};
const STATUS_DOT: Record<string, string> = {
  green: "bg-ok",
  amber: "bg-friction",
  red: "bg-blocked",
  na: "bg-tertiary",
};

function pct(n: number) {
  return `${Math.round(n * 100)}%`;
}

// ── Live run state, accumulated from the SSE stream ──────────────────────
// One card per executed node (graph-execution-cards), showing its OUTPUT.
interface NodeCardItem {
  id: number;
  scope: "run" | "persona";
  node: string;
  persona?: string;
  status?: string; // step status (red/amber/green) where applicable
  output?: Record<string, unknown>;
  screenshot_url?: string | null;
}
interface LiveState {
  runNodes: string[]; // run-scope nodes seen, in order (for the pipeline bar)
  log: NodeCardItem[]; // every node execution, with its output
  frame?: { persona: string; data: string }; // latest live-browser JPEG (base64)
  n: number; // monotonic id source
}

const RUN_PIPELINE = ["init", "aggregate", "score", "evidence", "alerts"];

function push(s: LiveState, item: Omit<NodeCardItem, "id">): LiveState {
  return { ...s, n: s.n + 1, log: [...s.log, { id: s.n, ...item }] };
}

function reduce(s: LiveState, e: StreamEvent): LiveState {
  if (e.type === "frame") {
    return { ...s, frame: { persona: e.persona, data: e.data } };
  }
  if (e.type === "node" && e.scope === "run") {
    const runNodes = s.runNodes.includes(e.node) ? s.runNodes : [...s.runNodes, e.node];
    return push({ ...s, runNodes }, { scope: "run", node: e.node, output: e.output });
  }
  if (e.type === "node" && e.scope === "persona") {
    return push(s, {
      scope: "persona", node: e.node, persona: e.persona,
      output: e.output, screenshot_url: e.screenshot_url ?? undefined,
    });
  }
  if (e.type === "step") {
    return push(s, {
      scope: "persona", node: "act", persona: e.persona, status: e.status,
      output: e.output, screenshot_url: e.screenshot_url,
    });
  }
  if (e.type === "persona_start") {
    return push(s, { scope: "persona", node: "start", persona: e.persona, output: { label: e.label } });
  }
  if (e.type === "persona_done") {
    return push(s, {
      scope: "persona", node: "done", persona: e.persona,
      status: e.verdict === "blocked" ? "red" : "green",
      output: { verdict: e.verdict, severity: e.severity, blocked_at: e.blocked_at },
    });
  }
  return s;
}

export default function AssessmentRunner({
  defaultTarget = DEFAULT_TARGET,
  defaultAppName = "DemoBank",
}: {
  defaultTarget?: string;
  defaultAppName?: string;
}) {
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [selected, setSelected] = useState<string[]>(["control", "oku_visual", "oku_motor"]);
  const [target, setTarget] = useState(defaultTarget);
  const [appName, setAppName] = useState(defaultAppName);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pack, setPack] = useState<Pack | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [live, setLive] = useState<LiveState | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getPersonas().then(setPersonas).catch((e) => setError(String(e)));
    return () => esRef.current?.close();
  }, []);

  const toggle = (stem: string) =>
    setSelected((s) => (s.includes(stem) ? s.filter((x) => x !== stem) : [...s, stem]));

  const canRun = selected.length >= 3 && !!target && !loading; // FR-1.4: ≥3 personas

  function run() {
    setLoading(true);
    setError(null);
    setPack(null);
    setLive({ runNodes: [], log: [], n: 1 });
    setUsage(null);
    esRef.current?.close();
    esRef.current = streamRun({ appName, targetUrl: target, personaNames: selected }, (e) => {
      if (e.type === "usage") {
        setUsage(e.summary);
        return;
      }
      if (e.type === "final") {
        setPack(e.pack);
        setRunId(e.run_id);
        if (e.usage) setUsage(e.usage);
        setLive(null);
        setLoading(false);
        esRef.current?.close();
        return;
      }
      if (e.type === "error") {
        setError(e.message);
        setUsage(null);
        setLoading(false);
        esRef.current?.close();
        return;
      }
      setLive((prev) => (prev ? reduce(prev, e) : prev));
    });
  }

  return (
    <div>
      {/* ── Config ── */}
      <section className="rounded-card bg-card p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_rgba(0,0,0,0.04)]">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="section-label">App name</span>
            <input
              className="rounded-lg bg-field px-3 py-2 text-[14px] text-primary outline-none focus:ring-2 focus:ring-brand"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="section-label">Target URL</span>
            <input
              className="rounded-lg bg-field px-3 py-2 text-[14px] text-primary outline-none focus:ring-2 focus:ring-brand"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
          </label>
        </div>

        <div className="mt-4">
          <span className="section-label">Personas ({selected.length} selected — need ≥3)</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {personas.map((p) => {
              const on = selected.includes(p.stem);
              return (
                <button
                  key={p.stem}
                  type="button"
                  onClick={() => toggle(p.stem)}
                  className={`rounded-full px-3 py-1.5 text-[13px] transition ${
                    on ? "bg-anchor text-on-dark" : "bg-field text-secondary hover:text-primary"
                  }`}
                  title={p.disabilities.join(", ") || "no disability tags"}
                >
                  {p.name}
                </button>
              );
            })}
          </div>
        </div>

        <button
          type="button"
          disabled={!canRun}
          onClick={run}
          className="mt-5 rounded-full bg-brand px-5 py-2.5 text-[14px] font-medium text-white disabled:opacity-40"
        >
          {loading ? "Running agents — streaming nodes…" : "Run assessment"}
        </button>
        {error && <p className="mt-3 text-[13px] text-blocked">{error}</p>}
        {usage && <UsageTicker usage={usage} live={!!live} />}
      </section>

      {live && <LiveView live={live} />}
      {pack && <Results pack={pack} runId={runId} usage={usage} />}
    </div>
  );
}

// ── Live node/agent visualization ────────────────────────────────────────
const NODE_DOT: Record<string, string> = {
  start: "bg-tertiary",
  observe: "bg-brand",
  comprehend: "bg-friction",
  decide: "bg-tertiary",
  act: "bg-anchor",
  done: "bg-ok",
};

function fmtVal(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  return String(v);
}

function formatTokens(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

function formatCost(amount: number, currency: string): string {
  if (amount === 0) return `${currency} 0.0000`;
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 4,
      maximumFractionDigits: 6,
    }).format(amount);
  } catch {
    return `$${amount.toFixed(4)}`;
  }
}

function UsageDetails({ usage, title, dense = false }: { usage: UsageSummary; title: string; dense?: boolean }) {
  const headingClass = dense ? "text-[13px] text-primary" : "text-[16px] text-primary";
  const totalClass = dense ? "font-mono text-[12px] text-anchor" : "font-mono text-[13px] text-anchor";
  const statsClass = dense ? "text-[11px] text-secondary" : "text-[12px] text-secondary";
  const legendClass = dense ? "text-[11px] text-tertiary" : "text-[12px] text-tertiary";
  const modelClass = dense ? "text-[11px] text-secondary" : "text-[12px] text-secondary";

  const prompt = formatTokens(usage.total_prompt_tokens);
  const completion = formatTokens(usage.total_completion_tokens);
  const tokens = formatTokens(usage.total_tokens);
  const costLine = usage.pricing_applied
    ? `Estimated cost ${formatCost(usage.total_cost, usage.currency)}`
    : "Set LLM_PRICING in the backend to unlock cost estimates.";

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className={headingClass}>{title}</span>
        <span className={totalClass}>{tokens} tok</span>
      </div>
      <div className={statsClass}>
        {prompt} prompt · {completion} completion
      </div>
      <div className={legendClass}>{costLine}</div>
      {usage.models.length > 0 && (
        <ul className="mt-2 space-y-1">
          {usage.models.map((m) => (
            <li key={m.model} className="flex items-baseline justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wide text-tertiary">{m.model}</span>
              <span className={`${modelClass} font-mono`}>
                {formatTokens(m.total_tokens)} tok
                {usage.pricing_applied && m.pricing_applied
                  ? ` · ${formatCost(m.cost, usage.currency)}`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function UsageTicker({ usage, live }: { usage: UsageSummary; live: boolean }) {
  return (
    <div className="mt-4 rounded-xl bg-field/60 p-3 shadow-inner">
      <UsageDetails usage={usage} title={live ? "Live token usage" : "Token usage"} dense />
    </div>
  );
}

function UsageCard({ usage }: { usage: UsageSummary }) {
  return (
    <div className="rounded-card bg-card p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <UsageDetails usage={usage} title="Token usage" />
    </div>
  );
}

function NodeOutputCard({ item }: { item: NodeCardItem }) {
  const title = item.scope === "persona" ? `${item.persona} · ${item.node}` : item.node;
  const dot = item.status
    ? STATUS_DOT[item.status]
    : NODE_DOT[item.node] ?? "bg-tertiary";
  const src = mediaUrl(item.screenshot_url ?? null);
  const entries = item.output ? Object.entries(item.output) : [];
  return (
    <div className="flex gap-3 rounded-card bg-card p-3">
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={item.node} className="h-[88px] w-[48px] shrink-0 rounded-md border border-hairline object-cover object-top" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dot}`} />
          <span className="font-mono text-[12px] text-primary">{title}</span>
        </div>
        {entries.length > 0 && (
          <dl className="mt-1.5 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-0.5">
            {entries.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-[11px] text-tertiary">{k}</dt>
                <dd className="truncate text-[11px] text-secondary">{fmtVal(v)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  );
}

function LiveView({ live }: { live: LiveState }) {
  const lastRunNode = live.runNodes[live.runNodes.length - 1];
  const feedRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [live.log.length]);

  return (
    <section className="mt-8">
      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        {/* Live browser — the external app the agent is driving (CDP screencast) */}
        <div>
          <h2 className="section-label mb-2">Live browser</h2>
          <div className="overflow-hidden rounded-[28px] border-4 border-anchor bg-anchor">
            {live.frame ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`data:image/jpeg;base64,${live.frame.data}`}
                alt="live agent browser"
                className="block w-full"
              />
            ) : (
              <div className="flex h-[560px] items-center justify-center text-[12px] text-on-dark-dim">
                launching browser…
              </div>
            )}
          </div>
          {live.frame && (
            <p className="mt-2 text-center text-[12px] text-tertiary">
              {live.frame.persona} · iPhone 13 viewport
            </p>
          )}
        </div>

        <div className="space-y-4">
          {/* Run pipeline bar */}
          <div>
            <h2 className="section-label mb-2">Graph nodes</h2>
            <div className="flex flex-wrap items-center gap-2">
              {RUN_PIPELINE.map((n, i) => {
                const seen = live.runNodes.includes(n);
                const active = lastRunNode === n && n !== "alerts";
                return (
                  <span key={n} className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-[12px] ${
                        active
                          ? "bg-brand text-white animate-pulse"
                          : seen
                            ? "bg-anchor text-on-dark"
                            : "bg-field text-tertiary"
                      }`}
                    >
                      {n}
                    </span>
                    {i < RUN_PIPELINE.length - 1 && <span className="text-tertiary">→</span>}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Per-node output feed (one card per node execution) */}
          <div>
            <h2 className="section-label mb-2">Node outputs</h2>
            <div ref={feedRef} className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {live.log.map((item) => (
                <NodeOutputCard key={item.id} item={item} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Results({ pack, runId, usage }: { pack: Pack; runId: string | null; usage: UsageSummary | null }) {
  return (
    <section className="mt-8 space-y-8">
      {/* Score + synthesis */}
      <div className="rounded-card bg-card p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-[40px] text-primary">{pct(pack.inclusion_score)}</span>
          <span className="text-[13px] text-tertiary">inclusion score · {pack.app}</span>
        </div>
        {pack.synthesis?.rollup && (
          <p className="mt-2 text-[15px] font-medium text-primary">{pack.synthesis.rollup}</p>
        )}
        {pack.synthesis?.narrative && (
          <p className="mt-1 text-[13px] text-secondary">{pack.synthesis.narrative}</p>
        )}
      </div>

      {usage && (
        <div>
          <h2 className="section-label mb-2">Token usage</h2>
          <UsageCard usage={usage} />
        </div>
      )}

      {/* Persona verdicts */}
      <div className="grid gap-3 sm:grid-cols-3">
        {pack.personas.map((p) => {
          const blocked = p.verdict === "blocked";
          return (
            <div
              key={p.persona}
              className={`rounded-card p-4 ${blocked ? "bg-tint-blocked border-l-[3px] border-blocked" : "bg-card"}`}
            >
              <div className="font-display text-[16px] text-primary">{p.persona}</div>
              <div className={`mt-1 text-[13px] ${blocked ? "font-medium text-blocked" : "text-secondary"}`}>
                {blocked ? `Blocked at ${p.blocked_at}` : "Completed"}
                {p.severity ? ` · ${p.severity}` : ""}
              </div>
              {p.wcag_failures.length > 0 && (
                <div className="mt-1 text-[12px] text-tertiary">WCAG: {p.wcag_failures.join(", ")}</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Friction matrix (the hero diff) */}
      <div>
        <h2 className="section-label mb-2">Friction matrix</h2>
        <div className="overflow-x-auto rounded-card bg-card p-3">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-tertiary">
                <th className="p-2 text-left font-medium">persona</th>
                {pack.matrix.steps.map((s) => (
                  <th key={s} className="p-2 text-left font-medium">{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(pack.matrix.rows).map(([persona, cells]) => (
                <tr key={persona} className="border-t border-hairline">
                  <td className="p-2 text-primary">{persona}</td>
                  {pack.matrix.steps.map((s) => {
                    const c = cells[s];
                    return (
                      <td key={s} className="p-2">
                        <span className={`inline-flex items-center gap-1.5 ${STATUS_COLOR[c?.status ?? "na"]}`}>
                          <span className={`h-2 w-2 rounded-full ${STATUS_DOT[c?.status ?? "na"]}`} />
                          {c?.status ?? "na"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Empathy replay — the screen through each persona's lens (§14) */}
      <div>
        <h2 className="section-label mb-2">Empathy replay</h2>
        <div className="space-y-6">
          {Object.entries(pack.replay).map(([persona, clip]) => (
            <div key={persona} className="rounded-card bg-card p-4">
              <div className="flex items-center gap-2">
                <span className="font-display text-[15px] text-primary">{persona}</span>
                {clip.lenses.length > 0 ? (
                  clip.lenses.map((l) => (
                    <span key={l} className="rounded-full bg-field px-2 py-0.5 text-[11px] text-secondary">
                      {l}
                    </span>
                  ))
                ) : (
                  <span className="text-[11px] text-tertiary">baseline (no lens)</span>
                )}
              </div>
              <div className="mt-3 flex gap-4 overflow-x-auto pb-2">
                {clip.frames.map((f) => (
                  <Frame key={f.step_idx} frame={f} lenses={clip.lenses} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {runId && <p className="text-[12px] text-tertiary">run {runId}</p>}
    </section>
  );
}

function Frame({ frame, lenses }: { frame: ReplayFrame; lenses: string[] }) {
  const filter = lenses.map((l) => LENS_FILTER[l]).filter((x) => x && x !== "none").join(" ");
  const src = mediaUrl(frame.screenshot_url);
  return (
    <div className="w-[180px] shrink-0">
      <div className="overflow-hidden rounded-lg border border-hairline bg-field">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={`${frame.step_key} as seen`}
            className="h-[300px] w-full object-cover object-top"
            style={{ filter: filter || undefined }}
          />
        ) : (
          <div className="flex h-[300px] items-center justify-center text-[12px] text-tertiary">no frame</div>
        )}
      </div>
      <div className={`mt-1.5 flex items-center gap-1.5 text-[12px] ${STATUS_COLOR[frame.status]}`}>
        <span className={`h-2 w-2 rounded-full ${STATUS_DOT[frame.status]}`} />
        {frame.step_key}
      </div>
      <div className="text-[12px] text-secondary">{frame.caption}</div>
    </div>
  );
}

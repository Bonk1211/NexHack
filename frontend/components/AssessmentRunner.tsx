"use client";

import { useEffect, useRef, useState } from "react";
import {
  getPersonas,
  streamRun,
  mediaUrl,
  type PersonaOption,
  type Pack,
  type ReplayClip,
  type PersonaResult,
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
  monologue?: string; // first-person line the persona "says" on this step
}
export interface LiveState {
  runNodes: string[]; // run-scope nodes seen, in order (for the pipeline bar)
  log: NodeCardItem[]; // every node execution, with its output
  frames: Record<string, string>; // persona stem → latest live-browser JPEG (base64)
  n: number; // monotonic id source
}

const RUN_PIPELINE = ["init", "aggregate", "score", "evidence", "alerts"];

function push(s: LiveState, item: Omit<NodeCardItem, "id">): LiveState {
  return { ...s, n: s.n + 1, log: [...s.log, { id: s.n, ...item }] };
}

export function reduce(s: LiveState, e: StreamEvent): LiveState {
  if (e.type === "frame") {
    return { ...s, frames: { ...s.frames, [e.persona]: e.data } };
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
      output: e.output, screenshot_url: e.screenshot_url, monologue: e.monologue,
    });
  }
  if (e.type === "monologue") {
    return push(s, { scope: "persona", node: "say", persona: e.persona, monologue: e.text });
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
  defaultTarget,
  defaultAppName = "DemoBank",
  linkedPersonas = [],
  mode = "sequential",
}: {
  defaultTarget?: string;
  defaultAppName?: string;
  linkedPersonas?: { id: string; identity: { name: string; disabilities: string[] } }[];
  mode?: "sequential" | "parallel";
}) {
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [target, setTarget] = useState(defaultTarget || "");
  const [appName, setAppName] = useState(defaultAppName);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pack, setPack] = useState<Pack | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [live, setLive] = useState<LiveState | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [showConfigError, setShowConfigError] = useState(!defaultTarget || linkedPersonas.length === 0);
  // After a run completes both views coexist; this toggles which one is shown so
  // the user can move back and forth between the live preview and the results.
  const [view, setView] = useState<"live" | "results">("live");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getPersonas().then((allPersonas) => {
      // Normalize: backend returns {id, identity:{name,...}} but UI expects {stem, name, disabilities}
      const normalized = allPersonas.map((p) => ({
        ...p,
        stem: p.stem || (p as any).id || "",
        name: p.name || (p as any).identity?.name || (p as any).id || "",
        disabilities: p.disabilities || (p as any).identity?.disabilities || [],
      }));
      const linkedIds = new Set(linkedPersonas.map((p) => p.id));
      const filtered = normalized.filter((p) => linkedIds.has(p.stem));
      setPersonas(filtered);
      setSelected(filtered.map((p) => p.stem));
    }).catch((e) => setError(String(e)));
    return () => esRef.current?.close();
  }, [linkedPersonas]);

  const toggle = (stem: string) =>
    setSelected((s) => (s.includes(stem) ? s.filter((x) => x !== stem) : [...s, stem]));

  const canRun = selected.length >= 1 && !!target && !loading && !showConfigError;

  function run() {
    setLoading(true);
    setError(null);
    setPack(null);
    setLive({ runNodes: [], log: [], frames: {}, n: 1 });
    setUsage(null);
    setView("live");
    esRef.current?.close();
    esRef.current = streamRun({ appName, targetUrl: target, personaNames: selected, mode }, (e) => {
      if (e.type === "usage") {
        setUsage(e.summary);
        return;
      }
      if (e.type === "final") {
        setPack(e.pack);
        setRunId(e.run_id);
        if (e.usage) setUsage(e.usage);
        // Keep `live` so the preview stays available; surface the results view.
        setView("results");
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
      {showConfigError && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="w-[480px] rounded-[20px] bg-card p-8 shadow-2xl">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blocked/10">
                <svg className="h-5 w-5 text-blocked" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="font-display text-[20px] text-primary">Configuration required</h3>
                <div className="mt-3 space-y-2 text-[14px] text-secondary">
                  {!defaultTarget && (
                    <p>No staging URL configured for this project. Please add a staging URL in the project settings before running tests.</p>
                  )}
                  {linkedPersonas.length === 0 && (
                    <p>No personas linked to this project. Please link at least 3 personas from the Personas tab before running tests.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

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
          <span className="section-label">Personas ({selected.length} selected)</span>
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
                  title={(p.disabilities || []).join(", ") || "no disability tags"}
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

      {/* Once a run finishes, both views coexist — switch between them freely. */}
      {pack && (
        <div className="mt-6 inline-flex items-center gap-1 rounded-lg bg-field p-1">
          {(["live", "results"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1 text-[12px] font-medium capitalize transition-colors ${
                view === v ? "bg-card text-primary shadow-sm" : "text-secondary hover:text-primary"
              }`}
            >
              {v === "live" ? "Live preview" : "Results"}
            </button>
          ))}
        </div>
      )}

      {live && (!pack || view === "live") && <LiveView live={live} />}
      {pack && view === "results" && <Results pack={pack} runId={runId} usage={usage} />}
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
          {item.scope === "run" && (
            <span className="rounded-full bg-field px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-tertiary">
              shared
            </span>
          )}
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

export function LiveView({
  live,
  personaInfoMap = {},
}: {
  live: LiveState;
  personaInfoMap?: Record<string, { name: string; figurineUrl?: string }>;
}) {
  const lastRunNode = live.runNodes[live.runNodes.length - 1];

  // Personas present in this run, in stream order. Persona-scope log items establish
  // the order; any persona that has only streamed a frame so far is appended.
  const personas: string[] = [];
  for (const item of live.log) {
    if (item.scope === "persona" && item.persona && !personas.includes(item.persona)) {
      personas.push(item.persona);
    }
  }
  for (const p of Object.keys(live.frames)) {
    if (!personas.includes(p)) personas.push(p);
  }

  return (
    <section className="mt-8 space-y-4">
      {/* Run pipeline bar — run-scope nodes, shared across all personas (rendered once) */}
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

      {/* One column per persona — own live browser + own node-reasoning feed (no mixing) */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {personas.map((p) => (
          <PersonaColumn
            key={p}
            persona={p}
            frame={live.frames[p]}
            personaInfo={personaInfoMap[p]}
            items={live.log.filter(
              (it) => it.scope === "run" || (it.scope === "persona" && it.persona === p),
            )}
          />
        ))}
      </div>
    </section>
  );
}

// Chat-bubble feed of the persona's first-person monologue. History renders static;
// only the latest line animates char-by-char (typewriter).
function MonologueFeed({ lines }: { lines: { id: number; text: string }[] }) {
  const last = lines[lines.length - 1];
  const typed = useTypewriter(last?.text ?? "");
  if (lines.length === 0) return null;
  return (
    <div className="mt-3 space-y-1.5">
      {lines.map((l, i) => (
        <div
          key={l.id}
          className="rounded-2xl rounded-tl-sm bg-anchor/10 px-3 py-1.5 text-[12px] leading-snug text-primary"
        >
          {i === lines.length - 1 ? typed : l.text}
        </div>
      ))}
    </div>
  );
}

// Reveal `text` one character at a time. Resets whenever the line changes.
function useTypewriter(text: string, msPerChar = 24) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    if (!text) return;
    const id = setInterval(() => {
      setN((c) => {
        if (c >= text.length) {
          clearInterval(id);
          return c;
        }
        return c + 1;
      });
    }, msPerChar);
    return () => clearInterval(id);
  }, [text, msPerChar]);
  return text.slice(0, n);
}

// One persona's live lane: its CDP screencast frame above its own node feed. Each
// column owns its scroll ref so feeds autoscroll independently.
function PersonaColumn({
  persona,
  frame,
  items,
  personaInfo,
}: {
  persona: string;
  frame?: string;
  items: NodeCardItem[];
  personaInfo?: { name: string; figurineUrl?: string };
}) {
  const feedRef = useRef<HTMLDivElement | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [items.length]);

  const displayName = personaInfo?.name ?? persona;
  const monologue = items
    .filter((it) => it.monologue)
    .map((it) => ({ id: it.id, text: it.monologue as string }));

  return (
    <div className="rounded-card bg-card p-3">
      {/* Persona header */}
      <div className="mb-3 flex items-center gap-2">
        {personaInfo?.figurineUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={personaInfo.figurineUrl} alt={displayName} className="h-7 w-7 rounded-full object-cover shrink-0" />
        ) : (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-anchor text-[11px] font-semibold text-on-dark">
            {displayName.charAt(0).toUpperCase()}
          </div>
        )}
        <span className="section-label truncate">{displayName}</span>
      </div>

      {/* Phone frame — CDP screencast renders here as it streams */}
      <div className="mx-auto w-[148px]">
        <div className="relative rounded-[28px] border-[6px] border-gray-900 bg-black shadow-xl">
          {/* notch */}
          <div className="absolute left-1/2 top-[6px] z-10 h-[10px] w-[40px] -translate-x-1/2 rounded-full bg-gray-900" />
          <div className="overflow-hidden rounded-[22px]">
            {frame ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`data:image/jpeg;base64,${frame}`}
                alt={`${displayName} live browser`}
                className="block w-full"
              />
            ) : (
              <div className="flex h-[288px] items-center justify-center bg-gray-950 text-[11px] text-gray-500">
                launching browser…
              </div>
            )}
          </div>
        </div>
        {/* home bar */}
        <div className="mx-auto mt-2 h-[4px] w-[36px] rounded-full bg-gray-300" />
      </div>

      {/* Toggle: raw node cards are secondary, hidden behind this by default */}
      <div className="mt-3 flex justify-end">
        <button
          onClick={() => setShowDetails((v) => !v)}
          className="text-[11px] text-tertiary hover:text-secondary"
        >
          {showDetails ? "Hide node details" : "Show node details"}
        </button>
      </div>

      {showDetails ? (
        // Raw graph-execution cards
        <div ref={feedRef} className="mt-2 max-h-[280px] space-y-2 overflow-y-auto pr-1">
          {(() => {
            const nodeCards = items.filter((it) => it.node !== "say");
            return nodeCards.length === 0 ? (
              <p className="text-[12px] text-tertiary">waiting for nodes…</p>
            ) : (
              nodeCards.map((item) => <NodeOutputCard key={item.id} item={item} />)
            );
          })()}
        </div>
      ) : (
        // First-person monologue — primary live view
        <div ref={feedRef} className="mt-2 max-h-[280px] overflow-y-auto pr-1">
          {monologue.length === 0 ? (
            <p className="text-[12px] text-tertiary">waiting for the persona to speak…</p>
          ) : (
            <MonologueFeed lines={monologue} />
          )}
        </div>
      )}
    </div>
  );
}

export function Results({ pack, runId, usage }: { pack: Pack; runId: string | null; usage: UsageSummary | null }) {
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

      {/* Empathy replay — one card per persona: an NLP summary of the friction they
          hit, with the screenshots collapsed into an expandable, slideable carousel. */}
      <div>
        <h2 className="section-label mb-2">Empathy replay</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(pack.replay).map(([persona, clip]) => (
            <ReplayCard
              key={persona}
              persona={persona}
              clip={clip}
              result={pack.personas.find((p) => p.persona === persona)}
            />
          ))}
        </div>
      </div>

      {runId && <p className="text-[12px] text-tertiary">run {runId}</p>}
    </section>
  );
}

// Compose a one-line, natural-language account of what this persona ran into,
// derived from their verdict plus the per-frame friction captions.
function replaySummary(clip: ReplayClip, result?: PersonaResult): string {
  const problems = clip.frames.filter((f) => f.status === "red" || f.status === "amber");
  if (result?.verdict === "blocked") {
    const where = result.blocked_at ? ` at “${result.blocked_at}”` : "";
    const sev = result.severity ? ` (${result.severity})` : "";
    const red = clip.frames.find((f) => f.status === "red");
    const why = red && red.caption !== "ok" ? ` — ${red.caption}` : "";
    return `Blocked${where}${sev}${why}.`;
  }
  if (problems.length > 0) {
    const first = problems[0];
    const detail = first.caption !== "ok" ? `: ${first.caption}` : "";
    return `Completed with friction on ${problems.length} step${problems.length > 1 ? "s" : ""} — first at “${first.step_key}”${detail}.`;
  }
  return "Completed the whole flow with no friction flagged.";
}

function ReplayCard({
  persona,
  clip,
  result,
}: {
  persona: string;
  clip: ReplayClip;
  result?: PersonaResult;
}) {
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);
  const n = clip.frames.length;
  const blocked = result?.verdict === "blocked";
  const filter = clip.lenses.map((l) => LENS_FILTER[l]).filter((x) => x && x !== "none").join(" ");

  const cur = n > 0 ? clip.frames[Math.min(idx, n - 1)] : undefined;
  const src = cur ? mediaUrl(cur.screenshot_url) : null;
  const go = (d: number) => setIdx((i) => (i + d + n) % n);

  return (
    <div className={`rounded-card p-4 ${blocked ? "bg-tint-blocked border-l-[3px] border-blocked" : "bg-card"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-display text-[15px] text-primary">{persona}</span>
        {clip.lenses.length > 0 ? (
          clip.lenses.map((l) => (
            <span key={l} className="rounded-full bg-field px-2 py-0.5 text-[11px] text-secondary">{l}</span>
          ))
        ) : (
          <span className="text-[11px] text-tertiary">baseline (no lens)</span>
        )}
      </div>

      {/* NLP summary — always visible, the space-saving default */}
      <p className={`mt-2 text-[13px] leading-relaxed ${blocked ? "font-medium text-blocked" : "text-secondary"}`}>
        {replaySummary(clip, result)}
      </p>
      {result && result.wcag_failures.length > 0 && (
        <p className="mt-1 text-[12px] text-tertiary">WCAG: {result.wcag_failures.join(", ")}</p>
      )}

      {n > 0 && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="mt-3 text-[12px] font-medium text-brand hover:underline"
        >
          {open ? "Hide screenshots" : `Show ${n} screenshot${n > 1 ? "s" : ""}`}
        </button>
      )}

      {/* Slideable carousel — one frame at a time, revealed on demand */}
      {open && cur && (
        <div className="mt-3">
          <div className="relative overflow-hidden rounded-lg border border-hairline bg-field">
            {src ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={src}
                alt={`${cur.step_key} as ${persona} saw it`}
                className="h-[320px] w-full object-cover object-top"
                style={{ filter: filter || undefined }}
              />
            ) : (
              <div className="flex h-[320px] items-center justify-center text-[12px] text-tertiary">no frame</div>
            )}
            {n > 1 && (
              <>
                <button
                  type="button"
                  onClick={() => go(-1)}
                  aria-label="Previous screenshot"
                  className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-anchor/70 px-2.5 py-1 text-[14px] text-on-dark hover:bg-anchor"
                >
                  ‹
                </button>
                <button
                  type="button"
                  onClick={() => go(1)}
                  aria-label="Next screenshot"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-anchor/70 px-2.5 py-1 text-[14px] text-on-dark hover:bg-anchor"
                >
                  ›
                </button>
                <span className="absolute bottom-2 right-2 rounded-full bg-anchor/70 px-2 py-0.5 text-[11px] text-on-dark">
                  {Math.min(idx, n - 1) + 1} / {n}
                </span>
              </>
            )}
          </div>
          <div className={`mt-1.5 flex items-center gap-1.5 text-[12px] ${STATUS_COLOR[cur.status]}`}>
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT[cur.status]}`} />
            {cur.step_key}
          </div>
          <div className="text-[12px] text-secondary">{cur.caption}</div>
        </div>
      )}
    </div>
  );
}

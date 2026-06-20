# Per-Project Aggregated Dashboard — Spec

> InclusionScope. Upgrades the existing `frontend/app/projects/[projectId]/page.tsx`
> from a "latest run" view into an **aggregated, multi-run dashboard** per project
> (= per app under test), surfacing insights, actions, and LLM token usage.
> Status: design only. No code in this doc.

## 1. Scope & framing

"Project" in InclusionScope = a target app (`apps` table). You already have a
per-project route with `overview / personas / runs` tabs, but Overview only renders
`project.latestRun`. This spec adds a fourth tab — **Dashboard** — that aggregates
*across all runs* for the app, plus the persistence needed to make that real.

Four insight tracks (all selected):

1. Persona pass/block trends (INDICATIVE stream)
2. Cost efficiency — token usage & cost (new data)
3. WCAG conformance trend (TRUSTED stream)
4. P0 blocks & owner routing (action queue)

The two-stream discipline (§16) is preserved: WCAG trend is drawn from the trusted
`screen_events.wcag_conformance`; persona trends are labeled INDICATIVE; cost is
operational metadata and never feeds the inclusion score.

## 2. The blocking problem: token usage is not persisted

This is the load-bearing finding. Today:

- `backend/app/llm_usage.py` tracks prompt/completion tokens + cost per run via an
  `LLMUsageTracker`, exposed through `serialized()`.
- `backend/app/routes/runs.py` holds results in `_STORE` — an in-memory dict that
  "survives only for the process lifetime" (its own comment). Usage is streamed over
  SSE (`{"type":"usage", "summary": ...}`) and returned on the final payload.
- The `runs` table has **no** token/cost columns. `frontend/lib/types.ts` has **no**
  usage type.

So there is nothing to aggregate. Restart the backend and all token history is gone.
Any "aggregated token usage per project" requires persisting usage first. That is
Phase 1 below.

## 3. Data model changes

### 3.1 New migration `0003_usage.sql`

Add a per-run usage rollup and a per-model breakdown. Mirrors the shape already
emitted by `LLMUsageTracker.serialized()`, so the write path is a near-direct copy.

```sql
-- Per-run token/cost rollup (one row per run)
alter table runs
  add column if not exists prompt_tokens     bigint  not null default 0,
  add column if not exists completion_tokens bigint  not null default 0,
  add column if not exists total_tokens      bigint  not null default 0,
  add column if not exists llm_cost          numeric not null default 0,
  add column if not exists llm_currency      text    not null default 'USD',
  add column if not exists pricing_applied   boolean not null default false;

-- Per-model breakdown within a run (DeepSeek today; keep model-keyed for the
-- §25 "model family is open" decision)
create table if not exists run_model_usage (
  id                uuid primary key default gen_random_uuid(),
  run_id            uuid not null references runs(id) on delete cascade,
  model             text not null,
  prompt_tokens     bigint  not null default 0,
  completion_tokens bigint  not null default 0,
  total_tokens      bigint  not null default 0,
  cost              numeric not null default 0,
  pricing_applied   boolean not null default false,
  created_at        timestamptz not null default now(),
  unique (run_id, model)
);

create index if not exists idx_run_model_usage_run on run_model_usage(run_id);
```

Optional (defer unless cost-per-persona is needed): add `prompt_tokens`,
`completion_tokens`, `cost` to `run_personas`. Requires attributing each LLM call to
the active persona — the tracker is currently run-scoped, not persona-scoped, so this
is a real change, not a column add. Listed as a stretch item, not Phase 1.

### 3.2 Write path

In `routes/runs.py`, where `_STORE[rid] = {"pack": pack, "usage": usage}` is set on
run completion, also persist: write the rollup onto the `runs` row and insert one
`run_model_usage` row per entry in `usage["models"]`. Do this in the same place for
both the sync and streaming endpoints (lines ~106 and ~266). Keep `_STORE` as a live
cache; the DB becomes the durable source for aggregation.

## 4. API additions

Backend (FastAPI), consumed by `frontend/lib/api.ts`:

- `GET /projects/{id}/dashboard` → single aggregated payload (preferred — one fetch,
  matches the existing `getProject` pattern). Shape in §5.
- Alternatively reuse `GET /projects/{id}/runs` and aggregate client-side, but
  per-model usage and WCAG criterion rollups are cheaper to compute in SQL. Recommend
  the dedicated endpoint.

Frontend: add `getProjectDashboard(projectId): Promise<ProjectDashboard>` alongside
the existing mock-friendly functions in `api.ts` (the file's comment notes swapping
mock → real `fetch()` is a one-line change; keep that property).

## 5. Types (frontend/lib/types.ts)

```ts
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

// One point per run, oldest → newest, for trend charts
export interface RunTrendPoint {
  runId: string;
  createdAt: string;
  overallScore: number;     // composite (DERIVED)
  blockedCount: number;     // INDICATIVE
  wcagPassRate: number;     // 0..1 TRUSTED
  totalTokens: number;
  cost: number;
}

export interface PersonaReliability {
  personaId: string;
  name: string;
  runsCount: number;
  blockedCount: number;     // across runs
  blockRate: number;        // 0..1, blockedCount / runsCount
  lastStatus: Severity;
}

export interface ActionItem {
  runId: string;
  personaId: string;
  personaName: string;
  severity: "P0" | "P1" | "P2" | "P3";
  blockedAt: string;        // step key
  wcagCriterion?: string;   // from trusted stream when available
  owner?: string;           // routed owning area (§13 remediation)
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
  usageByModel: UsageModel[];      // summed across runs
  actions: ActionItem[];           // open P0/P1, sorted by severity then recency
}
```

## 6. UI layout — Dashboard tab

Add `"dashboard"` to the `Tab` union in `page.tsx`. Layout, top to bottom, reusing
existing tokens/components (`card`, `section-label`, `ScoreRing`, `StatusDot`):

**Row A — KPI cards (4 across):**

- Inclusion score (latest) with delta vs previous run — `ScoreRing`.
- WCAG pass rate (latest) + arrow vs previous (TRUSTED, badge it).
- Open P0 blocks (count) — red if > 0.
- LLM cost — total across runs + total tokens; show "est." when
  `pricingApplied` is false (no pricing table configured).

**Row B — Trends (2 charts):**

- Score & block trend over runs: line (overallScore) + bar (blockedCount).
- WCAG pass-rate trend (TRUSTED) over runs. Keep visually separate from the
  composite so the trusted stream is never confused with the derived one.

**Row C — Cost efficiency:**

- Cost-per-run line + tokens-per-run.
- Usage-by-model table (`usageByModel`): model, prompt/completion/total tokens,
  cost. Label as DeepSeek today; table form survives a model swap (§25).

**Row D — Persona reliability:**

- Table from `personaReliability`, sorted by `blockRate` desc: persona, runs,
  blocked, block-rate bar, last status (`StatusDot`). This answers "which personas
  keep failing." INDICATIVE label.

**Row E — Action queue (the "what to do"):**

- List from `actions`: severity chip, persona, step blocked at, WCAG criterion,
  owner. Sorted P0→P3 then most recent. Links to the run detail
  (`/projects/{id}/runs/{runId}`). This is the compliance-action payoff and maps to
  `evidence_packs.remediation` (§13).

## 7. Build order (marks-ordered, mirrors README §21 style)

1. **Persist usage** — migration `0003_usage.sql` + write path in `runs.py`. Without
   this nothing aggregates. Backfill is impossible (data was never stored), so the
   dashboard is empty until the first post-deploy run — acceptable.
2. **Aggregation endpoint** — `GET /projects/{id}/dashboard` computing §5 from
   `runs`, `run_personas`, `screen_events`, `run_model_usage`.
3. **Types + api client** — add §5 types, `getProjectDashboard`.
4. **Dashboard tab shell + KPI cards** (Row A) — visible value fast.
5. **Trend charts** (Rows B, C) — a charting lib is a new frontend dep; pick one
   (e.g. Recharts) or render lightweight inline SVG to avoid the dep.
6. **Persona reliability + action queue** (Rows D, E).

## 8. Decisions to confirm before build

- **Chart dependency:** add Recharts (fast, heavier) vs hand-rolled SVG sparklines
  (no dep, more code). Default recommendation: inline SVG for the few charts here,
  consistent with the lean frontend.
- **Cost per persona:** Phase 1 is run-level only. Per-persona cost needs the tracker
  scoped per persona — confirm if that insight is worth the refactor.
- **Pricing table:** cost numbers are zero/`pricing_applied=false` until
  `llm_pricing` is set in config. Decide whether to ship a default DeepSeek pricing
  entry so the cost cards aren't empty in the demo.
- **Empty/low-N states:** with <2 runs there is no trend. Define the copy for the
  "needs more runs" state.

## 9. Out of scope

Cross-project (portfolio) roll-up — this dashboard is per-project by request. A
home-page portfolio table is a separate, easy follow-on once §5 exists. No new auth,
no export (evidence pack already covers PDF/JSON export, §13).

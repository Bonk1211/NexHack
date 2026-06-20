# Plan: Per-Persona 2×3 Acceptance-Test Grid under the Run section

## Summary
Restructure the live acceptance-test view so each persona gets its **own column** — its own
Playwright/CDP live-browser frame plus its own node-reasoning feed — laid out as a 2×3 grid
(3 columns × up to 2 rows). Relocate the whole `AssessmentRunner` out of the **overview** tab and
into the **runs** tab so the live run sits directly above run history. Today every persona's frames
and reasoning are collapsed into a single shared column; the change splits them per persona so no two
personas mix into the same reasoning stream.

## User Story
As an InclusionScope user running an acceptance test across multiple personas,
I want each persona's live browser and reasoning shown in its own column within the Run section,
so that I can watch and compare personas side-by-side without their node outputs bleeding together.

## Problem → Solution
**Current:** `AssessmentRunner` renders in the *overview* tab. Its `LiveView` keeps a **single** latest
`frame` and **one flat `log`** mixing all personas, shown as a two-column layout (one browser + one feed).
→
**Desired:** `AssessmentRunner` renders in the *runs* tab above run history. `LiveView` keeps **one frame
per persona** and **per-persona reasoning buckets**, rendered as a 2×3 grid where each cell is a single
persona (own live frame + own node feed). Run-scope pipeline nodes (`init…alerts`) render once, shared.

## Metadata
- **Complexity**: Medium
- **Source PRD**: N/A (free-form feature request)
- **PRD Phase**: N/A
- **Estimated Files**: 2 (1 core rewrite, 1 relocation)

---

## UX Design

### Before
```
RUNS TAB:                          OVERVIEW TAB (showRunner):
┌─ Run history ─────────────┐      ┌─ Acceptance test — live run ─────────────────┐
│ run_3   72%  1 blocked    │      │ [config: app, url, persona chips, Run btn]   │
│ run_2   80%  0 blocked    │      │ ┌─ Live browser ─┐ ┌─ Graph nodes ────────┐ │
│ run_1   65%  2 blocked    │      │ │  (latest only, │ │ init→aggregate→…     │ │
└───────────────────────────┘      │ │   1 persona)   │ │ ┌ Node outputs ─────┐│ │
                                    │ │                │ │ │ control · observe ││ │
                                    │ │                │ │ │ oku_motor · act   ││ │  ← personas
                                    │ └────────────────┘ │ │ control · decide  ││ │     INTERLEAVED
                                    │                    │ └───────────────────┘│ │     in one feed
                                    │                    └──────────────────────┘ │
                                    └──────────────────────────────────────────────┘
```

### After
```
RUNS TAB:
┌─ Acceptance test — live agent run ───────────────────────────────────────────┐
│ [config: app, url, persona chips, Run btn]                                    │
│ Graph nodes:  init → aggregate → score → evidence → alerts   (shared, once)   │
│ ┌ control ──────┐ ┌ oku_visual ───┐ ┌ oku_motor ────┐                         │
│ │ [live frame]  │ │ [live frame]  │ │ [live frame]  │   row 1 (cols 1–3)      │
│ │ observe       │ │ observe       │ │ observe       │                         │
│ │ comprehend    │ │ comprehend    │ │ act (red)     │   each feed = ONE       │
│ │ act (green)   │ │ act (amber)   │ │ done (blocked)│   persona only          │
│ └───────────────┘ └───────────────┘ └───────────────┘                         │
│ ┌ persona_4 ────┐ ┌ persona_5 ────┐ ┌ persona_6 ────┐                         │
│ │ …             │ │ …             │ │ …             │   row 2 (cols 1–3)      │
│ └───────────────┘ └───────────────┘ └───────────────┘                         │
└───────────────────────────────────────────────────────────────────────────────┘
┌─ Run history ─────────────────────────────────────────────────────────────────┐
│ run_3   72%   1 blocked   …                                                    │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| "▶ Run acceptance test" button | `handleStartRun` → `setTab("overview")`, reveals runner in overview | `handleStartRun` → `setTab("runs")`, reveals runner in runs tab | One-line change in `page.tsx` |
| Runner placement | `showRunner && tab === "overview"` block in page body | Rendered at top of `RunsTab`, above run history | Run history stays below |
| Live browser | single panel, latest frame of whichever persona streamed last | one frame per persona column | `frames` keyed by persona stem |
| Node outputs | one scrolling feed mixing all personas | one feed **per persona column** | filter `log` by `item.persona` |
| Run-scope nodes (`init…alerts`) | inside the right column | rendered once above the grid | shared, not per persona |
| Layout | `grid md:grid-cols-[300px_1fr]` | `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` | 3 across = 2×3 for 6 personas |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 (critical) | `frontend/components/AssessmentRunner.tsx` | 45-100 | `LiveState`, `NodeCardItem`, `push`, `reduce` — the state model to restructure |
| P0 (critical) | `frontend/components/AssessmentRunner.tsx` | 354-429 | `LiveView` — the component to rewrite into a per-persona grid |
| P0 (critical) | `frontend/components/AssessmentRunner.tsx` | 321-352 | `NodeOutputCard` — reused per column unchanged |
| P1 (important) | `frontend/lib/live.ts` | 114-143 | `StreamEvent` union — confirms every persona-scope/frame event carries `persona` |
| P1 (important) | `frontend/app/projects/[projectId]/page.tsx` | 53-57, 144-174, 393-437 | `handleStartRun`, runner placement, `RunsTab` to relocate into |
| P2 (reference) | `frontend/app/globals.css` | 7-39, 60-72 | Design tokens (`bg-card`, `bg-anchor`, `section-label`, `--radius-card`) |

## External Documentation
No external research needed — feature uses established internal patterns (React `useState`/`useRef`,
Tailwind v4 `@theme` tokens, existing SSE reducer). The "Playwright frame" is the existing CDP
screencast: backend emits `{ type: "frame", persona, data }` base64-JPEG events (`live.ts:140`).

---

## Patterns to Mirror

### NAMING_CONVENTION
```ts
// SOURCE: AssessmentRunner.tsx:47-67
interface NodeCardItem {
  id: number;
  scope: "run" | "persona";
  node: string;
  persona?: string;
  status?: string;
  output?: Record<string, unknown>;
  screenshot_url?: string | null;
}
interface LiveState {
  runNodes: string[];
  log: NodeCardItem[];
  frame?: { persona: string; data: string };
  n: number;
}
function push(s: LiveState, item: Omit<NodeCardItem, "id">): LiveState {
  return { ...s, n: s.n + 1, log: [...s.log, { id: s.n, ...item }] };
}
```

### REDUCER_PATTERN (pure, immutable, switch-on-`e.type`)
```ts
// SOURCE: AssessmentRunner.tsx:69-100
function reduce(s: LiveState, e: StreamEvent): LiveState {
  if (e.type === "frame") {
    return { ...s, frame: { persona: e.persona, data: e.data } };   // ← collapses to one frame today
  }
  if (e.type === "node" && e.scope === "persona") {
    return push(s, { scope: "persona", node: e.node, persona: e.persona,
      output: e.output, screenshot_url: e.screenshot_url ?? undefined });
  }
  // … step / persona_start / persona_done all carry e.persona
  return s;
}
```

### COMPONENT/GRID_PATTERN (responsive Tailwind grid + card)
```tsx
// SOURCE: AssessmentRunner.tsx:354-386 (two-col live view) and :456 (sm:grid-cols-3 verdicts)
<div className="grid gap-6 md:grid-cols-[300px_1fr]"> … </div>
<div className="grid gap-3 sm:grid-cols-3"> … </div>          // 3-across pattern already used
<div className="overflow-hidden rounded-[28px] border-4 border-anchor bg-anchor"> // live-browser frame
  <img src={`data:image/jpeg;base64,${live.frame.data}`} … className="block w-full" />
</div>
```

### AUTOSCROLL_PATTERN (per-feed ref + effect on length)
```tsx
// SOURCE: AssessmentRunner.tsx:356-359
const feedRef = useRef<HTMLDivElement | null>(null);
useEffect(() => { feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight }); }, [live.log.length]);
```

### CARD/SECTION_LABEL_PATTERN
```tsx
// SOURCE: AssessmentRunner.tsx:366, page.tsx:393-396
<h2 className="section-label mb-2">Live browser</h2>
<h2 className="section-label">Run history</h2>
```

### TAB_RELOCATION_PATTERN
```tsx
// SOURCE: page.tsx:53-57, 145-159, 173
function handleStartRun() { setShowRunner(true); setTab("overview"); }  // ← change to "runs"
{showRunner && tab === "overview" && ( … <AssessmentRunner … /> … )}   // ← move into RunsTab
{tab === "runs" && <RunsTab runs={runs} projectId={projectId} />}
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `frontend/components/AssessmentRunner.tsx` | UPDATE | Restructure `LiveState`/`reduce`/`LiveView` into per-persona frames + per-persona feeds in a 2×3 grid |
| `frontend/app/projects/[projectId]/page.tsx` | UPDATE | Relocate `AssessmentRunner` from overview tab into `RunsTab` (above run history); point `handleStartRun` at the runs tab |

## NOT Building
- No backend changes — the SSE contract already carries `persona` on every frame/step/node event.
- No change to `Results` / friction matrix / empathy replay (the post-run pack view) — only the **live** view.
- No new persona-selection UX — the existing chip selector and ≥3 rule (`canRun`, line 129) stay as-is.
- No hard cap forcing exactly 6 personas — grid is responsive; 3 personas → one row, 6 → two rows, >6 → more rows (still 3 cols). The "2×3" is the natural result of 6 selected personas, not an enforced limit.
- No persisted/replayable per-persona live history — live state is still ephemeral and cleared on `final`.
- No drag/reorder of columns; column order follows `selected` order.

---

## Step-by-Step Tasks

### Task 1: Restructure `LiveState` to hold per-persona frames
- **ACTION**: In `AssessmentRunner.tsx`, change the single `frame?` field into a per-persona map.
- **IMPLEMENT**: Replace `frame?: { persona: string; data: string };` with
  `frames: Record<string, string>;  // persona stem → latest base64 JPEG`.
  Initialize in `run()` (line 135): `setLive({ runNodes: [], log: [], frames: {}, n: 1 });`.
- **MIRROR**: NAMING_CONVENTION (LiveState shape).
- **IMPORTS**: none new.
- **GOTCHA**: Keep `log` flat (still `NodeCardItem[]`) — grouping happens at render time, not in state. This keeps `push`/`reduce` minimal and preserves global ordering/ids.
- **VALIDATE**: `npx tsc --noEmit` from `frontend/` shows no new errors after Task 2.

### Task 2: Update `reduce()` to store frames by persona
- **ACTION**: Change the `frame` branch (lines 70-72) to write into `frames[e.persona]`.
- **IMPLEMENT**:
  ```ts
  if (e.type === "frame") {
    return { ...s, frames: { ...s.frames, [e.persona]: e.data } };
  }
  ```
  Leave every other branch unchanged — persona-scope `node`/`step`/`persona_start`/`persona_done`
  already set `persona`, and run-scope `node` already sets `scope: "run"`.
- **MIRROR**: REDUCER_PATTERN.
- **GOTCHA**: Do not delete the run-scope branch — `init…alerts` cards still flow into `log` with
  `scope:"run"` and are filtered out of persona columns in Task 3.
- **VALIDATE**: type-check passes; manually confirm `frames` accumulates one key per streaming persona.

### Task 3: Rewrite `LiveView` into a shared pipeline bar + per-persona grid
- **ACTION**: Replace the body of `LiveView` (lines 354-429) with: (a) the run pipeline bar rendered
  once, then (b) a responsive grid of `PersonaColumn` cells — one per persona present in the run.
- **IMPLEMENT**:
  - Derive the persona list in stream order:
    ```ts
    const personas: string[] = [];
    for (const item of live.log) {
      if (item.scope === "persona" && item.persona && !personas.includes(item.persona)) {
        personas.push(item.persona);
      }
    }
    for (const p of Object.keys(live.frames)) if (!personas.includes(p)) personas.push(p);
    ```
  - Keep the existing run-pipeline bar block (lines 389-414) as a single shared row above the grid,
    wrapped in `<h2 className="section-label mb-2">Graph nodes</h2>`.
  - Render the grid:
    ```tsx
    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
      {personas.map((p) => (
        <PersonaColumn
          key={p}
          persona={p}
          frame={live.frames[p]}
          items={live.log.filter((it) => it.scope === "persona" && it.persona === p)}
        />
      ))}
    </div>
    ```
- **MIRROR**: COMPONENT/GRID_PATTERN (`lg:grid-cols-3`), CARD/SECTION_LABEL_PATTERN.
- **GOTCHA**: Remove the now-unused single-frame markup (lines 366-386) and the outer
  `md:grid-cols-[300px_1fr]` wrapper. The per-feed autoscroll ref must move into `PersonaColumn`
  (one ref per column) — a single shared ref would only scroll the last column.
- **VALIDATE**: type-check passes; with 6 personas selected the live view shows a 3-wide, 2-tall grid.

### Task 4: Add the `PersonaColumn` component
- **ACTION**: Add a new function component below `LiveView` rendering one persona's frame + feed.
- **IMPLEMENT**:
  ```tsx
  function PersonaColumn({ persona, frame, items }:
    { persona: string; frame?: string; items: NodeCardItem[] }) {
    const feedRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => {
      feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
    }, [items.length]);
    return (
      <div className="rounded-card bg-card p-3">
        <h3 className="section-label mb-2">{persona}</h3>
        <div className="overflow-hidden rounded-[20px] border-4 border-anchor bg-anchor">
          {frame ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`data:image/jpeg;base64,${frame}`} alt={`${persona} live browser`} className="block w-full" />
          ) : (
            <div className="flex h-[320px] items-center justify-center text-[12px] text-on-dark-dim">
              launching browser…
            </div>
          )}
        </div>
        <div ref={feedRef} className="mt-3 max-h-[360px] space-y-2 overflow-y-auto pr-1">
          {items.length === 0
            ? <p className="text-[12px] text-tertiary">waiting for nodes…</p>
            : items.map((it) => <NodeOutputCard key={it.id} item={it} />)}
        </div>
      </div>
    );
  }
  ```
- **MIRROR**: AUTOSCROLL_PATTERN, the live-browser frame markup, and `NodeOutputCard` reuse.
- **IMPORTS**: `NodeOutputCard` and `NodeCardItem` are already in-file; `useEffect`/`useRef` already imported (line 3).
- **GOTCHA**: `NodeOutputCard` title already shows `${persona} · ${node}` (line 322) — that's fine and harmless inside a per-persona column; leave it for continuity, or pass a flag later if redundancy bothers. Keep `mediaUrl`/`STATUS_DOT` usage unchanged.
- **VALIDATE**: each column scrolls independently; no persona's card appears in another's feed.

### Task 5: Relocate `AssessmentRunner` into the Runs tab
- **ACTION**: In `page.tsx`, move the runner out of the overview-gated block (lines 145-159) and into
  `RunsTab`, rendered above the run-history list.
- **IMPLEMENT**:
  - Change `handleStartRun` (line 54-57): `setTab("runs")` instead of `setTab("overview")`.
  - Delete the `{showRunner && tab === "overview" && (…)}` block (lines 145-159).
  - Pass `showRunner` / `onHideRunner` / `appName` into `RunsTab`:
    `{tab === "runs" && <RunsTab runs={runs} projectId={projectId} showRunner={showRunner} onHide={() => setShowRunner(false)} appName={project.name} />}`
  - In `RunsTab`, before the `<h2 className="section-label">Run history</h2>` block, render:
    ```tsx
    {showRunner && (
      <div className="mb-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="section-label">Acceptance test — live agent run</h2>
          <button type="button" onClick={onHide} className="text-[12px] text-secondary hover:text-primary">Hide</button>
        </div>
        <AssessmentRunner defaultAppName={appName} />
      </div>
    )}
    ```
  - Extend `RunsTab`'s prop type accordingly:
    `{ runs: RunSummary[]; projectId: string; showRunner: boolean; onHide: () => void; appName: string }`.
- **MIRROR**: TAB_RELOCATION_PATTERN; the exact runner header markup already at lines 146-158.
- **IMPORTS**: `AssessmentRunner` is already imported (page.tsx:19) — keep it.
- **GOTCHA**: After moving, remove any now-unused references in the overview body. `OverviewTab` keeps
  its `RunLog`/`PersonaWall`/`FrictionMatrix` (those render the persisted latest run, unrelated to the live runner).
- **VALIDATE**: clicking "▶ Run acceptance test" switches to the **runs** tab and shows the live runner above run history; overview tab no longer renders the runner.

---

## Testing Strategy

### Unit / Type Tests
There is no React test harness in `frontend/` today (no `*.test.tsx`); validation is type-check + manual.

| Check | Input | Expected | Edge Case? |
|---|---|---|---|
| `reduce` frame keying | two `frame` events, personas `a` then `b` | `frames = { a, b }`, both retained | No |
| `reduce` frame update | two `frame` events, same persona `a` | `frames.a` = latest data only | Yes (overwrite) |
| persona derivation | log with `run`+`persona` items | run-scope excluded; persona order preserved | Yes |
| column filter | log mixing personas `a`,`b` | column `a` shows only `a` items | Yes (no mixing) |

### Edge Cases Checklist
- [ ] 3 personas selected → single row of 3 columns (no empty cells).
- [ ] 6 personas → exact 2×3 grid.
- [ ] >6 personas → 3 columns, 3+ rows (responsive, not clipped).
- [ ] A persona that streams nodes but no frame yet → "launching browser…" placeholder.
- [ ] A persona with a frame but no nodes yet → "waiting for nodes…" placeholder.
- [ ] `final` event clears `live` → grid unmounts, `Results` renders (unchanged path).
- [ ] Narrow viewport → `grid-cols-1` / `sm:grid-cols-2` stack gracefully.

---

## Validation Commands

### Static Analysis
```bash
cd frontend && npx tsc --noEmit
```
EXPECT: Zero type errors.

### Lint
```bash
cd frontend && npm run lint
```
EXPECT: No new errors (keep the existing `eslint-disable @next/next/no-img-element` comments on `<img>`).

### Build
```bash
cd frontend && npm run build
```
EXPECT: Compiles successfully.

### Browser Validation
```bash
# backend (separate shell): from backend/  → uv run uvicorn app.main:app --reload
cd frontend && npm run dev    # http://localhost:3000
```
- [ ] Open a project → click "▶ Run acceptance test" → lands on **Runs** tab.
- [ ] Select 6 personas → Run → 2×3 grid, each column has its own browser frame.
- [ ] Confirm no persona's node card appears in another column's feed.
- [ ] Confirm `init→aggregate→score→evidence→alerts` bar renders once, above the grid.
- [ ] Run history list still renders below the runner.

---

## Acceptance Criteria
- [ ] `AssessmentRunner` renders in the **runs** tab, above run history; not in overview.
- [ ] Live view is a responsive 3-column grid (2×3 for 6 personas), one persona per cell.
- [ ] Each cell shows that persona's own live browser frame.
- [ ] Each cell shows that persona's own node-reasoning feed — no cross-persona mixing.
- [ ] Run-scope pipeline nodes render once, shared above the grid.
- [ ] `npx tsc --noEmit`, lint, and build all pass.

## Completion Checklist
- [ ] Code follows discovered patterns (reducer purity, Tailwind tokens, section-label headers).
- [ ] Per-column autoscroll ref (not a single shared ref).
- [ ] No backend/SSE-contract changes.
- [ ] `Results`/empathy-replay path untouched.
- [ ] No unused imports/markup left after relocation.
- [ ] Self-contained — no further codebase searching needed.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| In sequential mode only one persona streams frames at a time → other columns sit on placeholder | High | Low | Expected behavior; placeholders ("launching browser…") communicate state. Parallel mode fills columns concurrently. |
| Six concurrent base64-JPEG `<img>` updates strain the browser | Low | Low | Frames are small JPEGs already used today; only the *latest* per persona is kept (no buffer growth). |
| Single shared autoscroll ref accidentally retained | Med | Med | Task 4 moves the ref into `PersonaColumn`; called out in Task 3 GOTCHA. |
| Relocation leaves dead overview markup / type drift on `RunsTab` props | Med | Low | Task 5 enumerates exact deletions and the new prop type. |

## Notes
- The "Playwright frame" in the request is the existing CDP screencast: backend emits
  `{ type: "frame", persona, data }` base64-JPEG events (`live.ts:140`). No new capture mechanism needed —
  the fix is purely *keying frames by persona* instead of collapsing to one.
- The 2×3 shape is emergent: 3 fixed columns (`lg:grid-cols-3`) × the user's typical 6 personas = 2 rows.
  The implementation stays correct for any persona count ≥3 (the existing `canRun` minimum).
- Branch note: this targets the `feat/dashboard` project-detail page (tabs + `RunsTab`). The
  `AssessmentRunner` itself is identical on `main`. Implement on the branch where the tabbed project page lives.

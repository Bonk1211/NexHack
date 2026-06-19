# InclusionScope — Frontend Plan + Backend Endpoint Contracts

Stack: Next.js 15 (App Router) + TypeScript + Tailwind (custom tokens) + Geist + Instrument Serif.
Data: fetch from FastAPI; build against typed mock adapters first so the frontend stands alone.

---

## Route map

```
/                         Home — all projects (grid of project cards) + "New project"
/projects/[projectId]     Project detail — tabs: Overview | Personas | Runs
                            Overview = latest run summary (score, persona wall, friction matrix)
                            Personas = personas linked to this project's repos + link/unlink
                            Runs     = run history list
/projects/[projectId]/runs/[runId]   Run detail — full report (score, persona wall, friction matrix)
/projects/[projectId]/runs/[runId]/live   LIVE run — SSE, per-persona lanes, the money-shot
/personas                 Global persona library — grid + "New persona" (with figurine gen)
/personas/[personaId]     Persona detail/edit — attributes, behavior sliders, figurine
```

Navigation: persistent left sidebar (dark anchor) with: InclusionScope wordmark, Home,
Personas. Project context shows as breadcrumb in the top bar.

---

## Backend endpoint contracts (frontend codes against these)

All JSON. Base `/api`. Frontend uses a typed client; mock implementation returns fixtures
until FastAPI is live.

### Projects
```
GET    /api/projects                  -> Project[]
POST   /api/projects                  {name, description?} -> Project
GET    /api/projects/:id              -> ProjectDetail (incl. repos[], latestRun?)
DELETE /api/projects/:id              -> {ok}
```

### Repos (a project has repos; repo holds the staging URL + linked personas)
```
POST   /api/projects/:id/repos        {name, stagingUrl, viewport} -> Repo
GET    /api/repos/:repoId             -> Repo (incl. personas[])
DELETE /api/repos/:repoId             -> {ok}
POST   /api/repos/:repoId/personas    {personaId} -> {ok}        # link
DELETE /api/repos/:repoId/personas/:personaId -> {ok}            # unlink
```

### Personas (global library)
```
GET    /api/personas                  -> Persona[]
POST   /api/personas                  {name, label, ageBand, techSavviness, patience,
                                        language, disabilities[], behaviorProfile} -> Persona
GET    /api/personas/:id              -> Persona
PATCH  /api/personas/:id              {partial} -> Persona
DELETE /api/personas/:id              -> {ok}
POST   /api/personas/:id/figurine     {} -> {status:"generating"}   # async trigger
GET    /api/personas/:id/figurine     -> {status, url?}             # poll
```

### Runs
```
POST   /api/repos/:repoId/runs        {mode:"sequential"|"parallel"} -> {runId}
GET    /api/projects/:id/runs         -> RunSummary[]
GET    /api/runs/:runId               -> RunDetail (overallScore, personaResults[],
                                         frictionMatrix)
GET    /api/runs/:runId/stream        -> SSE  (text/event-stream)   # live events
```

### SSE event shapes (GET /api/runs/:runId/stream)
```
event: persona_step
data: {personaId, stepIdx, stepName, status:"ok"|"friction"|"blocked", dwellMs, screenshotUrl?}

event: persona_done
data: {personaId, confusionScore, completed:bool, blockedAt?}

event: run_done
data: {overallScore}
```

---

## Core TypeScript types

```ts
type Severity = "ok" | "friction" | "blocked";
type RunStatus = "pending" | "running" | "completed" | "failed";

interface Project {
  id: string; name: string; description?: string;
  personaCount: number; latestScore?: number; lastRunAt?: string;
}
interface Persona {
  id: string; name: string; label: string;     // label = "OKU — visual (low-vision)"
  ageBand: string; techSavviness: number;        // 0..1
  patience: number; language: string;
  disabilities: string[];
  behaviorProfile: { dwellMultiplier:number; hesitationProb:number;
                     readingSpeedWpm:number; giveupThresholdS:number; retryLimit:number };
  figurineUrl?: string; figurineStatus: "none"|"generating"|"ready"|"failed";
}
interface PersonaResult {
  personaId: string; persona: Persona;
  confusionScore: number; status: Severity;     // worst step status
  blockedAt?: string; completed: boolean;
  steps: { stepName:string; status:Severity; dwellMs:number }[];
}
interface RunDetail {
  id: string; projectId: string; mode:string; status: RunStatus;
  overallScore: number; personaResults: PersonaResult[];
  frictionMatrix: { steps: string[]; rows: { personaId:string; cells:
    { stepName:string; status:Severity; dwellMs:number|null }[] }[] };
}
```

---

## Page-by-page spec

### `/` Home — Projects
- Dark hero strip: wordmark + one-line product promise + "New project" primary button.
- Grid of ProjectCards (3-col): project name (serif), persona count, latest score ring (small),
  last-run relative time, a sparkline-free clean layout.
- Empty state: a single centered card prompting first project (designed, not a bare message).
- "New project" opens a modal/slide-over: name, description, then first repo (staging URL + viewport).

### `/projects/[id]` Project detail
- Top bar: breadcrumb (Home / ProjectName), project actions (Run acceptance test → mode toggle).
- Tabs: **Overview · Personas · Runs**.
- **Overview**: the latest RunDetail rendered — hero score band, persona wall, friction matrix
  (this is the screen you already have, now as one tab).
- **Personas**: personas linked to this project; "Add from library" (multi-select modal) +
  unlink. Cards reuse the global PersonaCard.
- **Runs**: table/list of past runs (date, mode, score, blocked count) → click to run detail;
  a prominent "▶ Run acceptance test" that, when started, routes to the live view.

### `/projects/[id]/runs/[runId]` Run detail
- Static report version of Overview for a specific historical run.

### `/projects/[id]/runs/[runId]/live` LIVE run (the money-shot)
- Per-persona **lanes** (one row each), led by the persona figurine (circular).
- Each lane shows the flow steps as a horizontal progress track; the current step pulses;
  steps fill ok(green dot)/friction(amber)/blocked(red) as SSE events arrive.
- The blocked persona's lane visibly **halts** at its step with a red marker — the
  "auntie-figurine-getting-blocked" moment. Confusion score ticks up live per lane.
- Top: overall score assembling in real time. On run_done, CTA → run detail report.

### `/personas` Persona library
- Grid of PersonaCards (figurine, name, label, behavior summary chips).
- "New persona" → creation flow (below).
- Click card → `/personas/[id]` detail/edit.

### `/personas/[id]` + New persona flow
- Form: name, label, age band (select), language, disabilities (multi-select chips),
  behavior sliders (tech-savviness, patience, dwell multiplier, hesitation, give-up threshold).
- **Figurine panel**: "Generate figurine" button → calls POST figurine → shows generating
  state (skeleton shimmer) → polls GET → swaps in image. Failure → friendly retry. Never
  blocks saving the persona.
- Live preview of how this persona "behaves" (a small descriptive sentence derived from sliders).

---

## Design system (baked in from line one — see one-shot prompt for exact values)

- Fonts: Instrument Serif (display: page titles, score numbers) + Geist (everything else).
- Dark anchor (#161617) for sidebar + hero bands; light field (#f5f5f7) for content; white cards.
- One accent for interactive (blue #0066cc); semantic accents desaturated
  (ok #1d8a4e, friction #b25e00, blocked #c8362f) used as dots/bars/tints only — never big fills.
- Blocked items always carry more visual weight than passing ones.
- 2.5% SVG grain overlay on the light field. Soft large shadows, hairline borders, 16–20px radii.
- Motion: 200–300ms ease-out, fade+translate-up; respect prefers-reduced-motion.
- Reference voice: Linear (primary), Vercel/Geist (type warmth).

---

## Build order (frontend, mock-first)

1. Design tokens + fonts + sidebar shell + grain overlay.
2. Typed mock API client + fixtures (2 projects, 8 personas, 1 completed run, 1 live script).
3. `/` projects grid + new-project flow.
4. `/personas` library + creation flow + figurine panel (mock async).
5. `/projects/[id]` Overview (port existing score/wall/matrix) + Personas tab + Runs tab.
6. Run detail page.
7. Live run view driven by a mock SSE emitter (replayable script) — perfect for demo safety.
8. Swap mock client for real FastAPI base URL.

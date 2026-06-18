BUILD: InclusionScope — a multi-page Next.js 15 frontend for an AI accessibility/navigability
auditor. Build the ENTIRE app described below in one pass. Use mock data (typed mock API client +
fixtures) so it runs standalone; structure the client so swapping to a real FastAPI base URL later
is a one-line change. This REPLACES any existing frontend.

╔══════════════════════════════════════════════════════════════╗
║ DESIGN LANGUAGE — match the FEELING of Linear (linear.app).   ║
║ Calm, opinionated, data-dense but restrained. Typographic     ║
║ warmth from Vercel/Geist + a serif display. NOT generic SaaS. ║
╚══════════════════════════════════════════════════════════════╝

── FONTS (do this first, it matters most) ──
- Display (page titles + big score numbers ONLY): "Instrument Serif" via next/font/google,
  weight 400, expose as --font-display.
- UI/body (everything else): Geist via the `geist` package, expose as --font-sans.
- Wire both into tailwind theme.fontFamily as `display` and `sans`. Never use system-ui/Inter.

── COLOR TOKENS (put in a tokens file / tailwind config; do NOT use raw Tailwind default palette) ──
  bg.field    #f5f5f7   (light page)
  bg.card     #ffffff
  bg.anchor   #161617   (dark: sidebar + hero bands)
  text.primary   #1d1d1f      text.secondary #6e6e73      text.tertiary #8e8e93
  text.onDark    #f5f5f7      text.onDarkDim #a1a1a6
  accent.brand   #0066cc   (interactive/links/primary buttons ONLY)
  sem.ok       #1d8a4e     sem.friction #b25e00     sem.blocked #c8362f
  tint.blocked #fdf3f2     tint.friction #fbf6ef
  hairline     rgba(0,0,0,0.06)
Semantic colors appear ONLY as small dots, 3px accent bars, text, or ~8% tints — never as large
saturated fills. Exactly one accent visible per region.

── GLOBAL CHROME ──
- Persistent LEFT SIDEBAR, bg.anchor, ~240px: "InclusionScope" wordmark (display serif, onDark),
  nav links (Home, Personas) with subtle active state, version tag at bottom in tertiary.
- Top bar in content area: breadcrumb + contextual actions.
- Light content field with a FIXED full-viewport SVG grain overlay (feTurbulence data-URI,
  ~2.5% opacity, pointer-events:none, behind content). Kills the flat default look.
- Cards: white, radius 16–20px, hairline border + soft large shadow
  (0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.04)). Section labels: Geist 12px, weight 600,
  letter-spacing .08em, UPPERCASE, text.tertiary.
- Motion: 200–300ms ease-out, content fades + translates up 6–8px on mount, staggered 30ms.
  Honor prefers-reduced-motion (disable transforms). NO animated/WebGL backgrounds anywhere.

── TYPED MOCK API CLIENT ──
Create lib/api.ts with functions matching these endpoints, returning typed fixtures with realistic
latency (setTimeout 200–500ms). One BASE_URL constant; mock now, real FastAPI later.
  Projects:  GET /projects, POST /projects, GET /projects/:id, DELETE /projects/:id
  Repos:     POST /projects/:id/repos, GET /repos/:id, link/unlink personas
  Personas:  GET/POST /personas, GET/PATCH/DELETE /personas/:id,
             POST /personas/:id/figurine (async), GET /personas/:id/figurine (poll)
  Runs:      POST /repos/:id/runs, GET /projects/:id/runs, GET /runs/:id,
             GET /runs/:id/stream (SSE — mock with a replayable event emitter)
Types: Project, Persona (with behaviorProfile + figurineStatus), PersonaResult,
RunDetail (with frictionMatrix {steps[], rows[{personaId, cells[{stepName,status,dwellMs}]}]}).
Severity = "ok"|"friction"|"blocked".

── PAGES / ROUTES ──

[ / ] HOME — Projects
- Dark hero strip (bg.anchor): wordmark eyebrow, serif headline "Audit every user. Before they
  leave.", one-line subtitle in onDarkDim, primary "New project" button (accent.brand).
- 3-col grid of ProjectCards: name (serif 20px), "{n} personas", small score ring, last-run
  relative time. Hover: lift + translate-up 2px.
- New project = slide-over: name, description, then first repo (staging URL + viewport select).
- Designed empty state when no projects.

[ /personas ] PERSONA LIBRARY
- 3–4 col grid of PersonaCards: circular figurine (48px) top-left OR skeleton shimmer if
  figurineStatus!=="ready"; name (serif 17px) + label (tertiary); small behavior chips
  (e.g. "low patience", "screen reader"). "New persona" primary button.
- Click card → /personas/:id.

[ /personas/:id ] PERSONA DETAIL / NEW
- Two-column: left = form (name, label, age band select, language, disabilities multi-chip,
  sliders: techSavviness, patience, dwellMultiplier, hesitationProb, giveupThresholdS).
- Right = FIGURINE PANEL: preview area; "Generate figurine" (calls POST figurine → shimmer →
  poll GET → swap image). On failure show friendly retry, never crash, never block Save.
- Below sliders: a live one-sentence "behavior preview" derived from slider values.

[ /projects/:id ] PROJECT DETAIL — tabs: Overview · Personas · Runs
- Top bar: breadcrumb (Home / {project}); right side: "▶ Run acceptance test" with a
  sequential/parallel toggle. Starting a run routes to the live view.
- OVERVIEW tab = latest run report:
    • HERO SCORE BAND (dark, bg.anchor, radius 20, padding 40): eyebrow "INCLUSIONSCOPE",
      title = "{project} (staging)" in serif onDark, "{n} personas", a one-line finding with the
      at-risk personas highlighted in soft red #ff6b60. Right: score ring (track #2c2c2e,
      progress amber #d97a2b, number in serif onDark, "SCORE" tertiary uppercase).
    • PERSONA WALL: 4-col cards. Card states — passing: white, no bar; friction: white + 3px
      left bar sem.friction; blocked: bg tint.blocked + 3px left bar sem.blocked. ORDER blocked
      first, then friction, then passing. Status dot top-right; bottom status text (blocked text
      in sem.blocked weight 500). "{x}/{n} blocked" counter in the section header.
    • FRICTION MATRIX as a RESTRAINED HEATMAP (not colored pills): rows=personas, cols=flow steps
      (Sign in, OTP verify, ID upload, Details form, Confirm). Each cell = dwell time value
      (Geist, tabular-nums, right-aligned) on an ~8% severity tint (ok faint green, friction faint
      amber, blocked faint red); blocked cell shows "blocked" in sem.blocked, not a grey dash.
      Hairline row dividers only, no cell borders. Column headers tertiary uppercase 12px.
- PERSONAS tab: personas linked to this project + "Add from library" multi-select modal + unlink.
- RUNS tab: list of past runs (relative date, mode, score, blocked count) → /projects/:id/runs/:runId.

[ /projects/:id/runs/:runId ] RUN DETAIL — static version of the Overview report for that run.

[ /projects/:id/runs/:runId/live ] LIVE RUN — THE MONEY-SHOT
- Subscribe to GET /runs/:id/stream (mock SSE emitter replaying a scripted run; make it
  deterministic and ~20–30s so it's demo-safe).
- One LANE per persona (stacked rows). Each lane: figurine (circular, left) + name, then a
  horizontal STEP TRACK of the flow steps. As persona_step events arrive, fill each step
  ok/friction/blocked; the active step pulses softly.
- The blocked persona's lane HALTS at its failing step with a red marker and a short
  "Blocked at {step}" label — this is the dramatic moment; let it sit visually heavier (the
  tint.blocked lane background). Per-lane confusion score ticks upward live.
- Header: overall score assembling in real time. On run_done: success toast + CTA "View report"
  → run detail.
- Honor reduced-motion (pulse becomes a static highlight).

── ACCEPTANCE CRITERIA ──
1. Squint test: dark sidebar + dark hero anchors, calm light field, blocked items instantly
   identifiable as the red-tinted ones.
2. Exactly one serif (titles + score numbers); everything else Geist; no Inter/system-ui.
3. No saturated fills except small dots / 3px bars / faint tints.
4. Live run is deterministic, replayable, ~20–30s, and clearly shows one persona getting blocked.
5. Everything runs on mock data with zero backend; api.ts is the single swap point.
6. prefers-reduced-motion fully respected.

Build all routes, components, the mock client, and fixtures now.

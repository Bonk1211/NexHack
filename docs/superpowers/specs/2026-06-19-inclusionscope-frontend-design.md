# InclusionScope Frontend — Design Spec

**Date:** 2026-06-19
**Scope:** Demo dashboard frontend (persona wall + friction matrix + evidence pack + empathy replay).
**Source of truth:** PRD `docs/prd/PRD_InclusionScope_v2_Merged.md` (§13, §14, §16, §20).

## Goal

Build the InclusionScope demo surface in the existing Next.js 15 app: an Apple-minimalist,
light-themed single-page dashboard that tells the §20 demo story top-to-bottom — persona wall →
friction matrix → evidence pack → empathy replay. The UI renders entirely from a committed mock
fixture shaped exactly like the backend `build_pack()` output (§13), so it runs with no backend.

This pass is the presentation layer (~20 marks, §24). It must not invert build priority — it is
polish over an engine that is built separately. It exists to make the exclusion *visible* and the
evidence *legible*.

## Non-goals

- No real backend wiring (`/runs` routes are stubs that raise `NotImplementedError`).
- No real per-step screenshots (nav agent not built) — replay uses CSS-rendered fake app screens.
- No multi-language run, no trend-over-releases view (both PRD stretch).
- No auth, no multi-app CRUD console (explicitly cut, §6, §21).

## Decisions (locked)

| Decision | Choice | Reason |
|---|---|---|
| Theme | Light, Apple-minimalist | Compliance/audit tool must read as trustworthy; Apple default is light |
| Styling | Tailwind CSS + design tokens | Fast, consistent spacing/typography scale |
| Data | Committed mock JSON fixture (build_pack shape) | Backend is stub; fixture swaps to real fetch in one place later |
| Structure | Single dashboard page + replay modal | One-scroll demo narrative; fewer demo clicks |
| Replay frames | CSS-rendered fake app screens + live CSS filters | No asset sourcing; filters genuinely demonstrate exclusion |
| Surfaces | Wall + matrix + evidence pack + replay (all four) | User selected all |

## Design tokens (Apple light)

- Background `#F5F5F7`; card surface `#FFFFFF`; hairline border `#D2D2D7`.
- Text primary `#1D1D1F`; secondary `#6E6E73`.
- Accent (system blue) `#0071E3`.
- Status: green `#34C759`, amber `#FF9F0A`, red `#FF3B30`.
- Font stack: `-apple-system, "SF Pro Text", system-ui, sans-serif`.
- Radii 12–16px; soft shadows (`0 1px 3px rgba(0,0,0,.08)`); generous whitespace.

## Page layout (top → bottom = §20 narrative)

1. **Header** — app name, run timestamp, inclusion-score ring (0–1).
2. **Persona wall (§14)** — grid of persona cards. Each: display name, status
   (idle/running/completed/blocked), severity badge (P0–P3), blocked-at step. Card click opens the
   replay modal for that persona.
3. **Friction matrix (§14, FR-3.3)** — persona rows × step columns. Each cell colored
   green/amber/red from `matrix.rows[persona][step].status`, showing dwell seconds. The hero diff:
   `control` row green where a protected persona's row is red. Cell click opens replay at that step.
4. **Evidence pack (§13)** — three visually distinct blocks enforcing two-stream discipline (§16):
   - **WCAG findings (TRUSTED)** — per-criterion pass/fail from `wcag_conformance`, with owner tag.
     Visually marked as the trusted, machine-verifiable stream.
   - **Persona verdicts (INDICATIVE)** — per-persona verdict + severity, explicitly labeled
     "indicative". Never blended into the trusted block.
   - **Remediation** — severity-sorted list, each routed to an owner (@frontend/@content/...).
     Mock "Export PDF" / "Export JSON" buttons (download the fixture JSON; PDF stubbed).
5. **Empathy replay modal (§14)** — opens over the dashboard. Renders a CSS-built fake app screen
   for the selected step. A persona "lens" applies a live CSS filter conveying that persona's
   experience:
   - low-vision: blur + reduced contrast
   - colorblind: hue/saturation matrix
   - motor: enlarged tap-target overlay boxes
   - elderly/low-literacy: dim + slowed step transitions
   - control: no filter (the baseline contrast)
   Includes a step scrubber and a caption: "This is what {persona} sees."

## Component tree

```
frontend/
  app/page.tsx                  dashboard composition (client component)
  app/layout.tsx                metadata + globals (existing, light theme update)
  app/globals.css               token layer + Tailwind directives
  components/
    ScoreRing.tsx               inclusion score gauge
    PersonaWall.tsx             grid container
    PersonaCard.tsx             one persona panel
    FrictionMatrix.tsx          persona × step grid
    EvidencePack.tsx            container for the three blocks
    WcagFindings.tsx            TRUSTED block
    PersonaVerdicts.tsx         INDICATIVE block
    Remediation.tsx             routed, severity-sorted list
    EmpathyReplay.tsx           modal + lens filter + scrubber
    FakeScreen.tsx              CSS-rendered app screens
    StatusBadge.tsx             severity / status pill (shared)
  lib/
    types.ts                    TS types mirroring backend dataclasses (§16, §13)
    fixtures.ts                 mock evidence pack + UI metadata
    personas.ts                 display names + lens config per persona
    screens.ts                  fake-screen step definitions
  tailwind.config.ts
  postcss.config.mjs
```

## Data contract (fixture shape — mirrors `build_pack()`)

```ts
type EvidencePack = {
  app: string;
  run_at: string;                              // ISO-8601
  inclusion_score: number;                     // 0..1, derived (§16)
  wcag_conformance: Record<string, "pass" | "fail">;   // TRUSTED (§16)
  matrix: {
    steps: string[];
    rows: Record<string, Record<string, { status: "green"|"amber"|"red"|"na"; dwell_s: number|null }>>;
  };
  personas: {
    persona: string;
    verdict: "completed" | "blocked";          // INDICATIVE
    severity: "P0"|"P1"|"P2"|"P3"|null;
    blocked_at: string|null;
    wcag_failures: string[];
    behavioral_note: string;                   // labeled indicative
    inclusion_score: number;
  }[];
  remediation: { criterion: string; issue: string; owner: string; severity: string }[];
};
```

UI-only metadata (display names, step labels, persona→lens map, fake-screen definitions) lives in
separate fixtures so the `EvidencePack` type stays a faithful mirror of the backend. Swapping mock →
real is replacing the `fixtures.ts` import with a `fetch('/runs/{id}')`.

The fixture is seeded to match the §20 demo: `control` completes clean; `oku_visual` is P0-blocked
at the OTP step (unlabeled field, `1.3.1`/`4.1.2` fail); contrast `1.4.3` fails on a primary CTA.

## Two-stream discipline (§16) in the UI

The single hardest credibility requirement: the trusted WCAG stream must never be visually collapsed
into the indicative persona-simulation stream.
- `WcagFindings` (trusted) and `PersonaVerdicts` (indicative) are separate, labeled blocks.
- The inclusion-score ring is labeled "composite (derived)" with a tooltip noting the two underlying
  streams.
- Persona `behavioral_note` carries the "indicative" label inline.

## Testing

Light, demo-appropriate (matches PRD §22 stance — heavy TDD lives on the scorer, not UI):
- Type-check passes (`tsc --noEmit` via build).
- `lib/fixtures.ts` validates against the `EvidencePack` type at compile time.
- Manual: dashboard renders, persona card + matrix cell open replay, lens filters apply, export
  buttons download JSON. (Optional: one render smoke test if a test runner is added — not required
  this pass.)

## Risks

- **Replay reads as gimmick** — mitigate by making filters genuinely degrade legibility (real blur/
  contrast loss), captioned with the WCAG criterion that causes it, not decorative.
- **Polish-over-engine inversion (§21, §24)** — bounded by non-goals; this is the presentation pass
  only, fixtures stand in for the engine.

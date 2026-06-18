# InclusionScope

> Inclusion & Accessibility Assurance Agent — NexHack 2026 (Track 1, Compliance).

An autonomous agent that runs a consumer app through simulated **vulnerable-user
personas** (elderly, OKU/disabled, low-literacy, non-native, low-end device),
measures where each is blocked using **real accessibility signals**, and generates
**continuous compliance evidence**. Inclusion assurance as audit evidence — not a
scanner, not a chatbot.

Single source of truth: [`docs/prd/PRD_InclusionScope_v2_Merged.md`](docs/prd/PRD_InclusionScope_v2_Merged.md).

## Layout

```
backend/          FastAPI + AI glue (§15)
  app/scoring/    Scoring engine (§16) — PURE, seeded, unit-tested. The defensible IP.
  app/agents/     Persona nav (a11y-tree) + dual-signal capture (§8, §9, §10)   [stub]
  app/evidence/   Evidence pack builder (§13) — the primary output              [stub]
  app/routes/     Run orchestrator API (§8)                                     [stub]
  tests/          Scorer tests (§22) — the hardest-tested layer
frontend/         Next.js persona wall + empathy replay (§14)                   [stub]
personas/         Persona library (§7, §11) — behavior_profile + thresholds
supabase/         Postgres schema (§17)
fixture-site/     Planted-flaw demo target (§20, §22)
```

## Two-stream discipline (the credibility spine, §16)

The scorer emits three results and **never collapses the trusted stream into the
composite**:

1. **WCAG conformance** — TRUSTED (axe-core / a11y signals). A compliance officer
   can rely on this without trusting the simulation.
2. **Persona verdict** — INDICATIVE (completion + severity P0–P3, §12).
3. **Composite inclusion score** — OPTIONAL, DERIVED roll-up with visible weights.

## Build order (marks-ordered, §21)

1. Schema + scoring function ✅ (this scaffold)
2. a11y-tree nav loop + axe-core + screenshot every step  [stub]
3. Persona behavior models + per-persona thresholds ✅ (configs + scorer)
4. Dual-stream → friction matrix → evidence pack export  [stub]
5. Empathy replay + persona wall  [stub]
6. Live alert + owner routing on a P0 block  [stub]
7. Commercial one-pager + 7-min video

## Dev

```bash
# Backend
cd backend
uv venv && uv pip install -e '.[dev]'   # or: uv pip install -e . then add dev group
PYTHONPATH=. .venv/bin/pytest            # scorer tests (no external deps needed)
uv run uvicorn app.main:app --reload     # API on :8000

# Frontend
cd frontend && npm install && npm run dev # wall on :3000

# Fixture site (demo target)
python3 -m http.server 5500 --directory fixture-site
```

Copy `backend/.env.example` → `backend/.env`. Model family is an **open decision**
(§25) — kept configurable, not locked. WCAG target defaults to 2.2 AA.

## Explicitly NOT built (§21 cut list)

No collectible figurines / image pipeline, no project-management CRUD, no
Lighthouse-per-screen, no design-token lint gate. Effort follows the marks.

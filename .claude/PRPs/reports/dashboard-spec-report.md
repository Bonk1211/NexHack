# Implementation Report: Per-Project Aggregated Dashboard

## Summary
Implemented the full dashboard spec (`docs/dashboard_spec.md`): persisted LLM token/cost
usage (the load-bearing blocker), added a per-project aggregation endpoint, and added a
fourth **Dashboard** tab to the project page that aggregates across all runs — KPI cards,
score/WCAG/cost trends (inline SVG), persona reliability, and a P0/P1 action queue. Two-stream
discipline (§16) preserved: WCAG trend is TRUSTED, persona/score trends are INDICATIVE/DERIVED,
cost is operational metadata and never feeds the score.

## Assessment vs Reality

| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Full-stack, 6 build steps | As planned |
| Confidence | High (clear build order) | Confirmed |
| Files Changed | ~7 across DB/backend/frontend | 8 (+1 migration, +1 route, +1 report) |

## Tasks Completed

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Persist usage: migration `0003_usage.sql` + write path | Complete | Usage columns on `runs` + `run_model_usage` table |
| 2 | `repository.persist_run(pack, usage)` writes rollup + per-model rows | Complete | Usage serialized before persist in both run paths |
| 3 | Aggregation endpoint `GET /projects/{id}/dashboard` | Complete | Pure `aggregate_dashboard()` + best-effort `fetch_project_dashboard()` |
| 4 | Types §5 + `getProjectDashboard` client | Complete | Mock-friendly (computed from fixtures); one-line swap to real `fetch()` |
| 5 | Dashboard tab shell + KPI cards (Row A) | Complete | Score/WCAG/P0/cost cards with deltas |
| 6 | Trend charts (Rows B, C) | Complete | Inline SVG — no new dep (spec default) |
| 7 | Persona reliability + action queue (Rows D, E) | Complete | Sorted by block-rate / severity |

## Validation Results

| Level | Status | Notes |
|---|---|---|
| Static Analysis (tsc) | Pass | `tsc --noEmit` clean |
| Backend Unit Tests | Pass | 6 new tests; full suite green except 1 pre-existing `test_llm` failure (unrelated, LLM `.invoke` drift — confirmed failing on clean tree) |
| Build (next build) | Pass | Compiles + lints clean |
| Integration (Playwright) | Pass | Dashboard renders all 5 rows; multi-run (MyDigital) and low-N "needs ≥2 runs" (FinBank) states both correct; only console error is favicon 404 |

## Files Changed

| File | Action | Lines |
|---|---|---|
| `supabase/migrations/0003_usage.sql` | CREATED | +32 |
| `backend/app/repository.py` | UPDATED | +~230 |
| `backend/app/routes/runs.py` | UPDATED | +6 / -5 |
| `backend/app/routes/projects.py` | CREATED | +30 |
| `backend/app/main.py` | UPDATED | +2 / -1 |
| `backend/tests/test_repository.py` | UPDATED | +131 |
| `frontend/lib/types.ts` | UPDATED | +67 |
| `frontend/lib/api.ts` | UPDATED | +166 |
| `frontend/app/projects/[projectId]/page.tsx` | UPDATED | +~300 |

## Deviations from Plan
- **Frontend data source:** `getProjectDashboard` aggregates the in-memory fixtures (mock-friendly,
  matching the rest of `api.ts`) rather than hitting the new backend endpoint. Token/cost figures
  are a deterministic, SSR-safe demo stand-in. The backend returns the exact same camelCase shape,
  so going live is the documented one-line `fetch()` swap. **Why:** the whole frontend is mock-driven;
  the backend persistence is best-effort and only populated post-deploy with Supabase configured.
- **Decisions (§8):** all resolved to spec defaults — inline SVG (no Recharts), DeepSeek pricing already
  in `config.py` (cost cards non-empty), low-N copy = "Needs ≥2 runs to chart a trend."

## Issues Encountered
- `uv run pytest` generated an untracked `backend/uv.lock` and Playwright dropped a stray
  `dashboard.png` at repo root — both removed/left untracked, not committed.
- Pre-existing `test_llm` failure (LLM client `.invoke` API drift) is unrelated to this work.

## Next Steps
- [ ] Code review via `/code-review`
- [ ] Commit + PR (not yet committed — awaiting your go-ahead)
- [ ] Optional: wire `getProjectDashboard` to the live endpoint once Supabase has runs

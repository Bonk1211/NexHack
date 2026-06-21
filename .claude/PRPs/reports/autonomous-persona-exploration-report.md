# Implementation Report: Autonomous Persona Exploration

## Summary
Replaced the persona subgraph's fixed `flow[step_idx]` indexer with a **goal-driven agent
loop**. A renamed `plan` node now picks the next action from the live a11y tree + action
history + per-app goal (`plan_action`), so each persona explores the app on its own across
pages until it reaches the goal, hits a dead end, or trips a safety cap. Scripted `flow`
mode is preserved (dual-mode) so all contract tests stay green. Also fixed the missing
`wait_for_load_state` after navigating clicks.

## Assessment vs Reality

| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Large | Large |
| Confidence | 8/10 | Single-pass, no rework |
| Files Changed | ~9 (6 changed, 1 new test) | 8 changed + 1 new test |

## Tasks Completed

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | `NavConfig` goal + max_steps (back-compat) | ✅ Complete | `flow` now defaults to `[]` |
| 2 | Declare new state channels | ✅ Complete | Added to PersonaInput/PersonaState/RunState |
| 3 | `AgentAction` schema + `plan_action` + offline explorer | ✅ Complete | Mirrors `vision_judge` exactly |
| 3b | `_parse_aria_controls` helper | ✅ Complete | Placed in `llm.py` (no import cycle) |
| 4 | Rewrite subgraph loop (dual-mode) | ✅ Complete | `comprehend`→`plan`; cycle + cap in `decide` |
| 5 | `_click_and_settle` nav-wait | ✅ Complete | Swallows `PWTimeout` for non-nav clicks |
| 6 | Thread goal/max_steps through run graph | ✅ Complete | Autonomy only when goal supplied |
| 7 | `_resolve_journey` + SSE `plan` rename | ✅ Complete | start_run + stream both use it |
| 8 | Orchestrator passthrough | ✅ Complete | |
| 9 | Autonomous contract tests | ✅ Complete | 5 tests, forced offline for determinism |
| 10 | Frontend NODE_DOT cosmetic | ✅ Complete | Added `plan: bg-friction` |

## Validation Results

| Level | Status | Notes |
|---|---|---|
| Static Analysis | ✅ Pass | `py_compile` clean; 1 ruff F401 is **pre-existing** (`current_tracker`, untouched line) |
| Unit Tests | ✅ Pass | 80 passed (excl. pre-existing repo failures); 5 new autonomous tests |
| Build (frontend tsc) | ✅ Pass | `npx tsc --noEmit` clean |
| Integration | ✅ Pass | Offline browser journey explores fixture beyond step 1, terminates ≤ cap |
| Edge Cases | ✅ Pass | empty tree → done; cap → blocked; cycle → blocked; non-nav click not mis-flagged |

### Pre-existing failures (NOT caused by this change)
`tests/test_repository.py` — 7 failures (`_FakeTable` stub missing `.select`). Confirmed
failing identically on `main` before any edit. Out of scope.

## Files Changed

| File | Action | Lines |
|---|---|---|
| `backend/app/agents/llm.py` | UPDATED | +100 |
| `backend/app/agents/persona_graph.py` | UPDATED | +156 / -77 region |
| `backend/app/agents/run_graph.py` | UPDATED | +18 |
| `backend/app/agents/state.py` | UPDATED | +15 |
| `backend/app/agents/navigator.py` | UPDATED | +4 |
| `backend/app/orchestrator.py` | UPDATED | +7 |
| `backend/app/routes/runs.py` | UPDATED | +50 |
| `frontend/components/AssessmentRunner.tsx` | UPDATED | +1 (NODE_DOT) |
| `backend/tests/test_autonomous_nav.py` | CREATED | +85 |

## Deviations from Plan
- **`_parse_aria_controls` + `_action_signature` live in `llm.py`** (not navigator) — as the
  plan's GOTCHA preferred, to avoid a navigator↔llm import cycle. `persona_graph` imports
  `_action_signature` from `llm`.
- **Autonomous tests force offline via `monkeypatch.setattr(settings,"llm_api_key","")`** —
  the plan assumed no key in CI, but the local `.env` has a real key. Pinning offline makes
  the tests deterministic everywhere. (Discovered during Task 3 validation: the real LLM was
  being hit, producing non-deterministic `fill:Textbox` output.)

## Issues Encountered
- **Wrong Python interpreter** at first (`/opt/anaconda3` lacked `langgraph`). Switched to
  the project venv `backend/.venv/bin/python` for all commands.
- **Local `.env` LLM key** made the first offline assertion flaky — resolved by the
  monkeypatch above.

## Tests Written

| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_autonomous_nav.py` | 5 | aria parser, heuristic fill→click→done, empty tree, autonomous explore ≥1 step + cap, terminate + screenshot-every-step |

## Next Steps
- [ ] Code review via `/code-review`
- [ ] Optional: add a `goal` column to the `apps` table + UI field (currently `_resolve_goal`
      falls back to a sensible default; no migration required for the feature to work)
- [ ] Follow-up (out of scope): multi-tab/new-window flows; goal-configurable step criticality

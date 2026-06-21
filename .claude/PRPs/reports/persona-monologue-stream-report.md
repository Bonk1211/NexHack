# Implementation Report: Streaming persona monologue during assessment

## Summary
Each persona now narrates a first-person monologue ("Alright, let's get this done.") as it drives the target app. The line is produced by the existing per-step planner LLM call (one new `say` field — no extra call), streamed on the `plan` SSE event, and rendered as a typewriter chat-bubble feed per persona, with raw node cards kept behind a "Show node details" toggle.

## Assessment vs Reality

| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Medium | Medium |
| Confidence | 8/10 | Matched |
| Files Changed | 5–6 | 6 |

## Tasks Completed

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Add `say` to AgentAction | ✅ Complete | |
| 2 | Thread persona voice into plan_action | ✅ Complete | Also had to add `"say":""` to the system-prompt JSON shape literal (deviation) |
| 3 | Offline template for `say` | ✅ Complete | `_offline_say` helper |
| 4 | Declare state channels | ✅ Complete | `persona_voice` + `current_say` |
| 5 | Wire plan node | ✅ Complete | `current_say` set on ALL plan branches (not just autonomous) to avoid stale carry-over |
| 6 | SSE emit + build persona_voice | ✅ Complete | |
| 7 | Frontend type + reducer | ✅ Complete | |
| 8 | Typewriter chat bubble | ✅ Complete | latest bubble animates, history static |

## Validation Results

| Level | Status | Notes |
|---|---|---|
| Static Analysis | ✅ Pass | backend imports clean; `tsc --noEmit` exit 0 |
| Unit Tests | ✅ Pass | `test_persona_graph.py` 6/6 green |
| Build | ✅ Pass | tsc clean (no separate build run) |
| Integration | ✅ Pass | live `plan_action` call returns in-character `say` |
| Edge Cases | ✅ Pass | offline `say` non-empty; default `say==""`; back-compat OK |

Pre-existing unrelated failures: 7 `test_repository.py` tests fail on a clean tree too (no DB creds) — not caused by this change (verified via `git stash`).

## Files Changed

| File | Action | Lines |
|---|---|---|
| `backend/app/agents/llm.py` | UPDATED | +31 / -5 |
| `backend/app/agents/persona_graph.py` | UPDATED | +13 / -6 |
| `backend/app/agents/state.py` | UPDATED | +2 |
| `backend/app/routes/runs.py` | UPDATED | +11 |
| `frontend/components/AssessmentRunner.tsx` | UPDATED | +57 / -6 |
| `frontend/lib/live.ts` | UPDATED | +2 / -1 |

## Deviations from Plan
1. **System-prompt JSON shape** — the live DeepSeek model copies the exact JSON shape literal in `_PLAN_SYSTEM`; adding the field description alone left `say` empty. Fixed by adding `"say":""` to the shape example. WHY: model fidelity to the literal example over the prose.
2. **`current_say` on every plan branch** — plan has deterministic early returns (upload/select/goal/scripted). Set `current_say` on all of them (with sensible human lines), not just the autonomous branch. WHY: LangGraph keeps the prior value for unset scratch keys, so an upload/select step would otherwise show the previous step's monologue.

## Issues Encountered
- Empty `say` from live LLM despite the new field → root cause was the system-prompt shape literal (deviation #1). Resolved.

## Tests Written
No new test files added — covered by the existing `test_persona_graph.py` (offline path, default field) plus manual live verification. New field is defaulted and offline-safe, so existing tests exercise the back-compat and offline paths.

## Next Steps
- [ ] Manual UI check: run an assessment, confirm bubbles reveal char-by-char and read in-character
- [ ] Optional: thread `tech_savviness`/`patience`/`behavior_prompt` through `_row_to_persona_config` so DB personas get richer voice (currently only JSON personas carry these)
- [ ] Code review via `/code-review`

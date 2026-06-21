# Implementation Report: Aggregate friction + confusion matrices into engineer proposals

## Summary
Added a PURE `build_proposals(runs)` aggregator that fuses the friction matrix (per-persona status + dwell + dead-ends) and the confusion stream (`llm_confusion` per persona×step) into ranked, owner-routed engineer proposals — including behavioural-only problems that `build_remediation` (WCAG/axe-only) misses. Attached to the pack, rendered in Results, and added to the PDF/JSON export.

## Assessment vs Reality

| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Medium | Medium |
| Confidence | 8/10 | Matched |
| Files Changed | 5 + 1 test | 5 (one is the test file) |

## Tasks Completed

| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Owner heuristic (`_proposal_owner`) | ✅ Complete | |
| 2 | `build_proposals` aggregator | ✅ Complete | imported `_step_blocks` from engine |
| 3 | Deterministic fix templates (`_propose_fix`) | ✅ Complete | WCAG → block → confusion → dwell priority |
| 4 | Attach in `build_pack` | ✅ Complete | single attach → all routes + persistence |
| 5 | PDF/JSON export section | ✅ Complete | "Proposed fixes — engineering" table below remediation |
| 6 | Tests | ✅ Complete | 5 new tests + empty-pack assertion |
| 7 | Frontend `Pack.proposals` type | ✅ Complete | optional (historical packs) |
| 8 | Render in `Results` | ✅ Complete | severity chip + step + owner + signals + fix |

## Validation Results

| Level | Status | Notes |
|---|---|---|
| Static Analysis | ✅ Pass | `tsc --noEmit` exit 0; backend imports clean |
| Unit Tests | ✅ Pass | `test_evidence` + `test_export` + `test_export_route` all green; 5 new tests |
| Build | ✅ Pass | tsc clean |
| Integration | N/A | pure builder; rides existing pack flow |
| Edge Cases | ✅ Pass | empty runs, na steps, all-green, confusion==0.5 boundary, historical pack |

Pre-existing unrelated failures: 7 `test_repository.py` tests (no DB creds) — confirmed unrelated in prior sessions.

## Files Changed

| File | Action | Lines |
|---|---|---|
| `backend/app/evidence/pack.py` | UPDATED | +122 |
| `backend/app/evidence/export.py` | UPDATED | +18 |
| `backend/tests/test_evidence.py` | UPDATED | +49 |
| `frontend/components/AssessmentRunner.tsx` | UPDATED | +37 |
| `frontend/lib/live.ts` | UPDATED | +12 |

## Deviations from Plan
None — implemented as planned. (Used `min(severities, key=...)` for worst-severity selection and `max(..., default=...)` guards exactly as the GOTCHAs called for.)

## Issues Encountered
None.

## Tests Written

| Test File | Tests | Coverage |
|---|---|---|
| `backend/tests/test_evidence.py` | 5 new + 1 assertion | behavioral-block-no-WCAG, confusion-only owner, WCAG owner precedence, severity ranking, empty/clean |

## Next Steps
- [ ] Manual UI check: run an assessment with a behavioral-only block; confirm the "Proposed fixes" section + PDF table
- [ ] Optional: LLM narration enrichment of `fix` (mirror `synthesize`, gated, template fallback) — deferred per plan
- [ ] Code review via `/code-review`

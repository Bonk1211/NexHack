# Implementation Report: LangGraph Agent Build (Two-Graph + Vision + Synthesis, DeepSeek V4)

## Summary
Rebuilt the navigation agent as **two LangGraph graphs**: a cyclic persona subgraph
(`load → observe → comprehend → decide → act → route_next`) and a top-level
map-reduce run graph (`init → Send(persona)×N → aggregate → score → evidence →
alerts`). Added the per-step vision-LLM `comprehend` node and a once-per-run
`synthesize` call, both on DeepSeek V4 (`deepseek-v4-flash` / `deepseek-v4-pro`) via
`langchain-deepseek`, each with a deterministic offline fallback. A `SqliteSaver`
checkpoints run-level state per `run_id` for per-persona resume. The pure scorer,
`build_pack`, and the two-stream §16 discipline are untouched at their core; LLM
output feeds only the indicative stream and the output-side narrative.

## Assessment vs Reality
| Metric | Predicted (Plan) | Actual |
|---|---|---|
| Complexity | Large→XL | Large (XL on the checkpoint-serialization debugging) |
| Confidence | 8.5/10 (post-spike) | Held — single pass, no design changes |
| Files Changed | ~13 (7 new, 6 modified) | 15 (7 new, 8 modified incl. .gitignore + pre-existing lint fix) |

## Tasks Completed
| # | Task | Status | Notes |
|---|---|---|---|
| 1 | Dependencies | ✅ | + langgraph 1.2.5, langchain-deepseek, langgraph-checkpoint-sqlite |
| 2 | state.py (RunState/PersonaState) | ✅ | Added `PersonaInput` (serializable Send payload) — see Deviations |
| 3 | llm.py | ✅ | Verified `ChatDeepSeek(model=,api_key=,api_base=)`; offline parity 1.0/0.0 |
| 4 | persona_graph.py (cyclic subgraph) | ✅ | Faithful to navigator loop; scratch keys declared as channels |
| 5 | navigator.run_journey delegates | ✅ | Contract preserved; function-local import breaks the cycle |
| 6 | run_graph.py (map-reduce) | ✅ | Send fan-out + reducer fan-in + aggregate reorder |
| 7 | Checkpointer + msgpack registration | ✅ | Two real bugs fixed (see Issues); registered domain dataclasses |
| 8 | orchestrator + route + config + env | ✅ | DeepSeek locked; run_id threaded as checkpoint thread_id |
| 9–11 | tests | ✅ | 21 new tests, all green offline |

## Validation Results
| Level | Status | Notes |
|---|---|---|
| Static Analysis (ruff) | ✅ Pass | `ruff check app tests` clean (also fixed 1 pre-existing unused import) |
| Unit/Contract Tests | ✅ Pass | 56 passed (35 baseline + 21 new), 0 warnings |
| Build (editable install) | ✅ Pass | `pip install -e .` + import smoke ok |
| Integration | ✅ Pass | End-to-end `run_assessment` against fixture site: hero diff + checkpoint |
| Edge Cases | ✅ Pass | offline parity, block-no-retry, raw-only state, resume idempotence, no live-object channels |

## Files Changed
| File | Action | ~Lines |
|---|---|---|
| `backend/app/agents/state.py` | CREATE | +110 |
| `backend/app/agents/llm.py` | CREATE | +185 |
| `backend/app/agents/persona_graph.py` | CREATE | +230 |
| `backend/app/agents/run_graph.py` | CREATE | +200 |
| `backend/tests/test_llm.py` | CREATE | +110 |
| `backend/tests/test_persona_graph.py` | CREATE | +95 |
| `backend/tests/test_run_graph.py` | CREATE | +110 |
| `backend/app/agents/navigator.py` | UPDATE | −122/+30 (loop extracted) |
| `backend/app/orchestrator.py` | UPDATE | thin shim over run graph |
| `backend/app/config.py` | UPDATE | DeepSeek defaults + base_url + checkpoint_db |
| `backend/app/routes/runs.py` | UPDATE | run_id → thread_id |
| `backend/.env.example` | UPDATE | DeepSeek lock + LLM_BASE_URL + CHECKPOINT_DB |
| `backend/pyproject.toml` | UPDATE | 4 deps |
| `backend/app/scoring/engine.py` | UPDATE | removed pre-existing unused import (lint gate) |
| `.gitignore` | UPDATE | ignore `*.sqlite` checkpoint store |

## Deviations from Plan
- **Added `PersonaInput` TypedDict (Task 2).** The plan had one `PersonaState`. LangGraph
  derives parent channels from each node's input annotation, so annotating the `persona`
  node with the full `PersonaState` injected the live `page`/`rng` as parent channels and
  broke checkpoint serialization. Split into `PersonaInput` (serializable Send payload) +
  `PersonaState` (subgraph-only, adds page/rng). WHY: keep non-serializable objects out of
  the checkpointer — exactly the plan's intent, reached via a cleaner type boundary.
- **`run_persona` runs the subgraph in a dedicated thread (Task 4).** Not in the plan.
  WHY: LangGraph propagates the parent checkpointer to nested invokes via an ambient
  contextvar; a fresh thread severs it (and keeps sync Playwright off any event loop).
- **Pulled the config change forward into Task 3.** `llm.py` references `settings.llm_base_url`;
  added the config fields when creating `llm.py` rather than waiting for Task 8.

## Issues Encountered
1. **Scratch keys silently dropped.** `current_*` keys returned by nodes vanished between
   nodes (LangGraph drops undeclared channels) → `oku_visual` didn't block, screenshots were
   None. Fixed by declaring all scratch keys in `PersonaState`.
2. **`Page` not msgpack-serializable (checkpoint).** Two layered causes: (a) node input
   annotation leaking PersonaState channels — fixed with `PersonaInput`; (b) nested-graph
   checkpointer inheritance via contextvar — fixed by the dedicated thread.
3. **msgpack "unregistered type … blocked in future version" warning.** Registered the domain
   dataclasses via `JsonPlusSerializer(allowed_msgpack_modules=[...])`. Verified gone under
   `-W error::UserWarning`.
4. **Persona identity key.** Run graph initially used the JSON display `name`; tests/pack key
   on the file stem. Switched to carry `stem` as identity.
5. **`retry=` deprecated** → `retry_policy=` on `add_node`.

## Tests Written
| Test File | Tests | Coverage |
|---|---|---|
| `tests/test_llm.py` | 7 | offline heuristic/template, structured pass-through, error fallback |
| `tests/test_persona_graph.py` | 6 | block-exit, completion, raw-only state, offline parity, no-retry, contract |
| `tests/test_run_graph.py` | 9 | fan-out, hero diff, ordering, score node, synthesis, resume, no live channels |

## Post-review fixes (/code-review high)
| # | Finding | Fix | Verified |
|---|---|---|---|
| 1 | Re-invoking a run_id duplicated personas (reducer accumulation) | `run_assessment` checks `get_state`: fresh→seed, interrupted→`invoke(None)` resume, completed→return existing pack | empirical: 2nd run stays `[control, oku_visual]`, idempotent |
| 2 | Resume test masked #1 (verdict-dict dedup) | assert full `personas` LIST + pack equality; added cross-run isolation test | 57 passed |
| 3 | LLM failures silently degraded to offline | `logger.warning(...)` on the except path in `vision_judge`/`synthesize` (still falls back) | logs `... 401 auth; using offline heuristic` |
| 4 | `llm_provider` dead config (silent provider mismatch) | removed from `config.py` + `.env.example` (client is DeepSeek-only by construction) | lint + suite green |
| 5 | Checkpointer unreachable via API (fresh uuid each POST) | `StartRunRequest.run_id` optional → clients can resume; checkpointer now correct + idempotent | route passes run_id through |

## Next Steps
- [ ] `/code-review` the diff
- [x] Live-key smoke (2026-06-19): DeepSeek key set; model ids `deepseek-v4-flash`/`deepseek-v4-pro`
  valid against the live endpoint. `vision_judge` confusion VARIES (0.0 labeled vs 0.8 unlabeled,
  not the 0/1 heuristic) with coherent reasons; `synthesize` rollup/narrative grounded in the pack
  (names `oku_visual` P0 at `otp`, no invented WCAG). Auth + `json_mode` confirmed.
- [ ] `/prp-pr` to open the PR

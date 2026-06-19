# Plan: LangGraph Agent Build — Two-Graph (Persona Subgraph + Run Map-Reduce), DeepSeek V4

## Summary
Build the navigation agent as **two graphs**, not one. (1) A **cyclic persona subgraph** — `observe → comprehend → decide → act → route_next` — that loops a single persona over the flow until blocked or done; the exit condition is emergent. (2) A **top-level map-reduce run graph** — `init → Send(persona_subgraph)×N → aggregate → score → evidence → alerts` — that fans out one subgraph per persona and fans in via a reducer. The **one** real LLM node is `comprehend` (DeepSeek V4 Flash vision: stream-B confusion + nav fallback); a single optional `synthesize` call sits in `evidence` (DeepSeek V4 Pro). Everything marks-bearing — `score`, `build_pack`, `aggregate` — stays **pure, deterministic compute** over **raw** stored signals (§16). A persona block is a **clean exit that writes a P0**, never an LLM-recoverable error.

## User Story
As an inclusion/compliance engineer, I want each persona driven by a real cyclic agent loop (observe→decide→act→repeat) and all personas fanned out / aggregated by a run graph, so that the agentic navigation is legible and resumable, while the WCAG/scoring core stays machine-verifiable and the same screen demonstrably blocks a protected persona yet passes the control.

## Problem → Solution
**Current:** `navigator.run_journey` is one procedural sync-Playwright loop with a monolithic body; `llm_confusion` hardcoded; orchestrator runs a plain `for` loop over personas; no graph, no LLM, no resume. → **Desired:** persona journey is a cyclic LangGraph subgraph with distinct deterministic vs LLM nodes; orchestrator is a top-level fan-out/fan-in graph with a checkpointer for per-persona crash-resume; `comprehend` produces real confusion; `evidence` attaches synthesis. Scorer + pack untouched at their core.

## Metadata
- **Complexity**: Large (→ borderline XL — two graphs + checkpointer)
- **Source PRD**: `docs/prd/PRD_InclusionScope_v2_Merged.md` (§8 nav loop, §13 evidence, §15 LLM, §16 raw-signal/pure-scorer, §20 sequential, §23 validity, §25 model lock)
- **PRD Phase**: standalone — the agentic deepening behind §21 #2
- **Estimated Files**: ~13 (7 new, 6 modified)

---

## Spike results (de-risk run, 2026-06-19) — both top risks CLEARED
Ran `/tmp/lg_spike.py` against `langgraph==1.2.5` + `playwright==1.60` (installed into `backend/.venv`):
- **sync Playwright under Send fan-out = OK.** Sync `.invoke` ran 3 persona subgraphs, each doing real sync Playwright (launch→goto→`aria_snapshot`→screenshot), **each in its own thread** (distinct thread ids) — **no asyncio-loop error**. The plan's mitigation (sync `.invoke` = thread-pool, own `sync_playwright` per persona thread) is confirmed. Execution is genuinely concurrent → keep per-persona `seed+i` + `aggregate` reorder.
- **checkpoint of domain types = OK with one chore.** Frozen dataclasses (`StepSignals`/`WcagSignal`) round-trip through `SqliteSaver` and rebuild as real instances. Caveats: (a) LangGraph warns *"Deserializing unregistered type … blocked in a future version"* → **register `app.scoring.engine` via `allowed_msgpack_modules`** (or store raw as dicts); (b) `tuple` fields deserialize as `list` (`wcag` came back a list) — harmless for the scorer (it iterates), but nothing may rely on tuple identity post-checkpoint.
- **Install note**: langgraph pulled `websockets 16→15.0.1`; Playwright bundles its own and the spike ran clean, but re-run the full suite after install (Task 1).

Confidence after spike: **8.5/10** single-pass.

## Decisions locked this session
- **Scope**: full two-graph (persona subgraph + run map-reduce) + **Send** fan-out + **reducer** fan-in + **checkpointer** for per-persona resume.
- **Model**: DeepSeek V4 — `deepseek-v4-flash` (per-step `comprehend`), `deepseek-v4-pro` (once-per-run `synthesize`). Resolves §25.
- **Cognition is concentrated**: exactly one mandatory LLM node (`comprehend`) + one optional LLM call (`synthesize`). `observe`/`act`/`decide`/`score`/`aggregate`/`build_evidence` are deterministic plumbing. (Per design review — modelling `score` as an LLM node would break the §16 trusted core.)
- **Block = product, not error**: `RetryPolicy` applies to **transient** Playwright/network failures on `observe`/`act` only. A persona that cannot proceed exits with a verdict; no loop-back retry erases the finding.

---

## UX Design

### Before
```
POST /runs ─► orchestrator (procedural for-loop over personas)
                └─ run_journey(cfg)  ── one monolithic sync loop
                     axe + aria + grade; per step locate→act→shot
                     llm_confusion = HARDCODED 0/1
                ─► score (pure) ─► build_pack ─► JSON
```

### After
```
POST /runs ─► run graph  (top-level, checkpointed by run_id)
   init ─┬─Send─► [persona subgraph]   ┐
         ├─Send─► [persona subgraph]   ├─► aggregate ─► score ─► evidence ─► alerts ─► END
         └─Send─► [persona subgraph]   ┘   (reorder)   (pure)   (pack+      (best-
                                              fan-in     per       synth)     effort)
                                              reducer    persona)
   persona subgraph (cyclic, one per persona):
       load ─► observe ─► comprehend ─► decide ─► act ─► route_next ─┐
                  ▲           (LLM:        (a11y     (PW)   │         │
                  └───────────  confusion   heuristic        loop ◄───┘  or
                                + fallback)  + behavior)      END (blocked|completed)
```

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| persona journey | monolithic loop | cyclic subgraph, 5 distinct nodes | observe/act/decide deterministic; comprehend = only LLM |
| persona orchestration | procedural `for` | top-level graph, `Send` fan-out + reducer fan-in | resumable per persona via checkpointer |
| `StepSignals.llm_confusion` | hardcoded | real vision score (offline → heuristic) | field already exists |
| stored per-step state | (verdict computed inline) | **raw** signals only (axe/dwell/a11y); verdict derived later by `score` node | §16 "store raw, derive on demand" |
| pack JSON | no narrative | `+ synthesis` block | output-side only, never feeds scorer |
| `run_journey(cfg)` | procedural | invokes persona subgraph standalone | contract tests stay green |
| offline (no key) | n/a | identical deterministic output to today | fallback parity |

---

## Mandatory Reading
| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `backend/app/agents/navigator.py` | 1-156 | Loop being split into nodes; preserve `FlowStep`/`NavConfig`/`JourneyResult`/`_role_has_name` + the dwell/hesitation/dead_end logic to distribute across decide/act |
| P0 | `backend/app/scoring/engine.py` | 30-43, 90-219 | `StepSignals` (raw fields incl. `llm_confusion`); `_step_blocks` (route_next reads raw flags, not the full scorer); scorer is PURE — stays so |
| P0 | `backend/app/orchestrator.py` | 1-85 | `run_assessment` becomes the top-level-graph invoker; must return the same dict shape (`pack` + `screenshots`) |
| P0 | `backend/app/config.py` | 1-25 | Two-tier model fields exist; switch to DeepSeek + add base_url + checkpoint path |
| P0 | `backend/app/evidence/pack.py` | 51-158 | `PersonaRunResult` shape consumed by `score`/`evidence` nodes; `build_pack` return shape synthesis augments |
| P1 | `backend/app/agents/signals.py` | 1-76 | `run_axe`/`axe_to_wcag`/`reading_grade` — called in `observe` (axe once on entry) |
| P1 | `backend/app/alerts.py` | all | `send_alerts(pack)` → the `alerts` node |
| P1 | `backend/tests/test_nav_contract.py` | 1-82 | Contract pattern the persona subgraph must keep passing via `run_journey` |
| P1 | `backend/app/routes/runs.py` | all | Passes `run_id`; becomes the checkpointer `thread_id` |
| P2 | `personas/oku_visual.json`, `control.json` | all | `behavior_profile`/`thresholds`/`disabilities` consumed by `decide` |

## External Documentation
| Topic | Source | Key Takeaway |
|---|---|---|
| LangGraph map-reduce / `Send` | https://docs.langchain.com/oss/python/langgraph/graph-api#send | Fan-out: a conditional edge returns `[Send("node", state), ...]`; fan-in: a downstream node with `Annotated[list, operator.add]` collects results |
| LangGraph subgraphs | https://docs.langchain.com/oss/python/langgraph/use-subgraphs | A compiled graph can be added as a node in a parent graph |
| LangGraph RetryPolicy | https://docs.langchain.com/oss/python/langgraph/graph-api#node-retry-policies | `add_node(..., retry=RetryPolicy(max_attempts=3))` — transient failures only |
| LangGraph checkpointing | https://docs.langchain.com/oss/python/langgraph/persistence | `SqliteSaver`; invoke with `config={"configurable": {"thread_id": run_id}}` for crash-resume |
| ChatDeepSeek | https://docs.langchain.com/oss/python/integrations/chat/deepseek | `pip install langchain-deepseek`; `ChatDeepSeek(model=, temperature=0)`; `with_structured_output(Model, strict=True)`; reads `DEEPSEEK_API_KEY` |
| DeepSeek V4 models | https://codersera.com/blog/how-to-use-deepseek-v4-api-developer-guide-2026/ | `deepseek-v4-pro` (synth), `deepseek-v4-flash` (vision/per-step); OpenAI-compatible `https://api.deepseek.com` |
| DeepSeek V4 vision | https://www.mindstudio.ai/blog/deepseek-v4-vision-cheaper-multimodal-ai-workflows | native image+text input |

### Research notes
```
KEY_INSIGHT: deepseek-reasoner (R1) has NO tool-calling/structured output.
APPLIES_TO: synthesize. GOTCHA: use deepseek-v4-pro, never a reasoner model.

KEY_INSIGHT: sync Playwright cannot run inside a live asyncio loop ("Playwright Sync API inside asyncio loop").
APPLIES_TO: every browser-touching node under the Send-fan-out run graph.
GOTCHA: drive the run graph with SYNC `.invoke` (Pregel runs sync nodes in a thread-pool, no loop in worker threads) so sync Playwright keeps working. Each persona subgraph instance must create its OWN `sync_playwright()` in its thread. VERIFY at Task 4; fallback = isolate each persona journey behind `concurrent.futures.ThreadPoolExecutor` or port observe/act to async Playwright. This is the #1 risk.

KEY_INSIGHT: §16 demands store-raw / derive-on-demand AND a pure seeded scorer.
APPLIES_TO: PersonaState.steps, the score node.
GOTCHA: subgraph stores RAW per-step signals (axe violations, dwell_ms, a11y tree, llm_confusion) only — NO verdict. The top-level `score` node derives WCAG conformance / verdict / composite. Never persist a precomputed verdict.

KEY_INSIGHT: LLM non-determinism vs §16/§20 reproducibility.
APPLIES_TO: comprehend, synthesize. GOTCHA: temperature=0 + offline fallback that reproduces today's heuristic exactly, so tests/demo are deterministic with no key.

KEY_INSIGHT: §20 wants sequential narration; Send executes concurrently.
APPLIES_TO: aggregate. GOTCHA: each persona carries its own seed (seed+i) so determinism survives concurrency; `aggregate` REORDERS persona_results to input order so output/narration is stable. Demo narration order is a stream-layer concern, not execution order.
```

---

## Patterns to Mirror

### A11Y_TREE_CHECK — the nav primitive `decide` reuses (don't reinvent)
```python
# SOURCE: backend/app/agents/navigator.py:57-65
def _role_has_name(aria_snapshot: str, role: str) -> bool:
    pat = re.compile(rf'^\s*-\s+{re.escape(role)}\s+"[^"]+"', re.MULTILINE)
    return bool(pat.search(aria_snapshot))
```

### TRUSTED_SIGNAL_CAPTURE — `observe` runs axe ONCE on entry (matches today)
```python
# SOURCE: backend/app/agents/navigator.py:86-91
wcag = axe_to_wcag(run_axe(page))           # page-level, persona-independent
aria = page.locator("body").aria_snapshot()
body_text = page.inner_text("body")
grade = reading_grade(body_text)
```

### BEHAVIOR_DRIVES_CONTROL_FLOW — `decide` must change the loop, not a prompt (§23)
```python
# SOURCE: backend/app/agents/navigator.py:94-126  (this logic moves into decide/act)
read_s = (word_count / wpm) * 60.0
dwell = read_s * dwell_mult
if rng.random() < hesitation_prob: dwell *= 1.5
...
if cfg.requires_labels and not labeled:      # persona depends on labels -> dead end
    dead_end, completed, confusion = True, False, 1.0
if dwell >= giveup_s:                          # behavior threshold blocks
    dead_end, completed = True, False
```

### RAW_STEPSIGNALS_EMIT — `act` appends RAW signals (verdict derived later)
```python
# SOURCE: backend/app/agents/navigator.py:136-149
StepSignals(step_idx=i, step_key=fs.key, critical=fs.critical,
            wcag=wcag if i == 0 else (), dwell_s=round(dwell,2), retries=retries,
            dead_end=dead_end, completed=completed,
            llm_confusion=confusion,      # <- from comprehend, not hardcoded
            reading_grade=grade)
```

### PURE_PER_PERSONA_SCORE — the `score` node maps this over fanned-in results
```python
# SOURCE: backend/app/orchestrator.py:67-78  (moves into the score node)
result = score(journey.steps, thresholds)
PersonaRunResult(persona=name, steps=tuple(journey.steps),
                 thresholds=thresholds, result=result)
```

### ATTACH-EXTRA-KEY — how `evidence` augments the pack
```python
# SOURCE: backend/app/orchestrator.py:82-84
pack = build_pack(app_name, run_at, runs)
pack["screenshots"] = screenshots
# + pack["synthesis"] = synthesize(pack).model_dump()
```

### BEST-EFFORT side-effect — the `alerts` node never breaks the run
```python
# SOURCE: backend/app/routes/runs.py:46-50
try: repository.persist_run(pack)
except Exception: pass
```

### CONFIG_SETTINGS / TEST_STRUCTURE
```python
# SOURCE: backend/app/config.py:8-23  — extend, don't restructure
# SOURCE: backend/tests/test_nav_contract.py:36-45 — module-scoped journey fixture, fixture-site URIs
```

---

## Files to Change
| File | Action | Justification |
|---|---|---|
| `backend/pyproject.toml` | UPDATE | + `langgraph`, `langchain-deepseek`, `langchain-core`, `langgraph-checkpoint-sqlite` |
| `backend/app/agents/state.py` | CREATE | `RunState` + `PersonaState` TypedDicts with reducers (`Annotated[list, operator.add]`) |
| `backend/app/agents/llm.py` | CREATE | DeepSeek two-tier client, `VisionJudgment`/`SynthesisResult` schemas, `vision_judge`/`synthesize` + offline fallback |
| `backend/app/agents/persona_graph.py` | CREATE | cyclic subgraph (load/observe/comprehend/decide/act + `route_next`), `build_persona_graph()`, `run_journey` wrapper |
| `backend/app/agents/run_graph.py` | CREATE | top-level map-reduce graph (init/fan-out `Send`/aggregate/score/evidence/alerts), `build_run_graph(checkpointer)`, `run_assessment(...)` |
| `backend/app/agents/navigator.py` | UPDATE | keep `FlowStep`/`NavConfig`/`JourneyResult`/`_role_has_name`; `run_journey` delegates to persona subgraph |
| `backend/app/orchestrator.py` | UPDATE | `run_assessment` invokes `run_graph` with `SqliteSaver` + `thread_id=run_id`; same return shape |
| `backend/app/config.py` | UPDATE | DeepSeek defaults + `llm_base_url` + `checkpoint_db` path |
| `backend/.env.example` | UPDATE | DeepSeek keys + `LLM_BASE_URL` + `CHECKPOINT_DB`; comment §25 "LOCKED" |
| `backend/app/routes/runs.py` | UPDATE | generate `run_id` first, pass as `thread_id` for resume; same response |
| `backend/tests/test_persona_graph.py` | CREATE | subgraph: loop terminates on block, clean page completes, offline parity, raw-only state |
| `backend/tests/test_run_graph.py` | CREATE | fan-out N personas, reducer fan-in, aggregate ordering, resume from checkpoint |
| `backend/tests/test_llm.py` | CREATE | `vision_judge`/`synthesize` mocked + offline fallback, no network |

## NOT Building
- A second model family — DeepSeek V4 only (§25). No reasoner-model structured output.
- `score`/`build_pack`/friction-matrix as LLM nodes — they stay pure deterministic compute (§16). LLM only in `comprehend` + optional `synthesize`.
- LLM-recoverable navigation: no loop-back/retry when a persona is blocked (that erases the finding, §23). `RetryPolicy` = transient PW/network only.
- `interrupt()` in the navigation path — CAPTCHA/OTP are mocked (§25). Human-in-the-loop maps to alert→owner routing, not nav.
- Vision-first navigation — a11y-tree-primary; vision is `comprehend` judgment + `decide` fallback only (§25).
- Feeding any LLM output into the trusted WCAG stream or composite math (§16/§23 hard line).
- Persisting a precomputed verdict in state — store raw signals only.

---

## Step-by-Step Tasks

### Task 1: Dependencies
- **ACTION**: Add `langgraph>=0.2`, `langchain-deepseek>=0.1`, `langchain-core>=0.3`, `langgraph-checkpoint-sqlite>=2.0` to `[project].dependencies`.
- **MIRROR**: the `# §NN — note` inline comment style in `pyproject.toml`.
- **GOTCHA**: install into `backend/.venv` (Python 3.13), not system 3.10.
- **VALIDATE**: `cd backend && .venv/bin/pip install -e . && .venv/bin/python -c "import langgraph, langchain_deepseek; from langgraph.checkpoint.sqlite import SqliteSaver"`.

### Task 2: State objects (two)
- **ACTION**: Create `backend/app/agents/state.py` with `PersonaState` and `RunState` TypedDicts.
- **IMPLEMENT**:
  - `PersonaState`: `persona, behavior_profile: dict, thresholds: PersonaThresholds, requires_labels: bool, target_url, flow: list[FlowStep], viewport, seed: int, artifact_dir: str|None, page: object, rng: object, step_idx: int, steps: Annotated[list[StepSignals], operator.add], shots: Annotated[list, operator.add], aria: str, wcag: tuple, grade: float, word_count: int, last_confusion: float, last_fallback: str|None, status: str, blocked_at: str|None, persona_idx: int`.
  - `RunState`: `app, target_url, viewport, personas: list[dict], flow: list[FlowStep], seed: int, artifact_root: str|None, run_at: str, persona_results: Annotated[list, operator.add], pack: dict`.
  - PRD-anchored docstring (§16: state stores RAW signals, never a verdict).
- **IMPORTS**: `import operator`; `from typing import Annotated, TypedDict`; `from app.scoring.engine import StepSignals, PersonaThresholds`; `from app.agents.navigator import FlowStep`.
- **GOTCHA**: reducer keys (`steps`, `shots`, `persona_results`) are the ONLY multi-writer keys; everything else is single-writer per superstep. `page`/`rng` are live objects — fine for in-process `.invoke`, but they are NOT checkpoint-serializable (see Task 7 GOTCHA).
- **VALIDATE**: `.venv/bin/python -c "from app.agents.state import RunState, PersonaState"`.

### Task 3: DeepSeek client + LLM functions (one LLM node + one synth call)
- **ACTION**: Create `backend/app/agents/llm.py`.
- **IMPLEMENT**:
  - `_client(model) -> ChatDeepSeek | None`: `None` when `settings.llm_api_key` empty; else `ChatDeepSeek(model=model, api_key=settings.llm_api_key, api_base=settings.llm_base_url, temperature=0, max_retries=2)`.
  - `VisionJudgment(BaseModel)`: `confusion: float = Field(ge=0, le=1)`, `reason: str`, `fallback_target: str | None = None`.
  - `SynthesisResult(BaseModel)`: `rollup: str` (§18 "who are we excluding" one-liner), `narrative: str`, `key_exclusions: list[str]`.
  - `vision_judge(screenshot_path, step_key, aria_excerpt, *, requires_labels, labeled, action) -> VisionJudgment`: offline (`_client is None`) → heuristic reproducing today: `confusion=1.0` when `action=="fill" and requires_labels and not labeled`, else `0.0`. Online → downscale screenshot (pillow), base64 image content-block + concise system prompt, `.with_structured_output(VisionJudgment, strict=True)`; `try/except` → heuristic on any failure.
  - `synthesize(pack) -> SynthesisResult`: offline → deterministic template derived from pack (rollup from blocked personas + `blocked_at`); online → `deepseek-v4-pro`, `.with_structured_output(SynthesisResult, strict=True)` over compact pack JSON; `try/except` → template.
- **MIRROR**: CONFIG_SETTINGS; module docstring style (§15).
- **IMPORTS**: `from langchain_deepseek import ChatDeepSeek`; `from pydantic import BaseModel, Field`; `import base64, io`; `from PIL import Image`; `from app.config import settings`.
- **GOTCHA**: never a reasoner model for synth. Downscale before base64 (§ cost). Every LLM path `try/except` → deterministic fallback. Verify ChatDeepSeek kwarg (`api_key` vs `deepseek_api_key`) + image content-block shape against installed version (isolated here).
- **VALIDATE**: Task 11 (`test_llm.py`); `.venv/bin/python -c "from app.agents.llm import vision_judge, synthesize, VisionJudgment"`.

### Task 4: Persona subgraph (cyclic)
- **ACTION**: Create `backend/app/agents/persona_graph.py` — nodes `load`, `observe`, `comprehend`, `decide`, `act`, edge fn `route_next`, plus `build_persona_graph()` and `run_journey(cfg)`.
- **IMPLEMENT**:
  - `load(state)`: open `sync_playwright()` (store on state via a module-level per-thread holder — see GOTCHA), launch chromium, `new_page(**devices[viewport])`, `goto(load)`, seed `rng=random.Random(seed)`, `step_idx=0`, empty `steps`/`shots`, `status="running"`.
  - `observe(state)` *(deterministic, RetryPolicy)*: on `step_idx==0` capture `wcag/aria/grade/word_count` (TRUSTED_SIGNAL_CAPTURE). On re-entry refresh `aria` + screenshot only (axe stays the entry-step capture).
  - `comprehend(state)` *(the only LLM node)*: `vision_judge(...)` on current screenshot → set `last_confusion`, `last_fallback`.
  - `decide(state)` *(deterministic, a11y + behavior)*: compute `dwell` from `behavior_profile` × seeded `rng` (BEHAVIOR_DRIVES_CONTROL_FLOW); `labeled=_role_has_name(aria, fs.role)`; if `requires_labels and not labeled and fs.action=="fill"` → intent-block; if `dwell>=giveup_s` → intent-block. Choose locator; if a11y locate not resolvable and `last_fallback` present, adopt fallback target.
  - `act(state)` *(deterministic, RetryPolicy on transient PW errors)*: execute fill/click via `get_by_role`; on PW failure set `dead_end`. Screenshot EVERY step. Append RAW `StepSignals` (RAW_STEPSIGNALS_EMIT) with `llm_confusion=last_confusion`. `step_idx += 1`. Set `status="blocked"`+`blocked_at` if `dead_end`/intent-block else keep running; `status="completed"` when `step_idx>=len(flow)`.
  - `route_next(state) -> str`: `"observe"` if `status=="running"` else `END`. (Reads RAW flags only, not the scorer.)
  - `build_persona_graph()`: `g=StateGraph(PersonaState)`; add nodes; `observe`/`act` with `retry=RetryPolicy(max_attempts=3)`; entry `load → observe → comprehend → decide → act`; `add_conditional_edges("act", route_next, {"observe":"observe", END:END})`; `return g.compile()`.
  - `run_journey(cfg: NavConfig) -> JourneyResult`: build single `PersonaState` from `cfg`, `graph.invoke(state)`, close browser in `finally`, return `JourneyResult(state["steps"], state["shots"])`.
- **MIRROR**: A11Y_TREE_CHECK, TRUSTED_SIGNAL_CAPTURE, BEHAVIOR_DRIVES_CONTROL_FLOW, RAW_STEPSIGNALS_EMIT.
- **IMPORTS**: `from langgraph.graph import StateGraph, END`; `from langgraph.types import RetryPolicy`; `from playwright.sync_api import sync_playwright`; `from app.agents.navigator import FlowStep, NavConfig, JourneyResult, _role_has_name`; `from app.agents.signals import ...`; `from app.agents.llm import vision_judge`; `from app.agents.state import PersonaState`.
- **GOTCHA (#1 risk)**: sync Playwright dies inside an asyncio loop. Drive with SYNC `.invoke` so nodes run in a thread-pool (no loop). Each subgraph instance owns its own `sync_playwright()` in its thread; do NOT share a page across personas. Own the PW lifecycle around `invoke` (in `run_journey`, and in the run graph's persona-node wrapper) — never tear it down inside a node. VERIFY the no-loop assumption first; fallback = wrap each persona journey in a `ThreadPoolExecutor` worker or port `observe`/`act` to async Playwright.
- **GOTCHA**: navigator↔persona_graph cycle — `persona_graph` imports from `navigator`; `navigator.run_journey` does a **function-local** import of `persona_graph.run_journey`.
- **VALIDATE**: `test_persona_graph.py` (Task 9); `.venv/bin/pytest tests/test_nav_contract.py -q` green unchanged.

### Task 5: `run_journey` delegates (navigator)
- **ACTION**: In `navigator.py`, replace `run_journey` body with function-local `from app.agents.persona_graph import run_journey as _rj; return _rj(cfg)`; keep `FlowStep`/`NavConfig`/`JourneyResult`/`_role_has_name`. Update docstring (loop now in `persona_graph`).
- **GOTCHA**: function-local import breaks the cycle.
- **VALIDATE**: `.venv/bin/pytest tests/test_nav_contract.py -q`.

### Task 6: Top-level run graph (map-reduce)
- **ACTION**: Create `backend/app/agents/run_graph.py` — nodes `init`, `aggregate`, `score`, `evidence`, `alerts`; fan-out edge `fan_out`; persona subgraph added as the `persona` node; `build_run_graph(checkpointer)`.
- **IMPLEMENT**:
  - `init(state)`: load each persona config, compute per-persona `requires_labels` (mirror `orchestrator._requires_labels`), set `run_at`, normalize flow/seed/artifact_root. No browser here.
  - `fan_out(state) -> list[Send]`: `[Send("persona", _persona_state(state, persona, i, seed=state["seed"]+i)) for i, persona in enumerate(state["personas"])]`.
  - `persona`: a thin node wrapping the compiled persona subgraph (own PW lifecycle around its `invoke`), returning `{"persona_results": [PersonaRunResult-precursor with raw steps+shots+persona_idx]}` so the reducer collects.
  - `aggregate(state)`: sort `persona_results` by `persona_idx` → deterministic order (§20 narration). Passthrough otherwise.
  - `score(state)`: per persona, pure `score(steps, thresholds)` → list[`PersonaRunResult`] (PURE_PER_PERSONA_SCORE).
  - `evidence(state)`: `pack = build_pack(app, run_at, runs)`; `pack["screenshots"] = {...}`; `pack["synthesis"] = synthesize(pack).model_dump()`; set `state["pack"]`.
  - `alerts(state)`: `send_alerts(pack)` wrapped best-effort (BEST-EFFORT pattern).
  - `build_run_graph(checkpointer)`: `g=StateGraph(RunState)`; add nodes + `persona` subgraph; `set_entry_point("init")`; `g.add_conditional_edges("init", fan_out, ["persona"])`; `persona→aggregate→score→evidence→alerts→END`; `return g.compile(checkpointer=checkpointer)`.
  - `run_assessment(app_name, target_url, persona_names, flow=None, seed=1337, artifact_root=None, run_id=None) -> dict`: open `SqliteSaver`, build graph, `invoke(init_state, config={"configurable":{"thread_id": run_id or uuid}})`, return `state["pack"]`.
- **MIRROR**: PURE_PER_PERSONA_SCORE, ATTACH-EXTRA-KEY, BEST-EFFORT; `orchestrator._requires_labels` logic.
- **IMPORTS**: `from langgraph.graph import StateGraph, END`; `from langgraph.types import Send`; `from langgraph.checkpoint.sqlite import SqliteSaver`; `from app.agents.persona_graph import build_persona_graph`; `from app.scoring.engine import score`; `from app.scoring.personas import load_persona, thresholds_for`; `from app.evidence.pack import build_pack, PersonaRunResult`; `from app.agents.llm import synthesize`; `from app.alerts import send_alerts`.
- **GOTCHA**: drive with sync `.invoke` (Task 4 #1). Concurrent Send → each persona node spawns its own browser; fine for 3. Seeds are `seed+i` so determinism holds under concurrency.
- **VALIDATE**: `test_run_graph.py` (Task 10).

### Task 7: Checkpointer wiring + resume
- **ACTION**: Configure `SqliteSaver` at a `settings.checkpoint_db` path; thread the `run_id` from the route as `thread_id`.
- **IMPLEMENT**: `run_assessment` accepts `run_id`; `compile(checkpointer=SqliteSaver.from_conn_string(settings.checkpoint_db))`; invoke with `thread_id=run_id`. Re-invoking the same `thread_id` resumes uncompleted personas.
- **GOTCHA**: live `page`/`rng`/`sync_playwright` are NOT serializable — keep them OUT of checkpointed top-level state (they live only inside the subgraph's in-process invoke). Checkpoint persists run-level RAW `persona_results`. **Spike-confirmed**: frozen `StepSignals`/`WcagSignal` round-trip fine, BUT (a) call `allowed_msgpack_modules` / register `app.scoring.engine` to avoid the future-version block warning, and (b) `tuple` fields come back as `list` — fine for the scorer, just don't assert tuple identity after a checkpoint.
- **VALIDATE**: `test_run_graph.py::test_resume_skips_completed_personas`.

### Task 8: Orchestrator + route + config + env
- **ACTION**: Point `orchestrator.run_assessment` at `run_graph.run_assessment` (keep signature + return shape); `routes/runs.py` generates `run_id` first and passes it; DeepSeek defaults in `config.py`/`.env.example`.
- **IMPLEMENT**: `config.py` — `llm_provider="deepseek"`, `llm_model_step="deepseek-v4-flash"`, `llm_model_synth="deepseek-v4-pro"`, `llm_base_url="https://api.deepseek.com"`, `checkpoint_db="checkpoints.sqlite"`. `.env.example` — same + `LLM_BASE_URL` + `CHECKPOINT_DB`; flip "OPEN DECISION (§25)" → "LOCKED: DeepSeek V4". `runs.py` — `run_id=str(uuid4())` then `orchestrator.run_assessment(..., run_id=run_id)`.
- **MIRROR**: CONFIG_SETTINGS; existing `runs.py` store/return.
- **GOTCHA**: keep the same `pack` + `screenshots` keys so `test_orchestrator.py` and the frontend stay green.
- **VALIDATE**: `.venv/bin/pytest tests/test_orchestrator.py -q`; `.venv/bin/python -c "from app.config import settings; print(settings.llm_model_synth)"` → `deepseek-v4-pro`.

### Task 9: Persona-subgraph tests
- **ACTION**: Create `backend/tests/test_persona_graph.py`.
- **IMPLEMENT** (mirror `test_nav_contract.py` fixtures): (a) `oku_visual` dead-ends at `otp`, `len(steps)==1`, `status=="blocked"`; (b) clean control page → both steps, `status=="completed"`; (c) **offline parity** — no key → confusion 1.0 at unlabeled OTP for label-dependent persona else 0.0, identical to pre-change; (d) **raw-only** — state stores no verdict, only raw `StepSignals`; (e) block does NOT loop back (no extra observe after block).
- **GOTCHA**: ensure `LLM_API_KEY` unset; assert no retry-on-block.
- **VALIDATE**: `.venv/bin/pytest tests/test_persona_graph.py -q`.

### Task 10: Run-graph tests
- **ACTION**: Create `backend/tests/test_run_graph.py`.
- **IMPLEMENT**: (a) fan-out 3 personas → 3 `persona_results`; (b) `aggregate` orders by `persona_idx` deterministically; (c) `score` node yields per-persona `ScoreResult`; (d) `evidence` produces a pack with `wcag_conformance` + `matrix` + `synthesis`; (e) the §14 hero diff — same OTP step green for control, red for `oku_visual`; (f) `test_resume_skips_completed_personas` via a checkpointer + same `thread_id`.
- **MIRROR**: TEST_STRUCTURE; `test_evidence.py`/`test_orchestrator.py` assertions.
- **GOTCHA**: in-memory or temp-file `SqliteSaver`; `LLM_API_KEY` unset (offline synth template).
- **VALIDATE**: `.venv/bin/pytest tests/test_run_graph.py -q`.

### Task 11: LLM tests
- **ACTION**: Create `backend/tests/test_llm.py`.
- **IMPLEMENT**: (a) offline `vision_judge` heuristic; (b) offline `synthesize` non-empty template; (c) monkeypatch `_client` → fake returning `VisionJudgment`, value flows through; (d) fake client raises → heuristic fallback, no raise.
- **MIRROR**: `test_alerts.py` helper-pack style.
- **GOTCHA**: patch `llm._client`; no network; Pydantic v2 (`model_dump`, `Field(ge=,le=)`).
- **VALIDATE**: `.venv/bin/pytest tests/test_llm.py -q`.

---

## Testing Strategy

### Unit / Contract / Integration
| Test | Input | Expected | Edge? |
|---|---|---|---|
| subgraph terminates on block | oku_visual @ flawed | 1 step, blocked P0 (after score) | yes |
| subgraph completes clean | visual @ control.html | 2 steps, completed | no |
| offline parity | no key | confusion == old hardcode | yes |
| raw-only state | any | no verdict stored, only StepSignals | yes |
| no retry-on-block | blocked persona | no second `observe` | yes |
| fan-out / fan-in | 3 personas | 3 persona_results, ordered | no |
| hero diff | same OTP step | control green, oku_visual red | yes |
| resume | re-invoke same thread_id | completed personas skipped | yes |
| vision_judge structured / error | mocked / raising client | honored / fallback | yes |
| synthesize offline | sample pack | non-empty rollup | yes |

### Edge Cases Checklist
- [ ] Empty `LLM_API_KEY` → deterministic fallback everywhere
- [ ] Malformed structured output → try/except fallback
- [ ] a11y locate fails AND no `fallback_target` → dead_end (today's behavior)
- [ ] Transient PW failure → RetryPolicy retries; persistent → dead_end (NOT retried away)
- [ ] sync Playwright under Send concurrency → no asyncio-loop error
- [ ] Checkpoint round-trip of `StepSignals`/`PersonaRunResult`
- [ ] navigator↔persona_graph import cycle

---

## Validation Commands
```bash
cd backend && .venv/bin/ruff check app tests                                  # zero lint
cd backend && .venv/bin/pytest tests/test_persona_graph.py tests/test_run_graph.py tests/test_llm.py tests/test_nav_contract.py tests/test_orchestrator.py -q   # all pass offline
cd backend && .venv/bin/pytest -q                                             # no regressions
cd backend && .venv/bin/python -c "from app.agents.run_graph import run_assessment; from app.agents.persona_graph import run_journey; print('ok')"   # import smoke
```
### Manual
- [ ] `uvicorn app.main:app`; `POST /runs` (control + oku_visual, fixture site) → pack has `synthesis.rollup`, matrix shows control-green/oku_visual-red at OTP.
- [ ] Kill mid-run, re-`POST` same flow → resume skips the completed persona (checkpointer).
- [ ] With real `LLM_API_KEY` → per-step `llm_confusion` varies (not just 0/1); narrative coherent.

---

## Acceptance Criteria
- [ ] All 11 tasks done; all validation commands pass
- [ ] Persona journey is a cyclic subgraph (observe/comprehend/decide/act/route_next); run is a `Send` fan-out + reducer fan-in graph
- [ ] `run_journey` contract unchanged; `test_nav_contract.py` green
- [ ] Scorer + `build_pack` core untouched; state stores RAW signals only (§16)
- [ ] `comprehend` is the only mandatory LLM node; synth is the only other LLM call; block is a clean exit (no LLM retry, §23)
- [ ] Offline runs deterministic and identical to pre-change behavior
- [ ] Per-persona resume works via checkpointer

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ~~sync Playwright inside asyncio loop under Send~~ | ~~Med~~ | ~~High~~ | **CLEARED by spike** — sync `.invoke` runs each persona subgraph in its own thread, no loop error. Keep: own `sync_playwright` per persona; never tear down inside a node |
| Live `page`/`rng` not checkpoint-serializable | Low | Med | keep them inside subgraph in-process invoke; **spike confirmed** domain dataclasses round-trip — register `app.scoring.engine` in `allowed_msgpack_modules` + treat checkpointed tuples as lists (Task 7) |
| `with_structured_output` bug (#31403) | Med | Med | `strict=True`/json_schema + try/except → fallback; pin & test version |
| LLM non-determinism vs §16/§20 | Med | High | temperature=0 + offline parity test; per-persona seed+i; aggregate reorders |
| Block-as-error temptation | Low | High | RetryPolicy transient-only; route_next exits on block; explicit test (9e) |
| navigator↔persona_graph cycle | Med | Low | function-local import (Task 5) |
| DeepSeek vision block / kwarg shape | Low | Med | isolated in `llm.py`; verify vs installed version; fallback covers it |

## Notes
- Design-review course-corrections folded in: two graphs not one; raw-signal state + pure scorer (§16); cognition concentrated in `comprehend` + one `synthesize`; block = product not error (§23); `decide` changes control flow via behavior profile, not prompt flavor (the §23 anti-costume seam).
- §20 sequential narration is preserved at the output layer (`aggregate` reorders); execution may be concurrent but each persona's `seed+i` keeps determinism.
- The differentiator (empathy replay) still runs on screenshots and the scorer stays pure — neither depends on the LLM working (§20/§23).
- The one genuine reason this top-level graph beats `asyncio.gather`: checkpoint/resume per persona (Task 7). If that ever proves not worth the machinery for the prelim, the persona subgraph still stands alone via `run_journey`.

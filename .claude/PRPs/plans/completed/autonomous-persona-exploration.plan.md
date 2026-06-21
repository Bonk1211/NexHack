# Plan: Autonomous Persona Exploration

## Summary
Today each persona drives a **fixed, pre-scripted `flow` list** (`FlowStep[]`) and the
subgraph simply indexes `flow[step_idx]` until the list is exhausted. Because the
default flow is only `[otp.fill, submit.click]` (both on page 1), the agent clicks
"Submit", the flow ends, and it **never observes the page it just navigated to**. This
plan replaces the scripted indexer with a **goal-driven agent loop**: the LLM looks at
the live accessibility tree + action history and chooses the *next* action each step,
so the persona explores the app on its own across pages until it reaches its goal,
hits a dead end, or hits a safety cap.

## User Story
As an accessibility auditor running an assessment,
I want each persona agent to explore the target app on its own (navigate across pages,
discover and operate controls) instead of replaying a hand-written step list,
So that I get inclusion evidence for the *whole* journey, not just the first screen.

## Problem → Solution
**Current**: `persona_graph` loop is `fs = state["flow"][state["step_idx"]]`; exit is
`next_idx >= len(state["flow"])` (`persona_graph.py:193`). Real runs fall back to
`DEFAULT_FLOW` (`run_graph.py:61`) = 2 first-page steps → page 2 never seen. Also there
is **no `wait_for_load_state` after a click** (`persona_graph.py:162-172`), so even a
multi-step flow would observe mid-navigation.
**Desired**: an LLM **action-planner** node chooses the next action from the live a11y
tree + history + a per-app goal. The loop runs until the planner says `done`, the
persona is blocked, or a `max_steps`/cycle safety cap trips. Navigation waits for load.
Scripted `flow` remains supported (dual-mode) so existing contract tests stay green.

## Metadata
- **Complexity**: Large
- **Source PRD**: N/A (free-form: "make the agent autonomous, explore the app themselves")
- **PRD Phase**: N/A
- **Estimated Files**: ~9 (6 changed, 1 new test, 2 touch-points)

---

## UX Design

### Before
```
┌──────────────────────────────────────────────┐
│ Persona column (LiveView)                     │
│ observe → comprehend → decide → act  (otp)    │
│ observe → comprehend → decide → act  (submit) │
│ done. ← agent stops on page 1 after submit    │
│ never sees the post-login page                │
└──────────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────┐
│ Persona column (LiveView)                     │
│ observe → plan → decide → act  click:Login    │  ← page 1
│ observe → plan → decide → act  fill:OTP       │
│ observe → plan → decide → act  click:Submit   │
│   ↳ wait_for_load_state → page 2 loads        │
│ observe → plan → decide → act  click:Pay      │  ← page 2, discovered live
│ observe → plan → decide → act  done           │
└──────────────────────────────────────────────┘
```

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| Frontend `NodeOutputCard` | shows node `comprehend`/`act` with scripted key | shows node `plan`/`act` with **dynamic** step_key (`click:Submit`) | `AssessmentRunner.tsx` `NODE_DOT` map should gain a `plan`/`observe` entry; not required (falls back to `bg-tertiary`) |
| Friction matrix columns | fixed `[otp, submit]` | variable per run (`click:Login`, `fill:OTP`, …) | `build_friction_matrix` already unions keys + fills `"na"` (`pack.py:69-95`) — **no change needed** |
| Per-app config | `flow_steps` in `apps` table | optional `goal` text per app; `flow_steps` still honored | new optional column; falls back to a default goal |

This is mostly an internal/agent change; the live UI and pack render unchanged because the
matrix and replay already tolerate variable-length, variable-key journeys.

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `backend/app/agents/persona_graph.py` | 50-227 | The cyclic loop being rewritten: `load/observe/comprehend/decide/act/route_next` + graph wiring |
| P0 | `backend/app/agents/llm.py` | 40-178 | `VisionJudgment` schema + `vision_judge` + the **offline-deterministic** pattern to mirror for the new planner |
| P0 | `backend/app/agents/navigator.py` | 26-73 | `FlowStep`, `NavConfig`, `JourneyResult`, `_role_has_name` contract + `run_journey` delegation |
| P0 | `backend/app/agents/state.py` | 29-100 | `PersonaInput`/`PersonaState` channels; **LangGraph drops undeclared keys** (line 71-72) |
| P1 | `backend/app/scoring/engine.py` | 30-128 | `StepSignals` shape + `_step_blocks`/`step_status` — what `act` must emit; cycle→`dead_end` |
| P1 | `backend/app/routes/runs.py` | 354-421 | SSE `stream_persona` consumer: node→event mapping (`observe/comprehend/decide/act`) — must follow the rename |
| P1 | `backend/app/agents/run_graph.py` | 60-101, 193-219 | `DEFAULT_FLOW`, `fan_out` payload, `run_assessment` signature — where `goal` threads in |
| P1 | `backend/app/evidence/pack.py` | 69-95 | Proof the matrix already handles variable step_keys (no change) |
| P2 | `backend/tests/test_nav_contract.py` | 1-82 | Contract tests that MUST stay green via scripted-mode back-compat |
| P2 | `backend/app/routes/runs.py` | 48-76 | `_resolve_flow` — sibling `_resolve_goal` added here |

## External Documentation

| Topic | Source | Key Takeaway |
|---|---|---|
| Playwright sync nav wait | https://playwright.dev/python/docs/navigations | After a click that navigates, call `page.wait_for_load_state("load")`; for SPA use `"networkidle"` as fallback. Sync API auto-waits for the click target but **not** the subsequent navigation. |
| `aria_snapshot` | https://playwright.dev/python/docs/aria-snapshots | `locator.aria_snapshot()` yields YAML-ish `- role "name"` lines — the exact text the planner reasons over; `page.accessibility` was removed (already noted `navigator.py:55-62`). |
| DeepSeek json_mode | (internal, `llm.py:15-25`) | V4 runs thinking-mode → use `response_format={"type":"json_object"}`, **not** tool-calling. Mirror `vision_judge` exactly. |

```
KEY_INSIGHT: The friction matrix already unions variable step_keys across personas and fills "na".
APPLIES_TO: pack.py / Results UI — no change needed for variable-length autonomous journeys.
GOTCHA: step_keys must be STABLE across personas for the matrix to align columns (same action → same key). Derive key deterministically from action+target, not from step_idx.

KEY_INSIGHT: Offline path (no LLM_API_KEY) must stay fully deterministic (§16/§22), tests run network-free.
APPLIES_TO: the new planner node — needs a deterministic heuristic explorer fallback, exactly like _heuristic_confusion.
GOTCHA: Math/random must come ONLY from the seeded state["rng"]; never time- or dict-order-dependent (aria_snapshot order is stable, so tree-order iteration is deterministic).

KEY_INSIGHT: LangGraph drops keys a node returns that aren't declared on PersonaState.
APPLIES_TO: every new scratch key (goal, action_history, current_action, step_count...) MUST be added to PersonaState in state.py.
```

---

## Patterns to Mirror

### OFFLINE_DETERMINISTIC_LLM_FALLBACK
```python
# SOURCE: backend/app/agents/llm.py:120-178
def vision_judge(screenshot_path, step_key, aria_excerpt, *, requires_labels, labeled, action):
    fallback = VisionJudgment(confusion=_heuristic_confusion(...), reason="offline heuristic", ...)
    client = _client(settings.llm_model_step)
    if client is None or not aria_excerpt:
        return fallback
    try:
        ...
        ai = client.invoke([SystemMessage(...), human], config={"response_format": {"type": "json_object"}})
        usage = getattr(ai, "usage_metadata", None) or {}
        record_usage(model_name or settings.llm_model_step, prompt_tokens, completion_tokens)
        payload = json.loads(_extract_text(ai.content))
        return VisionJudgment.model_validate(payload)
    except Exception as exc:
        logger.warning("comprehend LLM call failed (%s: %s); using offline heuristic", type(exc).__name__, exc)
        return fallback
```

### STRUCTURED_SCHEMA
```python
# SOURCE: backend/app/agents/llm.py:42-49
class VisionJudgment(BaseModel):
    confusion: float = Field(ge=0.0, le=1.0, description="...")
    reason: str = Field(default="", description="...")
    fallback_target: str | None = Field(default=None, description="...")
```

### NODE_RETURNS_DECLARED_SCRATCH
```python
# SOURCE: backend/app/agents/persona_graph.py:107-139  (decide)
def decide(state: PersonaState) -> dict:
    bp = _bp(state); rng = state["rng"]; fs = state["flow"][state["step_idx"]]
    ...
    return {"current_dwell": round(dwell, 2), "current_retries": retries,
            "current_label_block": label_block, "current_give_up": give_up}
# every returned key is declared in state.py PersonaState (state.py:71-85)
```

### ACT_EMITS_RAW_STEP_SIGNALS
```python
# SOURCE: backend/app/agents/persona_graph.py:177-205
step = StepSignals(step_idx=idx, step_key=fs.key, critical=fs.critical,
                   wcag=state.get("wcag", ()) if idx == 0 else (),
                   dwell_s=dwell, retries=retries, dead_end=dead_end,
                   completed=completed, llm_confusion=confusion, reading_grade=state.get("grade"))
return {"steps": [step], "shots": [state.get("current_shot")],
        "step_idx": next_idx, "status": status, "blocked_at": blocked_at}
```

### CONDITIONAL_LOOP_EDGE
```python
# SOURCE: backend/app/agents/persona_graph.py:208-226
def route_next(state): return "observe" if state.get("status") == "running" else END
...
g.add_conditional_edges("act", route_next, {"observe": "observe", END: END})
```

### SSE_NODE_EVENT_MAP
```python
# SOURCE: backend/app/routes/runs.py:386-415
for node, data in stream_persona(payload, on_frame=on_frame):
    if node == "observe": q.put({"type":"node","scope":"persona","node":"observe",...})
    elif node == "comprehend": q.put({...})   # rename target → "plan"
    elif node == "decide": q.put({...})
    elif node == "act": step = data["steps"][0]; ...
```

### CONTRACT_TEST_STRUCTURE
```python
# SOURCE: backend/tests/test_nav_contract.py:36-64
FLOW = [FlowStep("otp","fill",role="textbox",critical=True),
        FlowStep("submit","click",role="button",name="Submit",critical=True)]
@pytest.fixture(scope="module")
def flawed_control_journey():
    cfg = NavConfig(FLAWED, FLOW, behavior_profile=CONTROL_BP, requires_labels=False, seed=1)
    return run_journey(cfg)   # scripted mode MUST keep working
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `backend/app/agents/navigator.py` | UPDATE | Add `goal: str = ""` + `max_steps: int = 20` to `NavConfig`; keep `FlowStep`/`run_journey` contract |
| `backend/app/agents/state.py` | UPDATE | Add `goal`, `max_steps`, `action_history`, `current_action`, `step_count`, `seen_signatures` to `PersonaInput`/`PersonaState`; make `flow` optional |
| `backend/app/agents/llm.py` | UPDATE | New `AgentAction` schema + `plan_action(...)` planner with deterministic offline `_heuristic_explore(...)` |
| `backend/app/agents/persona_graph.py` | UPDATE | Replace scripted indexer: `comprehend`→`plan` (LLM action selection), rework `decide`/`act`/`route_next`, add nav-wait + cycle/step caps; dual-mode (scripted vs autonomous) |
| `backend/app/agents/run_graph.py` | UPDATE | Thread `goal`/`max_steps` through `fan_out` payload + `run_assessment`; keep `DEFAULT_FLOW` for back-compat |
| `backend/app/routes/runs.py` | UPDATE | `_resolve_goal(app_name)` sibling of `_resolve_flow`; pass `goal`; rename SSE `comprehend`→`plan` event branch; pass goal into `run_one` payload |
| `backend/tests/test_autonomous_nav.py` | CREATE | Autonomous-mode contract tests against `fixture-site` (offline heuristic path) |
| `backend/tests/test_nav_contract.py` | UPDATE (light) | Unchanged assertions; confirm scripted mode still passes (regression guard) |
| `frontend/components/AssessmentRunner.tsx` | UPDATE (optional) | Add `plan` to `NODE_DOT` map (line 293-300) for the renamed node dot; cosmetic |

## NOT Building
- **No vision/pixel model.** The DeepSeek endpoint is text-only (`llm.py:18-20`); the planner reasons over the a11y tree text, same as today. Screenshots remain capture-only for empathy replay.
- **No change to the scorer, pack, or two-stream discipline** (`engine.py`, `pack.py`). Autonomy changes *which* steps exist, not how they're scored.
- **No multi-tab / new-window handling**, no file uploads, no auth credential vault. Single page object, same-tab navigation only (out of scope; note as a risk).
- **No removal of scripted `flow` mode.** It stays for deterministic contract tests and for apps that define explicit `flow_steps`.
- **No frontend re-architecture.** At most a one-line `NODE_DOT` cosmetic addition.
- **No DB migration in this plan's critical path.** `goal` is resolved with a safe default if the column/value is absent (mirrors `_resolve_flow`'s fallback).

---

## Step-by-Step Tasks

### Task 1: Extend `NavConfig` with goal + cap (back-compat)
- **ACTION**: Add fields to `NavConfig` in `navigator.py`.
- **IMPLEMENT**:
  ```python
  @dataclass
  class NavConfig:
      target_url: str
      flow: list[FlowStep] = field(default_factory=list)  # was required; now optional (autonomous mode)
      goal: str = ""              # high-level task when flow is empty → autonomous exploration
      max_steps: int = 20         # safety cap on the autonomous loop
      viewport: str = "iPhone 13"
      behavior_profile: dict = field(default_factory=dict)
      requires_labels: bool = False
      seed: int = 1337
      artifact_dir: str | None = None
  ```
- **MIRROR**: existing `NavConfig` dataclass (`navigator.py:37-46`).
- **IMPORTS**: `field` already imported (`from dataclasses import dataclass, field`).
- **GOTCHA**: `flow` becoming optional must not break `NavConfig(FLAWED, FLOW, ...)` positional calls in `test_nav_contract.py:38`. Positional order is preserved (`flow` stays 2nd) → safe.
- **VALIDATE**: `python -c "from app.agents.navigator import NavConfig; NavConfig('u'); NavConfig('u', goal='log in and pay')"`.

### Task 2: Declare new state channels
- **ACTION**: Add channels to `PersonaInput` and `PersonaState` in `state.py`.
- **IMPLEMENT**:
  ```python
  # PersonaInput (serializable Send payload) — add:
  goal: str
  max_steps: int
  flow: list[FlowStep]            # already present; now may be []  (autonomous when empty)

  # PersonaState (subgraph scratch) — add:
  step_count: int                 # monotonic actions taken (separate from any flow index)
  action_history: list[dict]      # [{"key","action","role","name","reason"}] for planner context + cycle detection
  seen_signatures: list[str]      # action signatures already attempted, for loop detection
  current_action: dict            # the planner's chosen action for this superstep
  ```
- **MIRROR**: scratch-key declaration block (`state.py:71-85`) and the "MUST be declared" comment.
- **IMPORTS**: none new.
- **GOTCHA**: `action_history`/`seen_signatures` are single-writer per superstep (the loop is sequential within one persona) — do **not** wrap in `operator.add` (that would double-append on retries). Return the full updated list from the node each step.
- **VALIDATE**: `python -c "import app.agents.state"` imports clean.

### Task 3: Add the `AgentAction` schema + planner LLM function
- **ACTION**: In `llm.py`, add a Pydantic `AgentAction` and a `plan_action(...)` with an offline deterministic explorer.
- **IMPLEMENT**:
  ```python
  class AgentAction(BaseModel):
      """The planner's chosen next action (autonomous nav)."""
      action: str = Field(description="'click' | 'fill' | 'done' | 'blocked'")
      role: str = Field(default="", description="a11y role to target, e.g. 'button','textbox'")
      name: str = Field(default="", description="accessible name to match")
      value: str = Field(default="000000", description="text to type for 'fill'")
      key: str = Field(default="", description="stable step label, e.g. 'click:Submit'")
      confusion: float = Field(default=0.0, ge=0.0, le=1.0)
      reason: str = Field(default="")

  _PLAN_SYSTEM = (
      "You are simulating ONE user persona operating a mobile web app through its "
      "accessibility tree. Given the GOAL, the current a11y tree, and the actions already "
      "taken, choose the SINGLE next action that moves toward the goal. Prefer the "
      "accessibility tree as ground truth. Respond ONLY with JSON of exactly this shape: "
      '{"action":"click|fill|done|blocked","role":"","name":"","value":"","key":"",'
      '"confusion":0.0,"reason":""}. '
      "Use 'done' when the goal is achieved, 'blocked' when no control can advance it. "
      "Set key to a stable label like 'click:Submit' or 'fill:OTP' (action:Name)."
  )

  def _action_signature(a: dict) -> str:
      return f"{a.get('action')}:{a.get('role')}:{a.get('name')}".lower()

  def _heuristic_explore(aria: str, history: list[dict], rng) -> AgentAction:
      """Deterministic offline planner: fill unfilled textboxes (tree order), then click the
      first/primary actionable control, else done. Mirrors a real user clearing a form then advancing."""
      done_sigs = { _action_signature(h) for h in history }
      # parse "- role \"name\"" lines from aria_snapshot, in stable tree order
      controls = _parse_aria_controls(aria)   # [(role,name)] helper, see Task 3b
      for role, name in controls:
          if role in ("textbox","searchbox","combobox"):
              sig = f"fill:{role}:{name}".lower()
              if sig not in done_sigs:
                  return AgentAction(action="fill", role=role, name=name, value="000000",
                                     key=f"fill:{name or role}", reason="offline: fill field")
      for role, name in controls:
          if role in ("button","link","checkbox"):
              sig = f"click:{role}:{name}".lower()
              if sig not in done_sigs:
                  return AgentAction(action="click", role=role, name=name,
                                     key=f"click:{name or role}", reason="offline: advance")
      return AgentAction(action="done", key="done", reason="offline: nothing left to do")

  def plan_action(aria: str, goal: str, history: list[dict], rng) -> AgentAction:
      fallback = _heuristic_explore(aria, history, rng)
      client = _client(settings.llm_model_step)
      if client is None or not aria:
          return fallback
      try:
          from langchain_core.messages import HumanMessage, SystemMessage
          human = HumanMessage(content=(
              f"GOAL: {goal}\nActions taken so far: {json.dumps(history[-8:])}\n"
              f"Accessibility tree:\n{aria[:2500]}\nChoose the next action. Respond in JSON."))
          ai = client.invoke([SystemMessage(content=_PLAN_SYSTEM), human],
                             config={"response_format": {"type": "json_object"}})
          usage = getattr(ai, "usage_metadata", None) or {}
          record_usage(getattr(client,"model",settings.llm_model_step),
                       usage.get("input_tokens") or usage.get("prompt_tokens"),
                       usage.get("output_tokens") or usage.get("completion_tokens"))
          return AgentAction.model_validate(json.loads(_extract_text(ai.content)))
      except Exception as exc:
          logger.warning("plan_action LLM call failed (%s: %s); using offline explorer",
                         type(exc).__name__, exc)
          return fallback
  ```
- **MIRROR**: `vision_judge` exactly — client factory, `json_object` response_format, `record_usage`, try/except→fallback, `_extract_text` (`llm.py:104-178`).
- **IMPORTS**: reuse existing (`json`, `logging`, `BaseModel`, `Field`, `settings`, `record_usage`).
- **GOTCHA**: randomness must come only from the passed `rng` (here the heuristic is deterministic without rng; keep the param so a future hesitation/misinterpret hook is seeded, mirroring `decide`). Truncate `aria` (2500) and `history` (last 8) to bound tokens.
- **VALIDATE**: `python -c "from app.agents.llm import plan_action, AgentAction; import random; print(plan_action('- textbox\n- button \"Submit\"','log in',[],random.Random(1)))"` returns a fill action offline.

### Task 3b: a11y-tree control parser helper
- **ACTION**: Add `_parse_aria_controls(aria) -> list[tuple[str,str]]` (role, name in tree order) in `llm.py` (or `navigator.py` next to `_role_has_name`).
- **IMPLEMENT**:
  ```python
  _ARIA_LINE = re.compile(r'^\s*-\s+(?P<role>[a-z]+)(?:\s+"(?P<name>[^"]*)")?', re.MULTILINE)
  def _parse_aria_controls(aria: str) -> list[tuple[str, str]]:
      return [(m.group("role"), m.group("name") or "") for m in _ARIA_LINE.finditer(aria or "")]
  ```
- **MIRROR**: regex style of `_role_has_name` (`navigator.py:54-62`).
- **IMPORTS**: `import re` (already in `navigator.py`; add to `llm.py` if placed there).
- **GOTCHA**: keep it in **one** module to avoid a navigator↔llm import cycle; `llm.py` is the safer home (navigator already imports from scoring only). Function-local import if cross-referenced.
- **VALIDATE**: parser returns `[("textbox",""),("button","Submit")]` for the sample tree.

### Task 4: Rewrite the persona subgraph loop (dual-mode)
- **ACTION**: In `persona_graph.py`, rename `comprehend`→`plan`, rework `decide`/`act`/`route_next`, add nav-wait, and branch scripted vs autonomous on `state.get("flow")`.
- **IMPLEMENT** (key deltas):
  - `load`: init counters — `return {"step_count": 0, "status": "running", "action_history": [], "seen_signatures": []}`.
  - `observe`: unchanged capture, but axe/grade gate on `step_count == 0` instead of `step_idx == 0` (`persona_graph.py:69`).
  - `plan` (was `comprehend`):
    ```python
    def plan(state):
        flow = state.get("flow") or []
        if flow:  # SCRIPTED back-compat: synthesize an action from the FlowStep
            if state["step_count"] >= len(flow):
                return {"current_action": {"action": "done", "key": "done"}, "last_confusion": 0.0}
            fs = flow[state["step_count"]]
            labeled = _role_has_name(state.get("aria",""), fs.role) if fs.role else True
            j = vision_judge(state.get("current_shot"), fs.key, state.get("aria",""),
                             requires_labels=state.get("requires_labels",False), labeled=labeled, action=fs.action)
            act = {"action": fs.action, "role": fs.role, "name": fs.name, "value": fs.value,
                   "key": fs.key, "critical": fs.critical}
            return {"current_action": act, "last_confusion": j.confusion,
                    "last_reason": j.reason, "current_labeled": labeled}
        # AUTONOMOUS:
        a = plan_action(state.get("aria",""), state.get("goal",""), state.get("action_history",[]), state["rng"])
        labeled = _role_has_name(state.get("aria",""), a.role) if a.role else True
        return {"current_action": a.model_dump() | {"critical": True}, "last_confusion": a.confusion,
                "last_reason": a.reason, "current_labeled": labeled}
    ```
    (Autonomous steps are treated `critical=True` so a block on them is a P0 finding, consistent with the demo flow's criticality.)
  - `decide`: same behavior model, but read `fs = state["current_action"]` (a dict) and gate `label_block` on `act["action"]=="fill"`. Add **cycle detection**: if `_action_signature(act) in seen_signatures` → set `current_give_up=True` (loop → blocked). Add **step-cap**: if `step_count >= max_steps` → `current_give_up=True`.
  - `act`:
    ```python
    def act(state):
        page = state["page"]; act = state["current_action"]; idx = state["step_count"]
        dwell = state.get("current_dwell",0.0); retries = state.get("current_retries",0)
        dead_end, completed, confusion = False, True, state.get("last_confusion",0.0)
        action = act.get("action")
        if action == "done":
            status = "completed"
            return {"step_count": idx, "status": status, "blocked_at": None}  # no new step row
        if state.get("current_label_block") or action == "blocked":
            dead_end, completed = True, False
        elif action in ("fill","click"):
            try:
                if action == "fill":
                    page.get_by_role(act["role"]).first.fill(act.get("value","000000"), timeout=3000)
                elif act.get("name"):
                    page.get_by_role(act["role"], name=act["name"]).first.click(timeout=3000)
                    page.wait_for_load_state("load", timeout=5000)   # NAV WAIT (fix)
                else:
                    page.get_by_role(act["role"]).first.click(timeout=3000)
                    page.wait_for_load_state("load", timeout=5000)
            except Exception:
                dead_end, completed = True, False
        if state.get("current_give_up"):
            dead_end, completed = True, False
        step = StepSignals(step_idx=idx, step_key=act.get("key") or f"step{idx}",
                           critical=bool(act.get("critical", True)),
                           wcag=state.get("wcag",()) if idx == 0 else (),
                           dwell_s=dwell, retries=retries, dead_end=dead_end, completed=completed,
                           llm_confusion=confusion, reading_grade=state.get("grade"))
        sig = _action_signature(act)
        status = "blocked" if dead_end else "running"
        blocked_at = act.get("key") if dead_end else None
        return {"steps": [step], "shots": [state.get("current_shot")],
                "step_count": idx + 1, "status": status, "blocked_at": blocked_at,
                "action_history": state.get("action_history",[]) + [{"key": act.get("key"), **{k:act.get(k) for k in ("action","role","name","reason")}}],
                "seen_signatures": state.get("seen_signatures",[]) + [sig]}
    ```
  - `route_next`: `return "observe" if state.get("status") == "running" else END` (unchanged).
  - Graph wiring: rename node `"comprehend"`→`"plan"`; edges `observe→plan→decide→act`; `add_conditional_edges("act", route_next, {"observe":"observe", END:END})`.
- **MIRROR**: existing `decide`/`act` structure (`persona_graph.py:107-205`); `_action_signature` from llm.py (import it).
- **IMPORTS**: `from app.agents.llm import vision_judge, plan_action, _action_signature` (extend line 37).
- **GOTCHA**:
  - Use `step_count` everywhere the old code used `step_idx`; you can drop the old `step_idx` indexer entirely (keep the channel for back-compat but unused). Don't index `state["flow"][...]` in `decide`/`act` anymore.
  - `done` returns NO step row → the loop ends cleanly with `completed`; ensure `route_next` sees `status="completed"`.
  - `wait_for_load_state` must be wrapped so a no-nav click (e.g. checkbox) timing out doesn't false-block — use a short timeout and swallow `TimeoutError` (it's fine if there was no navigation).
  - The autonomous block treats every action `critical=True`; if that over-reports P0, make criticality a goal-config later (out of scope).
- **VALIDATE**: `cd backend && python -m pytest tests/test_nav_contract.py -q` (scripted mode unchanged) passes.

### Task 5: Handle the load-state-after-click edge precisely
- **ACTION**: Wrap nav-wait so non-navigating clicks don't block.
- **IMPLEMENT**:
  ```python
  from playwright.sync_api import TimeoutError as PWTimeout
  def _click_and_settle(page, locator):
      url_before = page.url
      locator.click(timeout=3000)
      try:
          page.wait_for_load_state("load", timeout=5000)
      except PWTimeout:
          pass   # SPA or in-page action: no full nav, that's OK
  ```
- **MIRROR**: try/except interaction pattern (`persona_graph.py:163-172`).
- **IMPORTS**: `from playwright.sync_api import TimeoutError as PWTimeout`.
- **GOTCHA**: Don't treat a nav-wait timeout as a dead end — only a failed `.click()` itself is a block.
- **VALIDATE**: clicking a same-page control in a unit test does not set `dead_end`.

### Task 6: Thread `goal`/`max_steps` through the run graph
- **ACTION**: In `run_graph.py`, add to the `fan_out` payload and `run_assessment` signature; default goal when none.
- **IMPLEMENT**:
  - `run_assessment(..., flow=None, goal: str = "", max_steps: int = 20, ...)`.
  - `init_state`: add `"goal": goal`, `"max_steps": max_steps`. If both `flow` is None/empty **and** `goal==""`, fall back to `DEFAULT_FLOW` (preserve current demo behavior) — autonomy only kicks in when a goal is supplied or flow is explicitly empty + goal set.
  - `fan_out` payload (`run_graph.py:86-99`): add `"goal": state.get("goal","")`, `"max_steps": state.get("max_steps",20)`, and pass `state["flow"]` (may be []).
- **MIRROR**: `fan_out` payload dict + `run_assessment` body (`run_graph.py:81-219`).
- **IMPORTS**: none new.
- **GOTCHA**: `RunState` must declare `goal`/`max_steps` (`state.py:103-124`) or LangGraph drops them. Add them there.
- **VALIDATE**: `python -c "from app.agents.run_graph import run_assessment"` imports; a goal run uses autonomous mode (manual smoke in Task 9).

### Task 7: Resolve a per-app goal + rename SSE event branch
- **ACTION**: In `runs.py`, add `_resolve_goal(app_name)` mirroring `_resolve_flow`; pass goal into both `start_run` and the SSE `run_one` payload; rename the `comprehend` event branch to `plan`.
- **IMPLEMENT**:
  - `_resolve_goal`: read `apps.goal` (or a `flow_steps`-style column); fall back to a sensible default e.g. `"Complete the primary task: log in / verify and reach the main screen."` Use the same try/except→default shape as `_resolve_flow` (`runs.py:48-76`).
  - In `run_one` payload (`runs.py:364-375`): set `"flow": _resolve_flow(app_name)` → if that returns `DEFAULT_FLOW` *and* a goal exists, prefer autonomous (`"flow": []`, `"goal": _resolve_goal(app_name)`, `"max_steps": 20`). Decision helper: `flow, goal = _resolve_journey(app_name)`.
  - SSE consumer (`runs.py:392`): change `elif node == "comprehend":` → `elif node == "plan":` and emit `"node": "plan"` with `output` carrying `confusion`/`reason`/`current_action`.
  - `start_run` (`runs.py:262-296`): pass `goal=`/`max_steps=` to `orchestrator.run_assessment`.
- **MIRROR**: `_resolve_flow` (`runs.py:48-76`) and the SSE branch block (`runs.py:386-415`).
- **IMPORTS**: none new.
- **GOTCHA**: `stream_persona` yields the **node name** — it must match the renamed graph node `"plan"`. If you forget the rename in one place, the live feed silently shows nothing for that node (no crash). Grep both files for `"comprehend"`.
- **VALIDATE**: `grep -rn '"comprehend"\|comprehend' backend/app` returns only docstring mentions, not live node strings.

### Task 8: Orchestrator passthrough
- **ACTION**: `orchestrator.run_assessment` (`app/orchestrator.py:25-40`) forwards `goal`/`max_steps`.
- **IMPLEMENT**: add `goal: str = ""`, `max_steps: int = 20` params and pass to `_run_assessment(...)`.
- **MIRROR**: existing passthrough signature there.
- **IMPORTS**: none.
- **VALIDATE**: `python -c "import app.orchestrator"` clean.

### Task 9: Autonomous contract tests
- **ACTION**: New `backend/tests/test_autonomous_nav.py` — exercise the offline heuristic explorer against `fixture-site/index.html`, asserting the agent (a) takes >1 step, (b) fills then clicks, (c) terminates (done or blocked) within `max_steps`, (d) screenshots every emitted step.
- **IMPLEMENT**:
  ```python
  import pathlib, pytest
  from app.agents.navigator import NavConfig, run_journey
  ROOT = pathlib.Path(__file__).resolve().parents[2]
  FLAWED = (ROOT/"fixture-site"/"index.html").as_uri()
  BP = {"dwell_multiplier":1.0,"reading_speed_wpm":220,"hesitation_prob":0.0,"giveup_threshold_s":60}

  def test_autonomous_explores_form():
      cfg = NavConfig(FLAWED, goal="Enter the code and submit", behavior_profile=BP, seed=1, max_steps=10)
      j = run_journey(cfg)
      keys = [s.step_key for s in j.steps]
      assert len(j.steps) >= 1
      assert any(k.startswith("fill") for k in keys)     # it discovered the textbox
      assert len(j.steps) <= 10                          # cap respected

  def test_autonomous_terminates(tmp_path):
      cfg = NavConfig(FLAWED, goal="do the task", behavior_profile=BP, seed=1,
                      max_steps=8, artifact_dir=str(tmp_path))
      j = run_journey(cfg)
      shots = [s for s in j.screenshots if s]
      assert len(shots) == len(j.steps)                  # FR-1.3 every step
  ```
- **MIRROR**: `test_nav_contract.py` fixtures/style (`test_nav_contract.py:36-82`).
- **IMPORTS**: as above.
- **GOTCHA**: tests run **offline** (no `LLM_API_KEY` in CI) → exercise `_heuristic_explore`, which must be deterministic. The fixture's exact a11y tree determines `keys`; if the fixture textbox has no accessible name, `key` becomes `fill:textbox` — assert on prefix, not exact name.
- **VALIDATE**: `cd backend && python -m pytest tests/test_autonomous_nav.py -q` passes offline.

### Task 10: (Optional) Frontend node-dot cosmetic
- **ACTION**: Add `plan` to `NODE_DOT` in `AssessmentRunner.tsx:293-300`.
- **IMPLEMENT**: `plan: "bg-friction",` (reuse the old comprehend color).
- **MIRROR**: existing `NODE_DOT` map.
- **GOTCHA**: purely cosmetic — unknown nodes already fall back to `bg-tertiary` (`AssessmentRunner.tsx:390-391`). Skip if time-boxed.
- **VALIDATE**: `cd frontend && npx tsc --noEmit`.

---

## Testing Strategy

### Unit Tests
| Test | Input | Expected Output | Edge Case? |
|---|---|---|---|
| `_parse_aria_controls` | `- textbox\n- button "Submit"` | `[("textbox",""),("button","Submit")]` | empty/malformed tree → `[]` |
| `_heuristic_explore` first call | tree w/ unfilled textbox | `action="fill"` | no controls → `action="done"` |
| `_heuristic_explore` after fill in history | same tree, history has the fill sig | `action="click"` | all clicked → `done` |
| cycle detection (`decide`) | action sig already in `seen_signatures` | `current_give_up=True` | — |
| step cap (`decide`) | `step_count >= max_steps` | `current_give_up=True` | exactly at cap |
| `plan` scripted mode | non-empty `flow` | synthesizes action from `FlowStep` (back-compat) | `step_count>=len(flow)` → `done` |
| nav-wait | click that doesn't navigate | no `dead_end` despite load-state timeout | SPA |
| autonomous offline e2e | `fixture-site/index.html`, goal | ≥1 step, fills then clicks, terminates ≤max_steps | blocked persona |

### Edge Cases Checklist
- [ ] Empty a11y tree (blank page after nav) → planner returns `done`/`blocked`, no crash
- [ ] `max_steps` reached → clean `blocked` exit, not infinite loop
- [ ] Same action repeated (cycle) → `seen_signatures` trips `give_up`
- [ ] Click that triggers no navigation → not a false dead end
- [ ] Offline (no API key) → deterministic heuristic, tests network-free (§22)
- [ ] Scripted `flow` still drives the old 2-step journey (regression)
- [ ] Persona that depends on labels still label-blocks on an unlabeled fill

---

## Validation Commands

### Static Analysis
```bash
cd backend && python -m pyflakes app/agents/persona_graph.py app/agents/llm.py app/agents/state.py app/agents/run_graph.py app/routes/runs.py
```
EXPECT: zero errors (or match the repo's existing lint baseline)

### Unit Tests (affected area)
```bash
cd backend && python -m pytest tests/test_nav_contract.py tests/test_autonomous_nav.py tests/test_persona_graph.py -q
```
EXPECT: all pass (scripted regression + new autonomous)

### Full Test Suite
```bash
cd backend && python -m pytest -q
```
EXPECT: no regressions

### Browser Validation
```bash
cd backend && uvicorn app.main:app --reload    # then run an assessment from the frontend with NO flow_steps but a goal set
```
EXPECT: the live persona column shows MORE than 2 act steps and a screenshot from a post-navigation page

### Manual Validation
- [ ] Start a run against a 2-page fixture/app with a goal, no `flow_steps`
- [ ] Live feed shows `observe → plan → decide → act` repeating across a page boundary
- [ ] At least one `act` step's screenshot is from the second page
- [ ] Run terminates (done or blocked) within `max_steps`; no hang
- [ ] Friction matrix renders variable columns (`fill:OTP`, `click:Submit`, …) with `na` where a persona diverged

---

## Acceptance Criteria
- [ ] Autonomous mode: a persona navigates beyond page 1 and emits steps for discovered controls
- [ ] Scripted mode (`flow` non-empty) unchanged — `test_nav_contract.py` green
- [ ] Loop always terminates: `done` | `blocked` | `max_steps` | cycle
- [ ] `wait_for_load_state` after navigating clicks; non-nav clicks not mis-flagged
- [ ] Offline determinism preserved; full suite passes network-free
- [ ] SSE live feed reflects the renamed `plan` node
- [ ] No type/lint errors

## Completion Checklist
- [ ] New code mirrors `vision_judge`'s offline-fallback shape exactly
- [ ] Every new node-returned key is declared on `PersonaState`/`PersonaInput`/`RunState`
- [ ] `record_usage` called on the planner LLM path (token ticker stays accurate)
- [ ] step_keys are stable across personas (action:Name), so the matrix aligns
- [ ] `"comprehend"` node string fully renamed to `"plan"` in graph + SSE consumer
- [ ] Tests follow `test_nav_contract.py` patterns
- [ ] No hardcoded API behavior; offline path deterministic

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Infinite/looping exploration | Med | High | `max_steps` cap + `seen_signatures` cycle detection both set `give_up` → blocked exit |
| Non-determinism breaks §22 tests | Med | High | Offline heuristic explorer is pure + tree-order; RNG only via seeded `state["rng"]`; assert on key *prefixes* |
| `wait_for_load_state` false-blocks non-nav clicks | Med | Med | Short timeout, swallow `PWTimeout`; only failed `.click()` is a dead end |
| LLM picks a control not in the tree | Med | Med | `get_by_role(...).first` raises → caught → dead_end (a real finding, not a crash); planner prompt says "tree is ground truth" |
| Variable step_keys misalign the matrix | Low | Med | Deterministic `action:Name` keys; matrix already unions + `na`-fills (`pack.py:69-95`) |
| New-tab / multi-window flows | Low | Med | Out of scope; single page object only — documented in NOT Building, note as follow-up |
| Autonomous `critical=True` over-reports P0 | Low | Low | Acceptable for v1; make criticality goal-configurable later |
| SSE node rename missed in one spot | Low | Low | Grep gate in Task 7 validation |

## Notes
- The **two latent bugs** the user hit are both fixed here: (1) only-first-page = scripted
  `DEFAULT_FLOW` had no page-2 steps → replaced by goal-driven exploration; (2) missing
  `wait_for_load_state` after click → added in `act`/`_click_and_settle`.
- **Dual-mode** is deliberate: keeps the defensible deterministic contract tests (§16/§22)
  intact while making autonomy the default for real app runs (goal supplied).
- Downstream (scorer, pack, friction matrix, empathy replay, SSE columns) needs **no
  structural change** — they already tolerate variable-length, variable-key journeys. The
  blast radius is the agent loop + its inputs, not the evidence pipeline.
- Cognition stays concentrated in one LLM node (now `plan`), preserving the §15/§25
  "one mandatory per-step LLM call" architecture — `plan_action` replaces `vision_judge`
  as that call in autonomous mode; `vision_judge` remains the call in scripted mode.
```

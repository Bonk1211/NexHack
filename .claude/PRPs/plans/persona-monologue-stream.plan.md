# Plan: Streaming persona monologue during assessment

## Summary
During a live assessment, each persona drives the target app step by step (observe→plan→decide→act). Today the live feed shows mechanical node cards (`action: click, target: Continue, reason: …`). This adds a **first-person monologue** — the persona "thinking out loud" as it interacts ("Hmm, where do I tap to keep going? This text is small… let me try the green Continue button") — generated in the persona's own voice and streamed to the live view with a typewriter reveal paced to the persona's reading speed.

## User Story
As a stakeholder watching an assessment run, I want each simulated persona to narrate what it's experiencing in plain first-person language, so that the agent reads like a real user struggling/succeeding — not a robot dumping JSON.

## Problem → Solution
Live feed today = terse node output cards, persona-blind LLM planner (the per-step LLM call never even sees who the persona *is*). → The existing per-step planner call also emits a short first-person `say` line in the persona's voice; it's streamed on the `plan` SSE event and rendered as a paced chat-bubble feed per persona.

## Metadata
- **Complexity**: Medium
- **Source PRD**: N/A (free-form feature)
- **PRD Phase**: N/A
- **Estimated Files**: 5 (3 backend, 2 frontend)

---

## UX Design

### Before
```
┌──────────────────────────┐
│ Siti · plan              │
│ action   click           │
│ target   Continue        │
│ confusion 0.20           │
│ reason   advance to next │
└──────────────────────────┘
```

### After
```
┌──────────────────────────┐
│ 🧓 Siti                  │
│ ┌──────────────────────┐ │
│ │ "Okay… a lot of words│ │  ← typewriter reveal,
│ │  here. I think the   │ │    paced to her 120 wpm
│ │  green button keeps  │ │
│ │  me going. Tapping   │ │
│ │  Continue."          │ │
│ └──────────────────────┘ │
│ (node cards still avail. │
│  as a collapsed detail)  │
└──────────────────────────┘
```

### Interaction Changes
| Touchpoint | Before | After | Notes |
|---|---|---|---|
| Live persona column | node-output cards only | monologue bubbles (primary) + node cards (kept) | Same SSE stream, one new field |
| Pacing | cards appear at node boundary | text reveals char-by-char, speed ∝ persona reading_speed_wpm | Frontend-only typewriter |
| Voice | none (planner is persona-blind) | planner is handed persona name/traits, speaks first-person | Reuses the existing per-step LLM call |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `backend/app/agents/llm.py` | 59-69, 196-233, 509-570 | `AgentAction` schema + `plan_action` (the one per-step LLM call to extend) |
| P0 | `backend/app/agents/persona_graph.py` | 223-288 | `plan` node — where `plan_action` is called and its result mapped to state |
| P0 | `backend/app/routes/runs.py` | 440-500 | persona payload build + per-node SSE emission (`plan` event at 473-480) |
| P0 | `frontend/components/AssessmentRunner.tsx` | 46-101, 388-424, 494-562 | `LiveState`/`reduce`, `NodeOutputCard`, `PersonaColumn` feed |
| P1 | `frontend/lib/live.ts` | 149-203 | `StreamEvent` union + SSE client |
| P1 | `backend/app/agents/state.py` | 29-52 | `PersonaInput` — add the `persona_voice` channel here |
| P1 | `backend/app/scoring/personas.py` | 47-71 | persona config shape (name/disabilities/language; DB rows drop behavior_prompt) |
| P2 | `personas/elderly_low_literacy.json` | all | concrete persona voice inputs (name, patience, tech_savviness, behavior_prompt) |

## External Documentation
No external research needed — feature uses established internal patterns (LangGraph node→SSE→React reducer, already in place for nodes/frames).

---

## Patterns to Mirror

### STRUCTURED_LLM_FIELD (add a field to an existing pydantic schema + json_mode call)
```python
# SOURCE: backend/app/agents/llm.py:59-69
class AgentAction(BaseModel):
    action: str = Field(description="'click' | 'fill' | 'navigate_back' | 'done' | 'blocked'")
    role: str = Field(default="", ...)
    ...
    confusion: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")
```
The model is validated at `AgentAction.model_validate(payload)` (llm.py:566). Adding an optional field with a default is backward-safe: offline/old payloads still validate.

### OFFLINE_FALLBACK (every LLM helper degrades deterministically — §16/§22)
```python
# SOURCE: backend/app/agents/llm.py:516-519
fallback = _heuristic_explore(aria, history, rng, current_screen_key=current_screen_key)
client = _client(settings.llm_model_step)
if client is None or not aria:
    return fallback
```
Any new prompt content must have a templated offline equivalent so tests stay network-free.

### NODE_RETURNS_STATE_DICT (plan node maps action → declared state keys)
```python
# SOURCE: backend/app/agents/persona_graph.py:284-288
labeled = _role_has_name(state.get("aria", ""), a.role) if a.role else True
action = a.model_dump()
action["critical"] = True
return {"current_action": action, "last_confusion": a.confusion,
        "last_fallback": None, "last_reason": a.reason, "current_labeled": labeled}
```
GOTCHA (state.py:84-98 comment): LangGraph DROPS undeclared keys returned by a node. Any new scratch key (e.g. `current_say`) MUST be declared in `PersonaState`.

### SSE_NODE_EMIT (worker pushes a dict; client routes by persona)
```python
# SOURCE: backend/app/routes/runs.py:473-480
elif node == "plan":
    act = data.get("current_action") or {}
    q.put({"type": "node", "scope": "persona", "persona": name,
           "node": "plan", "confusion": data.get("last_confusion"),
           "output": {"action": act.get("action"),
                      "target": act.get("name") or act.get("role"),
                      "confusion": data.get("last_confusion"),
                      "reason": data.get("last_reason")}})
```

### REACT_SSE_REDUCER (pure reducer folds each event into LiveState)
```ts
// SOURCE: frontend/components/AssessmentRunner.tsx:78-83
if (e.type === "node" && e.scope === "persona") {
  return push(s, {
    scope: "persona", node: e.node, persona: e.persona,
    output: e.output, screenshot_url: e.screenshot_url ?? undefined,
  });
}
```

### PERSONA_VOICE_INPUTS (what's available to build the voice)
```python
# SOURCE: backend/app/scoring/personas.py:47-71 + personas/elderly_low_literacy.json
# JSON personas carry: name, tech_savviness, patience, language, disabilities, behavior_prompt
# DB rows (via _row_to_persona_config) carry: name, label, language, disabilities (NO behavior_prompt/patience)
```
GOTCHA: build `persona_voice` from whatever keys exist (`cfg.get(...)`), don't assume `behavior_prompt`.

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `backend/app/agents/llm.py` | UPDATE | Add `say` to `AgentAction`; pass persona voice into `plan_action`; prompt + offline template for the monologue line |
| `backend/app/agents/state.py` | UPDATE | Declare `persona_voice` (input) and `current_say` (scratch) — else LangGraph drops them |
| `backend/app/agents/persona_graph.py` | UPDATE | `plan` node: pass `state["persona_voice"]` to `plan_action`, return `current_say` |
| `backend/app/routes/runs.py` | UPDATE | Build `persona_voice` from `cfg`; put it in payload; add `monologue` to the `plan` SSE event |
| `frontend/lib/live.ts` | UPDATE | Add optional `monologue?: string` to the persona `node` event type |
| `frontend/components/AssessmentRunner.tsx` | UPDATE | Carry monologue in `NodeCardItem`; render a typewriter chat-bubble in `PersonaColumn` |

## NOT Building
- No new LLM call. The monologue rides the existing per-step `plan_action` call (one extra output field). No extra latency, no extra cost line.
- No TTS / audio. Text monologue only.
- No monologue on `observe`/`decide`/`act` nodes — one line per step, emitted on `plan`, is enough to read as a person. (Add later only if a step's *outcome* needs a reaction.)
- No persistence of monologue text in the evidence pack. It's a live-view affordance; the pack already has captions/replay.
- No i18n rendering work — if the persona `language` is non-English the model may answer in that language; we render whatever comes back.

---

## Step-by-Step Tasks

### Task 1: Add `say` to AgentAction
- **ACTION**: Add an optional field to the planner schema.
- **IMPLEMENT**: In `AgentAction` (llm.py:59-69) add
  `say: str = Field(default="", description="ONE short first-person sentence in the persona's voice — what they're thinking/feeling as they do this action. No JSON, no meta.")`
- **MIRROR**: STRUCTURED_LLM_FIELD.
- **GOTCHA**: Keep `default=""` so old/offline payloads still `model_validate`.
- **VALIDATE**: `python -c "from app.agents.llm import AgentAction; print(AgentAction().say == '')"` → `True`.

### Task 2: Thread persona voice into plan_action
- **ACTION**: Give the planner persona context (it's currently persona-blind) and ask for `say`.
- **IMPLEMENT**:
  - Change signature: `def plan_action(aria, goal, history, rng, *, current_screen_key="", hints=None, persona_voice: str = "") -> AgentAction:` (llm.py:509-510).
  - In the human message (llm.py:540-554) prepend a `PERSONA: {persona_voice}` line when non-empty, and add to the system prompt (`_PLAN_SYSTEM`, llm.py:196-233) a closing instruction: *"Also set `say` to ONE short first-person sentence in this persona's voice describing what you're thinking/feeling as you take this action (e.g. doubt, relief, confusion). Stay in character; never mention being an AI, a test, or a11y trees."*
- **MIRROR**: existing human-message build (llm.py:540-554).
- **GOTCHA**: `persona_voice` defaults to `""` → behavior unchanged when not supplied (keeps `test_persona_graph.py` green).
- **VALIDATE**: existing tests pass: `cd backend && .venv/bin/python -m pytest tests/test_persona_graph.py -q`.

### Task 3: Offline template for `say`
- **ACTION**: Make `say` non-empty even with no API key (offline path returns `_heuristic_explore`).
- **IMPLEMENT**: In `_heuristic_explore` (llm.py:456-506), set `say` on the returned `AgentAction` from a tiny template keyed on the chosen verb, e.g.
  `fill→"Let me type my {name or 'details'} here."`, `click→"I'll tap {name}."`, `navigate_back→"Nothing left here — let me go back."`, `done→"Looks like I'm all done."`. Keep it generic (no persona traits needed offline).
- **MIRROR**: OFFLINE_FALLBACK.
- **VALIDATE**: `LLM_API_KEY` unset → run a persona; every `plan` event has a non-empty monologue (manual, Task 8).

### Task 4: Declare state channels
- **ACTION**: Stop LangGraph from dropping the new keys.
- **IMPLEMENT**: In `state.py`, add to `PersonaInput` (29-52): `persona_voice: str`. Add to `PersonaState` scratch block (85-98): `current_say: str`.
- **MIRROR**: existing declarations + the §"MUST be declared" comment (state.py:84).
- **GOTCHA**: Without this the `plan` node's `current_say` return is silently discarded — the classic LangGraph footgun called out in the file.
- **VALIDATE**: type-load `python -c "import app.agents.state"`.

### Task 5: Wire plan node
- **ACTION**: Pass voice in, return the say.
- **IMPLEMENT**: In `persona_graph.py` `plan` (autonomous branch, 280-288):
  `a = plan_action(..., hints=state.get("hints", {}), persona_voice=state.get("persona_voice", ""))`
  and add `"current_say": a.say` to the returned dict. (Scripted branch may set `"current_say": ""`.)
- **MIRROR**: NODE_RETURNS_STATE_DICT.
- **VALIDATE**: pytest as Task 2.

### Task 6: Emit monologue on the SSE plan event + build persona_voice
- **ACTION**: Surface the line to the client and supply voice from the persona config.
- **IMPLEMENT**:
  - In `runs.py` `run_one` (440-456) build a compact voice string from `cfg`, e.g.
    `voice = f"{cfg.get('name', name)}; tech_savviness={cfg.get('tech_savviness','?')}; patience={cfg.get('patience','?')}; language={cfg.get('language','en')}; disabilities={', '.join(cfg.get('disabilities', [])) or 'none'}. {cfg.get('behavior_prompt','')}".strip()`
    and add `"persona_voice": voice` to `payload`.
  - In the `plan` SSE branch (473-480) add `"monologue": (data.get("current_say") or "")` to the emitted dict.
- **MIRROR**: SSE_NODE_EMIT; payload build (runs.py:440-456).
- **GOTCHA**: `cfg` from DB rows lacks `behavior_prompt`/`patience`/`tech_savviness` (personas.py:47-71) — `.get(...,'?')` keeps it safe; consider also threading those columns through `_row_to_persona_config` later (out of scope).
- **VALIDATE**: `curl -N "http://localhost:8000/runs/stream?...&persona_names=elderly_low_literacy"` shows `"monologue":` on plan events.

### Task 7: Frontend type + reducer carry-through
- **ACTION**: Accept and store the monologue.
- **IMPLEMENT**:
  - `live.ts` (152-181): on the persona `node` event variant add `monologue?: string;`.
  - `AssessmentRunner.tsx`: add `monologue?: string` to `NodeCardItem` (46-56); in `reduce` persona-node branch (78-83) pass `monologue: e.monologue`.
- **MIRROR**: REACT_SSE_REDUCER.
- **VALIDATE**: `cd frontend && npx tsc --noEmit`.

### Task 8: Render typewriter chat bubble
- **ACTION**: Show monologue as the primary, paced, in-character feed.
- **IMPLEMENT**: In `PersonaColumn` (494-562) render a vertical list of monologue bubbles from `items.filter(it => it.monologue)`. Add a small `Typewriter` component: reveals `text` char-by-char with `setInterval`, cleared on unmount; speed derived from persona pace (default ~28ms/char; faster persona → smaller delay). Keep the existing `NodeOutputCard` feed behind a "details" toggle (collapsed by default) so node data stays available.
- **MIRROR**: existing autoscroll feed (AssessmentRunner.tsx:553-559) — keep the `feedRef` scroll-to-bottom on new items.
- **GOTCHA**: only animate the LATEST bubble; render already-shown bubbles fully (don't re-type history on every render). Track which ids have finished.
- **VALIDATE**: manual (below) — text reveals progressively, scrolls, reads first-person.

---

## Testing Strategy

### Unit Tests
| Test | Input | Expected | Edge? |
|---|---|---|---|
| `AgentAction` default | `AgentAction()` | `.say == ""` | yes (back-compat) |
| offline `say` present | `plan_action(aria, goal, [], rng)` no key | `.say != ""` | yes (offline) |
| state not dropped | run plan node with `persona_voice` set | returned state has `current_say` | yes (LangGraph drop) |

### Edge Cases Checklist
- [ ] No API key → templated monologue, never empty
- [ ] DB persona (no `behavior_prompt`) → voice string still builds
- [ ] `say` returned but very long → bubble wraps (CSS), typewriter still terminates
- [ ] Scripted (`flow` non-empty) mode → `current_say=""`, UI shows node cards as before
- [ ] Non-English persona → renders returned text as-is

---

## Validation Commands

### Static Analysis
```bash
cd backend && .venv/bin/python -c "import app.agents.llm, app.agents.state, app.agents.persona_graph, app.routes.runs"
cd frontend && npx tsc --noEmit
```
EXPECT: no import/type errors.

### Unit Tests
```bash
cd backend && .venv/bin/python -m pytest tests/test_persona_graph.py -q
```
EXPECT: all pass (offline path unchanged; new field defaulted).

### Manual Validation
- [ ] Start backend + frontend; open a project with ≥1 linked persona + staging URL.
- [ ] Run assessment; each persona column shows monologue bubbles revealing char-by-char.
- [ ] Lines are first-person, in character, never mention "AI"/"test"/"a11y tree".
- [ ] With `LLM_API_KEY` set, bubbles vary per persona (elderly = hesitant, control = brisk).
- [ ] Results view + matrix + replay still work unchanged.

---

## Acceptance Criteria
- [ ] Per-step first-person monologue streams live, one line per `plan` step
- [ ] Generated by the persona in its own voice (planner now persona-aware)
- [ ] Offline path produces non-empty templated monologue (tests stay network-free)
- [ ] Typewriter reveal, paced; latest bubble animates, history static
- [ ] No new LLM call, no extra per-step latency
- [ ] Existing tests + results/matrix/replay unaffected

## Completion Checklist
- [ ] New state keys declared in `PersonaState`/`PersonaInput`
- [ ] `AgentAction.say` defaulted (back-compat)
- [ ] Offline template covers every verb
- [ ] SSE event extended, TS type matches
- [ ] tsc + pytest green

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LangGraph drops `current_say` (undeclared) | Med | monologue always empty | Task 4 declares it; called out in state.py comment |
| Model breaks character / mentions a11y tree | Med | immersion broken | Explicit system-prompt guardrail (Task 2) |
| DB persona missing voice fields → bland line | Med | weaker voice for DB personas | `.get(...,'?')`; later thread columns through `_row_to_persona_config` |
| Typewriter re-types history on re-render | Med | janky feed | Animate latest id only; mark finished ids |

## Notes
- The high-leverage insight: the per-step planner LLM call (`plan_action`) is currently **persona-blind** — persona behavior is applied only deterministically in `decide`. Feeding persona voice into that existing call is what makes the monologue feel like a *specific* person, at zero extra call cost.
- `comprehend` in the docstrings is the historical name; the live node is `plan`. Emit the monologue there.
- Scripted mode is legacy/test-only (`_resolve_journey` always returns empty flow → autonomous), so monologue effectively always populates in real runs.

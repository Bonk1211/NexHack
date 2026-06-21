# Report: Autonomous Exploration Loop — `feat/autonomous-persona-exploration` vs `origin/main`

Two engineers built the autonomous loop **independently** from the same base (`a5171fd`). Both rewrote `persona_graph.py` + added ~350 lines to `llm.py`. They are **parallel, conflicting implementations** of the same feature — this will be a hard merge, not a fast-forward.

## The core difference: where the agent loop lives

| | **main** (other engineer) | **this branch** |
|---|---|---|
| Loop location | **Inside one fat `agent` node** — `run_agent()` runs its own `for turn in range(20)` loop | **The LangGraph cycle itself** — `observe→plan→decide→act→route_next`, one action per superstep |
| What the LLM returns | **Playwright Python code** → `exec(code)` on the live page | **Structured `AgentAction`** (action/role/name/nth/value), interpreted by `act()` |
| Graph shape | Branches at `observe`: autonomous → `agent`; scripted → `comprehend→decide→act` | One unified pipeline; mode handled by `is_autonomous` conditionals inside nodes |

Main barely uses LangGraph for autonomy (the real loop is a Python `for` inside a node). This branch makes LangGraph *be* the loop (each step is real nodes + a conditional edge), so streaming, checkpointing, and per-step retry policies apply to every action.

## Mechanism-by-mechanism

**Action execution**
- **main:** LLM emits `{"exec": "page.get_by_label('Year').select_option('1990')"}` → `_play_exec` runs `exec()`. One tool replaces all action types. Maximally flexible — selects, uploads, anything the LLM can code — but it's **arbitrary code execution** against the page, and correctness rides entirely on the model writing good Playwright each turn.
- **this branch:** Fixed action vocabulary (`fill/click/upload/navigate_back/done`). No `exec`. Selects and file uploads are handled **deterministically** in `plan()` (detect unset `<select>`/`<input type=file>`, act without asking the LLM). More code, but no eval and no per-turn LLM dependence for the hard controls.

**Determinism / testing**
- **main:** `if client is None → blocked "offline"`. **No deterministic fallback, no autonomous tests** (`test_autonomous_nav.py` absent). The loop cannot run or be tested without a live LLM.
- **this branch:** `_heuristic_explore` is a full offline planner → **207 lines of network-free deterministic tests** (13 passing). Runs with or without an LLM key.

**Loop / stuck detection**
- **main:** `url_visit_counts[url] >= 20`. URL-based — blind to multi-screen SPAs that share one URL (Next.js `pushState`), and 20 visits is loose.
- **this branch:** `screen_key = url + hash(structural skeleton)` + per-screen `seen_signatures`. Distinguishes SPA screens on the same URL; survives typing; masks volatile timers (resend countdowns).

**Success criteria**
- **main:** Explicit `success_url` / `success_element` / `hints` (e.g. inject the OTP) passed in per run — the LLM is told when it's done.
- **this branch:** Emergent — planner decides `done`; success isn't pre-declared. `hints` don't exist (it derives OTP/test data heuristically).

**Persona behavior model**
- **main:** Autonomous path **skips `decide`** — dwell, give-up threshold, hesitation aren't applied during exploration.
- **this branch:** `decide` stays in the loop for both modes, so persona pacing/give-up still shape autonomous runs.

**State channels added**
- **main:** `autonomous`, `hints`, `success_url`, `success_element`, `url_visit_counts`, `current_url`, `blocked_url`.
- **this branch:** `step_count`, `action_history`, `seen_signatures`, `current_action`, `current_screen_key`, `last_url`, plus `current_dwell_giveup/cycle/over_cap`.

## Trade-offs

**main's strengths:** far less code; the `exec` tool needs zero per-control logic (no upload/select handlers — the LLM just writes the call); conversation-style history; explicit success signals are reliable when known.

**main's risks:** arbitrary code execution; no offline mode or tests; URL-only loop guard breaks on SPAs; LLM-mandatory and non-reproducible; no persona model during exploration; cost scales with turns (full chat history each turn).

**this branch's strengths:** deterministic + tested; SPA-aware loop guard; no eval; concrete robustness fixes (React controlled-input typing, `requestSubmit` for swallowed SPA navigations, per-digit OTP, deterministic upload/select, recursion-limit sizing); persona model preserved; works offline.

**this branch's costs:** more code and more moving parts; relies on a fixed action vocabulary (a control type nobody coded for — e.g. a canvas signature pad — needs new handling, whereas main's LLM could just write code for it).

## Bottom line

They're two philosophies: main is an **LLM-writes-code agent** (flexible, terse, but eval-based, LLM-mandatory, untested, URL-naive). This branch is a **structured-action graph agent** (deterministic, SPA-aware, tested, with explicit robustness fixes, but more code and a fixed action set).

Recommended merge stance: keep **this branch's** graph-native loop, determinism, SPA loop-guard and robustness fixes as the base; selectively adopt from main the ideas that are strictly additive — explicit `success_url`/`success_element` and `hints` (e.g. inject a known OTP), and optionally an `exec`-style escape hatch *gated* behind the structured path for exotic controls. Do **not** take main's URL-only stuck detection or its no-offline design.

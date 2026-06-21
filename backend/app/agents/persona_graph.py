"""Persona navigation subgraph — the cyclic agent loop (§8, §9.1).

This is the part the email-router template does NOT have: the persona agent does
not "classify then route" — it OBSERVES a screen, COMPREHENDS it, DECIDES an
action against the a11y tree + behavior model, ACTS, and REPEATS until blocked or
done. The exit condition is emergent, expressed by `route_next`, not a fixed
pipeline.

Node responsibilities (cognition concentrated in exactly one node):
  observe    — deterministic: capture the trusted signals (axe once on entry,
               a11y tree, reading grade) + the screenshot the persona faces.
  comprehend — THE LLM node: vision confusion judgment (stream B) + nav fallback.
  decide     — deterministic: dwell from the behavior model × seeded RNG, the
               a11y-tree label check, give-up / label-block intent. This is where
               persona behavior becomes real control flow, not prompt flavor (§23).
  act        — deterministic: drive Playwright, screenshot accounting, emit the
               RAW StepSignals (no verdict — §16). A block is a CLEAN exit here,
               never an error to retry away (§23).
  route_next — loop back to observe, or END (blocked | completed).

Navigation method (§8/§25): the a11y tree drives navigation; the vision model is
comprehension judgment + fallback, never the primary driver. Sync Playwright on
purpose; the lifecycle is owned by run_journey / the run-graph persona node, never
inside a node (a node teardown would kill the browser mid-graph). Verified safe
under the run graph's Send fan-out via sync `.invoke` (thread-pool, no asyncio loop).
"""
from __future__ import annotations

import concurrent.futures
import pathlib
import random

from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy
from playwright.sync_api import sync_playwright

from app.agents.llm import run_agent, vision_judge
from app.agents.navigator import (
    FlowStep,
    JourneyResult,
    NavConfig,
    _role_has_name,
)
from app.agents.signals import axe_to_wcag, reading_grade, run_axe
from app.agents.state import PersonaInput, PersonaState
from app.scoring.engine import StepSignals
from app.llm_usage import current_tracker, set_tracker


def _bp(state: PersonaState) -> dict:
    return state.get("behavior_profile", {})


def load(state: PersonaState) -> dict:
    """Navigate to the target and initialize the loop (page is already open)."""
    page = state["page"]
    page.goto(state["target_url"], wait_until="load")
    return {"step_idx": 0, "status": "running"}


def observe(state: PersonaState) -> dict:
    """Capture the trusted signals + the screen the persona faces (deterministic)."""
    page = state["page"]
    idx = state["step_idx"]
    out: dict = {}

    aria = page.locator("body").aria_snapshot()
    out["aria"] = aria
    if idx == 0:
        # TRUSTED stream — page-level axe, persona-independent, on the entry step (§16).
        out["wcag"] = axe_to_wcag(run_axe(page))
        body_text = page.inner_text("body")
        out["grade"] = reading_grade(body_text)
        out["word_count"] = max(len(body_text.split()), 1)

    # Screenshot EVERY step (FR-1.3) — the screen comprehend judges + empathy replay.
    shot = None
    if state.get("artifact_dir"):
        d = pathlib.Path(state["artifact_dir"])
        d.mkdir(parents=True, exist_ok=True)
        shot = str(d / f"step_{idx}.png")
        page.screenshot(path=shot)
    out["current_shot"] = shot

    # Track current URL and visit count for autonomous stuck detection.
    current_url = page.url
    counts = dict(state.get("url_visit_counts") or {})
    counts[current_url] = counts.get(current_url, 0) + 1
    out["current_url"] = current_url
    out["url_visit_counts"] = counts
    return out


def comprehend(state: PersonaState) -> dict:
    """Scripted-mode LLM node: per-screen confusion judgment (stream B)."""
    aria = state.get("aria", "")
    requires_labels = state.get("requires_labels", False)
    fs: FlowStep = state["flow"][state["step_idx"]]
    labeled = _role_has_name(aria, fs.role) if fs.role else True
    j = vision_judge(
        state.get("current_shot"),
        fs.key,
        aria,
        requires_labels=requires_labels,
        labeled=labeled,
        action=fs.action,
    )
    return {
        "last_confusion": j.confusion,
        "last_fallback": j.fallback_target,
        "last_reason": j.reason,
        "current_labeled": labeled,
    }


def decide(state: PersonaState) -> dict:
    """Apply the persona behavior model to produce real control flow (§23).

    Dwell is reading-load × persona pace × seeded hesitation; the give-up
    threshold and the label dependency decide whether the step blocks BEFORE we
    even act. Same screen, different persona => different decision.

    In autonomous mode: label_block is skipped (agent targets named elements), but
    dwell and give-up still apply. Stuck detection (same URL ≥4 visits) overrides
    give-up to force an exit when the agent is looping.
    """
    bp = _bp(state)
    rng: random.Random = state["rng"]

    wpm = float(bp.get("reading_speed_wpm", 200))
    dwell_mult = float(bp.get("dwell_multiplier", 1.0))
    hesitation_prob = float(bp.get("hesitation_prob", 0.0))
    giveup_s = float(bp.get("giveup_threshold_s", 60))
    word_count = float(state.get("word_count", 1))

    dwell = (word_count / wpm) * 60.0 * dwell_mult
    if rng.random() < hesitation_prob:
        dwell *= 1.5

    if state.get("autonomous"):
        # Stuck detection: same URL visited 4+ times → force give-up.
        url_visit_counts = state.get("url_visit_counts") or {}
        current_url = state.get("current_url", "")
        stuck = url_visit_counts.get(current_url, 0) >= 10
        action_str = (state.get("last_action") or {}).get("action", "")
        give_up = stuck or dwell >= giveup_s or action_str == "blocked"
        return {
            "current_dwell": round(dwell, 2),
            "current_retries": 0,
            "current_label_block": False,
            "current_give_up": give_up,
        }

    fs: FlowStep = state["flow"][state["step_idx"]]
    labeled = state.get("current_labeled", True)
    label_block = fs.action == "fill" and state.get("requires_labels", False) and not labeled
    give_up = dwell >= giveup_s
    retries = 1 if rng.random() < hesitation_prob else 0

    return {
        "current_dwell": round(dwell, 2),
        "current_retries": retries,
        "current_label_block": label_block,
        "current_give_up": give_up,
    }


def act(state: PersonaState) -> dict:
    """Drive Playwright, then emit RAW StepSignals and advance the cursor.

    A persona that cannot proceed exits with dead_end/completed=False — that is a
    finding (a P0 once scored), NOT an error to retry away (§23). Only genuinely
    unexpected exceptions propagate to the node RetryPolicy (transient).

    In autonomous mode: executes the AgentAction decided by comprehend, using the
    accessible name to locate the element precisely (no .first ambiguity).
    In scripted mode: follows FlowStep — now also uses name for fill disambiguation
    (Track A fix: previously ignored name on fill, causing wrong-field overwrites).
    """
    page = state["page"]
    idx = state["step_idx"]
    rng: random.Random = state["rng"]

    dwell = state.get("current_dwell", 0.0)
    retries = state.get("current_retries", 0)
    dead_end = False
    completed = True
    confusion = state.get("last_confusion", 0.0)
    blocked_url: str | None = None

    if state.get("current_label_block"):
        dead_end, completed = True, False

    elif state.get("autonomous"):
        action = state.get("last_action") or {}
        a_type = action.get("action", "blocked")
        role = action.get("role", "")
        name = action.get("name", "")
        value = action.get("value", "")

        if a_type == "done":
            # Guard: only accept "done" when actually at the success URL.
            success_url = state.get("success_url", "")
            current_url = state.get("current_url", "")
            if success_url and success_url.lstrip("/") not in current_url:
                # LLM claimed "done" prematurely — not at target. Force blocked.
                dead_end, completed = True, False
            else:
                completed = True
        elif a_type == "blocked" or state.get("current_give_up"):
            dead_end, completed = True, False
        elif a_type in ("fill", "click"):
            try:
                loc = page.get_by_role(role, name=name) if name else page.get_by_role(role)
                if a_type == "fill":
                    loc.first.fill(value, timeout=3000)
                else:
                    loc.first.click(timeout=3000)
            except Exception:
                # Name fallback: only for fill actions (first textbox is safe).
                # Click fallback is dangerous — clicking the first button on a page
                # can submit forms before they're ready (e.g. OTP Verify before digits).
                if name and a_type == "fill":
                    try:
                        page.get_by_role(role).first.fill(value, timeout=3000)
                    except Exception:
                        dead_end, completed = True, False
                else:
                    dead_end, completed = True, False
        else:
            dead_end, completed = True, False

        step_key = action.get("step_label", f"step_{idx}")
        critical = False  # autonomous steps are not pre-classified

    else:
        fs: FlowStep = state["flow"][idx]
        step_key = fs.key
        critical = fs.critical

        if fs.action in ("fill", "click"):
            try:
                if fs.action == "fill":
                    loc = page.get_by_role(fs.role, name=fs.name) if fs.name else page.get_by_role(fs.role)
                    loc.first.fill(fs.value, timeout=3000)
                elif fs.name:
                    page.get_by_role(fs.role, name=fs.name).first.click(timeout=3000)
                else:
                    page.get_by_role(fs.role).first.click(timeout=3000)
            except Exception:
                # Name fallback: only for fill actions. Click fallback is dangerous.
                if fs.name and fs.action == "fill":
                    try:
                        page.get_by_role(fs.role).first.fill(fs.value, timeout=3000)
                    except Exception:
                        dead_end, completed = True, False
                else:
                    dead_end, completed = True, False

        if state.get("current_give_up"):
            dead_end, completed = True, False

    if dead_end:
        blocked_url = page.url

    step = StepSignals(
        step_idx=idx,
        step_key=step_key,
        critical=critical if not state.get("autonomous") else False,
        wcag=state.get("wcag", ()) if idx == 0 else (),
        dwell_s=dwell,
        retries=retries,
        dead_end=dead_end,
        completed=completed,
        llm_confusion=confusion,
        reading_grade=state.get("grade"),
    )

    next_idx = idx + 1
    flow = state.get("flow") or []
    if dead_end:
        status, blocked_at = "blocked", step_key
    elif state.get("autonomous"):
        # Only exit the loop when the LLM explicitly says "done" or a dead_end
        # occurs. Every other successful action keeps the agent running.
        action = state.get("last_action") or {}
        a_type = action.get("action", "")
        if a_type == "done":
            status, blocked_at = "completed", None
        elif a_type == "blocked":
            status, blocked_at = "blocked", step_key
        else:
            status, blocked_at = "running", None
    elif next_idx >= len(flow):
        status = "completed" if completed else "blocked"
        blocked_at = None if completed else step_key
    else:
        status, blocked_at = "running", None

    _ = rng
    out = {
        "steps": [step],
        "shots": [state.get("current_shot")],
        "step_idx": next_idx,
        "status": status,
        "blocked_at": blocked_at,
        "blocked_url": blocked_url,
    }
    return out


def agent(state: PersonaState) -> dict:
    """MCP-style autonomous agent: LLM with Playwright tools in a multi-turn loop.

    Replaces comprehend→decide→act for autonomous mode. The agent receives the a11y
    tree, makes an LLM call to decide an action, executes it via Playwright, feeds
    the result back (including error details with available element names), and
    repeats until done/blocked/max-turns. All regex fallbacks eliminated.
    """
    result = run_agent(
        page=state["page"],
        goal=state.get("goal", ""),
        hints=state.get("hints") or {},
        success_url=state.get("success_url", ""),
        success_element=state.get("success_element", ""),
        aria=state.get("aria", ""),
        requires_labels=state.get("requires_labels", False),
        behavior_profile=_bp(state),
        wcag=state.get("wcag", ()),
        grade=state.get("grade"),
        word_count=state.get("word_count", 1),
        rng=state["rng"],
        artifact_dir=state.get("artifact_dir"),
        current_url=state.get("current_url", ""),
        url_visit_counts=state.get("url_visit_counts") or {},
        step_idx=state["step_idx"],
    )
    # Merge accumulated steps and shots into the state reducers
    out = dict(result)
    # route_next reads "status"; shot/step reducers use operator.add
    return out


def route_next(state: PersonaState) -> str:
    """Emergent exit: loop while running, else END (blocked | completed)."""
    return "observe" if state.get("status") == "running" else END


def _route_after_observe(state: PersonaState) -> str:
    """Autonomous mode → agent node; scripted mode → comprehend pipeline."""
    return "agent" if state.get("autonomous") else "comprehend"


def build_persona_graph():
    """Compile the cyclic persona subgraph with dual-mode support.

    Autonomous: load → observe → agent ──────→ route_next → observe (loop) or END
    Scripted:   load → observe → comprehend → decide → act → route_next → observe or END
    """
    g = StateGraph(PersonaState)
    g.add_node("load", load)
    g.add_node("observe", observe, retry_policy=RetryPolicy(max_attempts=3))
    g.add_node("agent", agent, retry_policy=RetryPolicy(max_attempts=2))       # MCP-style
    g.add_node("comprehend", comprehend)
    g.add_node("decide", decide)
    g.add_node("act", act, retry_policy=RetryPolicy(max_attempts=3))
    g.set_entry_point("load")
    g.add_edge("load", "observe")
    g.add_conditional_edges("observe", _route_after_observe, {
        "agent": "agent",
        "comprehend": "comprehend",
    })
    g.add_conditional_edges("agent", route_next, {"observe": "observe", END: END})
    g.add_edge("comprehend", "decide")
    g.add_edge("decide", "act")
    g.add_conditional_edges("act", route_next, {"observe": "observe", END: END})
    return g.compile()


# Compile once; the graph is stateless and reusable across personas.
_PERSONA_GRAPH = build_persona_graph()


def _run_persona_sync(payload: PersonaInput) -> PersonaState:
    """Open a browser, seed the RNG, invoke the subgraph, return the FINAL state.

    Owns the Playwright lifecycle around `.invoke` so the browser survives the
    whole graph (never torn down inside a node) and so the live `page`/`rng` never
    leave this in-process invoke (they are not checkpoint-serializable).
    """
    p = sync_playwright().start()
    browser = p.chromium.launch()
    try:
        page = browser.new_page(**p.devices[payload.get("viewport", "iPhone 13")])
        state: PersonaState = {
            **payload,
            "page": page,
            "rng": random.Random(payload["seed"]),
            "step_idx": 0,
            "steps": [],
            "shots": [],
            "status": "running",
        }
        return _PERSONA_GRAPH.invoke(state)
    finally:
        browser.close()
        p.stop()


def stream_persona(payload: PersonaInput, on_frame=None):
    """Yield (node_name, update) for each subgraph step as it runs — LIVE.

    The streaming counterpart of `run_persona`: instead of one `.invoke`, it drives
    the subgraph with `.stream(stream_mode="updates")` so the caller can surface each
    node (observe→comprehend→decide→act) the moment it completes — the agent visibly
    testing the target app step by step. Owns the Playwright lifecycle around the
    stream so the browser survives the whole graph.

    If `on_frame` is given, a Chrome DevTools screencast is attached and `on_frame`
    is called with each base64 JPEG frame of the live page — so the caller can render
    the actual browser the agent drives (the external app) inside the dashboard.
    Frame events fire during Playwright calls (sync API pumps them), so the callback
    runs on THIS thread; keep it non-blocking (e.g. a bounded queue put).

    MUST be called from a thread WITHOUT a running asyncio loop (sync Playwright) —
    e.g. a Starlette threadpool worker (a sync generator endpoint qualifies).
    """
    p = sync_playwright().start()
    browser = p.chromium.launch()
    cdp = None
    try:
        page = browser.new_page(**p.devices[payload.get("viewport", "iPhone 13")])

        if on_frame is not None:
            cdp = page.context.new_cdp_session(page)

            def _frame(f):
                try:
                    on_frame(f["data"])  # base64 JPEG
                    cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]})
                except Exception:  # noqa: BLE001 — never let screencast break the run
                    pass

            cdp.on("Page.screencastFrame", _frame)
            cdp.send("Page.startScreencast", {
                "format": "jpeg", "quality": 50, "maxWidth": 420, "maxHeight": 900,
                "everyNthFrame": 1,
            })

        state: PersonaState = {
            **payload,
            "page": page,
            "rng": random.Random(payload["seed"]),
            "step_idx": 0,
            "steps": [],
            "shots": [],
            "status": "running",
        }
        for update in _PERSONA_GRAPH.stream(state, stream_mode="updates"):
            for node, data in update.items():
                yield node, data
    finally:
        if cdp is not None:
            try:
                cdp.send("Page.stopScreencast")
            except Exception:  # noqa: BLE001
                pass
        browser.close()
        p.stop()


def run_persona(payload: PersonaInput) -> PersonaState:
    """Run one persona's subgraph in a DEDICATED thread, returning the final state.

    The fresh thread does double duty:
      1. Severs the parent run graph's ambient RunnableConfig (a contextvar) — LangGraph
         otherwise propagates the parent's checkpointer into this nested invoke and tries
         to persist the subgraph's live `page` channel (not msgpack-serializable).
      2. Keeps sync Playwright off any asyncio loop, so it works under Send fan-out.
    """
    tracker = current_tracker()

    def _wrapped(p: PersonaInput):
        if tracker is not None:
            set_tracker(tracker)
        try:
            return _run_persona_sync(p)
        finally:
            if tracker is not None:
                set_tracker(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_wrapped, payload).result()


def run_journey(cfg: NavConfig) -> JourneyResult:
    """Drive one persona through the flow via the subgraph; return signals + shots."""
    final = run_persona({
        "persona": "",
        "persona_idx": 0,
        "behavior_profile": cfg.behavior_profile,
        "requires_labels": cfg.requires_labels,
        "target_url": cfg.target_url,
        "flow": cfg.flow,
        "viewport": cfg.viewport,
        "seed": cfg.seed,
        "artifact_dir": cfg.artifact_dir,
    })
    return JourneyResult(final["steps"], final["shots"])

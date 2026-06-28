"""Graph state objects (§8, §16).

Two graphs, two states:
  - PersonaState drives the CYCLIC persona subgraph (observe→comprehend→decide→
    act→route_next). It carries the live Playwright `page` and the seeded `rng`
    in-process — these are NOT checkpoint-serializable and never leave the
    subgraph's own `.invoke`.
  - RunState drives the top-level MAP-REDUCE run graph (init→Send→aggregate→
    score→evidence→alerts). It carries only serializable, run-level data.

§16 discipline (store raw, derive on demand): the subgraph stores RAW per-step
signals (axe violations, dwell, a11y tree, llm_confusion) in `steps` — NEVER a
precomputed verdict. The top-level `score` node derives WCAG conformance /
persona verdict / composite from those raw signals. That is what keeps the
trusted stream reportable on its own.

Reducer keys (`steps`, `shots`, `persona_results`) use `operator.add` so fan-in
accumulates across supersteps; every other key is single-writer per superstep.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

from app.agents.navigator import FlowStep
from app.scoring.engine import PersonaThresholds, StepSignals, WcagSignal


class PersonaInput(TypedDict, total=False):
    """The Send payload for one persona — SERIALIZABLE ONLY.

    This is the type the run graph's `persona` node is annotated with, so these
    are the only persona-related channels the parent graph (and its checkpointer)
    ever sees. It deliberately excludes the live `page`/`rng` — those are created
    inside `run_persona` and never leave the subgraph's in-process invoke, which is
    what keeps the checkpoint serializable (a `Page` is not msgpack-serializable).
    """
    persona: str
    persona_idx: int                 # input order, for deterministic aggregate (§20)
    behavior_profile: dict
    thresholds: PersonaThresholds
    requires_labels: bool
    target_url: str
    flow: list[FlowStep]
    viewport: str
    seed: int                        # per-persona seed+i — determinism under Send concurrency
    artifact_dir: Optional[str]
    # Autonomous (goal-directed) navigation — mutually exclusive with a non-empty flow.
    autonomous: bool                 # True = agent decides actions; False = follow flow
    goal: str                        # e.g. "claim a reward on BrewPoints"
    hints: dict                      # values agent must use: {"phone": "...", "otp": "..."}
    success_url: str                 # URL suffix that means goal achieved, e.g. "/rewards"
    success_element: str             # a11y text that means goal achieved, e.g. 'heading "Welcome"'
    persona_voice: str               # compact voice context — makes the agent's `say` in-character


class PersonaState(PersonaInput, total=False):
    """State for one persona's CYCLIC navigation subgraph (its own StateGraph).

    Extends the serializable input with the live, in-process-only objects and the
    raw per-step accumulation. None of these are ever parent-graph channels.
    """
    # In-process only (NOT checkpoint-serializable; stay inside the subgraph invoke)
    page: Any
    rng: Any
    on_say: Any                          # callback(text) — emits each monologue line LIVE

    # Trusted page-level signals, captured once on entry (§10)
    aria: str
    wcag: tuple[WcagSignal, ...]
    grade: float
    word_count: int

    # Loop cursor + RAW accumulation (§16 — raw signals, no verdict)
    step_idx: int
    steps: Annotated[list[StepSignals], operator.add]
    shots: Annotated[list[Optional[str]], operator.add]

    # Per-step scratch passed between observe→comprehend→decide→act.
    # MUST be declared: LangGraph drops undeclared keys returned by nodes.
    current_shot: Optional[str]
    current_labeled: bool
    current_dwell: float
    current_retries: int
    current_label_block: bool
    current_give_up: bool
    last_confusion: float
    last_fallback: Optional[str]
    last_reason: str

    # Autonomous mode scratch
    current_url: str                 # page.url captured each observe cycle
    url_visit_counts: dict           # {url: int} — stuck detection
    last_action: dict                # AgentAction dict from agent_decide

    # Control-flow status read by route_next ("running"|"blocked"|"completed")
    status: str
    blocked_at: Optional[str]
    blocked_url: Optional[str]       # browser address where the persona got stuck


class PersonaRunRaw(TypedDict):
    """One persona subgraph's RAW output, collected by the run-graph reducer.

    Deliberately verdict-free: scoring happens in the top-level `score` node so
    the trusted stream is derived once, centrally (§16).
    """
    persona: str
    persona_idx: int
    thresholds: PersonaThresholds
    steps: list[StepSignals]
    shots: list[Optional[str]]
    status: str
    blocked_at: Optional[str]


class RunState(TypedDict, total=False):
    """State for the top-level map-reduce run graph."""
    app: str
    target_url: str
    viewport: str
    personas: list[dict]             # resolved persona configs (name + behavior + thresholds)
    flow: list[FlowStep]
    seed: int
    artifact_root: Optional[str]
    run_at: str                      # ISO-8601, set by init
    # Autonomous navigation config (present when flow is empty)
    autonomous: bool
    goal: str
    hints: dict
    success_url: str
    success_element: str

    # Fan-in reducer: each Send-spawned persona subgraph contributes one entry
    persona_results: Annotated[list[PersonaRunRaw], operator.add]

    # aggregate writes the reducer's contents back in input order (plain channel —
    # a reducer key can't be reordered in place); score derives PersonaRunResults.
    ordered: list          # list[PersonaRunRaw], sorted by persona_idx (§20 narration)
    scored: list           # list[evidence.pack.PersonaRunResult]

    # Filled by the evidence node
    pack: dict

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
    flow: list[FlowStep]             # scripted steps; empty => autonomous (goal-driven)
    goal: str                        # high-level task for autonomous exploration
    max_steps: int                   # safety cap on the autonomous loop
    hints: dict                      # known values the agent must use, e.g. {"otp": "123456"}
    success_url: str                 # URL suffix meaning the goal is reached
    success_element: str             # a11y text meaning the goal is reached
    viewport: str
    seed: int                        # per-persona seed+i — determinism under Send concurrency
    artifact_dir: Optional[str]


class PersonaState(PersonaInput, total=False):
    """State for one persona's CYCLIC navigation subgraph (its own StateGraph).

    Extends the serializable input with the live, in-process-only objects and the
    raw per-step accumulation. None of these are ever parent-graph channels.
    """
    # In-process only (NOT checkpoint-serializable; stay inside the subgraph invoke)
    page: Any
    rng: Any

    # Trusted page-level signals, captured once on entry (§10)
    aria: str
    wcag: tuple[WcagSignal, ...]
    grade: float
    word_count: int

    # Loop cursor + RAW accumulation (§16 — raw signals, no verdict)
    step_idx: int
    steps: Annotated[list[StepSignals], operator.add]
    shots: Annotated[list[Optional[str]], operator.add]

    # Autonomous-loop control (single-writer per superstep — NOT operator.add, the loop
    # is sequential within one persona; each node returns the full updated list).
    step_count: int                  # monotonic actions taken (autonomous + scripted cursor)
    action_history: list             # [{"screen_key","key","action","role","name","reason"}] planner context
    seen_signatures: list            # screen-key-qualified signatures attempted, for cycle detection
    current_action: dict             # the planner's chosen action for this superstep
    last_url: str                    # screen_key axe/grade were last captured on (re-run when it changes)
    current_screen_key: str          # "{url}#{aria_hash}" — unique per screen content, not just URL

    # Per-step scratch passed between observe→comprehend→decide→act.
    # MUST be declared: LangGraph drops undeclared keys returned by nodes.
    current_shot: Optional[str]
    current_labeled: bool
    current_dwell: float
    current_retries: int
    current_label_block: bool
    current_give_up: bool                # scripted-mode terminal block (dwell over threshold)
    current_dwell_giveup: bool           # autonomous: dwell barrier — a finding, but keep exploring
    current_cycle: bool                  # autonomous: action already tried on this screen (loop guard)
    current_over_cap: bool               # autonomous: step budget exhausted — terminate exploration
    last_confusion: float
    last_fallback: Optional[str]
    last_reason: str

    # Control-flow status read by route_next ("running"|"blocked"|"completed")
    status: str
    blocked_at: Optional[str]


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
    flow: list[FlowStep]             # scripted steps; empty => autonomous (goal-driven)
    goal: str                        # high-level task for autonomous exploration
    max_steps: int                   # safety cap on the autonomous loop
    hints: dict                      # known values the agent must use, e.g. {"otp": "123456"}
    success_url: str                 # URL suffix meaning the goal is reached
    success_element: str             # a11y text meaning the goal is reached
    seed: int
    artifact_root: Optional[str]
    run_at: str                      # ISO-8601, set by init

    # Fan-in reducer: each Send-spawned persona subgraph contributes one entry
    persona_results: Annotated[list[PersonaRunRaw], operator.add]

    # aggregate writes the reducer's contents back in input order (plain channel —
    # a reducer key can't be reordered in place); score derives PersonaRunResults.
    ordered: list          # list[PersonaRunRaw], sorted by persona_idx (§20 narration)
    scored: list           # list[evidence.pack.PersonaRunResult]

    # Filled by the evidence node
    pack: dict

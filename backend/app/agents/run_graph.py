"""Top-level run graph — persona map-reduce (§8, §13, §16, §20).

This is the orchestrator as a graph, not a procedural loop:

    init ─► Send(persona)×N ─► aggregate ─► score ─► evidence ─► alerts ─► END

- `init` resolves the run and computes `run_at`. No browser here.
- `fan_out` emits one `Send` per persona (seed+i) — map. Each persona subgraph
  runs in its own thread under sync `.invoke` and owns its own browser.
- `persona` wraps the cyclic subgraph (app.agents.persona_graph) and returns RAW
  per-persona signals into the `persona_results` reducer — reduce.
- `aggregate` reorders the fanned-in results to input order so output/narration is
  deterministic (§20) even though execution was concurrent.
- `score` derives the trusted/indicative/composite results with the PURE scorer —
  raw signals in, verdict out, exactly once, centrally (§16).
- `evidence` assembles the §13 pack and attaches the optional once-per-run LLM
  synthesis. `alerts` fires owner routing on a P0, best-effort.

A `SqliteSaver` checkpoints run-level state keyed by `thread_id=run_id`, so a
crashed run resumes per persona rather than restarting the whole wall. The live
`page`/`rng` never reach the checkpointer — they live only inside each persona
subgraph's in-process invoke.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.agents.llm import synthesize
from app.agents.navigator import FlowStep
from app.agents.persona_graph import run_persona
from app.agents.state import PersonaInput, RunState
from app.alerts import send_alerts
from app.config import settings
from app.evidence.pack import PersonaRunResult, build_pack
from app.scoring.engine import (
    Composite,
    PersonaThresholds,
    PersonaVerdict,
    ScoreResult,
    ScoreWeights,
    StepSignals,
    WcagSignal,
    score,
)
from app.scoring.personas import load_persona, thresholds_for

# Domain dataclasses that travel through the checkpoint. Registering them keeps
# msgpack round-trips explicit (no "unregistered type … blocked in a future
# version" warning) — see the plan's spike note (Task 7).
_CHECKPOINT_TYPES = [
    FlowStep,
    StepSignals, WcagSignal, PersonaThresholds, PersonaVerdict,
    Composite, ScoreWeights, ScoreResult, PersonaRunResult,
]

# The demo fixture flow (§20, §22): enter the OTP (critical), then submit (critical).
DEFAULT_FLOW: list[FlowStep] = [
    FlowStep("otp", "fill", role="textbox", critical=True),
    FlowStep("submit", "click", role="button", name="Submit", critical=True),
]


def _requires_labels(persona: dict) -> bool:
    """Persona depends on labels/SR semantics (drives the nav agent's label check)."""
    disabilities = persona.get("disabilities", [])
    thresholds_block = persona.get("thresholds", {})
    return ("low_vision" in disabilities) or bool(thresholds_block.get("require_labels"))


# --- nodes ------------------------------------------------------------------

def init(state: RunState) -> dict:
    """Stamp the run; personas/flow are resolved by run_assessment before invoke."""
    return {"run_at": datetime.now(timezone.utc).isoformat()}


def fan_out(state: RunState) -> list[Send]:
    """Map: one Send per persona. seed+i keeps personas distinct yet reproducible."""
    sends: list[Send] = []
    for i, persona in enumerate(state["personas"]):
        name = persona["stem"]   # the persona file stem ("control", "oku_visual") = identity
        payload: PersonaInput = {
            "persona": name,
            "persona_idx": i,
            "behavior_profile": persona.get("behavior_profile", {}),
            "requires_labels": _requires_labels(persona),
            "thresholds": thresholds_for(persona),
            "target_url": state["target_url"],
            "flow": state["flow"],
            "viewport": state.get("viewport", "iPhone 13"),
            "seed": state["seed"] + i,
            "artifact_dir": (
                f"{state['artifact_root']}/{name}" if state.get("artifact_root") else None
            ),
        }
        sends.append(Send("persona", payload))
    return sends


def persona_node(payload: PersonaInput) -> dict:
    """Run one persona subgraph and contribute RAW signals to the reducer (reduce)."""
    final = run_persona(payload)
    raw = {
        "persona": payload["persona"],
        "persona_idx": payload["persona_idx"],
        "thresholds": payload["thresholds"],
        "steps": final["steps"],
        "shots": final["shots"],
        "status": final.get("status"),
        "blocked_at": final.get("blocked_at"),
    }
    return {"persona_results": [raw]}


def aggregate(state: RunState) -> dict:
    """Reorder fanned-in results to input order (§20) — execution was concurrent."""
    ordered = sorted(state["persona_results"], key=lambda r: r["persona_idx"])
    return {"ordered": ordered}


def score_node(state: RunState) -> dict:
    """Derive the trusted/indicative/composite results with the PURE scorer (§16)."""
    scored = [
        PersonaRunResult(
            persona=raw["persona"],
            steps=tuple(raw["steps"]),
            thresholds=raw["thresholds"],
            result=score(raw["steps"], raw["thresholds"]),
        )
        for raw in state["ordered"]
    ]
    return {"scored": scored}


def evidence(state: RunState) -> dict:
    """Assemble the §13 pack + attach the optional once-per-run synthesis."""
    pack = build_pack(state["app"], state["run_at"], state["scored"])
    pack["screenshots"] = {raw["persona"]: raw["shots"] for raw in state["ordered"]}
    pack["synthesis"] = synthesize(pack).model_dump()
    return {"pack": pack}


def alerts(state: RunState) -> dict:
    """Fire owner-routed alerts on a P0 — best-effort, never breaks the run."""
    try:
        send_alerts(state["pack"])
    except Exception:
        pass
    return {}


# --- graph ------------------------------------------------------------------

def build_run_graph(checkpointer=None):
    g = StateGraph(RunState)
    g.add_node("init", init)
    g.add_node("persona", persona_node)
    g.add_node("aggregate", aggregate)
    g.add_node("score", score_node)
    g.add_node("evidence", evidence)
    g.add_node("alerts", alerts)

    g.set_entry_point("init")
    g.add_conditional_edges("init", fan_out, ["persona"])
    g.add_edge("persona", "aggregate")
    g.add_edge("aggregate", "score")
    g.add_edge("score", "evidence")
    g.add_edge("evidence", "alerts")
    g.add_edge("alerts", END)
    return g.compile(checkpointer=checkpointer)


def run_assessment(
    app_name: str,
    target_url: str,
    persona_names: list[str],
    flow: list[FlowStep] | None = None,
    seed: int = 1337,
    artifact_root: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Run one assessment across personas via the map-reduce graph; return the pack.

    Checkpointed by `thread_id=run_id` so a re-invocation resumes uncompleted
    personas. Persists run-level RAW results only (page/rng stay in-process).
    """
    # Carry the file stem as the persona identity (the matrix/pack key, §17),
    # matching the pre-graph orchestrator contract.
    personas = [{**load_persona(name), "stem": name} for name in persona_names]
    init_state: RunState = {
        "app": app_name,
        "target_url": target_url,
        "viewport": "iPhone 13",
        "personas": personas,
        "flow": flow if flow is not None else DEFAULT_FLOW,
        "seed": seed,
        "artifact_root": artifact_root,
        "persona_results": [],
    }

    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(settings.checkpoint_db) as saver:
        saver.serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES)
        graph = build_run_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": run_id or str(uuid.uuid4())}}

        # Resume semantics. Re-seeding init_state on an existing thread would re-run
        # fan_out and APPEND to the `persona_results` reducer, duplicating personas.
        # Instead: fresh thread -> seed; interrupted thread -> resume pending work with
        # input=None (no re-fan-out); completed thread -> return the existing pack.
        snap = graph.get_state(config)
        if snap.created_at is None:
            final = graph.invoke(init_state, config=config)
        elif snap.next:
            final = graph.invoke(None, config=config)
        else:
            return snap.values["pack"]
    return final["pack"]

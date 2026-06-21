"""Run orchestrator (§8, §20, §21).

Thin shim over the top-level map-reduce run graph (app.agents.run_graph). The
end-to-end wiring — fan out one persona subgraph per persona, score with the pure
scorer, assemble the §13 evidence pack, fire alerts — now lives in the graph; this
module preserves the historical `run_assessment` entry point and return shape so
the route layer and tests are unaffected.

Persistence still lives in app.repository and is invoked by the route layer, not
here. The run graph checkpoints per persona (keyed by run_id) for crash-resume.
"""
from __future__ import annotations

from app.agents.navigator import FlowStep
from app.agents.run_graph import DEFAULT_FLOW, run_assessment as _run_assessment

# Re-exported for callers/tests that referenced the orchestrator's flow constant.
__all__ = ["DEFAULT_FLOW", "FlowStep", "run_assessment"]


def run_assessment(
    app_name: str,
    target_url: str,
    persona_names: list[str],
    flow: list[FlowStep] | None = None,
    seed: int = 1337,
    artifact_root: str | None = None,
    run_id: str | None = None,
    autonomous: bool = False,
    goal: str = "",
    hints: dict | None = None,
    success_url: str = "",
    success_element: str = "",
) -> dict:
    """Run one assessment across personas and return the §13 evidence pack.

    Delegates to the run graph. Return shape is unchanged: the §13 pack dict plus a
    `screenshots` key mapping each persona to its per-step screenshot paths, and a
    `synthesis` block (once-per-run LLM reasoning, §15).
    """
    return _run_assessment(
        app_name=app_name,
        target_url=target_url,
        persona_names=persona_names,
        flow=flow,
        seed=seed,
        artifact_root=artifact_root,
        run_id=run_id,
        autonomous=autonomous,
        goal=goal,
        hints=hints,
        success_url=success_url,
        success_element=success_element,
    )

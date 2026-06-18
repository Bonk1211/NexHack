"""Run orchestrator (§8, §20, §21).

Wires the already-built pieces into one end-to-end run: for each persona it
launches the navigator (app.agents.navigator), feeds the captured signals into
the pure scorer (app.scoring.engine), then assembles the §13 evidence pack
(app.evidence.pack). Personas run SEQUENTIALLY (§20) so a demo can narrate each
journey in turn and so per-persona RNG seeds stay reproducible.

This module is importable without any network/DB: persistence lives in
app.repository and is invoked by the route layer, not here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.agents.navigator import FlowStep, NavConfig, run_journey
from app.evidence.pack import PersonaRunResult, build_pack
from app.scoring.engine import score
from app.scoring.personas import load_persona, thresholds_for

# The demo fixture flow (§20, §22): enter the OTP (critical), then submit (critical).
DEFAULT_FLOW: list[FlowStep] = [
    FlowStep("otp", "fill", role="textbox", critical=True),
    FlowStep("submit", "click", role="button", name="Submit", critical=True),
]


def _requires_labels(persona: dict, thresholds_block: dict) -> bool:
    """Persona depends on labels/SR semantics (drives the nav agent's label check)."""
    disabilities = persona.get("disabilities", [])
    return ("low_vision" in disabilities) or bool(thresholds_block.get("require_labels"))


def run_assessment(
    app_name: str,
    target_url: str,
    persona_names: list[str],
    flow: list[FlowStep] | None = None,
    seed: int = 1337,
    artifact_root: str | None = None,
) -> dict:
    """Run one assessment across personas, sequentially, and build the evidence pack.

    Returns the §13 pack dict with an extra `screenshots` key mapping each persona
    to its per-step screenshot paths (None where no artifact_root was given).
    """
    flow = flow if flow is not None else DEFAULT_FLOW

    runs: list[PersonaRunResult] = []
    screenshots: dict[str, list[str | None]] = {}

    for i, name in enumerate(persona_names):
        persona = load_persona(name)
        thresholds_block = persona.get("thresholds", {})
        behavior_profile = persona.get("behavior_profile", {})

        cfg = NavConfig(
            target_url=target_url,
            flow=flow,
            behavior_profile=behavior_profile,
            requires_labels=_requires_labels(persona, thresholds_block),
            # Per-persona offset keeps personas distinct yet the whole run reproducible.
            seed=seed + i,
            artifact_dir=f"{artifact_root}/{name}" if artifact_root else None,
        )

        journey = run_journey(cfg)
        thresholds = thresholds_for(persona)
        result = score(journey.steps, thresholds)

        runs.append(
            PersonaRunResult(
                persona=name,
                steps=tuple(journey.steps),
                thresholds=thresholds,
                result=result,
            )
        )
        screenshots[name] = journey.screenshots

    run_at = datetime.now(timezone.utc).isoformat()
    pack = build_pack(app_name, run_at, runs)
    pack["screenshots"] = screenshots
    return pack

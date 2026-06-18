"""Run orchestration routes (§8 orchestrator). SCAFFOLD — wiring only.

Build order (§21): the orchestrator launches one nav agent per persona,
streams dual signals into the scorer, then builds the evidence pack.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    app_id: str
    persona_names: list[str]
    seed: int = 1337          # §16 deterministic runs
    mode: str = "sequential"  # §20: sequential for clean demo narration


@router.post("")
def start_run(req: StartRunRequest) -> dict:
    # TODO(§8,§21): orchestrate per-persona nav agents (app.agents.navigator),
    # capture dual signals (app.agents.signals), score (app.scoring.score),
    # persist run/run_personas/screen_events, then build evidence pack.
    raise NotImplementedError("orchestrator not implemented — scaffold")


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    # TODO: read run + run_personas + friction matrix from Supabase (app.db).
    raise NotImplementedError("scaffold")

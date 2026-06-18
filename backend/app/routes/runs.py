"""Run orchestration routes (§8 orchestrator).

The orchestrator (app.orchestrator) launches one nav agent per persona
SEQUENTIALLY (§20), scores each journey, then builds the evidence pack. The pack
is held in an in-memory store keyed by run_id so the API is usable without a DB;
persistence (app.repository) is invoked best-effort and never blocks the response.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import orchestrator, repository

router = APIRouter(prefix="/runs", tags=["runs"])

# In-memory store {run_id: pack}. Survives only for the process lifetime.
_STORE: dict[str, dict] = {}


class StartRunRequest(BaseModel):
    app_name: str
    target_url: str
    persona_names: list[str]
    seed: int = 1337           # §16 deterministic runs
    mode: str = "sequential"   # §20: sequential for clean demo narration


@router.post("")
def start_run(req: StartRunRequest) -> dict:
    pack = orchestrator.run_assessment(
        app_name=req.app_name,
        target_url=req.target_url,
        persona_names=req.persona_names,
        seed=req.seed,
    )
    run_id = str(uuid.uuid4())
    _STORE[run_id] = pack

    # Best-effort persistence — swallow DB errors so the demo path never breaks.
    try:
        repository.persist_run(pack)
    except Exception:
        pass

    return {"run_id": run_id, "pack": pack}


@router.get("")
def list_runs() -> list[dict]:
    return [
        {"run_id": rid, "app": pack.get("app"), "inclusion_score": pack.get("inclusion_score")}
        for rid, pack in _STORE.items()
    ]


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    pack = _STORE.get(run_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="run not found")
    return pack

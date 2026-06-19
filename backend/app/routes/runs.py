"""Run orchestration routes (§8 orchestrator).

The orchestrator (app.orchestrator) launches one nav agent per persona
SEQUENTIALLY (§20), scores each journey, then builds the evidence pack. The pack
is held in an in-memory store keyed by run_id so the API is usable without a DB;
persistence (app.repository) is invoked best-effort and never blocks the response.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app import orchestrator, repository
from app.evidence.export import pack_to_json_bytes, pack_to_pdf_bytes

router = APIRouter(prefix="/runs", tags=["runs"])

# In-memory store {run_id: pack}. Survives only for the process lifetime.
_STORE: dict[str, dict] = {}


class StartRunRequest(BaseModel):
    app_name: str
    target_url: str
    persona_names: list[str]
    seed: int = 1337           # §16 deterministic runs
    mode: str = "sequential"   # §20: sequential for clean demo narration
    run_id: str | None = None  # reuse to resume an interrupted run (§8 checkpoint)


@router.post("")
def start_run(req: StartRunRequest) -> dict:
    # run_id doubles as the run graph's checkpointer thread_id. A client may pass an
    # existing id to RESUME an interrupted run; re-POSTing a completed id is idempotent
    # (returns the existing pack), neither re-runs nor duplicates personas.
    run_id = req.run_id or str(uuid.uuid4())
    pack = orchestrator.run_assessment(
        app_name=req.app_name,
        target_url=req.target_url,
        persona_names=req.persona_names,
        seed=req.seed,
        run_id=run_id,
    )
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


def _safe_slug(text: str) -> str:
    """Filename-safe slug for the Content-Disposition download name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "evidence"


@router.get("/{run_id}/export")
def export_run(run_id: str, format: str = "json") -> Response:
    """Download the §13 evidence pack as a compliance artifact (FR-4.1).

    `format=json` (canonical, machine-readable) or `format=pdf` (audit deliverable).
    Renders the in-memory pack on demand; both share the two-stream layout (§16).
    """
    pack = _STORE.get(run_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="run not found")

    fmt = format.lower()
    if fmt not in ("json", "pdf"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'pdf'")

    stem = f"inclusionscope_{_safe_slug(str(pack.get('app', 'app')))}_{run_id[:8]}"
    if fmt == "pdf":
        body, media = pack_to_pdf_bytes(pack), "application/pdf"
    else:
        body, media = pack_to_json_bytes(pack), "application/json"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{stem}.{fmt}"'},
    )

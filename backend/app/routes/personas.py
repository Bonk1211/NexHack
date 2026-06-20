"""Persona CRUD + figurine generation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app import figurine as fig_module
from app import repository

router = APIRouter(prefix="/personas", tags=["personas"])


class IdentityIn(BaseModel):
    name: str
    label: str = ""
    ageBand: str = "25–34"
    language: str = "English"
    techSavviness: float = 0.5
    disabilities: list[str] = []


class BehaviorIn(BaseModel):
    dwellMultiplier: float = 1.0
    giveupThresholdS: float = 60.0
    misinterpretProb: float = 0.2


class PersonaIn(BaseModel):
    identity: IdentityIn
    behavior: BehaviorIn = BehaviorIn()


@router.get("")
def list_personas() -> list[dict]:
    return repository.list_personas()


@router.post("", status_code=201)
def create_persona(body: PersonaIn) -> dict:
    p = repository.create_persona(body.identity.model_dump(), body.behavior.model_dump())
    if not p:
        raise HTTPException(status_code=500, detail="DB write failed")
    return p


@router.get("/{slug}")
def get_persona(slug: str) -> dict:
    p = repository.get_persona_by_slug(slug)
    if not p:
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    return p


@router.put("/{slug}")
def update_persona(slug: str, body: PersonaIn) -> dict:
    p = repository.update_persona(slug, body.identity.model_dump(), body.behavior.model_dump())
    if not p:
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    return p


@router.delete("/{slug}", status_code=204)
def delete_persona(slug: str) -> None:
    repository.delete_persona(slug)


# ── Figurine generation ───────────────────────────────────────

@router.post("/{slug}/figurine", status_code=202)
def trigger_figurine(slug: str, background_tasks: BackgroundTasks) -> dict:
    """Kick off async figurine generation. Returns immediately with status=generating."""
    row = repository.get_raw_persona_row(slug)
    if not row:
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    repository.set_figurine_status(slug, "generating")
    background_tasks.add_task(fig_module.generate_and_store, slug, row)
    return {"status": "generating"}


@router.get("/{slug}/figurine")
def poll_figurine(slug: str) -> dict:
    """Poll current figurine status + url."""
    row = repository.get_raw_persona_row(slug)
    if not row:
        raise HTTPException(status_code=404, detail=f"Persona '{slug}' not found")
    return {
        "status": row.get("figurine_status", "none"),
        "url": row.get("figurine_url"),
    }

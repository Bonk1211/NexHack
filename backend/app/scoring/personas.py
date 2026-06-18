"""Persona library loader (§7, §11).

Reads the JSON persona configs from the repo-root `personas/` directory and
exposes their thresholds to the scorer. A persona = behavior_profile (drives the
nav agent) + thresholds (drives the scorer). Both, or it's a costume (§23).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.scoring.engine import PersonaThresholds

# personas/ lives at repo root: backend/app/scoring/personas.py -> ../../../personas
PERSONA_DIR = Path(__file__).resolve().parents[3] / "personas"


def load_persona(name: str) -> dict:
    """Load a single persona config by file stem (e.g. 'oku_visual')."""
    path = PERSONA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"persona config not found: {path}")
    return json.loads(path.read_text())


def load_library() -> dict[str, dict]:
    """Load the full persona library, keyed by persona name."""
    return {p.stem: json.loads(p.read_text()) for p in sorted(PERSONA_DIR.glob("*.json"))}


def thresholds_for(persona: dict) -> PersonaThresholds:
    """Build the scorer's PersonaThresholds from a persona config's `thresholds` block."""
    t = persona.get("thresholds", {})
    bp = persona.get("behavior_profile", {})
    return PersonaThresholds(
        max_dwell_s=float(t.get("max_dwell_s", 30.0)),
        giveup_threshold_s=float(bp.get("giveup_threshold_s", 60.0)),
        retry_limit=int(bp.get("retry_limit", 3)),
        max_reading_grade=float(t.get("max_reading_grade", 12.0)),
        min_tap_target_px=int(t.get("min_tap_target_px", 44)),
    )

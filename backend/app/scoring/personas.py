"""Persona library loader (§7, §11).

Reads persona configs from the Supabase `personas` table (primary) or falls back
to JSON files in the repo-root `personas/` directory. A persona = behavior_profile
(drives the nav agent) + thresholds (drives the scorer). Both, or it's a costume (§23).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.scoring.engine import PersonaThresholds

# personas/ lives at repo root: backend/app/scoring/personas.py -> ../../../personas
PERSONA_DIR = Path(__file__).resolve().parents[3] / "personas"


def _has_creds() -> bool:
    from app.config import settings
    return bool(settings.supabase_url and settings.supabase_key)


def load_persona(name: str) -> dict:
    """Load a single persona config by slug (e.g. 'p-siti' or 'siti')."""
    if _has_creds():
        from app.db import get_client
        client = get_client()
        # Try exact slug first, then with/without p- prefix
        slugs = [name]
        if name.startswith("p-"):
            slugs.append(name[2:])
        else:
            slugs.append(f"p-{name}")
        for slug in slugs:
            rows = client.table("personas").select("*").eq("slug", slug).limit(1).execute().data or []
            if rows:
                return _row_to_persona_config(rows[0])
    # Fallback to JSON files
    clean_name = name[2:] if name.startswith("p-") else name
    path = PERSONA_DIR / f"{clean_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"persona config not found: {path}")
    return json.loads(path.read_text())


def _row_to_persona_config(row: dict) -> dict:
    """Convert a personas table row to the config dict expected by the agent."""
    bp = row.get("behavior_profile") or {}
    thresholds = row.get("thresholds") or {}
    return {
        "name": row.get("name", ""),
        "label": row.get("label", ""),
        "language": row.get("language", "English"),
        "disabilities": row.get("disabilities") or [],
        "behavior_profile": {
            "dwell_multiplier": float(bp.get("dwell_multiplier", 1.0)),
            "hesitation_prob": float(bp.get("hesitation_prob", 0.0)),
            "reading_speed_wpm": float(bp.get("reading_speed_wpm", 200)),
            "giveup_threshold_s": float(bp.get("giveup_threshold_s", 60)),
            "retry_limit": int(bp.get("retry_limit", 3)),
        },
        "thresholds": {
            "max_dwell_s": float(thresholds.get("max_dwell_s", 30)),
            "max_reading_grade": float(thresholds.get("max_reading_grade", 12)),
            "min_tap_target_px": int(thresholds.get("min_tap_target_px", 44)),
            "require_labels": thresholds.get("require_labels", False),
            "require_contrast_aa": thresholds.get("require_contrast_aa", False),
        },
        "misinterpret_prob": float(row.get("misinterpret_prob") or 0),
    }


def load_library() -> dict[str, dict]:
    """Load the full persona library, keyed by slug."""
    if _has_creds():
        from app.db import get_client
        client = get_client()
        rows = client.table("personas").select("*").order("created_at").execute().data or []
        return {row["slug"]: _row_to_persona_config(row) for row in rows}
    # Fallback to JSON files
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

"""Evidence pack builder (§13). SCAFFOLD — the highest-priority build item.

This is the differentiated output that carries the marks a demo can't (§13, §24).
Per app, per run it produces: exec summary, persona x step friction matrix (hero
artifact), WCAG findings (trusted, mapped to criteria + screenshot), empathy-replay
clips, prioritized remediation routed to owning area, and a PDF/JSON export.

Structure keeps `wcag_conformance` (trusted) distinct from `behavioral_note`
(indicative) — §16.
"""
from __future__ import annotations

from app.scoring.engine import ScoreResult


def build_friction_matrix(per_persona: dict[str, list]) -> dict:
    """Persona x step matrix (green/amber/red, dwell + verdict per cell). FR-3.3.

    TODO: assemble cells from each persona's per-step verdicts + dwell.
    """
    raise NotImplementedError("scaffold")


def route_owner(issue: str, wcag_failures: list[str]) -> str:
    """Map an issue to its owning area (FR-4.3): frontend / content / i18n / backend."""
    # TODO(§9.4): real routing heuristics. Placeholder mapping below.
    if any(c in ("1.4.3", "2.5.8", "2.4.3") for c in wcag_failures):
        return "@frontend"
    if any(c in ("1.3.1", "4.1.2", "1.1.1") for c in wcag_failures):
        return "@content"
    return "@frontend"


def build_pack(run_id: str, results: dict[str, ScoreResult]) -> dict:
    """Assemble the evidence pack JSON (§13 schema) from per-persona ScoreResults.

    TODO(FR-4.1): exec summary + inclusion_score, friction matrix, WCAG findings
    with screenshots, empathy-replay refs, prioritized routed remediation; then
    render PDF and persist JSON to Supabase Storage. Keep trusted vs indicative
    fields separate (§16).
    """
    raise NotImplementedError("evidence pack builder not implemented — scaffold")

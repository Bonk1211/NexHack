"""Evidence pack builder (§13) — the highest-priority build item.

The differentiated output that carries the marks a demo can't (§13, §24). Per app,
per run it assembles: exec summary, persona x step friction matrix (the hero
artifact, FR-3.3), WCAG findings (trusted, mapped to criteria), prioritized
remediation routed to owning area (FR-4.3), and a JSON export (PDF is a thin
render on top — stubbed). Empathy-replay clips are referenced by screenshot/replay
URL, produced by the nav agent.

Two-stream discipline (§16): `wcag_conformance` (trusted) stays distinct from
`behavioral_note` (indicative) everywhere in the output.

This module is PURE (no I/O) so it is unit-testable like the scorer. Persistence
(Supabase Storage, PDF render) lives in the orchestrator, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.scoring.engine import (
    PersonaThresholds,
    ScoreResult,
    StepSignals,
    step_status,
)

# WCAG criterion -> owning area (FR-4.3). Trusted failures route deterministically.
_OWNER_BY_CRITERION = {
    "1.4.3": "@frontend",   # contrast
    "2.5.8": "@frontend",   # tap-target size
    "2.4.3": "@frontend",   # focus order
    "1.3.1": "@content",    # info & relationships / labels
    "4.1.2": "@content",    # name/role/value
    "1.1.1": "@content",    # text alternatives
}

# Severity rank for prioritization (P0 worst).
_SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, None: 4}

# Human-readable issue text per criterion, for the remediation list.
_ISSUE_TEXT = {
    "1.4.3": "Text/control contrast below WCAG AA",
    "2.5.8": "Tap target smaller than minimum size",
    "2.4.3": "Broken or illogical focus order",
    "1.3.1": "Form control missing programmatic label",
    "4.1.2": "Control missing accessible name/role/value",
    "1.1.1": "Non-text content missing text alternative",
}


@dataclass(frozen=True)
class PersonaRunResult:
    """One persona's journey + its scored result, fed into the pack."""
    persona: str
    steps: tuple[StepSignals, ...]
    thresholds: PersonaThresholds
    result: ScoreResult


def route_owner(wcag_failures: list[str]) -> str:
    """Map an issue's WCAG failures to its owning area (FR-4.3)."""
    for crit in wcag_failures:
        owner = _OWNER_BY_CRITERION.get(crit)
        if owner:
            return owner
    return "@frontend"


def build_friction_matrix(runs: list[PersonaRunResult]) -> dict:
    """Persona x step matrix (FR-3.3). Each cell: status + dwell + verdict.

    The hero diff (§14): the same step shows green for `control` and red for a
    protected persona.
    """
    step_keys: list[str] = []
    for r in runs:
        for s in r.steps:
            if s.step_key not in step_keys:
                step_keys.append(s.step_key)

    rows = {}
    for r in runs:
        by_key = {s.step_key: s for s in r.steps}
        rows[r.persona] = {
            key: (
                {
                    "status": step_status(by_key[key], r.thresholds),
                    "dwell_s": by_key[key].dwell_s,
                }
                if key in by_key
                else {"status": "na", "dwell_s": None}
            )
            for key in step_keys
        }
    return {"steps": step_keys, "rows": rows}


def build_remediation(runs: list[PersonaRunResult]) -> list[dict]:
    """Prioritized, routed remediation list (§13). One entry per failing criterion,
    tagged with the worst severity any persona hit it at."""
    worst: dict[str, dict] = {}
    for r in runs:
        sev = r.result.persona_verdict.severity
        for crit, verdict in r.result.wcag_conformance.items():
            if verdict != "fail":
                continue
            rank = _SEVERITY_RANK.get(sev, 4)
            if crit not in worst or rank < _SEVERITY_RANK.get(worst[crit]["severity"], 4):
                worst[crit] = {
                    "criterion": crit,
                    "issue": _ISSUE_TEXT.get(crit, f"WCAG {crit} failure"),
                    "owner": route_owner([crit]),
                    "severity": sev,
                }
    return sorted(worst.values(), key=lambda x: _SEVERITY_RANK.get(x["severity"], 4))


def _step_detail(s: StepSignals) -> dict:
    """Per-step evidence row, two streams kept distinct (§16).

    `wcag_conformance` is TRUSTED (axe-derived, reportable on its own);
    `llm_judgment` is INDICATIVE (persona-simulation confusion). Never collapsed.
    """
    wcag = {sig.criterion: ("pass" if sig.passed else "fail") for sig in s.wcag}
    return {
        "step_idx": s.step_idx,
        "step_key": s.step_key,
        "critical": s.critical,
        "dwell_s": s.dwell_s,
        "retries": s.retries,
        "backtracked": s.retries > 0,
        "dead_end": s.dead_end,
        "completed": s.completed,
        "reading_grade": s.reading_grade,
        "wcag_conformance": wcag,                                   # TRUSTED
        "axe_violations": [c for c, v in wcag.items() if v == "fail"],
        "llm_judgment": {"confusion": s.llm_confusion},             # INDICATIVE
    }


def build_pack(app: str, run_at: str, runs: list[PersonaRunResult]) -> dict:
    """Assemble the §13 evidence pack JSON from per-persona results.

    `inclusion_score` is the mean composite across personas (derived, §16) — the
    two underlying streams travel with each persona entry, never collapsed.
    """
    # Trusted WCAG roll-up: a criterion is "fail" if it failed for ANY persona.
    conformance: dict[str, str] = {}
    for r in runs:
        for crit, verdict in r.result.wcag_conformance.items():
            if conformance.get(crit) == "fail":
                continue
            conformance[crit] = verdict

    personas = [
        {
            "persona": r.persona,
            "verdict": r.result.persona_verdict.verdict,          # INDICATIVE
            "severity": r.result.persona_verdict.severity,
            "blocked_at": r.result.persona_verdict.blocked_at,
            "wcag_failures": [c for c, v in r.result.wcag_conformance.items() if v == "fail"],
            "behavioral_note": "indicative — persona-simulation signal",
            "inclusion_score": r.result.composite.inclusion_score,
            "steps": [_step_detail(s) for s in r.steps],   # per-step trusted+indicative (§16)
        }
        for r in runs
    ]

    scores = [r.result.composite.inclusion_score for r in runs]
    inclusion_score = round(sum(scores) / len(scores), 4) if scores else 1.0

    return {
        "app": app,
        "run_at": run_at,                       # ISO-8601, supplied by orchestrator
        "inclusion_score": inclusion_score,
        "wcag_conformance": conformance,        # TRUSTED, reportable on its own (§16)
        "matrix": build_friction_matrix(runs),  # hero artifact (FR-3.3)
        "personas": personas,
        "remediation": build_remediation(runs),
        # TODO: pdf_url / json_url filled by orchestrator after persisting to Storage.
        # TODO(§14): attach empathy-replay clip refs per persona (screenshot/replay URLs).
    }

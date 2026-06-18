"""Scoring engine — PRD §16.

The defensible core. Properties (non-negotiable, §16):
  - PURE function, zero I/O — exhaustively unit-testable.
  - Deterministic. Any persona hesitation/RNG lives in the behavior agent
    (app/agents), NOT here; the scorer only consumes already-captured signals.
  - Weights live in config and are surfaced (ScoreWeights), for defensibility.
  - Emits THREE results and NEVER collapses the trusted stream into the composite:
      1. wcag_conformance  (TRUSTED   — straight from axe-core / a11y signals)
      2. persona_verdict   (INDICATIVE — completion + severity, labeled indicative)
      3. composite         (OPTIONAL, DERIVED — convenience roll-up only)

Severity model: PRD §12. Severity = protected-group impact x step criticality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# --- Inputs -----------------------------------------------------------------

@dataclass(frozen=True)
class WcagSignal:
    """One machine-verifiable WCAG check on a step (TRUSTED, §10)."""
    criterion: str  # e.g. "1.4.3"
    passed: bool


@dataclass(frozen=True)
class StepSignals:
    """All signals captured for one step of one persona's journey."""
    step_idx: int
    step_key: str
    critical: bool = False                      # step criticality (§12) — KYC > footer
    wcag: tuple[WcagSignal, ...] = ()           # TRUSTED stream (axe-core)
    dwell_s: float = 0.0                         # INDICATIVE behavioral stream below
    retries: int = 0
    dead_end: bool = False
    completed: bool = True
    llm_confusion: float = 0.0                   # 0-1, vision-LLM "I don't know this field"
    reading_grade: Optional[float] = None        # Flesch-Kincaid grade of step copy


@dataclass(frozen=True)
class PersonaThresholds:
    """Per-persona pass/fail overrides (§11). One shared threshold defeats the thesis."""
    max_dwell_s: float = 30.0
    giveup_threshold_s: float = 60.0
    retry_limit: int = 3
    max_reading_grade: float = 12.0
    min_tap_target_px: int = 44                  # informational; 2.5.8 enforced via wcag stream


@dataclass(frozen=True)
class ScoreWeights:
    """Composite weights (§16) — surfaced and tunable. WCAG (trusted) weighted highest."""
    behavioral: float = 0.30
    wcag: float = 0.50
    llm: float = 0.20


# --- Output -----------------------------------------------------------------

@dataclass(frozen=True)
class PersonaVerdict:
    verdict: str                 # "completed" | "blocked"  (INDICATIVE)
    blocked_at: Optional[str]    # step_key where first blocked, else None
    severity: Optional[str]      # "P0".."P3" or None when clean


@dataclass(frozen=True)
class Composite:
    inclusion_score: float       # derived roll-up, 0-1
    wcag_score: float
    behavioral_score: float
    llm_score: float
    weights: ScoreWeights


@dataclass(frozen=True)
class ScoreResult:
    wcag_conformance: dict[str, str]   # TRUSTED: {criterion: "pass"|"fail"}
    persona_verdict: PersonaVerdict    # INDICATIVE
    composite: Composite               # OPTIONAL, DERIVED — never a substitute for the above


# --- Pure helpers -----------------------------------------------------------

def _step_blocks(step: StepSignals, t: PersonaThresholds) -> bool:
    """Does this step fully stop the persona? (drives 'blocked' verdict)"""
    return (
        step.dead_end
        or not step.completed
        or step.dwell_s >= t.giveup_threshold_s
        or step.retries > t.retry_limit
    )


def _step_ok(step: StepSignals, t: PersonaThresholds) -> bool:
    """Did the step go cleanly for this persona? (drives behavioral score)"""
    if _step_blocks(step, t):
        return False
    if step.dwell_s > t.max_dwell_s:
        return False
    if step.reading_grade is not None and step.reading_grade > t.max_reading_grade:
        return False
    return True


def _has_friction(step: StepSignals, t: PersonaThresholds) -> bool:
    """Completed but hard — the P2 band."""
    if _step_blocks(step, t):
        return False
    return (
        step.dwell_s > t.max_dwell_s
        or step.llm_confusion >= 0.5
        or (step.reading_grade is not None and step.reading_grade > t.max_reading_grade)
    )


def step_status(step: StepSignals, t: PersonaThresholds) -> str:
    """Per-cell status for the friction matrix (§14, FR-3.3): red/amber/green."""
    if _step_blocks(step, t):
        return "red"
    if _has_friction(step, t):
        return "amber"
    return "green"


# --- The scorer -------------------------------------------------------------

def score(
    steps: list[StepSignals],
    thresholds: PersonaThresholds,
    weights: ScoreWeights = ScoreWeights(),
) -> ScoreResult:
    """Pure scoring function. score(signals) -> {wcag, verdict, composite} (§16)."""
    if not steps:
        empty_w = {}
        return ScoreResult(
            wcag_conformance=empty_w,
            persona_verdict=PersonaVerdict("completed", None, None),
            composite=Composite(1.0, 1.0, 1.0, 1.0, weights),
        )

    # 1) WCAG conformance (TRUSTED). A criterion fails if it fails on ANY step.
    conformance: dict[str, str] = {}
    for step in steps:
        for sig in step.wcag:
            prev = conformance.get(sig.criterion)
            if prev == "fail":
                continue
            conformance[sig.criterion] = "pass" if sig.passed else "fail"

    # Which criteria failed, and did any fail on a critical step?
    any_wcag_fail = any(v == "fail" for v in conformance.values())
    any_wcag_fail_critical = any(
        step.critical and any((not s.passed) for s in step.wcag) for step in steps
    )

    # 2) Persona verdict (INDICATIVE).
    blocked_at: Optional[str] = None
    blocked_critical = False
    for step in steps:
        if _step_blocks(step, thresholds):
            blocked_at = step.step_key
            blocked_critical = step.critical
            break
    blocked = blocked_at is not None
    friction = any(_has_friction(step, thresholds) for step in steps)
    max_confusion = max(step.llm_confusion for step in steps)

    if blocked and blocked_critical:
        severity = "P0"
    elif blocked:
        severity = "P1"
    elif any_wcag_fail_critical:
        severity = "P1"
    elif friction:
        severity = "P2"
    elif any_wcag_fail or max_confusion > 0.0:
        severity = "P3"
    else:
        severity = None

    verdict = PersonaVerdict(
        verdict="blocked" if blocked else "completed",
        blocked_at=blocked_at,
        severity=severity,
    )

    # 3) Composite (OPTIONAL, DERIVED). Never replaces the two streams above.
    n = len(steps)
    behavioral_score = sum(1.0 for s in steps if _step_ok(s, thresholds)) / n
    total_crit = len(conformance)
    wcag_score = (
        sum(1.0 for v in conformance.values() if v == "pass") / total_crit
        if total_crit
        else 1.0
    )
    llm_score = 1.0 - (sum(s.llm_confusion for s in steps) / n)

    raw = (
        weights.behavioral * behavioral_score
        + weights.wcag * wcag_score
        + weights.llm * llm_score
    )
    inclusion_score = max(0.0, min(1.0, raw))

    composite = Composite(
        inclusion_score=round(inclusion_score, 4),
        wcag_score=round(wcag_score, 4),
        behavioral_score=round(behavioral_score, 4),
        llm_score=round(llm_score, 4),
        weights=weights,
    )

    return ScoreResult(conformance, verdict, composite)

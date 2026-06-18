"""Scorer tests — PRD §22 ("test it hardest").

Covers: trusted/indicative/composite separation, WCAG aggregation, every
severity band (P0-P3 + clean), determinism, and weight configurability.
"""
from __future__ import annotations

from app.scoring.engine import (
    PersonaThresholds,
    ScoreWeights,
    StepSignals,
    WcagSignal,
    score,
)

T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)


def _clean_step(idx=0, key="home", critical=False):
    return StepSignals(
        step_idx=idx,
        step_key=key,
        critical=critical,
        wcag=(WcagSignal("1.4.3", True), WcagSignal("1.3.1", True)),
        dwell_s=5.0,
        retries=0,
        completed=True,
        llm_confusion=0.0,
        reading_grade=6.0,
    )


def test_clean_journey_passes_all_streams():
    r = score([_clean_step(0), _clean_step(1, "otp", critical=True)], T)
    assert r.wcag_conformance == {"1.4.3": "pass", "1.3.1": "pass"}
    assert r.persona_verdict.verdict == "completed"
    assert r.persona_verdict.severity is None
    assert r.composite.inclusion_score == 1.0


def test_empty_journey_is_neutral():
    r = score([], T)
    assert r.persona_verdict.verdict == "completed"
    assert r.composite.inclusion_score == 1.0


def test_wcag_fail_aggregates_across_steps():
    # 1.3.1 passes on step 0 but fails on step 1 -> overall fail (trusted stream).
    steps = [
        _clean_step(0),
        StepSignals(1, "otp", critical=True, wcag=(WcagSignal("1.3.1", False),), dwell_s=4),
    ]
    r = score(steps, T)
    assert r.wcag_conformance["1.3.1"] == "fail"
    assert r.wcag_conformance["1.4.3"] == "pass"


def test_p0_blocked_at_critical_step():
    # Low-vision can't submit at OTP -> dead end on a critical step.
    steps = [
        _clean_step(0),
        StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", False),), dead_end=True,
                    completed=False),
    ]
    r = score(steps, T)
    assert r.persona_verdict.verdict == "blocked"
    assert r.persona_verdict.blocked_at == "otp"
    assert r.persona_verdict.severity == "P0"


def test_p1_blocked_at_noncritical_step():
    steps = [
        _clean_step(0),
        StepSignals(1, "promo", critical=False, dead_end=True, completed=False),
    ]
    r = score(steps, T)
    assert r.persona_verdict.severity == "P1"


def test_p1_wcag_fail_on_critical_but_completed():
    # Contrast fails AA on a primary CTA, persona still scrapes through.
    steps = [
        _clean_step(0),
        StepSignals(1, "pay", critical=True, wcag=(WcagSignal("1.4.3", False),), dwell_s=4,
                    completed=True),
    ]
    r = score(steps, T)
    assert r.persona_verdict.verdict == "completed"
    assert r.persona_verdict.severity == "P1"


def test_p2_friction_high_dwell():
    steps = [
        _clean_step(0),
        StepSignals(1, "form", critical=False, wcag=(WcagSignal("1.3.1", True),), dwell_s=45,
                    completed=True),
    ]
    r = score(steps, T)
    assert r.persona_verdict.verdict == "completed"
    assert r.persona_verdict.severity == "P2"


def test_p3_minor_noncritical_wcag_fail():
    # Untranslated footer string: non-critical fail, no friction, completed.
    steps = [
        _clean_step(0),
        StepSignals(1, "footer", critical=False, wcag=(WcagSignal("1.1.1", False),), dwell_s=4,
                    completed=True, llm_confusion=0.0, reading_grade=5.0),
    ]
    r = score(steps, T)
    assert r.persona_verdict.severity == "P3"


def test_determinism_same_input_same_output():
    steps = [_clean_step(0), _clean_step(1, "otp", critical=True)]
    assert score(steps, T) == score(steps, T)


def test_composite_drops_when_wcag_fails():
    good = score([_clean_step(0)], T).composite.inclusion_score
    bad = score(
        [StepSignals(0, "home", wcag=(WcagSignal("1.4.3", False), WcagSignal("1.3.1", False)),
                     dwell_s=5)],
        T,
    ).composite.inclusion_score
    assert bad < good


def test_weights_are_configurable_and_surfaced():
    steps = [_clean_step(0)]
    w = ScoreWeights(behavioral=0.1, wcag=0.8, llm=0.1)
    r = score(steps, T, w)
    assert r.composite.weights == w


def test_giveup_threshold_blocks_before_max_dwell_only_friction():
    # dwell over max_dwell (30) but under giveup (60) -> friction, not blocked.
    friction = score([StepSignals(0, "s", dwell_s=40, completed=True)], T)
    assert friction.persona_verdict.verdict == "completed"
    # dwell over giveup -> blocked.
    blocked = score([StepSignals(0, "s", dwell_s=65, completed=True)], T)
    assert blocked.persona_verdict.verdict == "blocked"

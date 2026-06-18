"""Contract tests (§22): the real Playwright loop against committed fixtures.

Asserts the trusted stream catches the planted WCAG flaws, that persona behavior
differentiates the verdict on the SAME screen (the §14 hero diff), and that the
clean control page returns no violations. Launches headless chromium — slower
than the pure scorer tests, but this is the layer §22 wants contract-tested.
"""
from __future__ import annotations

import pathlib

import pytest

from app.agents.navigator import FlowStep, NavConfig, run_journey
from app.scoring.engine import PersonaThresholds, score

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAWED = (ROOT / "fixture-site" / "index.html").as_uri()
CLEAN = (ROOT / "fixture-site" / "control.html").as_uri()

# The flow under test: enter OTP (critical), then submit (critical).
FLOW = [
    FlowStep("otp", "fill", role="textbox", critical=True),
    FlowStep("submit", "click", role="button", name="Submit", critical=True),
]

T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)

# Minimal behavior profiles (subset of personas/*.json).
CONTROL_BP = {"dwell_multiplier": 1.0, "reading_speed_wpm": 220, "hesitation_prob": 0.0,
              "giveup_threshold_s": 60}
VISUAL_BP = {"dwell_multiplier": 1.5, "reading_speed_wpm": 140, "hesitation_prob": 0.0,
             "giveup_threshold_s": 60}


@pytest.fixture(scope="module")
def flawed_control_journey():
    cfg = NavConfig(FLAWED, FLOW, behavior_profile=CONTROL_BP, requires_labels=False, seed=1)
    return run_journey(cfg)


def test_trusted_stream_catches_planted_flaws(flawed_control_journey):
    # axe is attached to the entry step; planted contrast (1.4.3) + label (4.1.2) fail.
    r = score(flawed_control_journey.steps, T)
    assert r.wcag_conformance.get("1.4.3") == "fail"
    assert r.wcag_conformance.get("4.1.2") == "fail"


def test_control_persona_completes_flawed_screen(flawed_control_journey):
    # Baseline user gets through (no label dependency) — but it's flagged P1
    # because a trusted WCAG failure lands on a critical step.
    r = score(flawed_control_journey.steps, T)
    assert r.persona_verdict.verdict == "completed"
    assert r.persona_verdict.severity == "P1"


def test_oku_visual_blocked_at_unlabeled_otp():
    # Same screen, persona that depends on labels -> dead end at the critical OTP step => P0.
    cfg = NavConfig(FLAWED, FLOW, behavior_profile=VISUAL_BP, requires_labels=True, seed=1)
    j = run_journey(cfg)
    r = score(j.steps, T)
    assert r.persona_verdict.verdict == "blocked"
    assert r.persona_verdict.blocked_at == "otp"
    assert r.persona_verdict.severity == "P0"


def test_clean_control_page_has_no_violations():
    cfg = NavConfig(CLEAN, FLOW, behavior_profile=VISUAL_BP, requires_labels=True, seed=1)
    j = run_journey(cfg)
    r = score(j.steps, T)
    assert "fail" not in r.wcag_conformance.values()
    assert r.persona_verdict.verdict == "completed"


def test_screenshot_captured_every_step(tmp_path):
    cfg = NavConfig(FLAWED, FLOW, behavior_profile=CONTROL_BP, requires_labels=False,
                    seed=1, artifact_dir=str(tmp_path))
    j = run_journey(cfg)
    shots = [s for s in j.screenshots if s]
    assert len(shots) == len(j.steps)
    assert all(pathlib.Path(s).exists() for s in shots)

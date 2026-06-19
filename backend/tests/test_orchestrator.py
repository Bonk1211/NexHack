"""E2E smoke for the orchestrator (§22).

Runs the real per-persona Playwright loop against the committed planted-flaw
fixture and asserts the full wired pack: trusted WCAG failures, the §14 hero diff
(control completes the same screen oku_visual is blocked on), the friction matrix
covering both personas, and a prioritized remediation list with a P0 first.
"""
from __future__ import annotations

import pathlib

import pytest

from app.orchestrator import run_assessment

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAWED = (ROOT / "fixture-site" / "index.html").as_uri()


@pytest.fixture(scope="module")
def pack():
    return run_assessment("DemoBank", FLAWED, ["control", "oku_visual"])


def test_trusted_wcag_failures(pack):
    # Planted flaws: low contrast (1.4.3) and unlabeled OTP (4.1.2).
    assert pack["wcag_conformance"]["1.4.3"] == "fail"
    assert pack["wcag_conformance"]["4.1.2"] == "fail"


def test_oku_visual_blocked_at_critical_otp(pack):
    entry = next(p for p in pack["personas"] if p["persona"] == "oku_visual")
    assert entry["verdict"] == "blocked"
    assert entry["severity"] == "P0"
    assert entry["blocked_at"] == "otp"


def test_control_completes_same_screen(pack):
    entry = next(p for p in pack["personas"] if p["persona"] == "control")
    assert entry["verdict"] == "completed"


def test_matrix_covers_both_personas(pack):
    rows = pack["matrix"]["rows"]
    assert "control" in rows
    assert "oku_visual" in rows


def test_remediation_prioritized_p0_first(pack):
    remediation = pack["remediation"]
    assert remediation, "remediation list should be non-empty"
    severities = [r["severity"] for r in remediation]
    assert remediation[0]["severity"] == "P0"
    # Sorted worst-first (P0 <= P1 <= ...).
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, None: 4}
    assert severities == sorted(severities, key=lambda s: rank.get(s, 4))

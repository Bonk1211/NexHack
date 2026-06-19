"""Persona subgraph tests (§8, §16, §23).

The cyclic subgraph must: terminate on a block, complete a clean screen, store
RAW signals only (no verdict), reproduce the pre-LLM heuristic offline, and treat
a block as a clean exit — never loop back to retry it away (§23). Runs against the
committed planted-flaw fixture, headless.
"""
from __future__ import annotations

import pathlib

from app.agents.navigator import FlowStep, NavConfig, run_journey
from app.agents.persona_graph import run_persona
from app.scoring.engine import PersonaThresholds, StepSignals, score

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAWED = (ROOT / "fixture-site" / "index.html").as_uri()
CLEAN = (ROOT / "fixture-site" / "control.html").as_uri()

FLOW = [
    FlowStep("otp", "fill", role="textbox", critical=True),
    FlowStep("submit", "click", role="button", name="Submit", critical=True),
]
T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)
CONTROL_BP = {"dwell_multiplier": 1.0, "reading_speed_wpm": 220, "hesitation_prob": 0.0,
              "giveup_threshold_s": 60}
VISUAL_BP = {"dwell_multiplier": 1.5, "reading_speed_wpm": 140, "hesitation_prob": 0.0,
             "giveup_threshold_s": 60}


def _payload(target, bp, requires_labels, *, artifact_dir=None):
    return {
        "persona": "p", "persona_idx": 0, "behavior_profile": bp,
        "requires_labels": requires_labels, "thresholds": T, "target_url": target,
        "flow": FLOW, "viewport": "iPhone 13", "seed": 1, "artifact_dir": artifact_dir,
    }


def test_subgraph_blocks_and_exits_at_unlabeled_otp(monkeypatch):
    # Label-dependent persona dead-ends at the critical OTP and the loop STOPS there.
    final = run_persona(_payload(FLAWED, VISUAL_BP, True))
    assert final["status"] == "blocked"
    assert final["blocked_at"] == "otp"
    assert len(final["steps"]) == 1                # did not advance past the block
    assert final["steps"][0].dead_end is True


def test_subgraph_completes_clean_page():
    final = run_persona(_payload(CLEAN, VISUAL_BP, True))
    assert final["status"] == "completed"
    assert len(final["steps"]) == len(FLOW)


def test_state_stores_raw_signals_not_a_verdict():
    # §16: the subgraph emits raw StepSignals; no precomputed verdict in state.
    final = run_persona(_payload(FLAWED, CONTROL_BP, False))
    assert all(isinstance(s, StepSignals) for s in final["steps"])
    assert "verdict" not in final and "severity" not in final


def test_offline_parity_with_pre_llm_heuristic(monkeypatch):
    # With no API key, confusion matches the old hardcode: 1.0 at unlabeled OTP
    # for a label-dependent persona, 0.0 otherwise.
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    blocked = run_persona(_payload(FLAWED, VISUAL_BP, True))
    assert blocked["steps"][0].llm_confusion == 1.0
    control = run_persona(_payload(FLAWED, CONTROL_BP, False))
    assert all(s.llm_confusion == 0.0 for s in control["steps"])


def test_block_is_clean_exit_no_retry_loop():
    # A block exits with exactly one step — it is NOT looped back / retried (§23).
    final = run_persona(_payload(FLAWED, VISUAL_BP, True))
    assert len(final["steps"]) == 1
    assert final["status"] == "blocked"


def test_run_journey_contract_preserved(tmp_path):
    # The NavConfig wrapper still returns aligned steps + screenshots (FR-1.3).
    cfg = NavConfig(FLAWED, FLOW, behavior_profile=CONTROL_BP, requires_labels=False,
                    seed=1, artifact_dir=str(tmp_path))
    j = run_journey(cfg)
    r = score(j.steps, T)
    assert r.wcag_conformance.get("4.1.2") == "fail"
    shots = [s for s in j.screenshots if s]
    assert len(shots) == len(j.steps)

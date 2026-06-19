"""Run-graph tests (§8, §13, §16, §20) — map-reduce + checkpoint resume.

Exercises the top-level graph: fan out N personas, fan in via the reducer,
reorder deterministically, score with the pure scorer, assemble the §13 pack with
synthesis, and resume from the per-run checkpoint. Offline (no API key) so the
synthesis is the deterministic template and there is no network.
"""
from __future__ import annotations

import pathlib

import pytest

from app.agents import run_graph as rg
from app.agents.run_graph import build_run_graph, fan_out, run_assessment

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAWED = (ROOT / "fixture-site" / "index.html").as_uri()


@pytest.fixture(autouse=True)
def _offline_and_temp_ckpt(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(rg.settings, "llm_api_key", "")
    monkeypatch.setattr(rg.settings, "checkpoint_db", str(tmp_path / "ckpt.sqlite"))


def test_fan_out_emits_one_send_per_persona():
    state = {
        "target_url": FLAWED, "viewport": "iPhone 13", "seed": 1, "artifact_root": None,
        "personas": [{**rg.load_persona(n), "stem": n} for n in ["control", "oku_visual", "low_literacy"]],
        "flow": rg.DEFAULT_FLOW,
    }
    sends = fan_out(state)
    assert [s.node for s in sends] == ["persona", "persona", "persona"]
    # per-persona seed offset (determinism under concurrency) + input order preserved
    assert [s.arg["seed"] for s in sends] == [1, 2, 3]
    assert [s.arg["persona_idx"] for s in sends] == [0, 1, 2]


@pytest.fixture(scope="module")
def pack():
    # module-scoped: one real headless run, reused across assertions
    import app.config as c
    import tempfile
    c.settings.llm_api_key = ""
    c.settings.checkpoint_db = tempfile.mktemp(suffix=".sqlite")
    return run_assessment("DemoBank", FLAWED, ["control", "oku_visual"], seed=1, run_id="rg-test")


def test_trusted_wcag_stream(pack):
    assert pack["wcag_conformance"]["1.4.3"] == "fail"
    assert pack["wcag_conformance"]["4.1.2"] == "fail"


def test_hero_diff_same_step_differs_by_persona(pack):
    # §14 hero diff: the OTP step is red for oku_visual, not red for control.
    rows = pack["matrix"]["rows"]
    assert rows["oku_visual"]["otp"]["status"] == "red"
    assert rows["control"]["otp"]["status"] != "red"


def test_aggregate_orders_personas_by_input(pack):
    # Output order is deterministic (input order) despite concurrent execution (§20).
    assert [p["persona"] for p in pack["personas"]] == ["control", "oku_visual"]


def test_score_node_derives_verdicts(pack):
    oku = next(p for p in pack["personas"] if p["persona"] == "oku_visual")
    assert oku["verdict"] == "blocked"
    assert oku["severity"] == "P0"


def test_evidence_attaches_synthesis(pack):
    assert "synthesis" in pack
    assert pack["synthesis"]["rollup"]
    assert "screenshots" in pack


def test_reinvoking_completed_run_id_is_idempotent(monkeypatch, tmp_path):
    # Re-invoking a COMPLETED run_id must return the same pack — NOT re-run and
    # NOT duplicate personas via the persona_results reducer. Assert the full
    # personas LIST (a verdict-dict would dedup and hide duplication).
    monkeypatch.setattr(rg.settings, "checkpoint_db", str(tmp_path / "resume.sqlite"))
    first = run_assessment("DemoBank", FLAWED, ["control", "oku_visual"], seed=1, run_id="resume-1")
    second = run_assessment("DemoBank", FLAWED, ["control", "oku_visual"], seed=1, run_id="resume-1")

    assert [p["persona"] for p in first["personas"]] == ["control", "oku_visual"]
    assert [p["persona"] for p in second["personas"]] == ["control", "oku_visual"]
    assert first["personas"] == second["personas"]


def test_fresh_run_id_each_time_does_not_share_state(monkeypatch, tmp_path):
    # Distinct run_ids in the same checkpoint DB stay isolated (no cross-run bleed).
    monkeypatch.setattr(rg.settings, "checkpoint_db", str(tmp_path / "iso.sqlite"))
    a = run_assessment("DemoBank", FLAWED, ["control", "oku_visual"], seed=1, run_id="iso-a")
    b = run_assessment("DemoBank", FLAWED, ["control"], seed=1, run_id="iso-b")
    assert len(a["personas"]) == 2
    assert len(b["personas"]) == 1


def test_compiled_graph_has_no_live_object_channels():
    # page/rng must never be parent-graph channels (checkpoint-serializable only).
    channels = build_run_graph().channels
    assert "page" not in channels
    assert "rng" not in channels

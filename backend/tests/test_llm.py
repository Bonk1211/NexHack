"""LLM node tests (§15) — offline determinism + structured pass-through.

Cognition is concentrated in two calls; both MUST degrade to a deterministic,
network-free path when no API key is set (§16/§22), and a mid-call failure must
fall back cleanly rather than break a run. These tests never hit the network:
the only online path is exercised through a monkeypatched fake client.
"""
from __future__ import annotations

from app.agents import llm
from app.agents.llm import SynthesisResult, VisionJudgment, synthesize, vision_judge


def _sample_pack() -> dict:
    return {
        "app": "DemoBank",
        "inclusion_score": 0.4,
        "wcag_conformance": {"4.1.2": "fail", "1.4.3": "fail"},
        "personas": [
            {"persona": "oku_visual", "verdict": "blocked", "severity": "P0", "blocked_at": "otp"},
            {"persona": "control", "verdict": "completed", "severity": "P1", "blocked_at": None},
        ],
        "remediation": [],
    }


# --- offline (no key) heuristic / template ----------------------------------

def test_vision_offline_blocks_unlabeled_fill(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    j = vision_judge(None, "otp", "- textbox", requires_labels=True, labeled=False, action="fill")
    assert j.confusion == 1.0


def test_vision_offline_clear_when_labeled(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    j = vision_judge(None, "otp", '- textbox "OTP"', requires_labels=True, labeled=True, action="fill")
    assert j.confusion == 0.0


def test_vision_offline_clear_when_not_label_dependent(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    j = vision_judge(None, "submit", "- button", requires_labels=False, labeled=False, action="click")
    assert j.confusion == 0.0


def test_synthesize_offline_template_names_blocked(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "")
    s = synthesize(_sample_pack())
    assert isinstance(s, SynthesisResult)
    assert "oku_visual" in s.rollup
    assert s.rollup and s.narrative


# --- online path via a fake client ------------------------------------------

class _FakeAIMessage:
    """Mirrors a LangChain AIMessage: `.content` is the model's JSON text."""

    def __init__(self, content):
        self.content = content
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5}


class _FakeClient:
    """Matches the current llm.py path: `.invoke(messages, config=...)` returns a
    message whose `.content` is the JSON the model produced (parsed by the caller)."""

    def __init__(self, result=None, raises=False):
        self._result = result
        self._raises = raises

    def invoke(self, _messages, config=None):
        if self._raises:
            raise RuntimeError("deepseek down")
        content = self._result.model_dump_json() if self._result is not None else "{}"
        return _FakeAIMessage(content)


def test_vision_structured_value_flows_through(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "present")
    fake = _FakeClient(VisionJudgment(confusion=0.7, reason="ambiguous", fallback_target="OTP"))
    monkeypatch.setattr(llm, "_client", lambda _m: fake)
    # Judged from the a11y tree (text-only endpoint); no screenshot needed.
    j = vision_judge(None, "otp", "- textbox", requires_labels=False, labeled=True, action="fill")
    assert j.confusion == 0.7
    assert j.fallback_target == "OTP"


def test_vision_falls_back_on_client_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "present")
    monkeypatch.setattr(llm, "_client", lambda _m: _FakeClient(raises=True))
    # Label-dependent unlabeled fill => heuristic 1.0 even though the client raised.
    j = vision_judge(None, "otp", "- textbox", requires_labels=True, labeled=False, action="fill")
    assert j.confusion == 1.0


def test_synthesize_falls_back_on_client_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_api_key", "present")
    monkeypatch.setattr(llm, "_client", lambda _m: _FakeClient(raises=True))
    s = synthesize(_sample_pack())
    assert "oku_visual" in s.rollup  # templated fallback, no raise

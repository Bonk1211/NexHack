"""Persistence tests (§17). Verifies the screen_events column mapping carries the
trusted per-step stream (wcag_conformance/axe_violations), the indicative stream
(llm_judgment), and the screenshot ref — with a mocked Supabase client (no network).
Also asserts the no-creds path is a clean no-op."""
from __future__ import annotations

from app import db, repository, storage
from app.evidence.pack import PersonaRunResult, build_pack
from app.scoring.engine import PersonaThresholds, StepSignals, WcagSignal, score

T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)


class _FakeTable:
    def __init__(self, name, sink):
        self.name, self.sink = name, sink

    def insert(self, row):
        self.sink.setdefault(self.name, []).append(row)
        return self

    def execute(self):
        return None


class _FakeClient:
    def __init__(self, sink):
        self.sink = sink

    def table(self, name):
        return _FakeTable(name, self.sink)


def _pack_with_steps():
    steps = [
        StepSignals(0, "home", dwell_s=3),
        StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", False),),
                    dwell_s=12.0, dead_end=True, completed=False, llm_confusion=1.0),
    ]
    runs = [PersonaRunResult("oku_visual", tuple(steps), T, score(steps, T))]
    pack = build_pack("DemoBank", "2026-06-19T00:00:00Z", runs)
    pack["screenshots"] = {"oku_visual": ["/tmp/home.png", "/tmp/otp.png"]}
    return pack


def test_persist_writes_trusted_and_indicative_per_step(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))

    repository.persist_run(_pack_with_steps())

    assert {"runs", "run_personas", "screen_events", "evidence_packs"} <= set(sink)
    events = sink["screen_events"]
    assert len(events) == 2
    otp = next(e for e in events if e["step_idx"] == 1)
    assert otp["wcag_conformance"] == {"4.1.2": "fail"}      # TRUSTED
    assert otp["axe_violations"] == ["4.1.2"]
    assert otp["llm_judgment"] == {"confusion": 1.0}         # INDICATIVE
    assert otp["backtracked"] is False
    assert otp["dwell_ms"] == 12000
    assert otp["screenshot_url"] == "/tmp/otp.png"


def test_persist_uploads_artifacts_and_persists_urls(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))

    # Storage uploads succeed → URLs replace local paths; pack URLs are persisted.
    monkeypatch.setattr(
        storage, "upload_file", lambda c, local, dest: f"https://cdn/{dest}"
    )
    monkeypatch.setattr(
        storage, "upload_pack", lambda c, pack, rid: (f"https://cdn/{rid}/p.pdf", f"https://cdn/{rid}/p.json")
    )

    run_id = repository.persist_run(_pack_with_steps())

    otp = next(e for e in sink["screen_events"] if e["step_idx"] == 1)
    assert otp["screenshot_url"] == f"https://cdn/{run_id}/oku_visual/step_1.png"
    ep = sink["evidence_packs"][0]
    assert ep["pdf_url"] == f"https://cdn/{run_id}/p.pdf"
    assert ep["json_url"] == f"https://cdn/{run_id}/p.json"


def test_persist_falls_back_to_local_path_when_upload_fails(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))
    monkeypatch.setattr(storage, "upload_file", lambda c, local, dest: None)
    monkeypatch.setattr(storage, "upload_pack", lambda c, pack, rid: (None, None))

    repository.persist_run(_pack_with_steps())

    otp = next(e for e in sink["screen_events"] if e["step_idx"] == 1)
    assert otp["screenshot_url"] == "/tmp/otp.png"   # local ref preserved
    ep = sink["evidence_packs"][0]
    assert ep["pdf_url"] is None and ep["json_url"] is None


def test_persist_is_noop_without_creds(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "")
    monkeypatch.setattr(repository.settings, "supabase_key", "")

    def _boom():
        raise AssertionError("get_client must not be called without creds")

    monkeypatch.setattr(db, "get_client", _boom)
    run_id = repository.persist_run(_pack_with_steps())
    assert isinstance(run_id, str) and len(run_id) > 0

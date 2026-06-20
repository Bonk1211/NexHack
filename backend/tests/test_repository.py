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


# ── usage persistence (dashboard §3.2) ────────────────────────────────────────

_USAGE = {
    "currency": "USD",
    "total_prompt_tokens": 1200,
    "total_completion_tokens": 800,
    "total_tokens": 2000,
    "total_cost": 0.42,
    "pricing_applied": True,
    "models": [
        {"model": "deepseek-v4-flash", "prompt_tokens": 1000, "completion_tokens": 500,
         "total_tokens": 1500, "cost": 0.21, "pricing_applied": True},
        {"model": "deepseek-v4-pro", "prompt_tokens": 200, "completion_tokens": 300,
         "total_tokens": 500, "cost": 0.21, "pricing_applied": True},
    ],
}


def test_persist_writes_usage_rollup_and_per_model(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))

    run_id = repository.persist_run(_pack_with_steps(), _USAGE)

    run_row = sink["runs"][0]
    assert run_row["total_tokens"] == 2000
    assert run_row["prompt_tokens"] == 1200
    assert run_row["completion_tokens"] == 800
    assert run_row["llm_cost"] == 0.42
    assert run_row["pricing_applied"] is True

    models = sink["run_model_usage"]
    assert len(models) == 2
    assert {m["model"] for m in models} == {"deepseek-v4-flash", "deepseek-v4-pro"}
    assert all(m["run_id"] == run_id for m in models)


def test_persist_without_usage_omits_model_rows(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))

    repository.persist_run(_pack_with_steps())  # no usage arg

    assert "run_model_usage" not in sink
    assert "total_tokens" not in sink["runs"][0]


# ── pure dashboard aggregation (dashboard §5) ─────────────────────────────────

def _dashboard_rows():
    runs_rows = [
        {"id": "r1", "created_at": "2026-06-01T00:00:00Z", "inclusion_score": 0.55,
         "total_tokens": 1000, "llm_cost": 0.10, "llm_currency": "USD", "pricing_applied": True},
        {"id": "r2", "created_at": "2026-06-03T00:00:00Z", "inclusion_score": 0.62,
         "total_tokens": 1500, "llm_cost": 0.20, "llm_currency": "USD", "pricing_applied": True},
    ]
    personas_rows = [
        {"run_id": "r1", "persona_id": "mei", "persona_name": "Mei", "verdict": "blocked",
         "severity": "P0", "blocked_at": "otp"},
        {"run_id": "r1", "persona_id": "david", "persona_name": "David", "verdict": "completed",
         "severity": "P3", "blocked_at": None},
        {"run_id": "r2", "persona_id": "mei", "persona_name": "Mei", "verdict": "blocked",
         "severity": "P1", "blocked_at": "upload"},
        {"run_id": "r2", "persona_id": "david", "persona_name": "David", "verdict": "completed",
         "severity": "P3", "blocked_at": None},
    ]
    model_rows = [
        {"model": "deepseek-v4-flash", "prompt_tokens": 600, "completion_tokens": 300,
         "total_tokens": 900, "cost": 0.05, "pricing_applied": True},
        {"model": "deepseek-v4-flash", "prompt_tokens": 700, "completion_tokens": 400,
         "total_tokens": 1100, "cost": 0.06, "pricing_applied": True},
        {"model": "deepseek-v4-pro", "prompt_tokens": 200, "completion_tokens": 300,
         "total_tokens": 500, "cost": 0.19, "pricing_applied": True},
    ]
    return runs_rows, personas_rows, model_rows


def test_aggregate_dashboard_shape_and_math():
    runs_rows, personas_rows, model_rows = _dashboard_rows()
    d = repository.aggregate_dashboard(
        "proj", runs_rows, personas_rows, model_rows,
        wcag_by_run={"r1": 0.5, "r2": 0.75},
    )

    assert d["runsCount"] == 2
    assert d["latestScore"] == 0.62           # newest run by created_at
    assert d["totalTokens"] == 2500
    assert round(d["totalCost"], 2) == 0.30
    assert d["pricingApplied"] is True

    # trend is oldest → newest, carries per-run blocked + trusted wcag rate
    assert [t["runId"] for t in d["trend"]] == ["r1", "r2"]
    assert d["trend"][0]["blockedCount"] == 1
    assert d["trend"][1]["wcagPassRate"] == 0.75

    # Mei blocked in both runs → blockRate 1.0, sorts first
    mei = d["personaReliability"][0]
    assert mei["name"] == "Mei" and mei["blockRate"] == 1.0
    assert mei["lastStatus"] == "blocked"
    david = next(p for p in d["personaReliability"] if p["name"] == "David")
    assert david["blockRate"] == 0.0 and david["lastStatus"] == "ok"

    # usage summed by model, flash pooled across runs
    flash = next(m for m in d["usageByModel"] if m["model"] == "deepseek-v4-flash")
    assert flash["totalTokens"] == 2000 and flash["promptTokens"] == 1300

    # action queue: only open P0/P1 blocks, P0 before P1
    assert [a["severity"] for a in d["actions"]] == ["P0", "P1"]
    assert d["actions"][0]["personaName"] == "Mei" and d["actions"][0]["blockedAt"] == "otp"


def test_aggregate_dashboard_empty():
    d = repository.aggregate_dashboard("proj", [], [], [])
    assert d["runsCount"] == 0 and d["latestScore"] is None
    assert d["trend"] == [] and d["actions"] == []


def test_wcag_pass_rate_by_run_pools_criteria():
    rp_rows = [{"id": "rp1", "run_id": "r1"}, {"id": "rp2", "run_id": "r1"}]
    event_rows = [
        {"run_personas_id": "rp1", "wcag_conformance": {"1.4.3": "pass", "4.1.2": "fail"}},
        {"run_personas_id": "rp2", "wcag_conformance": {"1.4.3": "pass"}},
    ]
    rates = repository.wcag_pass_rate_by_run(["r1"], rp_rows, event_rows)
    assert rates["r1"] == 2 / 3

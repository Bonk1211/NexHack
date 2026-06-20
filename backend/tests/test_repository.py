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

    def upsert(self, row):
        self.sink.setdefault(self.name, []).append(row)
        return self

    def execute(self):
        return None


class _FakeClient:
    def __init__(self, sink):
        self.sink = sink

    def table(self, name):
        return _FakeTable(name, self.sink)


class _QueryResult:
    def __init__(self, data):
        self.data = data


class _ReadTable:
    """Minimal PostgREST-style query chain over pre-seeded rows (read path)."""

    def __init__(self, rows):
        self._rows = list(rows)

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def in_(self, col, vals):
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def order(self, col, desc=False):
        self._rows = sorted(self._rows, key=lambda r: r.get(col), reverse=desc)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        return _QueryResult(list(self._rows))


class _ReadClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _ReadTable(self.tables.get(name, []))


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


def test_persist_records_run_history_with_app_fk_and_mode(monkeypatch):
    """Every run must land in `runs` — with the app_id FK satisfied (via an apps
    upsert), the caller's run_id, and the actual mode — or history is incomplete."""
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    sink: dict[str, list] = {}
    monkeypatch.setattr(db, "get_client", lambda: _FakeClient(sink))

    rid = repository.persist_run(
        _pack_with_steps(), run_id="run-123", mode="parallel", target_url="https://staging.demo"
    )
    assert rid == "run-123"

    # apps upserted so the runs.app_id FK resolves; same id reused on re-run.
    app = sink["apps"][0]
    assert app["name"] == "DemoBank" and app["staging_url"] == "https://staging.demo"

    run = sink["runs"][0]
    assert run["id"] == "run-123"
    assert run["app_id"] == app["id"]          # FK satisfied → row actually inserts
    assert run["mode"] == "parallel"           # real mode, not hardcoded
    assert run["status"] == "done"
    assert run["inclusion_score"] is not None


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


def test_list_runs_returns_app_runs_newest_first_with_blocked_counts(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    app_id = repository._app_id_for("DemoBank")
    tables = {
        "runs": [
            {"id": "r1", "app_id": app_id, "mode": "parallel", "status": "done",
             "inclusion_score": 0.8, "created_at": "2026-06-20T10:00:00Z"},
            {"id": "r2", "app_id": app_id, "mode": "sequential", "status": "done",
             "inclusion_score": 0.6, "created_at": "2026-06-20T09:00:00Z"},
            {"id": "rX", "app_id": "other-app", "mode": "sequential", "status": "done",
             "inclusion_score": 0.5, "created_at": "2026-06-20T11:00:00Z"},
        ],
        "run_personas": [
            {"run_id": "r1", "verdict": "completed"},
            {"run_id": "r2", "verdict": "blocked"},
            {"run_id": "r2", "verdict": "blocked"},
        ],
    }
    monkeypatch.setattr(db, "get_client", lambda: _ReadClient(tables))

    out = repository.list_runs("DemoBank")

    assert [r["id"] for r in out] == ["r1", "r2"]    # other app excluded; newest first
    assert out[0]["mode"] == "parallel"
    assert out[0]["blocked_count"] == 0
    assert out[1]["blocked_count"] == 2


def test_list_runs_empty_without_creds(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "")
    monkeypatch.setattr(repository.settings, "supabase_key", "")
    assert repository.list_runs("DemoBank") == []


def test_get_run_returns_persisted_pack(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(repository.settings, "supabase_key", "key")
    pack = {"app": "DemoBank", "inclusion_score": 0.42, "personas": []}
    tables = {"evidence_packs": [{"run_id": "run-1", "pack": pack}, {"run_id": "run-2", "pack": {}}]}
    monkeypatch.setattr(db, "get_client", lambda: _ReadClient(tables))

    assert repository.get_run("run-1") == pack
    assert repository.get_run("missing") is None


def test_get_run_none_without_creds(monkeypatch):
    monkeypatch.setattr(repository.settings, "supabase_url", "")
    monkeypatch.setattr(repository.settings, "supabase_key", "")
    assert repository.get_run("run-1") is None

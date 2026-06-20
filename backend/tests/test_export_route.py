"""Export endpoint tests (FR-4.1, §13).

GET /runs/{run_id}/export serves the evidence pack as a downloadable compliance
artifact in JSON (canonical) or PDF (audit). Drives the real FastAPI app via
TestClient with a pack injected into the in-memory store — no Playwright run needed.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.routes import runs

client = TestClient(app)

_PACK = {
    "app": "Demo Bank",
    "run_at": "2026-06-19T00:00:00Z",
    "inclusion_score": 0.42,
    "wcag_conformance": {"4.1.2": "fail", "1.4.3": "pass"},
    "matrix": {"steps": ["otp"], "rows": {}},
    "personas": [
        {"persona": "oku_visual", "verdict": "blocked", "severity": "P0", "blocked_at": "otp"},
    ],
    "remediation": [
        {"criterion": "4.1.2", "issue": "Control missing accessible name",
         "owner": "@content", "severity": "P0"},
    ],
}


def _seed(run_id="run-export-1"):
    runs._STORE[run_id] = {"pack": _PACK, "usage": None}
    return run_id


def test_export_json_is_downloadable_and_round_trips():
    rid = _seed()
    r = client.get(f"/runs/{rid}/export", params={"format": "json"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["content-disposition"].endswith('.json"')
    assert json.loads(r.content) == _PACK


def test_export_pdf_renders_valid_pdf():
    rid = _seed("run-export-2")
    r = client.get(f"/runs/{rid}/export", params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"
    assert len(r.content) > 0


def test_export_defaults_to_json():
    rid = _seed("run-export-3")
    r = client.get(f"/runs/{rid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_export_unknown_run_is_404():
    r = client.get("/runs/does-not-exist/export", params={"format": "json"})
    assert r.status_code == 404


def test_export_bad_format_is_400():
    rid = _seed("run-export-4")
    r = client.get(f"/runs/{rid}/export", params={"format": "csv"})
    assert r.status_code == 400


def test_export_filename_slugifies_app_name():
    rid = _seed("run-export-5")
    r = client.get(f"/runs/{rid}/export", params={"format": "json"})
    # "Demo Bank" -> no spaces in the download filename
    cd = r.headers["content-disposition"]
    assert "Demo_Bank" in cd
    assert " Bank" not in cd

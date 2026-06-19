"""Export tests (§13). JSON round-trips equal; PDF renders headless to a
non-empty %PDF file."""
from __future__ import annotations

import json
import os

from app.evidence.export import pack_to_json, pack_to_pdf

_PACK = {
    "app": "DemoBank",
    "run_at": "2026-06-19T00:00:00Z",
    "inclusion_score": 0.42,
    "wcag_conformance": {"4.1.2": "fail", "1.4.3": "pass"},
    "matrix": {"steps": ["home", "otp"], "rows": {}},
    "personas": [
        {
            "persona": "oku_visual",
            "verdict": "blocked",
            "severity": "P0",
            "blocked_at": "otp",
            "wcag_failures": ["4.1.2"],
            "behavioral_note": "indicative — persona-simulation signal",
            "inclusion_score": 0.2,
        },
        {
            "persona": "control",
            "verdict": "completed",
            "severity": None,
            "blocked_at": None,
            "wcag_failures": [],
            "behavioral_note": "indicative — persona-simulation signal",
            "inclusion_score": 1.0,
        },
    ],
    "remediation": [
        {"criterion": "4.1.2", "issue": "Control missing accessible name", "owner": "@content", "severity": "P0"},
    ],
}


def test_pack_to_json_round_trips(tmp_path):
    path = str(tmp_path / "pack.json")
    returned = pack_to_json(_PACK, path)
    assert returned == path
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == _PACK


def test_pack_to_pdf_writes_valid_pdf(tmp_path):
    path = str(tmp_path / "pack.pdf")
    returned = pack_to_pdf(_PACK, path)
    assert returned == path
    assert os.path.getsize(path) > 0
    with open(path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_pack_to_pdf_handles_empty_pack(tmp_path):
    empty = {
        "app": "X",
        "run_at": "2026-06-19T00:00:00Z",
        "inclusion_score": 1.0,
        "wcag_conformance": {},
        "matrix": {"steps": [], "rows": {}},
        "personas": [],
        "remediation": [],
    }
    path = str(tmp_path / "empty.pdf")
    pack_to_pdf(empty, path)
    assert os.path.getsize(path) > 0
    with open(path, "rb") as f:
        assert f.read(4) == b"%PDF"

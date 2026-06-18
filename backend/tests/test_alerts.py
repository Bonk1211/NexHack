"""Alert tests (FR-4.3). Asserts P0-only triggering, owner routing derived from
the pack's remediation, the human message, and that send_alerts makes no network
call when no webhook is configured."""
from __future__ import annotations

from app import alerts


def _pack(personas, remediation, app="DemoBank"):
    return {
        "app": app,
        "run_at": "2026-06-19T00:00:00Z",
        "inclusion_score": 0.5,
        "wcag_conformance": {"4.1.2": "fail"},
        "matrix": {"steps": [], "rows": {}},
        "personas": personas,
        "remediation": remediation,
    }


def _p0_pack():
    return _pack(
        personas=[
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
        remediation=[{"criterion": "4.1.2", "issue": "x", "owner": "@content", "severity": "P0"}],
    )


def test_build_p0_alerts_routes_and_summarizes():
    out = alerts.build_p0_alerts(_p0_pack())
    assert len(out) == 1
    a = out[0]
    assert a["persona"] == "oku_visual"
    assert a["blocked_at"] == "otp"
    assert a["severity"] == "P0"
    assert a["owner"] == "@content"          # routed from remediation entry
    assert a["wcag_failures"] == ["4.1.2"]
    assert "P0" in a["message"]
    assert "oku_visual" in a["message"]
    assert "@content" in a["message"]


def test_build_p0_alerts_owner_fallback():
    # Persona failure with no matching remediation entry -> @frontend fallback.
    pack = _pack(
        personas=[
            {
                "persona": "oku_motor",
                "verdict": "blocked",
                "severity": "P0",
                "blocked_at": "pay",
                "wcag_failures": ["9.9.9"],
                "behavioral_note": "indicative",
                "inclusion_score": 0.1,
            }
        ],
        remediation=[],
    )
    out = alerts.build_p0_alerts(pack)
    assert out[0]["owner"] == "@frontend"


def test_no_p0_personas_returns_empty():
    pack = _pack(
        personas=[
            {
                "persona": "control",
                "verdict": "completed",
                "severity": None,
                "blocked_at": None,
                "wcag_failures": [],
                "behavioral_note": "indicative",
                "inclusion_score": 1.0,
            }
        ],
        remediation=[],
    )
    assert alerts.build_p0_alerts(pack) == []


def test_send_alerts_in_dashboard_when_no_webhook(monkeypatch):
    monkeypatch.setattr(alerts.settings, "slack_webhook_url", "")

    # Guard: any network call would explode this test.
    def _boom(*args, **kwargs):
        raise AssertionError("send_alerts made a network call with no webhook configured")

    monkeypatch.setattr(alerts.httpx, "post", _boom)

    out = alerts.send_alerts(_p0_pack())
    assert len(out) == 1
    assert out[0]["delivered"] == "in-dashboard"

"""Live "persona blocked" alerts + owner routing (FR-4.3).

When a persona is *blocked* (severity P0 per §12 — a dead end at a critical step),
a compliance team needs to know now, and the alert must say *who owns the fix*
(frontend / content / i18n / backend). This module turns the §13 evidence pack
into routed alert payloads and optionally pushes them to Slack.

Two-stream discipline (§16): the alert carries the persona's *trusted* WCAG
failures (the citable evidence) alongside the *indicative* blocked verdict that
triggered it — labeled as such in the message.

`build_p0_alerts` is PURE (no I/O) so it is unit-testable. `send_alerts` is the
only function that touches the network, and only when a webhook is configured —
importing this module never does network I/O.
"""
from __future__ import annotations

import httpx

from app.config import settings

# Fallback owner when a persona's failures don't match any remediation entry.
_DEFAULT_OWNER = "@frontend"


def _route_owner(wcag_failures: list[str], remediation: list[dict]) -> str:
    """Pick the owning area for a blocked persona by matching its WCAG failures
    against the pack's remediation entries (which already carry routed owners,
    see app.evidence.pack). First shared criterion wins; fallback @frontend."""
    by_criterion = {r["criterion"]: r.get("owner", _DEFAULT_OWNER) for r in remediation}
    for crit in wcag_failures:
        owner = by_criterion.get(crit)
        if owner:
            return owner
    return _DEFAULT_OWNER


def build_p0_alerts(pack: dict) -> list[dict]:
    """Build one routed alert payload per blocked (P0) persona in the pack.

    P0 is the trigger per FR-4.3 ("blocked"). Pure: no I/O, no network.
    """
    app = pack.get("app", "")
    remediation = pack.get("remediation", [])
    alerts: list[dict] = []

    for p in pack.get("personas", []):
        if p.get("severity") != "P0":
            continue

        persona = p.get("persona", "")
        blocked_at = p.get("blocked_at")
        wcag_failures = p.get("wcag_failures", [])
        owner = _route_owner(wcag_failures, remediation)

        # Human one-liner. Cite the trusted WCAG failures so the alert stands as
        # evidence, not just a "something broke" ping.
        crit_text = f" (WCAG {', '.join(wcag_failures)})" if wcag_failures else ""
        at_text = blocked_at or "an unknown step"
        message = (
            f"P0: {persona} blocked at {at_text} on {app} "
            f"— owner {owner}{crit_text}"
        )

        alerts.append(
            {
                "persona": persona,
                "app": app,
                "blocked_at": blocked_at,
                "severity": "P0",
                "wcag_failures": wcag_failures,
                "owner": owner,
                "message": message,
            }
        )

    return alerts


def send_alerts(pack: dict) -> list[dict]:
    """Build P0 alerts and deliver them.

    If a Slack webhook is configured, POST each alert's message there and mark it
    delivered:"slack"; otherwise mark delivered:"in-dashboard" and make no network
    call (FR-4.3 allows Slack *or* in-dashboard). HTTP errors are caught and the
    alert is marked delivered:"error" with the exception string — a failed push
    never crashes the run.
    """
    alerts = build_p0_alerts(pack)
    webhook = settings.slack_webhook_url

    if not webhook:
        for a in alerts:
            a["delivered"] = "in-dashboard"
        return alerts

    for a in alerts:
        try:
            resp = httpx.post(webhook, json={"text": a["message"]}, timeout=10.0)
            resp.raise_for_status()
            a["delivered"] = "slack"
        except Exception as exc:  # network/HTTP failure must not abort the run
            a["delivered"] = "error"
            a["error"] = str(exc)

    return alerts

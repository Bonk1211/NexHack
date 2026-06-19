"""Optional Supabase persistence (§15, §17).

Best-effort: if Supabase creds are configured (app.config.settings) this writes
the run across runs / run_personas / screen_events / evidence_packs. If not, it
is a no-op that returns a generated uuid so the end-to-end path never depends on
a database. All Supabase imports are deferred inside functions, so importing this
module never requires network.
"""
from __future__ import annotations

import uuid

from app.config import settings


def _has_creds() -> bool:
    return bool(settings.supabase_url and settings.supabase_key)


def persist_run(pack: dict) -> str:
    """Persist an evidence pack and return its run_id.

    No-op (returns a fresh uuid) when Supabase is unconfigured. The route layer
    calls this best-effort and swallows DB errors, so a persistence failure never
    blocks returning the pack to the caller.
    """
    run_id = str(uuid.uuid4())
    if not _has_creds():
        return run_id

    from app.db import get_client  # deferred — importing this module stays network-free

    client = get_client()

    # runs (§17): one row per assessment, carrying the derived inclusion score.
    client.table("runs").insert(
        {
            "id": run_id,
            "mode": "sequential",
            "status": "complete",
            "inclusion_score": pack.get("inclusion_score"),
        }
    ).execute()

    # run_personas (§17): one row per persona verdict (indicative stream).
    screenshots = pack.get("screenshots", {})
    for p in pack.get("personas", []):
        rp_id = str(uuid.uuid4())
        client.table("run_personas").insert(
            {
                "id": rp_id,
                "run_id": run_id,
                "persona_name": p.get("persona"),
                "verdict": p.get("verdict"),
                "severity": p.get("severity"),
                "completed": p.get("verdict") == "completed",
                "status": p.get("verdict"),
            }
        ).execute()

        # screen_events (§17): one row per step, carrying BOTH streams kept distinct —
        # wcag_conformance/axe_violations (TRUSTED) and llm_judgment (INDICATIVE) — plus
        # the screenshot ref (a local path until Storage upload; see pack.py TODO).
        shots = screenshots.get(p.get("persona"), [])
        for sd in p.get("steps", []):
            idx = sd.get("step_idx", 0)
            client.table("screen_events").insert(
                {
                    "id": str(uuid.uuid4()),
                    "run_personas_id": rp_id,
                    "step_idx": idx,
                    "action": sd.get("step_key"),
                    "dwell_ms": int((sd.get("dwell_s") or 0) * 1000),
                    "backtracked": bool(sd.get("backtracked")),
                    "axe_violations": sd.get("axe_violations", []),
                    "wcag_conformance": sd.get("wcag_conformance", {}),   # TRUSTED
                    "llm_judgment": sd.get("llm_judgment", {}),           # INDICATIVE
                    "severity": p.get("severity"),
                    "screenshot_url": shots[idx] if idx < len(shots) else None,
                }
            ).execute()

    # evidence_packs (§17): the primary output artifact.
    client.table("evidence_packs").insert(
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "summary": {"app": pack.get("app"), "inclusion_score": pack.get("inclusion_score")},
            "matrix": pack.get("matrix"),
            "remediation": pack.get("remediation"),
        }
    ).execute()

    return run_id

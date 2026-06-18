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
    matrix_rows = pack.get("matrix", {}).get("rows", {})
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

        # screen_events (§17): one row per step cell of the friction matrix.
        cells = matrix_rows.get(p.get("persona"), {})
        for step_idx, (step_key, cell) in enumerate(cells.items()):
            client.table("screen_events").insert(
                {
                    "id": str(uuid.uuid4()),
                    "run_personas_id": rp_id,
                    "step_idx": step_idx,
                    "action": step_key,
                    "dwell_ms": int((cell.get("dwell_s") or 0) * 1000),
                    "severity": p.get("severity"),
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

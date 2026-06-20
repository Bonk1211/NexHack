"""Optional Supabase persistence (§15, §17).

Best-effort: if Supabase creds are configured (app.config.settings) this writes
the run across runs / run_personas / screen_events / evidence_packs. If not, it
is a no-op that returns a generated uuid so the end-to-end path never depends on
a database. All Supabase imports are deferred inside functions, so importing this
module never requires network.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.config import settings


def _has_creds() -> bool:
    return bool(settings.supabase_url and settings.supabase_key)


def _app_id_for(name: str) -> str:
    """Stable app id derived from the app name, so re-runs map to one apps row."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"inclusionscope:app:{name}"))


def list_runs(app_name: str, limit: int = 50) -> list[dict]:
    """Run history for one app, newest first, for the run-history tab.

    Returns [] when Supabase is unconfigured (dev path stays DB-free). Each item:
    id, mode, status, inclusion_score, created_at, blocked_count.
    """
    if not _has_creds():
        return []

    from app.db import get_client  # deferred — keeps this module import network-free

    client = get_client()
    app_id = _app_id_for(app_name)
    res = (
        client.table("runs")
        .select("id, mode, status, inclusion_score, created_at")
        .eq("app_id", app_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return []

    # One follow-up query for blocked verdicts across these runs (§17 indicative stream).
    run_ids = [r["id"] for r in rows]
    rp = client.table("run_personas").select("run_id, verdict").in_("run_id", run_ids).execute()
    blocked: dict[str, int] = {}
    for row in rp.data or []:
        if row.get("verdict") == "blocked":
            blocked[row["run_id"]] = blocked.get(row["run_id"], 0) + 1

    return [
        {
            "id": r["id"],
            "mode": r.get("mode"),
            "status": r.get("status"),
            "inclusion_score": r.get("inclusion_score"),
            "created_at": r.get("created_at"),
            "blocked_count": blocked.get(r["id"], 0),
        }
        for r in rows
    ]


def get_run(run_id: str) -> dict | None:
    """The full persisted evidence pack for one run, or None.

    Returns None when Supabase is unconfigured or the run isn't found, so the
    route can fall back / 404 cleanly.
    """
    if not _has_creds():
        return None

    from app.db import get_client  # deferred — keeps this module import network-free

    client = get_client()
    res = (
        client.table("evidence_packs")
        .select("pack")
        .eq("run_id", run_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    return rows[0].get("pack")


def persist_run(
    pack: dict,
    *,
    run_id: str | None = None,
    mode: str = "sequential",
    target_url: str | None = None,
    usage: dict | None = None,
) -> str:
    """Persist an evidence pack into run history and return its run_id.

    Pass the caller's `run_id` so the stored row shares the id the API/stream
    already handed the client (otherwise history can't be linked back). No-op
    (returns the given/fresh uuid) when Supabase is unconfigured. The route layer
    calls this best-effort, so a persistence failure never blocks the response.

    `usage` is the LLMUsageTracker.serialized() payload (dashboard §3.2). When given,
    the per-run token/cost rollup is written onto the runs row and one run_model_usage
    row per model — making usage durable for the per-project dashboard (§5). Cost is
    operational metadata (§16): it never feeds the inclusion score.
    """
    run_id = run_id or str(uuid.uuid4())
    if not _has_creds():
        return run_id

    from app import storage  # deferred — keeps this module import network-free
    from app.db import get_client  # deferred — importing this module stays network-free

    client = get_client()

    # apps (§17): the runs table requires app_id (FK → apps). Upsert a stable app
    # row by name first so every run satisfies the constraint and is recorded.
    app_name = pack.get("app") or "app"
    app_id = _app_id_for(app_name)
    client.table("apps").upsert(
        {"id": app_id, "name": app_name, "staging_url": target_url or ""}
    ).execute()

    # runs (§17): one row per assessment, carrying the derived inclusion score and
    # (when available) the LLM usage rollup (dashboard §3.1).
    run_row = {
        "id": run_id,
        "app_id": app_id,
        "mode": mode,
        "status": "done",
        "inclusion_score": pack.get("inclusion_score"),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if usage:
        run_row.update(
            {
                "prompt_tokens": usage.get("total_prompt_tokens", 0),
                "completion_tokens": usage.get("total_completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "llm_cost": usage.get("total_cost", 0),
                "llm_currency": usage.get("currency", "USD"),
                "pricing_applied": usage.get("pricing_applied", False),
            }
        )
    client.table("runs").insert(run_row).execute()

    # run_model_usage (§3.1): one row per model touched in this run.
    if usage:
        for m in usage.get("models", []):
            client.table("run_model_usage").insert(
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "model": m.get("model"),
                    "prompt_tokens": m.get("prompt_tokens", 0),
                    "completion_tokens": m.get("completion_tokens", 0),
                    "total_tokens": m.get("total_tokens", 0),
                    "cost": m.get("cost", 0),
                    "pricing_applied": m.get("pricing_applied", False),
                }
            ).execute()

    # §14/§17 Storage pre-pass: upload every per-step screenshot ONCE, then rewrite the
    # pack's refs — both the `screenshots` map and the empathy-replay frames — from local
    # paths to public URLs. Done BEFORE rendering the pack artifacts so the uploaded
    # JSON/PDF carry real URLs; mutating the shared pack dict also upgrades what the API
    # returns. Best-effort: a failed upload keeps the local ref.
    screenshots = pack.get("screenshots", {})
    replay = pack.get("replay", {})
    for persona, shots in screenshots.items():
        new_shots: list[str | None] = []
        for s_idx, local in enumerate(shots):
            if not local:
                new_shots.append(None)
                continue
            dest = f"{run_id}/{persona}/step_{s_idx}.png"
            new_shots.append(storage.upload_file(client, local, dest) or local)
        screenshots[persona] = new_shots
        for frame in replay.get(persona, {}).get("frames", []):
            idx = frame.get("step_idx", 0)
            if idx < len(new_shots):
                frame["screenshot_url"] = new_shots[idx]

    # run_personas (§17): one row per persona verdict (indicative stream).
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
        # the screenshot ref (now a Storage URL where upload succeeded).
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

    # evidence_packs (§17): the primary output artifact. Render JSON + PDF once and
    # upload both to Storage; the public URLs are persisted for download. Best-effort:
    # pdf_url/json_url stay None when Storage is unavailable.
    pdf_url, json_url = storage.upload_pack(client, pack, run_id)
    client.table("evidence_packs").insert(
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "summary": {"app": pack.get("app"), "inclusion_score": pack.get("inclusion_score")},
            "matrix": pack.get("matrix"),
            "remediation": pack.get("remediation"),
            "pack": pack,           # full artifact, so the detail page can rehydrate the run
            "pdf_url": pdf_url,
            "json_url": json_url,
        }
    ).execute()

    return run_id


# ── Per-project dashboard aggregation (dashboard spec §5) ──────────────────────

_BLOCK_SEVERITIES = ("P0", "P1")


def _wcag_pass_rate(conformance: dict) -> tuple[int, int]:
    """(passes, total) over a screen_events.wcag_conformance map (TRUSTED §16)."""
    passes = sum(1 for v in conformance.values() if v == "pass")
    total = sum(1 for v in conformance.values() if v in ("pass", "fail"))
    return passes, total


def wcag_pass_rate_by_run(run_ids: list[str], rp_rows: list[dict], event_rows: list[dict]) -> dict[str, float]:
    """Roll trusted WCAG conformance up to a 0..1 pass rate per run.

    `rp_rows` maps run_personas.id → run_id; `event_rows` carry wcag_conformance.
    Criteria are pooled across every step of every persona in the run.
    """
    rp_to_run = {rp["id"]: rp.get("run_id") for rp in rp_rows}
    tally: dict[str, list[int]] = {rid: [0, 0] for rid in run_ids}
    for ev in event_rows:
        rid = rp_to_run.get(ev.get("run_personas_id"))
        if rid is None or rid not in tally:
            continue
        p, t = _wcag_pass_rate(ev.get("wcag_conformance") or {})
        tally[rid][0] += p
        tally[rid][1] += t
    return {rid: (p / t if t else 0.0) for rid, (p, t) in tally.items()}


def aggregate_dashboard(
    project_id: str,
    runs_rows: list[dict],
    personas_rows: list[dict],
    model_usage_rows: list[dict],
    wcag_by_run: dict[str, float] | None = None,
) -> dict:
    """Pure §5 ProjectDashboard builder over already-fetched table rows.

    Emits camelCase keys matching frontend/lib/types.ts so the dedicated endpoint
    drops straight into `getProjectDashboard`. Kept side-effect-free for testing —
    the route does the querying, this does the math.
    """
    wcag_by_run = wcag_by_run or {}
    runs_sorted = sorted(runs_rows, key=lambda r: r.get("created_at") or "")
    run_created = {r["id"]: r.get("created_at") for r in runs_sorted}

    # blocked count per run (INDICATIVE stream)
    blocked_per_run: dict[str, int] = {}
    for p in personas_rows:
        if p.get("verdict") == "blocked":
            blocked_per_run[p["run_id"]] = blocked_per_run.get(p["run_id"], 0) + 1

    trend = [
        {
            "runId": r["id"],
            "createdAt": r.get("created_at"),
            "overallScore": float(r.get("inclusion_score") or 0),
            "blockedCount": blocked_per_run.get(r["id"], 0),
            "wcagPassRate": round(wcag_by_run.get(r["id"], 0.0), 4),
            "totalTokens": int(r.get("total_tokens") or 0),
            "cost": float(r.get("llm_cost") or 0),
        }
        for r in runs_sorted
    ]

    latest = runs_sorted[-1] if runs_sorted else None
    total_tokens = sum(int(r.get("total_tokens") or 0) for r in runs_rows)
    total_cost = sum(float(r.get("llm_cost") or 0) for r in runs_rows)
    currency = next((r.get("llm_currency") for r in runs_rows if r.get("llm_currency")), "USD")
    pricing_applied = any(r.get("pricing_applied") for r in runs_rows)

    # persona reliability across runs (INDICATIVE), keyed by persona identity
    by_persona: dict[str, dict] = {}
    for p in personas_rows:
        key = p.get("persona_id") or p.get("persona_name") or "unknown"
        bucket = by_persona.setdefault(
            key,
            {"personaId": key, "name": p.get("persona_name") or key,
             "runsCount": 0, "blockedCount": 0, "_lastAt": "", "lastStatus": "ok"},
        )
        bucket["runsCount"] += 1
        if p.get("verdict") == "blocked":
            bucket["blockedCount"] += 1
        at = run_created.get(p.get("run_id"), "") or ""
        if at >= bucket["_lastAt"]:
            bucket["_lastAt"] = at
            bucket["lastStatus"] = "blocked" if p.get("verdict") == "blocked" else "ok"

    persona_reliability = sorted(
        (
            {
                "personaId": b["personaId"],
                "name": b["name"],
                "runsCount": b["runsCount"],
                "blockedCount": b["blockedCount"],
                "blockRate": round(b["blockedCount"] / b["runsCount"], 4) if b["runsCount"] else 0.0,
                "lastStatus": b["lastStatus"],
            }
            for b in by_persona.values()
        ),
        key=lambda x: x["blockRate"],
        reverse=True,
    )

    # usage summed by model across runs
    by_model: dict[str, dict] = {}
    for m in model_usage_rows:
        name = m.get("model") or "unknown"
        agg = by_model.setdefault(
            name,
            {"model": name, "promptTokens": 0, "completionTokens": 0,
             "totalTokens": 0, "cost": 0.0, "pricingApplied": False},
        )
        agg["promptTokens"] += int(m.get("prompt_tokens") or 0)
        agg["completionTokens"] += int(m.get("completion_tokens") or 0)
        agg["totalTokens"] += int(m.get("total_tokens") or 0)
        agg["cost"] += float(m.get("cost") or 0)
        agg["pricingApplied"] = agg["pricingApplied"] or bool(m.get("pricing_applied"))
    usage_by_model = sorted(by_model.values(), key=lambda x: x["totalTokens"], reverse=True)

    # action queue: open P0/P1 blocks, sorted by severity then recency (§13)
    _sev_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    actions = [
        {
            "runId": p.get("run_id"),
            "personaId": p.get("persona_id") or p.get("persona_name"),
            "personaName": p.get("persona_name"),
            "severity": p.get("severity"),
            "blockedAt": p.get("blocked_at"),
            "wcagCriterion": p.get("wcag_criterion"),
            "owner": p.get("owner"),
        }
        for p in personas_rows
        if p.get("verdict") == "blocked" and p.get("severity") in _BLOCK_SEVERITIES
    ]
    actions.sort(key=lambda a: (_sev_rank.get(a["severity"], 9),
                                _neg_str(run_created.get(a["runId"], ""))))

    return {
        "projectId": project_id,
        "runsCount": len(runs_rows),
        "latestScore": float(latest["inclusion_score"]) if latest and latest.get("inclusion_score") is not None else None,
        "totalTokens": total_tokens,
        "totalCost": total_cost,
        "currency": currency,
        "pricingApplied": pricing_applied,
        "trend": trend,
        "personaReliability": persona_reliability,
        "usageByModel": usage_by_model,
        "actions": actions,
    }


def _neg_str(s: str) -> tuple:
    """Sort key that orders strings DESCENDING (most recent createdAt first)."""
    return tuple(-ord(c) for c in (s or ""))


def fetch_project_dashboard(app_id: str) -> dict:
    """Fetch + aggregate the §5 dashboard for an app. Empty shell when unconfigured.

    Best-effort and read-only: callers swallow errors. Per-model usage and WCAG
    pass-rate roll-ups are cheaper in SQL than re-deriving client-side (§4).
    """
    empty = {
        "projectId": app_id, "runsCount": 0, "latestScore": None,
        "totalTokens": 0, "totalCost": 0.0, "currency": "USD", "pricingApplied": False,
        "trend": [], "personaReliability": [], "usageByModel": [], "actions": [],
    }
    if not _has_creds():
        return empty

    from app.db import get_client  # deferred — keeps module import network-free

    client = get_client()
    runs_rows = (client.table("runs").select("*").eq("app_id", app_id).execute().data) or []
    if not runs_rows:
        return empty
    run_ids = [r["id"] for r in runs_rows]

    rp_rows = (client.table("run_personas").select("*").in_("run_id", run_ids).execute().data) or []
    model_rows = (client.table("run_model_usage").select("*").in_("run_id", run_ids).execute().data) or []
    rp_ids = [rp["id"] for rp in rp_rows]
    event_rows = (
        (client.table("screen_events").select("run_personas_id,wcag_conformance")
         .in_("run_personas_id", rp_ids).execute().data) or []
        if rp_ids else []
    )

    wcag = wcag_pass_rate_by_run(run_ids, rp_rows, event_rows)
    return aggregate_dashboard(app_id, runs_rows, rp_rows, model_rows, wcag)


# ── Personas ──────────────────────────────────────────────────────────────────

def _row_to_persona(row: dict) -> dict:
    bp = row.get("behavior_profile") or {}
    status = row.get("figurine_status") or "none"
    return {
        "id": row["slug"],
        "identity": {
            "name": row["name"],
            "label": row.get("label") or "",
            "ageBand": row.get("age_band") or "",
            "language": row.get("language") or "",
            "techSavviness": float(row.get("tech_savviness") or 0),
            "disabilities": row.get("disabilities") or [],
        },
        "behavior": {
            "dwellMultiplier": float(bp.get("dwell_multiplier", 1.0)),
            "giveupThresholdS": float(bp.get("giveup_threshold_s", 60)),
            "misinterpretProb": float(row.get("misinterpret_prob") or 0),
        },
        "figurineStatus": status,
        "figurineUrl": row.get("figurine_url"),
    }


def list_personas() -> list[dict]:
    if not _has_creds():
        return []
    from app.db import get_client
    rows = get_client().table("personas").select("*").order("created_at").execute().data or []
    return [_row_to_persona(r) for r in rows]


def get_persona_by_slug(slug: str) -> dict | None:
    if not _has_creds():
        return None
    from app.db import get_client
    rows = get_client().table("personas").select("*").eq("slug", slug).limit(1).execute().data or []
    return _row_to_persona(rows[0]) if rows else None


def create_persona(identity: dict, behavior: dict) -> dict | None:
    if not _has_creds():
        return None
    import re
    from app.db import get_client
    slug = "p-" + re.sub(r"[^a-z0-9]+", "-", identity["name"].lower()).strip("-")[:20]
    row = {
        "slug": slug,
        "name": identity["name"],
        "label": identity.get("label", ""),
        "age_band": identity.get("ageBand", "25–34"),
        "tech_savviness": identity.get("techSavviness", 0.5),
        "language": identity.get("language", "English"),
        "disabilities": identity.get("disabilities", []),
        "behavior_profile": {
            "dwell_multiplier": behavior.get("dwellMultiplier", 1.0),
            "giveup_threshold_s": behavior.get("giveupThresholdS", 60),
        },
        "misinterpret_prob": behavior.get("misinterpretProb", 0.2),
        "thresholds": {},
    }
    res = get_client().table("personas").insert(row).execute()
    rows = res.data or []
    return _row_to_persona(rows[0]) if rows else None


def update_persona(slug: str, identity: dict, behavior: dict) -> dict | None:
    if not _has_creds():
        return None
    from app.db import get_client
    patch = {
        "name": identity["name"],
        "label": identity.get("label", ""),
        "age_band": identity.get("ageBand", "25–34"),
        "tech_savviness": identity.get("techSavviness", 0.5),
        "language": identity.get("language", "English"),
        "disabilities": identity.get("disabilities", []),
        "behavior_profile": {
            "dwell_multiplier": behavior.get("dwellMultiplier", 1.0),
            "giveup_threshold_s": behavior.get("giveupThresholdS", 60),
        },
        "misinterpret_prob": behavior.get("misinterpretProb", 0.2),
    }
    res = get_client().table("personas").update(patch).eq("slug", slug).execute()
    rows = res.data or []
    return _row_to_persona(rows[0]) if rows else None


def delete_persona(slug: str) -> None:
    if not _has_creds():
        return
    from app.db import get_client
    get_client().table("personas").delete().eq("slug", slug).execute()


def get_raw_persona_row(slug: str) -> dict | None:
    if not _has_creds():
        return None
    from app.db import get_client
    rows = get_client().table("personas").select("*").eq("slug", slug).limit(1).execute().data or []
    return rows[0] if rows else None


def set_figurine_status(slug: str, status: str, url: str | None = None) -> None:
    if not _has_creds():
        return
    from app.db import get_client
    patch: dict = {"figurine_status": status}
    if url is not None:
        patch["figurine_url"] = url
    get_client().table("personas").update(patch).eq("slug", slug).execute()

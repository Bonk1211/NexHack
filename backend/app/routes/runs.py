"""Run orchestration routes (§8 orchestrator).

The orchestrator (app.orchestrator) launches one nav agent per persona
SEQUENTIALLY (§20), scores each journey, then builds the evidence pack. The pack
is held in an in-memory store keyed by run_id so the API is usable without a DB;
persistence (app.repository) is invoked best-effort and never blocks the response.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import pathlib
import queue
import re
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app import orchestrator, repository
from app.agents.llm import synthesize
from app.agents.persona_graph import stream_persona
from app.agents.run_graph import DEFAULT_FLOW, _requires_labels
from app.agents.navigator import FlowStep
from app.config import settings
from app.evidence.export import pack_to_json_bytes, pack_to_pdf_bytes
from app.evidence.pack import PersonaRunResult, build_pack, build_replay
from app.scoring.engine import score
from app.scoring.personas import load_library, load_persona, thresholds_for
from app.llm_usage import current_tracker, set_tracker, track_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])

# In-memory store {run_id: {pack, usage}}. Survives only for the process lifetime.
_STORE: dict[str, dict] = {}

# Local screenshot store, served as static files at /artifacts (see app.main).
_ARTIFACTS = pathlib.Path(settings.artifacts_dir).resolve()


def _resolve_flow(app_name: str) -> list[FlowStep]:
    """Look up custom flow steps for an app; fall back to DEFAULT_FLOW."""
    try:
        from app.db import get_client
        client = get_client()
        apps = client.table("apps").select("id, flow_steps").eq("name", app_name).limit(1).execute().data or []
        if not apps:
            logger.info("_resolve_flow: no app found for '%s', using DEFAULT_FLOW", app_name)
            return DEFAULT_FLOW
        raw = apps[0].get("flow_steps") or []
        if not raw:
            logger.info("_resolve_flow: app '%s' has no flow_steps, using DEFAULT_FLOW", app_name)
            return DEFAULT_FLOW
        flow = [
            FlowStep(
                key=s.get("key", ""),
                action=s.get("action", "click"),
                role=s.get("role", ""),
                name=s.get("name", ""),
                value=s.get("value", "000000"),
                critical=s.get("critical", False),
            )
            for s in raw
        ]
        logger.info("_resolve_flow: app '%s' using %d custom steps: %s", app_name, len(flow), [s.key for s in flow])
        return flow
    except Exception:
        logger.warning("_resolve_flow: DB error for '%s', using DEFAULT_FLOW", app_name, exc_info=True)
        return DEFAULT_FLOW


# Default goal for autonomous exploration when an app defines neither flow_steps nor a goal.
_DEFAULT_GOAL = (
    "Perform a deep two-pass functional test of this app, whatever its purpose "
    "(sign-up / login / onboarding / KYC / checkout / booking / application / survey / "
    "profile setup / settings). "
    "PASS 1 — PRIMARY FLOW: follow the main user journey screen by screen "
    "(fill inputs, choose dropdown options, accept required terms, click the primary CTA "
    "— Continue / Next / Submit / Verify / Sign Up / Pay / Confirm / Finish — to advance, "
    "never use 'Skip' shortcuts) until you reach the END state. The END state is a success "
    "/ confirmation / completion screen such as: a dashboard, home, feed, account or "
    "profile page; a 'You're in' / 'Welcome' / 'Success' / 'Thank you' / 'All done' / "
    "'Order placed' / 'Payment successful' / 'Application submitted' / rewards or receipt "
    "screen — a screen with no further required step. "
    "PASS 2 — SECONDARY EXPLORATION: navigate back through each screen and test "
    "every secondary control you skipped (Resend, Help, Skip, Cancel, Edit, toggles, "
    "carousels, tabs, links, menus). "
    "Stop only when both passes are complete for every reachable screen."
)


def _resolve_goal(app_name: str) -> str:
    """Look up a custom exploration goal for an app; fall back to the default goal."""
    try:
        from app.db import get_client
        client = get_client()
        apps = client.table("apps").select("goal").eq("name", app_name).limit(1).execute().data or []
        goal = (apps[0].get("goal") if apps else "") or ""
        return goal.strip() or _DEFAULT_GOAL
    except Exception:
        logger.warning("_resolve_goal: DB error for '%s', using default goal", app_name, exc_info=True)
        return _DEFAULT_GOAL


def _resolve_journey(app_name: str) -> tuple[list[FlowStep], str]:
    """All apps explore autonomously.

    Scripted flow_steps in the DB are intentionally ignored here: they were only
    ever partial lists (fill steps with no navigation clicks between pages), so
    replaying them kept the persona on the first page. The autonomous agent drives
    the real UI and navigates naturally across pages toward the app's goal.
    """
    return [], _resolve_goal(app_name)


class StartRunRequest(BaseModel):
    app_name: str
    target_url: str
    persona_names: list[str]
    seed: int = 1337           # §16 deterministic runs
    mode: str = "sequential"   # §20: sequential for clean demo narration
    run_id: str | None = None  # reuse to resume an interrupted run (§8 checkpoint)


def _to_served_url(ref: str | None) -> str | None:
    """Map a LOCAL artifact path to its /artifacts served URL; pass URLs through.

    After a run, screenshot refs are either Storage URLs (Supabase configured) or
    local paths under the artifacts dir (dev). Storage URLs (http…) are returned
    as-is; local paths become `/artifacts/<run_id>/<persona>/step_N.png` so the
    frontend can render the empathy-replay frames (FR-1.3).
    """
    if not ref or ref.startswith(("http://", "https://", "/artifacts/")):
        return ref
    try:
        rel = os.path.relpath(pathlib.Path(ref).resolve(), _ARTIFACTS)
    except ValueError:
        return ref
    if rel.startswith(".."):
        return ref  # outside the served root — leave untouched
    return "/artifacts/" + rel.replace(os.sep, "/")


def _serve_screenshots(pack: dict) -> None:
    """Rewrite every screenshot ref in the pack to a browser-loadable URL (in place)."""
    for persona, shots in pack.get("screenshots", {}).items():
        pack["screenshots"][persona] = [_to_served_url(s) for s in shots]
    for clip in pack.get("replay", {}).values():
        for frame in clip.get("frames", []):
            frame["screenshot_url"] = _to_served_url(frame.get("screenshot_url"))


@router.get("/apps")
def list_apps() -> list[dict]:
    """All apps with metadata for the projects listing page."""
    return repository.list_apps()


@router.get("/apps/{app_id}")
def get_app(app_id: str) -> dict:
    """Single app detail for the project detail page."""
    result = repository.get_app(app_id)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


class CreateAppRequest(BaseModel):
    name: str
    stagingUrl: str | None = None
    repoUrl: str | None = None
    description: str | None = None


@router.post("/apps")
def create_app(req: CreateAppRequest) -> dict:
    """Create a new app."""
    result = repository.create_app(req.name, req.stagingUrl, req.repoUrl, req.description)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create app")
    return result


class UpdateAppRequest(BaseModel):
    description: str | None = None


@router.patch("/apps/{app_id}")
def update_app(app_id: str, req: UpdateAppRequest) -> dict:
    """Patch an app's metadata."""
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    result = repository.update_app(app_id, patch)
    if not result:
        raise HTTPException(status_code=404, detail="App not found")
    return result


# ── Demographics ──────────────────────────────────────────────────────────────

@router.get("/apps/{app_id}/demographics")
def get_demographics(app_id: str) -> list[dict]:
    return repository.get_demographics(app_id)


class AddDemographicRequest(BaseModel):
    label: str
    description: str | None = None


@router.post("/apps/{app_id}/demographics")
def add_demographic(app_id: str, req: AddDemographicRequest) -> list[dict]:
    return repository.add_demographic(app_id, req.label, req.description)


@router.delete("/apps/{app_id}/demographics/{demo_id}")
def delete_demographic(app_id: str, demo_id: str) -> list[dict]:
    return repository.delete_demographic(app_id, demo_id)


@router.post("/apps/{app_id}/suggest-personas")
def suggest_personas(app_id: str) -> list[dict]:
    """Ask DeepSeek to suggest personas for this project based on its demographics."""
    from app import suggest
    app = repository.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return suggest.suggest_personas(app_id, app["name"])


class LinkPersonaRequest(BaseModel):
    personaId: str


@router.post("/apps/{app_id}/personas")
def link_persona_to_app(app_id: str, req: LinkPersonaRequest) -> dict:
    """Link a persona to an app."""
    success = repository.link_persona_to_app(app_id, req.personaId)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to link persona")
    return {"success": True}


@router.delete("/apps/{app_id}/personas/{persona_id}")
def unlink_persona_from_app(app_id: str, persona_id: str) -> dict:
    """Unlink a persona from an app."""
    success = repository.unlink_persona_from_app(app_id, persona_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to unlink persona")
    return {"success": True}


@router.get("/apps/{app_id}/personas")
def get_linked_personas(app_id: str) -> list[str]:
    """Get list of persona IDs linked to an app."""
    return repository.get_linked_personas_for_app(app_id)


class UpdateFlowRequest(BaseModel):
    steps: list[dict]


@router.get("/apps/{app_id}/flow")
def get_flow_steps(app_id: str) -> list[dict]:
    """Get flow steps for an app."""
    return repository.get_flow_steps(app_id)


@router.put("/apps/{app_id}/flow")
def update_flow_steps(app_id: str, req: UpdateFlowRequest) -> dict:
    """Update flow steps for an app."""
    success = repository.update_flow_steps(app_id, req.steps)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update flow steps")
    return {"success": True}


@router.get("")
def list_runs(app_name: str | None = None) -> list[dict]:
    """Run listing.

    With `app_name`: persisted run history for that app (newest first), from
    Supabase — backs the run-history tab; returns [] when persistence is off.
    Without it: the in-memory runs produced in this process (legacy/session view).
    """
    if app_name:
        return repository.list_runs(app_name)

    response = []
    for rid, payload in _STORE.items():
        pack = payload.get("pack") if isinstance(payload, dict) and "pack" in payload else payload
        if not isinstance(pack, dict):
            continue
        response.append(
            {"run_id": rid, "app": pack.get("app"), "inclusion_score": pack.get("inclusion_score")}
        )
    return response


@router.post("")
def start_run(req: StartRunRequest) -> dict:
    # run_id doubles as the run graph's checkpointer thread_id. A client may pass an
    # existing id to RESUME an interrupted run; re-POSTing a completed id is idempotent
    # (returns the existing pack), neither re-runs nor duplicates personas.
    run_id = req.run_id or str(uuid.uuid4())
    flow, goal = _resolve_journey(req.app_name)
    with track_usage() as tracker:
        pack = orchestrator.run_assessment(
            app_name=req.app_name,
            target_url=req.target_url,
            persona_names=req.persona_names,
            flow=flow,
            goal=goal,
            seed=req.seed,
            run_id=run_id,
            artifact_root=str(_ARTIFACTS / run_id),   # FR-1.3: capture a screenshot every step
        )

        # Serialize usage first so it persists onto the run row (dashboard §3.2).
        usage = tracker.serialized()

        # Best-effort persistence — log DB errors so failures are visible, but never
        # block the demo path. Pass the real run_id so history links back to this run.
        try:
            repository.persist_run(
                pack, run_id=run_id, mode="sequential", target_url=req.target_url, usage=usage
            )
        except Exception:
            logger.warning("persist_run failed for run %s", run_id, exc_info=True)

        # Make any remaining LOCAL screenshot paths loadable by the browser (dev, no Storage).
        _serve_screenshots(pack)

    _STORE[run_id] = {"pack": pack, "usage": usage}
    return {"run_id": run_id, "pack": pack, "usage": usage}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _safe_enqueue(q: queue.Queue, item: dict) -> None:
    try:
        q.put_nowait(item)
    except queue.Full:
        pass


def _step_status(step) -> str:
    if step.dead_end:
        return "red"
    return "green" if step.completed else "amber"


@router.get("/stream")
def stream_run(
    app_name: str,
    target_url: str,
    persona_names: str,
    seed: int = 1337,
    run_id: str | None = None,
    mode: str = "sequential",
) -> StreamingResponse:
    """SSE: run the assessment and stream every graph node as it executes (§8/§20).

    `persona_names` is comma-separated (EventSource is GET-only). `mode` selects
    `sequential` (personas run one after another, §20 narration) or `parallel`
    (all personas drive their own browser concurrently). Either way each persona
    subgraph node (observe→comprehend→decide→act) is emitted the moment it completes,
    carrying the screenshot the agent just captured, tagged with its persona so the
    client can route it to the right column.
    """
    names = [n for n in persona_names.split(",") if n]
    parallel = mode == "parallel"
    rid = run_id or str(uuid.uuid4())
    root = _ARTIFACTS / rid

    # The graph runs on a worker thread and pushes events onto this queue; the SSE
    # generator drains it. This lets CDP screencast frames stream CONTINUOUSLY (the
    # live external-app browser) while the graph is mid-node, instead of only at node
    # boundaries. `frame` events are dropped under backpressure so video never lags.
    q: queue.Queue = queue.Queue(maxsize=48)
    SENTINEL = object()

    tracker_cm = track_usage(on_update=lambda summary: _safe_enqueue(q, {"type": "usage", "summary": summary}))
    tracker = tracker_cm.__enter__()

    def worker():
        try:
            set_tracker(tracker)
            q.put({"type": "node", "scope": "run", "node": "init", "personas": names})

            def run_one(i: int, name: str) -> tuple[PersonaRunResult, list]:
                """Drive one persona end-to-end, emitting its nodes onto `q`.

                Returns its scored result and screenshots. When run on a persona
                thread (parallel mode) the usage tracker is thread-local, so re-bind
                it here; in sequential mode this is a harmless no-op.
                """
                set_tracker(tracker)
                cfg = {**load_persona(name), "stem": name}
                thresholds = thresholds_for(cfg)
                flow, goal = _resolve_journey(app_name)
                payload = {
                    "persona": name,
                    "persona_idx": i,
                    "behavior_profile": cfg.get("behavior_profile", {}),
                    "requires_labels": _requires_labels(cfg),
                    "thresholds": thresholds,
                    "target_url": target_url,
                    "flow": flow,
                    "goal": goal,                     # autonomous exploration when flow is empty
                    "max_steps": 50,                  # safety cap on the autonomous loop
                    "viewport": "iPhone 13",          # FR-1.1 mobile device descriptor
                    "seed": seed + i,                 # §16 deterministic per persona
                    "artifact_dir": str(root / name),  # FR-1.3 screenshot every step
                }
                q.put({"type": "persona_start", "persona": name, "idx": i,
                       "label": cfg.get("name", name)})

                def on_frame(b64, _name=name):
                    try:
                        q.put_nowait({"type": "frame", "persona": _name, "data": b64})
                    except queue.Full:
                        pass  # drop the frame — keep the live view current, not buffered

                steps, shots = [], []
                for node, data in stream_persona(payload, on_frame=on_frame):
                    if node == "observe":
                        q.put({"type": "node", "scope": "persona", "persona": name,
                               "node": "observe", "step_idx": len(steps),
                               "output": {"captured": f"step {len(steps)} screen + a11y tree"},
                               "screenshot_url": _to_served_url(data.get("current_shot"))})
                    elif node == "plan":
                        act = data.get("current_action") or {}
                        q.put({"type": "node", "scope": "persona", "persona": name,
                               "node": "plan", "confusion": data.get("last_confusion"),
                               "output": {"action": act.get("action"),
                                          "target": act.get("name") or act.get("role"),
                                          "confusion": data.get("last_confusion"),
                                          "reason": data.get("last_reason")}})
                    elif node == "decide":
                        q.put({"type": "node", "scope": "persona", "persona": name,
                               "node": "decide", "dwell_s": data.get("current_dwell"),
                               "output": {"dwell_s": data.get("current_dwell"),
                                          "label_block": data.get("current_label_block"),
                                          "give_up": data.get("current_give_up")}})
                    elif node == "act":
                        if "steps" not in data:  # done-path early return has no step row
                            continue
                        step = data["steps"][0]
                        shot = data["shots"][0]
                        steps.append(step)
                        shots.append(shot)
                        q.put({"type": "step", "scope": "persona", "persona": name,
                               "node": "act", "step_idx": step.step_idx,
                               "step_key": step.step_key, "status": _step_status(step),
                               "confusion": step.llm_confusion, "dwell_s": step.dwell_s,
                               "output": {"step": step.step_key, "status": _step_status(step),
                                          "dead_end": step.dead_end, "completed": step.completed},
                               "screenshot_url": _to_served_url(shot)})

                res = PersonaRunResult(name, tuple(steps), thresholds, score(steps, thresholds))
                v = res.result.persona_verdict
                q.put({"type": "persona_done", "persona": name, "verdict": v.verdict,
                       "severity": v.severity, "blocked_at": v.blocked_at})
                return res, shots

            # Run personas concurrently (own browser each) or one at a time. Either way
            # assemble results in submission order so downstream scoring is deterministic.
            per_persona: dict[str, tuple[PersonaRunResult, list]] = {}
            if parallel and len(names) > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(names)) as ex:
                    futures = {ex.submit(run_one, i, name): name for i, name in enumerate(names)}
                    for fut in concurrent.futures.as_completed(futures):
                        per_persona[futures[fut]] = fut.result()
            else:
                for i, name in enumerate(names):
                    per_persona[name] = run_one(i, name)

            results: list[PersonaRunResult] = [per_persona[name][0] for name in names]
            shots_map: dict[str, list] = {name: per_persona[name][1] for name in names}

            # Reduce → score → evidence (the run-graph tail, narrated as nodes w/ output).
            q.put({"type": "node", "scope": "run", "node": "aggregate",
                   "output": {"ordered_personas": [r.persona for r in results]}})
            q.put({"type": "node", "scope": "run", "node": "score",
                   "output": {"scores": [
                       {"persona": r.persona,
                        "inclusion_score": r.result.composite.inclusion_score,
                        "verdict": r.result.persona_verdict.verdict,
                        "severity": r.result.persona_verdict.severity}
                       for r in results]}})
            pack = build_pack(app_name, datetime.now(timezone.utc).isoformat(), results)
            pack["screenshots"] = {r.persona: shots_map.get(r.persona, []) for r in results}
            disab = {r.persona: load_persona(r.persona).get("disabilities", []) for r in results}
            rows = pack["matrix"]["rows"]
            pack["replay"] = {
                p["persona"]: build_replay(
                    disab.get(p["persona"], []), p["steps"],
                    pack["screenshots"].get(p["persona"], []), rows.get(p["persona"], {}),
                )
                for p in pack["personas"]
            }
            pack["synthesis"] = synthesize(pack).model_dump()
            wcag_fails = [c for c, vd in pack.get("wcag_conformance", {}).items() if vd == "fail"]
            blocked = [p["persona"] for p in pack["personas"] if p["verdict"] == "blocked"]
            q.put({"type": "node", "scope": "run", "node": "evidence",
                   "output": {"inclusion_score": pack["inclusion_score"],
                              "wcag_failures": wcag_fails,
                              "remediations": len(pack.get("remediation", [])),
                              "blocked_personas": blocked,
                              "rollup": pack["synthesis"].get("rollup")}})

            # Serialize usage first so it persists onto the run row (dashboard §3.2).
            usage = tracker.serialized()
            try:
                repository.persist_run(
                    pack, run_id=rid, mode=mode, target_url=target_url, usage=usage
                )
            except Exception:
                logger.warning("persist_run failed for run %s", rid, exc_info=True)
            _serve_screenshots(pack)
            q.put({"type": "node", "scope": "run", "node": "alerts",
                   "output": {"p0_alerts": len([p for p in pack["personas"]
                                                if p.get("severity") == "P0"])}})
            _STORE[rid] = {"pack": pack, "usage": usage}
            _safe_enqueue(q, {"type": "usage", "summary": usage})
            q.put({"type": "final", "run_id": rid, "pack": pack, "usage": usage})
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client
            q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            set_tracker(None)
            q.put(SENTINEL)

    def gen():
        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                item = q.get()
                if item is SENTINEL:
                    break
                yield _sse(item)
        finally:
            tracker_cm.__exit__(None, None, None)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


personas_router = APIRouter(prefix="/personas", tags=["personas"])


@personas_router.get("")
def list_personas() -> list[dict]:
    """The persona library (FR-1.4): pick ≥3 to run over the same flow."""
    return [
        {
            "stem": stem,
            "name": cfg.get("name", stem),
            "disabilities": cfg.get("disabilities", []),
            "language": cfg.get("language"),
        }
        for stem, cfg in load_library().items()
    ]


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    """Single run for the detail page: in-memory first (this session), then the
    Supabase-persisted pack so historical runs from run history open too."""
    payload = _STORE.get(run_id)
    if payload is not None:
        if isinstance(payload, dict) and "pack" in payload:
            return {"pack": payload["pack"], "usage": payload.get("usage")}
        return payload

    pack = repository.get_run(run_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"pack": pack, "usage": None}


def _safe_slug(text: str) -> str:
    """Filename-safe slug for the Content-Disposition download name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "evidence"


@router.get("/{run_id}/export")
def export_run(run_id: str, format: str = "json") -> Response:
    """Download the §13 evidence pack as a compliance artifact (FR-4.1).

    `format=json` (canonical, machine-readable) or `format=pdf` (audit deliverable).
    Renders the in-memory pack on demand; both share the two-stream layout (§16).
    """
    payload = _STORE.get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    if isinstance(payload, dict) and "pack" in payload:
        pack = payload["pack"]
    else:
        pack = payload

    fmt = format.lower()
    if fmt not in ("json", "pdf"):
        raise HTTPException(status_code=400, detail="format must be 'json' or 'pdf'")

    stem = f"inclusionscope_{_safe_slug(str(pack.get('app', 'app')))}_{run_id[:8]}"
    if fmt == "pdf":
        body, media = pack_to_pdf_bytes(pack), "application/pdf"
    else:
        body, media = pack_to_json_bytes(pack), "application/json"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{stem}.{fmt}"'},
    )

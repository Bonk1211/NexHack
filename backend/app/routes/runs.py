"""Run orchestration routes (§8 orchestrator).

The orchestrator (app.orchestrator) launches one nav agent per persona
SEQUENTIALLY (§20), scores each journey, then builds the evidence pack. The pack
is held in an in-memory store keyed by run_id so the API is usable without a DB;
persistence (app.repository) is invoked best-effort and never blocks the response.
"""
from __future__ import annotations

import concurrent.futures
import json
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
from app.config import settings
from app.evidence.export import pack_to_json_bytes, pack_to_pdf_bytes
from app.evidence.pack import PersonaRunResult, build_pack, build_replay
from app.scoring.engine import score
from app.scoring.personas import load_library, load_persona, thresholds_for
from app.llm_usage import current_tracker, set_tracker, track_usage

router = APIRouter(prefix="/runs", tags=["runs"])

# In-memory store {run_id: {pack, usage}}. Survives only for the process lifetime.
_STORE: dict[str, dict] = {}

# Local screenshot store, served as static files at /artifacts (see app.main).
_ARTIFACTS = pathlib.Path(settings.artifacts_dir).resolve()


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


@router.post("")
def start_run(req: StartRunRequest) -> dict:
    # run_id doubles as the run graph's checkpointer thread_id. A client may pass an
    # existing id to RESUME an interrupted run; re-POSTing a completed id is idempotent
    # (returns the existing pack), neither re-runs nor duplicates personas.
    run_id = req.run_id or str(uuid.uuid4())
    with track_usage() as tracker:
        pack = orchestrator.run_assessment(
            app_name=req.app_name,
            target_url=req.target_url,
            persona_names=req.persona_names,
            seed=req.seed,
            run_id=run_id,
            artifact_root=str(_ARTIFACTS / run_id),   # FR-1.3: capture a screenshot every step
        )

        # Best-effort persistence — swallow DB errors so the demo path never breaks.
        try:
            repository.persist_run(pack)
        except Exception:
            pass

        # Make any remaining LOCAL screenshot paths loadable by the browser (dev, no Storage).
        _serve_screenshots(pack)
        usage = tracker.serialized()

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
                payload = {
                    "persona": name,
                    "persona_idx": i,
                    "behavior_profile": cfg.get("behavior_profile", {}),
                    "requires_labels": _requires_labels(cfg),
                    "thresholds": thresholds,
                    "target_url": target_url,
                    "flow": DEFAULT_FLOW,
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
                    elif node == "comprehend":
                        q.put({"type": "node", "scope": "persona", "persona": name,
                               "node": "comprehend", "confusion": data.get("last_confusion"),
                               "output": {"confusion": data.get("last_confusion"),
                                          "reason": data.get("last_reason"),
                                          "fallback_target": data.get("last_fallback")}})
                    elif node == "decide":
                        q.put({"type": "node", "scope": "persona", "persona": name,
                               "node": "decide", "dwell_s": data.get("current_dwell"),
                               "output": {"dwell_s": data.get("current_dwell"),
                                          "label_block": data.get("current_label_block"),
                                          "give_up": data.get("current_give_up")}})
                    elif node == "act":
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

            try:
                repository.persist_run(pack)
            except Exception:
                pass
            _serve_screenshots(pack)
            q.put({"type": "node", "scope": "run", "node": "alerts",
                   "output": {"p0_alerts": len([p for p in pack["personas"]
                                                if p.get("severity") == "P0"])}})
            usage = tracker.serialized()
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


@router.get("")
def list_runs() -> list[dict]:
    response = []
    for rid, payload in _STORE.items():
        pack = payload.get("pack") if isinstance(payload, dict) and "pack" in payload else payload
        if not isinstance(pack, dict):
            continue
        response.append({
            "run_id": rid,
            "app": pack.get("app"),
            "inclusion_score": pack.get("inclusion_score"),
        })
    return response


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    payload = _STORE.get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not found")
    if isinstance(payload, dict) and "pack" in payload:
        return {"pack": payload["pack"], "usage": payload.get("usage")}
    return payload


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

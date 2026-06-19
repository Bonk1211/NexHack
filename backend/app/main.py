"""FastAPI entrypoint. `uv run uvicorn app.main:app --reload` (from backend/)."""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import runs

app = FastAPI(title="InclusionScope", version="0.1.0")

# Dev CORS: the Next.js frontend (localhost:3000) calls this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(runs.personas_router)

# Serve per-run screenshots (FR-1.3 empathy-replay frames) when Supabase Storage is
# not configured — the run route rewrites local paths to /artifacts/<run_id>/... URLs.
_ARTIFACTS = pathlib.Path(settings.artifacts_dir).resolve()
_ARTIFACTS.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(_ARTIFACTS)), name="artifacts")

# Serve the demo fixture site (the planted-flaw OTP flow) so a run has a target
# out of the box: http://localhost:8000/fixture/index.html
_FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "fixture-site"
if _FIXTURE.is_dir():
    app.mount("/fixture", StaticFiles(directory=str(_FIXTURE)), name="fixture")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

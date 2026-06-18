"""FastAPI entrypoint. `uv run uvicorn app.main:app --reload` (from backend/)."""
from __future__ import annotations

from fastapi import FastAPI

from app.routes import runs

app = FastAPI(title="InclusionScope", version="0.1.0")
app.include_router(runs.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

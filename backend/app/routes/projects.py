"""Per-project aggregated dashboard (dashboard spec §4).

One fetch returns the §5 ProjectDashboard for an app: KPI headline, run trends,
persona reliability, usage-by-model, and the open P0/P1 action queue. Per-model
usage and WCAG roll-ups are computed in SQL (cheaper than client-side, §4); the
math lives in app.repository.aggregate_dashboard so it stays unit-testable.

Best-effort like the rest of the persistence layer: with no Supabase creds (or no
runs yet) it returns an empty shell, so the endpoint never 500s on a fresh deploy.
"""
from __future__ import annotations

from fastapi import APIRouter

from app import repository

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}/dashboard")
def project_dashboard(project_id: str) -> dict:
    try:
        return repository.fetch_project_dashboard(project_id)
    except Exception:
        # Never break the dashboard on a DB hiccup — return the empty shell.
        return {
            "projectId": project_id, "runsCount": 0, "latestScore": None,
            "totalTokens": 0, "totalCost": 0.0, "currency": "USD", "pricingApplied": False,
            "trend": [], "personaReliability": [], "usageByModel": [], "actions": [],
        }

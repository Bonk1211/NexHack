"""Persona navigation contract (§8, §9.1).

This module owns the STABLE types every caller depends on — `FlowStep`,
`NavConfig`, `JourneyResult` — plus the a11y-tree primitive `_role_has_name`.
The navigation LOOP itself now lives in `app.agents.persona_graph` as a cyclic
LangGraph subgraph (observe→comprehend→decide→act→route_next); `run_journey`
delegates to it. The signature and return type are unchanged so the orchestrator
and the contract tests keep working.

Resolved navigation method (§8): the ACCESSIBILITY TREE drives navigation — it is
robust, cheap, and is the trusted signal source. The vision LLM provides per-screen
comprehension judgment and is the navigation FALLBACK, not the driver. A screenshot
is captured every step (FR-1.3), powering empathy replay independent of the LLM.

All persona hesitation/randomness uses a SEEDED RNG (FR-2.3, §16) so runs are
deterministic; the RNG is seeded in `run_journey`, not in the scorer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.scoring.engine import StepSignals


@dataclass
class FlowStep:
    """One step of the target flow, located by a11y role/name."""
    key: str
    action: str            # 'fill' | 'click' | 'view'
    role: str = ""         # a11y role to target (e.g. 'textbox', 'button')
    name: str = ""         # accessible name to match (for click disambiguation)
    value: str = "000000"  # text to fill
    critical: bool = False  # step criticality for severity (§12)


@dataclass
class NavConfig:
    target_url: str
    flow: list[FlowStep]
    viewport: str = "iPhone 13"          # Playwright device descriptor (FR-1.1, mobile emulation)
    behavior_profile: dict = field(default_factory=dict)  # §11
    requires_labels: bool = False        # persona depends on labels/SR semantics (oku_visual)
    seed: int = 1337                     # deterministic per (persona, run)
    artifact_dir: str | None = None      # where to save per-step screenshots


@dataclass
class JourneyResult:
    steps: list[StepSignals]
    screenshots: list[str | None]


def _role_has_name(aria_snapshot: str, role: str) -> bool:
    """True if the a11y tree contains `role` WITH a non-empty accessible name.

    Modern Playwright exposes the tree via `locator.aria_snapshot()` (the
    `page.accessibility` API was removed). A labeled control renders as
    `- textbox "One-time code"`; an unlabeled one as a bare `- textbox`.
    """
    pat = re.compile(rf'^\s*-\s+{re.escape(role)}\s+"[^"]+"', re.MULTILINE)
    return bool(pat.search(aria_snapshot))


def run_journey(cfg: NavConfig) -> JourneyResult:
    """Drive one persona through the flow; return per-step signals + screenshots.

    Thin wrapper over the persona subgraph. The import is function-local to break
    the navigator↔persona_graph cycle (persona_graph imports the types above).
    """
    from app.agents.persona_graph import run_journey as _run

    return _run(cfg)

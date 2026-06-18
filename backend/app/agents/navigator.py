"""Persona navigation agent (§8, §9.1).

Resolved navigation method (§8): the ACCESSIBILITY TREE drives navigation — it is
robust, cheap, and it is also the trusted signal source. The vision LLM (stretch)
provides per-screen comprehension judgment and is the navigation FALLBACK when the
a11y tree is insufficient; it does not drive nav. A screenshot is captured EVERY
step regardless (FR-1.3) — that is what powers empathy replay, so the differentiator
never depends on vision-driven navigation.

All persona hesitation/randomness uses a SEEDED RNG (FR-2.3, §16) so runs are
deterministic. The RNG lives HERE, not in the scorer (the scorer stays pure).

Sync Playwright on purpose: each persona journey is a self-contained unit the
orchestrator runs (threaded) per persona; sync keeps the loop and its tests simple.
"""
from __future__ import annotations

import pathlib
import random
import re
from dataclasses import dataclass, field

from playwright.sync_api import sync_playwright

from app.agents.signals import axe_to_wcag, reading_grade, run_axe
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
    """Drive one persona through the flow; return per-step signals + screenshots."""
    rng = random.Random(cfg.seed)
    bp = cfg.behavior_profile
    dwell_mult = float(bp.get("dwell_multiplier", 1.0))
    wpm = float(bp.get("reading_speed_wpm", 200))
    hesitation_prob = float(bp.get("hesitation_prob", 0.0))
    giveup_s = float(bp.get("giveup_threshold_s", 60))

    steps: list[StepSignals] = []
    shots: list[str | None] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(**p.devices[cfg.viewport])
        try:
            page.goto(cfg.target_url, wait_until="load")

            # TRUSTED stream — page-level axe, persona-independent (§16).
            wcag = axe_to_wcag(run_axe(page))
            aria = page.locator("body").aria_snapshot()
            body_text = page.inner_text("body")
            grade = reading_grade(body_text)
            word_count = max(len(body_text.split()), 1)

            for i, fs in enumerate(cfg.flow):
                # Dwell from reading load x persona pace + seeded hesitation.
                read_s = (word_count / wpm) * 60.0
                dwell = read_s * dwell_mult
                if rng.random() < hesitation_prob:
                    dwell *= 1.5

                dead_end = False
                completed = True
                retries = 0
                confusion = 0.0

                if fs.action in ("fill", "click"):
                    labeled = _role_has_name(aria, fs.role)

                    if fs.action == "fill" and cfg.requires_labels and not labeled:
                        # Persona relies on labels/SR semantics; the field is unlabeled.
                        # Indicative: "agent could not locate a labeled field" (§13 example).
                        dead_end, completed, confusion = True, False, 1.0
                    else:
                        try:
                            if fs.action == "fill":
                                page.get_by_role(fs.role).first.fill(fs.value, timeout=3000)
                            elif fs.name:
                                page.get_by_role(fs.role, name=fs.name).first.click(timeout=3000)
                            else:
                                page.get_by_role(fs.role).first.click(timeout=3000)
                            retries = 1 if rng.random() < hesitation_prob else 0
                        except Exception:
                            dead_end, completed = True, False

                if dwell >= giveup_s:
                    dead_end, completed = True, False

                # Screenshot EVERY step (FR-1.3) — feeds empathy replay + evidence.
                shot = None
                if cfg.artifact_dir:
                    d = pathlib.Path(cfg.artifact_dir)
                    d.mkdir(parents=True, exist_ok=True)
                    shot = str(d / f"step_{i}.png")
                    page.screenshot(path=shot)
                shots.append(shot)

                steps.append(
                    StepSignals(
                        step_idx=i,
                        step_key=fs.key,
                        critical=fs.critical,
                        wcag=wcag if i == 0 else (),  # page-level axe attached to entry step
                        dwell_s=round(dwell, 2),
                        retries=retries,
                        dead_end=dead_end,
                        completed=completed,
                        llm_confusion=confusion,
                        reading_grade=grade,
                    )
                )
                if dead_end:
                    break
        finally:
            browser.close()

    return JourneyResult(steps, shots)

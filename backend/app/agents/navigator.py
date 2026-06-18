"""Persona navigation agent (§8, §9.1). SCAFFOLD.

Resolved navigation method (§8): the accessibility tree drives navigation
(robust, cheap, AND it is the trusted signal source). The vision LLM provides
per-screen comprehension judgment (the indicative "I don't know what this field
wants" signal) and is the navigation FALLBACK when the a11y tree is insufficient.
Screenshot every step regardless (FR-1.3) — that is what powers empathy replay,
so the differentiator never depends on vision-driven navigation.

All persona hesitation/randomness uses a SEEDED RNG (FR-2.3, §16) so runs are
reproducible. The RNG lives HERE, not in the scorer (the scorer stays pure).
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class NavConfig:
    target_url: str
    viewport: str           # Playwright device descriptor (FR-1.1, mobile emulation)
    behavior_profile: dict  # persona behavior_profile (§11)
    seed: int = 1337


async def run_journey(cfg: NavConfig):
    """Drive one persona through the flow; yield per-step capture.

    TODO(§9.1, FR-1.1..1.4):
      - launch Playwright with the mobile device descriptor (cfg.viewport)
      - walk the a11y tree, parameterized by cfg.behavior_profile
      - vision-LLM comprehension judgment + nav fallback
      - screenshot every step (FR-1.3) -> Supabase Storage
      - inject hesitation via `rng` below for determinism
    STRETCH: CDP network throttle (FR-1.5); second-language run (FR-1.6).
    """
    rng = random.Random(cfg.seed)  # seeded — deterministic per (persona, run)
    _ = rng
    raise NotImplementedError("Playwright a11y-tree nav loop not implemented — scaffold")

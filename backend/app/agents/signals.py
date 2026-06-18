"""Dual-signal capture (§8, §9.2, §10).

Stream A — ACCESSIBILITY SIGNALS (TRUSTED): produced here from axe-core (§10).
Maps each axe result's WCAG tag (e.g. `wcag143`) to its criterion (`1.4.3`) so it
stands up as evidence. We do NOT rebuild contrast/label math — axe owns that.

Stream B — BEHAVIORAL SIGNALS (INDICATIVE): produced by the navigator
(app/agents/navigator.py) as it drives a persona through the flow.

The two streams stay distinct all the way to the scorer (§16).
"""
from __future__ import annotations

import re

from axe_playwright_python.sync_playwright import Axe

from app.scoring.engine import WcagSignal

_axe = Axe()  # bundles axe-core; no network needed


def _tag_to_criterion(tag: str) -> str | None:
    """'wcag143' -> '1.4.3'. Returns None for non-numbered tags (wcag2a, wcag2aa…)."""
    if not tag.startswith("wcag"):
        return None
    n = tag[4:]
    if not n.isdigit() or len(n) < 3:
        return None
    return f"{n[0]}.{n[1]}.{n[2:]}"


def run_axe(page) -> dict:
    """Run axe-core against the current page; return the raw results dict."""
    return _axe.run(page, options={"resultTypes": ["violations", "passes"]}).response


def axe_to_wcag(axe_response: dict) -> tuple[WcagSignal, ...]:
    """Translate axe passes/violations into per-criterion WcagSignals (TRUSTED).

    A criterion seen only in `passes` is a pass; any violation flips it to fail.
    """
    seen: dict[str, bool] = {}
    for item in axe_response.get("passes", []):
        for tag in item.get("tags", []):
            crit = _tag_to_criterion(tag)
            if crit and crit not in seen:
                seen[crit] = True
    for item in axe_response.get("violations", []):
        for tag in item.get("tags", []):
            crit = _tag_to_criterion(tag)
            if crit:
                seen[crit] = False  # violation overrides
    return tuple(WcagSignal(c, p) for c, p in sorted(seen.items()))


def _syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def reading_grade(text: str) -> float:
    """Rough Flesch-Kincaid grade level of on-screen copy (low-literacy lens, §11)."""
    words = re.findall(r"[A-Za-z]+", text)
    if not words:
        return 0.0
    sentences = max(len(re.findall(r"[.!?]+", text)), 1)
    syllables = sum(_syllables(w) for w in words)
    w = len(words)
    grade = 0.39 * (w / sentences) + 11.8 * (syllables / w) - 15.59
    return round(max(grade, 0.0), 1)

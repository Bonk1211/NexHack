"""Dual-signal capture (§8, §9.2, §10). SCAFFOLD.

Stream A — ACCESSIBILITY SIGNALS (TRUSTED): contrast, label presence, tap-target
size, focus order, text alternatives. Use axe-core (§10) — do NOT rebuild the
contrast/label math. Maps to WCAG criteria so it stands up as evidence.

Stream B — BEHAVIORAL SIGNALS (INDICATIVE): completion/blocked, dwell, retries,
dead-ends, first-person confusion note from the vision LLM.

These two streams are kept DISTINCT all the way to the scorer (§16) — that
separation is what protects the product from the "it's just a costume" critique.
"""
from __future__ import annotations

from app.scoring.engine import StepSignals, WcagSignal


async def extract_accessibility_signals(page) -> tuple[WcagSignal, ...]:
    """Stream A (trusted). Run axe-core against `page`, map violations to WCAG.

    TODO(§10): inject axe-core, run, translate results to WcagSignal tuples
    keyed by criterion (1.4.3, 1.3.1, 2.5.8, 2.4.3, 1.1.1).
    """
    raise NotImplementedError("axe-core integration not implemented — scaffold")


def behavioral_signals(step_idx: int, step_key: str, **capture) -> StepSignals:
    """Stream B (indicative). Fold the captured behavior into a StepSignals row.

    Trusted WCAG signals (from extract_accessibility_signals) are attached here
    too, but the scorer keeps them in their own result — never collapsed (§16).
    """
    return StepSignals(
        step_idx=step_idx,
        step_key=step_key,
        critical=capture.get("critical", False),
        wcag=tuple(capture.get("wcag", ())),
        dwell_s=capture.get("dwell_s", 0.0),
        retries=capture.get("retries", 0),
        dead_end=capture.get("dead_end", False),
        completed=capture.get("completed", True),
        llm_confusion=capture.get("llm_confusion", 0.0),
        reading_grade=capture.get("reading_grade"),
    )

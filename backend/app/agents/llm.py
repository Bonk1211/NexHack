"""DeepSeek V4 LLM nodes (§15, §25 LOCKED).

Cognition is CONCENTRATED here, on purpose. The whole product has exactly:
  - one mandatory per-step LLM call — `vision_judge` (the `comprehend` node):
    stream-B "I don't know what this field wants" confusion + a nav fallback
    target, on `deepseek-v4-flash`.
  - one optional once-per-run call — `synthesize` (inside the `evidence` node):
    the "who are we excluding" rollup + narrative, on `deepseek-v4-pro`.

Everything marks-bearing (the scorer, the friction matrix, the WCAG conformance)
stays PURE deterministic compute elsewhere — never an LLM (§16). LLM output feeds
only the INDICATIVE stream (`llm_confusion`) and the OUTPUT-side narrative; it
never touches the trusted WCAG stream or the composite math (§16/§23 hard line).

DeepSeek V4 specifics (verified against the live endpoint):
  - Structured output uses `method="json_mode"`, NOT tool-calling/`strict` — the
    V4 models run in thinking mode, which rejects `tool_choice`.
  - The endpoint is TEXT-ONLY (rejects image content), so `comprehend` judges from
    the accessibility tree as text, not the screenshot pixels. That is the right
    signal anyway: the a11y tree is what a screen-reader / low-vision user perceives.

Determinism (§16/§20): temperature=0, and — critically — when no API key is set
every call DEGRADES to a deterministic offline path (heuristic confusion /
templated synthesis) that reproduces the pre-LLM behavior exactly. That keeps
tests network-free (§22) and the demo reproducible.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# --- Structured schemas -----------------------------------------------------

class VisionJudgment(BaseModel):
    """Per-screen comprehension judgment (INDICATIVE stream B, §9.2)."""
    confusion: float = Field(ge=0.0, le=1.0, description="0 clear … 1 'I don't know what this wants'")
    reason: str = Field(default="", description="one short phrase of why")
    fallback_target: str | None = Field(
        default=None, description="accessible name to try if the a11y locate failed"
    )


class SynthesisResult(BaseModel):
    """Once-per-run reasoning synthesis (OUTPUT-side only, §15)."""
    rollup: str = Field(description="the one business line — who is silently excluded (§18)")
    narrative: str = Field(description="2-3 sentence audit-style summary")
    key_exclusions: list[str] = Field(default_factory=list)


# --- Client factory ---------------------------------------------------------

def _client(model: str):
    """Return a configured ChatDeepSeek, or None when offline (no API key).

    None is the signal for every caller to take the deterministic fallback path.
    """
    if not settings.llm_api_key:
        return None
    from langchain_deepseek import ChatDeepSeek

    return ChatDeepSeek(
        model=model,
        api_key=settings.llm_api_key,
        api_base=settings.llm_base_url,
        temperature=0,          # §16 determinism
        max_retries=2,
    )


# --- comprehend (per-step vision) -------------------------------------------

_VISION_SYSTEM = (
    "You simulate a specific user persona attempting one step of a mobile app flow. "
    "From the accessibility tree and the step context, judge how confused this persona "
    "would be about what to do — this is the experience of a screen-reader / low-vision "
    "user, who perceives the page through its a11y semantics, not its pixels. "
    "Respond ONLY with a JSON object of exactly this shape: "
    '{"confusion": <float 0.0-1.0>, "reason": "<short phrase>", '
    '"fallback_target": "<accessible name to try, or null>"}. '
    "confusion 0.0 = obvious, 1.0 = cannot tell what the control wants. "
    "Set fallback_target only when the expected control is not present in the tree."
)


def _heuristic_confusion(*, action: str, requires_labels: bool, labeled: bool) -> float:
    """Offline confusion, identical to the pre-LLM navigator behavior.

    A label-dependent persona facing an unlabeled fill control is fully blocked
    (confusion 1.0); everything else reads as no comprehension signal (0.0).
    """
    if action == "fill" and requires_labels and not labeled:
        return 1.0
    return 0.0


def vision_judge(
    screenshot_path: str | None,
    step_key: str,
    aria_excerpt: str,
    *,
    requires_labels: bool,
    labeled: bool,
    action: str,
) -> VisionJudgment:
    """The `comprehend` node's work: a per-step confusion judgment.

    Judges from the ACCESSIBILITY TREE as text — the configured DeepSeek endpoint
    is text-only (it rejects image content), and the a11y tree is precisely what a
    screen-reader / low-vision user perceives, so this is the right signal for the
    personas that matter. `screenshot_path` is retained for API stability and is
    still captured for empathy replay; it is simply not sent to a text-only model.

    Offline (no key) or on any failure, returns the deterministic heuristic so a
    run never depends on the network (§16/§22).
    """
    fallback = VisionJudgment(
        confusion=_heuristic_confusion(
            action=action, requires_labels=requires_labels, labeled=labeled
        ),
        reason="offline heuristic",
        fallback_target=None,
    )
    client = _client(settings.llm_model_step)
    if client is None or not aria_excerpt:
        return fallback

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        human = HumanMessage(content=(
            f"Persona depends on labels/screen-reader semantics: {requires_labels}. "
            f"Step '{step_key}', action '{action}'. "
            f"Target control has an accessible name in the tree: {labeled}. "
            f"Accessibility tree:\n{aria_excerpt[:2000]}\n"
            "Judge this persona's confusion. Respond in JSON."
        ))
        # json_mode (NOT function_calling/strict): DeepSeek V4 runs in thinking mode,
        # which rejects tool_choice ("Thinking mode does not support this tool_choice").
        # json_mode uses response_format=json_object — no tool call — and parses into
        # the schema; the prompt states the exact JSON shape json_mode needs.
        structured = client.with_structured_output(VisionJudgment, method="json_mode")
        out = structured.invoke([SystemMessage(content=_VISION_SYSTEM), human])
        return out if isinstance(out, VisionJudgment) else fallback
    except Exception as exc:
        # Degrade to the heuristic, but LOG it — a bad/expired key or misconfigured
        # endpoint must not be silently indistinguishable from running offline.
        logger.warning("comprehend LLM call failed (%s: %s); using offline heuristic",
                       type(exc).__name__, exc)
        return fallback


# --- synthesize (once-per-run reasoning) ------------------------------------

_SYNTH_SYSTEM = (
    "You are an accessibility compliance analyst. Given an inclusion evidence pack "
    "(trusted WCAG conformance + indicative persona verdicts), write a short, "
    "audit-style synthesis. Lead with the single business line naming who is "
    "silently excluded. Do not invent WCAG results; use only what is in the pack. "
    "Respond ONLY with a JSON object of exactly this shape: "
    '{"rollup": "<one business line>", "narrative": "<2-3 sentences>", '
    '"key_exclusions": ["<persona (severity) at step>", ...]}.'
)


def _template_synthesis(pack: dict) -> SynthesisResult:
    """Deterministic offline synthesis derived straight from the pack."""
    personas = pack.get("personas", [])
    blocked = [p for p in personas if p.get("verdict") == "blocked"]
    app = pack.get("app", "this app")
    if blocked:
        names = ", ".join(p["persona"] for p in blocked)
        where = blocked[0].get("blocked_at") or "a critical step"
        rollup = f"{app} silently blocks {names} at {where}."
        exclusions = [f"{p['persona']} ({p.get('severity')}) at {p.get('blocked_at')}" for p in blocked]
    else:
        rollup = f"{app} completed for all simulated personas, with residual friction noted."
        exclusions = []
    fails = [c for c, v in pack.get("wcag_conformance", {}).items() if v == "fail"]
    narrative = (
        f"Inclusion score {pack.get('inclusion_score')}. "
        f"Trusted WCAG failures: {', '.join(fails) if fails else 'none'}. "
        f"{len(blocked)} of {len(personas)} personas blocked (indicative)."
    )
    return SynthesisResult(rollup=rollup, narrative=narrative, key_exclusions=exclusions)


def synthesize(pack: dict) -> SynthesisResult:
    """Once-per-run reasoning synthesis. Offline/error → deterministic template."""
    fallback = _template_synthesis(pack)
    client = _client(settings.llm_model_synth)
    if client is None:
        return fallback
    try:
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        compact = json.dumps({
            "app": pack.get("app"),
            "inclusion_score": pack.get("inclusion_score"),
            "wcag_conformance": pack.get("wcag_conformance"),
            "personas": pack.get("personas"),
            "remediation": pack.get("remediation"),
        })[:6000]
        # json_mode, not tool-calling — DeepSeek V4 thinking mode rejects tool_choice.
        structured = client.with_structured_output(SynthesisResult, method="json_mode")
        out = structured.invoke([
            SystemMessage(content=_SYNTH_SYSTEM),
            HumanMessage(content=compact),
        ])
        return out if isinstance(out, SynthesisResult) else fallback
    except Exception as exc:
        logger.warning("synthesize LLM call failed (%s: %s); using template synthesis",
                       type(exc).__name__, exc)
        return fallback

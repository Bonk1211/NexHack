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

import json
import logging
import re

from pydantic import BaseModel, Field

from app.config import settings
from app.llm_usage import record_usage

logger = logging.getLogger(__name__)


# --- Structured schemas -----------------------------------------------------

class VisionJudgment(BaseModel):
    """Per-screen comprehension judgment (INDICATIVE stream B, §9.2)."""
    confusion: float = Field(ge=0.0, le=1.0, description="0 clear … 1 'I don't know what this wants'")
    reason: str = Field(default="", description="one short phrase of why")
    fallback_target: str | None = Field(
        default=None, description="accessible name to try if the a11y locate failed"
    )


class AgentAction(BaseModel):
    """One autonomous navigation decision (goal-directed mode)."""
    step_label: str = Field(description="concise label, e.g. 'entering phone number'")
    action: str = Field(description="fill | click | done | blocked")
    role: str = Field(default="", description="a11y role of target element")
    name: str = Field(default="", description="exact accessible name from the tree")
    value: str = Field(default="", description="text to type for fill, empty otherwise")
    confusion: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="one sentence why this action")


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


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                text = chunk.get("text")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(chunk))
        return "".join(parts)
    return str(content)


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
        ai = client.invoke(
            [SystemMessage(content=_VISION_SYSTEM), human],
            config={"response_format": {"type": "json_object"}},
        )
        usage = getattr(ai, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        model_name = getattr(client, "model", getattr(client, "model_name", ""))
        record_usage(model_name or settings.llm_model_step, prompt_tokens, completion_tokens)

        payload = json.loads(_extract_text(ai.content))
        return VisionJudgment.model_validate(payload)
    except Exception as exc:
        # Degrade to the heuristic, but LOG it — a bad/expired key or misconfigured
        # endpoint must not be silently indistinguishable from running offline.
        logger.warning("comprehend LLM call failed (%s: %s); using offline heuristic",
                       type(exc).__name__, exc)
        return fallback


# --- agent_decide (autonomous goal-directed navigation) ---------------------

_AGENT_SYSTEM = (
    "You are simulating a user persona navigating a mobile web app toward a specific goal. "
    "You perceive the page only through its accessibility tree — exactly as a screen reader would. "
    "Decide the single best NEXT action to take toward the goal. "
    "Respond ONLY with a JSON object of exactly this shape: "
    '{"step_label": "<concise label>", "action": "fill|click|done|blocked", '
    '"role": "<a11y role>", "name": "<exact accessible name from tree>", '
    '"value": "<text to type if fill, else empty>", '
    '"confusion": <0.0-1.0>, "reasoning": "<one sentence>"}. '
    'Use "done" if the goal is achieved or the success URL pattern is visible. '
    'CRITICAL — use "blocked" ONLY when there are literally zero actionable elements on the page. '
    'Confusing, misleading, or double-negative labels are NOT a reason to return "blocked" — '
    'capture your confusion in the confusion score (0.7–1.0) and still choose an action. '
    'BEFORE returning "blocked", you MUST check for a primary action button: any button whose '
    'name contains Finish, Continue, Next, Submit, Done, Proceed, Confirm, OK, or Skip. '
    'If such a button exists, click it — even if you cannot understand the surrounding content. '
    'The "name" field must exactly match an accessible name visible in the tree. '
    "confusion 0.0 = obvious next step, 1.0 = page is confusing but you are still acting. "
    "NAVIGATION RULES: "
    "1) When you see individual OTP digit fields labeled 'Digit 1', 'Digit 2' etc., "
    "fill each one with the corresponding digit from the hint value (e.g. hint 'otp=1234' "
    "→ fill Digit 1 with '1', Digit 2 with '2', etc.). If no OTP hint is provided, "
    "look for a 'Skip for now' link or 'Verify' button and use it — do NOT re-type a "
    "phone number into an OTP field. "
    "2) Only return 'done' when the current URL actually matches the success URL pattern. "
    "If you are not at the target page, keep navigating — 'done' on the wrong page is the "
    "same as giving up."
)

# Deterministic CTA fallback: matches primary action buttons by name keyword.
# Used to override an LLM "blocked" verdict when a clear forward path exists in the tree.
_CTA_PATTERN = re.compile(
    r'button "([^"]*(?:Finish|Continue|Next|Submit|Done|Proceed|Confirm|Okay|OK|Skip)[^"]*)"',
    re.IGNORECASE,
)


def _find_cta(aria: str) -> "AgentAction | None":
    """Scan the a11y tree for a primary CTA button. Returns an AgentAction or None."""
    m = _CTA_PATTERN.search(aria)
    if not m:
        return None
    name = m.group(1)
    return AgentAction(
        step_label=f"click primary CTA: {name}",
        action="click",
        role="button",
        name=name,
        value="",
        confusion=0.8,  # high — page was confusing enough that LLM nearly blocked
        reasoning=f"Deterministic CTA fallback: clicking '{name}' to proceed past confusing page",
    )


def agent_decide(
    goal: str,
    hints: dict,
    success_url: str,
    current_url: str,
    aria_excerpt: str,
    *,
    requires_labels: bool,
) -> AgentAction:
    """Autonomous navigation: LLM decides next action toward goal from the a11y tree.

    Falls back to a safe 'blocked' action on any failure so the run never crashes.
    """
    fallback = AgentAction(
        step_label="navigation",
        action="blocked",
        reasoning="offline — no LLM key or call failed",
    )
    client = _client(settings.llm_model_step)
    if client is None or not aria_excerpt:
        return fallback

    # Short-circuit: success URL already reached
    if success_url and success_url.lstrip("/") in current_url:
        return AgentAction(step_label="goal reached", action="done",
                           reasoning=f"current URL {current_url} matches success_url")

    hints_text = ", ".join(f"{k}={v}" for k, v in hints.items()) if hints else "none"
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        human = HumanMessage(content=(
            f"Goal: {goal}\n"
            f"Current URL: {current_url}\n"
            f"Success URL pattern: {success_url or '(none — infer from goal)'}\n"
            f"Persona depends on labels/screen-reader semantics: {requires_labels}\n"
            f"Available hint values to use in form fields: {hints_text}\n\n"
            f"Accessibility tree:\n{aria_excerpt[:3000]}\n\n"
            "What is the next action? "
            "Remember: if labels are confusing, set confusion high and still act. "
            "Only return 'blocked' if NO buttons, links, or inputs exist on the page. "
            "Respond in JSON."
        ))
        ai = client.invoke(
            [SystemMessage(content=_AGENT_SYSTEM), human],
            config={"response_format": {"type": "json_object"}},
        )
        usage = getattr(ai, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        model_name = getattr(client, "model", getattr(client, "model_name", ""))
        record_usage(model_name or settings.llm_model_step, prompt_tokens, completion_tokens)

        payload = json.loads(_extract_text(ai.content))
        action = AgentAction.model_validate(payload)

        # Fix 2: deterministic CTA override — if LLM returned blocked but a primary
        # action button exists in the tree, click it instead of giving up.
        if action.action == "blocked":
            cta = _find_cta(aria_excerpt)
            if cta:
                logger.info("agent_decide: overriding 'blocked' with CTA fallback '%s'", cta.name)
                return cta

        return action
    except Exception as exc:
        logger.warning("agent_decide failed (%s: %s); returning blocked", type(exc).__name__, exc)
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
        from langchain_core.messages import HumanMessage, SystemMessage

        compact = json.dumps({
            "app": pack.get("app"),
            "inclusion_score": pack.get("inclusion_score"),
            "wcag_conformance": pack.get("wcag_conformance"),
            "personas": pack.get("personas"),
            "remediation": pack.get("remediation"),
        })[:6000]
        ai = client.invoke(
            [
                SystemMessage(content=_SYNTH_SYSTEM),
                HumanMessage(content=compact),
            ],
            config={"response_format": {"type": "json_object"}},
        )
        usage = getattr(ai, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        model_name = getattr(client, "model", getattr(client, "model_name", ""))
        record_usage(model_name or settings.llm_model_synth, prompt_tokens, completion_tokens)

        payload = json.loads(_extract_text(ai.content))
        return SynthesisResult.model_validate(payload)
    except Exception as exc:
        logger.warning("synthesize LLM call failed (%s: %s); using template synthesis",
                       type(exc).__name__, exc)
        return fallback

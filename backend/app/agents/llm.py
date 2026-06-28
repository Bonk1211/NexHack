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

from pydantic import BaseModel, Field

from app.config import settings
from app.llm_usage import record_usage
from app.scoring.engine import StepSignals

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


# --- MCP-style autonomous agent ----------------------------------------------
# Replaces the single-shot agent_decide + regex fallbacks with a multi-turn
# conversation loop. The LLM writes raw Playwright Python executed against the
# live page — one `exec` tool replaces all hardcoded action types, locator
# strategies, and per-site patches.

_MCP_SYSTEM = (
    "You are a user persona navigating a mobile web app to reach a specific goal. "
    "You perceive the page through its accessibility tree — exactly as a screen reader would. "
    "You have FULL control of the browser via a Playwright `page` object (sync API).\n\n"
    "Respond with ONE of these JSON forms:\n\n"
    '  {"exec": "<Playwright Python code>", "step_label": "<what you just did>", '
    '"confusion": <0.0-1.0>, "reasoning": "<one sentence>", "say": "<one short first-person sentence>"}\n\n'
    '  {"done": true, "reasoning": "<why goal is achieved>", "say": "<one short first-person sentence>"}\n\n'
    '  {"blocked": true, "reasoning": "<why no path forward>", "say": "<one short first-person sentence>"}\n\n'
    "The `page` object is in scope. You can call any sync Playwright method on it:\n"
    "  page.get_by_role('textbox', name='Mobile Number').fill('0123456789')\n"
    "  page.get_by_role('button', name='Continue').click()\n"
    "  page.get_by_label('Year').select_option('1990')\n"
    "  page.locator('#outlet').select_option('KLCC')\n"
    "  page.locator('select').first.select_option('1990')\n"
    "  page.keyboard.press('Enter')\n"
    "  page.get_by_role('switch', name='Promos').check()\n"
    "  page.wait_for_load_state('networkidle')\n"
    "  page.url  (read current URL)\n\n"
    "RULES:\n"
    "1. Use the EXACT accessible names shown in the a11y tree. If an action fails, "
    "the error will show available element names — use them in your next attempt.\n"
    "2. Use `done` ONLY when the goal is achieved or success URL is visible.\n"
    "3. Use `blocked` ONLY after trying genuinely different approaches — "
    "a name mismatch is a reason to try again, not to give up.\n"
    "4. For OTP: fill individual 'Digit N' fields one at a time.\n"
    "5. For dropdowns: use select_option() on the element directly — try "
    "get_by_label, then get_by_role, then locator.\n"
    "6. Confusion 0.0=obvious, 1.0=very confused but keep trying.\n"
    "7. 'say' is ONE short first-person sentence in THIS persona's voice — what you're "
    "thinking or feeling right now (doubt, relief, confusion, impatience). Stay fully in "
    "character; never mention being an AI, a test, a screen reader, or an accessibility tree."
)

# Whitelist of safe page methods for exec(). The LLM can only call methods
# on the page object, not import modules or access the filesystem.
_EXEC_GLOBALS = {
    "__builtins__": {
        "True": True, "False": False, "None": None,
        "str": str, "int": int, "float": float, "list": list, "dict": dict,
    },
}

_PLAY_SNAPSHOT = (
    "def snapshot(page):\n"
    "    return page.locator('body').aria_snapshot()\n"
)


def _play_exec(page, code: str) -> str:
    """Execute the LLM's Playwright code against the live page. Returns result/error."""
    import traceback

    # Inject the page object and snapshot helper
    ns = {"page": page}
    try:
        exec(_PLAY_SNAPSHOT, _EXEC_GLOBALS, ns)
        result = exec(code, _EXEC_GLOBALS, ns)
        # If the code is an expression that returns a value, capture it
        result_str = str(result) if result is not None else ""
        # Wait for any navigation to settle
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        url = page.url
        return f"OK. URL: {url}" + (f" → {result_str}" if result_str else "")
    except Exception as exc:
        tb = traceback.format_exc().splitlines()
        # Return the last 3 lines of traceback for conciseness
        err = "\n".join(tb[-3:]) if len(tb) > 3 else "\n".join(tb)
        return f"ERROR:\n{err}"


# A 1×1 JPEG — the smallest valid image we can hand a file <input>. The agent can't
# author files (the exec sandbox blocks the filesystem) and the LLM has no path, so
# document-upload steps are handled deterministically with this fixture.
_UPLOAD_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP//////////////////////////////////////////"
    "////////////////////////////////////////////////wAALCAABAAEBAREA/8QAFAABAAAA"
    "AAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AfwD/2Q=="
)


def _upload_fixture_path(artifact_dir: str | None) -> str:
    """Write the fixture image to disk once and return its path."""
    import base64, pathlib, tempfile
    base = pathlib.Path(artifact_dir) if artifact_dir else pathlib.Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    p = base / "nexhack_upload.jpg"
    if not p.exists():
        p.write_bytes(base64.b64decode(_UPLOAD_JPEG_B64))
    return str(p)


# Localized line for the deterministic upload step (the LLM can't author a file, so
# this `say` doesn't pass through the model — without this it was always English,
# clashing with a non-English persona's monologue). Substring match on persona_voice's
# "language=..." field; default English.
_UPLOAD_SAY = {
    "cantonese": "等我上載我份文件先。",
    "bahasa": "Biar saya muat naik dokumen saya di sini.",
    "iban": "Biar saya muat naik dokumen saya di sini.",
}


def _upload_say(persona_voice: str) -> str:
    v = persona_voice.lower()
    for lang, line in _UPLOAD_SAY.items():
        if lang in v:
            return line
    return "Let me upload my document here."


def _say_language(persona_voice: str) -> str:
    """Resolve the language the agent's `say` should be written in, from persona_voice.

    The behavior_prompt is English prose, so without an explicit directive the model
    writes `say` in English even for a non-English persona. Map the 'language=' field
    to a clear instruction; default to that persona's natural language verbatim.
    """
    v = persona_voice.lower()
    if "cantonese" in v:
        return "colloquial written Cantonese (粤语)"
    if "iban" in v:
        return "Bahasa Melayu"
    if "bahasa" in v or "melayu" in v:
        return "Bahasa Melayu"
    return "English"


def _handle_pending_upload(page, handled: set, artifact_dir: str | None) -> str | None:
    """Set any not-yet-handled file <input> with the fixture image. Returns a human
    line on success, else None. Keyed by URL+index so each page's upload fires once
    and we never loop forever on a hidden input the LLM can't satisfy."""
    try:
        inputs = page.locator('input[type="file"]')
        n = inputs.count()
    except Exception:
        return None
    for i in range(n):
        key = f"{page.url}#{i}"
        if key in handled:
            continue
        handled.add(key)
        try:
            inputs.nth(i).set_input_files(_upload_fixture_path(artifact_dir))
            page.wait_for_load_state("networkidle", timeout=3000)
            return "Uploaded nexhack_upload.jpg"
        except Exception:
            continue  # not settable (e.g. detached) — move on, key stays marked
    return None


def run_agent(
    page,
    *,
    goal: str,
    hints: dict | None = None,
    success_url: str = "",
    success_element: str = "",
    aria: str = "",
    requires_labels: bool = False,
    behavior_profile: dict | None = None,
    wcag: tuple = (),
    grade: float | None = None,
    word_count: int = 1,
    rng=None,
    artifact_dir: str | None = None,
    current_url: str = "",
    url_visit_counts: dict | None = None,
    step_idx: int = 0,
    persona_voice: str = "",
    on_say=None,
) -> dict:
    """Multi-turn LLM agent with full Playwright `exec` access.

    The LLM writes raw Playwright Python code executed against the live page.
    One `exec` tool replaces all hardcoded action types, locator strategies,
    and per-site patches. Returns accumulated steps/shots/status.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    import pathlib as _pl

    client = _client(settings.llm_model_step)
    if client is None:
        return {
            "steps": [StepSignals(
                step_idx=step_idx, step_key="offline", critical=False,
                dwell_s=0, retries=0, dead_end=True, completed=False,
                llm_confusion=0, reading_grade=grade,
            )],
            "shots": [], "step_idx": step_idx + 1,
            "status": "blocked", "blocked_at": "offline",
            "blocked_url": current_url,
            "current_url": current_url, "url_visit_counts": url_visit_counts or {},
        }

    hints = hints or {}
    url_counts = dict(url_visit_counts or {})
    steps: list = []
    shots: list = []
    idx = step_idx
    max_turns = 20
    stuck_limit = 20

    def _field_values() -> str:
        """List each form field's current value. The a11y tree omits values, so without
        this a weak model re-fills an already-filled field forever (it looks empty)."""
        try:
            vals = page.evaluate(
                "() => Array.from(document.querySelectorAll('input,textarea,select'))"
                ".map(e => ({n: e.labels?.[0]?.innerText || e.getAttribute('aria-label')"
                " || e.name || e.placeholder || e.id || '', v: e.value || ''}))"
                ".filter(f => f.n)"
            )
        except Exception:
            return ""
        if not vals:
            return ""
        lines = [f"  {f['n']}: {f['v'] if f['v'] else '(empty)'}" for f in vals]
        return "\nCurrent field values (do NOT re-fill non-empty ones):\n" + "\n".join(lines)

    def _snap() -> str:
        return (f"Current URL: {page.url}\nAccessibility tree:\n"
                f"{page.locator('body').aria_snapshot()}{_field_values()}")

    snapshot = _snap() if not aria else f"Current URL: {current_url}\nAccessibility tree:\n{aria}{_field_values()}"
    history: list = []
    uploaded: set = set()  # file-input keys already handled (URL#index)
    last_code = ""    # last exec code — detect a model looping the same action
    repeat = 0        # consecutive identical actions

    for turn in range(max_turns):
        current_url = page.url
        url_counts[current_url] = url_counts.get(current_url, 0) + 1
        stuck = url_counts[current_url] >= stuck_limit
        hints_text = ", ".join(f"{k}={v}" for k, v in hints.items()) if hints else "none"

        # Deterministic document upload — the LLM can't author a file, so clear any
        # pending file <input> before it gets stuck, then re-observe and continue.
        up = _handle_pending_upload(page, uploaded, artifact_dir)
        if up:
            upload_say = _upload_say(persona_voice)
            if on_say:
                on_say(upload_say)
            shot = None
            if artifact_dir:
                d = _pl.Path(artifact_dir)
                d.mkdir(parents=True, exist_ok=True)
                shot = str(d / f"step_{idx}.png")
                try:
                    page.screenshot(path=shot)
                except Exception:
                    shot = None
            step = StepSignals(
                step_idx=idx, step_key="upload document", critical=True,
                dwell_s=0, retries=0, dead_end=False, completed=True,
                llm_confusion=0, reading_grade=grade, say=upload_say,
            )
            steps.append(step)
            if shot:
                shots.append(shot)
            idx += 1
            snapshot = f"Result: {up}\n\n{_snap()}"
            continue

        turn_msgs = [SystemMessage(content=_MCP_SYSTEM)]
        for h in history:
            turn_msgs.append(HumanMessage(content=h["user"]))
            if h.get("assistant"):
                turn_msgs.append(SystemMessage(content=h["assistant"]))

        persona_line = (
            f"PERSONA (speak in this voice for 'say'): {persona_voice}\n"
            f"Write the 'say' sentence in {_say_language(persona_voice)}, "
            "first-person, regardless of the language of this instruction.\n"
        ) if persona_voice else ""
        user_msg = (
            persona_line +
            f"GOAL: {goal}\n"
            f"Success URL pattern: {success_url or '(none)'}\n"
            f"Success element: {success_element or '(none — look for matching text in a11y tree)'}\n"
            f"Hint values: {hints_text}\n"
            f"Persona depends on labels: {requires_labels}\n"
            f"Stuck on this page for {url_counts[current_url]} visits (limit {stuck_limit}): {stuck}\n\n"
            f"{snapshot}\n\n"
            "Respond with {\"exec\": \"<code>\"} to run Playwright, or {\"done\": true} / {\"blocked\": true}."
        )
        turn_msgs.append(HumanMessage(content=user_msg))

        try:
            ai = client.invoke(
                turn_msgs,
                config={"response_format": {"type": "json_object"}},
            )
            usage = getattr(ai, "usage_metadata", None) or {}
            prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
            completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
            model_name = getattr(client, "model", getattr(client, "model_name", ""))
            record_usage(model_name or settings.llm_model_step, prompt_tokens, completion_tokens)

            payload = json.loads(_extract_text(ai.content))
        except Exception as exc:
            logger.warning("run_agent: LLM call failed on turn %d: %s", turn, exc)
            step = StepSignals(
                step_idx=idx, step_key="llm_error", critical=False,
                dwell_s=0, retries=0, dead_end=True, completed=False,
                llm_confusion=0, reading_grade=grade,
            )
            steps.append(step)
            return {
                "steps": steps, "shots": shots, "step_idx": idx + 1,
                "status": "blocked", "blocked_at": "llm_error",
                "blocked_url": current_url,
                "current_url": current_url, "url_visit_counts": url_counts,
            }

        step_label = payload.get("step_label", f"turn_{turn}")
        confusion = float(payload.get("confusion", 0))
        say = payload.get("say", "")
        # Emit the persona's line LIVE — run_agent returns all steps at once, so without
        # this the monologue would only surface when the whole persona loop finishes.
        if on_say and say:
            on_say(say)

        # --- done (dual gate: URL or element) -------------------------------
        if payload.get("done"):
            url_ok = not success_url or success_url.lstrip("/") in page.url
            elem_ok = success_element and success_element in page.locator("body").aria_snapshot()
            if not url_ok and not elem_ok:
                gates = []
                if success_url: gates.append(f"URL contains '{success_url}'")
                if success_element: gates.append(f"a11y tree contains '{success_element[:80]}'")
                result_msg = f"WARNING: said 'done' but neither gate passed: {' OR '.join(gates)}. Try again."
                history.append({"user": user_msg, "assistant": json.dumps(payload)})
                history.append({"user": result_msg, "assistant": None})
                snapshot = f"Action rejected — still at: {_snap()}"
                continue

            step = StepSignals(
                step_idx=idx, step_key=step_label, critical=False,
                dwell_s=0, retries=0, dead_end=False, completed=True,
                llm_confusion=confusion, reading_grade=grade, say=say,
            )
            steps.append(step)
            return {
                "steps": steps, "shots": shots, "step_idx": idx + 1,
                "status": "completed", "blocked_at": None, "blocked_url": None,
                "current_url": page.url, "url_visit_counts": url_counts,
            }

        # --- blocked --------------------------------------------------------
        if payload.get("blocked") or stuck:
            # Override: if goal is objectively reached, complete regardless.
            url_ok = success_url and success_url.lstrip("/") in page.url
            elem_ok = success_element and success_element in page.locator("body").aria_snapshot()
            if url_ok or elem_ok:
                step = StepSignals(
                    step_idx=idx, step_key="goal reached", critical=False,
                    dwell_s=0, retries=0, dead_end=False, completed=True,
                    llm_confusion=confusion, reading_grade=grade,
                )
                steps.append(step)
                return {
                    "steps": steps, "shots": shots, "step_idx": idx + 1,
                    "status": "completed", "blocked_at": None, "blocked_url": None,
                    "current_url": page.url, "url_visit_counts": url_counts,
                }
            step = StepSignals(
                step_idx=idx, step_key=step_label, critical=False,
                dwell_s=0, retries=0, dead_end=True, completed=False,
                llm_confusion=confusion, reading_grade=grade, say=say,
            )
            steps.append(step)
            return {
                "steps": steps, "shots": shots, "step_idx": idx + 1,
                "status": "blocked", "blocked_at": step_label,
                "blocked_url": page.url,
                "current_url": page.url, "url_visit_counts": url_counts,
            }

        # --- exec -----------------------------------------------------------
        code = payload.get("exec", "")
        if not code:
            # Empty response — LLM has nothing to do. Auto-check if at goal.
            url_ok = success_url and success_url.lstrip("/") in page.url
            elem_ok = success_element and success_element in page.locator("body").aria_snapshot()
            if url_ok or elem_ok:
                step = StepSignals(
                    step_idx=idx, step_key="goal reached", critical=False,
                    dwell_s=0, retries=0, dead_end=False, completed=True,
                    llm_confusion=0, reading_grade=grade,
                )
                steps.append(step)
                return {
                    "steps": steps, "shots": shots, "step_idx": idx + 1,
                    "status": "completed", "blocked_at": None, "blocked_url": None,
                    "current_url": page.url, "url_visit_counts": url_counts,
                }
            # Not at goal and no action — blocked
            step = StepSignals(
                step_idx=idx, step_key="no_action", critical=False,
                dwell_s=0, retries=0, dead_end=True, completed=False,
                llm_confusion=0, reading_grade=grade,
            )
            steps.append(step)
            return {
                "steps": steps, "shots": shots, "step_idx": idx + 1,
                "status": "blocked", "blocked_at": "no_action",
                "blocked_url": page.url,
                "current_url": page.url, "url_visit_counts": url_counts,
            }
        else:
            result_msg = _play_exec(page, code)
            # Loop-breaker: a weak model re-runs the same action forever because the a11y
            # tree looks unchanged. Escalate the nudge the more it repeats.
            if code.strip() == last_code:
                repeat += 1
                if repeat >= 3:
                    result_msg += (
                        "\n\nSTOP. You have run this SAME action several times with no effect. "
                        "A click that doesn't advance means a REQUIRED FIELD above the button is "
                        "still empty or invalid — read the screen (incl. any on-screen code/hint), "
                        "FILL that field, THEN click. Do something DIFFERENT now."
                    )
                else:
                    result_msg += (
                        "\n\nNOTE: You just ran this EXACT action again and nothing changed — "
                        "it is already done. Do NOT repeat it; fill remaining fields or click the next button."
                    )
            else:
                repeat = 0
            last_code = code.strip()

        # Screenshot
        shot = None
        if artifact_dir:
            d = _pl.Path(artifact_dir)
            d.mkdir(parents=True, exist_ok=True)
            shot = str(d / f"step_{idx}.png")
            try:
                page.screenshot(path=shot)
            except Exception:
                pass

        dead_end = result_msg.startswith("ERROR")
        step = StepSignals(
            step_idx=idx, step_key=step_label, critical=False,
            dwell_s=0, retries=0, dead_end=dead_end, completed=not dead_end,
            llm_confusion=confusion, reading_grade=grade, say=say,
            wcag=wcag if idx == 0 else (),
        )
        steps.append(step)
        if shot:
            shots.append(shot)
        idx += 1

        # Auto-detect success: if the exec brought us to the goal, complete immediately.
        if not dead_end:
            url_ok = success_url and success_url.lstrip("/") in page.url
            elem_ok = success_element and success_element in page.locator("body").aria_snapshot()
            if url_ok or elem_ok:
                return {
                    "steps": steps, "shots": shots, "step_idx": idx,
                    "status": "completed", "blocked_at": None, "blocked_url": None,
                    "current_url": page.url, "url_visit_counts": url_counts,
                }

        # Next turn's snapshot
        snapshot = f"Result: {result_msg}\n\n{_snap()}"

        history.append({"user": user_msg, "assistant": json.dumps(payload)})
        history.append({"user": result_msg, "assistant": None})

    # Max turns exhausted
    step = StepSignals(
        step_idx=idx, step_key="max_turns", critical=False,
        dwell_s=0, retries=0, dead_end=True, completed=False,
        llm_confusion=0, reading_grade=grade,
    )
    steps.append(step)
    return {
        "steps": steps, "shots": shots, "step_idx": idx + 1,
        "status": "blocked", "blocked_at": "max_turns",
        "blocked_url": page.url,
        "current_url": page.url, "url_visit_counts": url_counts,
    }


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

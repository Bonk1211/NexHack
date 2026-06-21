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


class SynthesisResult(BaseModel):
    """Once-per-run reasoning synthesis (OUTPUT-side only, §15)."""
    rollup: str = Field(description="the one business line — who is silently excluded (§18)")
    narrative: str = Field(description="2-3 sentence audit-style summary")
    key_exclusions: list[str] = Field(default_factory=list)


class AgentAction(BaseModel):
    """The planner's chosen next action in autonomous exploration (§8 agent loop)."""
    action: str = Field(description="'click' | 'fill' | 'navigate_back' | 'done' | 'blocked'")
    role: str = Field(default="", description="a11y role to target, e.g. 'button','textbox','combobox','switch'")
    name: str = Field(default="", description="accessible name to match")
    nth: int = Field(default=0, description="0-based index among same-role controls when name is missing/ambiguous")
    value: str = Field(default="", description="text to type ('fill' on textbox) or option label ('fill' on combobox)")
    key: str = Field(default="", description="stable step label, e.g. 'click:Submit'")
    confusion: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")
    say: str = Field(default="", description="ONE short first-person sentence in the persona's voice — what they're thinking/feeling as they take this action. No JSON, no meta.")


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


# --- plan_action (per-step autonomous nav) ----------------------------------

_PLAN_SYSTEM = (
    "You are simulating ONE user persona performing a deep functional test of a mobile "
    "web app. Follow this two-pass strategy:\n\n"
    "PASS 1 — PRIMARY FLOW (walk every screen in sequence):\n"
    "  Fill all required input fields with realistic test data, then click the PRIMARY "
    "  navigation control (the main CTA — 'Continue', 'Next', 'Submit', 'Verify', 'Sign "
    "  Up', 'Pay', 'Confirm', 'Finish', etc.) to advance to the next screen. NEVER click "
    "  shortcuts that skip screens ('Skip for now', 'Skip', 'Skip this step', etc.) on the "
    "  first pass — they bypass intermediate screens that must be tested. Keep advancing "
    "  until you reach the END state: a success / confirmation / completion screen (a "
    "  dashboard, home, feed, account/profile page, or a 'You're in' / 'Welcome' / "
    "  'Success' / 'Thank you' / 'Order placed' / 'Payment successful' / 'Application "
    "  submitted' / rewards / receipt screen with no further required step).\n\n"
    "PASS 2 — SECONDARY EXPLORATION (use navigate_back to revisit each screen):\n"
    "  After reaching the final screen, navigate_back through each screen and test the "
    "  secondary controls you skipped: 'Resend OTP', 'Help', 'Cancel', 'Skip for now', "
    "  toggles, links, carousels, icon buttons. Test them one at a time.\n\n"
    "Given the current a11y tree and actions already taken, choose the SINGLE next action. "
    "Respond ONLY with a JSON object of exactly this shape:\n"
    '{"action":"click|fill|navigate_back|done|blocked","role":"","name":"","nth":0,'
    '"value":"","key":"","confusion":0.0,"reason":"","say":""}.\n'
    "  'fill'  — for a text input (role textbox/searchbox/spinbutton) set value to realistic, "
    "TYPE-APPROPRIATE data: a phone field gets digits, an email field gets name@example.com, "
    "a name field gets a full name, an OTP/code field gets the code shown in any on-screen hint. "
    "Also use 'fill' for a dropdown (role combobox/listbox): set value to one of its option "
    "labels (never leave a select on its placeholder).\n"
    "  'click' — press a button/link, or flip a switch/checkbox/radio.\n"
    "  'navigate_back' — go back one screen to test secondary controls (role/name/value ignored).\n"
    "  'done'  — ONLY after both passes are complete across every screen.\n"
    "  'blocked' — only if completely stuck and navigate_back cannot help.\n"
    "TARGETING: prefer the accessible 'name'. When a control has NO name or shares its name "
    "with others (e.g. several unlabeled dropdowns or switches), set 'nth' to its 0-based "
    "position among controls of the SAME role in tree order (1st=0, 2nd=1, ...).\n"
    "If you clicked the primary CTA but the screen did not change, a required field is "
    "invalid or empty — read the error text and fix that field before retrying.\n"
    "confusion 0.0 = obvious, 1.0 = genuinely unclear. "
    "Set key like 'click:Continue' or 'fill:Mobile Number' (action:Name).\n"
    "Set 'say' to ONE short first-person sentence in THIS persona's voice describing what "
    "you are thinking or feeling as you take this action (doubt, relief, confusion, impatience). "
    "Stay fully in character; never mention being an AI, a test, a persona, a screen-reader, "
    "or an accessibility tree — just a real person using the app."
)

# Parse an aria_snapshot's "- role \"name\"" lines, in stable tree order.
_ARIA_LINE = re.compile(r'^\s*-\s+(?P<role>[a-z]+)(?:\s+"(?P<name>[^"]*)")?', re.MULTILINE)

# Interaction taxonomy — how a human tester drives each control TYPE (validated live
# against BrewPoints): text inputs get typed, native selects get an option chosen,
# toggles get clicked to flip, buttons/links get clicked (and may navigate).
_FILL_ROLES = ("textbox", "searchbox", "spinbutton")          # .fill()
_SELECT_ROLES = ("combobox", "listbox")                       # .select_option()  NOT .fill()
_TOGGLE_ROLES = ("switch", "checkbox", "radio")               # .click() to flip, stays on screen
_BUTTON_ROLES = ("button", "tab", "menuitem")                 # .click(), may advance
_LINK_ROLES = ("link",)                                       # .click(), often secondary/skip
_INTERACTIVE = _FILL_ROLES + _SELECT_ROLES + _TOGGLE_ROLES + _BUTTON_ROLES + _LINK_ROLES

# On-screen hint like "the code is 1234" / "OTP: 482913" — read it like a human would.
_CODE_HINT = re.compile(r'(?:code|otp|pin|password)\D{0,24}(\d{3,8})', re.I)

# Shortcut controls that BYPASS screens — never auto-followed on the forward walk.
_SKIP_TOKENS = ("skip", "maybe later", "not now", "no thanks", "do it later", "remind me later")


def _parse_aria_controls(aria: str) -> list[tuple[str, str, int]]:
    """(role, accessible-name, nth) for each control in tree order.

    `nth` is the 0-based occurrence of that ROLE so far — this is what lets the agent
    target unnamed duplicates (the 3 birthday <select>s, the 4 permission switches) by
    position via Playwright's get_by_role(role).nth(n), exactly as a human disambiguates
    them visually.
    """
    out: list[tuple[str, str, int]] = []
    per_role: dict[str, int] = {}
    for m in _ARIA_LINE.finditer(aria or ""):
        role = m.group("role")
        nth = per_role.get(role, 0)
        per_role[role] = nth + 1
        out.append((role, m.group("name") or "", nth))
    return out


def _verb_for(role: str) -> str:
    """The interaction verb the planner emits for a control role (fill | click)."""
    return "fill" if role in _FILL_ROLES or role in _SELECT_ROLES else "click"


# A screen's IDENTITY skeleton: its interactive controls + headings, ignoring volatile
# value/text nodes. Typing into a field adds a text node and would otherwise change the
# screen hash on every keystroke, resetting per-screen progress — so we key off structure.
_SKELETON_ROLES = frozenset(_INTERACTIVE + ("heading",))


# Digit/number runs in a control NAME are volatile: OTP "Resend in 29s" countdowns,
# cart counts, timers. Left in the skeleton they churn the screen hash every second and
# defeat the cycle guard (the agent thinks each tick is a brand-new screen). Mask them
# for IDENTITY only — targeting still uses the real name.
_VOLATILE_NUM = re.compile(r"\d+")


def _screen_skeleton(aria: str) -> list[tuple[str, str]]:
    """Stable (role, name) skeleton identifying THIS screen (filled values + live counters
    excluded) — see _VOLATILE_NUM for why numbers are masked out of the name."""
    return [(r, _VOLATILE_NUM.sub("#", n))
            for r, n, _ in _parse_aria_controls(aria) if r in _SKELETON_ROLES]


def _action_signature(a: dict) -> str:
    """Stable per-control signature for cycle/dedup: action:role:name:nth (case-insensitive)."""
    return (f"{a.get('action')}:{a.get('role') or ''}:"
            f"{a.get('name') or ''}:{a.get('nth') or 0}").lower()


def _control_signature(role: str, name: str, nth: int) -> str:
    """The signature a control WOULD have once tested (verb derived from its role)."""
    return f"{_verb_for(role)}:{role}:{name}:{nth}".lower()


def _example_from_placeholder(ph: str) -> str:
    """A field's placeholder is the app author's OWN valid example — use it when it is a
    concrete value (email or phone/number with real digits), not a format mask or
    instruction. This is what makes format-strict fields pass (e.g. BrewPoints wants
    '12-345 6789', not '0123456789'). Returns '' when the placeholder is unusable."""
    ph = (ph or "").strip()
    for pre in ("e.g.", "eg.", "ex.", "ex:", "example:", "i.e."):
        if ph.lower().startswith(pre):
            ph = ph[len(pre):].strip()
            break
    if "@" in ph and "." in ph.split("@")[-1]:
        return ph                                       # concrete email example
    if sum(c.isdigit() for c in ph) >= 3 and re.fullmatch(r"[0-9 +()\-]+", ph):
        return ph                                       # concrete phone/number (digits+separators only)
    return ""                                            # mask ("DD/MM/YYYY") or instruction ("Enter code")


# Ordered (keywords -> value) table for realistic test data. FIRST match wins, so more
# specific terms come before generic ones (e.g. "username"/"first name" before "name").
# Extend this list to teach the agent a new field type — that's the whole knob.
_VALUE_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("email", "e-mail", "emel"), "test@example.com"),
    (("cvv", "cvc", "security code", "card verification"), "123"),
    (("card number", "card no", "credit card", "debit card", "pan"), "4111111111111111"),
    (("expiry", "expiration", "exp date", "mm/yy", "valid thru"), "12/30"),
    (("phone", "mobile", "tel", "whatsapp", "contact number", "contact no", "hp"), "0123456789"),
    (("mykad", "nric", "ic number", "no. mykad", "passport", "identity", "national id"), "901234567890"),
    (("confirm password", "retype password", "re-enter password"), "Test1234!"),
    (("password", "passcode", "kata laluan"), "Test1234!"),
    (("username", "user name", "userid", "user id", "login id", "handle"), "testuser"),
    (("first name", "given name", "nama pertama"), "Test"),
    (("last name", "surname", "family name", "nama keluarga"), "User"),
    (("full name", "name", "nama"), "Test User"),
    (("company", "organi", "business name", "employer", "syarikat"), "Test Sdn Bhd"),
    (("occupation", "job title", "profession", "position", "pekerjaan"), "Engineer"),
    (("country", "negara"), "Malaysia"),
    (("state", "negeri", "province"), "Selangor"),
    (("city", "bandar", "town"), "Kuala Lumpur"),
    (("postcode", "postal", "zip", "poskod"), "50000"),
    (("address", "alamat", "street", "jalan"), "123 Jalan Test, Kuala Lumpur"),
    (("gender", "jantina"), "Male"),
    (("age", "umur"), "25"),
    (("date", "birthday", "dob", "tarikh lahir"), "1995-06-15"),
    (("url", "website", "link"), "https://example.com"),
    (("coupon", "promo", "voucher", "referral", "discount code"), "TEST10"),
    (("search", "cari", "find"), "coffee"),
    (("message", "comment", "description", "notes", "feedback", "review", "bio", "about"),
     "This is a test message."),
    (("amount", "quantity", "qty", "price", "salary", "income", "number of"), "10"),
)


# Caller-supplied known values ("hints") matched to a field by accessible name. A hint
# is authoritative test data the run already knows (a fixed staging OTP, a specific phone),
# adapted from main's `hints` design. Synonyms let "phone" match a "Mobile Number" field.
_HINT_SYNS: dict[str, tuple[str, ...]] = {
    "phone": ("phone", "mobile", "tel", "contact number", "contact no", "hp", "telefon"),
    "email": ("email", "e-mail", "emel"),
    "ic": ("ic", "mykad", "nric", "identity", "kad pengenalan", "no. mykad"),
    "name": ("name", "nama"),
    "password": ("password", "passcode", "kata laluan"),
}


def _hint_value(name_lower: str, hints: dict | None) -> str:
    """A hint whose key (or its synonyms) matches the field name, else ''. OTP is excluded —
    it needs per-digit splitting and is sourced inside `_smart_value._otp` instead."""
    if not hints:
        return ""
    for hk, hv in hints.items():
        hkl = str(hk).lower()
        if hkl in ("otp", "code"):
            continue
        if hkl and hkl in name_lower:
            return str(hv)
        if any(s in name_lower for s in _HINT_SYNS.get(hkl, ())):
            return str(hv)
    return ""


def _smart_value(role: str, name: str, aria: str = "", hints: dict | None = None) -> str:
    """Realistic, type-appropriate test data — what a human enters so validation passes.

    Generic across projects: keys off the field's accessible name (and the on-screen OTP
    hint), not any one app's wording. A caller `hints` dict (e.g. {"otp": "123456"}) is
    authoritative when it matches the field. Falls back to a benign alphanumeric string.
    """
    n = (name or "").lower()
    hints = hints or {}

    def _otp() -> str:
        # Code source: an explicit hint, else an on-screen hint, else the test code 1234.
        code = str(hints.get("otp") or hints.get("code") or "")
        if not code:
            hint_m = _CODE_HINT.search(aria or "")
            code = hint_m.group(1) if hint_m else "1234"
        # Per-digit box ("Digit 3") returns JUST that digit (a 1-char field keeps only its
        # first char, so the whole code in every box yields 1111). The index FOLLOWS a box
        # keyword — "6-digit OTP" is a SINGLE field (number precedes "digit") and must not
        # be split, so only match a number that comes after digit/box/char/position.
        bm = re.search(r"(?:digit|box|char(?:acter)?|position|pin)\s*[#:]?\s*(\d+)", n)
        if bm:
            i = int(bm.group(1)) - 1
            if 0 <= i < len(code):
                return code[i]
        return code

    # 1) unambiguous OTP/verification fields.
    if any(k in n for k in ("otp", "verification code", "verify code", "one-time", "digit")):
        return _otp()
    # 1.5) an explicit hint matching this field wins over synthesized data.
    hv = _hint_value(n, hints)
    if hv:
        return hv
    # 2) specific named fields (CVV/coupon/etc. own their "...code" before the bare fallback).
    for keys, val in _VALUE_MAP:
        if any(k in n for k in keys):
            return val
    # 3) a bare "code"/"pin" field left over => treat as OTP-style.
    if re.search(r"\bcode\b", n) or re.search(r"\bpin\b", n):
        return _otp()
    if role == "spinbutton":
        return "10"
    return "Test123"


def _screen_control_status(aria: str, history: list[dict], current_screen_key: str):
    """Split the current screen's controls into (untested, tested) (role, name, nth) lists.

    This is what gives the agent *awareness*: instead of re-deriving "what have I done
    here" from a truncated action log, the planner is handed an explicit per-screen
    checklist of remaining work, scoped to THIS exact screen_key.
    """
    if current_screen_key:
        done = {_action_signature(h) for h in history
                if h.get("screen_key", "") == current_screen_key}
    else:
        done = {_action_signature(h) for h in history}
    untested, tested = [], []
    for role, name, nth in _parse_aria_controls(aria):
        if role not in _INTERACTIVE:
            continue
        bucket = tested if _control_signature(role, name, nth) in done else untested
        bucket.append((role, name, nth))
    return untested, tested


def _offline_say(verb: str, name: str) -> str:
    """A plain first-person line for the offline path (no key) so the monologue is never
    empty. Generic on purpose — persona flavour comes from the LLM path; this just keeps
    the live view human-readable in tests/demos."""
    if verb == "fill":
        return f"Let me type my {name or 'details'} here."
    if verb == "navigate_back":
        return "Nothing left here — let me go back."
    if verb == "done":
        return "Looks like I'm all done."
    return f"I'll tap {name}." if name else "Let me try this."


def _heuristic_explore(aria: str, history: list[dict], rng, *,
                       current_screen_key: str = "") -> AgentAction:
    """Deterministic offline planner (§16/§22) that mirrors a careful human tester:

      1. fill every text input + choose an option in every <select>,
      2. flip every toggle/checkbox/radio (in-place, safe),
      3. click the primary button (the CTA that advances),
      4. only then follow secondary links (Skip/Help),
      5. when the screen is exhausted, navigate back to explore elsewhere, else done.

    Each pass picks the FIRST control of that class not yet tested on THIS screen, using
    type-correct values and nth-based targeting. Fully deterministic (network-free, §22).
    """
    _ = rng  # reserved; offline path is deterministic on the (stable) tree order
    if current_screen_key:
        done = {_action_signature(h) for h in history
                if h.get("screen_key", "") == current_screen_key}
    else:
        done = {_action_signature(h) for h in history}
    controls = _parse_aria_controls(aria)

    def pick(roles, reason):
        for role, name, nth in controls:
            if role not in roles:
                continue
            # Never auto-follow a "Skip" shortcut on the forward walk — it bypasses the
            # very screens we must test (OTP, profile). Backtracking covers other paths.
            if any(t in name.lower() for t in _SKIP_TOKENS):
                continue
            verb = _verb_for(role)
            if f"{verb}:{role}:{name}:{nth}".lower() in done:
                continue
            value = _smart_value(role, name, aria) if (verb == "fill" and role in _FILL_ROLES) else ""
            return AgentAction(action=verb, role=role, name=name, nth=nth, value=value,
                               key=f"{verb}:{name or role}#{nth}", reason=reason,
                               say=_offline_say(verb, name))
        return None

    chosen = (
        pick(_FILL_ROLES + _SELECT_ROLES, "offline: fill/select input")
        or pick(_TOGGLE_ROLES, "offline: toggle control")
        or pick(_BUTTON_ROLES, "offline: primary action / advance")
        or pick(_LINK_ROLES, "offline: secondary link")
    )
    if chosen is not None:
        return chosen
    # Current screen fully exercised — back out to explore other paths, once per screen.
    nav_sig = _action_signature({"action": "navigate_back"})
    if nav_sig not in done and history:
        return AgentAction(action="navigate_back", key="navigate_back",
                           reason="offline: screen exhausted, exploring back",
                           say=_offline_say("navigate_back", ""))
    return AgentAction(action="done", key="done", reason="offline: all reachable screens exhausted",
                       say=_offline_say("done", ""))


def plan_action(aria: str, goal: str, history: list[dict], rng, *,
                current_screen_key: str = "", hints: dict | None = None,
                persona_voice: str = "") -> AgentAction:
    """The `plan` node's work: choose the next action from the live a11y tree (§8).

    Offline (no key) or on any failure, returns the deterministic heuristic explorer so a
    run never depends on the network (§16/§22).
    """
    fallback = _heuristic_explore(aria, history, rng, current_screen_key=current_screen_key)
    client = _client(settings.llm_model_step)
    if client is None or not aria:
        return fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        # Give the agent an explicit per-screen checklist so it KNOWS what is left to
        # test on this screen rather than re-inferring it from a truncated action log.
        untested, tested = _screen_control_status(aria, history, current_screen_key)

        def _fmt(items):
            parts = []
            for r, n, i in items:
                label = f'{r} "{n}"' if n else r
                parts.append(f"{label} (nth={i})" if not n or i > 0 else label)
            return ", ".join(parts)

        untested_str = _fmt(untested) or "(none — screen exhausted)"
        tested_str = _fmt(tested) or "(none yet)"
        # Distinct screens already visited — lets the agent gauge overall progress in PASS 2.
        screens_visited = len({h.get("screen_key", "") for h in history if h.get("screen_key")})

        hints_text = ", ".join(f"{k}={v}" for k, v in (hints or {}).items()) or "(none)"
        persona_line = f"PERSONA (speak in this voice for 'say'): {persona_voice}\n" if persona_voice else ""
        human = HumanMessage(content=(
            persona_line +
            f"GOAL: {goal}\n"
            f"Known values to use when a field matches (USE THESE EXACTLY): {hints_text}\n"
            f"Distinct screens visited so far: {screens_visited}\n"
            f"UNTESTED controls on THIS screen (test these before leaving): {untested_str}\n"
            f"Already-tested controls on THIS screen: {tested_str}\n"
            f"Recent actions (most recent last): {json.dumps(history[-15:])}\n"
            f"Accessibility tree:\n{aria[:4000]}\n"
            "Pick the SINGLE next action. On the forward pass: first fill inputs and toggle "
            "any switches/checkboxes/radios (these stay on the screen), then click the PRIMARY "
            "CTA to advance — never a 'Skip' shortcut. Save ambiguous secondary buttons/links "
            "(Help, Resend, Skip) for the backtrack pass. If this screen has no untested "
            "controls left and you have reached the final screen, navigate_back to test what "
            "you saved. Respond in JSON."
        ))
        ai = client.invoke(
            [SystemMessage(content=_PLAN_SYSTEM), human],
            config={"response_format": {"type": "json_object"}},
        )
        usage = getattr(ai, "usage_metadata", None) or {}
        prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        model_name = getattr(client, "model", getattr(client, "model_name", ""))
        record_usage(model_name or settings.llm_model_step, prompt_tokens, completion_tokens)

        payload = json.loads(_extract_text(ai.content))
        return AgentAction.model_validate(payload)
    except Exception as exc:
        logger.warning("plan_action LLM call failed (%s: %s); using offline explorer",
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

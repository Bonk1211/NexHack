"""Persona navigation subgraph — the cyclic agent loop (§8, §9.1).

This is the part the email-router template does NOT have: the persona agent does
not "classify then route" — it OBSERVES a screen, COMPREHENDS it, DECIDES an
action against the a11y tree + behavior model, ACTS, and REPEATS until blocked or
done. The exit condition is emergent, expressed by `route_next`, not a fixed
pipeline.

Node responsibilities (cognition concentrated in exactly one node):
  observe    — deterministic: capture the trusted signals (axe once on entry,
               a11y tree, reading grade) + the screenshot the persona faces.
  comprehend — THE LLM node: vision confusion judgment (stream B) + nav fallback.
  decide     — deterministic: dwell from the behavior model × seeded RNG, the
               a11y-tree label check, give-up / label-block intent. This is where
               persona behavior becomes real control flow, not prompt flavor (§23).
  act        — deterministic: drive Playwright, screenshot accounting, emit the
               RAW StepSignals (no verdict — §16). A block is a CLEAN exit here,
               never an error to retry away (§23).
  route_next — loop back to observe, or END (blocked | completed).

Navigation method (§8/§25): the a11y tree drives navigation; the vision model is
comprehension judgment + fallback, never the primary driver. Sync Playwright on
purpose; the lifecycle is owned by run_journey / the run-graph persona node, never
inside a node (a node teardown would kill the browser mid-graph). Verified safe
under the run graph's Send fan-out via sync `.invoke` (thread-pool, no asyncio loop).
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import pathlib
import random
import tempfile
from urllib.parse import urlparse

from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

from app.agents.llm import (
    _SELECT_ROLES,
    _action_signature,
    _example_from_placeholder,
    _hint_value,
    _screen_skeleton,
    _smart_value,
    plan_action,
    vision_judge,
)
from app.agents.navigator import (
    FlowStep,
    JourneyResult,
    NavConfig,
    _role_has_name,
)
from app.agents.signals import axe_to_wcag, reading_grade, run_axe
from app.agents.state import PersonaInput, PersonaState
from app.scoring.engine import StepSignals
from app.llm_usage import current_tracker, set_tracker


def _bp(state: PersonaState) -> dict:
    return state.get("behavior_profile", {})


def _goal_reached(state: PersonaState) -> bool:
    """Explicit success signal (adapted from main): the walk is DONE the moment the URL
    ends with `success_url` or the a11y tree contains `success_element` text. Lets a run
    stop cleanly on 'You're in!' / '/rewards' instead of exploring until the step cap."""
    su = (state.get("success_url") or "").strip().rstrip("/")
    if su:
        try:
            if state["page"].url.rstrip("/").endswith(su):
                return True
        except Exception:
            pass
    se = (state.get("success_element") or "").strip().lower()
    return bool(se and se in (state.get("aria", "") or "").lower())


# Generated test files for upload steps, one per kind, made once and reused.
_UPLOAD_CACHE: dict[str, str] = {}


def _test_upload_path(accept: str) -> str:
    """A throwaway test file matching the input's `accept` (image vs pdf), generated once.

    Most upload forms just need *a* valid file of the right type; we draw a plausible
    ID-card-ish image so even a thumbnail preview looks right. PIL writes a real PDF when the
    extension is .pdf, covering document uploads too."""
    kind = "pdf" if "pdf" in (accept or "").lower() else "image"
    if kind in _UPLOAD_CACHE:
        return _UPLOAD_CACHE[kind]
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 400), (210, 225, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, 628, 388], outline=(40, 70, 120), width=4)
    for i, line in enumerate(("TEST DOCUMENT", "Name: Test User", "ID: 123456-01-1234")):
        d.text((40, 70 + i * 48), line, fill=(20, 40, 90))
    ext = "pdf" if kind == "pdf" else "jpg"
    p = str(pathlib.Path(tempfile.gettempdir()) / f"nexhack_upload.{ext}")
    img.save(p)
    _UPLOAD_CACHE[kind] = p
    return p


def _pending_select(page) -> dict | None:
    """First UNSET native <select> on the page as a fill action, else None.

    The LLM planner routinely skips dropdowns (it fills the text fields and jumps to the
    CTA), so a required <select> left on its placeholder silently blocks the form. Like
    uploads, choose for it deterministically: find a select still on its empty/placeholder
    option and pick the first REAL option, targeting by accessible name."""
    try:
        return page.evaluate("""() => {
          const sels = [...document.querySelectorAll('select')];
          for (let i = 0; i < sels.length; i++) {
            const s = sels[i];
            const cur = s.options[s.selectedIndex];
            const unset = !s.value || /^(—|-{1,}|select|choose|please|pilih|sila)/i
              .test((cur && cur.text || '').trim());
            if (!unset) continue;
            // A name from an ADJACENT form control is wrong (it's that control's text, e.g.
            // the previous <select>'s options) — only trust real labels, else fall back to
            // nth targeting (name '').
            const sib = s.previousElementSibling;
            const sibText = sib && !/^(SELECT|INPUT|BUTTON|TEXTAREA)$/.test(sib.tagName)
              ? sib.innerText : '';
            const name = s.getAttribute('aria-label')
              || (s.labels && s.labels[0] && s.labels[0].innerText)
              || (s.id && document.querySelector('label[for="' + s.id + '"]')?.innerText)
              || sibText || '';
            const opt = [...s.options].find((o, idx) => idx > 0 && o.value !== ''
              && !/^(—|-{1,})$/.test(o.text.trim()));
            return {nth: i, name: name.replace(/\\s+/g, ' ').trim().slice(0, 40),
                    value: opt ? opt.text : ''};
          }
          return null;
        }""")
    except Exception:
        return None


def _pending_upload(page) -> dict | None:
    """First UNFILLED <input type=file> on the page as an upload action, else None.

    File inputs are hidden behind styled dropzones, so they never surface in the a11y tree
    the planner sees — uploads would otherwise stall the walk (the CTA stays disabled and
    the dropzone div has no actionable role). Surfacing the input here lets `act` set a file
    on it deterministically. Returns the input's index + accept + a human label."""
    try:
        return page.evaluate("""() => {
          const ins = [...document.querySelectorAll('input[type=file]')];
          for (let i = 0; i < ins.length; i++) {
            if (ins[i].files.length === 0) {
              const raw = ins[i].getAttribute('aria-label')
                || ins[i].closest('label')?.innerText
                || ins[i].parentElement?.innerText || 'file';
              const lbl = raw.replace(/\\s+/g, ' ').trim().slice(0, 40) || 'file';
              return {nth: i, accept: ins[i].accept || '', label: lbl};
            }
          }
          return null;
        }""")
    except Exception:
        return None


def load(state: PersonaState) -> dict:
    """Navigate to the target and initialize the loop (page is already open)."""
    page = state["page"]
    page.goto(state["target_url"], wait_until="load")
    return {
        "step_idx": 0,
        "step_count": 0,
        "status": "running",
        "action_history": [],
        "seen_signatures": [],
        "current_screen_key": "",
    }


def observe(state: PersonaState) -> dict:
    """Capture the trusted signals + the screen the persona faces (deterministic)."""
    page = state["page"]
    idx = state["step_count"]
    out: dict = {}

    aria = page.locator("body").aria_snapshot()
    out["aria"] = aria
    current_url = page.url
    # Screen key = URL + a hash of the STRUCTURAL skeleton (controls + headings), NOT the
    # raw aria. Typing into a field changes the raw aria (the value shows up as a text node)
    # but not the skeleton, so per-screen progress survives fills. Distinct SPA screens that
    # share a URL still differ (different controls/headings => different key).
    skeleton = _screen_skeleton(aria)
    skel_hash = hashlib.md5(repr(skeleton).encode()).hexdigest()[:8]
    current_screen_key = f"{current_url}#{skel_hash}"
    out["current_screen_key"] = current_screen_key

    screen_changed = current_screen_key != state.get("last_url", "")
    if idx == 0 or screen_changed:
        # TRUSTED stream — page-level axe, persona-independent; re-run on every new screen (§16).
        out["wcag"] = axe_to_wcag(run_axe(page))
        body_text = page.inner_text("body")
        out["grade"] = reading_grade(body_text)
        out["word_count"] = max(len(body_text.split()), 1)
    # last_url now stores the last SCREEN KEY axe ran on (re-run when the screen changes).
    out["last_url"] = current_screen_key

    # Screenshot EVERY step (FR-1.3) — the screen comprehend judges + empathy replay.
    shot = None
    if state.get("artifact_dir"):
        d = pathlib.Path(state["artifact_dir"])
        d.mkdir(parents=True, exist_ok=True)
        shot = str(d / f"step_{idx}.png")
        page.screenshot(path=shot)
    out["current_shot"] = shot
    return out


def plan(state: PersonaState) -> dict:
    """Choose the next action for this screen (the one cognition node, §15).

    Dual-mode:
      - SCRIPTED  (`flow` non-empty): replay the next FlowStep, judging confusion with
        `vision_judge` — the original contract, kept for deterministic tests (§22).
      - AUTONOMOUS (`flow` empty): the agent picks the next action from the live a11y
        tree + history + goal via `plan_action`, exploring the app on its own (§8).
    """
    flow = state.get("flow") or []
    if flow:
        if state["step_count"] >= len(flow):
            return {"current_action": {"action": "done", "key": "done"}, "last_confusion": 0.0,
                    "current_labeled": True}
        fs: FlowStep = flow[state["step_count"]]
        labeled = _role_has_name(state.get("aria", ""), fs.role) if fs.role else True
        j = vision_judge(
            state.get("current_shot"),
            fs.key,
            state.get("aria", ""),
            requires_labels=state.get("requires_labels", False),
            labeled=labeled,
            action=fs.action,
        )
        action = {"action": fs.action, "role": fs.role, "name": fs.name, "value": fs.value,
                  "key": fs.key, "critical": fs.critical}
        return {"current_action": action, "last_confusion": j.confusion,
                "last_fallback": j.fallback_target, "last_reason": j.reason,
                "current_labeled": labeled}

    # AUTONOMOUS
    # Explicit success signal reached => stop cleanly, no further exploration.
    if _goal_reached(state):
        return {"current_action": {"action": "done", "key": "done"}, "last_confusion": 0.0,
                "last_fallback": None, "last_reason": "goal reached", "current_labeled": True}

    # An unfilled file input on this screen is handled deterministically (the planner can't
    # see hidden inputs) and BEFORE the CTA, which is usually gated on the upload.
    pend = _pending_upload(state["page"])
    if pend is not None:
        label = pend.get("label") or "file"
        action = {"action": "upload", "role": "", "name": label, "nth": pend.get("nth", 0),
                  "value": pend.get("accept", ""), "key": f"upload:{label}",
                  "critical": True, "reason": "upload required document"}
        return {"current_action": action, "last_confusion": 0.0,
                "last_fallback": None, "last_reason": "upload", "current_labeled": True}

    # An unset <select> is chosen deterministically too — the LLM tends to skip dropdowns.
    psel = _pending_select(state["page"])
    if psel is not None:
        name = psel.get("name") or ""        # '' => act targets by nth (unnamed selects)
        action = {"action": "fill", "role": "combobox", "name": name, "nth": psel.get("nth", 0),
                  "value": psel.get("value", ""), "key": f"fill:{name or 'dropdown'}",
                  "critical": True, "reason": "choose dropdown option"}
        return {"current_action": action, "last_confusion": 0.0,
                "last_fallback": None, "last_reason": "select", "current_labeled": True}

    a = plan_action(state.get("aria", ""), state.get("goal", ""),
                    state.get("action_history", []), state["rng"],
                    current_screen_key=state.get("current_screen_key", ""),
                    hints=state.get("hints", {}))
    labeled = _role_has_name(state.get("aria", ""), a.role) if a.role else True
    action = a.model_dump()
    action["critical"] = True  # autonomously-discovered steps are treated as critical (§12)
    return {"current_action": action, "last_confusion": a.confusion,
            "last_fallback": None, "last_reason": a.reason, "current_labeled": labeled}


def decide(state: PersonaState) -> dict:
    """Apply the persona behavior model to produce real control flow (§23).

    Dwell is reading-load × persona pace × seeded hesitation; the give-up threshold,
    the label dependency, the step cap and a cycle check decide whether the step blocks
    BEFORE we even act. Same screen, different persona => different decision.
    """
    bp = _bp(state)
    rng: random.Random = state["rng"]
    act_chosen = state.get("current_action", {})

    wpm = float(bp.get("reading_speed_wpm", 200))
    dwell_mult = float(bp.get("dwell_multiplier", 1.0))
    hesitation_prob = float(bp.get("hesitation_prob", 0.0))
    giveup_s = float(bp.get("giveup_threshold_s", 60))
    word_count = float(state.get("word_count", 1))

    dwell = (word_count / wpm) * 60.0 * dwell_mult
    if rng.random() < hesitation_prob:
        dwell *= 1.5

    labeled = state.get("current_labeled", True)
    # Persona depends on labels/SR semantics and the field is unlabeled => label-block.
    label_block = (
        act_chosen.get("action") == "fill"
        and state.get("requires_labels", False)
        and not labeled
    )
    dwell_giveup = dwell >= giveup_s

    # SCRIPTED mode: a dwell give-up is a clean terminal exit (§23, contract-preserved).
    # AUTONOMOUS mode: blocks are NOTED but exploration continues — so dwell/label/cycle are
    # findings (not terminal), and only the step cap terminates the walk. Cycle = this exact
    # action was already tried on THIS screen (loop guard); navigate_back is never a cycle.
    is_autonomous = not bool(state.get("flow"))
    cycle = over_cap = False
    if is_autonomous:
        sig = f"{state.get('current_screen_key', '')}:{_action_signature(act_chosen)}"
        cycle = (act_chosen.get("action") in ("fill", "click", "upload")
                 and sig in state.get("seen_signatures", []))
        over_cap = state["step_count"] >= int(state.get("max_steps", 50))
    retries = 1 if rng.random() < hesitation_prob else 0

    return {
        "current_dwell": round(dwell, 2),
        "current_retries": retries,
        "current_label_block": label_block,
        "current_give_up": (dwell_giveup and not is_autonomous),  # scripted terminal only
        "current_dwell_giveup": (dwell_giveup and is_autonomous),  # autonomous finding
        "current_cycle": cycle,
        "current_over_cap": over_cap,
    }


def _settle(page) -> None:
    """Wait for the result of an interaction to settle — including SPA client-side routes.

    A Next.js/SPA route is a pushState with NO 'load' event, so waiting only for 'load'
    returns instantly and the next observe captures the OLD screen (the agent then thinks
    the CTA did nothing). 'networkidle' waits for the route's data fetch to finish; for a
    no-nav click (toggle) it's already idle and returns fast."""
    for st in ("load", "networkidle"):
        try:
            page.wait_for_load_state(st, timeout=4000)
        except PWTimeout:
            pass


def _click_and_settle(page, locator) -> None:
    """Click a control and wait for the screen to settle, recovering from no-op clicks.

    A Playwright click dispatches mouse events at the control's coordinates and relies on
    the browser default action. On real React/Next apps that can leave the screen unchanged:
      - a type=submit button whose navigation lives in the form's onSubmit either never
        fires its submit (synthetic event swallowed by an overlay) OR fires it but the
        client-side router push hasn't applied yet, because `wait_for_load_state` returns
        instantly for an already-idle pushState route — the URL updates a beat LATER.
    A human still gets through, so this is a tooling artifact, not a UX finding. When the
    screen is UNCHANGED (URL + a11y identical) after the click, submit the enclosing form
    directly via requestSubmit (fires onSubmit + validation; a DOM click for non-form
    controls) and give the SPA route real wall-clock time to commit. A genuinely dead
    control changes nothing either way and is reported as such."""
    before_url = page.url
    before_aria = page.locator("body").aria_snapshot()
    locator.click(timeout=3000)
    _settle(page)
    if page.url == before_url and page.locator("body").aria_snapshot() == before_aria:
        for _ in range(2):
            try:
                locator.evaluate("""el => {
                  const form = el.closest('form');
                  if (form && form.requestSubmit) form.requestSubmit(el); else el.click();
                }""")
            except Exception:  # noqa: BLE001 — recovery only; a real dead control stays put
                break
            page.wait_for_timeout(400)  # let an SPA router push apply before re-checking
            _settle(page)
            if page.url != before_url:
                break


def _select_option(page, locator, value: str) -> None:
    """Choose an option in a native <select>, like a human picking from a dropdown.

    Prefer the planner's value (by visible label, then by value); otherwise pick the
    first real (non-placeholder) option. Placeholders are usually index 0, so index 1 is
    a safe realistic choice across forms (year/month/day, outlet pickers, etc.)."""
    value = (value or "").strip()
    if value and value not in ("000000",):
        try:
            locator.select_option(label=value, timeout=3000)
            return
        except Exception:
            try:
                locator.select_option(value=value, timeout=3000)
                return
            except Exception:
                pass  # fall through to first-real-option
    locator.select_option(index=1, timeout=3000)


# Accessible names that denote an in-app "go back" control, in priority order.
_BACK_NAMES = ("back", "previous", "prev", "go back", "return", "←", "<")


def _origin(url: str) -> tuple[str, str]:
    p = urlparse(url)
    return (p.scheme, p.netloc)


def _go_back(page, aria: str) -> bool:
    """Return to the previous screen, SPA-aware.

    SPA wizards (BrewPoints etc.) mutate JS state on 'Continue' and push NO browser
    history entry, so `page.go_back()` is a no-op there. So we FIRST look for an in-app
    back control (a button/link named Back/Previous/<) in the current a11y tree and click
    it; only if none exists do we fall back to browser history. Returns True on success."""
    pre_url = page.url
    pre_aria = aria
    for token in _BACK_NAMES:
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=token, exact=False)
                if loc.count() > 0:
                    _click_and_settle(page, loc.first)
                    # Confirm the screen actually changed (URL or a11y content).
                    if page.url != pre_url or page.locator("body").aria_snapshot() != pre_aria:
                        return True
            except Exception:
                continue
    # No usable in-app back control — try the browser as a last resort (MPA case).
    try:
        page.go_back(wait_until="load", timeout=5000)
    except Exception:
        return False
    # ponytail: back must STAY in the app. Landing on about:blank / a new origin is the
    # "white screen" bug — undo it and report no path back.
    if page.url == pre_url or _origin(page.url) != _origin(pre_url):
        try:
            page.go_forward(wait_until="load", timeout=5000)
        except Exception:
            pass
        return False
    return True


def act(state: PersonaState) -> dict:
    """Drive Playwright, emit RAW StepSignals, advance the cursor.

    Two block disciplines:
      - SCRIPTED (§23): a block is a CLEAN terminal exit — dead_end/completed=False,
        the loop stops there. Contract-preserved.
      - AUTONOMOUS: a block is RECORDED as a finding (dead_end=True on that step) but the
        agent KEEPS EXPLORING — it even performs the action best-effort so downstream
        screens stay reachable, then moves on to the rest of the app. The walk ends only
        when the planner says done, the step budget is exhausted, or there is no way back.
    """
    page = state["page"]
    idx = state["step_count"]
    act_chosen = state.get("current_action", {})
    action = act_chosen.get("action")
    is_autonomous = not bool(state.get("flow"))

    # The planner signalled the goal is reached — clean completion, no extra step row.
    if action == "done":
        return {"step_count": idx, "status": "completed", "blocked_at": None}

    # AUTONOMOUS exploration budget exhausted — stop cleanly (we mapped as much as allowed).
    if is_autonomous and state.get("current_over_cap"):
        return {"step_count": idx, "status": "completed", "blocked_at": state.get("blocked_at")}

    dwell = state.get("current_dwell", 0.0)
    retries = state.get("current_retries", 0)
    confusion = state.get("last_confusion", 0.0)
    role = act_chosen.get("role", "")
    name = act_chosen.get("name", "")
    nth = int(act_chosen.get("nth", 0) or 0)
    label_block = bool(state.get("current_label_block"))

    # Target by accessible NAME when present (robust, unique); otherwise by ROLE + position
    # so unnamed duplicates (birthday <select>s, permission switches) are reachable.
    def _target():
        if name:
            return page.get_by_role(role, name=name).first
        return page.get_by_role(role).nth(nth)

    # AUTONOMOUS: a repeat on this screen means it's exhausted but the planner looped —
    # back out to keep exploring instead of redoing the action. No way back => walk is done.
    effective = action
    if is_autonomous and state.get("current_cycle"):
        effective = "navigate_back"

    barrier = False     # a recorded finding (does NOT stop the autonomous walk)
    terminate = False   # the autonomous walk has nowhere left to go

    # SCRIPTED legacy: a label-blocked fill / explicit block does NOT perform — clean exit.
    if not is_autonomous and (label_block or effective == "blocked"):
        barrier = True
    elif effective == "blocked":
        barrier = True   # autonomous: planner is stuck here; note it and move on
    elif effective == "navigate_back":
        if not _go_back(page, state.get("aria", "")):
            if is_autonomous:
                terminate = True   # exhausted + cannot go back => end the walk
            else:
                barrier = True
    elif effective == "upload":
        # A file input is hidden behind a styled dropzone, so it never appears in the a11y
        # tree and can't be .fill()ed. Set a generated test file on the input directly —
        # Playwright forces hidden inputs and fires the change event, so the app's upload
        # handler runs exactly as if the user had picked a file (no native dialog needed).
        try:
            page.locator("input[type=file]").nth(nth).set_input_files(
                _test_upload_path(act_chosen.get("value", "")), timeout=5000)
            _settle(page)
        except Exception:
            barrier = True
    elif effective in ("fill", "click"):
        try:
            if effective == "fill" and role in _SELECT_ROLES:
                # Native <select>: choose an option (NOT .fill() — that throws on a select).
                _select_option(page, _target(), act_chosen.get("value", ""))
            elif effective == "fill":
                tgt = _target()
                # The field's own placeholder (when concrete) is the authoritative valid
                # format; else the planner's value; else synthesized type-correct data.
                try:
                    ph = tgt.get_attribute("placeholder", timeout=1000) or ""
                except Exception:
                    ph = ""
                # A caller hint that matches this field wins outright (it's the known-good
                # value); else the placeholder's concrete format; else planner/synthesized.
                hints = state.get("hints", {})
                value = (_hint_value((name or "").lower(), hints)
                         or _example_from_placeholder(ph) or act_chosen.get("value", "")
                         or _smart_value(role, name, state.get("aria", ""), hints))
                # Type real keystrokes, NOT .fill(). React controlled inputs (Next.js apps
                # like BrewPoints) only commit to component state on per-key input events;
                # .fill() sets the DOM value + one synthetic event that React may drop, so
                # the value shows on screen but the CTA's state-based validation sees empty
                # and the primary button becomes a silent no-op. press_sequentially drives
                # the real onChange path. Clear first so a retry doesn't append.
                tgt.click(timeout=3000)
                tgt.fill("", timeout=3000)
                tgt.press_sequentially(value, delay=25, timeout=5000)
            else:  # click: button, link, or toggle (switch/checkbox/radio)
                _click_and_settle(page, _target())
        except Exception:
            # a11y locate / interaction failure => record a finding (autonomous keeps going).
            barrier = True

    # Persona-level barriers are FINDINGS. In autonomous mode we performed the action above
    # (best-effort) and merely flag it; in scripted mode they are terminal.
    if label_block:
        barrier = True
    if state.get("current_give_up"):        # scripted-only terminal dwell give-up
        barrier = True
    if is_autonomous and state.get("current_dwell_giveup"):
        barrier = True                       # noted, but exploration continues

    if terminate:
        # Record the terminal step as completed-walk (nothing actionable remained).
        return {"step_count": idx, "status": "completed", "blocked_at": state.get("blocked_at")}

    dead_end = barrier
    completed = not barrier

    # SCRIPTED: keep the FlowStep's key (contract — the matrix columns are the fixed flow).
    # AUTONOMOUS: derive a CANONICAL key from the action's identity, NOT the planner's
    # freeform `key`. Different personas (and the LLM run-to-run) label the same step
    # differently ("click:Continue" vs "click:Continue button"), which would scatter the
    # friction matrix into one column per label and show "NA" everywhere the labels didn't
    # happen to match. Keying on action+name (or action+role#nth for unnamed controls) makes
    # the same logical step collapse to ONE column across every persona.
    if is_autonomous:
        _nm = (act_chosen.get("name") or "").strip()
        _role = act_chosen.get("role") or "control"
        key = f"{action}:{_nm}" if _nm else f"{action}:{_role}#{int(act_chosen.get('nth', 0) or 0)}"
    else:
        key = act_chosen.get("key") or f"step{idx}"
    step = StepSignals(
        step_idx=idx,
        step_key=key,
        critical=bool(act_chosen.get("critical", True)),
        wcag=state.get("wcag", ()) if idx == 0 else (),
        dwell_s=dwell,
        retries=retries,
        dead_end=dead_end,
        completed=completed,
        llm_confusion=confusion,
        reading_grade=state.get("grade"),
    )

    # SCRIPTED: a block stops the loop. AUTONOMOUS: keep exploring regardless — the block is
    # already recorded on the step above; termination is handled via done / cap / no-way-back.
    if is_autonomous:
        status = "running"
    else:
        status = "blocked" if dead_end else "running"
    blocked_at = key if dead_end else state.get("blocked_at")

    screen_key = state.get("current_screen_key", "")
    hist_entry = {"screen_key": screen_key, "key": key,
                  **{k: act_chosen.get(k) for k in ("action", "role", "name", "nth", "reason")}}
    screen_sig = f"{screen_key}:{_action_signature(act_chosen)}"
    return {
        "steps": [step],
        "shots": [state.get("current_shot")],
        "step_count": idx + 1,
        "status": status,
        "blocked_at": blocked_at,
        "action_history": state.get("action_history", []) + [hist_entry],
        "seen_signatures": state.get("seen_signatures", []) + [screen_sig],
    }


def route_next(state: PersonaState) -> str:
    """Emergent exit: loop while running, else END (blocked | completed)."""
    return "observe" if state.get("status") == "running" else END


def build_persona_graph():
    """Compile the cyclic persona subgraph."""
    g = StateGraph(PersonaState)
    g.add_node("load", load)
    g.add_node("observe", observe, retry_policy=RetryPolicy(max_attempts=3))  # transient capture only
    g.add_node("plan", plan)
    g.add_node("decide", decide)
    g.add_node("act", act, retry_policy=RetryPolicy(max_attempts=3))          # transient PW only
    g.set_entry_point("load")
    g.add_edge("load", "observe")
    g.add_edge("observe", "plan")
    g.add_edge("plan", "decide")
    g.add_edge("decide", "act")
    g.add_conditional_edges("act", route_next, {"observe": "observe", END: END})
    return g.compile()


# Compile once; the graph is stateless and reusable across personas.
_PERSONA_GRAPH = build_persona_graph()


def _recursion_config(payload: PersonaInput) -> dict:
    """LangGraph counts SUPERSTEPS, not actions; one action = observe+plan+decide+act
    (4) plus the load+observe startup. The default cap of 25 kills an autonomous walk
    after ~5 actions. Budget 4 supersteps per allowed step plus headroom."""
    max_steps = int(payload.get("max_steps", 20) or 20)
    return {"recursion_limit": 4 * (max_steps + 2) + 10}


def _run_persona_sync(payload: PersonaInput) -> PersonaState:
    """Open a browser, seed the RNG, invoke the subgraph, return the FINAL state.

    Owns the Playwright lifecycle around `.invoke` so the browser survives the
    whole graph (never torn down inside a node) and so the live `page`/`rng` never
    leave this in-process invoke (they are not checkpoint-serializable).
    """
    p = sync_playwright().start()
    browser = p.chromium.launch()
    try:
        page = browser.new_page(**p.devices[payload.get("viewport", "iPhone 13")])
        # Safety net: if any click opens a native file chooser (instead of a hidden input we
        # set directly), answer it with the test file so the run never hangs on the dialog.
        page.on("filechooser", lambda fc: fc.set_files(_test_upload_path(""))
                if not fc.is_multiple() else fc.set_files([_test_upload_path("")]))
        state: PersonaState = {
            **payload,
            "page": page,
            "rng": random.Random(payload["seed"]),
            "step_idx": 0,
            "steps": [],
            "shots": [],
            "status": "running",
        }
        return _PERSONA_GRAPH.invoke(state, config=_recursion_config(payload))
    finally:
        browser.close()
        p.stop()


def stream_persona(payload: PersonaInput, on_frame=None):
    """Yield (node_name, update) for each subgraph step as it runs — LIVE.

    The streaming counterpart of `run_persona`: instead of one `.invoke`, it drives
    the subgraph with `.stream(stream_mode="updates")` so the caller can surface each
    node (observe→comprehend→decide→act) the moment it completes — the agent visibly
    testing the target app step by step. Owns the Playwright lifecycle around the
    stream so the browser survives the whole graph.

    If `on_frame` is given, a Chrome DevTools screencast is attached and `on_frame`
    is called with each base64 JPEG frame of the live page — so the caller can render
    the actual browser the agent drives (the external app) inside the dashboard.
    Frame events fire during Playwright calls (sync API pumps them), so the callback
    runs on THIS thread; keep it non-blocking (e.g. a bounded queue put).

    MUST be called from a thread WITHOUT a running asyncio loop (sync Playwright) —
    e.g. a Starlette threadpool worker (a sync generator endpoint qualifies).
    """
    p = sync_playwright().start()
    browser = p.chromium.launch()
    cdp = None
    try:
        page = browser.new_page(**p.devices[payload.get("viewport", "iPhone 13")])

        if on_frame is not None:
            cdp = page.context.new_cdp_session(page)

            def _frame(f):
                try:
                    on_frame(f["data"])  # base64 JPEG
                    cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]})
                except Exception:  # noqa: BLE001 — never let screencast break the run
                    pass

            cdp.on("Page.screencastFrame", _frame)
            cdp.send("Page.startScreencast", {
                "format": "jpeg", "quality": 50, "maxWidth": 420, "maxHeight": 900,
                "everyNthFrame": 1,
            })

        state: PersonaState = {
            **payload,
            "page": page,
            "rng": random.Random(payload["seed"]),
            "step_idx": 0,
            "steps": [],
            "shots": [],
            "status": "running",
        }
        for update in _PERSONA_GRAPH.stream(state, stream_mode="updates",
                                             config=_recursion_config(payload)):
            for node, data in update.items():
                yield node, data
    finally:
        if cdp is not None:
            try:
                cdp.send("Page.stopScreencast")
            except Exception:  # noqa: BLE001
                pass
        browser.close()
        p.stop()


def run_persona(payload: PersonaInput) -> PersonaState:
    """Run one persona's subgraph in a DEDICATED thread, returning the final state.

    The fresh thread does double duty:
      1. Severs the parent run graph's ambient RunnableConfig (a contextvar) — LangGraph
         otherwise propagates the parent's checkpointer into this nested invoke and tries
         to persist the subgraph's live `page` channel (not msgpack-serializable).
      2. Keeps sync Playwright off any asyncio loop, so it works under Send fan-out.
    """
    tracker = current_tracker()

    def _wrapped(p: PersonaInput):
        if tracker is not None:
            set_tracker(tracker)
        try:
            return _run_persona_sync(p)
        finally:
            if tracker is not None:
                set_tracker(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_wrapped, payload).result()


def run_journey(cfg: NavConfig) -> JourneyResult:
    """Drive one persona through the flow via the subgraph; return signals + shots."""
    final = run_persona({
        "persona": "",
        "persona_idx": 0,
        "behavior_profile": cfg.behavior_profile,
        "requires_labels": cfg.requires_labels,
        "target_url": cfg.target_url,
        "flow": cfg.flow,
        "goal": cfg.goal,
        "max_steps": cfg.max_steps,
        "hints": cfg.hints,
        "success_url": cfg.success_url,
        "success_element": cfg.success_element,
        "viewport": cfg.viewport,
        "seed": cfg.seed,
        "artifact_dir": cfg.artifact_dir,
    })
    return JourneyResult(final["steps"], final["shots"])

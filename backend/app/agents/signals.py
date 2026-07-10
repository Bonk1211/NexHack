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

from app.scoring.engine import WcagNode, WcagSignal

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


def _nodes_from(item: dict) -> tuple[WcagNode, ...]:
    """Extract the offending elements axe already found for a violation — the
    'which element caused this' detail that used to get thrown away entirely."""
    out = []
    for n in item.get("nodes", []):
        target = n.get("target") or []
        out.append(WcagNode(
            target=", ".join(t for t in target if isinstance(t, str)),
            html=(n.get("html") or "")[:300],
            failure_summary=(n.get("failureSummary") or "").strip(),
        ))
    return tuple(out)


def axe_to_wcag(axe_response: dict) -> tuple[WcagSignal, ...]:
    """Translate axe passes/violations into per-criterion WcagSignals (TRUSTED).

    A criterion seen only in `passes` is a pass; any violation flips it to fail.
    Carries through axe's own rule description/help link and per-node detail
    (selector, HTML snippet, failure summary) — without this, a "fail" on
    criterion 1.4.3 is unactionable: nobody can tell what a contrast SC number
    means or which element on the page violated it.
    """
    by_crit: dict[str, dict] = {}

    for item in axe_response.get("passes", []):
        for tag in item.get("tags", []):
            crit = _tag_to_criterion(tag)
            if crit and crit not in by_crit:
                by_crit[crit] = {
                    "passed": True, "rule_id": item.get("id", ""),
                    "description": item.get("description", ""),
                    "help_url": item.get("helpUrl", ""), "nodes": (),
                }

    for item in axe_response.get("violations", []):
        for tag in item.get("tags", []):
            crit = _tag_to_criterion(tag)
            if not crit:
                continue
            nodes = _nodes_from(item)
            existing = by_crit.get(crit)
            if existing and not existing["passed"]:
                # A second rule can fail under the same SC — keep every offending
                # element, not just the first rule's.
                existing["nodes"] = existing["nodes"] + nodes
            else:
                by_crit[crit] = {
                    "passed": False, "rule_id": item.get("id", ""),
                    "description": item.get("description", ""),
                    "help_url": item.get("helpUrl", ""), "nodes": nodes,
                }

    return tuple(
        WcagSignal(
            criterion=c, passed=d["passed"], rule_id=d["rule_id"],
            description=d["description"], help_url=d["help_url"], nodes=d["nodes"],
        )
        for c, d in sorted(by_crit.items())
    )


def _syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


# A "real" sentence boundary: punctuation followed by a new capitalized
# sentence, or the end of the text. Excludes abbreviation periods like "e.g."
# (followed by a digit/lowercase letter, not a capitalized word) from being
# miscounted as sentence breaks.
_SENTENCE_END_RE = re.compile(r"[.!?]+(?=\s+[A-Z]|\s*$)")

_PARAGRAPH_RE = re.compile(r"paragraph:\s*(.+)")


def paragraph_text(aria: str) -> str:
    """Extract just the paragraph-role text from an a11y snapshot — the actual
    body copy a screen-reader user would have read out as prose, not the
    labels/buttons/nav/footer chrome that happens to share the page. Even a
    field's format hint ("e.g. 123456-01-1234") is short and caption-like, not
    prose — reading_grade()'s own length/sentence-boundary checks filter that
    out; this only narrows the INPUT to text meant to be read, not clicked."""
    return " ".join(m.group(1).strip() for m in _PARAGRAPH_RE.finditer(aria or ""))

_MALAY_MARKERS = {
    "yang", "dan", "untuk", "dengan", "anda", "ini", "itu", "akan", "atau",
    "tidak", "adalah", "pada", "dari", "ke", "sila", "kemudian", "boleh",
    "seperti", "sudah", "belum", "juga", "kami", "kita", "saya", "mereka",
}


def _looks_non_english(text: str) -> bool:
    """Cheap language guard. The Flesch-Kincaid syllable heuristic below is
    English-only — Malay's prefix/suffix morphology (me-, pen-, -kan) reads as
    long, complex words to a vowel-group syllable counter and inflates grade
    level into nonsense (verified: an equivalent Malay/English sentence pair
    scored 18.3 vs 7.0 — same meaning, wildly different "grade"). Returns True
    when the formula can't be trusted for this text, so the caller reports no
    grade instead of a fabricated one."""
    non_latin = sum(1 for ch in text if ord(ch) > 0x2FF and not ch.isspace())
    if text and non_latin > len(text) * 0.15:
        return True  # CJK / Tamil / Arabic / etc. — not even Latin script
    words = re.findall(r"[A-Za-z]+", text.lower())
    if not words:
        return False
    malay_hits = sum(1 for w in words if w in _MALAY_MARKERS)
    return malay_hits / len(words) > 0.08


def reading_grade(text: str) -> float | None:
    """Rough Flesch-Kincaid grade level of on-screen copy (low-literacy lens,
    §11). English-only formula — returns None (not a fabricated number) when
    the text doesn't look like English. A wrong grade is worse than no grade:
    it would silently fail every step of a translated page regardless of
    actual complexity, which is not a friction signal, it's a broken metric."""
    if _looks_non_english(text):
        return None
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 10:
        return None  # too little text to say anything meaningful
    sentence_ends = len(_SENTENCE_END_RE.findall(text.strip()))
    if sentence_ends == 0:
        # No genuine sentence boundary found — this is UI labels/buttons/nav
        # dumped into one string, not prose. The old `max(count, 1)` floor
        # treated a whole page of short labels as ONE giant sentence, which
        # explodes the words-per-sentence term into a nonsense grade (verified:
        # a real MyRakyat form screen — mostly field labels, one stray "e.g."
        # abbreviation period — scored 15.2 despite being simple English UI
        # copy). Flesch-Kincaid needs real sentence structure to mean anything.
        return None
    syllables = sum(_syllables(w) for w in words)
    w = len(words)
    grade = 0.39 * (w / sentence_ends) + 11.8 * (syllables / w) - 15.59
    return round(max(grade, 0.0), 1)

"""Autonomous-exploration contract tests (§8, §22).

The persona agent drives the app on its own — no scripted `flow`, just a goal — and
must explore beyond the first control, terminate within the safety cap, and screenshot
every step. Pinned to the DETERMINISTIC offline planner (`_heuristic_explore`) by
clearing the LLM key, so the run is network-free and reproducible regardless of the
local environment's `.env`.
"""
from __future__ import annotations

import pathlib
import random

import pytest

from app.agents import llm
from app.agents.llm import (
    AgentAction,
    _example_from_placeholder,
    _heuristic_explore,
    _parse_aria_controls,
    _screen_control_status,
    _smart_value,
)
from app.agents.navigator import NavConfig, run_journey
from app.config import settings

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLAWED = (ROOT / "fixture-site" / "index.html").as_uri()
WIZARD = (ROOT / "fixture-site" / "wizard.html").as_uri()

BP = {"dwell_multiplier": 1.0, "reading_speed_wpm": 220, "hesitation_prob": 0.0,
      "giveup_threshold_s": 60}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Force the deterministic offline planner — tests never hit the network (§22)."""
    monkeypatch.setattr(settings, "llm_api_key", "", raising=False)


# --- pure unit tests: the offline planner -----------------------------------

def test_parse_aria_controls():
    assert _parse_aria_controls('- textbox\n- button "Submit"') == [
        ("textbox", "", 0), ("button", "Submit", 0)]
    assert _parse_aria_controls("") == []


def test_parse_aria_controls_indexes_duplicates():
    # 3 unnamed comboboxes (birthday Y/M/D) must get distinct nth so each is targetable.
    aria = '- combobox "Outlet"\n- combobox\n- combobox\n- combobox'
    assert _parse_aria_controls(aria) == [
        ("combobox", "Outlet", 0), ("combobox", "", 1),
        ("combobox", "", 2), ("combobox", "", 3)]


def test_smart_value_is_type_appropriate():
    assert _smart_value("textbox", "Email") == "test@example.com"
    assert _smart_value("textbox", "Mobile Number").isdigit()
    assert _smart_value("textbox", "Full Name") == "Test User"
    # OTP digit box reads the on-screen hint and returns the right single digit.
    aria = '- paragraph "Hint: the code is 1234"\n- textbox "Digit 3"'
    assert _smart_value("textbox", "Digit 3", aria) == "3"
    # Specific keywords win over generic ones and over the bare "code" fallback.
    assert _smart_value("textbox", "Username") == "testuser"        # not "Test User"
    assert _smart_value("textbox", "First Name") == "Test"
    assert _smart_value("textbox", "Country") == "Malaysia"
    assert _smart_value("textbox", "Card Number") == "4111111111111111"
    assert _smart_value("textbox", "Security Code") == "123"        # CVV, not OTP 1234
    assert _smart_value("textbox", "Discount Code") == "TEST10"     # coupon, not OTP 1234
    assert _smart_value("textbox", "Enter Code") == "1234"          # bare code => OTP fallback


def test_example_from_placeholder():
    # Concrete examples are used verbatim (the app's own valid format).
    assert _example_from_placeholder("12-345 6789") == "12-345 6789"   # the BrewPoints fix
    assert _example_from_placeholder("you@example.com") == "you@example.com"
    assert _example_from_placeholder("e.g. +60 12 345 6789") == "+60 12 345 6789"
    # Masks and instructions are rejected (fall back to synthesized data).
    assert _example_from_placeholder("DD/MM/YYYY") == ""
    assert _example_from_placeholder("Enter your 6-digit code") == ""
    assert _example_from_placeholder("Search...") == ""
    assert _example_from_placeholder("") == ""


def test_heuristic_uses_select_and_toggle_order():
    # combobox filled first, then the switch toggled, then the button — never the link first.
    aria = ('- combobox "Outlet"\n- switch "Promo"\n- button "Continue"\n- link "Skip"')
    a1 = _heuristic_explore(aria, [], random.Random(1), current_screen_key="s#1")
    assert a1.action == "fill" and a1.role == "combobox"
    hist = [{"screen_key": "s#1", "action": "fill", "role": "combobox", "name": "Outlet", "nth": 0}]
    a2 = _heuristic_explore(aria, hist, random.Random(1), current_screen_key="s#1")
    assert a2.action == "click" and a2.role == "switch"


def test_heuristic_fills_then_clicks_then_done():
    aria = '- textbox\n- button "Submit"'
    rng = random.Random(1)
    first = _heuristic_explore(aria, [], rng)
    assert first.action == "fill"
    after_fill = _heuristic_explore(aria, [{"action": "fill", "role": "textbox", "name": ""}], rng)
    assert after_fill.action == "click" and after_fill.name == "Submit"
    # After fill+click the heuristic navigates back to explore other paths before giving up.
    after_both = _heuristic_explore(
        aria,
        [{"action": "fill", "role": "textbox", "name": ""},
         {"action": "click", "role": "button", "name": "Submit"}],
        rng,
    )
    assert after_both.action == "navigate_back"
    # After fill+click+navigate_back there is truly nothing left — done.
    after_back = _heuristic_explore(
        aria,
        [{"action": "fill", "role": "textbox", "name": ""},
         {"action": "click", "role": "button", "name": "Submit"},
         {"action": "navigate_back", "role": "", "name": ""}],
        rng,
    )
    assert after_back.action == "done"


def test_heuristic_empty_tree_is_done():
    assert _heuristic_explore("", [], random.Random(1)).action == "done"


def test_screen_control_status_tracks_untested_per_screen():
    aria = '- textbox "Phone"\n- button "Continue"\n- link "Skip for now"'
    sk = "http://app#aaa"
    # Nothing done yet -> all three untested.
    untested, tested = _screen_control_status(aria, [], sk)
    assert ("textbox", "Phone", 0) in untested and len(tested) == 0
    # After filling Phone + clicking Continue ON THIS screen -> only Skip remains.
    history = [
        {"screen_key": sk, "action": "fill", "role": "textbox", "name": "Phone", "nth": 0},
        {"screen_key": sk, "action": "click", "role": "button", "name": "Continue", "nth": 0},
    ]
    untested, tested = _screen_control_status(aria, history, sk)
    assert untested == [("link", "Skip for now", 0)]
    assert ("textbox", "Phone", 0) in tested and ("button", "Continue", 0) in tested


def test_screen_control_status_is_scoped_per_screen():
    aria = '- button "Continue"'
    # Same control name, but tested on a DIFFERENT screen -> still untested here.
    history = [{"screen_key": "http://app#other", "action": "click",
                "role": "button", "name": "Continue", "nth": 0}]
    untested, tested = _screen_control_status(aria, history, "http://app#here")
    assert untested == [("button", "Continue", 0)] and tested == []


# --- integration: a real headless browser, offline planner ------------------

def test_autonomous_explores_form():
    cfg = NavConfig(FLAWED, goal="Enter the code and submit", behavior_profile=BP,
                    seed=1, max_steps=10)
    j = run_journey(cfg)
    keys = [s.step_key for s in j.steps]
    assert len(j.steps) >= 1
    assert any(k.startswith("fill") for k in keys)   # discovered the textbox itself
    # navigate_back adds one extra step before the cap fires, so allow max_steps + 1.
    assert len(j.steps) <= cfg.max_steps + 1          # safety cap respected


def test_autonomous_terminates_and_screenshots(tmp_path):
    cfg = NavConfig(FLAWED, goal="do the task", behavior_profile=BP, seed=1,
                    max_steps=8, artifact_dir=str(tmp_path))
    j = run_journey(cfg)
    shots = [s for s in j.screenshots if s]
    assert len(shots) == len(j.steps)                  # FR-1.3 screenshot every step
    assert all(pathlib.Path(s).exists() for s in shots)


def test_autonomous_records_block_but_keeps_exploring():
    """A blocked step is NOTED (dead_end) but does NOT stop the autonomous walk.

    Label-dependent persona on the unlabeled-OTP fixture: scripted mode would exit at the
    first block (1 step), but autonomous mode records the finding and continues testing the
    rest of the screen — so we get the finding AND more than one step.
    """
    cfg = NavConfig(FLAWED, goal="explore the whole screen", behavior_profile=BP,
                    requires_labels=True, seed=1, max_steps=12)
    j = run_journey(cfg)
    assert any(s.dead_end for s in j.steps), [s.step_key for s in j.steps]  # block recorded
    assert len(j.steps) >= 2, [s.step_key for s in j.steps]                 # did NOT stop at it


def test_autonomous_walks_full_wizard_handling_every_control_type():
    """End-to-end on the BrewPoints-shaped SPA wizard, offline & deterministic.

    Proves the encoded human workflow: type-correct fills, native <select> via
    select_option, nth-targeting of the 3 unnamed birthday selects (the validation
    gate), toggling unnamed switches, and reaching the terminal screen — all WITHOUT a
    scripted flow. If selects/duplicates were mishandled the agent would stall on the
    profile screen's 'Please enter your birthday' gate and never reach perms/done.
    """
    cfg = NavConfig(WIZARD, goal="Complete the signup wizard end to end",
                    behavior_profile=BP, seed=1, max_steps=60)
    j = run_journey(cfg)
    keys = [s.step_key for s in j.steps]

    # Walked past the profile birthday gate into the permissions screen (switches).
    assert any("Promo offers" in k or "switch" in k.lower() for k in keys), keys
    # Chose options in the birthday selects (3 unnamed comboboxes were reached by nth).
    assert sum(1 for k in keys if k.startswith("fill")) >= 5, keys
    # Did not get stuck: terminated cleanly (not via the safety cap).
    assert len(j.steps) < 60, len(j.steps)

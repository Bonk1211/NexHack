"""Evidence pack tests (§13). Asserts the hero diff (control passes, protected
persona blocked), severity-ranked routed remediation, and the trusted/indicative
separation in the §13 JSON."""
from __future__ import annotations

from app.evidence.pack import (
    PersonaRunResult,
    build_friction_matrix,
    build_pack,
    build_remediation,
    build_replay,
    lenses_for,
    route_owner,
)
from app.scoring.engine import PersonaThresholds, StepSignals, WcagSignal, score

T = PersonaThresholds(max_dwell_s=30, giveup_threshold_s=60, retry_limit=3, max_reading_grade=12)


def _run(persona, steps):
    return PersonaRunResult(persona, tuple(steps), T, score(steps, T))


def _otp_clean():
    return StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", True),), dwell_s=5)


def _otp_blocked():
    # unlabeled OTP -> dead end at a critical step (the planted P0 flaw)
    return StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", False),),
                       dead_end=True, completed=False)


def test_route_owner_maps_criteria():
    assert route_owner(["1.4.3"]) == "@frontend"
    assert route_owner(["1.3.1"]) == "@content"
    assert route_owner([]) == "@frontend"


def test_matrix_shows_hero_diff():
    home = StepSignals(0, "home", dwell_s=4)
    control = _run("control", [home, _otp_clean()])
    visual = _run("oku_visual", [home, _otp_blocked()])
    matrix = build_friction_matrix([control, visual])
    assert matrix["steps"] == ["home", "otp"]
    # Same step: green for control, red for the protected persona — the §14 diff.
    assert matrix["rows"]["control"]["otp"]["status"] == "green"
    assert matrix["rows"]["oku_visual"]["otp"]["status"] == "red"


def test_lenses_for_dedupes_and_maps_disability():
    assert lenses_for([]) == []                                   # baseline persona
    assert lenses_for(["low_vision"]) == ["low_vision_blur", "contrast"]
    assert lenses_for(["motor"]) == ["tap_target_overlay"]
    assert lenses_for(["low_vision", "low_vision"]) == ["low_vision_blur", "contrast"]
    assert lenses_for(["nonsense"]) == []                         # unknown tag → no lens


def test_build_replay_frames_carry_status_url_and_caption():
    visual = _run("oku_visual", [StepSignals(0, "home", dwell_s=4), _otp_blocked()])
    pack = build_pack("DemoBank", "2026-06-19T00:00:00Z", [visual])
    steps = pack["personas"][0]["steps"]
    row = pack["matrix"]["rows"]["oku_visual"]
    shots = ["s3://home.png", "s3://otp.png"]

    replay = build_replay(["low_vision"], steps, shots, row)

    assert replay["lenses"] == ["low_vision_blur", "contrast"]
    assert [f["step_key"] for f in replay["frames"]] == ["home", "otp"]
    otp = replay["frames"][1]
    assert otp["status"] == "red"                                 # matches the hero diff
    assert otp["screenshot_url"] == "s3://otp.png"
    assert otp["caption"].startswith("blocked")                   # dead-end at critical step
    assert replay["frames"][0]["caption"] == "ok"


def test_build_replay_tolerates_short_shot_list():
    visual = _run("oku_visual", [StepSignals(0, "home", dwell_s=4), _otp_blocked()])
    pack = build_pack("DemoBank", "2026-06-19T00:00:00Z", [visual])
    steps = pack["personas"][0]["steps"]
    replay = build_replay([], steps, [], pack["matrix"]["rows"]["oku_visual"])
    assert all(f["screenshot_url"] is None for f in replay["frames"])


def test_matrix_handles_missing_step():
    a = _run("a", [StepSignals(0, "home", dwell_s=2)])
    b = _run("b", [StepSignals(0, "home", dwell_s=2), StepSignals(1, "extra", dwell_s=2)])
    matrix = build_friction_matrix([a, b])
    assert matrix["rows"]["a"]["extra"]["status"] == "na"


def test_remediation_prioritized_and_routed():
    visual = _run("oku_visual", [_otp_blocked()])          # 4.1.2 fail at P0
    motor = _run("oku_motor", [
        StepSignals(0, "pay", critical=False, wcag=(WcagSignal("2.5.8", False),), dwell_s=4),
    ])                                                     # 2.5.8 fail, completed -> lower sev
    rem = build_remediation([visual, motor])
    assert rem[0]["criterion"] == "4.1.2"                  # P0 ranks first
    assert rem[0]["severity"] == "P0"
    assert rem[0]["owner"] == "@content"
    assert {r["criterion"] for r in rem} == {"4.1.2", "2.5.8"}


def test_pack_keeps_trusted_and_indicative_separate():
    home = StepSignals(0, "home", dwell_s=3)
    control = _run("control", [home, _otp_clean()])
    visual = _run("oku_visual", [home, _otp_blocked()])
    pack = build_pack("DemoBank", "2026-06-19T00:00:00Z", [control, visual])

    # Trusted stream reported on its own (§16): 4.1.2 failed for one persona -> fail overall.
    assert pack["wcag_conformance"]["4.1.2"] == "fail"
    # Indicative stream lives per-persona and is labeled.
    visual_entry = next(p for p in pack["personas"] if p["persona"] == "oku_visual")
    assert visual_entry["verdict"] == "blocked"
    assert visual_entry["severity"] == "P0"
    assert "indicative" in visual_entry["behavioral_note"]
    # Derived roll-up present but separate.
    assert 0.0 <= pack["inclusion_score"] <= 1.0
    assert pack["remediation"][0]["severity"] == "P0"


def test_empty_pack_is_neutral():
    pack = build_pack("X", "2026-06-19T00:00:00Z", [])
    assert pack["inclusion_score"] == 1.0
    assert pack["remediation"] == []


def test_pack_carries_per_step_two_streams():
    # Per-step detail must travel with each persona: trusted wcag_conformance +
    # indicative llm_judgment, kept distinct (§16). Feeds DB persistence + the UI.
    visual = _run("oku_visual", [
        StepSignals(0, "home", dwell_s=3),
        StepSignals(1, "otp", critical=True, wcag=(WcagSignal("4.1.2", False),),
                    dead_end=True, completed=False, llm_confusion=1.0),
    ])
    pack = build_pack("DemoBank", "2026-06-19T00:00:00Z", [visual])
    steps = next(p for p in pack["personas"] if p["persona"] == "oku_visual")["steps"]
    assert [s["step_key"] for s in steps] == ["home", "otp"]
    otp = steps[1]
    assert otp["wcag_conformance"] == {"4.1.2": "fail"}     # TRUSTED
    assert otp["axe_violations"] == ["4.1.2"]
    assert otp["llm_judgment"] == {"confusion": 1.0}        # INDICATIVE
    assert otp["dead_end"] is True

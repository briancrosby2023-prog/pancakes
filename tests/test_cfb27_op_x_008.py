import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_op_x_008 import build_op_x_008, current_records

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_008"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_team_state_002_preserves_state1_and_current_resources():
    state = load("team_state_002")
    assert state["parent_state"] == "TEAM_STATE_001" and state["preserves_team_state_001"]
    assert state["resources"]["coins"]["amount"] == 209644
    assert state["resources"]["green"]["identity"] == "UNKNOWN"


def test_current_versions_never_borrow_historical_ratings():
    rows = current_records(_cards(ROOT))
    hinzman = next(row for row in rows if row["player"] == "Carson Hinzman")
    assert hinzman["ratings"] is None
    assert 86 in hinzman["historical_reference_overalls"]
    assert hinzman["historical_reference_used_as_current"] is False


def test_owen_and_specialist_overalls_stay_separate():
    owen = load("owen_allen_multi_role")
    assert owen["normal"]["overall"] == 86
    assert owen["specialist_roles"] == {"3DRB1": 79, "GAD1": 89, "PWHB1": 89}
    assert owen["normal_and_specialist_ovr_separate"]


def test_protected_assets_and_duce_are_safe():
    fs = load("fs1_protected_analysis")
    assert fs["card_retention"] == "MANDATORY_POLICY"
    duce = load("duce_specialist_reassessment")
    assert duce["sell"] == "PROHIBITED" and duce["legal_slwr_eligibility"] == "UNKNOWN"
    assert load("bowen_value")["decision"] == "DO_NOT_TOUCH"


def test_coin_plan_does_not_force_spend_or_invent_prices():
    plan = load("coin_plan_209644")
    assert plan["recommendation"] == "SAVE_AND_WATCH" and plan["spend_now"] == 0
    assert load("coin_efficiency_frontier")["ranked"] == []


def test_packet_deterministic_and_integrity_strict():
    first = build_op_x_008(ROOT)
    assert first == build_op_x_008(ROOT)
    assert first["freeze"]["source_commit"] == "7b75903"
    assert len(first["secondary_gates"]) >= 10
    assert len(first["mandatory_validation"]) == 8
    assert all(value is False for value in first["validation"].values())

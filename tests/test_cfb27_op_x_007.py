import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_007 import (
    apply_snapshot_delta,
    build_op_x_007,
    replacement_delta,
)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_007"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_twin_is_partial_and_player_slots_are_separate():
    twin = load("team_digital_twin_v1")
    assert twin["partial_records_legal"]
    assert {row["player"] for row in twin["roster"]} == {"Duce Robinson", "Junior Seau"}
    assert all(row["object_type"] != "PLAYER_CARD" for row in load("roster_slot_model"))


def test_snapshot_delta_is_idempotent_and_does_not_treat_absence_as_removal():
    row = {"slot_id": "QB1", "card_id": "a", "overall": 88, "readable": True}
    delta = apply_snapshot_delta([row], [row])
    assert delta["changes"][0]["classification"] == "UNCHANGED"
    assert apply_snapshot_delta([row], [])["changes"][0]["classification"] == "AMBIGUOUS"
    assert delta == apply_snapshot_delta([row], [row])


def test_replacement_delta_uses_role_ratings_not_overall():
    result = replacement_delta({"ratings": {"RBK": 80}}, {"ratings": {"RBK": 85}}, ["RBK"])
    assert result["classification"] == "CLEAR_UPGRADE"
    assert result["ovr_used_as_decision"] is False
    assert replacement_delta(None, {}, ["RBK"])["classification"] == "INSUFFICIENT_DATA"


def test_mandatory_cases_protect_assets_and_bnd():
    cases = load("mandatory_validation")
    assert cases["duce"]["sell"] == "PROHIBITED"
    assert cases["seau"]["starting_decision_quality"] != cases["seau"]["roll_quality"]
    assert all(not row["discard_card_allowed"] for row in cases["protected"])
    assert set(cases["two_edge"]) == {"EDGE1", "EDGE2"}


def test_unknown_roster_blocks_only_dependent_outputs():
    assert all(row["classification"] == "UNKNOWN" for row in load("team_weakness_map"))
    assert (
        load("top_team_improvements")["top_bnd_opportunity"]["value"] == "DUCE_SPECIALIST_PLACEMENT"
    )
    assert load("budget_frontier")["populated"] == []


def test_full_packet_is_deterministic_and_strict():
    first = build_op_x_007(ROOT)
    assert first == build_op_x_007(ROOT)
    assert first["freeze"]["source_commit"] == "25dc0cc"
    assert len(first["secondary_gates"]) >= 8
    assert all(value is False for value in first["validation"].values())

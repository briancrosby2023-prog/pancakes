import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_op_x_009 import build_op_x_009, resolve_current_identity

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_009"


def load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text())


def test_team_state_003_is_incremental_and_preserves_history():
    state = load("team_state_003")
    assert state["parent_state"] == "TEAM_STATE_002"
    assert state["preserves_team_state_001"] and state["preserves_team_state_002"]


def test_native_ovr_mismatch_is_quarantined_not_promoted():
    row = {"player": "Carson Hinzman", "position": "C", "overall": 87}
    result = resolve_current_identity(row, _cards(ROOT))
    assert result["identity_classification"] in {"PROBABLE_MATCH", "AMBIGUOUS"}
    assert result["current_attribute_vector"] is None


def test_exact_identity_requires_unique_player_position_native_ovr():
    row = {"player": "Junior Seau", "position": "MLB", "overall": 86}
    result = resolve_current_identity(row, _cards(ROOT))
    assert result["identity_classification"] == "EXACT_MATCH"
    assert result["current_attribute_vector"]


def test_unknowns_are_never_converted_to_zero():
    state = load("team_state_003")
    unresolved = [
        row for row in state["normal_slots"] if row["identity_classification"] != "EXACT_MATCH"
    ]
    assert unresolved
    assert all(row["current_attribute_vector"] is None for row in unresolved)
    assert all(not row["unknown_ratings_converted_to_zero"] for row in unresolved)


def test_coverage_and_minimum_input_are_explicit():
    coverage = load("vector_coverage")
    assert coverage["normal"] == {"exact_vectors": 1, "percent": 4.17, "total": 24}
    assert coverage["ol"]["exact_vectors"] == 0
    request = load("minimum_user_input")
    assert len(request["players"]) == 5


def test_protected_bnd_and_coin_rules_survive():
    board = load("gm_action_board_v3")
    assert any(row["target"] == "DRAYK_BOWEN" and row["action"] == "DO_NOT_TOUCH" for row in board)
    assert load("duce_legality_v2")["sell"] == "PROHIBITED"
    assert load("coin_decision_209644_v2")["decision"] == "SAVE"


def test_packet_is_deterministic_and_integrity_strict():
    first = build_op_x_009(ROOT)
    assert first == build_op_x_009(ROOT)
    assert first["freeze"]["source_commit"] == "6c8d96e"
    assert len(first["secondary_gates"]) >= 12
    assert all(value is False for value in first["validation"].values())

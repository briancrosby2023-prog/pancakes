import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import build_op_x_001

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_001"


def _load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text(encoding="utf-8"))


def test_freeze_and_stack_cover_frozen_population() -> None:
    freeze = _load("freeze")
    stack = _load("ability_stack_coherence")
    assert freeze["source_commit"] == "ab54a79"
    assert freeze["population_n"] == len(stack) == 435
    assert len(freeze["input_sha256"]) == 2
    assert all(row["gameplay_effectiveness_claimed"] is False for row in stack)
    assert all(
        row["source_status"] == "STRUCTURED_THRESHOLD_NOT_VERIFIED_CUT_AVAILABILITY"
        for row in stack
    )


def test_signatures_cover_all_requested_positions_deterministically() -> None:
    signatures = _load("archetype_signatures")
    assert set(signatures) == {"QB", "HB", "WR", "TE", "EDGE", "MIKE", "CB", "FS"}
    assert all(signatures[position] for position in signatures)
    assert build_op_x_001(ROOT) == build_op_x_001(ROOT)


def test_mike_and_seau_do_not_synthesize_missing_states() -> None:
    mike = _load("mike_deep_dive")
    seau = _load("seau_crosswalk")
    assert set(mike["archetypes"]) == {"Thumper", "Lurker", "Signal Caller"}
    assert seau["known_missing_vectors"] == [81, 84]
    assert seau["synthetic_vectors"] is False
    assert [row["overall"] for row in seau["validated_states"]] == [86, 87]


def test_outputs_preserve_evidence_boundaries() -> None:
    validation = _load("validation")
    assert validation == {
        "access_bypass": False,
        "canonical_changes": False,
        "conflicts_preserved": True,
        "guessed_values": False,
        "unsupported_gameplay_claims": False,
    }
    support = _load("focused_support")
    assert support["special_cards"]["ea_intent_inferred"] is False
    assert all(row["height_matched"] is None for row in support["cb_candidates"])
    assert len(_load("chatgpt_handoff")) >= 12

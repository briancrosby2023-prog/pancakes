import json
from pathlib import Path

from operation_pancake.acquisition.cfb_fan import parse_player_listing, parse_player_page
from operation_pancake.research.cfb27_inheritance import build_inheritance_analysis

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/external/cfb_fan_population_state.json"
SUMMARY = ROOT / "data/research/cfb27_inheritance_phase1/analysis_summary.json"


def _summary():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_population_is_substantial_complete_and_offline_reproducible() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert len(state["cards"]) >= 90
    assert len({card["position"] for card in state["cards"].values()}) >= 10
    for card in state["cards"].values():
        snapshot = ROOT / card["raw_snapshot_reference"]
        reparsed = parse_player_page(
            snapshot.read_text(encoding="utf-8"),
            card["source_reference"],
            card["retrieval_timestamp"],
            card["raw_snapshot_reference"],
        )
        assert reparsed.external_card_id == card["external_card_id"]
        assert reparsed.displayed_ratings == card["displayed_ratings"]
        assert len(card["displayed_ratings"]) >= 15


def test_listing_snapshots_reproduce_selected_links() -> None:
    discovery = json.loads(
        (ROOT / "data/external/cfb_fan_population_discovery.json").read_text(encoding="utf-8")
    )
    for snapshot in discovery["listing_snapshots"].values():
        links = parse_player_listing(
            (ROOT / snapshot["snapshot_location"]).read_text(encoding="utf-8")
        )
        assert len(links) >= snapshot["links_selected"] > 0


def test_current_position_labels_are_normalized_without_losing_source_label() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    mike = next(card for card in state["cards"].values() if card["position"] == "MLB")
    assert mike["metadata"]["source_position"] == "MIKE"
    assert any(card["position"] == "LE" for card in state["cards"].values())
    assert any(card["position"] == "RE" for card in state["cards"].values())


def test_analysis_is_deterministic_and_staging_only() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    summary = _summary()
    rebuilt = build_inheritance_analysis(list(state["cards"].values()), summary["historical_leads"])
    for key in (
        "cards_acquired",
        "positions",
        "center_inheritance",
        "threshold_candidates",
        "pc_evaluator",
    ):
        assert json.loads(json.dumps(rebuilt[key], sort_keys=True)) == summary[key]
    assert summary["canonical_modified"] is False
    assert summary["guessed_values"] is False
    assert summary["operationally_solved_98_positions"] == []


def test_center_inheritance_is_leakage_safe_and_special_separated() -> None:
    center = _summary()["center_inheritance"]
    assert center["population"] >= 15
    assert center["ordinary_population"] + center["special_population"] == center["population"]
    assert center["classification"] in {"STABLE_CORE_WITH_RECALIBRATION", "INSUFFICIENT_EVIDENCE"}
    assert "leave_one_out" in "leave_one_out_recalibration"


def test_threshold_claims_are_conservative() -> None:
    rows = _summary()["threshold_candidates"]
    assert rows
    assert {row["classification"] for row in rows} <= {
        "CANDIDATE_THRESHOLD",
        "SUPPORTED_THRESHOLD",
        "INSUFFICIENT",
    }
    assert "SUPPORTED_THRESHOLD" not in {row["classification"] for row in rows}


def test_historical_leads_do_not_fabricate_values() -> None:
    leads = _summary()["historical_leads"]
    assert (
        leads["table_44_ability_progression_tunable_archetypes"]["numeric_values_recovered"]
        is False
    )
    assert leads["madden16_attribute_weights"]["numeric_values_recovered"] is False

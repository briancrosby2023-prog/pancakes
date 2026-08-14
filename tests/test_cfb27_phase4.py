import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_inheritance_phase4"


def _load(name: str):
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def test_phase4_snapshot_freezes_phase3_population_before_future_acquisition() -> None:
    frozen = _load("phase4_frozen_snapshot.json")
    assert frozen["source_commit"] == "cd72120"
    assert frozen["population_n"] == 435
    assert len(frozen["card_ids"]) == 435
    assert len(frozen["population_sha256"]) == 64
    assert frozen["frozen_te_models_modified"] is False


def test_te_nulls_use_exact_historical_cross_ovr_objective() -> None:
    nulls = _load("te_null_distributions.json")
    assert nulls["Vertical Threat"]["historical"] == {
        "accuracy": 0.98571429,
        "correct": 138,
        "failures": nulls["Vertical Threat"]["historical"]["failures"],
        "mean_margin": nulls["Vertical Threat"]["historical"]["mean_margin"],
        "pairs": 140,
    }
    assert nulls["Gritty Possession"]["historical"]["correct"] == 97
    assert nulls["Gritty Possession"]["historical"]["pairs"] == 98
    assert nulls["Physical Route Runner"]["historical"]["correct"] == 404
    assert nulls["Physical Route Runner"]["historical"]["pairs"] == 404
    for result in nulls.values():
        for family in ("random_positive", "shuffled_historical", "random_subsets"):
            assert result[family]["draws"] == 1000


def test_te_conclusions_are_adversarial_and_coefficients_not_overclaimed() -> None:
    nulls = _load("te_null_distributions.json")
    assert nulls["Vertical Threat"]["random_positive"]["tie_or_beat"] == 0
    assert nulls["Physical Route Runner"]["random_positive"]["tie_or_beat"] == 0
    assert nulls["Gritty Possession"]["equal"]["accuracy"] == 0.98979592
    assert nulls["Gritty Possession"]["classification"]["ranking"] == "NOT_EXCEPTIONAL"
    assert all(
        result["classification"]["numeric"] == "ARCHITECTURE_ONLY" for result in nulls.values()
    )


def test_schema_inventory_covers_every_claimed_game_and_actual_fields() -> None:
    sources = _load("ea_schema_sources.json")
    assert sources["supported_games_from_bundled_schemas"] == [
        "M19",
        "M20",
        "M21",
        "M22",
        "M23",
        "M24",
        "M25",
        "M26",
        "M27",
        "C27",
    ]
    assert len(sources["catalog"]) == 10
    for row in sources["catalog"]:
        with gzip.open(ROOT / row["inventory"], "rt", encoding="utf-8") as stream:
            inventory = json.load(stream)
        player = next(table for table in inventory["tables"] if table["name"] == "Player")
        assert any(field["name"] == "AwarenessRating" for field in player["fields"])


def test_ability_progression_table_family_is_directly_observed_not_inferred() -> None:
    continuity = _load("ability_progression_tunable_continuity.json")
    assert set(continuity) == {"M19", "M20", "M21", "M22", "M23", "M24", "M25", "M26", "M27", "C27"}
    assert all(table["name"] == "AbilityProgressionTunable" for table in continuity.values())
    cross_check = _load("table_44_cross_check.json")
    assert len(cross_check["ability_progression_tunable_present_games"]) == 10
    assert cross_check["exact_historical_long_name_found"] is False


def test_evidence_types_are_separate_and_unsupported_records_empty() -> None:
    ability = _load("ability_threshold_schema.json")
    gameplay = _load("gameplay_breakpoint_schema.json")
    boundary = _load("ovr_boundary_schema.json")
    assert ability["evidence_type"] == "ABILITY_THRESHOLD" and ability["records"] == []
    assert gameplay["evidence_type"] == "GAMEPLAY_BREAKPOINT" and gameplay["records"] == []
    assert boundary["evidence_type"] == "OVR_BOUNDARY"
    assert boundary["supported_records"] == []
    assert boundary["historical_falsified_candidates"]["candidates_before"] == 29


def test_base_roster_denial_is_preserved_without_access_bypass() -> None:
    pilot = _load("base_roster_pilot.json")
    assert pilot["no_access_bypass"] is True
    assert pilot["populations"]["Backfield Creator"]["n"] == 13
    assert pilot["source_declared_population"]["Raw Strength"] == 105
    assert any(row["status"] == "HTTP_403" for row in pilot["sources"])


def test_moneyball_release_and_market_outputs_remain_descriptive() -> None:
    summary = _load("phase4_summary.json")
    assert summary["moneyball_crosswalk"]["gameplay_value_claimed"] is False
    assert len(summary["moneyball_crosswalk"]["top_targets"]) == 10
    assert summary["release_intelligence"]["forecast_readiness"] == "INSUFFICIENT"
    assert summary["market_bridge"]["records"] == 0
    assert summary["data_validation"] == {
        "access_bypass": False,
        "canonical_modified": False,
        "guessed_values": False,
        "leakage": False,
        "special_ordinary_contamination": False,
    }

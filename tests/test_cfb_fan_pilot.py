import json
from pathlib import Path

from operation_pancake.acquisition.cfb_fan import PARSER_VERSION, parse_player_page

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/external/cfb_fan_pilot_state.json"
REPORT = ROOT / "data/research/cfb_fan_controlled_pilot/pilot_report.json"


def pilot_state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def pilot_report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_saved_snapshots_parse_without_live_access() -> None:
    state = pilot_state()
    cards = []
    for snapshot in state["snapshots"].values():
        html = (ROOT / snapshot["snapshot_location"]).read_text(encoding="utf-8")
        cards.append(
            parse_player_page(
                html,
                snapshot["external_identifiers"]["source_url"],
                snapshot["retrieved_at"],
                snapshot["snapshot_location"],
            )
        )
    assert len(cards) == 6
    assert {card.position for card in cards} == {"C"}
    assert {card.player_name for card in cards} == {
        "Iapani Laloulu",
        "Ashton Beers",
        "Kade Pieper",
        "Carson Hinzman",
        "Cole Best",
        "Kevin Mawae",
    }


def test_player_parser_captures_full_center_vector() -> None:
    state = pilot_state()
    snapshot = next(
        item
        for item in state["snapshots"].values()
        if "ashton-beers" in item["external_identifiers"]["source_url"]
    )
    card = parse_player_page(
        (ROOT / snapshot["snapshot_location"]).read_text(encoding="utf-8"),
        snapshot["external_identifiers"]["source_url"],
        snapshot["retrieved_at"],
        snapshot["snapshot_location"],
    )
    assert (card.player_name, card.overall, card.program, card.archetype) == (
        "Ashton Beers",
        85,
        "Standouts",
        "Raw Strength",
    )
    assert set(card.displayed_ratings) == {
        "SPD",
        "ACC",
        "AGI",
        "COD",
        "AWR",
        "STR",
        "TGH",
        "RBK",
        "RBF",
        "RBP",
        "PBK",
        "PBF",
        "PBP",
        "LBK",
        "IBL",
    }
    assert card.displayed_ratings["STR"] == 85


def test_pilot_report_is_staging_only_and_rate_safe() -> None:
    report = pilot_report()
    assert report["pages_fetched"] == 6
    assert report["center_cards_staged"] == 6
    assert report["center_ovr_range"] == [80, 86]
    assert report["canonical_promotions"] == 0
    assert report["initial_pilot_staging"] == {
        "ambiguous_identities": 0,
        "canonical_identity_matches": 1,
        "canonical_promotions": 0,
        "conflicts": 0,
        "new_external_cards": 5,
    }
    assert report["failed_pages"] == []
    assert report["parser_version"] == PARSER_VERSION
    assert "<=12 requests/minute" in report["request_observations"]


def test_historical_cross_reference_preserves_different_cards() -> None:
    cross = pilot_report()["historical_cross_reference"]
    assert cross["Ashton Beers"]["classification"] == "MATCH"
    assert cross["Carson Hinzman"]["classification"] == "DIFFERENT_CARD"
    assert cross["Joey Harrington"]["classification"] == "DIFFERENT_CARD_CONFIRMS_COMPARISON"


def test_progression_discovery_is_not_promoted_to_progression_linkage() -> None:
    discovery = pilot_report()["progression_target_discovery"]
    assert discovery["Chris Peal"] == [70, 84, 86, 87]
    assert discovery["Michael Crabtree"] == [80]
    assert discovery["Bo Jackson"] == [70, 80, 83, 85, 86]
    assert discovery["Peyton Bowen"] == [70, 80, 82, 83, 85, 86]
    assert discovery["Junior Seau"] == [80, 82]
    assert discovery["Joey Harrington"] == [80]


def test_capability_grades_are_explicit() -> None:
    grades = pilot_report()["capability_grades"]
    assert grades["population_discovery"] == "GOOD"
    assert grades["full_rating_vector_acquisition"] == "GOOD"
    assert grades["release_tracking"] == "PARTIAL"
    assert grades["market_tracking"] == "PARTIAL"
    assert grades["historical_progression_recovery"] == "PARTIAL"

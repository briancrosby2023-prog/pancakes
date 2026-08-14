import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_cfb27_population_v3.py"
SPEC = importlib.util.spec_from_file_location("population_v3", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
parse_listing = MODULE.parse_listing
merge_listing_cards = MODULE.merge_listing_cards
normalize_listing_ids = MODULE.normalize_listing_ids
pages_to_fetch = MODULE.pages_to_fetch


def test_listing_parser_preserves_partial_status_and_source_id():
    html = """
    <div class="player-list-item"><a href="/players/7-test-player/27-12345/">
    <div class="player-list-item__score-value">88</div>
    <div class="player-list-item__name-first">Test</div>
    <div class="player-list-item__name-last">Player</div>
    <div class="player-list-item__stat-name">SPD</div>
    <div class="player-list-item__stat-value">90</div>
    <div class="player-list-item__program">Season 1</div>
    <div class="player-list-item__archetype">MIKE - Lurker</div>
    """
    card = parse_listing(html, "raw.html")[0]
    assert card["external_card_id"] == "27-12345"
    assert card["position"] == "MLB"
    assert card["displayed_ratings"] == {"SPD": 90}
    assert card["extraction_status"] == "PARTIAL_LISTING_VECTOR"
    assert card["source_reference"].endswith("/players/7-test-player/27-12345/")
    assert card["raw_snapshot_reference"] == "raw.html"


def test_incremental_refresh_targets_newest_pages():
    assert list(pages_to_fetch(3)) == [588, 589, 590]
    assert pages_to_fetch(0).start == 1
    assert pages_to_fetch(0).stop == 591


def test_new_cards_are_added_and_conflicts_preserve_existing_detail():
    state = {
        "cards": {
            "CFB_FAN:1": {
                "external_card_id": "1",
                "player_name": "Existing Detail",
                "position": "QB",
                "overall": 88,
                "program": "Program A",
                "archetype": "Pocket Passer",
                "extraction_status": "COMPLETE",
            }
        },
        "conflicts": {},
    }
    listing = {
        "1": {
            "external_card_id": "1",
            "player_name": "Conflicting Listing",
            "position": "QB",
            "overall": 88,
            "program": "Program A",
            "archetype": "Pocket Passer",
            "source_reference": "https://cfb.fan/players/1/27-1/",
        },
        "2": {
            "external_card_id": "2",
            "player_name": "New Card",
            "position": "HB",
            "overall": 80,
            "program": "Program B",
            "archetype": "Elusive",
            "source_reference": "https://cfb.fan/players/2/27-2/",
        },
    }
    result = merge_listing_cards(state, listing)
    assert result == {"added": 1, "conflicts": 1}
    assert state["cards"]["CFB_FAN:1"]["player_name"] == "Existing Detail"
    assert state["cards"]["CFB_FAN:1"]["extraction_status"] == "COMPLETE"
    assert state["cards"]["CFB_FAN:2"]["player_name"] == "New Card"
    assert state["conflicts"]["V3:1"]["resolution"] == "PRESERVE_COMPLETE_DETAIL_RECORD"


def test_listing_id_normalization_deduplicates_against_complete_detail():
    checkpoint = {
        "cards": {
            "123": {
                "external_card_id": "123",
                "extraction_status": "PARTIAL_LISTING_VECTOR",
            }
        }
    }
    complete = {"external_card_id": "27-123", "extraction_status": "COMPLETE"}
    state = {
        "cards": {
            "CFB_FAN:27-123": complete,
            "CFB_FAN:123": {
                "external_card_id": "123",
                "extraction_status": "PARTIAL_LISTING_VECTOR",
            },
        }
    }
    normalize_listing_ids(checkpoint, state)
    assert list(checkpoint["cards"]) == ["27-123"]
    assert state["cards"] == {"CFB_FAN:27-123": complete}

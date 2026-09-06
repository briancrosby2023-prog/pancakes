from __future__ import annotations

from pathlib import Path

import pytest

from operation_pancake.production.engine import load_population
from operation_pancake.production.reveals import (
    RELEASE_METHODS,
    merge_registry,
    monitor_targets,
    normalize_reveal,
    reconcile_live,
    render_whats_coming,
    save_registry,
    whats_coming,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-20T21:00:00+00:00"
SEEN = "2026-08-20T20:00:00+00:00"


def raw(**changes: object) -> dict:
    return {
        "player": "Verified Player",
        "overall": 99,
        "position": "QB",
        "program": "Verified Program",
        "source": "https://cfb.fan/reveals/",
        "provenance": "CFB.FAN Player Reveals",
        **changes,
    }


def reveal(**changes: object) -> dict:
    return normalize_reveal(raw(**changes), first_seen_at=SEEN, ingested_at=NOW, fixture=True)


def test_release_method_vocabulary_is_closed() -> None:
    assert "UNKNOWN" in RELEASE_METHODS and "SET / COLLECTION" in RELEASE_METHODS
    with pytest.raises(ValueError, match="unsupported"):
        reveal(release_method="PROBABLY PACKS", release_method_source="guess")


def test_unknown_is_default_and_no_method_is_inferred() -> None:
    row = reveal()
    assert row["release_method"] == "UNKNOWN"
    assert row["release_method_source"] is None


def test_verified_method_requires_method_source() -> None:
    with pytest.raises(ValueError, match="release_method_source"):
        reveal(release_method="PACKS")


def test_release_time_requires_explicit_source() -> None:
    with pytest.raises(ValueError, match="explicit source"):
        reveal(release_time="2026-08-21T17:00:00+00:00")


def test_auctionability_requires_explicit_source() -> None:
    with pytest.raises(ValueError, match="auctionability"):
        reveal(auctionable=True)


def test_set_rules_are_explicit_and_complete_shape() -> None:
    row = reveal(
        release_method="SET / COLLECTION",
        release_method_source="official set description",
        method_details={"required_items": ["item-a"], "quantity_required": 1},
        method_details_source="official set description",
    )
    assert row["method_details"]["required_items"] == ["item-a"]
    assert row["method_details"]["submitted_items_returned"] is None


@pytest.mark.parametrize("method", ["FIELD PASS / SEASON REWARD", "OBJECTIVE", "CHALLENGE"])
def test_requirement_rewards_capture_actual_requirement(method: str) -> None:
    row = reveal(
        release_method=method,
        release_method_source="official requirement",
        method_details={"acquisition_requirement": "Win 10 games"},
        method_details_source="official requirement",
    )
    assert row["method_details"] == {"acquisition_requirement": "Win 10 games"}


def test_ltd_captures_only_sourced_availability_window() -> None:
    row = reveal(
        release_method="LTD / LIMITED-TIME PACKS",
        release_method_source="official post",
        method_details={"availability_window": "Aug 21 1 PM–Aug 23 1 PM ET"},
        method_details_source="official post",
    )
    assert "Aug 23" in row["method_details"]["availability_window"]


def test_merge_preserves_first_seen_and_upgrades_unknown() -> None:
    old = reveal()
    new = normalize_reveal(
        raw(release_method="PACKS", release_method_source="official post"),
        first_seen_at="2026-08-20T20:30:00+00:00",
        ingested_at=NOW,
        fixture=True,
    )
    merged = merge_registry([old], [new])[0]
    assert merged["first_seen_at"] == SEEN
    assert merged["release_method"] == "PACKS"


def test_fixture_cannot_enter_production_registry(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fixture"):
        save_registry(tmp_path / "registry.json", [reveal()], production=True)


def test_exact_live_match_links_canonical_card_and_can_monitor() -> None:
    card = load_population(ROOT)[0]
    row = normalize_reveal(
        raw(
            player=card["player_name"],
            overall=card["native_overall"],
            position=card["position"],
            program=card["program"],
        ),
        first_seen_at=SEEN,
        ingested_at=NOW,
        fixture=True,
    )
    linked = reconcile_live(
        row,
        [card],
        {
            "source": "canonical live page",
            "observed_at": NOW,
            "auctionable": True,
            "auctionability_source": "live auction listing",
        },
    )
    assert linked["canonical_card_id"] == card["card_id"]
    assert monitor_targets([linked])[0]["card_id"] == card["card_id"]


def test_nonauctionable_and_unmatched_cards_are_never_monitored() -> None:
    linked = reconcile_live(
        reveal(),
        [],
        {
            "source": "live reward page",
            "observed_at": NOW,
            "auctionable": False,
            "auctionability_source": "BND label",
        },
    )
    assert linked["canonical_card_id"] is None
    assert linked["market_monitor"] is False
    assert monitor_targets([linked]) == []


def test_live_evidence_is_required() -> None:
    with pytest.raises(ValueError, match="sourced evidence"):
        reconcile_live(reveal(), [], {})


def test_whats_coming_has_exact_columns_and_excludes_live() -> None:
    upcoming = reveal()
    live = {**reveal(), "status": "LIVE — EXACT CANONICAL MATCH"}
    rows = whats_coming([upcoming, live])
    assert list(rows[0]) == [
        "PLAYER",
        "OVR",
        "POS",
        "PROGRAM",
        "RELEASE METHOD",
        "RELEASE TIME",
        "STATUS",
    ]
    report = render_whats_coming([upcoming])
    assert report.startswith("WHAT'S COMING\n") and "UNKNOWN" in report

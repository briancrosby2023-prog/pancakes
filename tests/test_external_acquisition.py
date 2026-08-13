from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.acquisition.adapters import AccessPolicy, ExternalCardAdapter, FixtureAdapter
from operation_pancake.acquisition.cfb_fan import CfbFanAdapterNamespace, import_saved_discoveries
from operation_pancake.acquisition.models import ExternalCard, MarketObservation
from operation_pancake.acquisition.pipeline import (
    AcquisitionPipeline,
    AcquisitionState,
    canonical_conflicts,
    match_external_card,
    population_targets,
)
from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import BulkManifestIngestor

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/external_cards.json"


def fixture_adapter(payload=None):
    payload = payload or json.loads(FIXTURE.read_text())
    cards = payload["cards"]
    return FixtureAdapter(
        [{"external_card_id": str(card["external_card_id"])} for card in cards],
        {
            str(card["external_card_id"]): json.dumps(card, sort_keys=True).encode()
            for card in cards
        },
    )


def pipeline(tmp_path):
    return AcquisitionPipeline(
        tmp_path,
        BulkManifestIngestor(build_evidence_index(ROOT)),
    )


def test_external_card_schema_preserves_unknown_and_full_vocabulary() -> None:
    payload = json.loads(FIXTURE.read_text())["cards"][0]
    payload.update(
        raw_snapshot_reference="raw.bin",
        extraction_status="COMPLETE",
        validation_status="STAGED_EXTERNAL",
        market_observations=(),
    )
    card = ExternalCard(**payload)
    assert card.displayed_ratings["RBP"] is None
    assert card.displayed_ratings["KAC"] == 70  # acquisition is not limited to C attributes


def test_adapter_contract_has_full_lifecycle() -> None:
    methods = {"discover_cards", "fetch_card", "parse_card", "normalize_card", "stage_card"}
    assert methods <= set(dir(ExternalCardAdapter))
    assert AccessPolicy().bypass_restricted_access is False


def test_fixture_end_to_end_preserves_snapshot_and_stages(tmp_path) -> None:
    pipe = pipeline(tmp_path)
    report = pipe.acquire_fixture(fixture_adapter(), "2026-08-13T12:00:00Z", dry_run=False)
    assert report["results"][0]["status"] == "NEW_CARD"
    assert report["staging_report"]["records_promoted"] == 0
    assert report["staging_report"]["result_counts"]["UNRESOLVED"] == 1
    snapshot = next(iter(pipe.state.snapshots.values()))
    assert len(snapshot["content_sha256"]) == 64
    assert (tmp_path / snapshot["snapshot_location"]).exists()
    assert snapshot["parser_version"] == "fixture-v1"


def test_market_observations_are_separate_from_card_identity(tmp_path) -> None:
    pipe = pipeline(tmp_path)
    pipe.acquire_fixture(fixture_adapter(), "2026-08-13T12:00:00Z", dry_run=False)
    assert "MARKET-card-100-20260813" in pipe.state.market_observations
    card = next(iter(pipe.state.cards.values()))
    identity_fields = ExternalCard(
        **{
            **card,
            "market_observations": tuple(
                MarketObservation(**item) for item in card["market_observations"]
            ),
        }
    ).conservative_identity
    assert 15000 not in identity_fields


def test_conservative_identity_separates_programs() -> None:
    card_payload = json.loads(FIXTURE.read_text())["cards"][0]
    card_payload.update(
        raw_snapshot_reference="x", extraction_status="COMPLETE", validation_status="VALID"
    )
    card = ExternalCard(**card_payload)
    candidates = [
        {
            "player": "Fixture Center",
            "position": "C",
            "overall": 82,
            "archetype": "Power",
            "program": "Different Program",
            "card_type": "Regular CUT",
        }
    ]
    assert match_external_card(card, candidates)["status"] == "IDENTITY_AMBIGUITY"


def test_external_id_matching_is_stronger_than_text_identity() -> None:
    payload = json.loads(FIXTURE.read_text())["cards"][0]
    payload.update(
        raw_snapshot_reference="x", extraction_status="COMPLETE", validation_status="VALID"
    )
    card = ExternalCard(**payload)
    result = match_external_card(
        card, [{"external_source": "FIXTURE", "external_card_id": "card-100"}]
    )
    assert result["status"] == "EXTERNAL_ID_MATCH"


def test_external_canonical_rating_conflict_preserves_both_values() -> None:
    index = build_evidence_index(ROOT)
    canonical = index.records[("player_card", "QB-0074")]
    card = ExternalCard(
        external_source="FIXTURE",
        external_player_id=None,
        external_card_id="qb-0074-ext",
        player_name=canonical["player"],
        position=canonical["position"],
        overall=canonical["overall"],
        archetype=canonical["archetype"],
        program=canonical["program"],
        card_type=None,
        team_school=None,
        release_date=None,
        displayed_ratings={"THP": canonical["attributes"]["THP"] + 1},
        source_reference="fixture://qb-0074",
        retrieval_timestamp="2026-08-13T00:00:00Z",
        raw_snapshot_reference="raw.bin",
        extraction_status="COMPLETE",
        validation_status="STAGED_EXTERNAL",
    )
    conflicts = canonical_conflicts(card, index)
    assert conflicts[0]["type"] == "RATING_MISMATCH"
    assert conflicts[0]["existing_value"] == canonical["attributes"]["THP"]
    assert conflicts[0]["incoming_value"] == card.displayed_ratings["THP"]
    assert canonical["attributes"]["THP"] != card.displayed_ratings["THP"]


def test_incremental_unchanged_updated_source_and_conflict(tmp_path) -> None:
    pipe = pipeline(tmp_path)
    adapter = fixture_adapter()
    pipe.acquire_fixture(adapter, "2026-08-13T12:00:00Z", dry_run=False)
    unchanged = pipe.acquire_fixture(adapter, "2026-08-13T12:00:00Z", dry_run=False)
    assert unchanged["results"][0]["status"] == "UNCHANGED"
    payload = json.loads(FIXTURE.read_text())
    payload["cards"][0]["displayed_ratings"]["STR"] = 86
    conflict = pipe.acquire_fixture(fixture_adapter(payload), "2026-08-14T12:00:00Z", dry_run=False)
    assert conflict["results"][0]["status"] == "CONFLICT"
    assert pipe.state.conflicts
    assert "RATING_MISMATCH" in next(iter(pipe.state.conflicts.values()))["types"]


def test_cfb_fan_saved_discovery_import(tmp_path) -> None:
    path = tmp_path / "discovery.json"
    path.write_text(
        json.dumps(
            [
                {
                    "season_id": 27,
                    "card_id": 100,
                    "player_id": 9,
                    "saved_page_reference": "saved/card-100.html",
                    "discovered_at": "2026-08-01T00:00:00Z",
                }
            ]
        )
    )
    result = import_saved_discoveries(path)
    assert result[0]["season_id"] == "27"
    assert result[0]["external_card_id"] == "100"
    assert CfbFanAdapterNamespace.live_access_status.startswith("BLOCKED")


def test_blocked_source_is_logged_without_bypass(tmp_path) -> None:
    class Blocked(FixtureAdapter):
        def fetch_card(self, discovery):
            raise PermissionError("Normal access denied")

    base = fixture_adapter()
    adapter = Blocked(base._discoveries, base._payloads)
    pipe = pipeline(tmp_path)
    report = pipe.acquire_fixture(adapter, "2026-08-13T12:00:00Z", dry_run=False)
    assert report["results"][0]["status"] == "BLOCKED"
    assert report["failures"][0]["bypass_attempted"] is False


def test_population_targets_follow_completeness_audit() -> None:
    targets = population_targets(ROOT)
    center = next(item for item in targets if item["position"] == "C")
    assert center["needed_ovr_range"] == [80, 85]
    assert center["needed_archetypes"] == 2
    assert center["minimum_desired_cards"] == 5
    assert targets[0]["priority"] == "CRITICAL"


def test_acquisition_state_round_trip_is_deterministic(tmp_path) -> None:
    pipe = pipeline(tmp_path)
    pipe.acquire_fixture(fixture_adapter(), "2026-08-13T12:00:00Z", dry_run=False)
    path = tmp_path / "state.json"
    pipe.save(path)
    assert AcquisitionState.load(path).as_dict() == pipe.state.as_dict()

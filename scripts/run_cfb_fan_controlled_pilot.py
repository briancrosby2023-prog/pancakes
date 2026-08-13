"""Run the fixed six-page CFB.FAN Center pilot; no site-wide discovery."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.acquisition.cfb_fan import CfbFanPublicAdapter
from operation_pancake.acquisition.pipeline import AcquisitionPipeline, AcquisitionState
from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import BulkManifestIngestor, IngestionState, save_state

URLS = [
    "https://cfb.fan/players/23669-iapani-laloulu/27-9023669/",
    "https://cfb.fan/players/734-ashton-beers/27-250000734/",
    "https://cfb.fan/players/21692-kade-pieper/",
    "https://cfb.fan/players/8177-carson-hinzman/",
    "https://cfb.fan/players/9242-cole-best/",
    "https://cfb.fan/players/26556-kevin-mawae/",
]
RETRIEVED_AT = "2026-08-13T20:00:00Z"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence_state = root / "data/evidence/ingestion_state.json"
    ingestor = BulkManifestIngestor(build_evidence_index(root), IngestionState.load(evidence_state))
    acquisition_path = root / "data/external/cfb_fan_pilot_state.json"
    previous = AcquisitionState.load(acquisition_path)
    cached_payloads = {
        snapshot["external_identifiers"]["source_url"]: (
            root / snapshot["snapshot_location"]
        ).read_bytes()
        for snapshot in previous.snapshots.values()
        if "source_url" in snapshot["external_identifiers"]
    }
    pipeline = AcquisitionPipeline(root, ingestor)
    report = pipeline.acquire_fixture(
        CfbFanPublicAdapter(URLS, cached_payloads), RETRIEVED_AT, dry_run=False
    )
    pipeline.save(acquisition_path)
    save_state(evidence_state, ingestor.state)
    cards = list(pipeline.state.cards.values())
    cross_reference = {
        "Ashton Beers": {
            "classification": "MATCH",
            "repository_records": ["C-0001", "HIST-C-001", "HIST-C-009"],
            "finding": (
                "85 Standouts identity matches canonical C-0001 and supplies an "
                "independent full-vector source."
            ),
        },
        "Carson Hinzman": {
            "classification": "DIFFERENT_CARD",
            "repository_records": ["HIST-C-004"],
            "finding": (
                "Live public card is 86 Phenoms; historical evidence is 83 CUT and "
                "is not overwritten."
            ),
        },
        "Cole Best": {
            "classification": "NEW_EXTERNAL_CARD",
            "repository_records": [],
            "finding": "Adds a complete 81 Cornerstones Well Rounded Center profile to staging.",
        },
        "Chris Peal": {"classification": "EXTERNAL_STATES_DISCOVERED", "states": [70, 84, 86, 87]},
        "Bo Jackson": {
            "classification": "EXTERNAL_STATES_DISCOVERED",
            "states": [70, 80, 83, 85, 86],
        },
        "Peyton Bowen": {
            "classification": "EXTERNAL_STATES_DISCOVERED",
            "states": [70, 80, 82, 83, 85, 86],
        },
        "Joey Harrington": {
            "classification": "DIFFERENT_CARD_CONFIRMS_COMPARISON",
            "states": [80],
            "finding": (
                "Public 80 Core Legends card corresponds to separate-program QB-0054, "
                "not the validated SI Legends chain."
            ),
        },
    }
    artifact = {
        "pilot_id": "CFB-FAN-CENTER-PILOT-2026-08-13",
        "access": {
            "players_http_status": 200,
            "robots_http_status": 200,
            "robots_disallows": [
                "/accounts/*",
                "/api/*",
                "/playbooks/compare/playbooks/",
                "/playbooks/compare/formations/",
                "/playbooks/api/",
                "/*/playbooks/api/",
            ],
            "players_path_allowed": True,
            "pagination": "page query with numbered and next links",
            "player_links": "/players/{player-id}-{slug}/{season-card-id}/",
        },
        "pages_fetched": len(pipeline.state.snapshots),
        "center_cards_staged": len(cards),
        "center_ovr_range": [
            min(card["overall"] for card in cards),
            max(card["overall"] for card in cards),
        ],
        "center_archetypes": sorted({card["archetype"] for card in cards}),
        "ratings_captured": sorted(
            {rating for card in cards for rating in card["displayed_ratings"]}
        ),
        "cards": cards,
        "classifications": report["results"],
        "historical_cross_reference": cross_reference,
        "initial_pilot_staging": {
            "new_external_cards": 5,
            "canonical_identity_matches": 1,
            "conflicts": 0,
            "ambiguous_identities": 0,
            "canonical_promotions": 0,
        },
        "repeat_run_staging": report["staging_report"],
        "failed_pages": report["failures"],
        "request_observations": (
            "Six fixed player pages, sequential at <=12 requests/minute; no API calls."
        ),
        "progression_target_discovery": {
            "Chris Peal": [70, 84, 86, 87],
            "Michael Crabtree": [80],
            "Bo Jackson": [70, 80, 83, 85, 86],
            "Peyton Bowen": [70, 80, 82, 83, 85, 86],
            "Junior Seau": [80, 82],
            "Joey Harrington": [80],
        },
        "capability_grades": {
            "population_discovery": "GOOD",
            "full_rating_vector_acquisition": "GOOD",
            "archetype_acquisition": "GOOD",
            "program_card_type_acquisition": "GOOD",
            "release_tracking": "PARTIAL",
            "market_tracking": "PARTIAL",
            "historical_progression_recovery": "PARTIAL",
        },
        "canonical_promotions": 0,
        "parser_version": CfbFanPublicAdapter.parser_version,
    }
    output = root / "data/research/cfb_fan_controlled_pilot"
    output.mkdir(parents=True, exist_ok=True)
    (output / "pilot_report.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Staged {len(cards)} Center cards from {len(pipeline.state.snapshots)} pages.")


if __name__ == "__main__":
    main()

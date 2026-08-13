"""Acquire a bounded public CFB27 population and generate inheritance research."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from operation_pancake.acquisition.cfb_fan import CfbFanPublicAdapter, parse_player_listing
from operation_pancake.acquisition.pipeline import AcquisitionPipeline, AcquisitionState
from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import BulkManifestIngestor, IngestionState, save_state
from operation_pancake.research.cfb27_inheritance import (
    build_inheritance_analysis,
    write_inheritance_artifacts,
)

TARGETS = {
    "C": 18,
    "WR": 8,
    "HB": 8,
    "CB": 8,
    "FS": 8,
    "SS": 8,
    "MIKE": 8,
    "LEDG": 4,
    "REDG": 4,
    "LT": 8,
    "LG": 8,
    "QB": 8,
    "TE": 8,
}
REQUESTS_PER_MINUTE = 12
RETRIEVED_AT = "2026-08-13T22:00:00Z"


def _fetch(url: str, last_request: float) -> tuple[bytes, float]:
    delay = 60 / REQUESTS_PER_MINUTE
    elapsed = time.monotonic() - last_request
    if last_request and elapsed < delay:
        time.sleep(delay - elapsed)
    request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise PermissionError(f"HTTP {response.status} for {url}")
        content = response.read()
    return content, time.monotonic()


def _discover(root: Path) -> tuple[list[str], dict[str, object]]:
    discovery_path = root / "data/external/cfb_fan_population_discovery.json"
    previous = (
        json.loads(discovery_path.read_text(encoding="utf-8")) if discovery_path.exists() else {}
    )
    previous_snapshots = previous.get("listing_snapshots", {})
    raw_root = root / "data/external/raw/cfb_fan_listings"
    urls: list[str] = []
    listing_snapshots = {}
    last_request = 0.0
    for position, limit in TARGETS.items():
        listing_url = f"https://cfb.fan/players/?{urlencode({'positions': position})}"
        cached = previous_snapshots.get(position)
        cached_path = root / cached["snapshot_location"] if cached else None
        if cached_path and cached_path.exists():
            content = cached_path.read_bytes()
        else:
            content, last_request = _fetch(listing_url, last_request)
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("data/external/raw/cfb_fan_listings") / f"{digest}.html"
        raw_root.mkdir(parents=True, exist_ok=True)
        if not (root / relative).exists():
            (root / relative).write_bytes(content)
        found = parse_player_listing(content.decode("utf-8"))[:limit]
        urls.extend(found)
        listing_snapshots[position] = {
            "source_url": listing_url,
            "content_sha256": digest,
            "snapshot_location": relative.as_posix(),
            "retrieved_at": RETRIEVED_AT,
            "links_selected": len(found),
        }
    payload = {
        "retrieved_at": RETRIEVED_AT,
        "requests_per_minute": REQUESTS_PER_MINUTE,
        "selection": "first displayed unique cards from each bounded position listing",
        "targets": TARGETS,
        "listing_snapshots": listing_snapshots,
        "selected_urls": list(dict.fromkeys(urls)),
    }
    discovery_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload["selected_urls"], payload


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    urls, discovery = _discover(root)
    evidence_state_path = root / "data/evidence/ingestion_state.json"
    ingestor = BulkManifestIngestor(
        build_evidence_index(root), IngestionState.load(evidence_state_path)
    )
    state_path = root / "data/external/cfb_fan_population_state.json"
    previous = AcquisitionState.load(state_path)
    cached = {
        snapshot["external_identifiers"]["source_url"]: (
            root / snapshot["snapshot_location"]
        ).read_bytes()
        for snapshot in previous.snapshots.values()
        if "source_url" in snapshot["external_identifiers"]
        and (root / snapshot["snapshot_location"]).exists()
    }
    pilot = AcquisitionState.load(root / "data/external/cfb_fan_pilot_state.json")
    cached.update(
        {
            snapshot["external_identifiers"]["source_url"]: (
                root / snapshot["snapshot_location"]
            ).read_bytes()
            for snapshot in pilot.snapshots.values()
            if "source_url" in snapshot["external_identifiers"]
        }
    )
    pipeline = AcquisitionPipeline(root, ingestor, previous)
    report = pipeline.acquire_fixture(
        CfbFanPublicAdapter(urls, cached), RETRIEVED_AT, dry_run=False
    )
    identities = {
        (
            card["player_name"].casefold(),
            card["position"],
            card["overall"],
            (card.get("archetype") or "").casefold(),
            (card.get("program") or "").casefold(),
        )
        for card in pipeline.state.cards.values()
    }
    for key, card in pilot.cards.items():
        identity = (
            card["player_name"].casefold(),
            card["position"],
            card["overall"],
            (card.get("archetype") or "").casefold(),
            (card.get("program") or "").casefold(),
        )
        if identity not in identities:
            pipeline.state.cards[key] = card
            identities.add(identity)
    pipeline.state.conflicts = {
        key: conflict
        for key, conflict in pipeline.state.conflicts.items()
        if not (
            conflict.get("types") == ["ARCHETYPE_MISMATCH"]
            and conflict.get("incoming", {}).get("archetype")
            == re.sub(r" - [A-Z]+$", "", conflict.get("existing", {}).get("archetype", ""))
        )
    }
    pipeline.save(state_path)
    save_state(evidence_state_path, ingestor.state)
    historical_leads = {
        "table_44_ability_progression_tunable_archetypes": {
            "status": "PRECISE_UNRESOLVED_LEAD",
            "repository_search": "NO_MATCH",
            "public_search": "NO_DOWNLOADABLE_SOURCE_LOCATED",
            "claimed_filename": "Table_44-_Ability_Progression_Tunable_Archetypes.xlsx",
            "claimed_contributor": "Primetime",
            "numeric_values_recovered": False,
        },
        "madden16_attribute_weights": {
            "status": "PRECISE_UNRESOLVED_LEAD",
            "repository_search": "NO_MATCH",
            "public_search": "NO_VERIFIABLE_WEIGHT_TABLE_LOCATED",
            "numeric_values_recovered": False,
        },
        "madden19": {
            "status": "EXISTING_REPOSITORY_PRIOR",
            "source": "historical frozen Center model",
            "numeric_values_recovered": True,
        },
        "madden21_public_secondary_evidence": {
            "status": "CORROBORATING_SECONDARY_EVIDENCE",
            "source_url": "https://www.reddit.com/r/MaddenUltimateTeam/comments/npchdm",
            "finding": (
                "Public 2021 archetype tables support continued archetype-specific weighting, "
                "but do not authenticate the named Table_44 workbook."
            ),
        },
        "operation_sports_historical_lead": {
            "status": "CORROBORATING_SECONDARY_EVIDENCE",
            "source_url": "https://forums.operationsports.com/forums/forum/football/madden-nfl-football/862218-guide-weightings-towards-the-ovr-for-each-attribute-at-every-position-archetype",
            "finding": (
                "Historical discussion attributes position/archetype weight extraction to game "
                "XML; retained as a lead, not primary numeric evidence."
            ),
        },
    }
    cards = list(pipeline.state.cards.values())
    analysis = build_inheritance_analysis(cards, historical_leads)
    analysis["acquisition"] = {
        "selected_urls": len(urls),
        "cards_staged": len(cards),
        "failures": report["failures"],
        "listing_positions": list(TARGETS),
        "listing_snapshots": len(discovery["listing_snapshots"]),
        "requests_per_minute": REQUESTS_PER_MINUTE,
        "canonical_promotions": 0,
    }
    write_inheritance_artifacts(root / "data/research/cfb27_inheritance_phase1", analysis)
    print(
        f"Staged {len(cards)} cards across {len(analysis['positions'])} positions; "
        f"failures={len(report['failures'])}."
    )


if __name__ == "__main__":
    main()

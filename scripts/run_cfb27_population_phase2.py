"""Expand the cached CFB27 population with bounded second-page/deep-C listings."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from operation_pancake.acquisition.cfb_fan import CfbFanPublicAdapter, parse_player_listing
from operation_pancake.acquisition.pipeline import AcquisitionPipeline, AcquisitionState
from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import BulkManifestIngestor, IngestionState, save_state

POSITIONS = (
    "C",
    "WR",
    "HB",
    "CB",
    "FS",
    "SS",
    "MIKE",
    "LEDG",
    "REDG",
    "DT",
    "LT",
    "LG",
    "RG",
    "RT",
    "QB",
    "TE",
)
LISTINGS = tuple((position, 2) for position in POSITIONS) + (("C", 3), ("C", 4))
REQUESTS_PER_MINUTE = 12
RETRIEVED_AT = "2026-08-14T00:00:00Z"


def _fetch(url: str, last_request: float) -> tuple[bytes, float]:
    delay = 60 / REQUESTS_PER_MINUTE
    elapsed = time.monotonic() - last_request
    if last_request and elapsed < delay:
        time.sleep(delay - elapsed)
    request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise PermissionError(f"HTTP {response.status} for {url}")
        return response.read(), time.monotonic()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    state_path = root / "data/external/cfb_fan_population_state.json"
    discovery_path = root / "data/external/cfb_fan_population_phase2_discovery.json"
    previous_discovery = (
        json.loads(discovery_path.read_text(encoding="utf-8")) if discovery_path.exists() else {}
    )
    listing_cache = previous_discovery.get("listing_snapshots", {})
    listing_snapshots = {}
    urls: list[str] = []
    last_request = 0.0
    for position, page in LISTINGS:
        key = f"{position}:page:{page}"
        query = urlencode({"positions": position, "page": page})
        source_url = f"https://cfb.fan/players/?{query}"
        cached = listing_cache.get(key)
        cached_path = root / cached["snapshot_location"] if cached else None
        if cached_path and cached_path.exists():
            content = cached_path.read_bytes()
        else:
            content, last_request = _fetch(source_url, last_request)
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("data/external/raw/cfb_fan_listings") / f"{digest}.html"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        if not (root / relative).exists():
            (root / relative).write_bytes(content)
        found = parse_player_listing(content.decode("utf-8"))
        urls.extend(found)
        listing_snapshots[key] = {
            "source_url": source_url,
            "content_sha256": digest,
            "snapshot_location": relative.as_posix(),
            "retrieved_at": RETRIEVED_AT,
            "links_selected": len(found),
        }
    selected_urls = list(dict.fromkeys(urls))
    discovery = {
        "retrieved_at": RETRIEVED_AT,
        "requests_per_minute": REQUESTS_PER_MINUTE,
        "selection": "all displayed unique cards from bounded page-2 listings and Center pages 3-4",
        "listing_snapshots": listing_snapshots,
        "selected_urls": selected_urls,
    }
    discovery_path.write_text(
        json.dumps(discovery, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    evidence_state_path = root / "data/evidence/ingestion_state.json"
    ingestor = BulkManifestIngestor(
        build_evidence_index(root), IngestionState.load(evidence_state_path)
    )
    previous = AcquisitionState.load(state_path)
    cached_payloads = {
        snapshot["external_identifiers"]["source_url"]: (
            root / snapshot["snapshot_location"]
        ).read_bytes()
        for snapshot in previous.snapshots.values()
        if "source_url" in snapshot["external_identifiers"]
        and (root / snapshot["snapshot_location"]).exists()
    }
    pipeline = AcquisitionPipeline(root, ingestor, previous)
    report = pipeline.acquire_fixture(
        CfbFanPublicAdapter(selected_urls, cached_payloads), RETRIEVED_AT, dry_run=False
    )
    pipeline.save(state_path)
    save_state(evidence_state_path, ingestor.state)
    print(
        f"Population now {len(pipeline.state.cards)} cards; "
        f"selected={len(selected_urls)} failures={len(report['failures'])}."
    )


if __name__ == "__main__":
    main()

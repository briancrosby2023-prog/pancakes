"""Acquire bounded deeper Center listings after the Phase-III model freeze."""

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

PAGES = (5, 6, 7, 8)
REQUESTS_PER_MINUTE = 12
RETRIEVED_AT = "2026-08-14T02:00:00Z"


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
    freeze_path = root / "data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json"
    if not freeze_path.exists():
        raise RuntimeError("Phase-III freeze must exist before acquisition.")
    snapshots, urls, last_request = {}, [], 0.0
    for page in PAGES:
        source_url = "https://cfb.fan/players/?" + urlencode({"positions": "C", "page": page})
        content, last_request = _fetch(source_url, last_request)
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("data/external/raw/cfb_fan_listings") / f"{digest}.html"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        if not (root / relative).exists():
            (root / relative).write_bytes(content)
        found = parse_player_listing(content.decode("utf-8"))
        urls.extend(found)
        snapshots[f"C:page:{page}"] = {
            "source_url": source_url,
            "content_sha256": digest,
            "snapshot_location": relative.as_posix(),
            "retrieved_at": RETRIEVED_AT,
            "links_selected": len(found),
        }
    selected = list(dict.fromkeys(urls))
    discovery = {
        "retrieved_at": RETRIEVED_AT,
        "requests_per_minute": REQUESTS_PER_MINUTE,
        "selection": "all displayed unique cards from Center listing pages 5-8",
        "listing_snapshots": snapshots,
        "selected_urls": selected,
    }
    discovery_path = root / "data/external/cfb_fan_population_phase3_discovery.json"
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
        CfbFanPublicAdapter(selected, cached_payloads), RETRIEVED_AT, dry_run=False
    )
    pipeline.save(state_path)
    save_state(evidence_state_path, ingestor.state)
    print(
        f"Population now {len(pipeline.state.cards)}; selected={len(selected)} "
        f"failures={len(report['failures'])}."
    )


if __name__ == "__main__":
    main()

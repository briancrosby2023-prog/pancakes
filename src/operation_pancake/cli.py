"""Read-only evidence discovery CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from operation_pancake.evidence.catalog import build_evidence_index
from operation_pancake.evidence.ingestion import (
    BulkManifestIngestor,
    IngestionState,
    load_manifest,
    save_report,
    save_state,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="operation-pancake")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--position")
    sources = sub.add_parser("sources")
    sources.add_argument("--status")
    sub.add_parser("unresolved")
    source = sub.add_parser("source")
    source.add_argument("source_id")
    card = sub.add_parser("card")
    card.add_argument("card_id")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("manifest", type=Path)
    ingest.add_argument("--dry-run", action="store_true")
    ingest.add_argument("--promote", action="store_true")
    sub.add_parser("reconcile")
    sub.add_parser("coverage")
    sub.add_parser("conflicts")
    sub.add_parser("incomplete")
    args = parser.parse_args()
    root = args.root.resolve()
    index = build_evidence_index(root)
    state_path = root / "data/evidence/ingestion_state.json"
    ingestor = BulkManifestIngestor(index, IngestionState.load(state_path))
    if args.command == "search":
        filters = {"positions": args.position} if args.position else {}
        result = index.search(args.query, **filters)
        manifest_result = ingestor.search(args.query)
        result["manifest_records"] = manifest_result["records"]
        result["manifest_reconciliation"] = manifest_result["reconciliation"]
        result["manifest_conflicts"] = manifest_result["conflicts"]
    elif args.command == "sources":
        result = (
            index.search(extraction_status=args.status.upper())["sources"]
            if args.status
            else index.as_dict()["sources"]
        )
    elif args.command == "unresolved":
        result = index.audit()["highest_priority_reconciliation"]
    elif args.command == "source":
        result = index.source_impact(args.source_id)
    elif args.command == "card":
        result = index.record_provenance("player_card", args.card_id)
    elif args.command == "ingest":
        manifest = load_manifest(args.manifest.resolve())
        result = ingestor.ingest(manifest, dry_run=args.dry_run, promote=args.promote)
        if not args.dry_run:
            save_state(state_path, ingestor.state)
            save_report(
                root / "data/evidence/ingestion_reports" / f"{manifest['manifest_id']}.json",
                result,
            )
    elif args.command == "reconcile":
        result = {
            "base_queue": index.audit()["highest_priority_reconciliation"],
            "manifest_resolutions": ingestor.state.as_dict()["reconciliation"],
        }
    elif args.command == "conflicts":
        result = list(ingestor.state.as_dict()["conflicts"].values())
    elif args.command == "incomplete":
        coverage = ingestor.coverage_report()
        result = {
            "incomplete_records": coverage["incomplete_records"],
            "historical_players_without_rating_vectors": coverage[
                "historical_players_without_rating_vectors"
            ],
        }
    else:
        result = ingestor.coverage_report()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

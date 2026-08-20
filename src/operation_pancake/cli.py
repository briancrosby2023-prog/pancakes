"""Read-only evidence discovery CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from operation_pancake.acquisition.adapters import FixtureAdapter
from operation_pancake.acquisition.pipeline import (
    AcquisitionPipeline,
    AcquisitionState,
    population_targets,
)
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
    sub = parser.add_subparsers(dest="command")
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
    acquire = sub.add_parser("acquire")
    acquire_sub = acquire.add_subparsers(dest="acquire_command", required=True)
    acquire_sub.add_parser("plan")
    acquire_import = acquire_sub.add_parser("import")
    acquire_import.add_argument("file", type=Path)
    acquire_import.add_argument("--dry-run", action="store_true")
    acquire_sub.add_parser("status")
    acquire_sub.add_parser("conflicts")
    gm_run = sub.add_parser("gm-run")
    gm_run.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    root = args.root.resolve()
    if args.command == "gm-run":
        from operation_pancake.production import build_production_outputs

        print(json.dumps(build_production_outputs(root, args.output_dir), indent=2, sort_keys=True))
        return
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
    elif args.command == "acquire":
        acquisition_path = root / "data/external/acquisition_state.json"
        acquisition = AcquisitionState.load(acquisition_path)
        if args.acquire_command == "plan":
            result = population_targets(root)
        elif args.acquire_command == "status":
            result = acquisition.as_dict()
        elif args.acquire_command == "conflicts":
            result = list(acquisition.as_dict()["conflicts"].values())
        else:
            payload = json.loads(args.file.resolve().read_text(encoding="utf-8"))
            discoveries = [
                {"external_card_id": str(card["external_card_id"])} for card in payload["cards"]
            ]
            fixture = FixtureAdapter(
                discoveries,
                {
                    str(card["external_card_id"]): json.dumps(card, sort_keys=True).encode()
                    for card in payload["cards"]
                },
            )
            pipeline = AcquisitionPipeline(root, ingestor, acquisition)
            result = pipeline.acquire_fixture(
                fixture, payload["retrieved_at"], dry_run=args.dry_run
            )
            if not args.dry_run:
                pipeline.save(acquisition_path)
                save_state(state_path, ingestor.state)
    else:
        result = ingestor.coverage_report()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

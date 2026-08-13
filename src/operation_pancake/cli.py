"""Read-only evidence discovery CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from operation_pancake.evidence.catalog import build_evidence_index


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
    args = parser.parse_args()
    index = build_evidence_index(args.root.resolve())
    if args.command == "search":
        filters = {"positions": args.position} if args.position else {}
        result = index.search(args.query, **filters)
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
    else:
        result = index.record_provenance("player_card", args.card_id)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Extract reproducible inventories from a public madden-franchise checkout."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

SEARCH_TERMS = (
    "ability",
    "progression",
    "tunable",
    "archetype",
    "upgrade",
    "rating",
    "threshold",
    "path",
    "overall",
    "scheme",
)


def _read(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checkout = args.checkout.resolve()
    commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={checkout}", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    schema_paths = sorted((checkout / "data/schemas").glob("*/*.gz"))
    target = root / "data/external/ea_schema_inventory"
    target.mkdir(parents=True, exist_ok=True)
    catalog = []
    inventories = {}
    for path in schema_paths:
        payload = _read(path)
        game = path.stem.split("_")[0]
        tables = []
        for schema in payload["schemas"]:
            fields = [
                {
                    "name": field.get("name"),
                    "type": field.get("type"),
                    "enum": field.get("enum"),
                }
                for field in schema.get("attributes", [])
            ]
            tables.append(
                {
                    "name": schema.get("name"),
                    "asset_id": str(schema.get("assetId"))
                    if schema.get("assetId") is not None
                    else None,
                    "base": schema.get("base"),
                    "fields": fields,
                }
            )
        inventory = {
            "source_repository": "https://github.com/bep713/madden-franchise",
            "source_commit": commit,
            "source_schema": path.relative_to(checkout).as_posix(),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "meta": payload["meta"],
            "tables": tables,
            "enum_names": sorted((payload.get("enumMap") or {}).keys()),
        }
        output = target / f"{game}_inventory.json.gz"
        with gzip.open(output, "wt", encoding="utf-8", compresslevel=9) as stream:
            json.dump(inventory, stream, separators=(",", ":"), sort_keys=True)
        inventories[game] = inventory
        catalog.append(
            {
                "game": game,
                "meta": payload["meta"],
                "tables": len(tables),
                "fields": sum(len(table["fields"]) for table in tables),
                "enums": len(inventory["enum_names"]),
                "inventory": output.relative_to(root).as_posix(),
            }
        )

    research = root / "data/research/cfb27_inheritance_phase4"
    research.mkdir(parents=True, exist_ok=True)
    games = [f"M{year}" for year in range(19, 28)] + ["C27"]
    continuity = []
    for left, right in zip(games, games[1:], strict=False):
        left_tables = {table["name"]: table for table in inventories[left]["tables"]}
        right_tables = {table["name"]: table for table in inventories[right]["tables"]}
        shared = sorted(left_tables.keys() & right_tables.keys())
        same_ids = [
            name
            for name in shared
            if left_tables[name]["asset_id"] is not None
            and left_tables[name]["asset_id"] == right_tables[name]["asset_id"]
        ]
        continuity.append(
            {
                "from": left,
                "to": right,
                "shared_table_names": len(shared),
                "unchanged_asset_ids": len(same_ids),
                "left_tables": len(left_tables),
                "right_tables": len(right_tables),
                "name_jaccard": round(
                    len(shared) / len(left_tables.keys() | right_tables.keys()), 6
                ),
                "added_tables": sorted(right_tables.keys() - left_tables.keys()),
                "removed_tables": sorted(left_tables.keys() - right_tables.keys()),
            }
        )
    player_fields = {}
    for game, inventory in inventories.items():
        player = next(table for table in inventory["tables"] if table["name"] == "Player")
        player_fields[game] = {field["name"]: field["type"] for field in player["fields"]}
    field_continuity = []
    for left, right in zip(games, games[1:], strict=False):
        old, new = player_fields[left], player_fields[right]
        field_continuity.append(
            {
                "from": left,
                "to": right,
                "persistent": sorted(old.keys() & new.keys()),
                "added": sorted(new.keys() - old.keys()),
                "removed": sorted(old.keys() - new.keys()),
                "type_changed": sorted(
                    name for name in old.keys() & new.keys() if old[name] != new[name]
                ),
            }
        )
    searches = {}
    for game, inventory in inventories.items():
        matches = []
        for table in inventory["tables"]:
            table_hit = any(term in (table["name"] or "").casefold() for term in SEARCH_TERMS)
            fields = [
                field
                for field in table["fields"]
                if any(term in (field["name"] or "").casefold() for term in SEARCH_TERMS)
            ]
            if table_hit or fields:
                matches.append(
                    {
                        "table": table["name"],
                        "asset_id": table["asset_id"],
                        "matched_fields": fields,
                    }
                )
        searches[game] = matches
    ability_progression = {}
    for game, inventory in inventories.items():
        table = next(
            (
                table
                for table in inventory["tables"]
                if table["name"] == "AbilityProgressionTunable"
            ),
            None,
        )
        ability_progression[game] = table
    source = {
        "repository": "https://github.com/bep713/madden-franchise",
        "commit": commit,
        "license": "MIT",
        "supported_games_from_bundled_schemas": games,
        "provenance": (
            "Project documentation states schemas are found within EA game files via Frosty; "
            "inventories are direct transformations of bundled schema files."
        ),
        "catalog": catalog,
    }
    for name, payload in {
        "ea_schema_sources.json": source,
        "cross_year_table_continuity.json": continuity,
        "player_field_continuity.json": field_continuity,
        "archetype_progression_schema_search.json": searches,
        "ability_progression_tunable_continuity.json": ability_progression,
    }.items():
        (research / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"Inventoried {len(inventories)} schemas at {commit[:12]}.")


if __name__ == "__main__":
    main()

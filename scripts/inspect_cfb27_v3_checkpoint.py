#!/usr/bin/env python3
"""Emit a compact schema/count summary for the large CFB.FAN V3 checkpoint."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/external/cfb_fan_population_v3_checkpoint.json"
OUTPUT = ROOT / "data/research/cfb27_alpha/v3_checkpoint_summary.json"


def _shape(value):
    if isinstance(value, dict):
        return {"type": "dict", "count": len(value), "keys": sorted(value)[:30]}
    if isinstance(value, list):
        return {"type": "list", "count": len(value)}
    return {"type": type(value).__name__}


def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    summary = {"top_level": _shape(payload)}
    if isinstance(payload, dict):
        summary["sections"] = {key: _shape(value) for key, value in payload.items()}
        cards = payload.get("cards")
        if isinstance(cards, dict):
            statuses = Counter()
            positions = Counter()
            samples = []
            for card_id, card in cards.items():
                if not isinstance(card, dict):
                    continue
                statuses[str(card.get("extraction_status"))] += 1
                positions[str(card.get("position"))] += 1
                if len(samples) < 3:
                    samples.append({
                        "id": card_id,
                        "keys": sorted(card),
                        "position": card.get("position"),
                        "status": card.get("extraction_status"),
                        "metadata_keys": sorted((card.get("metadata") or {}).keys()),
                    })
            summary["cards"] = {
                "statuses": dict(sorted(statuses.items())),
                "positions": dict(sorted(positions.items())),
                "samples": samples,
            }
        conflicts = payload.get("conflicts")
        if isinstance(conflicts, dict):
            types = Counter()
            samples = []
            for conflict_id, conflict in conflicts.items():
                if not isinstance(conflict, dict):
                    continue
                for kind in conflict.get("types", ()):
                    types[str(kind)] += 1
                if len(samples) < 5:
                    samples.append({
                        "id": conflict_id,
                        "keys": sorted(conflict),
                        "types": conflict.get("types"),
                        "external_card_id": conflict.get("external_card_id"),
                        "details": conflict.get("details"),
                    })
            summary["conflicts"] = {
                "count": len(conflicts),
                "types": dict(sorted(types.items())),
                "samples": samples,
            }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

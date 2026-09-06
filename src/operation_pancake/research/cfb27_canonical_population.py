"""Materialize the refreshed CFB.FAN population for production scoring."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_op_x_010 import _public_entities

EXPORT_NAMES = {
    "players": "players",
    "cards": "cards",
    "card_native_states": "native_states",
}


def materialize_canonical_population(root: Path) -> dict[str, int]:
    """Write only the canonical population exports read by production scoring."""
    public = _public_entities(_cards(root))
    export_dir = root / "data/research/cfb27_op_x_010/canonical_exports_v2"
    export_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for export_name, public_name in EXPORT_NAMES.items():
        payload = public[public_name]
        target = export_dir / f"{export_name}.json"
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        counts[export_name] = len(payload)
    return counts

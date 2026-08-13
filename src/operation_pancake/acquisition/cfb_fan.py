"""CFB.FAN saved-page discovery compatibility; no live endpoint assumptions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def import_saved_discoveries(path: Path) -> list[dict[str, Any]]:
    """Import historical offline discovery records with stable identifiers."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    discoveries = []
    for item in payload:
        if not item.get("season_id") or not item.get("card_id"):
            raise ValueError("CFB.FAN discoveries require season_id and card_id.")
        discoveries.append(
            {
                "external_source": "CFB_FAN",
                "season_id": str(item["season_id"]),
                "external_card_id": str(item["card_id"]),
                "external_player_id": str(item["player_id"]) if item.get("player_id") else None,
                "saved_page_reference": item["saved_page_reference"],
                "discovered_at": item["discovered_at"],
                "discovery_status": item.get("discovery_status", "DISCOVERED_OFFLINE"),
            }
        )
    return sorted(discoveries, key=lambda item: (item["season_id"], item["external_card_id"]))


class CfbFanAdapterNamespace:
    """Marker for a future validated adapter; intentionally exposes no live acquisition."""

    source_name = "CFB_FAN"
    live_access_status = "BLOCKED_UNTIL_PUBLIC_INTERFACE_VALIDATED"

"""Durable, exact-card artwork references for Pancake-owned assets."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Iterable


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def asset_filename(card_id: str, extension: str) -> str:
    """Return a Windows-safe filename deterministically keyed by card_id."""
    safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", card_id).strip("-")
    return f"{safe_id}.{extension.casefold().lstrip('.')}"


def local_art_url(asset: str | None) -> str | None:
    """Map one production asset reference to the local serving route."""
    if not isinstance(asset, str):
        return None
    path = PurePosixPath(asset)
    expected_parent = PurePosixPath("data/production/card_art")
    if path.parent != expected_parent or not path.name:
        return None
    return f"/card-art/{path.name}"


def resolve_exact_card_art(
    cards: Iterable[dict[str, Any]], player_name: str | None, program: str | None
) -> tuple[str | None, str | None]:
    """Resolve artwork only when name and observed program select one exact card."""
    if not _normalized(player_name) or not _normalized(program):
        return None, None
    matches = [
        card
        for card in cards
        if _normalized(card.get("player_name")) == _normalized(player_name)
        and _normalized(card.get("program")) == _normalized(program)
    ]
    if len(matches) != 1:
        return None, None
    card = matches[0]
    card_id = card.get("card_id")
    asset = card.get("card_art_asset")
    if not isinstance(card_id, str) or local_art_url(asset) is None:
        return None, None
    asset_path = PurePosixPath(asset)
    if asset_path.name != asset_filename(card_id, asset_path.suffix):
        return None, None
    return card_id, asset

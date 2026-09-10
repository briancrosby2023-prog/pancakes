"""One-time acquisition of validated CFB27 card art into Pancake storage."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError

from operation_pancake.card_art import asset_filename
from operation_pancake.models.cfb27_card_state import stable_id

SUPPORTED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def card_art_source_url(external_card_id: str) -> str:
    numeric_id = external_card_id.removeprefix("27-")
    return f"https://media.cfb.fan/27/cutdb/playeritem/{numeric_id}.png"


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _image_extension(payload: bytes) -> str | None:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
            return SUPPORTED_FORMATS.get(image.format or "")
    except (OSError, SyntaxError, UnidentifiedImageError):
        return None


def acquire_card_art(
    root: Path,
    card: dict[str, Any],
    *,
    fetcher: Callable[[str], bytes] = _fetch,
) -> str | None:
    """Acquire a new exact card once; valid local bytes always win thereafter."""
    source = card.get("external_source")
    external_card_id = card.get("external_card_id")
    if not isinstance(source, str) or not isinstance(external_card_id, str):
        return None
    card_id = stable_id("card", source, external_card_id)
    art_root = root / "data/production/card_art"
    for extension in SUPPORTED_FORMATS.values():
        existing = art_root / asset_filename(card_id, extension)
        if existing.is_file() and _image_extension(existing.read_bytes()) == extension:
            return existing.relative_to(root).as_posix()
        page_asset = art_root / (
            Path(asset_filename(card_id, extension)).stem + "-page." + extension
        )
        if page_asset.is_file() and _image_extension(page_asset.read_bytes()) == extension:
            return page_asset.relative_to(root).as_posix()
    payload = fetcher(card_art_source_url(external_card_id))
    extension = _image_extension(payload)
    if extension is None:
        return None
    art_root.mkdir(parents=True, exist_ok=True)
    target = art_root / asset_filename(card_id, extension)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return target.relative_to(root).as_posix()


def existing_card_art_asset(root: Path, card: dict[str, Any]) -> str | None:
    """Return a validated local asset for an exact canonical card, if present."""
    source = card.get("external_source")
    external_card_id = card.get("external_card_id")
    if not isinstance(source, str) or not isinstance(external_card_id, str):
        return None
    card_id = stable_id("card", source, external_card_id)
    art_root = root / "data/production/card_art"
    for extension in SUPPORTED_FORMATS.values():
        path = art_root / asset_filename(card_id, extension)
        if path.is_file() and _image_extension(path.read_bytes()) == extension:
            return path.relative_to(root).as_posix()
        page_asset = art_root / (
            Path(asset_filename(card_id, extension)).stem + "-page." + extension
        )
        if page_asset.is_file() and _image_extension(page_asset.read_bytes()) == extension:
            return page_asset.relative_to(root).as_posix()
    return None

"""Fail-open persistence for the four screenshots behind a C-3PO roster."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from operation_pancake.c3po_roster import C3PORoster

IMAGE_COUNT = 4
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class C3POSourceImage:
    order: int
    mime_type: str
    payload: bytes


@dataclass(frozen=True)
class C3POSourceEvidence:
    roster_fingerprint: str
    images: tuple[C3POSourceImage, ...]


def roster_fingerprint(roster: C3PORoster) -> str:
    payload = {
        "players": [asdict(player) for player in roster.players],
        "provider": roster.provider,
        "model": roster.model,
        "status": roster.status,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _image_mime(payload: bytes, suffix: str | None = None) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    if suffix and suffix.casefold() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix and suffix.casefold() in {".png", ".webp"}:
        return f"image/{suffix.casefold().lstrip('.')}"
    raise ValueError("Unsupported screenshot image data")


class C3POSourceEvidenceStore:
    """Atomic, bounded archive kept separately from the raw roster."""

    def __init__(self, path: Path):
        self.path = path

    def save(self, roster: C3PORoster, screenshots: Iterable[Path]) -> None:
        paths = tuple(screenshots)
        if len(paths) != IMAGE_COUNT:
            raise ValueError("Source evidence requires exactly four screenshots")
        images = []
        total = 0
        for order, path in enumerate(paths):
            payload = path.read_bytes()
            if not payload or len(payload) > MAX_IMAGE_BYTES:
                raise ValueError("Screenshot evidence size is invalid")
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Screenshot evidence total size is invalid")
            images.append(
                {
                    "order": order,
                    "mime_type": _image_mime(payload, path.suffix),
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "payload": payload,
                }
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            manifest = {
                "version": 1,
                "roster_fingerprint": roster_fingerprint(roster),
                "images": [
                    {key: value for key, value in image.items() if key != "payload"}
                    for image in images
                ],
            }
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as bundle:
                bundle.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
                for image in images:
                    bundle.writestr(f"images/{image['order']}.bin", image["payload"])
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load_for(self, roster: C3PORoster) -> C3POSourceEvidence | None:
        try:
            with zipfile.ZipFile(self.path) as bundle:
                manifest = json.loads(bundle.read("manifest.json"))
                rows = manifest["images"]
                if (
                    manifest.get("version") != 1
                    or manifest.get("roster_fingerprint") != roster_fingerprint(roster)
                    or not isinstance(rows, list)
                    or len(rows) != IMAGE_COUNT
                ):
                    return None
                images = []
                total = 0
                for expected_order, row in enumerate(rows):
                    if not isinstance(row, dict) or row.get("order") != expected_order:
                        return None
                    payload = bundle.read(f"images/{expected_order}.bin")
                    total += len(payload)
                    if (
                        not payload
                        or len(payload) > MAX_IMAGE_BYTES
                        or total > MAX_TOTAL_BYTES
                        or row.get("size") != len(payload)
                        or row.get("sha256") != hashlib.sha256(payload).hexdigest()
                        or row.get("mime_type")
                        not in {"image/jpeg", "image/png", "image/webp"}
                    ):
                        return None
                    images.append(
                        C3POSourceImage(expected_order, row["mime_type"], payload)
                    )
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
            zipfile.BadZipFile,
        ):
            return None
        return C3POSourceEvidence(manifest["roster_fingerprint"], tuple(images))

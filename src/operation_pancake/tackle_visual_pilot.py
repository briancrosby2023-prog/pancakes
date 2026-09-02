"""Bounded CFB27 LT/RT visual+text recognition pilot.

The pilot deliberately does not alter the production lineup matcher.  It builds an
auditable tackle-only index from the checked-in CFB.FAN CFB27 snapshots and uses
real card-art and portrait pixels as an independent ranking signal.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

POSITIONS = {"LT", "RT"}


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _program(row: dict) -> str:
    value = row.get("program")
    return str(value.get("name") or "") if isinstance(value, dict) else str(value or "")


def _url(row: dict, key: str) -> str | None:
    value = row.get(key)
    return value.get("url") if isinstance(value, dict) else None


@dataclass(frozen=True)
class TackleCard:
    external_id: str
    canonical_card_id: str | None
    player_name: str
    position: str
    overall: int
    program: str
    season: str
    card_image_url: str
    portrait_url: str | None
    border_url: str | None
    program_image_url: str | None
    team_image_url: str | None
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class VisualFingerprint:
    color: tuple[float, ...]
    spatial: tuple[float, ...]
    dhash: int
    edge_hash: int


@dataclass(frozen=True)
class IndexedTackle:
    card: TackleCard
    fingerprint: VisualFingerprint
    image_sha256: str
    portrait_sha256: str | None


def load_cards(
    raw_dir: Path, population_path: Path, positions: set[str] | None = None
) -> list[TackleCard]:
    """Load every unique CFB27 LT/RT card and link it to production metadata."""
    population = json.loads(population_path.read_text(encoding="utf-8"))
    canonical: dict[tuple[str, str, int, str], list[str]] = {}
    for row in population:
        key = (
            _norm(row.get("player_name")),
            str(row.get("position") or "").upper(),
            int(row.get("native_overall") or 0),
            _norm(row.get("program")),
        )
        canonical.setdefault(key, []).append(row.get("card_id"))

    eligible_positions = POSITIONS if positions is None else {value.upper() for value in positions}
    raw: dict[str, dict] = {}
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("data", []):
            position = ((row.get("position") or {}).get("abbreviation") or "").upper()
            if str(row.get("gameSlug")) == "27" and position in eligible_positions:
                raw[str(row["externalId"])] = row

    cards = []
    for external_id, row in sorted(raw.items(), key=lambda item: int(item[0])):
        position = row["position"]["abbreviation"].upper()
        name = " ".join(x for x in (row.get("firstName"), row.get("lastName")) if x).strip()
        program = _program(row)
        key = (_norm(name), position, int(row["overall"]), _norm(program))
        ids = [value for value in canonical.get(key, []) if value]
        # A non-unique metadata join is not silently guessed.
        canonical_id = ids[0] if len(ids) == 1 else None
        image_url = _url(row, "fullImage") or _url(row, "image")
        portrait_url = _url(row.get("portrait") or {}, "image")
        border_url = _url(row, "borderImage")
        program_image_url = _url(row.get("program") or {}, "image")
        team_image_url = _url(row.get("team") or {}, "image")
        if not image_url:
            continue
        aliases = tuple(dict.fromkeys(filter(None, (_norm(name), _norm(row.get("lastName"))))))
        cards.append(
            TackleCard(
                external_id,
                canonical_id,
                name,
                position,
                int(row["overall"]),
                program,
                "CFB27",
                image_url,
                portrait_url,
                border_url,
                program_image_url,
                team_image_url,
                aliases,
            )
        )
    return cards


def _download(url: str, cache_dir: Path) -> tuple[bytes, Path]:
    suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
    target = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}{suffix}"
    if not target.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "Operation-Pancake/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
    return target.read_bytes(), target


def compose_card(
    card_bytes: bytes,
    portrait_bytes: bytes | None,
    border_bytes: bytes | None = None,
    program_bytes: bytes | None = None,
    team_bytes: bytes | None = None,
) -> Image.Image:
    """Compose the two independent CFB27 visual layers without adding text."""
    with Image.open(io.BytesIO(card_bytes)) as source:
        canvas = source.convert("RGBA").resize((240, 321), Image.Resampling.LANCZOS)
    if portrait_bytes:
        with Image.open(io.BytesIO(portrait_bytes)) as source:
            portrait = source.convert("RGBA")
        portrait.thumbnail((218, 218), Image.Resampling.LANCZOS)
        canvas.alpha_composite(portrait, ((240 - portrait.width) // 2, 73))
    if border_bytes:
        with Image.open(io.BytesIO(border_bytes)) as source:
            border = source.convert("RGBA").resize((240, 321), Image.Resampling.LANCZOS)
        canvas.alpha_composite(border)
    for raw, size, xy in (
        (program_bytes, (46, 46), (15, 251)),
        (team_bytes, (42, 42), (183, 254)),
    ):
        if raw:
            with Image.open(io.BytesIO(raw)) as source:
                badge = source.convert("RGBA")
            badge.thumbnail(size, Image.Resampling.LANCZOS)
            canvas.alpha_composite(badge, xy)
    return canvas.convert("RGB")


def _bits(image: Image.Image, edge: bool = False) -> int:
    gray = ImageOps.grayscale(image)
    if edge:
        gray = gray.filter(ImageFilter.FIND_EDGES)
    gray = gray.resize((17, 16), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    value = 0
    for y in range(16):
        for x in range(16):
            value = (value << 1) | (pixels[y * 17 + x] > pixels[y * 17 + x + 1])
    return value


def fingerprint(image: Image.Image) -> VisualFingerprint:
    rgb = image.convert("RGB").resize((64, 80), Image.Resampling.LANCZOS)
    hist = rgb.histogram()
    color = []
    for channel in range(3):
        bins = hist[channel * 256 : (channel + 1) * 256]
        total = max(sum(bins), 1)
        color.extend(sum(bins[index : index + 32]) / total for index in range(0, 256, 32))
    spatial = []
    for gy in range(5):
        for gx in range(4):
            region = rgb.crop((gx * 16, gy * 16, (gx + 1) * 16, (gy + 1) * 16))
            means = Image.Image.getextrema(region)
            # Midpoint of extrema is robust to JPEG and modest overlays.
            spatial.extend((low + high) / 510 for low, high in means)
    return VisualFingerprint(tuple(color), tuple(spatial), _bits(rgb), _bits(rgb, edge=True))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    denom = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return dot / denom if denom else 0.0


def visual_score(left: VisualFingerprint, right: VisualFingerprint) -> float:
    dhash = 1 - (left.dhash ^ right.dhash).bit_count() / 256
    edge = 1 - (left.edge_hash ^ right.edge_hash).bit_count() / 256
    score = (
        0.32 * _cosine(left.color, right.color)
        + 0.38 * _cosine(left.spatial, right.spatial)
        + 0.18 * dhash
        + 0.12 * edge
    )
    return max(0.0, min(1.0, score))


def build_index(cards: list[TackleCard], cache_dir: Path) -> list[IndexedTackle]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    urls = sorted(
        {
            url
            for card in cards
            for url in (
                card.card_image_url,
                card.portrait_url,
                card.border_url,
                card.program_image_url,
                card.team_image_url,
            )
            if url
        }
    )
    failures = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_download, url, cache_dir): url for url in urls}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                failures[futures[future]] = str(exc)
    index = []
    for card in cards:
        if card.card_image_url in failures:
            continue
        card_bytes, _ = _download(card.card_image_url, cache_dir)
        portrait_bytes = None
        if card.portrait_url:
            try:
                portrait_bytes, _ = _download(card.portrait_url, cache_dir)
            except Exception:  # a missing portrait retains usable card-art evidence
                portrait_bytes = None
        layers = []
        for url in (card.border_url, card.program_image_url, card.team_image_url):
            try:
                layers.append(_download(url, cache_dir)[0] if url else None)
            except Exception:
                layers.append(None)
        image = compose_card(card_bytes, portrait_bytes, *layers)
        index.append(
            IndexedTackle(
                card,
                fingerprint(image),
                hashlib.sha256(card_bytes).hexdigest(),
                hashlib.sha256(portrait_bytes).hexdigest() if portrait_bytes else None,
            )
        )
    return index


def _name_score(observed: str | None, card: TackleCard) -> float:
    value = _norm(observed)
    if not value:
        return 0.0
    return max(SequenceMatcher(None, value, alias).ratio() for alias in card.aliases)


def rank(
    index: list[IndexedTackle],
    query: VisualFingerprint | None,
    observed_name: str | None,
    observed_ovr: int | None,
    position: str,
) -> list[dict]:
    output = []
    for item in index:
        position_score = 1.0 if item.card.position == position.upper() else 0.0
        if not position_score:
            continue
        visual = visual_score(query, item.fingerprint) if query else 0.0
        name = _name_score(observed_name, item.card)
        if observed_ovr is None:
            ovr = 0.0
        else:
            delta = abs(item.card.overall - observed_ovr)
            ovr = 1.0 if delta == 0 else 0.55 if delta == 1 else 0.15 if delta == 2 else 0.0
        # Visual remains the largest single signal and can retrieve without OCR.
        final = 0.52 * visual + 0.26 * name + 0.14 * ovr + 0.08 * position_score
        output.append(
            {
                "external_id": item.card.external_id,
                "canonical_card_id": item.card.canonical_card_id,
                "player_name": item.card.player_name,
                "position": item.card.position,
                "overall": item.card.overall,
                "program": item.card.program,
                "visual": round(visual, 6),
                "name": round(name, 6),
                "ovr": round(ovr, 6),
                "position_score": position_score,
                "final": round(final, 6),
            }
        )
    return sorted(output, key=lambda row: (row["final"], row["visual"], row["name"]), reverse=True)


def resolve(ranking: list[dict], threshold: float = 0.61, margin: float = 0.035) -> dict | None:
    if not ranking:
        return None
    runner_up = ranking[1]["final"] if len(ranking) > 1 else 0.0
    if ranking[0]["final"] < threshold or ranking[0]["final"] - runner_up < margin:
        return None
    return ranking[0]

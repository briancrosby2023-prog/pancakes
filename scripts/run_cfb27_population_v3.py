"""Restartable public CFB.FAN global-listing acquisition for OP-X-012."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

LAST_PAGE = 590
REQUESTS_PER_MINUTE = 12
RETRIEVED_AT = "2026-08-14T12:00:00Z"
BASE_URL = "https://cfb.fan"
POSITION_ALIASES = {"MIKE": "MLB", "LEDG": "LE", "REDG": "RE"}


def _text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_listing(html: str, snapshot: str) -> list[dict]:
    """Parse public listing summaries without claiming a full vector."""
    cards = []
    for segment in html.split('<div class="player-list-item"')[1:]:
        url = re.search(
            r'<a href="(?P<url>/players/(?P<player>\d+)-[^/]+/(?P<card>27-[^/]+)/)"', segment
        )
        ovr = re.search(r'player-list-item__score-value">\s*(\d+)\s*</div>', segment)
        first = re.search(r'player-list-item__name-first">(.*?)</div>', segment, re.DOTALL)
        last = re.search(r"player-list-item__name-last[^>]*>\s*(.*?)\s*</div>", segment, re.DOTALL)
        program = re.search(r'player-list-item__program">(.*?)</div>', segment, re.DOTALL)
        archetype = re.search(r'player-list-item__archetype">\s*(.*?)\s*</div>', segment, re.DOTALL)
        if not all((url, ovr, first, last, program, archetype)):
            continue
        summary = _text(archetype.group(1))
        position, _, archetype_name = summary.partition(" - ")
        ratings = {
            name: int(value)
            for name, value in re.findall(
                r'player-list-item__stat-name">\s*([A-Z0-9]+)\s*</div>.*?'
                r'player-list-item__stat-value">\s*(\d+)\s*</div>',
                segment,
                re.DOTALL,
            )
        }
        external_id = url.group("card").removeprefix("27-")
        cards.append(
            {
                "external_source": "CFB_FAN",
                "external_player_id": url.group("player"),
                "external_card_id": external_id,
                "player_name": f"{_text(first.group(1))} {_text(last.group(1))}",
                "position": POSITION_ALIASES.get(position, position),
                "overall": int(ovr.group(1)),
                "archetype": archetype_name or None,
                "program": _text(program.group(1)),
                "card_type": "CUT",
                "team_school": None,
                "release_date": None,
                "displayed_ratings": dict(sorted(ratings.items())),
                "source_reference": f"{BASE_URL}{url.group('url')}",
                "retrieval_timestamp": RETRIEVED_AT,
                "raw_snapshot_reference": snapshot,
                "extraction_status": "PARTIAL_LISTING_VECTOR",
                "validation_status": "VALIDATED_PUBLIC_LISTING_IDENTITY",
                "market_observations": [],
                "metadata": {"listing_derived": True},
            }
        )
    return cards


def _save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fetch(url: str, attempts: int = 3) -> bytes:
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
            with urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - bounded and persisted by caller
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Acquisition failed after {attempts} attempts: {last_error}")


def pages_to_fetch(refresh_pages: int) -> range:
    """Return the full initial range or the newest bounded refresh range."""
    if refresh_pages:
        return range(max(1, LAST_PAGE - refresh_pages + 1), LAST_PAGE + 1)
    return range(1, LAST_PAGE + 1)


def merge_listing_cards(state: dict, cards: dict[str, dict]) -> dict[str, int]:
    """Merge new listing identities without replacing complete detail records."""
    added = conflicts = 0
    conflict_fields = ("player_name", "position", "overall", "program", "archetype")
    for external_id, card in cards.items():
        key = f"CFB_FAN:{external_id}"
        if key not in state["cards"]:
            state["cards"][key] = card
            added += 1
            continue
        existing = state["cards"][key]
        if existing.get("extraction_status") == "PARTIAL_LISTING_VECTOR":
            existing["validation_status"] = "VALIDATED_PUBLIC_LISTING_IDENTITY"
        differences = {
            field: {"existing": existing.get(field), "listing": card.get(field)}
            for field in conflict_fields
            if existing.get(field) != card.get(field)
        }
        if differences:
            state["conflicts"][f"V3:{external_id}"] = {
                "type": "SOURCE_RECORD_CONFLICT",
                "source": card["source_reference"],
                "differences": differences,
                "resolution": "PRESERVE_COMPLETE_DETAIL_RECORD",
            }
            conflicts += 1
    return {"added": added, "conflicts": conflicts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-pages",
        type=int,
        default=0,
        help="Recheck only the newest N pages after the initial complete enumeration.",
    )
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="Merge the persisted checkpoint without making network requests.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checkpoint_path = root / "data/external/cfb_fan_population_v3_checkpoint.json"
    state_path = root / "data/external/cfb_fan_population_state.json"
    raw_root = root / "data/external/raw/cfb_fan_global_listings"
    raw_root.mkdir(parents=True, exist_ok=True)
    checkpoint = (
        json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint_path.exists()
        else {"pages": {}, "cards": {}, "failures": []}
    )
    delay = 60 / REQUESTS_PER_MINUTE
    last_request = 0.0
    pages = range(0) if args.finalize_only else pages_to_fetch(args.refresh_pages)
    for page in pages:
        key = str(page)
        if key in checkpoint["pages"] and not args.refresh_pages:
            continue
        elapsed = time.monotonic() - last_request
        if last_request and elapsed < delay:
            time.sleep(delay - elapsed)
        url = f"{BASE_URL}/players/?page={page}"
        try:
            content = _fetch(url)
            last_request = time.monotonic()
            digest = hashlib.sha256(content).hexdigest()
            relative = Path("data/external/raw/cfb_fan_global_listings") / f"{digest}.html"
            target = root / relative
            if not target.exists():
                target.write_bytes(content)
            cards = parse_listing(content.decode("utf-8"), relative.as_posix())
            for card in cards:
                checkpoint["cards"][card["external_card_id"]] = card
            checkpoint["pages"][key] = {
                "url": url,
                "sha256": digest,
                "snapshot": relative.as_posix(),
                "cards": len(cards),
            }
        except Exception as exc:  # noqa: BLE001 - persisted bounded acquisition failure
            checkpoint["failures"].append({"page": page, "url": url, "error": str(exc)})
        _save(checkpoint_path, checkpoint)
        if page % 10 == 0 or page == LAST_PAGE:
            print(f"page={page}/{LAST_PAGE} unique={len(checkpoint['cards'])}", flush=True)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for card in checkpoint["cards"].values():
        if card.get("extraction_status") == "PARTIAL_LISTING_VECTOR":
            card["validation_status"] = "VALIDATED_PUBLIC_LISTING_IDENTITY"
    merge_listing_cards(state, checkpoint["cards"])
    completed_page = max((int(page) for page in checkpoint["pages"]), default=0)
    state["resume_cursor"] = f"global-page-{completed_page}"
    _save(state_path, state)
    print(
        f"Population now {len(state['cards'])}; enumerated={len(checkpoint['cards'])}; "
        f"failures={len(checkpoint['failures'])}."
    )


if __name__ == "__main__":
    main()

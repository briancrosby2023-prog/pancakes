"""CFB.FAN saved-page discovery compatibility; no live endpoint assumptions."""

from __future__ import annotations

import json
import re
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from operation_pancake.acquisition.adapters import AccessPolicy, ExternalCardAdapter
from operation_pancake.acquisition.models import ExternalCard, RawSnapshot

PARSER_VERSION = "cfb-fan-html-v1"


def _text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_player_page(html: str, source_url: str, retrieved_at: str, snapshot: str) -> ExternalCard:
    """Parse fields exposed by one public CFB.FAN CFB27 player page."""
    title_match = re.search(r"<title>.*?(?P<overall>\d{2}) OVR - College Football 27", html)
    header_match = re.search(
        r'<h1 class="player-header__name[^>]*>(?P<header>.*?)'
        r'<span class="player-header__ovr">',
        html,
        re.DOTALL,
    )
    meta_match = re.search(
        r'player-header__meta.*?positions=(?P<position>[^"&]+)"[^>]*>.*?</a>.*?'
        r'program_id=\d+"[^>]*>(?P<program>.*?)</a>',
        html,
        re.DOTALL,
    )
    if not title_match or not header_match or not meta_match:
        raise ValueError("Not a recognized CFB.FAN CFB27 player page.")
    player = " ".join(unescape(re.sub(r"<[^>]+>", "", header_match.group("header"))).split())
    program = _text(meta_match.group("program"))
    overall = int(title_match.group("overall"))
    position = _text(meta_match.group("position"))
    ratings_html = html
    general_index = html.find(">General</")
    team_index = html.find('text-lighter-gray">Team</div>', general_index)
    if general_index >= 0 and team_index > general_index:
        ratings_html = html[general_index:team_index]
    rating_pairs = re.findall(
        r'<span class="rating__label">\s*([A-Z0-9]+)\s*</span>.*?'
        r'<span class="rating__value"[^>]*>\s*(\d+)\s*</span>',
        ratings_html,
        re.DOTALL,
    )
    ratings: dict[str, int] = {}
    for name, value in rating_pairs:
        ratings.setdefault(name, int(value))
    archetype_match = re.search(
        r"text-lighter-gray\">Archetype</div>\s*<div[^>]*>\s*(.*?)\s*</div>", html, re.DOTALL
    )
    team_match = re.search(
        r"text-lighter-gray\">Team</div>\s*<div[^>]*>(.*?)</div>", html, re.DOTALL
    )
    date_match = re.search(
        r"text-lighter-gray\">Date Added</div>\s*<div[^>]*>\s*([^<]*)</div>", html
    )
    ids = re.search(r"/players/(\d+)-[^/]+/(27-[^/]+)/?", source_url)
    if not ids:
        ids = re.search(r"/players/(\d+)-[^/]+/?", source_url)
    external_player_id = ids.group(1) if ids else None
    compare_id = re.search(r'href="/compare/#(\d+)"', html)
    external_card_id = (
        ids.group(2)
        if ids and ids.lastindex and ids.lastindex >= 2
        else compare_id.group(1)
        if compare_id
        else source_url.rstrip("/").split("/")[-1]
    )
    archetype = (
        _text(archetype_match.group(1)).removesuffix(f" - {position}") if archetype_match else None
    )
    return ExternalCard(
        external_source="CFB_FAN",
        external_player_id=external_player_id,
        external_card_id=external_card_id,
        player_name=player,
        position=position,
        overall=overall,
        archetype=archetype,
        program=program,
        card_type="CUT",
        team_school=_text(team_match.group(1)) or None if team_match else None,
        release_date=_text(date_match.group(1)) or None if date_match else None,
        displayed_ratings=ratings,
        source_reference=source_url,
        retrieval_timestamp=retrieved_at,
        raw_snapshot_reference=snapshot,
        extraction_status="COMPLETE" if ratings else "PARTIAL",
        validation_status="STAGED_EXTERNAL_PUBLIC_SOURCE",
    )


class CfbFanPublicAdapter(ExternalCardAdapter):
    """Small-list public HTML adapter with no API or crawl discovery."""

    source_name = "CFB_FAN"
    parser_version = PARSER_VERSION
    access_policy = AccessPolicy(requests_per_minute=12, max_retries=2)

    def __init__(self, urls: list[str], cached_payloads: dict[str, bytes] | None = None) -> None:
        self.urls = urls
        self.cached_payloads = cached_payloads or {}
        self._last_request = 0.0

    def discover_cards(self):
        return [
            {"external_card_id": url.rstrip("/").split("/")[-1], "source_url": url}
            for url in self.urls
        ]

    def fetch_card(self, discovery):
        if discovery["source_url"] in self.cached_payloads:
            return self.cached_payloads[discovery["source_url"]]
        delay = 60 / self.access_policy.requests_per_minute
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < delay:
            time.sleep(delay - elapsed)
        request = Request(
            discovery["source_url"], headers={"User-Agent": "OperationPancakePilot/1.0"}
        )
        with urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise PermissionError(f"HTTP {response.status}")
            content = response.read()
        self._last_request = time.monotonic()
        return content

    def parse_card(self, snapshot: RawSnapshot, content: bytes):
        return {
            "html": content.decode("utf-8"),
            "source_url": snapshot.external_identifiers["source_url"],
        }

    def normalize_card(self, parsed, snapshot):
        return parse_player_page(
            parsed["html"], parsed["source_url"], snapshot.retrieved_at, snapshot.snapshot_location
        )


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

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

PARSER_VERSION = "cfb-fan-html-v2-cfb27-native-positions"


def parse_player_listing(html: str, base_url: str = "https://cfb.fan") -> list[str]:
    """Return stable CFB27 player URLs from a public listing, in displayed order."""
    paths = re.findall(r'href="(?P<path>/players/\d+-[^"/]+/(?:27-[^"/]+/)?)"', html)
    urls: list[str] = []
    for path in paths:
        url = f"{base_url}{path}"
        if url not in urls:
            urls.append(url)
    return urls


def _text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_player_page(html: str, source_url: str, retrieved_at: str, snapshot: str) -> ExternalCard:
    """Parse fields exposed by one public CFB.FAN CFB27 player page.

    Alpha preserves the position label displayed by CFB.FAN/CFB27. Historical
    Madden/NFL aliases such as MLB/LE/RE are not canonicalized here.
    """
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
        re.sub(r" - [A-Z]+$", "", _text(archetype_match.group(1))) if archetype_match else None
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
        team=_text(team_match.group(1)) if team_match else None,
        date_added=_text(date_match.group(1)) if date_match else None,
        ratings=ratings,
        source_url=source_url,
        retrieved_at=retrieved_at,
        raw_snapshot=snapshot,
        parser_version=PARSER_VERSION,
    )


class CfbFanAdapter(ExternalCardAdapter):
    """Optional live fetch plus deterministic saved-page parsing for CFB.FAN."""

    source_name = "CFB_FAN"

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self.snapshot_dir = snapshot_dir or Path("data/raw/cfb_fan")

    def discover(self, query: str, policy: AccessPolicy) -> list[str]:
        html = self._fetch(query, policy)
        return parse_player_listing(html)

    def fetch(self, external_id: str, policy: AccessPolicy) -> RawSnapshot:
        url = external_id
        html = self._fetch(url, policy)
        snapshot_path = self.snapshot_dir / f"{int(time.time())}.html"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(html, encoding="utf-8")
        return RawSnapshot(
            source=self.source_name,
            source_url=url,
            retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            content=html,
            snapshot_path=str(snapshot_path),
        )

    def parse(self, raw_snapshot: RawSnapshot) -> list[ExternalCard]:
        return [
            parse_player_page(
                raw_snapshot.content,
                raw_snapshot.source_url,
                raw_snapshot.retrieved_at,
                raw_snapshot.snapshot_path,
            )
        ]

    def _fetch(self, url: str, policy: AccessPolicy) -> str:
        request = Request(url, headers={"User-Agent": policy.user_agent})
        with urlopen(request, timeout=policy.timeout_seconds) as response:
            payload = response.read()
        return payload.decode("utf-8", errors="replace")


def save_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

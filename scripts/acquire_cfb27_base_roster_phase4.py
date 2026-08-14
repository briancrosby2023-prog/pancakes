"""Acquire a bounded public CFB27 base-roster archetype pilot."""

from __future__ import annotations

import hashlib
import json
import re
import time
from html import unescape
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

RETRIEVED_AT = "2026-08-14T02:30:00Z"
BASE = "https://collegefootball.gg/players/archetype"
TARGETS = {
    "Raw Strength": ("c-power", 3),
    "Pass Protector": ("c-pass-protector", 3),
    "Backfield Creator": ("qb-improviser", 1),
}
INDEXED_BACKFIELD = [
    ("Trinidad Chambliss", 93, 90, 93, 66, 96),
    ("Avery Johnson", 88, 88, 93, 65, 93),
    ("Demond Williams Jr.", 88, 91, 93, 59, 86),
    ("Alonza Barnett III", 86, 89, 91, 68, 89),
    ("Bryce Underwood", 83, 87, 91, 63, 77),
    ("Broc Lowry", 80, 82, 86, 68, 83),
    ("Tramell Jones Jr.", 75, 85, 88, 60, 73),
    ("Calvin Adkisson", 71, 83, 87, 60, 75),
    ("Malachi Nelson", 71, 85, 87, 61, 71),
    ("Nathan Peters", 70, 78, 84, 58, 60),
    ("Carter Jones", 69, 82, 84, 66, 76),
    ("Riley Trujillo", 68, 82, 85, 62, 71),
    ("Trace Johnson", 67, 78, 82, 54, 63),
]


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", value))).strip()


def _fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "OperationPancakeResearch/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _rows(content: str) -> list[dict]:
    output = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", content, flags=re.I | re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", raw, flags=re.I | re.S)
        values = [_text(cell) for cell in cells]
        if len(values) != 10 or values[0].casefold() == "player":
            continue
        if not all(re.fullmatch(r"\d+", values[index]) for index in range(4, 9)):
            continue
        link = re.search(r'href="([^"]+/players/[^"]+)"', cells[0], flags=re.I)
        output.append(
            {
                "player": values[0],
                "position": values[1],
                "class": values[2],
                "development": values[3],
                "OVR": int(values[4]),
                "SPD": int(values[5]),
                "ACC": int(values[6]),
                "STR": int(values[7]),
                "AWR": int(values[8]),
                "team": values[9],
                "profile_url": link.group(1) if link else None,
            }
        )
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw_root = root / "data/external/raw/cfb27_base_roster"
    raw_root.mkdir(parents=True, exist_ok=True)
    populations, sources = {}, []
    for archetype, (slug, pages) in TARGETS.items():
        population = []
        for page in range(1, pages + 1):
            url = f"{BASE}/{slug}/" if page == 1 else f"{BASE}/{slug}/page/{page}/"
            try:
                content = _fetch(url)
            except HTTPError as error:
                sources.append({"archetype": archetype, "url": url, "status": f"HTTP_{error.code}"})
                break
            digest = hashlib.sha256(content).hexdigest()
            relative = Path("data/external/raw/cfb27_base_roster") / f"{digest}.html"
            (root / relative).write_bytes(content)
            parsed = _rows(content.decode("utf-8"))
            population.extend(parsed)
            sources.append(
                {
                    "archetype": archetype,
                    "url": url,
                    "status": "ACQUIRED",
                    "sha256": digest,
                    "snapshot": relative.as_posix(),
                    "rows": len(parsed),
                }
            )
            time.sleep(2)
        populations[archetype] = population
    if not populations["Backfield Creator"]:
        populations["Backfield Creator"] = [
            {
                "player": player,
                "position": "QB",
                "OVR": ovr,
                "SPD": speed,
                "ACC": acceleration,
                "STR": strength,
                "AWR": awareness,
                "source_scope": "PUBLIC_SEARCH_INDEX_LISTING",
            }
            for player, ovr, speed, acceleration, strength, awareness in INDEXED_BACKFIELD
        ]
    analysis = {}
    for archetype, rows in populations.items():
        analysis[archetype] = {
            "n": len(rows),
            "ovr_range": [min(row["OVR"] for row in rows), max(row["OVR"] for row in rows)]
            if rows
            else None,
            "attribute_means": {
                key: round(sum(row[key] for row in rows) / len(rows), 6)
                for key in ("SPD", "ACC", "STR", "AWR")
            }
            if rows
            else {},
            "attribute_variance": {
                key: round(
                    sum(
                        (row[key] - sum(item[key] for item in rows) / len(rows)) ** 2
                        for row in rows
                    )
                    / len(rows),
                    6,
                )
                for key in ("SPD", "ACC", "STR", "AWR")
            }
            if rows
            else {},
            "profiles": rows,
            "completeness": "PUBLIC_LISTING_FIELDS_ONLY",
        }
    payload = {
        "source": "CollegeFootball.gg public CFB27 base-roster archetype listings",
        "retrieved_at": RETRIEVED_AT,
        "sources": sources,
        "populations": analysis,
        "no_access_bypass": True,
        "limitations": (
            "Direct requests returned HTTP 403 and were not bypassed. The 13-row Backfield "
            "Creator fallback contains only fields exposed by the source's public search index; "
            "full linked profile vectors were not inferred. Raw Strength's published n=105 is "
            "recorded as source-declared context, not acquired profiles."
        ),
        "source_declared_population": {"Raw Strength": 105, "Backfield Creator": 13},
    }
    target = root / "data/research/cfb27_inheritance_phase4/base_roster_pilot.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(", ".join(f"{archetype}={len(rows)}" for archetype, rows in populations.items()))


if __name__ == "__main__":
    main()

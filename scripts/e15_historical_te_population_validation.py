#!/usr/bin/env python3
"""Acquire and validate historical CFB.FAN tight-end populations for E.15."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://cfb.fan"
OUT = Path("data/research/cfb27_e15/historical_validation")
TITLE_RE = re.compile(r"(?P<name>.+?)\s+(?P<ovr>\d{2})\s+OVR", re.I)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def get(session: requests.Session, url: str, pause: float) -> str:
    last = None
    for attempt in range(7):
        try:
            r = session.get(url, timeout=30, headers={"User-Agent": "Operation-Pancake-research/1.0"})
            last = r.status_code
            if r.status_code == 200:
                time.sleep(pause)
                return r.text
            if r.status_code not in {429, 500, 502, 503, 504}:
                r.raise_for_status()
        except requests.RequestException:
            if attempt == 6:
                raise
        time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"failed after retries status={last}: {url}")


def enumerate_te_links(session: requests.Session, season: int, pause: float) -> list[str]:
    links: set[str] = set()
    page = 1
    pages = []
    while True:
        url = f"{BASE}/{season}/players/?page={page}"
        try:
            html = get(session, url, pause)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404 and page > 1:
                atomic_json(OUT / f"cfb{season}_page_manifest.json", {"season": season, "pages": pages, "unique_te_links": len(links), "complete": True, "terminal_page": page, "terminal_status": 404})
                print(f"season={season} terminal_page={page} status=404 total_te={len(links)}", flush=True)
                break
            raise
        soup = BeautifulSoup(html, "html.parser")
        cards = []
        for a in soup.find_all("a", href=True):
            text, href = " ".join(a.stripped_strings), a["href"]
            if "/players/" in href and re.search(r"\bTE\s+-\s+", text):
                cards.append(urljoin(BASE, href))
        all_cards = [a for a in soup.find_all("a", href=True) if re.search(r"\bOVR\b", " ".join(a.stripped_strings)) and "/players/" in a["href"]]
        before = len(links)
        links.update(cards)
        pages.append({"page": page, "url": url, "player_cards": len(all_cards), "te_links": len(cards), "new_te_links": len(links) - before})
        atomic_json(OUT / f"cfb{season}_page_manifest.json", {"season": season, "pages": pages, "unique_te_links": len(links), "complete": not bool(all_cards)})
        print(f"season={season} page={page} te_links={len(cards)} total_te={len(links)}", flush=True)
        if not all_cards:
            break
        page += 1
        if page > 1000:
            raise RuntimeError("pagination safety limit reached")
    atomic_json(OUT / f"cfb{season}_te_urls.json", sorted(links))
    return sorted(links)


def parse_player(html: str, url: str, season: int) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    h1 = soup.find("h1")
    title = " ".join(h1.stripped_strings) if h1 else ""
    mt = TITLE_RE.search(title)
    if not mt or " TE " not in f" {text} ":
        return None
    record = {"season": season, "url": url, "name": mt.group("name").strip(), "ovr": int(mt.group("ovr"))}
    archetype = re.search(r"Archetype\s*[:\-]?\s*([A-Za-z ]+?)(?=\s{2,}|\s\d{2}\s|$)", text, re.I)
    if archetype:
        record["archetype"] = archetype.group(1).strip()
    attrs = {}
    for m in re.finditer(r"\b([A-Z]{2,4})\s+(\d{1,2})\b", text):
        attrs[m.group(1)] = int(m.group(2))
    record["attributes"] = attrs
    return record


def acquire_population(session: requests.Session, season: int, links: list[str], pause: float) -> list[dict]:
    path = OUT / f"cfb{season}_te_population.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []
    by_url = {r["url"]: r for r in existing if isinstance(r, dict) and r.get("url")}
    failures = []
    for i, url in enumerate(links, 1):
        if url in by_url:
            continue
        try:
            record = parse_player(get(session, url, pause), url, season)
            if record is None:
                failures.append({"url": url, "kind": "parse_failure"})
            else:
                by_url[url] = record
        except Exception as exc:  # preserve resumable checkpoint and evidence
            failures.append({"url": url, "kind": "fetch_failure", "error": repr(exc)})
        if i % 10 == 0 or i == len(links):
            atomic_json(path, list(by_url.values()))
            atomic_json(OUT / f"cfb{season}_failures.json", failures)
            print(f"season={season} fetched={i}/{len(links)} persisted={len(by_url)} failures={len(failures)}", flush=True)
    return list(by_url.values())


def summarize(season: int, links: list[str], population: list[dict]) -> dict:
    urls = [r.get("url") for r in population]
    archetypes = {}
    ovrs = {}
    for r in population:
        archetypes[r.get("archetype", "UNKNOWN")] = archetypes.get(r.get("archetype", "UNKNOWN"), 0) + 1
        ovrs[str(r.get("ovr", "UNKNOWN"))] = ovrs.get(str(r.get("ovr", "UNKNOWN")), 0) + 1
    return {
        "season": season,
        "enumerated_urls": len(links),
        "persisted_population": len(population),
        "unique_source_urls": len(set(urls)),
        "missing_urls": sorted(set(links) - set(urls)),
        "duplicate_urls": len(urls) - len(set(urls)),
        "archetype_counts": archetypes,
        "ovr_distribution": ovrs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=[25, 26])
    parser.add_argument("--pause", type=float, default=0.20)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    summaries = []
    for season in args.seasons:
        links = enumerate_te_links(session, season, args.pause)
        population = acquire_population(session, season, links, args.pause)
        summary = summarize(season, links, population)
        atomic_json(OUT / f"cfb{season}_summary.json", summary)
        summaries.append(summary)
    atomic_json(OUT / "summary.json", {"seasons": summaries})
    print(json.dumps({"seasons": summaries}, indent=2), flush=True)


if __name__ == "__main__":
    main()

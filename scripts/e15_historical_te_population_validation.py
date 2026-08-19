#!/usr/bin/env python3
"""Acquire CFB.FAN CFB25/26 TE populations and blind-score frozen E.15 models.

This script intentionally keeps acquisition, normalization, frozen scoring, and
measurement in one reproducible operation. It never refits model weights.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://cfb.fan"
OUT = Path("data/research/cfb27_e15/historical_validation")

# Canonical File Library: Operation_Pancake_Master_Database_v1.1_TE_Analysis.xlsx,
# Madden19_TE_Weights. Percent weights sum to 100 in each historical archetype.
M19 = {
    "SPD": (0, 3, 7), "ACC": (0, 4, 7), "AGI": (0, 3, 4),
    "STR": (6, 4, 0), "JMP": (0, 0, 3), "AWR": (9, 9, 9),
    "BCV": (0, 1, 2), "BTK": (2, 2, 3), "ELU": (0, 0, 2),
    "TRK": (1, 1, 1), "SFA": (2, 2, 2), "CTH": (3, 10, 11),
    "CIT": (3, 14, 8), "SPC": (0, 1, 4), "RLS": (0, 2, 3),
    "SRR": (5, 12, 7), "MRR": (4, 6, 9), "DRR": (0, 0, 5),
    "IBL": (9, 4, 0), "LBK": (8, 2, 0), "PBK": (8, 3, 2),
    "PBF": (6, 2, 1), "PBP": (6, 2, 1), "RBK": (10, 5, 3),
    "RBF": (9, 4, 3), "RBP": (9, 4, 3),
}
BLOCKING = {k: v[0] for k, v in M19.items()}
POSSESSION = {k: v[1] for k, v in M19.items()}
VERTICAL = {k: v[2] for k, v in M19.items() if k != "ELU"}
VERTICAL_V13 = {**VERTICAL, "LBK": 2, "IBL": 3}  # frozen +2 LBK/+3 IBL

MODEL_BY_ARCHETYPE = {
    "Vertical Threat": "TE-MODEL-006 v1.3",
    "Gritty Possession": "TE-MODEL-001 v1.1",
    "Possession": "TE-MODEL-001 v1.1",  # CFB25 historical label
    "Physical Route Runner": "TE-MODEL-003 v1.1",
    "Pure Blocker": "TE-MODEL-004 v1.1",
    "Blocking": "TE-MODEL-004 v1.1",  # CFB25 historical label
}

ATTR_RE = re.compile(r"\b(SPD|ACC|AGI|AWR|STR|JMP|CTH|CIT|SRR|MRR|DRR|SPC|RLS|CAR|BCV|JKM|SPM|TRK|SFA|COD|BTK|RBK|RBF|RBP|PBK|PBF|PBP|LBK|IBL)\s+(\d{1,3})\b")
TITLE_RE = re.compile(r"(.+?)\s+(\d{2})\s+OVR")
ARCH_RE = re.compile(r"Archetype\s+(.+?)\s+-\s+TE")


def get(session: requests.Session, url: str, pause: float) -> str:
    for attempt in range(5):
        r = session.get(url, timeout=30, headers={"User-Agent": "Operation-Pancake-research/1.0"})
        if r.status_code == 200:
            time.sleep(pause)
            return r.text
        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep((attempt + 1) * 2)
            continue
        r.raise_for_status()
    raise RuntimeError(f"failed after retries: {url}")


def enumerate_te_links(session: requests.Session, season: int, pause: float) -> list[str]:
    links: set[str] = set()
    page = 1
    while True:
        url = f"{BASE}/{season}/players/?page={page}"
        soup = BeautifulSoup(get(session, url, pause), "html.parser")
        cards = []
        for a in soup.find_all("a", href=True):
            text = " ".join(a.stripped_strings)
            href = a["href"]
            if "/players/" in href and re.search(r"\bTE\s+-\s+", text):
                cards.append(urljoin(BASE, href))
        before = len(links)
        links.update(cards)
        # CFB.FAN currently exposes 15 cards/page. Stop only when a page has no
        # player-card links; this avoids assuming a hard-coded historical count.
        all_player_cards = [a for a in soup.find_all("a", href=True) if re.search(r"\bOVR\b", " ".join(a.stripped_strings)) and "/players/" in a["href"]]
        print(f"season={season} page={page} te_links={len(cards)} total_te={len(links)}")
        if not all_player_cards:
            break
        page += 1
        if page > 1000:
            raise RuntimeError("pagination safety limit reached")
    return sorted(links)


def parse_player(html: str, url: str, season: int) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    h1 = soup.find("h1")
    title = " ".join(h1.stripped_strings) if h1 else ""
    mt = TITLE_RE.search(title)
    if not mt or " TE " not in f" {text} ":
        return None
    name, overall = mt.group(1).strip(), int(mt.group(2))
    ma = ARCH_RE.search(text)
    archetype = ma.group(1).strip() if ma else None
    attrs = {k: int(v) for k, v in ATTR_RE.findall(text)}
    return {"season": season, "name": name, "overall": overall, "archetype": archetype, "source_url": url, "ratings": attrs}


def weighted(attrs: dict[str, int], weights: dict[str, int]) -> float | None:
    needed = [k for k, w in weights.items() if w > 0]
    if any(k not in attrs for k in needed):
        return None
    denom = sum(weights[k] for k in needed)
    return sum(attrs[k] * weights[k] for k in needed) / denom


def score(record: dict) -> dict:
    arch = record["archetype"]
    attrs = record["ratings"]
    model = MODEL_BY_ARCHETYPE.get(arch)
    s = None
    if model == "TE-MODEL-006 v1.3":
        s = weighted(attrs, VERTICAL_V13)
    elif model == "TE-MODEL-001 v1.1":
        s = weighted(attrs, POSSESSION)
    elif model == "TE-MODEL-004 v1.1":
        s = weighted(attrs, BLOCKING)
    elif model == "TE-MODEL-003 v1.1":
        vt, pos = weighted(attrs, VERTICAL_V13), weighted(attrs, POSSESSION)
        if vt is not None and pos is not None:
            s = 0.71 * vt + 0.29 * pos
    return {**record, "model": model, "score": s, "residual_score_minus_ovr": None if s is None else s - record["overall"]}


def metrics(rows: list[dict]) -> dict:
    usable = [r for r in rows if r["score"] is not None and r["model"]]
    pairs = correct = ties = 0
    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            if a["archetype"] != b["archetype"] or a["overall"] == b["overall"]:
                continue
            pairs += 1
            expected = 1 if a["overall"] > b["overall"] else -1
            delta = a["score"] - b["score"]
            if delta == 0:
                ties += 1
            elif (delta > 0 and expected > 0) or (delta < 0 and expected < 0):
                correct += 1
    residuals = [abs(r["residual_score_minus_ovr"]) for r in usable]
    return {
        "population_n": len(rows),
        "model_scored_n": len(usable),
        "cross_ovr_pairs_n": pairs,
        "ranking_correct_n": correct,
        "ranking_ties_n": ties,
        "ranking_accuracy": None if pairs == 0 else correct / pairs,
        "raw_weighted_score_mae_vs_displayed_ovr": None if not residuals else sum(residuals) / len(residuals),
        "exact_ovr_accuracy": None,
        "exact_ovr_accuracy_note": "Not applicable: frozen TE models are ranking architectures, not proven displayed-OVR conversion formulas.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=[25, 26])
    ap.add_argument("--pause", type=float, default=0.20)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    summary = {"phase": "OP-X-012E.15", "freeze_commit": "5c7a9d88b711fed19374d170712e3acec5e4ed1b", "seasons": {}}
    for season in args.seasons:
        links = enumerate_te_links(session, season, args.pause)
        rows = []
        for n, url in enumerate(links, 1):
            rec = parse_player(get(session, url, args.pause), url, season)
            if rec:
                rows.append(score(rec))
            if n % 25 == 0:
                print(f"season={season} details={n}/{len(links)}")
        (OUT / f"cfb{season}_te_population.json").write_text(json.dumps(rows, indent=2) + "\n")
        with (OUT / f"cfb{season}_te_population.csv").open("w", newline="") as f:
            fields = ["season", "name", "overall", "archetype", "model", "score", "residual_score_minus_ovr", "source_url"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in fields})
        by_arch = defaultdict(list)
        for r in rows:
            by_arch[r["archetype"]].append(r)
        sm = metrics(rows)
        sm["by_archetype"] = {str(k): metrics(v) for k, v in sorted(by_arch.items(), key=lambda x: str(x[0]))}
        summary["seasons"][str(season)] = sm
    (OUT / "te_historical_validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

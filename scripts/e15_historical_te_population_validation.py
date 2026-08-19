#!/usr/bin/env python3
"""Acquire CFB.FAN CFB25/26 TE populations and blind-score frozen E.15 models.

Acquisition is resumable and persists provenance/completeness evidence. Frozen
model weights are never refit from historical outcomes.
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
FREEZE_COMMIT = "5c7a9d88b711fed19374d170712e3acec5e4ed1b"

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
VERTICAL_V13 = {**VERTICAL, "LBK": 2, "IBL": 3}
MODEL_BY_ARCHETYPE = {
    "Vertical Threat": "TE-MODEL-006 v1.3",
    "Gritty Possession": "TE-MODEL-001 v1.1",
    "Possession": "TE-MODEL-001 v1.1",
    "Physical Route Runner": "TE-MODEL-003 v1.1",
    "Pure Blocker": "TE-MODEL-004 v1.1",
    "Blocking": "TE-MODEL-004 v1.1",
}
ATTR_RE = re.compile(r"\b(SPD|ACC|AGI|AWR|STR|JMP|CTH|CIT|SRR|MRR|DRR|SPC|RLS|CAR|BCV|JKM|SPM|TRK|SFA|COD|BTK|RBK|RBF|RBP|PBK|PBF|PBP|LBK|IBL)\s+(\d{1,3})\b")
TITLE_RE = re.compile(r"(.+?)\s+(\d{2})\s+OVR")
ARCH_RE = re.compile(r"Archetype\s+(.+?)\s+-\s+TE")


def atomic_json(path: Path, value) -> None:
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
        soup = BeautifulSoup(get(session, url, pause), "html.parser")
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
    ma = ARCH_RE.search(text)
    return {"season": season, "name": mt.group(1).strip(), "overall": int(mt.group(2)), "archetype": ma.group(1).strip() if ma else None, "source_url": url, "ratings": {k: int(v) for k, v in ATTR_RE.findall(text)}}


def weighted(attrs: dict[str, int], weights: dict[str, int]) -> float | None:
    needed = [k for k, w in weights.items() if w > 0]
    if any(k not in attrs for k in needed):
        return None
    return sum(attrs[k] * weights[k] for k in needed) / sum(weights[k] for k in needed)


def score(record: dict) -> dict:
    arch, attrs = record["archetype"], record["ratings"]
    model, s = MODEL_BY_ARCHETYPE.get(arch), None
    if model == "TE-MODEL-006 v1.3": s = weighted(attrs, VERTICAL_V13)
    elif model == "TE-MODEL-001 v1.1": s = weighted(attrs, POSSESSION)
    elif model == "TE-MODEL-004 v1.1": s = weighted(attrs, BLOCKING)
    elif model == "TE-MODEL-003 v1.1":
        vt, pos = weighted(attrs, VERTICAL_V13), weighted(attrs, POSSESSION)
        if vt is not None and pos is not None: s = .71 * vt + .29 * pos
    return {**record, "model": model, "score": s, "residual_score_minus_ovr": None if s is None else s - record["overall"]}


def metrics(rows: list[dict]) -> dict:
    usable = [r for r in rows if r.get("score") is not None and r.get("model")]
    pairs = correct = ties = 0
    inversions = []
    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            if a["archetype"] != b["archetype"] or a["overall"] == b["overall"]: continue
            pairs += 1
            delta = a["score"] - b["score"]
            expected = 1 if a["overall"] > b["overall"] else -1
            if delta == 0: ties += 1
            elif (delta > 0) == (expected > 0): correct += 1
            else:
                inversions.append({"archetype": a["archetype"], "a": {k: a[k] for k in ("name","overall","score","source_url")}, "b": {k: b[k] for k in ("name","overall","score","source_url")}, "score_gap": abs(delta), "ovr_gap": abs(a["overall"]-b["overall"])})
    residuals = [abs(r["residual_score_minus_ovr"]) for r in usable]
    return {"population_n": len(rows), "model_scored_n": len(usable), "cross_ovr_pairs_n": pairs, "ranking_correct_n": correct, "ranking_inversions_n": len(inversions), "ranking_ties_n": ties, "ranking_accuracy": None if not pairs else correct/pairs, "raw_weighted_score_mae_vs_displayed_ovr": None if not residuals else sum(residuals)/len(residuals), "exact_ovr_accuracy": None, "exact_ovr_accuracy_note": "Not applicable: frozen TE models are ranking architectures, not proven displayed-OVR conversion formulas.", "inversions": sorted(inversions, key=lambda x: (-x["ovr_gap"], -x["score_gap"]))}


def write_population(season: int, rows: list[dict]) -> None:
    rows = sorted({r["source_url"]: r for r in rows}.values(), key=lambda r: r["source_url"])
    atomic_json(OUT / f"cfb{season}_te_population.json", rows)
    with (OUT / f"cfb{season}_te_population.csv").open("w", newline="") as f:
        fields = ["season","name","overall","archetype","model","score","residual_score_minus_ovr","source_url"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in fields})


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--seasons", nargs="+", type=int, default=[25,26]); ap.add_argument("--pause", type=float, default=.20); args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); session = requests.Session()
    summary = {"phase":"OP-X-012E.15","freeze_commit":FREEZE_COMMIT,"seasons":{}}
    for season in args.seasons:
        links = enumerate_te_links(session, season, args.pause)
        population_path = OUT / f"cfb{season}_te_population.json"
        rows = json.loads(population_path.read_text()) if population_path.exists() else []
        by_url = {r["source_url"]: r for r in rows}
        failures = []
        for n, url in enumerate(links, 1):
            if url in by_url: continue
            try:
                rec = parse_player(get(session, url, args.pause), url, season)
                if rec: by_url[url] = score(rec)
                else: failures.append({"url":url,"error":"parse returned no TE record"})
            except Exception as exc:
                failures.append({"url":url,"error":f"{type(exc).__name__}: {exc}"})
            if n % 10 == 0 or failures:
                write_population(season, list(by_url.values()))
                atomic_json(OUT / f"cfb{season}_acquisition_state.json", {"season":season,"enumerated_n":len(links),"persisted_n":len(by_url),"remaining_n":len(links)-len(by_url),"failures":failures})
                print(f"season={season} details={n}/{len(links)} persisted={len(by_url)} failures={len(failures)}", flush=True)
        rows = list(by_url.values()); write_population(season, rows)
        missing = sorted(set(links)-set(by_url))
        duplicate_urls = len(rows)-len({r["source_url"] for r in rows})
        by_arch = defaultdict(list)
        for r in rows: by_arch[r["archetype"]].append(r)
        sm = metrics(rows); sm["by_archetype"] = {str(k):metrics(v) for k,v in sorted(by_arch.items(), key=lambda x:str(x[0]))}
        sm["completeness"] = {"enumerated_te_urls_n":len(links),"persisted_unique_urls_n":len(by_url),"missing_urls_n":len(missing),"missing_urls":missing,"duplicate_source_urls_n":duplicate_urls,"parse_or_fetch_failures_n":len(failures),"complete":not missing and not failures}
        summary["seasons"][str(season)] = sm
        atomic_json(OUT / f"cfb{season}_acquisition_state.json", {"season":season,**sm["completeness"],"failures":failures})
        atomic_json(OUT / "te_historical_validation_summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)

if __name__ == "__main__": main()

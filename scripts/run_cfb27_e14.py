#!/usr/bin/env python3
"""Execute the observable discovery stage of OP-X-012E.14.

This runner deliberately does not assign scientific verdicts. It proves the
canonical Alpha population is executable in CI and inventories the exact
cross-position populations/contrast opportunities consumed by E.14.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from operation_pancake.research.cfb27_alpha_population import build_alpha_population

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/cfb27_e14/execution_discovery.json"

FAMILIES = {
    "BSH": ({"FS", "SS"}, {"SAM", "MIKE", "WILL"}, {"LEDG", "REDG"}),
    "PRC": ({"FS", "SS"}, {"CB"}, {"SAM", "MIKE", "WILL"}),
    "SPD": ({"CB"}, {"FS", "SS"}, {"SAM", "MIKE", "WILL"}),
    "PMV": ({"MIKE"}, {"LEDG", "REDG"}, {"DT"}),
    "FMV": ({"MIKE"}, {"LEDG", "REDG"}, {"DT"}),
}


def _eligible(card: dict) -> bool:
    ratings = card.get("displayed_ratings") or {}
    return (
        card.get("extraction_status") == "COMPLETE"
        and isinstance(card.get("overall"), int)
        and bool(card.get("position"))
        and bool(card.get("archetype"))
        and len(ratings) >= 15
        and all(isinstance(value, int) and 0 <= value <= 99 for value in ratings.values())
        and not (card.get("metadata") or {}).get("dynamic_state")
        and not (card.get("metadata") or {}).get("projected_state")
    )


def _fingerprint(cards: list[dict]) -> str:
    rows = []
    for card in sorted(cards, key=lambda row: row["external_card_id"]):
        rows.append(
            {
                "id": card["external_card_id"],
                "position": card["position"],
                "archetype": card["archetype"],
                "overall": card["overall"],
                "ratings": dict(sorted((card.get("displayed_ratings") or {}).items())),
            }
        )
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _family_inventory(cards: list[dict], rating: str, groups: tuple[set[str], ...]) -> dict:
    positions = set().union(*groups)
    members = [card for card in cards if card["position"] in positions and rating in card["displayed_ratings"]]
    strata = Counter((card["position"], card["archetype"], card["overall"]) for card in members)
    by_ovr: dict[int, list[dict]] = defaultdict(list)
    for card in members:
        by_ovr[card["overall"]].append(card)

    same_ovr = 0
    adjacent_ovr = 0
    for ovr, rows in by_ovr.items():
        for left, right in combinations(rows, 2):
            if left["position"] != right["position"]:
                same_ovr += 1
        for left in rows:
            for right in by_ovr.get(ovr + 1, []):
                if left["position"] != right["position"]:
                    adjacent_ovr += 1

    return {
        "target_rating": rating,
        "positions": sorted(positions),
        "eligible_cards": len(members),
        "position_counts": dict(sorted(Counter(card["position"] for card in members).items())),
        "archetype_counts": dict(sorted(Counter(card["archetype"] for card in members).items())),
        "ovr_range": [min(card["overall"] for card in members), max(card["overall"] for card in members)],
        "native_position_archetype_ovr_strata": len(strata),
        "same_ovr_cross_position_candidate_pairs": same_ovr,
        "adjacent_ovr_cross_position_candidate_pairs": adjacent_ovr,
    }


def main() -> None:
    population = build_alpha_population(ROOT)
    all_cards = list(population["cards"].values())
    eligible = [card for card in all_cards if _eligible(card)]
    result = {
        "stage": "E.14_EXECUTION_DISCOVERY",
        "scientific_verdicts_emitted": False,
        "e15_started": False,
        "input_source": "build_alpha_population(data/external/cfb_fan_population_state.json + committed structured snapshots)",
        "alpha_summary": population["summary"],
        "input_record_count": len(all_cards),
        "formula_eligible_record_count": len(eligible),
        "population_sha256": _fingerprint(eligible),
        "position_counts": dict(sorted(Counter(card["position"] for card in eligible).items())),
        "component_families": {
            rating: _family_inventory(eligible, rating, groups)
            for rating, groups in FAMILIES.items()
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"E.14 input source: {result['input_source']}")
    print(f"E.14 input records: {len(all_cards)}; eligible: {len(eligible)}")
    for rating, family in result["component_families"].items():
        print(
            f"E.14 {rating}: cards={family['eligible_cards']} positions={family['position_counts']} "
            f"same_ovr_pairs={family['same_ovr_cross_position_candidate_pairs']} "
            f"adjacent_pairs={family['adjacent_ovr_cross_position_candidate_pairs']}"
        )
    print(f"E.14 discovery artifact: {OUTPUT.relative_to(ROOT)}")
    print("E.15 started: NO")


if __name__ == "__main__":
    main()

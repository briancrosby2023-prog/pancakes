"""Execute OP-X-051 over the canonical CFB27 population and persist evidence."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from operation_pancake.production.gm import GMProduct
from operation_pancake.production.role_intelligence import (
    ROLE_ATTRIBUTES,
    card_ratings,
    card_role_candidates,
    family,
    role_alternatives,
    role_profile,
    scientific_firewall,
)
from operation_pancake.production.roster import normalize_name

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_051"
OUT.mkdir(parents=True, exist_ok=True)


def dump(name: str, obj: object) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scoreable(evaluation: dict) -> bool:
    return evaluation.get("score") is not None


def main() -> None:
    gm = GMProduct(ROOT)
    population = gm.population
    if len(population) != 8838:
        raise RuntimeError(
            f"canonical CFB27 population drift: expected 8838, found {len(population)}"
        )
    evaluations = {card["card_id"]: gm.lookup(card_id=card["card_id"]) for card in population}
    scoreable_ids = {
        card_id
        for card_id, result in evaluations.items()
        if scoreable(result.get("evaluation", {}))
    }
    if len(scoreable_ids) != 8184:
        raise RuntimeError(
            f"OP-X-051 scoreable population drift: expected 8184, found {len(scoreable_ids)}"
        )

    role_candidates: list[dict] = []
    complete: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)
    for card in population:
        for candidate in card_role_candidates(card):
            row = {
                "card_id": card["card_id"],
                "player": card.get("player_name"),
                "position": card.get("position"),
                "ovr": card.get("native_overall"),
                **candidate,
            }
            role_candidates.append(row)
            if candidate["attribute_coverage"] == 1 and card["card_id"] in scoreable_ids:
                complete[(candidate["position_family"], candidate["role"])].append(card)

    boards: dict[str, dict] = {}
    supported = 0
    blocked = 0
    for position_family, roles in ROLE_ATTRIBUTES.items():
        for role in roles:
            key = f"{position_family}:{role}"
            rows = []
            for card in complete.get((position_family, role), []):
                evaluation = evaluations[card["card_id"]]["evaluation"]
                rows.append(
                    {
                        "card_id": card["card_id"],
                        "player": card.get("player_name"),
                        "ovr": card.get("native_overall"),
                        "base_pancake_score": evaluation.get("score"),
                        "position_rank": evaluation.get("position_rank"),
                        "role_fit": "UNKNOWN",
                        "market_used": False,
                    }
                )
            rows.sort(
                key=lambda row: (
                    -(row["base_pancake_score"] or -1),
                    -(row["ovr"] or -1),
                    row["card_id"],
                )
            )
            status = "SUPPORTED" if rows else "ROLE BOARD BLOCKED — INSUFFICIENT EVIDENCE"
            supported += bool(rows)
            blocked += not bool(rows)
            boards[key] = {
                "status": status,
                "profile": role_profile(position_family, role),
                "candidate_count": len(rows),
                "rows": rows[:25],
            }

    money = []
    for (position_family, role), cards in complete.items():
        attributes = ROLE_ATTRIBUTES[position_family][role]
        ordered = sorted(
            cards,
            key=lambda card: (-(card.get("native_overall") or 0), card["card_id"]),
        )
        for higher in ordered:
            higher_ratings = card_ratings(higher)
            best = None
            for lower in ordered:
                if (lower.get("native_overall") or 0) >= (higher.get("native_overall") or 0):
                    continue
                lower_ratings = card_ratings(lower)
                distance = sum(
                    abs(float(lower_ratings[attr]) - float(higher_ratings[attr]))
                    for attr in attributes
                )
                if distance <= 5 and (best is None or distance < best[0]):
                    best = (distance, lower)
            if best:
                distance, lower = best
                money.append(
                    {
                        "position_family": position_family,
                        "role": role,
                        "higher_card_id": higher["card_id"],
                        "higher_player": higher.get("player_name"),
                        "higher_ovr": higher.get("native_overall"),
                        "lower_card_id": lower["card_id"],
                        "lower_player": lower.get("player_name"),
                        "lower_ovr": lower.get("native_overall"),
                        "trait_distance": round(distance, 3),
                        "classification": "NEAR ROLE EQUIVALENT",
                        "price_conclusion": "UNKNOWN",
                    }
                )

    roster_path = ROOT / "data/production/roster/canonical_roster.json"
    roster_raw = json.loads(roster_path.read_text()) if roster_path.exists() else []
    if isinstance(roster_raw, list):
        entries = roster_raw
    else:
        entries = roster_raw.get("roster", roster_raw.get("entries", roster_raw.get("players", [])))
    roster = []
    for entry in entries:
        card_id = (
            entry.get("canonical_card_id")
            or entry.get("card_id")
            or entry.get("resolved_card_id")
        )
        card = gm.cards.get(card_id) if card_id else None
        if card is None:
            name = entry.get("player_name") or entry.get("name")
            matches = [
                candidate
                for candidate in population
                if name
                and normalize_name(candidate.get("player_name") or "") == normalize_name(name)
            ]
            if len(matches) == 1:
                card = matches[0]
                card_id = card["card_id"]
        roster.append(
            {
                "slot": entry.get("slot") or entry.get("roster_slot"),
                "input_name": entry.get("player_name") or entry.get("name"),
                "card_id": card_id,
                "resolved": bool(card),
                "scored": bool(card_id in scoreable_ids),
                "deployment": "DEPLOYMENT REQUIRED",
                "role_candidates": card_role_candidates(card) if card else [],
            }
        )

    target_pairs = [
        ("Anthony Donkoh", "Brendan Black"),
        ("Samson Okunlola", "E'Marion Harris"),
        ("Dashawn Spears", "Bray Hubbard"),
        ("Cole", "Kip Lewis"),
        ("McClain", "Kobe Black"),
    ]

    def matches(name: str) -> list[dict]:
        return [
            card
            for card in population
            if normalize_name(card.get("player_name") or "") == normalize_name(name)
        ]

    targets = []
    for current_name, candidate_name in target_pairs:
        current_matches = matches(current_name)
        candidate_matches = matches(candidate_name)
        row = {
            "current_name": current_name,
            "candidate_name": candidate_name,
            "current_matches": [card["card_id"] for card in current_matches],
            "candidate_matches": [card["card_id"] for card in candidate_matches],
            "purchase_action": "UNCHANGED",
            "market_conclusion": "PRICE CHECK REQUIRED",
        }
        if len(current_matches) == 1 and len(candidate_matches) == 1:
            current, candidate = current_matches[0], candidate_matches[0]
            current_eval = evaluations[current["card_id"]]["evaluation"]
            candidate_eval = evaluations[candidate["card_id"]]["evaluation"]
            row.update(
                {
                    "status": "EXECUTED",
                    "current_card_id": current["card_id"],
                    "candidate_card_id": candidate["card_id"],
                    "frozen_score_current": current_eval.get("score"),
                    "frozen_score_candidate": candidate_eval.get("score"),
                    "frozen_pancake_delta": (
                        None
                        if current_eval.get("score") is None or candidate_eval.get("score") is None
                        else round(candidate_eval["score"] - current_eval["score"], 6)
                    ),
                    "role_specific_relevance": "DEPLOYMENT REQUIRED",
                    "binding_trait_improvement": "UNKNOWN",
                    "secondary_gains": "UNKNOWN",
                    "contextual_risks": "UNKNOWN",
                    "deployment_change_possibility": "UNKNOWN",
                }
            )
            position_family = family(current.get("position") or "")
            row["population_role_challenges"] = {
                role: role_alternatives(ROOT, candidate["card_id"], role, 10)
                for role in ROLE_ATTRIBUTES.get(position_family, {})
            }
        else:
            row["status"] = (
                "AMBIGUOUS CARD VERSION"
                if current_matches and candidate_matches
                else "UNRESOLVED IDENTITY"
            )
        targets.append(row)

    free_bnd = [
        {
            "card_id": row["card_id"],
            "acquisition_state": "UNKNOWN",
            "purchase_avoidance": "UNKNOWN",
            "fabricated_coin_value": None,
        }
        for row in roster
        if row["resolved"]
    ]
    context = {
        "canonical_population": len(population),
        "scoreable_population": len(scoreable_ids),
        "role_candidate_records": sum(
            row["classification"] == "ROLE CANDIDATE" for row in role_candidates
        ),
        "unknown_role_candidate_records": sum(
            row["classification"] == "UNKNOWN" for row in role_candidates
        ),
        "supported_role_boards": supported,
        "blocked_role_boards": blocked,
        "roster_entries": len(roster),
        "roster_resolved": sum(row["resolved"] for row in roster),
        "roster_scored": sum(row["scored"] for row in roster),
    }

    dump("CONTEXT_COVERAGE.json", context)
    dump(
        "ROLE_PROFILES.json",
        {
            f"{position_family}:{role}": role_profile(position_family, role)
            for position_family, roles in ROLE_ATTRIBUTES.items()
            for role in roles
        },
    )
    dump(
        "ROLE_BOARDS.json",
        {"summary": {"supported": supported, "blocked": blocked}, "boards": boards},
    )
    dump("ROLE_ALTERNATIVES.json", {"target_challenge_alternatives": targets})
    dump(
        "ROLE_MONEYBALL.json",
        {
            "case_count": len(money),
            "cases": money[:1000],
            "truncated": len(money) > 1000,
        },
    )
    dump(
        "OVR_WASTE.json",
        {
            "supported_case_count": 0,
            "cases": [],
            "status": (
                "UNKNOWN — requires evidence that surplus attributes are role-irrelevant; "
                "no inference from low weight alone"
            ),
        },
    )
    dump(
        "BINDING_TRAITS.json",
        {
            "finding_count": sum(len(roles) for roles in ROLE_ATTRIBUTES.values()),
            "profiles": {
                f"{position_family}:{role}": list(attributes)
                for position_family, roles in ROLE_ATTRIBUTES.items()
                for role, attributes in roles.items()
            },
        },
    )
    dump(
        "ROSTER_ROLE_MAP.json",
        {
            "entries": roster,
            "summary": {
                "entries": len(roster),
                "resolved": sum(row["resolved"] for row in roster),
                "scored": sum(row["scored"] for row in roster),
                "deployment_required": sum(row["resolved"] for row in roster),
            },
        },
    )
    dump(
        "ROSTER_MISMATCHES.json",
        {
            "supported_count": 0,
            "cases": [],
            "status": "UNKNOWN — deployment evidence absent; no mismatch inferred",
        },
    )
    dump(
        "ZERO_COIN_UPGRADES.json",
        {
            "supported_count": 0,
            "cases": [],
            "status": (
                "UNKNOWN — acquisition/deployment evidence insufficient; "
                "unsupported assumptions forbidden"
            ),
        },
    )
    dump(
        "PURCHASE_AVOIDANCE.json",
        {
            "supported_count": 0,
            "cases": [],
            "coin_values": [],
            "status": "UNKNOWN unless free/BND acquisition and role coverage are both evidenced",
        },
    )
    dump("CURRENT_TARGET_REVIEW.json", {"targets": targets})
    dump(
        "TARGET_CHALLENGES.json",
        {
            "targets": targets,
            "seeded_challengers": [
                "Addison Nichols",
                "Drew Azzopardi",
                "Jay Green",
                "Isaiah Glasker",
                "Dontay Joyner",
            ],
        },
    )
    dump(
        "FREE_BND_ROLE_COVERAGE.json",
        {"entries": free_bnd, "supported_purchase_avoidance_count": 0},
    )
    residual_path = OUT / "META_ROLE_RESIDUALS.json"
    residual = json.loads(residual_path.read_text()) if residual_path.exists() else {}
    residual["execution_status"] = "EXECUTED"
    residual["model_error_claimed"] = False
    dump("META_ROLE_RESIDUALS.json", residual)
    dump(
        "RESEARCH_QUEUE.json",
        {
            "priorities": [
                "resolve deployment roles for current roster",
                "capture exact target card versions where ambiguous",
                "capture equipped abilities/AP",
                "capture observed usage vs recommendation separately",
                "capture free/BND acquisition evidence",
            ]
        },
    )
    (OUT / "PRODUCT_DEMOS.md").write_text(
        "# OP-X-051 Product Demos\n\n"
        f"Canonical cards: {len(population)}; scoreable: {len(scoreable_ids)}.\n"
        f"Role-candidate records: {context['role_candidate_records']}.\n"
        f"Supported role boards: {supported}; blocked: {blocked}.\n"
        f"Moneyball role relationships: {len(money)}.\n\n"
        "UNKNOWN context never changes frozen score/rank/percentile. "
        "Market price is not used for football role ranking.\n"
    )
    summary = {
        "status": "EXECUTED",
        "counts": context,
        "role_moneyball_cases": len(money),
        "ovr_waste_supported": 0,
        "roster_mismatches_supported": 0,
        "zero_coin_supported": 0,
        "purchase_avoidance_supported": 0,
        "scientific_firewall": scientific_firewall(),
        "targets": targets,
    }
    dump("execution_summary.json", summary)
    (OUT / "RESULTS.md").write_text(
        "# OP-X-051B Execution Results\n\n" + json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

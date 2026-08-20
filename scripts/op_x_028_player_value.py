"""Generate OP-X-028 intrinsic artifacts, then separately evaluate observed prices."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from operation_pancake.production.engine import ProductionEngine, load_population
from operation_pancake.production.gm import optimize_budget
from operation_pancake.production.registry import build_model_registry
from operation_pancake.production.valuation import (
    PRICE_GRID,
    VALUE_INDEX_WEIGHTS,
    population_value_curves,
    price_sensitivity,
    relative_value_classes,
    upgrade_value,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/op_x_028"
TARGETS = (
    ("Anthony Donkoh", "Brendan Black"),
    ("Samson Okunlola", "E'Marion Harris"),
    ("Dashawn Spears", "Bray Hubbard"),
    ("Chris Cole", "Kip Lewis"),
    ("Cormani McClain", "Kobe Black"),
)


def write(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def context() -> tuple[list[dict], dict[str, dict], dict, dict]:
    population = load_population(ROOT)
    registry = build_model_registry(ROOT)
    engine = ProductionEngine(registry)
    ranked = engine.rank([engine.score(card) for card in population])
    return (
        ranked,
        {row["card_id"]: row for row in population},
        population_value_curves(ranked),
        registry,
    )


def attribute_efficiency(
    current_card: dict, candidate_card: dict, candidate_score: dict, registry: dict, slack: dict
) -> dict:
    model = next(
        row
        for row in registry["models"]
        if row["id"] == candidate_score["pancake_model_id"]
        and row["version"] == candidate_score["pancake_model_version"]
    )
    profile = candidate_score["routing"]["profile"]
    if profile == "Blend":
        return {
            "status": "NOT ATTRIBUTED",
            "reason": "blended profile requires profile decomposition",
        }
    weights = model["profiles"][profile]
    total_weight = sum(weights.values())
    positive_weights = sorted(weight for weight in weights.values() if weight > 0)
    high_weight_cutoff = positive_weights[len(positive_weights) // 2]
    cell = slack.get(f"{candidate_card['archetype']}|{candidate_card['native_overall']}", {})
    attributes = []
    for attribute, weight in weights.items():
        current = current_card.get("native_ratings", {}).get(attribute)
        candidate = candidate_card.get("native_ratings", {}).get(attribute)
        if current is None or candidate is None or current == candidate:
            continue
        slack_range = cell.get("attributes", {}).get(attribute, {}).get("range")
        attributes.append(
            {
                "attribute": attribute,
                "delta": candidate - current,
                "model_weight": weight,
                "weighted_score_contribution": round(
                    (candidate - current) * weight / total_weight, 6
                ),
                "weight_tier": "HIGH" if weight >= high_weight_cutoff else "LOW",
                "same_ovr_range": slack_range,
            }
        )
    return {
        "status": "PROFILED",
        "interpretation": (
            "model contribution is production evidence; same-OVR range is hypothesis evidence"
        ),
        "positive_gain_on_high_weight_attributes": round(
            sum(
                row["weighted_score_contribution"]
                for row in attributes
                if row["weight_tier"] == "HIGH" and row["delta"] > 0
            ),
            6,
        ),
        "positive_gain_on_low_weight_attributes": round(
            sum(
                row["weighted_score_contribution"]
                for row in attributes
                if row["weight_tier"] == "LOW" and row["delta"] > 0
            ),
            6,
        ),
        "attributes": attributes,
    }


def target_rows(
    ranked: list[dict], cards: dict[str, dict], curves: dict, registry: dict
) -> list[dict]:
    replacements = json.loads(
        (ROOT / "data/production/roster/replacement_candidates.json").read_text(encoding="utf-8")
    )
    slack = json.loads(
        (ROOT / "data/research/op_x_024/same_cell_slack.json").read_text(encoding="utf-8")
    )
    output = []
    for current_name, candidate_name in TARGETS:
        roster_row = next(row for row in replacements if row["current"] == current_name)
        candidate_id = next(
            choice["card_id"]
            for choice in roster_row["candidates"].values()
            if choice["player_name"] == candidate_name
        )
        current = next(
            row
            for row in ranked
            if row["player_name"] == current_name
            and row["position_rank"] == roster_row["current_rank"]
        )
        candidate = next(row for row in ranked if row["card_id"] == candidate_id)
        output.append(
            {
                "current": current_name,
                "candidate": candidate_name,
                "current_card_id": current["card_id"],
                "candidate_card_id": candidate_id,
                **upgrade_value(current, candidate, ranked, curves),
                "attribute_efficiency": attribute_efficiency(
                    cards[current["card_id"]], cards[candidate_id], candidate, registry, slack
                ),
            }
        )
    return output


def intrinsic() -> None:
    ranked, cards, curves, registry = context()
    targets = target_rows(ranked, cards, curves, registry)
    scarcity = {row["candidate_card_id"]: row["scarcity"] for row in targets}
    replacement = {
        row["candidate_card_id"]: {
            key: row[key]
            for key in (
                "current_percentile",
                "candidate_percentile",
                "percentile_gain",
                "rank_gain",
                "replacement_level_score",
                "current_above_replacement",
                "candidate_above_replacement",
                "distance_toward_elite",
                "confidence",
            )
        }
        for row in targets
    }
    write("population_value_curves.json", curves)
    write(
        "scarcity.json",
        {"definition": "inverse local density within +/-0.5 score", "targets": scarcity},
    )
    write("replacement_value.json", replacement)
    write("roster_marginal_value.json", targets)
    spec = {
        "version": "op-x-028-v1",
        "market_price_included": False,
        "weights": VALUE_INDEX_WEIGHTS,
        "confidence_factors": {"HIGH": 1.0, "MEDIUM": 0.85, "LOW": 0.65},
        "normalization": {
            "score_gain": "gain / within-position p50-to-p90 score span, capped [0,1]",
            "percentile_gain": "gain / 25 percentile points, capped [0,1]",
            "rank_gain": "gain / position population, capped [0,1]",
            "scarcity": "1 - comparable cards within +/-0.5 / position population",
            "roster_need": "(100 - current percentile) / 25, capped [0,1]",
        },
        "class_method": "contextual efficiency quintiles within a declared opportunity set",
        "class_warning": "classification is not an estimate of auction clearing price",
        "price_grid": PRICE_GRID,
    }
    write("value_index_spec.json", spec)
    sensitivity = {}
    for row in targets:
        base = row["value_index"]
        sensitivity[row["candidate_card_id"]] = {
            component: round(base - row["confidence_factor"] * weight * 100 * value, 6)
            for component, weight in VALUE_INDEX_WEIGHTS.items()
            for value in [row["value_index_components"][component]]
        }
    write(
        "value_index_sensitivity.json",
        {
            "method": "one-at-a-time component ablation; values are resulting index scores",
            "targets": sensitivity,
        },
    )
    write(
        "price_sensitivity.json",
        {row["candidate_card_id"]: price_sensitivity(row) for row in targets},
    )
    freeze_files = [
        "population_value_curves.json",
        "scarcity.json",
        "replacement_value.json",
        "roster_marginal_value.json",
        "value_index_spec.json",
        "value_index_sensitivity.json",
        "price_sensitivity.json",
    ]
    digest = hashlib.sha256()
    for name in freeze_files:
        digest.update(name.encode())
        digest.update((OUTPUT / name).read_bytes())
    write("pre_price_freeze.json", {"sha256": digest.hexdigest(), "files": freeze_files})


def market() -> None:
    ranked, cards, curves, registry = context()
    targets = target_rows(ranked, cards, curves, registry)
    observations = json.loads(
        (ROOT / "data/research/op_x_027/roster_market_decisions.json").read_text(encoding="utf-8")
    )["decisions"]
    price_by_candidate = {row["candidate"]: row for row in observations}
    evaluated = []
    for row in targets:
        observation = price_by_candidate[row["candidate"]]
        evaluated.append(
            {
                **row,
                "observed_price": observation["public_display_price"],
                "price_evidence_confidence": observation["confidence"],
                "market_verdict": "PRICE CHECK REQUIRED",
                "score_gain_per_1000": round(
                    row["score_gain"] * 1000 / observation["public_display_price"], 8
                ),
                "rank_gain_per_1000": round(
                    row["rank_gain"] * 1000 / observation["public_display_price"], 8
                ),
            }
        )
    classified = relative_value_classes(evaluated)
    write(
        "current_target_valuations.json",
        {
            "scientific_control": (
                "prices were evaluated after the intrinsic freeze and never enter the index"
            ),
            "targets": classified,
        },
    )
    candidates = [
        {
            "candidate": row["candidate"],
            "net_cost": row["observed_price"],
            "score_improvement": row["value_index"],
        }
        for row in classified
    ]
    allocations = {
        str(budget): optimize_budget(candidates, budget)
        for budget in (
            50_000,
            100_000,
            150_000,
            250_000,
            500_000,
            750_000,
            1_000_000,
            2_000_000,
            5_000_000,
        )
    }
    write(
        "budget_allocations.json",
        {
            "objective": "maximize frozen Pancake Value Index under observed-price budget",
            "price_warning": "OP-X-027 public displays are low-confidence observations",
            "allocations": allocations,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("intrinsic", "market"))
    args = parser.parse_args()
    intrinsic() if args.phase == "intrinsic" else market()

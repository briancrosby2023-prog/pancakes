"""Generate compact OP-X-030 attribute intelligence artifacts."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from operation_pancake.production.attributes import (
    AttributeIntelligence,
    population_attribute_stats,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/op_x_030"


def write(name: str, payload: object) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def outliers(intelligence: AttributeIntelligence) -> tuple[list[dict], list[dict]]:
    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in intelligence.ranked:
        groups[(row["position_family"], row["archetype"], row["native_overall"])].append(row)
    high, low = [], []
    for (family, archetype, overall), rows in groups.items():
        if len(rows) < 3:
            continue
        mean = statistics.mean(row["score"] for row in rows)
        ordered = sorted(rows, key=lambda row: row["score"])
        for row in rows:
            residual = row["score"] - mean
            record = {
                "card_id": row["card_id"],
                "player_name": row["player_name"],
                "position_family": family,
                "archetype": archetype,
                "overall": overall,
                "score": row["score"],
                "same_ovr_peer_count": len(rows),
                "same_ovr_percentile": round(
                    100 * sum(peer["score"] <= row["score"] for peer in ordered) / len(rows), 6
                ),
                "score_residual": round(residual, 6),
                "attribute_drivers": [
                    item["attribute"]
                    for item in intelligence.contribution(row["card_id"])["contributions"][:3]
                ],
            }
            (high if residual >= 0 else low).append(record)
    high.sort(key=lambda row: (-row["score_residual"], row["card_id"]))
    low.sort(key=lambda row: (row["score_residual"], row["card_id"]))
    return high[:250], low[:250]


def dominance(intelligence: AttributeIntelligence) -> list[dict]:
    groups: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in intelligence.ranked:
        groups[(row["position_family"], row["archetype"], row["native_overall"])].append(row)
    results = []
    for (family, archetype, overall), rows in groups.items():
        if len(rows) < 2:
            continue
        best, worst = (
            max(rows, key=lambda row: row["score"]),
            min(rows, key=lambda row: row["score"]),
        )
        if best["score"] - worst["score"] < 0.5:
            continue
        attributes = [
            item["attribute"]
            for item in intelligence.contribution(best["card_id"])["contributions"]
        ]
        best_ratings = intelligence.cards[best["card_id"]]["native_ratings"]
        worst_ratings = intelligence.cards[worst["card_id"]]["native_ratings"]
        comparable = [attribute for attribute in attributes if attribute in worst_ratings]
        strict = (
            comparable
            and all(best_ratings[a] >= worst_ratings[a] for a in comparable)
            and any(best_ratings[a] > worst_ratings[a] for a in comparable)
        )
        results.append(
            {
                "position_family": family,
                "archetype": archetype,
                "overall": overall,
                "winner": best["player_name"],
                "winner_card_id": best["card_id"],
                "loser": worst["player_name"],
                "loser_card_id": worst["card_id"],
                "score_difference": round(best["score"] - worst["score"], 6),
                "classification": "STRICT ATTRIBUTE DOMINANCE" if strict else "MODEL DOMINANCE",
            }
        )
    return sorted(results, key=lambda row: (-row["score_difference"], row["winner_card_id"]))[:250]


def roster_diagnosis(intelligence: AttributeIntelligence) -> dict:
    roster = json.loads(
        (ROOT / "data/production/roster/scored_roster.json").read_text(encoding="utf-8")
    )
    starters = []
    weaknesses: dict[str, list[float]] = defaultdict(list)
    for row in roster:
        if row.get("starter_status") != "STARTER" or not row.get("card_id"):
            continue
        explanation = intelligence.contribution(row["card_id"])
        if explanation.get("status") != "EXPLAINED":
            starters.append({"player_name": row["player_name"], "status": explanation["status"]})
            continue
        by_percentile = sorted(
            explanation["contributions"], key=lambda item: item["attribute_percentile"]
        )
        for item in by_percentile:
            weaknesses[f"{explanation['position_family']}|{item['attribute']}"].append(
                item["attribute_percentile"]
            )
        starters.append(
            {
                "player_name": row["player_name"],
                "card_id": row["card_id"],
                "position_family": explanation["position_family"],
                "score": explanation["score"],
                "best_modeled_strengths": explanation["contributions"][:3],
                "largest_modeled_deficiencies": by_percentile[:3],
            }
        )
    aggregate = sorted(
        (
            {
                "position_attribute": key,
                "mean_percentile": round(statistics.mean(values), 6),
                "starter_observations": len(values),
            }
            for key, values in weaknesses.items()
        ),
        key=lambda row: (row["mean_percentile"], row["position_attribute"]),
    )
    return {"starters": starters, "largest_normalized_weaknesses": aggregate[:20]}


def main() -> None:
    intelligence = AttributeIntelligence(ROOT)
    stats = population_attribute_stats(intelligence)
    write("attribute_population_stats.json", stats)
    write(
        "attribute_scarcity.json",
        {
            key: {"n": row["n"], "elite_thresholds": {k: row[k] for k in ("p90", "p95", "p98")}}
            for key, row in stats.items()
        },
    )
    marginal = {}
    for model in intelligence.registry["models"]:
        if not model["production"]:
            continue
        for profile, weights in model["profiles"].items():
            denominator = sum(weights.values())
            marginal[f"{model['id']}|{model['version']}|{profile}"] = {
                attribute: {
                    str(delta): round(weight * delta / denominator, 9) for delta in (1, 2, 3, 5)
                }
                for attribute, weight in weights.items()
            }
    write("marginal_model_value.json", marginal)
    high, low = outliers(intelligence)
    write("football_value_outliers.json", high)
    write("inefficient_ovr_profiles.json", low)
    write("same_ovr_dominance.json", dominance(intelligence))
    write(
        "differentiation_index.json",
        [
            {"position_archetype_attribute": key, **value}
            for key, value in sorted(
                stats.items(), key=lambda item: (-item[1]["differentiation_index"], item[0])
            )
        ],
    )
    diagnosis = roster_diagnosis(intelligence)
    write("roster_attribute_diagnosis.json", diagnosis)
    valuations = json.loads(
        (ROOT / "data/research/op_x_028/current_target_valuations.json").read_text(encoding="utf-8")
    )["targets"]
    decompositions = []
    for row in valuations:
        result = intelligence.compare(row["current_card_id"], row["candidate_card_id"])
        result["near_equivalent_alternatives"] = intelligence.alternatives(
            row["candidate_card_id"], 1.0
        )
        decompositions.append(result)
    write("current_upgrade_decomposition.json", decompositions)
    te_stats = {key: value for key, value in stats.items() if key.startswith("TE|")}
    slack = json.loads(
        (ROOT / "data/research/op_x_024/same_cell_slack.json").read_text(encoding="utf-8")
    )
    te_archetypes = {
        row["archetype"] for row in intelligence.ranked if row["position_family"] == "TE"
    }
    ranges: dict[str, list[float]] = defaultdict(list)
    for key, cell in slack.items():
        archetype, _overall = key.rsplit("|", 1)
        if archetype not in te_archetypes:
            continue
        for attribute, detail in cell.get("attributes", {}).items():
            ranges[attribute].append(detail["range"])
    write(
        "te_economics_overlay.json",
        {
            "production_coefficients_modified": False,
            "same_ovr_slack_status": "SUPPORTED DESCRIPTIVE EVIDENCE",
            "attribute_economics_status": "HYPOTHESIS",
            "legacy_403_405_status": "BLOCKED",
            "te_model_stats": te_stats,
            "mean_same_ovr_ranges": {
                key: round(statistics.mean(values), 6) for key, values in ranges.items()
            },
        },
    )
    demonstration = {
        "why_one_player_outranks_another": decompositions[0],
        "same_ovr_hidden_value": high[0] if high else None,
        "near_equivalent_alternatives": decompositions[0]["near_equivalent_alternatives"],
        "roster_weakness": diagnosis["largest_normalized_weaknesses"][:5],
        "attribute_specific_upgrade_search": intelligence.attribute_upgrades(
            valuations[0]["current_card_id"], "RBK", min_score_gain=1
        ),
    }
    write("product_demonstration.json", demonstration)


if __name__ == "__main__":
    main()

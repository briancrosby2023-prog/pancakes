"""Recover production-scored quality for the Supercharged control cohort."""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORED = ROOT / "data/production/cfb27_scored_population.json"
OUT = ROOT / "data/research/execution_loop/supercharged_quality_controls.json"
TARGETS = {
    "Sutton Smith": "27-280008728",
    "Bo Jackson": "27-280024922",
    "Hayden Hansen": "27-280001353",
    "Christian Gray": "27-280021403",
    "Daniel Wingate": "27-280000639",
    "Jake Guarnera": "27-280019722",
}


def percentile(value: float, values: list[float]) -> float:
    return round(100.0 * sum(v <= value for v in values) / len(values), 6)


def main() -> None:
    rows = json.loads(SCORED.read_text())
    by_family: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("score") is not None:
            by_family[row["position_family"]].append(float(row["score"]))
    results = []
    for name, external in TARGETS.items():
        external_values = {external, external.removeprefix("27-")}
        matches = [
            r
            for r in rows
            if r.get("player_name") == name
            and str(r.get("source_card_id", r.get("external_card_id", "")))
            in external_values
        ]
        if not matches:
            matches = [
                r
                for r in rows
                if r.get("player_name") == name
                and r.get("native_overall") in {87, 88}
                and r.get("program") == "Supercharged"
            ]
        if len(matches) != 1:
            results.append(
                {
                    "player_name": name,
                    "external_card_id": external,
                    "status": "UNRESOLVED",
                    "matches": len(matches),
                }
            )
            continue
        row = matches[0]
        score = row.get("score")
        family = row.get("position_family")
        position_percentile = (
            None if score is None else percentile(float(score), by_family[family])
        )
        results.append(
            {
                "player_name": name,
                "external_card_id": external,
                "card_id": row.get("card_id"),
                "overall": row.get("native_overall"),
                "program": row.get("program"),
                "position": row.get("position"),
                "position_family": family,
                "archetype": row.get("archetype"),
                "score": score,
                "score_confidence": row.get("score_confidence"),
                "attribute_coverage": row.get("attribute_coverage"),
                "position_rank": row.get("position_rank"),
                "position_percentile": position_percentile,
                "status": "SCORED" if score is not None else "UNSCORED",
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"cohort": results}, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cohort": results}, indent=2))


if __name__ == "__main__":
    main()

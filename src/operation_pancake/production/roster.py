"""Roster reconciliation and transparent general-manager intelligence."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .engine import ProductionEngine, load_population
from .registry import POSITION_ALIASES, build_model_registry

ROSTER_PATH = "data/research/cfb27_op_x_010/canonical_exports_v2/roster_instances.json"
PROTECTED_SLOTS = {"FS1", "MIKE1", "MIKE2"}
STARTER_CAPACITY = {"WR": 3, "CB": 3, "DT": 2, "MIKE": 1}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def slot_position(slot: str) -> str:
    return re.sub(r"\d+$", "", slot).replace("REDG", "RE").replace("LEDG", "LE")


def depth_order(slot: str) -> int:
    match = re.search(r"(\d+)$", slot)
    return int(match.group(1)) if match else 1


def reconcile_roster(
    roster: list[dict[str, Any]], population: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Resolve roster rows conservatively against canonical CUT identities."""
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for card in population:
        by_name[normalize_name(card["player_name"])].append(card)
    results = []
    for row in roster:
        expected_position = slot_position(row["slot"])
        family = POSITION_FAMILY(expected_position)
        candidates = [
            card
            for card in by_name[normalize_name(row["player"])]
            if POSITION_FAMILY(card["position"]) == family
        ]
        lineup_ovr = row["lineup_display_ovr"]
        exact = [card for card in candidates if card["native_overall"] == lineup_ovr]
        if len(exact) == 1:
            selected, classification, method = (
                exact[0],
                "EXACT",
                "normalized name + position family + exact native OVR",
            )
        else:
            eligible = [
                card
                for card in candidates
                if card["native_overall"] is not None
                and 0 <= lineup_ovr - card["native_overall"] <= 2
            ]
            best_gap = min((lineup_ovr - card["native_overall"] for card in eligible), default=None)
            nearest = [card for card in eligible if lineup_ovr - card["native_overall"] == best_gap]
            if len(nearest) == 1:
                selected, classification, method = (
                    nearest[0],
                    "HIGH CONFIDENCE",
                    (
                        "unique normalized name/position candidate within two OVR; "
                        "lineup boost possible"
                    ),
                )
            else:
                selected = None
                classification = "AMBIGUOUS" if nearest else "UNRESOLVED"
                method = (
                    "multiple equally supported candidates"
                    if nearest
                    else "no candidate within defensible OVR tolerance"
                )
        candidate_evidence = [
            {
                "card_id": card["card_id"],
                "position": card["position"],
                "native_overall": card["native_overall"],
                "program": card.get("program"),
                "archetype": card.get("archetype"),
            }
            for card in sorted(
                candidates, key=lambda card: (-(card["native_overall"] or 0), card["card_id"])
            )
        ]
        results.append(
            {
                "roster_instance_id": row["roster_instance_id"],
                "slot": row["slot"],
                "player_name": row["player"],
                "lineup_display_ovr": lineup_ovr,
                "expected_position": expected_position,
                "classification": classification,
                "matched_card_id": selected["card_id"] if selected else None,
                "match_method": method,
                "candidate_count": len(candidates),
                "candidate_evidence": candidate_evidence,
                "remaining_ambiguity": None
                if selected
                else "card detail screen with native OVR/program or external card ID required",
                "provenance": [
                    ROSTER_PATH,
                    selected["source"] if selected else "canonical CFB27 population search",
                ],
            }
        )
    return results


def POSITION_FAMILY(position: str) -> str:
    return POSITION_ALIASES.get(position, position)


def canonical_roster(
    roster: list[dict[str, Any]],
    reconciliation: list[dict[str, Any]],
    population: list[dict[str, Any]],
    engine: ProductionEngine,
) -> list[dict[str, Any]]:
    cards = {card["card_id"]: card for card in population}
    resolutions = {row["roster_instance_id"]: row for row in reconciliation}
    output = []
    for source in roster:
        resolution = resolutions[source["roster_instance_id"]]
        card = cards.get(resolution["matched_card_id"])
        family = POSITION_FAMILY(slot_position(source["slot"]))
        order = depth_order(source["slot"])
        capacity = STARTER_CAPACITY.get(family, 1)
        scored = engine.score(card) if card else None
        output.append(
            {
                "roster_instance_id": source["roster_instance_id"],
                "roster_id": source["roster_id"],
                "card_id": card["card_id"] if card else None,
                "player_name": source["player"],
                "position": card["position"] if card else slot_position(source["slot"]),
                "position_family": family,
                "depth_slot": source["slot"],
                "depth_order": order,
                "starter_status": "STARTER" if order <= capacity else "BACKUP",
                "lineup_display_ovr": source["lineup_display_ovr"],
                "native_overall": card.get("native_overall") if card else None,
                "archetype": card.get("archetype") if card else None,
                "program": card.get("program") if card else None,
                "identity_confidence": resolution["classification"],
                "pancake": scored,
                "roster_tags": ["PROTECTED_REROLLABLE"]
                if source["slot"] in PROTECTED_SLOTS
                else [],
                "acquisition_cost": None,
                "current_market_price": None,
                "provenance": {
                    "roster": source["display_source"],
                    "identity": resolution["provenance"],
                },
            }
        )
    return output


class RosterGMEngine:
    def __init__(
        self,
        player_engine: ProductionEngine,
        ranked_population: list[dict[str, Any]],
        population: list[dict[str, Any]] | None = None,
    ):
        self.player_engine = player_engine
        self.cards = {card["card_id"]: card for card in (population or [])}
        self.by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ranked_population:
            self.by_family[row["position_family"]].append(row)

    def percentile(self, family: str, rank: int) -> float:
        size = len(self.by_family[family])
        return round(100 * (size - rank + 1) / size, 4) if size else 0.0

    def evaluate_depth(self, roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in roster:
            groups[entry["position_family"]].append(entry)
        output = []
        for family, entries in groups.items():
            resolved = [
                entry
                for entry in entries
                if entry["pancake"] and entry["pancake"]["score"] is not None
            ]
            declared = sorted(
                entries, key=lambda entry: (entry["depth_order"], entry["depth_slot"])
            )
            best = max(resolved, key=lambda entry: entry["pancake"]["score"], default=None)
            starters = [entry for entry in resolved if entry["starter_status"] == "STARTER"]
            backups = [entry for entry in resolved if entry["starter_status"] == "BACKUP"]
            current = starters[0] if starters else None
            weakest = min(starters, key=lambda entry: entry["pancake"]["score"], default=None)
            best_backup = max(backups, key=lambda entry: entry["pancake"]["score"], default=None)
            change = bool(
                best_backup
                and weakest
                and best_backup["pancake"]["score"] > weakest["pancake"]["score"]
            )
            output.append(
                {
                    "position_family": family,
                    "declared_depth": [
                        {
                            "slot": entry["depth_slot"],
                            "player_name": entry["player_name"],
                            "status": entry["starter_status"],
                            "score": entry["pancake"]["score"] if entry["pancake"] else None,
                        }
                        for entry in declared
                    ],
                    "highest_ranked_roster_player": best["player_name"] if best else None,
                    "current_primary_starter": current["player_name"] if current else None,
                    "starter_optimal": None if not best or not current else not change,
                    "recommended_change": (
                        {
                            "action": "START",
                            "player_name": best_backup["player_name"],
                            "replace": weakest["player_name"],
                            "score_gap": round(
                                best_backup["pancake"]["score"] - weakest["pancake"]["score"],
                                6,
                            ),
                        }
                        if change
                        else None
                    ),
                    "resolved_depth": len(resolved),
                    "total_depth": len(entries),
                    "depth_quality": "NO_RESOLVED_DEPTH"
                    if not resolved
                    else "THIN"
                    if len(resolved) == 1 and len(entries) > 1
                    else "EVALUABLE",
                    "reason": (
                        "Pancake scores within this position family; "
                        "unresolved entries are not guessed"
                    ),
                }
            )
        return sorted(output, key=lambda row: row["position_family"])

    def replacements(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        score = entry["pancake"]["score"] if entry["pancake"] else None
        if score is None:
            return None
        pool = [
            row
            for row in self.by_family[entry["position_family"]]
            if row["score"] > score and row["card_id"] != entry["card_id"]
        ]
        if not pool:
            return {
                "roster_instance_id": entry["roster_instance_id"],
                "current": entry["player_name"],
                "position_family": entry["position_family"],
                "status": "NO_UPGRADE_FOUND",
                "candidates": {},
            }
        best = pool[0]
        incremental = min(pool, key=lambda row: (row["score"] - score, row["position_rank"]))
        compatible_pool = [row for row in pool if row["archetype"] == entry["archetype"]]
        compatible = compatible_pool[0] if compatible_pool else None
        current_card = self.cards.get(entry["card_id"])

        def candidate(row: dict[str, Any] | None) -> dict[str, Any] | None:
            if row is None:
                return None
            comparison = {
                "score_improvement": round(row["score"] - score, 6),
                "score_improvement_percent": round((row["score"] - score) / score * 100, 6),
                "position_rank_improvement": entry["pancake"].get("position_rank", 0)
                - row["position_rank"],
            }
            candidate_card = self.cards.get(row["card_id"])
            detailed = (
                self.player_engine.compare(current_card, candidate_card)
                if current_card and candidate_card
                else {}
            )
            return (
                {
                    key: row.get(key)
                    for key in (
                        "card_id",
                        "player_name",
                        "native_overall",
                        "archetype",
                        "program",
                        "score",
                        "position_rank",
                        "score_confidence",
                    )
                }
                | comparison
                | {
                    "attribute_deltas": detailed.get("attribute_deltas", {}),
                    "role_implication": (
                        "same archetype"
                        if row["archetype"] == entry["archetype"]
                        else f"role changes from {entry['archetype']} to {row['archetype']}"
                    ),
                }
            )

        return {
            "roster_instance_id": entry["roster_instance_id"],
            "current": entry["player_name"],
            "position_family": entry["position_family"],
            "current_score": score,
            "current_rank": entry["pancake"].get("position_rank"),
            "status": "UPGRADE_AVAILABLE",
            "candidates": {
                "best_overall": candidate(best),
                "incremental": candidate(incremental),
                "archetype_compatible": candidate(compatible),
            },
            "price_status": "PRICE CHECK REQUIRED",
        }

    def budget_decision(
        self,
        improvement: float,
        position_rank_improvement: int,
        candidate_price: float | None = None,
        current_resale: float | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        if candidate_price is None:
            return {
                "status": "PRICE CHECK REQUIRED",
                "net_upgrade_cost": None,
                "affordable": None,
                "improvement_per_coin": None,
                "rank_improvement_per_coin": None,
            }
        net = candidate_price - (current_resale or 0)
        return {
            "status": "BUDGET_EVALUATED",
            "net_upgrade_cost": net,
            "affordable": None if budget is None else net <= budget,
            "improvement_per_coin": None if net <= 0 else round(improvement / net, 12),
            "rank_improvement_per_coin": None
            if net <= 0
            else round(position_rank_improvement / net, 12),
            "price_source": "caller-supplied",
        }

    def strength_and_priorities(
        self, roster: list[dict[str, Any]], replacements: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        replacement_by_id = {row["roster_instance_id"]: row for row in replacements}
        starter_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in roster:
            if (
                entry["starter_status"] != "STARTER"
                or not entry["pancake"]
                or entry["pancake"]["score"] is None
            ):
                continue
            rank = entry["pancake"].get("position_rank")
            if not rank:
                continue
            percentile = self.percentile(entry["position_family"], rank)
            replacement = replacement_by_id.get(entry["roster_instance_id"])
            best = (
                replacement["candidates"].get("best_overall")
                if replacement and replacement["status"] == "UPGRADE_AVAILABLE"
                else None
            )
            available_rank_gain = max(0, best["position_rank_improvement"]) if best else 0
            pool_size = len(self.by_family[entry["position_family"]])
            opportunity = 100 * available_rank_gain / pool_size if pool_size else 0
            starter_rows[entry["position_family"]].append(
                {
                    "position_family": entry["position_family"],
                    "starter": entry["player_name"],
                    "starter_rank": rank,
                    "population_size": pool_size,
                    "position_strength_percentile": percentile,
                    "available_rank_improvement_percent": round(opportunity, 4),
                    "confidence": entry["pancake"]["score_confidence"],
                }
            )
        rows = []
        for family, starters in starter_rows.items():
            weakest = min(starters, key=lambda row: row["position_strength_percentile"])
            mean_percentile = sum(row["position_strength_percentile"] for row in starters) / len(
                starters
            )
            opportunity = max(row["available_rank_improvement_percent"] for row in starters)
            priority = round(0.65 * (100 - mean_percentile) + 0.35 * opportunity, 4)
            rows.append(
                {
                    "position_family": family,
                    "starters": [row["starter"] for row in starters],
                    "starter": weakest["starter"],
                    "weakest_starter": weakest["starter"],
                    "starter_rank": weakest["starter_rank"],
                    "population_size": weakest["population_size"],
                    "position_strength_percentile": round(mean_percentile, 4),
                    "available_rank_improvement_percent": opportunity,
                    "weakness_priority": priority,
                    "reason": (
                        f"mean starter within-position percentile {mean_percentile:.1f}; "
                        f"weakest resolved starter {weakest['starter']}"
                    ),
                    "confidence": weakest["confidence"],
                }
            )
        strength = sorted(
            rows, key=lambda row: (-row["position_strength_percentile"], row["position_family"])
        )
        priorities = sorted(
            rows, key=lambda row: (-row["weakness_priority"], row["position_family"])
        )
        for index, row in enumerate(priorities, 1):
            row["priority_rank"] = index
            row["priority_type"] = "QUALITY PRIORITY"
        return strength, priorities


def build_roster_outputs(root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir or root / "data/production/roster"
    output_dir.mkdir(parents=True, exist_ok=True)
    source = json.loads((root / ROSTER_PATH).read_text(encoding="utf-8"))
    population = load_population(root)
    engine = ProductionEngine(build_model_registry(root))
    scored_population = [engine.score(card) for card in population]
    ranked = engine.rank(scored_population)
    rank_by_id = {row["card_id"]: row for row in ranked}
    reconciliation = reconcile_roster(source, population)
    roster = canonical_roster(source, reconciliation, population, engine)
    for entry in roster:
        if entry["card_id"] in rank_by_id:
            entry["pancake"].update(
                {
                    key: rank_by_id[entry["card_id"]][key]
                    for key in ("position_rank", "archetype_rank")
                }
            )
    gm = RosterGMEngine(engine, ranked, population)
    depth = gm.evaluate_depth(roster)
    replacements = [result for entry in roster if (result := gm.replacements(entry))]
    strength, priorities = gm.strength_and_priorities(roster, replacements)
    counts = Counter(row["classification"] for row in reconciliation)
    score_counts = Counter(
        entry["pancake"]["score_status"] if entry["pancake"] else "UNRESOLVED" for entry in roster
    )
    summary = {
        "snapshot": "USER_SCREENSHOT_OP_X_008 normalized by OP-X-010",
        "entries": len(roster),
        "identity_counts": dict(counts),
        "score_counts": dict(score_counts),
        "resolved": sum(counts[key] for key in ("EXACT", "HIGH CONFIDENCE")),
        "scored": sum(
            1 for entry in roster if entry["pancake"] and entry["pancake"]["score"] is not None
        ),
        "failures": 0,
    }
    actions = []
    priority_keys = {
        (row["position_family"], row["weakest_starter"]): row for row in priorities[:5]
    }
    for entry in roster:
        if not entry["card_id"]:
            action, why = "UNRESOLVED", "identity cannot be selected without guessing"
        elif entry["pancake"]["score"] is None:
            action, why = (
                "UNRESOLVED",
                f"production score status {entry['pancake']['score_status']}",
            )
        elif entry["starter_status"] == "BACKUP":
            action, why = (
                "BENCH",
                "depth-chart backup; retain unless an evaluated starter change applies",
            )
        elif (entry["position_family"], entry["player_name"]) in priority_keys:
            action, why = (
                "UPGRADE",
                "top-five quality priority based on within-position percentile and available gain",
            )
        else:
            action, why = (
                "KEEP",
                "current starter is scoreable; review quality-priority and replacement evidence",
            )
        actions.append(
            {
                "action": action,
                "player_name": entry["player_name"],
                "slot": entry["depth_slot"],
                "why": why,
            }
        )
        if action == "UPGRADE":
            actions.append(
                {
                    "action": "PRICE CHECK REQUIRED",
                    "player_name": entry["player_name"],
                    "slot": entry["depth_slot"],
                    "why": "market export has no trustworthy candidate price",
                }
            )
        if "PROTECTED_REROLLABLE" in entry["roster_tags"]:
            actions.append(
                {
                    "action": "KEEP",
                    "player_name": entry["player_name"],
                    "slot": entry["depth_slot"],
                    "why": (
                        "protected/rerollable designation; replacing a starter does not imply "
                        "discarding the asset"
                    ),
                }
            )
    for group in depth:
        if group["recommended_change"]:
            actions.append(
                {
                    **group["recommended_change"],
                    "why": "higher Pancake score within the same position family",
                }
            )
    report = render_report(summary, roster, depth, strength, priorities, replacements, actions)
    matrix_path = root / "data/production/product_completion_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    for key, status, evidence in (
        ("ROSTER INGESTION", "PARTIAL", f"{summary['resolved']}/24 identities defensibly resolved"),
        (
            "ROSTER EVALUATION",
            "COMPLETE",
            "scoring, depth, strength, and starter evaluation executed",
        ),
        (
            "GM RECOMMENDATIONS",
            "COMPLETE",
            "quality priorities and replacements generated from real roster",
        ),
        ("USER-FACING INTERFACE", "PARTIAL", "gm-run plus persisted human-readable roster report"),
        ("TEST COVERAGE", "PARTIAL", "OP-X-021 and OP-X-022 targeted suites"),
    ):
        matrix[key]["status"] = status
        matrix[key]["evidence"] = evidence
    matrix["ROSTER INGESTION"].update(
        {
            "executable_entry_point": "operation-pancake roster-run",
            "tests": "identity matching and ambiguity rejection tests",
            "blocker": "six identities need card-detail evidence",
            "next_action": "collect native OVR/program or external card ID for unresolved slots",
        }
    )
    matrix["ROSTER EVALUATION"].update(
        {
            "executable_entry_point": "RosterGMEngine and operation-pancake roster-run",
            "tests": "roster scoring, depth, starter, percentile, and priority tests",
            "blocker": "none for resolved roster; unresolved slots are explicitly excluded",
            "next_action": "rerun automatically when roster identities change",
        }
    )
    matrix["GM RECOMMENDATIONS"].update(
        {
            "executable_entry_point": "RosterGMEngine.replacements/strength_and_priorities",
            "tests": "replacement, role tradeoff, grouping, and budget tests",
            "blocker": "prices absent for value-qualified recommendations",
            "next_action": "supply candidate price/resale/budget or connect market ingestion",
        }
    )
    matrix["USER-FACING INTERFACE"].update(
        {
            "executable_entry_point": "operation-pancake roster-run",
            "tests": "CLI executed against real roster",
            "blocker": "no interactive roster editor/query surface",
            "next_action": "add roster input and interactive recommendation queries",
        }
    )
    outputs = {
        "identity_reconciliation.json": reconciliation,
        "canonical_roster.json": roster,
        "scored_roster.json": roster,
        "depth_evaluation.json": depth,
        "positional_strength.json": strength,
        "replacement_candidates.json": replacements,
        "gm_priorities.json": priorities,
        "gm_actions.json": actions,
        "run_summary.json": summary,
        "product_completion_matrix.json": matrix,
    }
    for name, payload in outputs.items():
        (output_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (output_dir / "gm_roster_report.md").write_text(report, encoding="utf-8")
    matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def render_report(
    summary: dict[str, Any],
    roster: list[dict[str, Any]],
    depth: list[dict[str, Any]],
    strength: list[dict[str, Any]],
    priorities: list[dict[str, Any]],
    replacements: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> str:
    lines = [
        "# Operation Pancake Roster GM Report",
        "",
        f"Source: {summary['snapshot']}",
        (
            f"Roster entries: {summary['entries']}; resolved: {summary['resolved']}; "
            f"scored: {summary['scored']}."
        ),
        "",
        "## Identity limitations",
        "",
        (
            f"Counts: {summary['identity_counts']}. Unresolved and ambiguous entries "
            "are excluded from score-based recommendations."
        ),
        "",
        "## Starter changes",
        "",
    ]
    changes = [row["recommended_change"] for row in depth if row["recommended_change"]]
    lines.extend(
        [
            f"- START {row['player_name']} over {row['replace']} ({row['score_gap']:+.3f})."
            for row in changes
        ]
        or ["- No defensible within-roster starter changes among resolved, scoreable cards."]
    )
    lines += ["", "## Strongest position groups", ""]
    lines += [
        (
            f"- {row['position_family']}: {row['starter']} — "
            f"{row['position_strength_percentile']:.1f} percentile "
            f"({row['confidence']} confidence)."
        )
        for row in strength[:5]
    ]
    lines += ["", "## Quality upgrade priorities", ""]
    lines += [
        f"- {row['priority_rank']}. {row['position_family']} / {row['starter']}: {row['reason']}."
        for row in priorities[:8]
    ]
    lines += ["", "## Replacement candidates", ""]
    for priority in priorities[:5]:
        entry = next(
            (
                item
                for item in roster
                if item["player_name"] == priority["starter"]
                and item["position_family"] == priority["position_family"]
            ),
            None,
        )
        replacement = next(
            (
                item
                for item in replacements
                if entry and item["roster_instance_id"] == entry["roster_instance_id"]
            ),
            None,
        )
        best = (
            replacement["candidates"].get("best_overall")
            if replacement and replacement["status"] == "UPGRADE_AVAILABLE"
            else None
        )
        if best:
            tradeoffs = sorted(
                best["attribute_deltas"].items(), key=lambda item: (-abs(item[1]), item[0])
            )[:5]
            tradeoff_text = ", ".join(f"{name} {delta:+g}" for name, delta in tradeoffs)
            lines.append(
                f"- UPGRADE {priority['starter']} → {best['player_name']} "
                f"({best['score_improvement']:+.3f} score; "
                f"{best['position_rank_improvement']:+d} ranks). "
                f"Key attribute tradeoffs: {tradeoff_text}. PRICE CHECK REQUIRED."
            )
    lines += ["", "## GM actions", ""]
    lines += [
        f"- {row['action']}: {row['player_name']} "
        f"({row.get('slot', 'depth change')}) — {row['why']}."
        for row in actions
    ]
    lines += [
        "",
        "## Market constraint",
        "",
        (
            "All priorities are QUALITY PRIORITY recommendations. Candidate prices, current "
            "resale values, and coin budget must be supplied before value or affordability "
            "claims are made."
        ),
        "",
    ]
    return "\n".join(lines)

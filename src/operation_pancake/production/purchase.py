"""Unified GM purchase intelligence composed from existing production layers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .attributes import AttributeIntelligence
from .gm import GMProduct, optimize_budget
from .market_campaign import REAL_HISTORY, calibrate_decision, history_statistics
from .valuation import percentile_of

TIER_LABELS = ("MARGINAL", "MODEST", "MEANINGFUL", "MAJOR", "TRANSFORMATIVE")


def empirical_upgrade_tier(
    score_gain: float, rank_gain: int, reference: list[dict[str, float]]
) -> dict[str, Any]:
    positive = [row for row in reference if row["score_gain"] > 0 and row["rank_gain"] > 0]
    if score_gain <= 0 or rank_gain <= 0 or not positive:
        return {"tier": "MARGINAL", "magnitude_percentile": 0.0}
    score_percentile = percentile_of(score_gain, [row["score_gain"] for row in positive])
    rank_percentile = percentile_of(float(rank_gain), [row["rank_gain"] for row in positive])
    magnitude = (score_percentile + rank_percentile) / 2
    bucket = min(4, int(max(0, magnitude - 0.000001) // 20))
    return {
        "tier": TIER_LABELS[bucket],
        "magnitude_percentile": round(magnitude, 6),
        "score_gain_reference_percentile": score_percentile,
        "rank_gain_reference_percentile": rank_percentile,
        "reference_opportunities": len(positive),
    }


def detect_decision_change(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any] | None:
    old = previous.get("decision", {}).get("gm_action")
    new = current.get("decision", {}).get("gm_action")
    material = {
        "action": (old, new),
        "market_quality": (
            previous.get("market", {}).get("evidence_quality"),
            current.get("market", {}).get("evidence_quality"),
        ),
        "net_cost": (
            previous.get("cost", {}).get("net_upgrade_cost"),
            current.get("cost", {}).get("net_upgrade_cost"),
        ),
    }
    changed = {key: values for key, values in material.items() if values[0] != values[1]}
    if not changed:
        return None
    return {
        "previous_action": old,
        "new_action": new,
        "what_changed": changed,
        "reason": current.get("decision", {}).get("reason"),
    }


class PurchaseIntelligence:
    def __init__(self, root: Path):
        self.root = root
        self.gm = GMProduct(root)
        self.attributes = AttributeIntelligence(root)
        self.history_path = root / REAL_HISTORY
        self.history = (
            json.loads(self.history_path.read_text(encoding="utf-8"))
            if self.history_path.exists()
            else []
        )
        self.history_by_card: dict[str, list[dict[str, Any]]] = {}
        for row in self.history:
            self.history_by_card.setdefault(row["card_id"], []).append(row)
        self.contextual = self._load_contextual()
        self.valuations = self._load_valuations()
        self.reference = self._upgrade_reference()

    def _load_contextual(self) -> dict[str, dict[str, Any]]:
        path = self.root / "data/research/op_x_027/roster_market_decisions.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["decisions"]
        values = json.loads(
            (self.root / "data/research/op_x_028/current_target_valuations.json").read_text(
                encoding="utf-8"
            )
        )["targets"]
        ids = {row["candidate"]: row["candidate_card_id"] for row in values}
        return {ids[row["candidate"]]: row for row in rows}

    def _load_valuations(self) -> dict[tuple[str, str], dict[str, Any]]:
        path = self.root / "data/research/op_x_028/current_target_valuations.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["targets"]
        return {(row["current_card_id"], row["candidate_card_id"]): row for row in rows}

    def _upgrade_reference(self) -> list[dict[str, float]]:
        path = self.root / "data/production/roster/replacement_candidates.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        reference = []
        for row in rows:
            for candidate in row.get("candidates", {}).values():
                if candidate:
                    reference.append(
                        {
                            "score_gain": float(candidate["score_improvement"]),
                            "rank_gain": float(candidate["position_rank_improvement"]),
                        }
                    )
        return reference

    def _market(self, card_id: str, as_of: str | None = None) -> dict[str, Any]:
        real = self.history_by_card.get(card_id, [])
        if real:
            stats = history_statistics(real, as_of)
            latest = max(real, key=lambda row: row["user_observed_at"])
            return {
                "latest_observation": latest,
                "latest_price": latest["observed_price"],
                "observation_semantics": latest["observation_type"],
                "observation_age_hours": stats["latest_age_hours"],
                "sample_size": stats["observation_count"],
                "evidence_quality": stats["quality"],
                "recent_range": [stats["minimum"], stats["maximum"]],
                "dispersion_ratio": stats["dispersion_ratio"],
                "risk_flags": []
                if stats["quality"] in {"USABLE", "STRONG"}
                else ["INSUFFICIENT LONGITUDINAL MARKET EVIDENCE"],
                "statistics": stats,
            }
        context = self.contextual.get(card_id)
        if context:
            return {
                "latest_observation": {
                    "observed_price": context["public_display_price"],
                    "observation_type": context["price_semantics"],
                    "user_observed_at": None,
                    "source_published_at": None,
                    "evidence_scope": "OP_X_027_CONTEXT_ONLY",
                },
                "latest_price": context["public_display_price"],
                "observation_semantics": context["price_semantics"],
                "observation_age_hours": None,
                "sample_size": 1,
                "evidence_quality": "CONTEXT_ONLY",
                "recent_range": None,
                "dispersion_ratio": None,
                "risk_flags": context["risk"],
                "statistics": {"observation_count": 1, "quality": "INSUFFICIENT"},
            }
        return {
            "latest_observation": None,
            "latest_price": None,
            "observation_semantics": None,
            "observation_age_hours": None,
            "sample_size": 0,
            "evidence_quality": "INSUFFICIENT",
            "recent_range": None,
            "dispersion_ratio": None,
            "risk_flags": ["NO MARKET OBSERVATION"],
            "statistics": {"observation_count": 0, "quality": "INSUFFICIENT"},
        }

    def report(
        self,
        current_id: str,
        candidate_id: str,
        *,
        budget: int | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        if current_id not in self.gm.cards or candidate_id not in self.gm.cards:
            return {
                "status": "UNRESOLVED IDENTITY",
                "decision": {"gm_action": "UNRESOLVED IDENTITY"},
            }
        current = self.gm.rank_by_id.get(current_id)
        candidate = self.gm.rank_by_id.get(candidate_id)
        if current is None or candidate is None:
            return {"status": "UNSUPPORTED MODEL", "decision": {"gm_action": "UNSUPPORTED MODEL"}}
        if current["position_family"] != candidate["position_family"]:
            return {"status": "INCOMPARABLE", "decision": {"gm_action": "KEEP"}}
        value = self.gm.value(current_id, candidate_id)
        decomposition = self.attributes.compare(current_id, candidate_id)
        score_gain = value.get("score_gain", candidate["score"] - current["score"])
        rank_gain = value.get("rank_gain", current["position_rank"] - candidate["position_rank"])
        tier = empirical_upgrade_tier(score_gain, rank_gain, self.reference)
        alternative_cache: dict[str, dict[str, Any]] = {}

        def enrich_alternative(row: dict[str, Any]) -> dict[str, Any]:
            if row["card_id"] in alternative_cache:
                return alternative_cache[row["card_id"]]
            comparison = self.attributes.compare(row["card_id"], candidate_id)
            gains = [
                item
                for item in comparison.get("attributes", [])
                if item["score_contribution_change"] > 0
            ]
            losses = [
                item
                for item in comparison.get("attributes", [])
                if item["score_contribution_change"] < 0
            ]
            enriched = {
                **row,
                "target_attribute_advantages": sorted(
                    gains, key=lambda item: -item["score_contribution_change"]
                )[:3],
                "target_attribute_losses": sorted(
                    losses, key=lambda item: item["score_contribution_change"]
                )[:3],
                "market_evidence": self._market(row["card_id"], as_of),
            }
            alternative_cache[row["card_id"]] = enriched
            return enriched

        alternatives_by_tolerance = {
            str(tolerance): [
                enrich_alternative(row)
                for row in self.attributes.alternatives(candidate_id, tolerance)
            ]
            for tolerance in (0.25, 0.5, 1.0)
        }
        alternatives = alternatives_by_tolerance["1.0"]
        best_alternative = alternatives[0] if alternatives else None
        target_market = self._market(candidate_id, as_of)
        target_premium = None
        if best_alternative:
            alternative_score = candidate["score"] + best_alternative["score_difference"]
            target_premium = {
                "target_score": candidate["score"],
                "alternative_score": alternative_score,
                "score_premium": round(candidate["score"] - alternative_score, 6),
                "rank_premium": best_alternative["rank_difference"],
                "football_relationship": self._premium_label(
                    candidate["score"] - alternative_score
                ),
                "attribute_advantages": best_alternative["target_attribute_advantages"],
                "attribute_losses": best_alternative["target_attribute_losses"],
                "price_premium": (
                    None
                    if target_market["latest_price"] is None
                    or best_alternative["market_evidence"]["latest_price"] is None
                    else target_market["latest_price"]
                    - best_alternative["market_evidence"]["latest_price"]
                ),
            }
        valuation = self.valuations.get((current_id, candidate_id), {})
        market = target_market
        resale_market = self._market(current_id, as_of)
        candidate_price = market["latest_price"]
        resale = resale_market["latest_price"] if resale_market["sample_size"] else None
        net = None if candidate_price is None or resale is None else candidate_price - resale
        intrinsic_class = valuation.get("relative_valuation")
        if score_gain <= 0:
            action, reason = "KEEP", "candidate is not a football upgrade"
        elif tier["tier"] == "MARGINAL":
            action, reason = "WAIT", "football upgrade is marginal in the empirical opportunity set"
        elif market["evidence_quality"] == "CONTEXT_ONLY":
            action, reason = "PRICE CHECK REQUIRED", "only contextual market evidence exists"
        else:
            calibrated = calibrate_decision(
                market["statistics"],
                intrinsic_class or "UNCLASSIFIED",
                gross_cost=candidate_price,
                resale_value=resale,
                budget=budget,
            )
            action, reason = calibrated["decision"], calibrated["reason"]
        spend = net if net is not None and net > 0 else None
        moneyball = {
            "score_gain_per_1000_net_coins": None
            if not spend
            else round(score_gain * 1000 / spend, 8),
            "rank_gain_per_1000_net_coins": None
            if not spend
            else round(rank_gain * 1000 / spend, 8),
            "value_index_per_1000_net_coins": None
            if not spend or not value.get("value_index")
            else round(value["value_index"] * 1000 / spend, 8),
        }
        primary_gains = sorted(
            [
                row
                for row in decomposition.get("attributes", [])
                if row.get("role") == "PRIMARY UPGRADE DRIVER"
            ],
            key=lambda row: -row["score_contribution_change"],
        )
        secondary_gains = sorted(
            [
                row
                for row in decomposition.get("attributes", [])
                if row.get("role") == "SECONDARY GAIN"
            ],
            key=lambda row: -row["score_contribution_change"],
        )
        losses = sorted(
            [
                row
                for row in decomposition.get("attributes", [])
                if row.get("role") == "LOSS/OFFSET"
            ],
            key=lambda row: row["score_contribution_change"],
        )
        return {
            "status": "PURCHASE EVALUATED",
            "current_player": self.gm._identity(self.gm.cards[current_id]),
            "candidate": self.gm._identity(self.gm.cards[candidate_id]),
            "identity_confidence": {"current": "EXACT", "candidate": "EXACT"},
            "football": {
                "current_score": current["score"],
                "candidate_score": candidate["score"],
                "score_gain": score_gain,
                "percentage_gain": value.get("score_gain_percent"),
                "current_position_rank": current["position_rank"],
                "candidate_position_rank": candidate["position_rank"],
                "rank_gain": rank_gain,
                "current_percentile": value.get("current_percentile"),
                "candidate_percentile": value.get("candidate_percentile"),
                "percentile_gain": value.get("percentile_gain"),
                "upgrade_tier": tier,
                "model_confidence": {
                    "current": current["score_confidence"],
                    "candidate": candidate["score_confidence"],
                },
                "attribute_coverage": {
                    "current": current["attribute_coverage"],
                    "candidate": candidate["attribute_coverage"],
                },
            },
            "why": {
                "primary_attribute_drivers": primary_gains[:3],
                "secondary_gains": secondary_gains[:3],
                "negative_tradeoffs": losses[:3],
                "top_three_contribution_share_percent": decomposition.get(
                    "top_three_gain_share_percent"
                ),
                "decomposition_caveat": decomposition.get("decomposition_caveat"),
            },
            "roster": {
                "position_need": value.get("roster_need"),
                "replacement_level_score": value.get("replacement_level_score"),
                "roster_marginal_value": value.get("value_index"),
            },
            "intrinsic_value": {
                "pancake_value_index": value.get("value_index"),
                "relative_valuation_class": intrinsic_class,
            },
            "alternatives": {
                "by_tolerance": alternatives_by_tolerance,
                "best_near_equivalent": best_alternative,
                "target_premium": target_premium,
            },
            "market": market,
            "cost": {
                "candidate_price": candidate_price,
                "current_player_resale_evidence": resale_market,
                "resale_value": resale,
                "net_upgrade_cost": net,
            },
            "moneyball": moneyball,
            "decision": {
                "football_verdict": "UPGRADE" if score_gain > 0 else "KEEP",
                "market_verdict": market["evidence_quality"],
                "gm_action": action,
                "confidence": "LOW"
                if action in {"PRICE CHECK REQUIRED", "INSUFFICIENT MARKET DATA"}
                else "MEDIUM",
                "reason": reason,
                "next_evidence_required": self._next_evidence(
                    market, resale_market, best_alternative
                ),
            },
        }

    @staticmethod
    def _premium_label(score_premium: float) -> str:
        if score_premium <= 0.25:
            return "ESSENTIALLY INTERCHANGEABLE"
        if score_premium <= 0.5:
            return "MARGINALLY SUPERIOR"
        if score_premium <= 1:
            return "MEANINGFULLY SUPERIOR"
        return "CLEARLY SUPERIOR"

    @staticmethod
    def _next_evidence(
        market: dict[str, Any], resale: dict[str, Any], alternative: dict | None
    ) -> list[str]:
        requests = []
        if market["evidence_quality"] not in {"USABLE", "STRONG"}:
            requests.append("new timestamped target observation with explicit semantics")
        if resale["sample_size"] == 0:
            requests.append("current-player resale listing or completed sale")
        if alternative:
            requests.append(f"market observation for alternative {alternative['player_name']}")
        return requests

    def render(self, report: dict[str, Any]) -> str:
        if report.get("status") != "PURCHASE EVALUATED":
            return f"PANCAKE GM - PURCHASE REPORT\n\nDECISION: {report['decision']['gm_action']}\n"
        football, why, alternative = report["football"], report["why"], report["alternatives"]
        drivers = ", ".join(row["attribute"] for row in why["primary_attribute_drivers"]) or "none"
        losses = ", ".join(row["attribute"] for row in why["negative_tradeoffs"]) or "none"
        best = alternative["best_near_equivalent"]
        return (
            "PANCAKE GM - PURCHASE REPORT\n\n"
            f"CURRENT: {report['current_player']['player_name']}\n"
            f"TARGET: {report['candidate']['player_name']}\n\n"
            f"FOOTBALL: +{football['score_gain']:.6f} Pancake, +{football['rank_gain']} ranks, "
            f"+{football['percentile_gain']:.6f} percentile; {football['upgrade_tier']['tier']}\n"
            f"WHY: {drivers}; offsets: {losses}\n"
            f"ALTERNATIVE: {best['player_name'] if best else 'none within 1.0'}"
            f" ({best['score_difference']:+.6f} score)\n"
            if best
            else "ALTERNATIVE: none within 1.0\n"
        ) + (
            f"VALUE: {report['intrinsic_value']['relative_valuation_class'] or 'UNCLASSIFIED'}; "
            f"market {report['market']['evidence_quality']}\n"
            f"COST: gross {report['cost']['candidate_price']}; "
            f"net {report['cost']['net_upgrade_cost']}\n"
            f"DECISION: {report['decision']['gm_action']} - {report['decision']['reason']}\n"
            f"NEXT: {'; '.join(report['decision']['next_evidence_required']) or 'none'}\n"
        )

    def shopping_board(self) -> list[dict[str, Any]]:
        replacements = json.loads(
            (self.root / "data/production/roster/replacement_candidates.json").read_text(
                encoding="utf-8"
            )
        )
        board = []
        for row in replacements:
            best = row.get("candidates", {}).get("best_overall")
            if not best:
                continue
            current = next(
                (
                    item
                    for item in self.gm.ranked
                    if item["player_name"] == row["current"]
                    and item["position_rank"] == row["current_rank"]
                ),
                None,
            )
            if not current:
                continue
            report = self.report(current["card_id"], best["card_id"])
            board.append(
                {
                    "current": row["current"],
                    "target": best["player_name"],
                    "football_tier": report["football"]["upgrade_tier"]["tier"],
                    "pancake_gain": report["football"]["score_gain"],
                    "intrinsic_class": report["intrinsic_value"]["relative_valuation_class"],
                    "best_alternative": report["alternatives"]["best_near_equivalent"],
                    "target_premium": report["alternatives"]["target_premium"],
                    "market_evidence_quality": report["market"]["evidence_quality"],
                    "net_cost": report["cost"]["net_upgrade_cost"],
                    "gm_action": report["decision"]["gm_action"],
                    "priority_score": round(
                        report["football"]["upgrade_tier"]["magnitude_percentile"], 6
                    ),
                }
            )
        return sorted(
            board, key=lambda row: (-row["priority_score"], -row["pancake_gain"], row["current"])
        )

    def optimize_reports(self, reports: list[dict[str, Any]], budget: int) -> dict[str, Any]:
        candidates = []
        rejected = []
        for report in reports:
            cost = report["cost"]["net_upgrade_cost"]
            if cost is None:
                cost = report["cost"]["candidate_price"]
            if cost is None:
                rejected.append(
                    {
                        "candidate": report["candidate"]["player_name"],
                        "reason": "PRICE CHECK REQUIRED",
                    }
                )
                continue
            candidates.append(
                {
                    "card_id": report["candidate"]["card_id"],
                    "player_name": report["candidate"]["player_name"],
                    "net_cost": cost,
                    "score_improvement": report["football"]["score_gain"],
                    "rank_gain": report["football"]["rank_gain"],
                    "value_index": report["intrinsic_value"]["pancake_value_index"],
                    "market_quality": report["market"]["evidence_quality"],
                }
            )
        result = optimize_budget(candidates, budget)
        result["rank_gain"] = sum(row["rank_gain"] for row in result["selected"])
        result["intrinsic_value"] = round(
            sum(row.get("value_index") or 0 for row in result["selected"]), 6
        )
        result["rejected"] = rejected
        result["keep_coins"] = not result["selected"]
        return result

    def evidence_priority(
        self, reports: list[dict[str, Any]], limit: int = 2
    ) -> list[dict[str, Any]]:
        class_priority = {"STRONG VALUE": 3, "VALUE": 2, "FAIR": 1}
        rows = []
        for report in reports:
            if report["market"]["evidence_quality"] in {"USABLE", "STRONG"}:
                continue
            score = (
                class_priority.get(report["intrinsic_value"]["relative_valuation_class"], 0) * 100
            )
            score += report["football"]["upgrade_tier"]["magnitude_percentile"]
            rows.append(
                {
                    "candidate": report["candidate"]["player_name"],
                    "candidate_card_id": report["candidate"]["card_id"],
                    "priority_score": round(score, 6),
                    "request": report["decision"]["next_evidence_required"],
                }
            )
        return sorted(rows, key=lambda row: (-row["priority_score"], row["candidate"]))[:limit]

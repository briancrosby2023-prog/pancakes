"""Unified Operation Pancake GM product surface.

This module composes frozen production scoring, roster, and market services.
Research artifacts never alter production model routing here.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .engine import ProductionEngine, load_population
from .market import MoneyballEngine, normalize_observation, resolve_observations
from .registry import build_model_registry
from .roster import normalize_name
from .valuation import population_value_curves, price_sensitivity, upgrade_value

ACTIONS = {
    "KEEP",
    "START",
    "BENCH",
    "UPGRADE",
    "BUY",
    "WAIT",
    "SELL/REPLACE",
    "BUDGET UPGRADE",
    "PREMIUM UPGRADE",
    "PRICE CHECK REQUIRED",
    "INSUFFICIENT ATTRIBUTES",
    "UNRESOLVED IDENTITY",
    "UNSUPPORTED MODEL",
    "INSUFFICIENT MARKET DATA",
}


def _confidence(
    card: dict[str, Any] | None, score: dict[str, Any] | None, market: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "identity": "EXACT" if card else "UNRESOLVED",
        "attributes": None if not score else score.get("attribute_coverage"),
        "model": None if not score else score.get("score_confidence"),
        "ranking": "AVAILABLE" if score and score.get("position_rank") else "UNAVAILABLE",
        "market": "NO CURRENT PRICE" if not market else market.get("market_confidence", "OBSERVED"),
        "moneyball": "UNAVAILABLE" if not market else market.get("value_classification"),
    }


class GMProduct:
    """One high-level interface for lookup, evaluation, comparison and value decisions."""

    def __init__(self, root: Path):
        self.root = root
        self.population = load_population(root)
        self.engine = ProductionEngine(build_model_registry(root))
        self.ranked = self.engine.rank([self.engine.score(card) for card in self.population])
        self.rank_by_id = {row["card_id"]: row for row in self.ranked}
        self.cards = {row["card_id"]: row for row in self.population}
        self.value_curves = population_value_curves(self.ranked)

    def lookup(
        self,
        *,
        card_id: str | None = None,
        player_name: str | None = None,
        position: str | None = None,
        overall: int | None = None,
        program: str | None = None,
    ) -> dict[str, Any]:
        if card_id:
            matches = [self.cards[card_id]] if card_id in self.cards else []
        else:
            matches = [
                row
                for row in self.population
                if player_name
                and normalize_name(row.get("player_name") or "") == normalize_name(player_name)
            ]
            if position:
                matches = [row for row in matches if row["position"] == position]
            if overall is not None:
                matches = [row for row in matches if row.get("native_overall") == overall]
            if program:
                matches = [row for row in matches if row.get("program") == program]
        if not matches:
            return {"status": "UNRESOLVED IDENTITY", "matches": []}
        if len(matches) > 1:
            return {
                "status": "AMBIGUOUS CARD VERSION",
                "matches": [self._identity(x) for x in matches],
            }
        card = matches[0]
        score = self.engine.score(card)
        rank = self.rank_by_id.get(card["card_id"])
        if rank:
            score = {
                **score,
                "position_rank": rank["position_rank"],
                "archetype_rank": rank["archetype_rank"],
            }
        return {
            "status": score["score_status"],
            "card": self._identity(card),
            "evaluation": score,
            "confidence": _confidence(card, score),
            "limitations": score.get("model_limitations", [])
            + ([] if score.get("score") is not None else [score["score_status"]]),
        }

    @staticmethod
    def _identity(card: dict[str, Any]) -> dict[str, Any]:
        return {
            key: card.get(key)
            for key in (
                "card_id",
                "player_name",
                "position",
                "native_overall",
                "program",
                "archetype",
            )
        }

    def compare(
        self,
        current_id: str,
        candidate_id: str,
        candidate_price: int | None = None,
        current_resale: int | None = None,
        as_of: str = "2026-08-20T00:00:00-07:00",
    ) -> dict[str, Any]:
        if current_id not in self.cards or candidate_id not in self.cards:
            return {"status": "UNRESOLVED IDENTITY"}
        comparison = self.engine.compare(
            self.cards[current_id], self.cards[candidate_id], candidate_price
        )
        football = comparison.get("classification", "INCOMPARABLE")
        market = {"status": "PRICE CHECK REQUIRED"}
        if candidate_price is not None and comparison.get("score_delta") is not None:
            observation = normalize_observation(
                {
                    "canonical_card_id": candidate_id,
                    "observed_price": candidate_price,
                    "currency": "CUT_COINS",
                    "source": "USER_SUPPLIED",
                    "observed_at": as_of,
                    "observation_type": "USER_SUPPLIED_OBSERVATION",
                    "provenance": "GMProduct.compare",
                },
                "GMProduct.compare",
            )
            left_rank = self.rank_by_id.get(current_id, {}).get("position_rank", 0)
            right_rank = self.rank_by_id.get(candidate_id, {}).get("position_rank", 0)
            market = MoneyballEngine().evaluate(
                comparison["score_delta"],
                comparison.get("score_delta_percent") or 0,
                left_rank - right_rank,
                observation,
                as_of,
                current_resale,
            )
        return {
            "status": "OK",
            "football_verdict": football,
            "market_verdict": market["status"],
            "comparison": comparison,
            "market": market,
            "confidence": _confidence(
                self.cards[candidate_id], comparison.get("candidate"), market
            ),
        }

    def value(self, current_id: str, candidate_id: str) -> dict[str, Any]:
        """Return price-independent intrinsic upgrade value and its hypothetical cost curve."""
        if current_id not in self.cards or candidate_id not in self.cards:
            return {"status": "UNRESOLVED IDENTITY"}
        current = self.rank_by_id.get(current_id)
        candidate = self.rank_by_id.get(candidate_id)
        if current is None or candidate is None:
            return {"status": "UNSUPPORTED MODEL", "value_index": None}
        value = upgrade_value(current, candidate, self.ranked, self.value_curves)
        return {**value, "price_sensitivity": price_sensitivity(value)}


def optimize_budget(candidates: list[dict[str, Any]], budget: int) -> dict[str, Any]:
    """Exact 0/1 budget optimizer for independent upgrade candidates."""
    eligible = [
        c
        for c in candidates
        if c.get("net_cost") is not None
        and c["net_cost"] >= 0
        and c.get("score_improvement", 0) > 0
        and not c.get("protected", False)
    ]
    states: dict[int, tuple[float, list[dict[str, Any]]]] = {0: (0.0, [])}
    for candidate in eligible:
        cost = int(candidate["net_cost"])
        gain = float(candidate["score_improvement"])
        for spent, (value, chosen) in sorted(list(states.items()), reverse=True):
            new_cost = spent + cost
            if new_cost > budget:
                continue
            proposal = (value + gain, chosen + [candidate])
            if new_cost not in states or proposal[0] > states[new_cost][0]:
                states[new_cost] = proposal
    spent, (gain, chosen) = max(states.items(), key=lambda item: (item[1][0], -item[0]))
    return {
        "status": "BUDGET_EVALUATED",
        "budget": budget,
        "spent": spent,
        "remaining": budget - spent,
        "score_improvement": round(gain, 6),
        "action": "KEEP" if not chosen else ("BUDGET UPGRADE" if len(chosen) > 1 else "UPGRADE"),
        "selected": chosen,
    }


def price_check_list(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in recommendations:
        if row.get("candidate_price") is not None:
            continue
        output.append(
            {
                key: row.get(key)
                for key in (
                    "card_id",
                    "player_name",
                    "position",
                    "native_overall",
                    "program",
                    "archetype",
                )
            }
            | {"reason": row.get("reason") or "current price required for market verdict"}
        )
    return output


def manual_price_payload(
    rows: list[dict[str, Any]],
    observed_at: str,
    population: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    accepted, rejected = [], []
    for index, row in enumerate(rows):
        payload = {
            **row,
            "observed_at": row.get("observed_at") or observed_at,
            "source": row.get("source") or "USER_SUPPLIED",
            "currency": "CUT_COINS",
            "provenance": row.get("provenance") or "manual GM entry",
        }
        try:
            observation = normalize_observation(payload, f"manual#{index}")
            observation_payload = asdict(observation)
            if population is not None:
                resolution = resolve_observations([observation], population)[0]
                if resolution["classification"] not in {"EXACT", "HIGH CONFIDENCE"}:
                    raise ValueError(
                        "manual price identity must resolve exactly or uniquely; "
                        f"got {resolution['classification']}"
                    )
                observation_payload["card_id"] = resolution["canonical_card_id"]
            accepted.append(observation_payload)
        except (TypeError, ValueError, KeyError) as error:
            rejected.append({"row_index": index, "reason": str(error), "row": row})
    return {"accepted": accepted, "rejected": rejected}

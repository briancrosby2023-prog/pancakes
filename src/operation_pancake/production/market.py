"""Canonical market ingestion, risk, and Moneyball production services."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .engine import ProductionEngine, load_population
from .registry import build_model_registry
from .roster import normalize_name

REAL_MARKET_SOURCE = "data/research/cfb27_op_x_003/market_observations.json"
QUICKSELL_SOURCE = "src/operation_pancake/research/cfb27_op_x_012.py"
CORE_TRAINING_QUICKSELL = {
    64: 1,
    65: 1,
    66: 2,
    67: 3,
    68: 4,
    69: 5,
    70: 6,
    71: 9,
    72: 13,
    73: 19,
    74: 28,
    75: 41,
    76: 59,
    77: 86,
    78: 124,
    79: 180,
    80: 260,
    81: 380,
    82: 550,
    83: 800,
    84: 1160,
    85: 1680,
    86: 2400,
    87: 3500,
    88: 5100,
}
PLATINUM_COIN_QUICKSELL = {
    75: 2600,
    76: 4100,
    77: 6750,
    78: 12000,
    79: 20000,
    80: 34000,
    81: 60000,
    82: 100000,
    83: 210000,
    84: 350000,
    85: 510000,
}


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    return parsed


@dataclass(frozen=True, slots=True)
class CanonicalMarketObservation:
    observation_id: str
    external_card_id: str | None
    card_id: str | None
    player_name: str | None
    position: str | None
    overall: int | None
    program: str | None
    observed_price: int
    currency: str
    source: str
    source_url: str | None
    observed_at: str
    observation_type: str
    platform: str
    sample_count: int
    low: int | None
    median: int | None
    high: int | None
    liquidity_proxy: float | None
    confidence: str
    provenance: str

    def __post_init__(self) -> None:
        if not self.observation_id or not self.source or not self.provenance:
            raise ValueError("observation ID, source, and provenance are required")
        if self.observed_price <= 0:
            raise ValueError("observed price must be a positive integer")
        if self.currency != "CUT_COINS":
            raise ValueError("only CUT_COINS observations are supported")
        if self.sample_count < 1:
            raise ValueError("sample_count must be at least one")
        parse_timestamp(self.observed_at)
        values = [value for value in (self.low, self.median, self.high) if value is not None]
        if any(value <= 0 for value in values):
            raise ValueError("low, median, and high must be positive when supplied")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError("low cannot exceed high")


def _stable_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "market:" + hashlib.sha256(encoded).hexdigest()[:20]


def normalize_observation(row: dict[str, Any], provenance: str) -> CanonicalMarketObservation:
    raw_price = row.get("observed_price", row.get("price", row.get("median")))
    try:
        price = float(raw_price)
    except (TypeError, ValueError) as error:
        raise ValueError("price must be a positive whole number") from error
    if isinstance(raw_price, bool) or int(price) != price:
        raise ValueError("price must be a positive whole number")
    source = str(row.get("source") or "USER_SUPPLIED")
    observed_at = str(row.get("observed_at") or "")
    observation_type = str(row.get("observation_type") or "USER_SUPPLIED_OBSERVATION")
    identity = {
        "external_card_id": row.get(
            "external_card_id", row.get("source_card_id", row.get("card_id"))
        ),
        "card_id": row.get("canonical_card_id"),
        "player_name": row.get("player_name", row.get("player")),
        "position": row.get("position"),
        "overall": int(row["overall"]) if row.get("overall") not in (None, "") else None,
        "program": row.get("program"),
        "observed_price": int(price),
        "currency": str(row.get("currency") or "CUT_COINS").replace("coins", "CUT_COINS"),
        "source": source,
        "source_url": row.get("source_url"),
        "observed_at": observed_at,
        "observation_type": observation_type,
        "platform": str(row.get("platform") or "UNSPECIFIED"),
        "sample_count": int(row.get("sample_count") or row.get("listing_count") or 1),
        "low": int(row["low"]) if row.get("low") not in (None, "") else None,
        "median": int(row["median"]) if row.get("median") not in (None, "") else None,
        "high": int(row["high"]) if row.get("high") not in (None, "") else None,
        "liquidity_proxy": float(row["liquidity_proxy"])
        if row.get("liquidity_proxy") not in (None, "")
        else None,
        "confidence": str(row.get("confidence") or "OBSERVED"),
        "provenance": str(row.get("provenance") or provenance),
    }
    identity["observation_id"] = str(row.get("observation_id") or _stable_id(identity))
    return CanonicalMarketObservation(**identity)


def ingest_market_file(path: Path) -> tuple[list[CanonicalMarketObservation], list[dict[str, Any]]]:
    if path.suffix.casefold() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("observations", [])
    elif path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raise ValueError("market ingestion supports only JSON and CSV")
    accepted, rejected = [], []
    for index, row in enumerate(rows):
        try:
            accepted.append(normalize_observation(row, f"{path.as_posix()}#{index}"))
        except (KeyError, TypeError, ValueError) as error:
            rejected.append({"row_index": index, "reason": str(error), "row": row})
    return deduplicate(accepted), rejected


def deduplicate(
    observations: Iterable[CanonicalMarketObservation],
) -> list[CanonicalMarketObservation]:
    unique: dict[tuple[Any, ...], CanonicalMarketObservation] = {}
    for row in observations:
        key = (
            row.card_id,
            row.external_card_id,
            row.observed_at,
            row.source,
            row.observation_type,
            row.platform,
            row.observed_price,
        )
        unique.setdefault(key, row)
    return sorted(unique.values(), key=lambda row: (row.observed_at, row.observation_id))


def resolve_observations(
    observations: list[CanonicalMarketObservation], population: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {row["card_id"]: row for row in population}
    by_external = {str(row.get("source_card_id")): row for row in population}
    results = []
    for observation in observations:
        selected, method = None, None
        if observation.card_id and observation.card_id in by_id:
            selected, method = by_id[observation.card_id], "canonical card ID"
        elif observation.external_card_id and observation.external_card_id in by_external:
            selected, method = by_external[observation.external_card_id], "exact source card ID"
        if selected:
            classification = "EXACT"
            candidates = [selected]
        else:
            candidates = [
                row
                for row in population
                if observation.player_name
                and normalize_name(row["player_name"]) == normalize_name(observation.player_name)
                and (not observation.position or row["position"] == observation.position)
                and (observation.overall is None or row["native_overall"] == observation.overall)
                and (not observation.program or row.get("program") == observation.program)
            ]
            if len(candidates) == 1:
                selected, classification, method = (
                    candidates[0],
                    "HIGH CONFIDENCE",
                    "unique full identity signature",
                )
            elif candidates:
                classification, method = "AMBIGUOUS", "multiple identity matches"
            else:
                classification, method = "UNRESOLVED", "no defensible identity match"
        results.append(
            {
                "observation": asdict(observation),
                "classification": classification,
                "canonical_card_id": selected["card_id"] if selected else None,
                "match_method": method,
                "candidate_card_ids": [row["card_id"] for row in candidates],
            }
        )
    return results


def risk_flags(
    observation: CanonicalMarketObservation,
    as_of: str,
    stale_hours: float = 24,
    high_spread_ratio: float = 0.25,
    is_ltd: bool = False,
) -> list[str]:
    flags = []
    age = (parse_timestamp(as_of) - parse_timestamp(observation.observed_at)).total_seconds() / 3600
    if age > stale_hours:
        flags.append("STALE PRICE")
    if observation.sample_count == 1:
        flags.append("SINGLE OBSERVATION")
    if observation.liquidity_proxy is not None and observation.liquidity_proxy <= 1:
        flags.append("LOW LIQUIDITY")
    if observation.low and observation.high:
        midpoint = observation.median or observation.observed_price
        if (observation.high - observation.low) / midpoint >= high_spread_ratio:
            flags.append("HIGH SPREAD")
    if is_ltd:
        flags.append("LTD")
    if observation.sample_count < 2 or age > stale_hours:
        flags.append("INSUFFICIENT DATA")
    return flags


class MoneyballEngine:
    def evaluate(
        self,
        score_improvement: float,
        score_improvement_percent: float,
        position_rank_improvement: int,
        observation: CanonicalMarketObservation | None,
        as_of: str,
        current_resale_value: int | None = None,
        coin_budget: int | None = None,
        classification_thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        if observation is None:
            return {
                "status": "PRICE CHECK REQUIRED",
                "value_classification": "INSUFFICIENT MARKET DATA",
                "candidate_price": None,
            }
        price = observation.median or observation.observed_price
        net = price - current_resale_value if current_resale_value is not None else None
        spend_basis = net if net is not None and net > 0 else price
        flags = risk_flags(observation, as_of)
        value_rate = score_improvement * 1000 / spend_basis
        rank_rate = position_rank_improvement * 1000 / spend_basis
        classification = "INSUFFICIENT MARKET DATA"
        if classification_thresholds and "INSUFFICIENT DATA" not in flags:
            if value_rate >= classification_thresholds["elite"]:
                classification = "ELITE VALUE"
            elif value_rate >= classification_thresholds["good"]:
                classification = "GOOD VALUE"
            elif value_rate >= classification_thresholds["fair"]:
                classification = "FAIR VALUE"
            else:
                classification = "POOR VALUE"
        return {
            "status": "PRICE CHECK REQUIRED" if flags else "VALUE EVALUATED",
            "candidate_price": price,
            "current_player_resale_value": current_resale_value,
            "net_upgrade_cost": net,
            "score_improvement": score_improvement,
            "score_improvement_percent": score_improvement_percent,
            "position_rank_improvement": position_rank_improvement,
            "improvement_per_1000_coins": round(value_rate, 8),
            "rank_improvement_per_1000_coins": round(rank_rate, 8),
            "affordable": None if coin_budget is None else spend_basis <= coin_budget,
            "value_classification": classification,
            "market_confidence": "LOW" if flags else observation.confidence,
            "risk_flags": flags,
            "price_semantics": observation.observation_type,
        }


def training_economics(
    price: int | None, overall: int, program: str, training_value: int | None = None
) -> dict[str, Any]:
    is_platinum = "Platinum" in program
    floor = PLATINUM_COIN_QUICKSELL.get(overall) if is_platinum else None
    training = (
        training_value
        if training_value is not None
        else (None if is_platinum else CORE_TRAINING_QUICKSELL.get(overall))
    )
    return {
        "overall": overall,
        "program": program,
        "training_value": training,
        "coin_quicksell_floor": floor,
        "coins_per_training": None if price is None or not training else round(price / training, 6),
        "effective_downside": None if price is None or floor is None else max(0, price - floor),
        "source": QUICKSELL_SOURCE,
        "status": "SUPPORTED_CURRENT_TABLE"
        if training is not None or floor is not None
        else "UNSUPPORTED",
    }


def analyze_ltd(
    acquisition_price: int | None,
    current_price: int | None,
    quicksell_floor: int | None,
    observed_at: str | None,
    release_date: str | None,
) -> dict[str, Any]:
    return {
        "acquisition_price": acquisition_price,
        "current_price": current_price,
        "quicksell_floor": quicksell_floor,
        "observed_at": observed_at,
        "release_date": release_date,
        "downside_to_floor": None
        if current_price is None or quicksell_floor is None
        else current_price - quicksell_floor,
        "unrealized_change": None
        if acquisition_price is None or current_price is None
        else current_price - acquisition_price,
        "depreciation_prediction": None,
        "status": "SUPPORTED_FIELDS_ONLY",
        "limitations": ["no predictive depreciation without longitudinal completed-sale evidence"],
    }


def build_market_outputs(
    root: Path,
    output_dir: Path | None = None,
    as_of: str = "2026-08-20T00:00:00-07:00",
    input_files: list[Path] | None = None,
) -> dict[str, Any]:
    output_dir = output_dir or root / "data/production/market"
    output_dir.mkdir(parents=True, exist_ok=True)
    observations, rejected = ingest_market_file(root / REAL_MARKET_SOURCE)
    supplied_sources = []
    for path in input_files or []:
        supplied, supplied_rejected = ingest_market_file(path.resolve())
        observations.extend(supplied)
        rejected.extend({**row, "input_file": str(path)} for row in supplied_rejected)
        supplied_sources.append(str(path.resolve()))
    observations = deduplicate(observations)
    population = load_population(root)
    resolution = resolve_observations(observations, population)
    exact = [row for row in resolution if row["classification"] == "EXACT"]
    history = [{**row["observation"], "card_id": row["canonical_card_id"]} for row in exact]
    cards = {card["card_id"]: card for card in population}
    registry = build_model_registry(root)
    player_engine = ProductionEngine(registry)
    ranked = player_engine.rank([player_engine.score(card) for card in population])
    rank_by_id = {row["card_id"]: row for row in ranked}
    market_scores = []
    for row in exact:
        card_id = row["canonical_card_id"]
        observation = CanonicalMarketObservation(**row["observation"])
        score = rank_by_id.get(card_id)
        market_scores.append(
            {
                "card_id": card_id,
                "player_name": cards[card_id]["player_name"],
                "position_family": score["position_family"] if score else None,
                "pancake_score": score["score"] if score else None,
                "position_rank": score["position_rank"] if score else None,
                "observed_price": observation.observed_price,
                "observation_type": observation.observation_type,
                "risk_flags": risk_flags(observation, as_of),
                "training_economics": training_economics(
                    observation.observed_price,
                    cards[card_id]["native_overall"],
                    cards[card_id]["program"],
                ),
            }
        )
    for row in market_scores:
        comparable = [
            item for item in market_scores if item["position_family"] == row["position_family"]
        ]
        if len(comparable) < 2 or row["pancake_score"] is None:
            row["relative_market_value"] = None
            row["relative_value_reason"] = "fewer than two priced cards in position family"
            continue
        ratios = sorted(
            item["pancake_score"] / item["observed_price"]
            for item in comparable
            if item["pancake_score"] is not None
        )
        ratio = row["pancake_score"] / row["observed_price"]
        row["relative_market_value"] = {
            "score_per_1000_coins": round(ratio * 1000, 8),
            "within_observed_family_percentile": round(
                100 * sum(value <= ratio for value in ratios) / len(ratios), 4
            ),
            "comparison_count": len(ratios),
        }
        row["relative_value_reason"] = "descriptive within sparse stale observed family only"
    roster_replacements = json.loads(
        (root / "data/production/roster/replacement_candidates.json").read_text(encoding="utf-8")
    )
    observation_by_card = {
        row["canonical_card_id"]: CanonicalMarketObservation(**row["observation"]) for row in exact
    }
    moneyball = MoneyballEngine()
    roster_value = []
    for replacement in roster_replacements:
        if replacement["status"] != "UPGRADE_AVAILABLE":
            continue
        candidates = {}
        for tier, candidate in replacement["candidates"].items():
            if not candidate:
                candidates[tier] = {"status": "PRICE CHECK REQUIRED"}
                continue
            candidates[tier] = {
                "candidate": candidate,
                "value": moneyball.evaluate(
                    candidate["score_improvement"],
                    candidate["score_improvement_percent"],
                    candidate["position_rank_improvement"],
                    observation_by_card.get(candidate["card_id"]),
                    as_of,
                ),
            }
        roster_value.append(
            {
                "current": replacement["current"],
                "position_family": replacement["position_family"],
                "candidates": candidates,
            }
        )
    priority_names = {
        "Anthony Donkoh",
        "Samson Okunlola",
        "Dashawn Spears",
        "Chris Cole",
        "Cormani McClain",
    }
    priority_value = [row for row in roster_value if row["current"] in priority_names]
    priority_families = {row["position_family"] for row in priority_value}
    weak_position_tiers = []
    for family in sorted(priority_families):
        priced = [row for row in market_scores if row["position_family"] == family]
        best = max(priced, key=lambda row: row["pancake_score"], default=None)
        weak_position_tiers.append(
            {
                "position_family": family,
                "BEST PLAYER": best or {"status": "PRICE CHECK REQUIRED"},
                "BEST VALUE": (
                    max(
                        priced,
                        key=lambda row: row["pancake_score"] / row["observed_price"],
                    )
                    if len(priced) >= 2
                    else {"status": "INSUFFICIENT MARKET DATA"}
                ),
                "BUDGET UPGRADE": {
                    "status": "PRICE CHECK REQUIRED",
                    "reason": "no budget supplied",
                },
                "PREMIUM UPGRADE": (
                    max(priced, key=lambda row: row["observed_price"])
                    if len(priced) >= 2
                    else {"status": "INSUFFICIENT MARKET DATA"}
                ),
            }
        )
    audit = {
        "as_of": as_of,
        "sources": {
            "CFB_FAN_PUBLIC": {
                "status": (
                    "PUBLIC_CLIENT_RENDERED_LIVE_DASHBOARD; AUTOMATED PAYLOAD NOT ESTABLISHED"
                ),
                "url": "https://cfb.fan/prices/",
                "semantics": (
                    "dashboard advertises real-time market; repository observations are public "
                    "display prices, not completed sales"
                ),
            },
            "REPOSITORY_SNAPSHOT": {
                "status": "INGESTED_REAL_STALE_OBSERVATIONS",
                "path": REAL_MARKET_SOURCE,
            },
            "USER_SUPPLIED": {"status": "PRODUCTION JSON/CSV INGESTION READY"},
        },
        "live_acquisition_blocker": (
            "public dashboard content is client-rendered; no repository-established structured "
            "API or reproducible payload contract"
        ),
        "prohibited_actions_not_attempted": [
            "authentication bypass",
            "anti-bot evasion",
            "invented API",
            "fabricated price",
        ],
        "supplied_input_files": supplied_sources,
    }
    ltd_state = {
        "status": "PARTIAL_SUPPORTED_INTERFACE",
        "inventory_source": "data/research/cfb27_op_x_012/ltd_inventory_v3.json",
        "analysis_example_without_invented_values": analyze_ltd(None, None, None, None, None),
    }
    schema = {
        "schema_version": "1.0",
        "required": [
            "observed_price",
            "currency",
            "source",
            "observed_at",
            "observation_type",
            "provenance",
        ],
        "identity_priority": [
            "canonical card_id",
            "external_card_id",
            "player+position+overall+program",
        ],
        "formats": {
            field: str(annotation)
            for field, annotation in CanonicalMarketObservation.__annotations__.items()
        },
    }
    summary = {
        "as_of": as_of,
        "observations_ingested": len(observations),
        "observations_rejected": len(rejected),
        "unique_cards": len({row["canonical_card_id"] for row in exact}),
        "resolution_counts": {
            status: sum(row["classification"] == status for row in resolution)
            for status in ("EXACT", "HIGH CONFIDENCE", "AMBIGUOUS", "UNRESOLVED")
        },
        "fresh_observations": sum(
            "STALE PRICE" not in risk_flags(row, as_of) for row in observations
        ),
        "stale_observations": sum("STALE PRICE" in risk_flags(row, as_of) for row in observations),
        "roster_priority_prices": sum(
            1
            for row in priority_value
            for value in row["candidates"].values()
            if value.get("value", {}).get("candidate_price") is not None
        ),
        "purchase_recommendations": 0,
    }
    roster_followup = {
        "opportunistic_recovery": "NO_NEW_DEFENSIBLE_RESOLUTIONS",
        "identity_targets": {
            row["player_name"]: row["identity_confidence"]
            for row in json.loads(
                (root / "data/production/roster/canonical_roster.json").read_text(encoding="utf-8")
            )
            if row["player_name"]
            in {
                "Peter Clarke",
                "Jidah Baugh",
                "Owen Allen",
                "Kalik Lockett",
                "Javon Nicholas",
                "King Mack",
            }
        },
        "dante_moore_vector": "INSUFFICIENT_ATTRIBUTES_IN_MATCHED_CURRENT_CARD",
        "next_evidence": "card detail screen with native program/OVR and full ratings",
    }
    outputs = {
        "market_source_audit.json": audit,
        "market_observation_schema.json": schema,
        "canonical_observations.json": [asdict(row) for row in observations],
        "rejected_observations.json": rejected,
        "price_card_resolution.json": resolution,
        "price_history.json": history,
        "market_score_join.json": market_scores,
        "market_risk.json": [
            {"card_id": row["card_id"], "risk_flags": row["risk_flags"]} for row in market_scores
        ],
        "training_economics.json": [
            {"card_id": row["card_id"], **row["training_economics"]} for row in market_scores
        ],
        "roster_moneyball.json": roster_value,
        "priority_upgrade_value.json": priority_value,
        "weak_position_value_tiers.json": weak_position_tiers,
        "ltd_state.json": ltd_state,
        "run_summary.json": summary,
        "quicksell_tables.json": {
            "core_training": CORE_TRAINING_QUICKSELL,
            "platinum_coin": PLATINUM_COIN_QUICKSELL,
            "source": QUICKSELL_SOURCE,
        },
        "roster_identity_followup.json": roster_followup,
    }
    for name, payload in outputs.items():
        (output_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    (output_dir / "manual_observation_template.csv").write_text(
        "external_card_id,player_name,position,overall,program,observed_price,currency,source,source_url,observed_at,observation_type,platform,sample_count,low,median,high,liquidity_proxy,confidence,provenance\n",
        encoding="utf-8",
    )
    (output_dir / "market_audit.md").write_text(
        "# OP-X-023 Market Source Audit\n\n"
        f"As of: {as_of}\n\n"
        f"Real repository observations ingested: {len(observations)}. "
        f"Fresh: {summary['fresh_observations']}; stale: {summary['stale_observations']}.\n\n"
        "CFB.FAN publicly exposes a CFB27 real-time price dashboard, but the payload is "
        "client-rendered and no structured contract is established in the repository. "
        "No authentication bypass, anti-bot evasion, invented API, or fabricated price was "
        "used.\n\n"
        "The eight repository observations are public display prices, not completed sales. "
        "They are retained as timestamped stale evidence and are not sufficient for purchase "
        "calls.\n",
        encoding="utf-8",
    )
    update_completion_matrix(root, summary)
    return summary


def update_completion_matrix(root: Path, summary: dict[str, Any]) -> None:
    path = root / "data/production/product_completion_matrix.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    updates = {
        "VALUE/MONEYBALL": (
            "PARTIAL",
            "production calculations executed; all current prices stale",
        ),
        "MARKET INGESTION": (
            "PARTIAL",
            (
                f"{summary['observations_ingested']} real observations ingested; "
                "no live structured acquisition"
            ),
        ),
        "PRICE HISTORY": (
            "PARTIAL",
            f"{summary['observations_ingested']} timestamped observations persisted",
        ),
        "LTD ENGINE": (
            "PARTIAL",
            "supported downside/current-state interface; prediction withheld",
        ),
        "MARKET RISK": (
            "PARTIAL",
            "staleness, sample, liquidity, spread, LTD, and insufficient-data flags implemented",
        ),
    }
    for key, (status, evidence) in updates.items():
        matrix[key]["status"] = status
        matrix[key]["evidence"] = evidence
        matrix[key]["executable_entry_point"] = "operation-pancake market-run"
        matrix[key]["tests"] = "OP-X-023 targeted market production tests"
    path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

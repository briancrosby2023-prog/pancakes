"""OP-X-003 cross-year source, economy, release, and market intelligence."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from operation_pancake.research.cfb27_op_x_001 import _cards
from operation_pancake.research.cfb27_phase2 import is_special
from operation_pancake.research.cfb27_phase6_10 import _card_position

RETRIEVAL_DATE = "2026-08-13"
COMMON_EXACT = ("SPD", "ACC", "AGI", "AWR", "STR", "TGH", "COD", "BSH", "MCV", "ZCV")
POSITION_ROLES = {
    "TE": ("RBK", "PBK", "IBL", "STR"),
    "CB": ("MCV", "ZCV", "PRS", "PRC"),
    "MIKE": ("BSH", "STR", "TAK", "POW"),
    "EDGE": ("BSH", "PMV", "FMV", "STR"),
    "C": ("RBK", "PBK", "IBL", "STR"),
    "LG": ("RBK", "PBK", "IBL", "STR"),
    "RG": ("RBK", "PBK", "IBL", "STR"),
    "LT": ("RBK", "PBK", "IBL", "STR"),
    "RT": ("RBK", "PBK", "IBL", "STR"),
    "HB": ("BTK", "COD", "CAR", "SPD"),
    "WR": ("CTH", "SRR", "MRR", "DRR"),
    "QB": ("THP", "SAC", "MAC", "DAC"),
    "FS": ("ZCV", "MCV", "PRC", "SPD"),
    "SS": ("ZCV", "MCV", "POW", "SPD"),
    "DT": ("BSH", "PMV", "FMV", "STR"),
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_release_date(value: str) -> datetime:
    """Accept legacy M/D/Y and canonical ISO-8601 release timestamps."""
    try:
        return datetime.strptime(value, "%m/%d/%Y")
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _mean(values) -> float | None:
    values = list(values)
    return round(statistics.mean(values), 4) if values else None


def _slope(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3 or len({x for x, _ in pairs}) < 2:
        return None
    xbar = statistics.mean(x for x, _ in pairs)
    ybar = statistics.mean(y for _, y in pairs)
    denominator = sum((x - xbar) ** 2 for x, _ in pairs)
    return round(sum((x - xbar) * (y - ybar) for x, y in pairs) / denominator, 6)


def source_registry() -> list[dict]:
    def row(game, source, url, coverage, access, **kwargs):
        return {
            "game": game,
            "season": game.split()[-1],
            "source": source,
            "url": url,
            "access_method": access,
            "coverage": coverage,
            "retrieval_date": RETRIEVAL_DATE,
            "confidence": kwargs.pop("confidence", "PUBLIC_PAGE_CONFIRMED"),
            **kwargs,
        }

    common_cut = {
        "positions": "MULTI_POSITION",
        "ovr_range": "PUBLIC_FILTER; NOT EXHAUSTIVELY ACQUIRED",
        "archetypes": True,
        "program_card_type": True,
        "ratings_available": "CARD_SUMMARY_AND_DETAIL",
        "abilities_available": "CARD_DETAIL",
        "release_information": True,
        "market_information": "PUBLIC_DISPLAY_PRICE_WHERE_AVAILABLE",
        "stable_ids": True,
    }
    return [
        row(
            "CFB27",
            "CFB.FAN",
            "https://cfb.fan/players/",
            "CUT CARD DATABASE",
            "ORDINARY_PUBLIC_HTML_PAGINATION",
            limitations=(
                "435 previously frozen detail records; bulk history not acquired this packet"
            ),
            **common_cut,
        ),
        row(
            "CFB26",
            "CFB.FAN",
            "https://cfb.fan/26/players/",
            "CUT CARD DATABASE",
            "ORDINARY_PUBLIC_HTML_PAGINATION",
            limitations="discovered; no exhaustive acquisition",
            **common_cut,
        ),
        row(
            "CFB25",
            "CFB.FAN",
            "https://cfb.fan/25/players/",
            "CUT CARD DATABASE",
            "ORDINARY_PUBLIC_HTML_PAGINATION",
            limitations="discovered; no exhaustive acquisition",
            **common_cut,
        ),
        row(
            "CFB27",
            "CollegeFootball.gg",
            "https://collegefootball.gg/players/",
            "11,730 BASE-ROSTER PLAYERS CLAIMED BY SOURCE",
            "ORDINARY_PUBLIC_HTML; 25 VISIBLE ROWS",
            positions="21 POSITION GROUPS",
            ovr_range="VISIBLE 74-99; FULL RANGE NOT ACQUIRED",
            archetypes=True,
            program_card_type=False,
            ratings_available="OVR/SPD/ACC/STR/AWR VISIBLE; DETAIL PAGES MORE",
            abilities_available=True,
            release_information=False,
            market_information=False,
            stable_ids="SLUG",
            limitations=(
                "bulk client route unavailable through ordinary navigation; "
                "coverage claim registered, not ingested"
            ),
        ),
        row(
            "Madden 27",
            "MUT.GG",
            "https://www.mut.gg/players/",
            "MUT CARD DATABASE",
            "ORDINARY_PUBLIC_HTML",
            positions="MULTI_POSITION",
            ovr_range="NOT ACQUIRED",
            archetypes=True,
            program_card_type=True,
            ratings_available=True,
            abilities_available=True,
            release_information=True,
            market_information=True,
            stable_ids=True,
            limitations="discovered only; no bulk acquisition",
        ),
        row(
            "Madden 25",
            "EA schema inventory",
            "data/external/ea_schema_inventory/M25_inventory.json.gz",
            "DATABASE SCHEMA ONLY",
            "LOCAL_FROZEN_ARTIFACT",
            positions="SCHEMA",
            ovr_range=None,
            archetypes="STRUCTURAL",
            program_card_type="STRUCTURAL",
            ratings_available="FIELD DEFINITIONS",
            abilities_available="FIELD DEFINITIONS",
            release_information="STRUCTURAL",
            market_information=False,
            stable_ids="STRUCTURAL",
            limitations="not a player population",
        ),
        row(
            "Madden 19",
            "Historical Center workbook",
            "Operation_Pancake_Madden19_Center_Formula.xlsx",
            "53 CENTER MODEL POPULATION",
            "HISTORICALLY_RECOVERED",
            positions=["C"],
            ovr_range="MODEL METADATA ONLY",
            archetypes=False,
            program_card_type=False,
            ratings_available="AGGREGATE MODEL/WEIGHTS",
            abilities_available=False,
            release_information=False,
            market_information=False,
            stable_ids=False,
            limitations="individual 53-player vectors not in canonical repository",
        ),
    ]


def crosswalk() -> list[dict]:
    rows = [
        {"source_field": field, "common_field": field, "classification": "EXACT"}
        for field in COMMON_EXACT
    ]
    rows += [
        {"source_field": "TAK", "common_field": "TAC", "classification": "RENAMED"},
        {"source_field": "PAC", "common_field": "PAC", "classification": "EXACT"},
        {"source_field": "SAC", "common_field": "SAC", "classification": "EXACT"},
        {"source_field": "MAC", "common_field": "MAC", "classification": "EXACT"},
        {
            "source_field": "skill_group_caps",
            "common_field": None,
            "classification": "GAME_SPECIFIC",
        },
        {"source_field": "dev_trait", "common_field": None, "classification": "GAME_SPECIFIC"},
        {
            "source_field": "unknown_historical_alias",
            "common_field": None,
            "classification": "UNRESOLVED",
        },
    ]
    return rows


def common_cards(cards: list[dict]) -> list[dict]:
    return [
        {
            "game": "CFB27",
            "year": 27,
            "player": card["player_name"],
            "position": card["position"],
            "analysis_position": _card_position(card),
            "overall": card["overall"],
            "archetype": card["archetype"],
            "program": card["program"],
            "card_type": card["card_type"],
            "team": card["team_school"],
            "release_date": card["release_date"],
            "height": None,
            "weight": None,
            "displayed_attributes": card["displayed_ratings"],
            "abilities": [],
            "ability_tiers": [],
            "source_id": card["external_source"],
            "source_card_id": card["external_card_id"],
            "validation": card["validation_status"],
            "external_staged": True,
        }
        for card in cards
    ]


def attribute_economy(cards: list[dict]) -> dict:
    result = {}
    for position in sorted({_card_position(card) for card in cards}):
        selected = [card for card in cards if _card_position(card) == position]
        attributes = sorted({key for card in selected for key in card["displayed_ratings"]})
        result[position] = {}
        for attribute in attributes:
            pairs = [
                (card["overall"], card["displayed_ratings"][attribute])
                for card in selected
                if attribute in card["displayed_ratings"]
            ]
            slope = _slope(pairs)
            classification = "UNRESOLVED"
            if slope is not None:
                absolute = abs(slope)
                classification = (
                    "OVR_EXPENSIVE"
                    if absolute >= 1.25
                    else "OVR_MODERATE"
                    if absolute >= 0.6
                    else "OVR_CHEAP"
                    if absolute >= 0.15
                    else "OVR_NEUTRAL"
                )
            by_ovr = defaultdict(list)
            by_arch = defaultdict(list)
            for card in selected:
                if attribute in card["displayed_ratings"]:
                    by_ovr[card["overall"]].append(card["displayed_ratings"][attribute])
                    by_arch[card["archetype"]].append(card["displayed_ratings"][attribute])
            result[position][attribute] = {
                "count": len(pairs),
                "ovr_slope": slope,
                "ovr_cost": classification,
                "same_ovr_range_mean": _mean(
                    max(values) - min(values) for values in by_ovr.values() if len(values) > 1
                ),
                "same_archetype_variance_mean": _mean(
                    statistics.pvariance(values) for values in by_arch.values() if len(values) > 1
                ),
                "ordinary_mean": _mean(
                    card["displayed_ratings"][attribute]
                    for card in selected
                    if attribute in card["displayed_ratings"] and not is_special(card)
                ),
                "special_mean": _mean(
                    card["displayed_ratings"][attribute]
                    for card in selected
                    if attribute in card["displayed_ratings"] and is_special(card)
                ),
                "minimum": min((value for _, value in pairs), default=None),
                "maximum": max((value for _, value in pairs), default=None),
                "gameplay_value": "UNKNOWN",
            }
    return {"CFB27": result, "cross_year_status": "INSUFFICIENT_ACQUIRED_HISTORICAL_POPULATIONS"}


def capability_creep(cards: list[dict]) -> dict:
    result = {}
    for position in sorted({_card_position(card) for card in cards}):
        selected = sorted(
            (card for card in cards if _card_position(card) == position and card["release_date"]),
            key=lambda card: (
                _parse_release_date(card["release_date"]),
                card["overall"],
                card["external_card_id"],
            ),
        )
        if not selected:
            continue
        first = _parse_release_date(selected[0]["release_date"]).date()
        ceiling = -1
        events = []
        for card in selected:
            if card["overall"] > ceiling:
                observed = _parse_release_date(card["release_date"]).date()
                events.append(
                    {
                        "date": observed.isoformat(),
                        "days_from_first": (observed - first).days,
                        "overall": card["overall"],
                        "card_id": card["external_card_id"],
                        "special": is_special(card),
                        "program": card["program"],
                    }
                )
                ceiling = card["overall"]
        result[position] = {
            "cards": len(selected),
            "first_observed_ovr": selected[0]["overall"],
            "maximum_observed_ovr": max(card["overall"] for card in selected),
            "ovr_ceiling_events": events,
            "days_to_next_ovr": [
                right["days_from_first"] - left["days_from_first"]
                for left, right in zip(events, events[1:], strict=False)
            ],
            "spd_date_slope": _dated_slope(selected, "SPD"),
            "acc_date_slope": _dated_slope(selected, "ACC"),
            "causation_claimed": False,
        }
    return {"CFB27": result, "cross_year_status": "BLOCKED_BY_HISTORICAL_POPULATION_DATA"}


def _dated_slope(cards: list[dict], attribute: str):
    pairs = [
        (
            _parse_release_date(card["release_date"]).date().toordinal(),
            card["displayed_ratings"][attribute],
        )
        for card in cards
        if attribute in card["displayed_ratings"]
    ]
    return _slope(pairs)


def archetype_evolution(cards: list[dict]) -> dict:
    inventory = defaultdict(Counter)
    for card in cards:
        inventory[_card_position(card)][card["archetype"]] += 1
    return {
        "inventory": {
            position: dict(sorted(counts.items())) for position, counts in sorted(inventory.items())
        },
        "lineage_candidates": [],
        "classification": "UNRESOLVED_SINGLE_ACQUIRED_YEAR",
        "forced_equivalence": False,
    }


def market_observations() -> list[dict]:
    observed_at = "2026-08-13T22:00:00-07:00"
    rows = [
        ("27-201023902", "Ahmad Hardy", 1630000),
        ("27-201007473", "Matayo Uiagalelei", 2030000),
        ("27-27001160", "Raleek Brown", 782000),
        ("27-270020185", "DJ Lagway", 982000),
        ("27-211026417", "Warren Moon", 512000),
        ("27-201008202", "Bray Hubbard", 888000),
        ("27-700026051", "Michael Vick", 798000),
        ("27-201018293", "Trey'Dez Green", 992000),
    ]
    return [
        {
            "card_id": card_id,
            "player": player,
            "observed_at": observed_at,
            "source": "CFB.FAN_PUBLIC_PLAYERS_PAGE",
            "currency": "CUT_COINS",
            "platform": "UNSPECIFIED",
            "observation_type": "PUBLIC_DISPLAY_PRICE",
            "price": price,
            "listing_count": None,
            "sale_price": None,
            "source_url": "https://cfb.fan/players/",
            "provenance": "VISIBLE_PUBLIC_PAGE_2026-08-13",
            "historical": False,
        }
        for card_id, player, price in rows
    ]


def inheritance() -> dict:
    return {
        "TE": {
            "classification": "STABLE_WITH_RECALIBRATION",
            "basis": "existing Madden-to-CFB ranking inheritance; no new historical vectors",
        },
        "C": {
            "classification": "INSUFFICIENT_DATA",
            "basis": (
                "M19 53-player aggregate model preserved; individual cross-year vectors unavailable"
            ),
        },
        "QB": {"classification": "INSUFFICIENT_DATA"},
        "MIKE": {"classification": "INSUFFICIENT_DATA"},
        "CB": {"classification": "INSUFFICIENT_DATA"},
        "EDGE": {"classification": "INSUFFICIENT_DATA"},
        "OL": {"classification": "INSUFFICIENT_DATA"},
        "coefficients_assumed_equal": False,
    }


def moneyball(cards: list[dict], economy: dict) -> dict:
    pools = defaultdict(list)
    for card in cards:
        position = _card_position(card)
        roles = POSITION_ROLES.get(position, ())
        cheap = [
            attribute
            for attribute in roles
            if economy["CFB27"].get(position, {}).get(attribute, {}).get("ovr_cost")
            in {"OVR_CHEAP", "OVR_NEUTRAL"}
            and attribute in card["displayed_ratings"]
        ]
        if not cheap:
            continue
        peers = [
            other
            for other in cards
            if _card_position(other) == position and other["overall"] == card["overall"]
        ]
        unusual = {
            attribute: round(
                card["displayed_ratings"][attribute]
                - statistics.mean(
                    other["displayed_ratings"][attribute]
                    for other in peers
                    if attribute in other["displayed_ratings"]
                ),
                3,
            )
            for attribute in cheap
        }
        positive = {attribute: value for attribute, value in unusual.items() if value > 0}
        if positive:
            pools[position].append(
                {
                    "card_id": card["external_card_id"],
                    "player": card["player_name"],
                    "overall": card["overall"],
                    "archetype": card["archetype"],
                    "positive_cheap_attribute_residuals": positive,
                    "ovr_cost": "CHEAP_OR_NEUTRAL",
                    "market_premium": None,
                    "ability_leverage": "JOIN_AVAILABLE_FOR_SUPPORTED_POSITIONS",
                    "gameplay_confidence": "UNVALIDATED",
                }
            )
    targets = {
        "TE": ("TE",),
        "CB": ("CB",),
        "MIKE": ("MIKE",),
        "EDGE": ("EDGE",),
        "OL": ("C", "LG", "RG", "LT", "RT"),
        "HB": ("HB",),
        "WR": ("WR",),
        "QB": ("QB",),
        "SAFETY": ("FS", "SS"),
        "DT": ("DT",),
    }
    result = {}
    for name, positions in targets.items():
        rows = [row for position in positions for row in pools.get(position, [])]
        rows.sort(
            key=lambda row: (
                -sum(row["positive_cheap_attribute_residuals"].values()),
                row["card_id"],
            )
        )
        result[name] = {
            "candidates": rows[:10],
            "status": (
                "STATISTICAL_CANDIDATES_NOT_VALIDATED"
                if rows
                else "NO_POSITIVE_OVR_CHEAP_ROLE_RESIDUAL_IN_CURRENT_POPULATION"
            ),
            "explanation": (
                "Requires a cheap/neutral displayed-OVR relationship and a positive "
                "same-position/same-OVR role-rating residual. Market and gameplay "
                "validation remain separate."
            ),
        }
    return result


def secondary(cards: list[dict]) -> dict:
    by_player = defaultdict(list)
    for card in cards:
        by_player[(card["player_name"], card["position"])].append(card)
    lineage = [
        {
            "player": key[0],
            "position": key[1],
            "cards": [
                card["external_card_id"]
                for card in sorted(values, key=lambda card: card["overall"])
            ],
            "classification": "SAME_GAME_CANDIDATE_NOT_CONFIRMED_PROGRESSION",
        }
        for key, values in sorted(by_player.items())
        if len(values) > 1
    ]
    promos = Counter(card["program"] for card in cards if is_special(card))
    ltd = [card["external_card_id"] for card in cards if "LTD" in card["program"].upper()]
    balance = Counter((_card_position(card), card["archetype"]) for card in cards)
    return {
        "same_player_lineage": lineage,
        "promo_construction": dict(promos.most_common()),
        "ltd_construction": {"cards": ltd, "status": "DESCRIPTIVE_ONLY"},
        "spd_inflation": {
            position: _dated_slope(
                [card for card in cards if _card_position(card) == position], "SPD"
            )
            for position in sorted({_card_position(card) for card in cards})
        },
        "technical_inflation": {
            position: {
                attribute: _dated_slope(
                    [card for card in cards if _card_position(card) == position], attribute
                )
                for attribute in POSITION_ROLES.get(position, ())
            }
            for position in sorted({_card_position(card) for card in cards})
        },
        "archetype_population_balance": {
            f"{position}::{archetype}": count
            for (position, archetype), count in sorted(balance.items())
        },
        "pc_evaluator_interface": {
            "required_inputs": [
                "game",
                "year",
                "card_id",
                "position",
                "overall",
                "attributes",
                "source_provenance",
            ],
            "optional_inputs": [
                "archetype",
                "program",
                "release_date",
                "market_observations",
                "abilities",
            ],
            "outputs": ["ovr_cost", "market_premium", "ability_leverage", "gameplay_confidence"],
        },
    }


def build_op_x_003(root: Path) -> dict:
    cards = _cards(root)
    inputs = [
        root / "data/external/cfb_fan_population_state.json",
        root / "data/research/cfb27_op_x_002/freeze.json",
        root / "data/research/cfb27_op_x_002/secondary_gates.json",
    ]
    economy = attribute_economy(cards)
    market = market_observations()
    return {
        "freeze": {
            "source_commit": "8b58b55",
            "population_n": len(cards),
            "input_sha256": {
                path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in inputs
            },
        },
        "ea_historical_source_registry": source_registry(),
        "acquisition_manifest": {
            "populations": {
                "CFB25": 0,
                "CFB26": 0,
                "CFB27_CUT": len(cards),
                "CFB27_BASE_ROSTER": 0,
                "Madden25": 0,
                "Madden26": 0,
                "Madden27": 0,
                "older_madden_cards": 0,
            },
            "historical_model_population_not_cards": {"Madden19_C": 53},
            "status": (
                "PUBLIC_SOURCES_DISCOVERED; HISTORICAL_BULK_ACQUISITION_BLOCKED_BY_ORDINARY_ACCESS"
            ),
            "rate_limit_bypassed": False,
            "raw_existing_snapshots_preserved": True,
        },
        "attribute_crosswalk": crosswalk(),
        "ea_cross_year_card_model": common_cards(cards),
        "attribute_economy": economy,
        "capability_creep_history": capability_creep(cards),
        "archetype_evolution": archetype_evolution(cards),
        "market_observations": market,
        "market_premium": {
            "status": "BLOCKED_BY_DATA",
            "real_observations": len(market),
            "minimum_reason": (
                "eight heterogeneous one-time display prices cannot support "
                "within-position/OVR cohort premiums"
            ),
            "forward_collection_active": True,
            "listing_as_sale": False,
        },
        "formula_inheritance": inheritance(),
        "moneyball_candidates": moneyball(cards, economy),
        "secondary_gates": secondary(cards),
        "validation": {
            "guessed": False,
            "unknown_zero_conversion": False,
            "forced_mappings": False,
            "canonical_changes": False,
            "market_fabrication": False,
            "listing_as_sale": False,
            "conflicts_preserved": True,
            "access_bypass": False,
        },
    }


def write_artifacts(output: Path, analysis: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in analysis.items():
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

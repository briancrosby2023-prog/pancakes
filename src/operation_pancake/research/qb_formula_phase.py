"""Deterministic population and boundary research for the QB Formula Phase."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, median, pstdev
from typing import Any, Iterable

from operation_pancake.models.player_card import PlayerCard
from operation_pancake.repository.canonical_repository import CanonicalRepository

QB_RATING_FIELDS = (
    "SPD",
    "ACC",
    "AGI",
    "AWR",
    "STR",
    "TGH",
    "THP",
    "TAC",
    "SAC",
    "MAC",
    "DAC",
    "RUN",
    "TUP",
    "PAC",
    "BSK",
)

FIT_ROLE = "DEVELOPMENT"
HOLDOUT_ROLE = "INDEPENDENT HOLDOUT"
PROFILE_DUPLICATE_ROLE = "PROFILE DUPLICATE — EXCLUDED FROM MODEL COUNT"
BOUNDARY_ROLE = "DEVELOPMENT BOUNDARY"
RESEARCH_ONLY_ROLE = "RESEARCH ONLY — INSUFFICIENT"
BOUNDARY_SCOPE = "PROGRESSION BOUNDARY <80"
SPARSE_CELL_MAX = 2


@dataclass(frozen=True, slots=True)
class QBObservation:
    """One validated canonical QB observation prepared for formula research."""

    qb_id: str
    player: str
    overall: int
    archetype: str
    program: str
    ratings: tuple[int, ...]
    model_role: str
    population_scope: str
    unique_profile_key: str
    duplicate_note: str | None
    frozen_score_check: float
    frozen_score_formula: float
    formula_delta: float
    source_id: str
    source_locator: str
    source_record: str
    workbook_sheet: str
    workbook_row: int
    analysis_partition: str

    def rating_map(self) -> dict[str, int]:
        """Return the named rating vector in canonical field order."""
        return dict(zip(QB_RATING_FIELDS, self.ratings, strict=True))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable machine-readable representation."""
        return {
            "qb_id": self.qb_id,
            "player": self.player,
            "overall": self.overall,
            "archetype": self.archetype,
            "program": self.program,
            "ratings": self.rating_map(),
            "model_role": self.model_role,
            "population_scope": self.population_scope,
            "unique_profile_key": self.unique_profile_key,
            "duplicate_note": self.duplicate_note,
            "frozen_score_check": self.frozen_score_check,
            "frozen_score_formula": self.frozen_score_formula,
            "formula_delta": self.formula_delta,
            "source_id": self.source_id,
            "source_locator": self.source_locator,
            "source_record": self.source_record,
            "workbook_sheet": self.workbook_sheet,
            "workbook_row": self.workbook_row,
            "analysis_partition": self.analysis_partition,
        }


def _required_text(value: object, field_name: str, qb_id: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"QB {qb_id!r} has missing or invalid {field_name}.")
    return value.strip()


def _required_number(value: object, field_name: str, qb_id: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"QB {qb_id!r} has missing or invalid {field_name}.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"QB {qb_id!r} has non-finite {field_name}.")
    return number


def _partition(model_role: str, population_scope: str) -> str:
    if model_role == PROFILE_DUPLICATE_ROLE:
        return "profile_duplicate"
    if model_role == HOLDOUT_ROLE:
        return "holdout"
    if model_role == RESEARCH_ONLY_ROLE:
        return "research_only"
    if model_role == BOUNDARY_ROLE or population_scope == BOUNDARY_SCOPE:
        return "boundary"
    if model_role == FIT_ROLE:
        return "fit"
    return "unclassified"


def observation_from_card(card: PlayerCard) -> QBObservation:
    """Validate and convert one canonical PlayerCard without filling missing data."""
    if card.position.strip().upper() != "QB":
        raise ValueError(f"Expected QB card; received {card.position!r}.")

    actual_fields = set(card.attributes)
    expected_fields = set(QB_RATING_FIELDS)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(actual_fields - expected_fields)
        raise ValueError(
            f"QB rating vector must contain exactly 15 fields; "
            f"missing={missing}, unexpected={unexpected}."
        )

    qb_id_value = card.metadata.get("qb_id")
    qb_id = _required_text(qb_id_value, "qb_id", qb_id_value)
    archetype = _required_text(card.archetype, "archetype", qb_id)
    program = _required_text(card.program, "program", qb_id)
    model_role = _required_text(card.metadata.get("model_role"), "model_role", qb_id)
    population_scope = _required_text(
        card.metadata.get("population_scope"), "population_scope", qb_id
    )
    unique_profile_key = _required_text(
        card.metadata.get("unique_profile_key"), "unique_profile_key", qb_id
    )

    ratings = tuple(card.attributes[field] for field in QB_RATING_FIELDS)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in ratings):
        raise TypeError(f"QB {qb_id!r} ratings must all be integers.")

    source_record = _required_text(card.source_record, "source_record", qb_id)
    source_id = _required_text(card.metadata.get("source_id"), "source_id", qb_id)
    source_locator = _required_text(
        card.metadata.get("source_locator"), "source_locator", qb_id
    )
    workbook_sheet = _required_text(
        card.metadata.get("workbook_sheet"), "workbook_sheet", qb_id
    )
    workbook_row = card.metadata.get("workbook_row")
    if isinstance(workbook_row, bool) or not isinstance(workbook_row, int):
        raise TypeError(f"QB {qb_id!r} has missing or invalid workbook_row.")

    duplicate_note_value = card.metadata.get("duplicate_note")
    duplicate_note = (
        None
        if duplicate_note_value is None
        else _required_text(duplicate_note_value, "duplicate_note", qb_id)
    )

    return QBObservation(
        qb_id=qb_id,
        player=card.name.strip(),
        overall=card.overall,
        archetype=archetype,
        program=program,
        ratings=ratings,
        model_role=model_role,
        population_scope=population_scope,
        unique_profile_key=unique_profile_key,
        duplicate_note=duplicate_note,
        frozen_score_check=_required_number(
            card.metadata.get("frozen_score_check"), "frozen_score_check", qb_id
        ),
        frozen_score_formula=_required_number(
            card.metadata.get("frozen_score_formula"), "frozen_score_formula", qb_id
        ),
        formula_delta=_required_number(
            card.metadata.get("formula_delta"), "formula_delta", qb_id
        ),
        source_id=source_id,
        source_locator=source_locator,
        source_record=source_record,
        workbook_sheet=workbook_sheet,
        workbook_row=workbook_row,
        analysis_partition=_partition(model_role, population_scope),
    )


def observations_from_repository(repository: CanonicalRepository) -> list[QBObservation]:
    """Build a deterministic QB research population from the canonical repository."""
    observations = [
        observation_from_card(card) for card in repository.players_by_position("QB")
    ]
    observations.sort(key=lambda observation: observation.qb_id)

    qb_ids = [observation.qb_id for observation in observations]
    if len(qb_ids) != len(set(qb_ids)):
        raise ValueError("Canonical QB research population contains duplicate QB_ID values.")

    return observations


def _counts(values: Iterable[object]) -> dict[str, int]:
    counter = Counter(str(value) for value in values)
    return dict(sorted(counter.items()))


def _stats(values: list[int]) -> dict[str, int | float]:
    return {
        "count": len(values),
        "minimum": min(values),
        "maximum": max(values),
        "mean": round(fmean(values), 6),
        "median": round(float(median(values)), 6),
        "population_standard_deviation": round(pstdev(values), 6),
    }


def _attribute_statistics(
    observations: list[QBObservation],
) -> dict[str, dict[str, int | float]]:
    return {
        field: _stats([observation.rating_map()[field] for observation in observations])
        for field in QB_RATING_FIELDS
    }


def _pearson(xs: list[int], ys: list[int]) -> float | None:
    x_mean = fmean(xs)
    y_mean = fmean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    denominator = math.sqrt(
        sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys)
    )
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _correlations(observations: list[QBObservation]) -> dict[str, float | None]:
    overalls = [observation.overall for observation in observations]
    return {
        field: _pearson(
            [observation.rating_map()[field] for observation in observations], overalls
        )
        for field in QB_RATING_FIELDS
    }


def _distance(left: QBObservation, right: QBObservation) -> float:
    return round(
        math.sqrt(sum((a - b) ** 2 for a, b in zip(left.ratings, right.ratings, strict=True))),
        6,
    )


def _pair(left: QBObservation, right: QBObservation) -> dict[str, Any]:
    deltas = {
        field: right_value - left_value
        for field, left_value, right_value in zip(
            QB_RATING_FIELDS, left.ratings, right.ratings, strict=True
        )
    }
    return {
        "lower_qb_id": left.qb_id,
        "upper_qb_id": right.qb_id,
        "lower_overall": left.overall,
        "upper_overall": right.overall,
        "archetype": left.archetype if left.archetype == right.archetype else None,
        "euclidean_distance": _distance(left, right),
        "rating_deltas": deltas,
    }


def _adjacent_ovr_nearest(observations: list[QBObservation]) -> list[dict[str, Any]]:
    by_archetype: dict[str, list[QBObservation]] = defaultdict(list)
    for observation in observations:
        by_archetype[observation.archetype].append(observation)

    results: list[dict[str, Any]] = []
    for archetype in sorted(by_archetype):
        cards = by_archetype[archetype]
        levels = sorted({card.overall for card in cards})
        for lower_ovr, upper_ovr in zip(levels, levels[1:], strict=False):
            if upper_ovr - lower_ovr != 1:
                continue
            candidates = [
                (lower, upper)
                for lower in cards
                if lower.overall == lower_ovr
                for upper in cards
                if upper.overall == upper_ovr
            ]
            lower, upper = min(
                candidates,
                key=lambda pair: (_distance(*pair), pair[0].qb_id, pair[1].qb_id),
            )
            results.append(_pair(lower, upper))
    return results


def _same_ovr_contrasts(observations: list[QBObservation]) -> list[dict[str, Any]]:
    cells: dict[tuple[str, int], list[QBObservation]] = defaultdict(list)
    for observation in observations:
        cells[(observation.archetype, observation.overall)].append(observation)

    results: list[dict[str, Any]] = []
    for _, cards in sorted(cells.items()):
        if len(cards) < 2:
            continue
        candidates = [
            (left, right)
            for index, left in enumerate(cards)
            for right in cards[index + 1 :]
        ]
        left, right = max(
            candidates,
            key=lambda pair: (_distance(*pair), pair[0].qb_id, pair[1].qb_id),
        )
        results.append(_pair(left, right))
    return results


def _same_player_evidence(observations: list[QBObservation]) -> list[dict[str, Any]]:
    players: dict[str, list[QBObservation]] = defaultdict(list)
    for observation in observations:
        players[observation.player.casefold()].append(observation)

    evidence: list[dict[str, Any]] = []
    for cards in players.values():
        if len(cards) < 2:
            continue
        cards.sort(key=lambda card: (card.overall, card.qb_id))
        for lower, upper in zip(cards, cards[1:], strict=False):
            pair = _pair(lower, upper)
            pair["player"] = lower.player
            pair["evidence_type"] = (
                "same_player_same_ovr"
                if lower.overall == upper.overall
                else "same_player_cross_ovr"
            )
            pair["confirmed_progression"] = False
            evidence.append(pair)
    return sorted(evidence, key=lambda item: (item["player"].casefold(), item["lower_qb_id"]))


def _repeated_profiles(observations: list[QBObservation]) -> list[dict[str, Any]]:
    profiles: dict[str, list[QBObservation]] = defaultdict(list)
    for observation in observations:
        profiles[observation.unique_profile_key].append(observation)
    return [
        {
            "unique_profile_key": profile,
            "qb_ids": [card.qb_id for card in sorted(cards, key=lambda card: card.qb_id)],
            "model_roles": [card.model_role for card in sorted(cards, key=lambda card: card.qb_id)],
        }
        for profile, cards in sorted(profiles.items())
        if len(cards) > 1
    ]


def build_qb_formula_research(repository: CanonicalRepository) -> dict[str, Any]:
    """Build the complete reproducible QB population and boundary research dataset."""
    observations = observations_from_repository(repository)
    if not observations:
        raise ValueError("Canonical repository contains no QB observations.")

    overall_levels = sorted({observation.overall for observation in observations})
    missing_levels = [
        level
        for level in range(min(overall_levels), max(overall_levels) + 1)
        if level not in overall_levels
    ]
    archetypes = sorted({observation.archetype for observation in observations})
    cells = [
        {
            "archetype": archetype,
            "overall": overall,
            "count": sum(
                observation.archetype == archetype and observation.overall == overall
                for observation in observations
            ),
        }
        for archetype in archetypes
        for overall in overall_levels
    ]

    by_archetype = {
        archetype: [
            observation for observation in observations if observation.archetype == archetype
        ]
        for archetype in archetypes
    }

    explicit_boundary = [
        observation.to_dict()
        for observation in observations
        if observation.analysis_partition == "boundary"
    ]

    return {
        "schema_version": 1,
        "phase": "QB Formula Phase — Population & Boundary Research Foundation",
        "formula_status": "unsolved",
        "rating_fields": list(QB_RATING_FIELDS),
        "population": {
            "count": len(observations),
            "counts_by_overall": _counts(observation.overall for observation in observations),
            "counts_by_archetype": _counts(
                observation.archetype for observation in observations
            ),
            "counts_by_program": _counts(observation.program for observation in observations),
            "counts_by_model_role": _counts(
                observation.model_role for observation in observations
            ),
            "counts_by_population_scope": _counts(
                observation.population_scope for observation in observations
            ),
            "counts_by_analysis_partition": _counts(
                observation.analysis_partition for observation in observations
            ),
            "overall_minimum": min(overall_levels),
            "overall_maximum": max(overall_levels),
            "missing_overall_levels": missing_levels,
            "ovr_archetype_cells": cells,
            "sparse_ovr_archetype_cells": [
                cell for cell in cells if 0 < cell["count"] <= SPARSE_CELL_MAX
            ],
        },
        "attribute_statistics": {
            "global": _attribute_statistics(observations),
            "by_archetype": {
                archetype: {
                    "sample_size": len(cards),
                    "statistics": _attribute_statistics(cards),
                }
                for archetype, cards in by_archetype.items()
            },
            "pearson_correlation_with_overall": {
                "global": _correlations(observations),
                "by_archetype": {
                    archetype: {
                        "sample_size": len(cards),
                        "correlations": _correlations(cards),
                    }
                    for archetype, cards in by_archetype.items()
                    if len(cards) >= 3
                },
                "interpretation_warning": (
                    "Correlation is descriptive evidence, not a formula weight."
                ),
            },
        },
        "boundary_evidence": {
            "adjacent_ovr_nearest_within_archetype": _adjacent_ovr_nearest(observations),
            "same_ovr_maximum_contrasts_within_archetype": _same_ovr_contrasts(
                observations
            ),
            "same_player_card_sequences": _same_player_evidence(observations),
            "repeated_profiles": _repeated_profiles(observations),
            "explicit_boundary_records": explicit_boundary,
            "progression_claim_warning": (
                "Same-player sequences are candidates only; progression is not inferred "
                "without an explicit canonical link."
            ),
        },
        "architecture_hypotheses": [
            {
                "id": "A",
                "name": "universal_weighted_formula",
                "description": "One shared QB rating vector and OVR mapping.",
            },
            {
                "id": "B",
                "name": "archetype_specific_weighted_formulas",
                "description": "Independent rating weights and mappings by QB archetype.",
            },
            {
                "id": "C",
                "name": "shared_core_with_archetype_modifiers",
                "description": "Shared positional core plus limited archetype-specific effects.",
            },
            {
                "id": "D",
                "name": "shared_weights_archetype_thresholds",
                "description": (
                    "Shared rating weights with archetype-specific thresholds or intercepts."
                ),
            },
        ],
        "model_selection_criteria": [
            "cross_ovr_accuracy",
            "archetype_consistency",
            "boundary_behavior",
            "progression_evidence",
            "parameter_simplicity",
            "held_out_performance",
            "ea_plausibility",
            "systematic_failure_patterns",
        ],
        "observations": [observation.to_dict() for observation in observations],
    }


def write_qb_formula_research(path: str | Path, repository: CanonicalRepository) -> None:
    """Write deterministic UTF-8 JSON research output."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_qb_formula_research(repository)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

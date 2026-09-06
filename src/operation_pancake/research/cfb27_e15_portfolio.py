"""Position-level portfolio control for OP-X-012E.15.

E.15 should not become a serial perfection hunt. This module turns the
validated Alpha population into an explicit position queue and records when a
position is ready for GM use versus when more formula research is warranted.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from operation_pancake.research.cfb27_e15_formula import classify_deployment

# CFB27-native taxonomy is canonical. Do not silently collapse these positions
# to legacy Madden/NFL aliases such as MLB/LE/RE.
PRIORITY_POSITIONS = (
    "C",
    "TE",
    "CB",
    "FS",
    "SS",
    "DT",
    "SAM",
    "MIKE",
    "WILL",
    "LEDG",
    "REDG",
)


def build_position_portfolio(cards: Iterable[Mapping]) -> dict:
    """Summarize formula-reconstruction coverage from canonical Alpha cards."""
    counts: dict[str, int] = {}
    archetypes: dict[str, set[str]] = {}
    for card in cards:
        position = card.get("position")
        if not position:
            continue
        counts[position] = counts.get(position, 0) + 1
        archetype = card.get("archetype")
        if archetype:
            archetypes.setdefault(position, set()).add(str(archetype))

    rows = []
    for position in PRIORITY_POSITIONS:
        rows.append(
            {
                "position": position,
                "cards": counts.get(position, 0),
                "archetypes": sorted(archetypes.get(position, set())),
                "archetype_count": len(archetypes.get(position, set())),
                "research_state": "CALIBRATION_ACTIVE" if position == "C" else "QUEUED",
            }
        )
    return {
        "phase": "OP-X-012E.15",
        "strategy": "DECISION_QUALITY_NOT_PERFECTION",
        "priority_positions": rows,
        "priority_card_coverage": sum(row["cards"] for row in rows),
    }


def apply_position_result(portfolio: Mapping, position: str, result: Mapping) -> dict:
    """Attach a measured formula result and decide whether research should advance."""
    output = {
        **portfolio,
        "priority_positions": [dict(row) for row in portfolio["priority_positions"]],
    }
    deployment = classify_deployment(result)
    for row in output["priority_positions"]:
        if row["position"] != position:
            continue
        row["measured_exact_match_rate"] = result.get("exact_match_rate")
        row["measured_mean_absolute_error"] = result.get("mean_absolute_error")
        row["deployment"] = deployment
        if deployment == "GM_READY":
            row["research_state"] = "DEPLOY_AND_ADVANCE"
        elif deployment == "GM_USABLE":
            row["research_state"] = "DEPLOY_WITH_LIMITS_AND_ADVANCE"
        else:
            row["research_state"] = "RESEARCH_REQUIRED"
        break
    return output

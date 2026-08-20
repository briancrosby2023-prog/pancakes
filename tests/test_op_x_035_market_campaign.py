from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from operation_pancake.production.campaign import (
    build_campaign,
    campaign_round,
    evidence_blocker,
    movement,
    parse_compact_snapshot,
)
from operation_pancake.production.engine import load_population
from operation_pancake.production.market_campaign import (
    append_history,
    calibrate_decision,
    history_statistics,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-08-20T20:00:00+00:00"


@pytest.fixture(scope="module")
def cards() -> dict[str, dict]:
    return {row["card_id"]: row for row in load_population(ROOT)}


def _rows(prices: list[int], hours: list[int]) -> list[dict]:
    base = datetime(2026, 8, 17, 20, tzinfo=timezone.utc)
    return [
        {
            "card_id": "fixture:card",
            "observed_price": price,
            "user_observed_at": (base + timedelta(hours=hour)).isoformat(),
            "observation_type": "LOWEST_VISIBLE_LISTING",
            "identity_confidence": "EXACT",
            "evidence_scope": "FIXTURE",
        }
        for price, hour in zip(prices, hours, strict=True)
    ]


def test_compact_snapshot_enriches_exact_identity(cards: dict[str, dict]) -> None:
    card_id = "card:f35e84cba0d56c4270c3"
    rows = parse_compact_snapshot(
        f"{card_id} 55500\n",
        cards,
        observed_at="2026-08-20T12:00:00+00:00",
        ingested_at="2026-08-20T12:01:00+00:00",
        fixture=True,
    )
    assert rows[0]["player_name"] == "Brendan Black"
    assert rows[0]["identity_confidence"] == "EXACT"
    assert rows[0]["evidence_scope"] == "FIXTURE"


@pytest.mark.parametrize(
    "text, message",
    [
        ("unknown 100", "unresolved canonical"),
        ("card:f35e84cba0d56c4270c3 1.5", "positive integer"),
        ("card:f35e84cba0d56c4270c3 -1", "positive integer"),
        ("card:f35e84cba0d56c4270c3", "expected CARD_ID PRICE"),
    ],
)
def test_compact_snapshot_rejects_malformed_input(
    cards: dict[str, dict], text: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_compact_snapshot(
            text,
            cards,
            observed_at="2026-08-20T12:00:00+00:00",
            ingested_at="2026-08-20T12:01:00+00:00",
            fixture=True,
        )


def test_future_timestamp_and_bad_semantics_are_rejected(cards: dict[str, dict]) -> None:
    card_id = "card:f35e84cba0d56c4270c3"
    with pytest.raises(ValueError, match="future"):
        parse_compact_snapshot(
            f"{card_id} 100",
            cards,
            observed_at="2026-08-21T12:00:00+00:00",
            ingested_at="2026-08-20T12:00:00+00:00",
            fixture=True,
        )
    with pytest.raises(ValueError, match="unsupported observation type"):
        parse_compact_snapshot(
            f"{card_id} 100",
            cards,
            observed_at="2026-08-20T12:00:00+00:00",
            ingested_at="2026-08-20T12:01:00+00:00",
            observation_type="INVENTED",
            fixture=True,
        )


def test_fixture_cannot_contaminate_history(cards: dict[str, dict], tmp_path: Path) -> None:
    rows = parse_compact_snapshot(
        "card:f35e84cba0d56c4270c3 100",
        cards,
        observed_at="2026-08-20T12:00:00+00:00",
        ingested_at="2026-08-20T12:01:00+00:00",
        fixture=True,
    )
    with pytest.raises(ValueError, match="fixture observations"):
        append_history(tmp_path / "history.json", rows)
    assert not (tmp_path / "history.json").exists()


def test_round_accepts_partial_observation_set(cards: dict[str, dict]) -> None:
    requested = ["card:f35e84cba0d56c4270c3", "card:223972d9a434a9d9fb4c"]
    rows = parse_compact_snapshot(
        f"{requested[0]} 100",
        cards,
        observed_at="2026-08-20T12:00:00+00:00",
        ingested_at="2026-08-20T12:01:00+00:00",
        fixture=True,
    )
    result = campaign_round("ROUND 1", requested, rows)
    assert result["cards_observed"] == [requested[0]]
    assert result["cards_missing"] == [requested[1]]


def test_evidence_states_and_price_directions() -> None:
    assert history_statistics([], AS_OF)["quality"] == "INSUFFICIENT"
    one = history_statistics(_rows([100], [72]), AS_OF)
    assert evidence_blocker(one) == "WAIT — NEED 1 MORE OBSERVATION"
    assert (
        movement(history_statistics(_rows([100, 101, 100, 100], [0, 24, 48, 72]), AS_OF))[
            "direction"
        ]
        == "STABLE"
    )
    assert (
        movement(history_statistics(_rows([100, 110, 120, 130], [0, 24, 48, 72]), AS_OF))[
            "direction"
        ]
        == "RISING"
    )
    assert (
        movement(history_statistics(_rows([130, 120, 110, 100], [0, 24, 48, 72]), AS_OF))[
            "direction"
        ]
        == "FALLING"
    )
    assert (
        movement(history_statistics(_rows([100, 200, 90, 210], [0, 24, 48, 72]), AS_OF))[
            "direction"
        ]
        == "VOLATILE"
    )


def test_buy_gate_remains_independent_and_can_legitimately_pass() -> None:
    strong = history_statistics(_rows([100] * 8, [0, 12, 24, 36, 48, 60, 66, 72]), AS_OF)
    assert strong["quality"] == "STRONG"
    assert calibrate_decision(strong, "VALUE", gross_cost=100, budget=100)["decision"] == "BUY"
    assert calibrate_decision(strong, "PREMIUM", gross_cost=100, budget=100)["decision"] == "WAIT"


def test_real_campaign_is_evidence_limited_and_deduplicated() -> None:
    result = build_campaign(ROOT, [], AS_OF)
    assert len(result["comparison_sets"]) == 5
    assert len(result["unique_targets"]) == 16
    assert not result["arbitrage"]
    assert all(row["gm_action"] == "PRICE CHECK REQUIRED" for row in result["market_board"])


def test_durable_outputs_do_not_promote_context_prices() -> None:
    recovery = json.loads((ROOT / "data/research/op_x_035/market_state_recovery.json").read_text())
    assert recovery["context_only_observations"] == 8
    assert recovery["qualified_user_observations"] == 0
    assert recovery["context_observations_promoted"] == 0

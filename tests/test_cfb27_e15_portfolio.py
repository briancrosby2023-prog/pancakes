from operation_pancake.research.cfb27_e15_portfolio import (
    apply_position_result,
    build_position_portfolio,
)


def test_portfolio_keeps_multiple_positions_moving():
    cards = [
        {"position": "C", "archetype": "Agile"},
        {"position": "C", "archetype": "Pass Protector"},
        {"position": "TE", "archetype": "Possession"},
        {"position": "CB", "archetype": "Man To Man"},
    ]
    portfolio = build_position_portfolio(cards)
    rows = {row["position"]: row for row in portfolio["priority_positions"]}
    assert rows["C"]["research_state"] == "CALIBRATION_ACTIVE"
    assert rows["TE"]["research_state"] == "QUEUED"
    assert rows["C"]["archetype_count"] == 2
    assert portfolio["priority_card_coverage"] == 4


def test_portfolio_preserves_cfb27_native_defensive_positions():
    cards = [
        {"position": "MIKE", "archetype": "Field General"},
        {"position": "LEDG", "archetype": "Power Rusher"},
        {"position": "REDG", "archetype": "Speed Rusher"},
    ]
    portfolio = build_position_portfolio(cards)
    rows = {row["position"]: row for row in portfolio["priority_positions"]}

    assert rows["MIKE"]["cards"] == 1
    assert rows["LEDG"]["cards"] == 1
    assert rows["REDG"]["cards"] == 1
    assert "MLB" not in rows
    assert "LE" not in rows
    assert "RE" not in rows
    assert portfolio["priority_card_coverage"] == 3


def test_gm_ready_position_deploys_and_advances():
    portfolio = build_position_portfolio([{"position": "C", "archetype": "Agile"}])
    updated = apply_position_result(
        portfolio,
        "C",
        {
            "scored_cards": 100,
            "exact_match_rate": 0.96,
            "mean_absolute_error": 0.04,
            "maximum_absolute_error": 1,
        },
    )
    row = next(row for row in updated["priority_positions"] if row["position"] == "C")
    assert row["deployment"] == "GM_READY"
    assert row["research_state"] == "DEPLOY_AND_ADVANCE"


def test_gm_usable_position_does_not_get_stuck_chasing_perfection():
    portfolio = build_position_portfolio([{"position": "TE", "archetype": "Possession"}])
    updated = apply_position_result(
        portfolio,
        "TE",
        {
            "scored_cards": 100,
            "exact_match_rate": 0.92,
            "mean_absolute_error": 0.08,
            "maximum_absolute_error": 1,
        },
    )
    row = next(row for row in updated["priority_positions"] if row["position"] == "TE")
    assert row["deployment"] == "GM_USABLE"
    assert row["research_state"] == "DEPLOY_WITH_LIMITS_AND_ADVANCE"

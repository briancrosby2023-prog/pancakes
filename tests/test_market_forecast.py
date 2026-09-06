from operation_pancake.production.market_forecast import (
    buy_ceiling,
    buy_economics,
    forecast,
    intraday_profile,
    rank_opportunity,
    sell_decision,
)


def sale(hour: int, price: int, day: int = 1):
    return {"card_id": "x", "observation_type": "COMPLETED_SALE", "observed_price": price, "user_observed_at": f"2026-08-{day:02d}T{hour:02d}:00:00-07:00"}


def history():
    rows = []
    for day in range(1, 5):
        rows.extend([sale(10, 100000 + day * 1000, day), sale(18, 120000 + day * 1000, day), sale(22, 110000 + day * 1000, day)])
    return rows


def test_insufficient_history_stays_unknown():
    result = forecast([sale(10, 100000)], "2026-08-05T10:00:00-07:00", 60)
    assert result["status"] == "INSUFFICIENT DATA"
    assert result["forecast_price"] is None
    assert result["confidence"] == "NONE"


def test_intraday_effect_is_measured_not_hardcoded():
    profile = intraday_profile(history())
    assert profile["completed_sales"] == 12
    assert profile["hours"]["18"]["median"] > profile["hours"]["10"]["median"]


def test_supported_horizons_are_deterministic():
    first = forecast(history(), "2026-08-05T17:00:00-07:00", 60)
    second = forecast(history(), "2026-08-05T17:00:00-07:00", 60)
    assert first == second
    assert first["status"] == "FORECAST"
    assert first["time_of_day_effect"] > 0


def test_tax_and_buy_ceiling():
    economics = buy_economics(184000, 147000)
    assert economics["tax_rate"] == 0.10
    assert economics["net_proceeds"] == 165600
    assert economics["net_profit"] == 18600
    assert buy_ceiling(184000, 18000) == 147600


def test_absolute_profit_ranking_respects_probability_hold_and_confidence():
    assert rank_opportunity(30000, 0.8, 60, "MEDIUM") > rank_opportunity(5000, 0.9, 60, "MEDIUM")
    assert rank_opportunity(30000, None, 60, "MEDIUM") is None


def test_owned_card_sell_engine():
    result = sell_decision(170000, 184000, 147000, 120, "MEDIUM")
    assert result["action"] == "HOLD"
    assert result["expected_additional_profit_from_waiting"] > 0
    assert sell_decision(184000, 170000, 147000, 120, "MEDIUM")["action"] == "SELL NOW"

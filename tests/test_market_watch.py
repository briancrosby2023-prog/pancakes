from operation_pancake.production.market_watch import (
    alert_candidate,
    buy_window_evidence,
    forecast_watch,
    next_opera_inspection,
    prioritize,
    search_queue,
    watcher_alerts,
)

CARD = {
    "card_id": "card:x",
    "player_name": "Test Player",
    "position": "WR",
    "native_overall": 88,
    "program": "Test",
    "archetype": "Route Runner",
}
AS_OF = "2026-08-10T23:00:00-07:00"


def sale(day, hour, price, card_id="card:x"):
    stamp = f"2026-08-{day:02d}T{hour:02d}:00:00-07:00"
    return {
        "card_id": card_id,
        "observation_type": "COMPLETED_SALE",
        "observed_price": price,
        "value": price,
        "observed_at": stamp,
        "user_observed_at": stamp,
    }


def listing(price, card_id="card:x"):
    return {
        "card_id": card_id,
        "observation_type": "LOWEST_VISIBLE_LISTING",
        "observed_price": price,
        "value": price,
        "observed_at": "2026-08-10T22:59:00-07:00",
        "user_observed_at": "2026-08-10T22:59:00-07:00",
    }


def history(live=90000, card_id="card:x"):
    rows = []
    for day in range(1, 9):
        rows.extend(
            [
                sale(day, 10, 120000 + day * 500, card_id),
                sale(day, 18, 130000 + day * 500, card_id),
                sale(day, 22, 125000 + day * 500, card_id),
            ]
        )
    rows.append(listing(live, card_id))
    return rows


def test_forecast_wires_to_buy_ceiling_and_tax():
    result = forecast_watch(CARD, history(90000), AS_OF, minimum_net_profit=5000)
    assert result["forecast_state"] == "FORECAST"
    assert result["tax_rate"] == 0.10
    assert result["buy_ceiling"] == result["net_proceeds"] - 5000
    assert result["after_tax_net_profit"] == result["net_proceeds"] - 90000


def test_buy_crossing_and_alert_contract():
    result = forecast_watch(CARD, history(90000), AS_OF)
    assert result["action"] == "BUY"
    alert = alert_candidate(result)
    required = {
        "exact_identity",
        "observed_price",
        "threshold",
        "forecast_exit",
        "forecast_horizon_minutes",
        "after_tax_net_profit",
        "expected_hold_minutes",
        "exit_probability",
        "confidence",
        "liquidity",
        "risk_flags",
        "market_evidence_quality",
        "action",
    }
    assert required <= set(alert)
    assert alert["action"] == "BUY"


def test_watch_semantics_unchanged_above_ceiling():
    result = forecast_watch(CARD, history(200000), AS_OF)
    assert result["action"] == "WATCH"
    assert alert_candidate(result)["opportunity_type"] == "WATCH TARGET"


def test_insufficient_history_never_fabricates_forecast():
    result = forecast_watch(CARD, [sale(1, 10, 100000), listing(90000)], AS_OF)
    assert result["forecast_state"] == "INSUFFICIENT DATA"
    assert result["forecast_exit"] is None
    assert result["after_tax_net_profit"] is None
    assert result["priority_score"] is None
    assert result["action"] == "INSUFFICIENT DATA"


def test_static_watch_can_survive_without_model_forecast():
    result = forecast_watch(CARD, [listing(90000)], AS_OF, static_buy_ceiling=95000)
    assert result["action"] == "WATCH"
    assert result["forecast_exit"] is None


def test_listing_does_not_count_as_completed_sale():
    evidence = buy_window_evidence([listing(90000)], AS_OF)
    assert evidence["completed_sale_count"] == 0
    assert evidence["completed_sale_median"] is None


def test_measured_buy_window_dimensions_are_exposed():
    evidence = buy_window_evidence(history(), AS_OF)
    assert evidence["hour_of_day_samples"]
    assert evidence["day_of_week_samples"]
    assert evidence["price_dispersion"] is not None
    assert evidence["sale_velocity_per_day"] is not None


def test_event_deduplication_reuses_existing_watcher():
    result = forecast_watch(CARD, history(90000), AS_OF)
    first, state = watcher_alerts([result], {}, AS_OF)
    second, _ = watcher_alerts([result], state, AS_OF)
    assert len(first) == 1
    assert second == []


def test_prioritization_excludes_unknown_exit_probability():
    result = forecast_watch(CARD, history(90000), AS_OF)
    assert result["forecast_state"] == "FORECAST"
    assert result["exit_probability"] is None
    assert result["priority_score"] is None
    assert prioritize([result]) == []


def test_prioritization_accepts_supported_exit_probability():
    supported = forecast_watch(CARD, history(90000), "2026-08-08T23:00:00-07:00")
    assert supported["forecast_state"] == "FORECAST"
    assert supported["exit_probability"] is not None
    assert supported["priority_score"] is not None
    assert prioritize([supported]) == [supported]


def test_scientific_firewall_no_sales_means_no_buy():
    result = forecast_watch(CARD, [listing(1)], AS_OF)
    assert result["action"] == "INSUFFICIENT DATA"
    assert result["buy_ceiling"] is None


def test_search_queue_unknown_probability_stays_explore():
    sparse = {**CARD, "card_id": "card:y", "player_name": "Sparse"}
    inputs = [(sparse, [listing(30000, "card:y")]), (CARD, history(90000))]
    first = search_queue(inputs, AS_OF)
    second = search_queue(list(reversed(inputs)), AS_OF)
    assert first == second
    assert all(item["queue_class"] == "EXPLORE" for item in first)
    ready = next(item for item in first if item["exact_version"]["card_id"] == "card:x")
    assert ready["forecast_state"] == "FORECAST"
    assert ready["exit_probability"] is None


def test_search_queue_supported_probability_can_exploit():
    queue = search_queue([(CARD, history(90000))], "2026-08-08T23:00:00-07:00")
    assert queue[0]["queue_class"] == "EXPLOIT"
    assert queue[0]["exit_probability"] is not None


def test_queue_profit_objective_is_capital_neutral():
    cheap = {**CARD, "card_id": "card:a", "player_name": "Cheap"}
    large = {**CARD, "card_id": "card:b", "player_name": "Large"}
    queue = search_queue(
        [(large, history(250000, "card:b")), (cheap, history(30000, "card:a"))],
        AS_OF,
    )
    assert all("priority" in item for item in queue)
    assert {item["exact_version"]["card_id"] for item in queue} == {"card:a", "card:b"}


def test_explore_never_fabricates_economics_and_values_more_evidence():
    near = {**CARD, "card_id": "card:n", "player_name": "Near"}
    empty = {**CARD, "card_id": "card:e", "player_name": "Empty"}
    near_rows = [sale(day, 10, 100000 + day, "card:n") for day in range(1, 8)]
    queue = search_queue([(empty, []), (near, near_rows)], AS_OF)
    near_item = next(item for item in queue if item["exact_version"]["card_id"] == "card:n")
    empty_item = next(item for item in queue if item["exact_version"]["card_id"] == "card:e")
    assert near_item["queue_class"] == empty_item["queue_class"] == "EXPLORE"
    assert near_item["priority"] > empty_item["priority"]
    assert near_item["forecast_exit"] is None
    assert near_item["expected_net_profit"] is None
    assert near_item["buy_ceiling"] is None


def test_opera_contract_is_read_only_and_requests_only_current_gap():
    queue = search_queue([(CARD, history())], AS_OF)
    target = next_opera_inspection(queue)
    assert target["collector_mode"] == "READ ONLY"
    assert target["next_card_to_inspect"]["card_id"] == "card:x"
    assert target["what_evidence_is_needed"] == ["live listings"]

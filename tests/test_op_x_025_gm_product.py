from operation_pancake.production.gm import ACTIONS, manual_price_payload, optimize_budget, price_check_list


def test_action_vocabulary_separates_market_and_football_states():
    assert {"UPGRADE", "BUY", "WAIT", "PRICE CHECK REQUIRED", "UNRESOLVED IDENTITY"} <= ACTIONS


def test_budget_optimizer_can_choose_multiple_smaller_upgrades():
    candidates = [
        {"card_id": "premium", "net_cost": 100, "score_improvement": 5.0},
        {"card_id": "a", "net_cost": 45, "score_improvement": 3.0},
        {"card_id": "b", "net_cost": 45, "score_improvement": 3.0},
    ]
    result = optimize_budget(candidates, 100)
    assert [row["card_id"] for row in result["selected"]] == ["a", "b"]
    assert result["spent"] == 90
    assert result["action"] == "BUDGET UPGRADE"


def test_budget_optimizer_does_not_force_spending():
    result = optimize_budget([{"card_id": "bad", "net_cost": 50, "score_improvement": 0}], 100)
    assert result["selected"] == []
    assert result["spent"] == 0
    assert result["action"] == "KEEP"


def test_price_check_list_contains_card_identity():
    rows = [{"card_id": "x", "player_name": "Player", "position": "TE", "native_overall": 85,
             "program": "Core", "archetype": "Vertical Threat", "reason": "upgrade candidate"}]
    result = price_check_list(rows)
    assert result[0]["card_id"] == "x"
    assert result[0]["reason"] == "upgrade candidate"


def test_manual_price_entry_accepts_and_rejects_without_overwrite_semantics():
    result = manual_price_payload([
        {"canonical_card_id": "x", "observed_price": 10000},
        {"canonical_card_id": "y", "observed_price": -1},
    ], "2026-08-20T08:00:00-07:00")
    assert len(result["accepted"]) == 1
    assert len(result["rejected"]) == 1
    assert result["accepted"][0]["source"] == "USER_SUPPLIED"

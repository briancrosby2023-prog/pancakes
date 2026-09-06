import json
from pathlib import Path

from operation_pancake.research.cfb27_op_x_003 import build_op_x_003

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "data/research/cfb27_op_x_003"


def _load(name):
    return json.loads((RESEARCH / f"{name}.json").read_text(encoding="utf-8"))


def test_registry_and_acquisition_are_truthful() -> None:
    registry = _load("ea_historical_source_registry")
    assert {row["game"] for row in registry} >= {
        "CFB25",
        "CFB26",
        "CFB27",
        "Madden 19",
        "Madden 25",
        "Madden 27",
    }
    manifest = _load("acquisition_manifest")
    assert manifest["populations"]["CFB27_CUT"] == 8838
    assert manifest["populations"]["CFB25"] == manifest["populations"]["CFB26"] == 0
    assert manifest["rate_limit_bypassed"] is False


def test_cross_year_model_and_crosswalk_do_not_force_unknowns() -> None:
    model = _load("ea_cross_year_card_model")
    assert len(model) == 8838
    assert len({row["source_card_id"] for row in model}) == 8838
    assert all(row["game"] == "CFB27" and row["external_staged"] for row in model)
    assert all(row["height"] is None and row["weight"] is None for row in model)
    crosswalk = _load("attribute_crosswalk")
    assert {row["classification"] for row in crosswalk} >= {
        "EXACT",
        "RENAMED",
        "GAME_SPECIFIC",
        "UNRESOLVED",
    }


def test_market_observations_are_real_display_prices_not_sales() -> None:
    rows = _load("market_observations")
    assert len(rows) == 8
    assert all(
        row["price"] > 0 and row["observation_type"] == "PUBLIC_DISPLAY_PRICE" for row in rows
    )
    assert all(row["sale_price"] is None and row["historical"] is False for row in rows)
    premium = _load("market_premium")
    assert premium["status"] == "BLOCKED_BY_DATA"
    assert premium["forward_collection_active"] is True


def test_economy_creep_and_archetypes_are_descriptive() -> None:
    economy = _load("attribute_economy")
    assert economy["cross_year_status"].startswith("INSUFFICIENT")
    assert all(
        row["gameplay_value"] == "UNKNOWN"
        for position in economy["CFB27"].values()
        for row in position.values()
    )
    creep = _load("capability_creep_history")
    assert creep["cross_year_status"].startswith("BLOCKED")
    assert all(not row["causation_claimed"] for row in creep["CFB27"].values())
    assert _load("archetype_evolution")["forced_equivalence"] is False


def test_inheritance_moneyball_and_secondary_interfaces() -> None:
    inheritance = _load("formula_inheritance")
    assert inheritance["coefficients_assumed_equal"] is False
    assert inheritance["C"]["classification"] == "INSUFFICIENT_DATA"
    pools = _load("moneyball_candidates")
    assert set(pools) == {"TE", "CB", "MIKE", "EDGE", "OL", "HB", "WR", "QB", "SAFETY", "DT"}
    assert all(
        row["gameplay_confidence"] == "UNVALIDATED" and row["market_premium"] is None
        for pool in pools.values()
        for row in pool["candidates"]
    )
    secondary = _load("secondary_gates")
    assert len(secondary) >= 4
    assert "pc_evaluator_interface" in secondary


def test_freeze_validation_and_generation_are_deterministic() -> None:
    assert _load("freeze")["source_commit"] == "8b58b55"
    validation = _load("validation")
    assert validation == {
        "access_bypass": False,
        "canonical_changes": False,
        "conflicts_preserved": True,
        "forced_mappings": False,
        "guessed": False,
        "listing_as_sale": False,
        "market_fabrication": False,
        "unknown_zero_conversion": False,
    }
    assert build_op_x_003(ROOT) == build_op_x_003(ROOT)

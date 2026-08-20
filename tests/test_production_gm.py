from pathlib import Path

import pytest

from operation_pancake.production.engine import ProductionEngine, load_population
from operation_pancake.production.registry import build_model_registry

ROOT = Path(__file__).resolve().parents[1]


def test_registry_covers_all_named_position_families_and_preserves_controls():
    registry = build_model_registry(ROOT)
    assert set(registry["routes"]) == {
        "QB",
        "RB",
        "FB",
        "WR",
        "TE",
        "OT",
        "G",
        "C",
        "EDGE",
        "DT",
        "MIKE",
        "SAM",
        "CB",
        "S",
        "KP",
    }
    assert registry["controls"]["fallback_models"] == "forbidden"
    assert len(registry["models"]) == 18


def test_router_has_explicit_unsupported_and_diagnostic_outcomes():
    engine = ProductionEngine(build_model_registry(ROOT))
    assert engine.route("QB", "Pure Runner")["status"] == "UNSUPPORTED"
    assert engine.route("TE", "Pure Blocker")["status"] == "DIAGNOSTIC_ONLY"
    assert engine.route("FS", "Hybrid")["status"] == "ROUTED"


@pytest.mark.parametrize(
    ("position", "archetype"),
    [
        ("QB", "Pocket Passer"),
        ("HB", "Contact Seeker"),
        ("FB", "Utility"),
        ("WR", "Speedster"),
        ("TE", "Vertical Threat"),
        ("LT", "Pass Protector"),
        ("LG", "Agile"),
        ("C", "Agile"),
        ("RE", "Speed Rusher"),
        ("DT", "Pure Power"),
        ("MLB", "Lurker"),
        ("SAM", "Thumper"),
        ("CB", "Zone"),
        ("SS", "Hybrid"),
        ("K", "Accurate"),
    ],
)
def test_every_named_position_family_routes(position, archetype):
    assert (
        ProductionEngine(build_model_registry(ROOT)).route(position, archetype)["status"]
        == "ROUTED"
    )


def test_score_is_deterministic_and_partial_coverage_is_disclosed():
    engine = ProductionEngine(build_model_registry(ROOT))
    card = {
        "card_id": "x",
        "position": "HB",
        "archetype": "Contact Seeker",
        "native_ratings": {"SPD": 90, "TRK": 80},
    }
    first = engine.score(card)
    assert first == engine.score(card)
    assert first["score_status"] == "SCORED_PARTIAL"
    assert 0 < first["attribute_coverage"] < 1


def test_comparison_and_optional_value_never_invent_price():
    engine = ProductionEngine(build_model_registry(ROOT))
    low = {
        "card_id": "a",
        "position": "HB",
        "archetype": "Contact Seeker",
        "native_ratings": {"SPD": 70, "TRK": 70},
    }
    high = {
        "card_id": "b",
        "position": "HB",
        "archetype": "Contact Seeker",
        "native_ratings": {"SPD": 90, "TRK": 90},
    }
    assert engine.compare(low, high)["value"] is None
    priced = engine.compare(low, high, 1000)
    assert priced["classification"] == "UPGRADE"
    assert priced["value"]["price_source"] == "caller-supplied"


def test_canonical_population_is_complete_and_identity_unique():
    population = load_population(ROOT)
    assert len(population) == 8838
    assert len({row["card_id"] for row in population}) == 8838


def test_registry_schema_exposes_capability_validation_and_provenance():
    for model in build_model_registry(ROOT)["models"]:
        assert model["model_type"]
        assert model["capabilities"]["displayed_overall_prediction"] is False
        assert "validation" in model and model["evidence_paths"]

from operation_pancake.research.cfb27_e15_multi_family import (
    analyze_position,
    build_multi_family_matrix,
)


def _cell(position, archetype, ovr, driver, noise, start):
    return [
        {
            "external_card_id": f"{position}-{archetype}-{ovr}-{i}",
            "position": position,
            "archetype": archetype,
            "overall": ovr,
            "displayed_ratings": {"DRV": driver + i % 2, "NOISE": noise + i * 5, "FLAT": start},
        }
        for i in range(4)
    ]


def test_same_ovr_spread_and_adjacent_boundary_separate_signals():
    cards = []
    cards += _cell("TE", "Test", 80, 70, 40, 50)
    cards += _cell("TE", "Test", 81, 75, 40, 50)
    cards += _cell("TE", "Test", 82, 80, 40, 50)
    cards += _cell("TE", "Test", 83, 85, 40, 50)
    result = analyze_position(cards, "TE")
    by_rating = {row["rating"]: row for row in result["ratings"]}
    assert by_rating["DRV"]["positive_boundary_share"] == 1.0
    assert by_rating["DRV"]["median_adjacent_delta"] == 5
    assert by_rating["NOISE"]["median_same_ovr_spread"] == 15
    assert "DRV" in {row["rating"] for row in result["candidate_drivers"]}
    assert "NOISE" in {row["rating"] for row in result["likely_non_drivers"]}


def test_shared_driver_is_detected_across_archetypes():
    cards = []
    for archetype in ("A", "B"):
        for ovr, driver in ((80, 70), (81, 75), (82, 80), (83, 85)):
            cards += _cell("CB", archetype, ovr, driver, 40, 50)
    result = analyze_position(cards, "CB")
    shared = {row["rating"] for row in result["shared_component_candidates"]}
    assert "DRV" in shared


def test_opposite_archetype_direction_is_flagged():
    cards = []
    for ovr, driver in ((80, 70), (81, 75), (82, 80), (83, 85)):
        cards += _cell("DT", "Power", ovr, driver, 40, 50)
    for ovr, driver in ((80, 85), (81, 80), (82, 75), (83, 70)):
        cards += _cell("DT", "Speed", ovr, driver, 40, 50)
    result = analyze_position(cards, "DT")
    dependent = {row["rating"] for row in result["archetype_dependent_candidates"]}
    assert "DRV" in dependent


def test_matrix_covers_three_scientific_families():
    matrix = build_multi_family_matrix([])
    assert set(matrix["families"]) == {"BLOCKING", "COVERAGE", "FRONT_SEVEN"}
    assert matrix["prediction_accuracy_measured"] is False

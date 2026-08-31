from operation_pancake.ocr_team_app import REAL_TEAM_MANAGER_REGIONS
from operation_pancake.team_import import OCRObservation, extract_structured


def _obs(text, x, y):
    return OCRObservation(text, (x - .002, y - .004, x + .002, y + .004), .95)


def test_real_offense_layout_maps_nameplates_not_left_menu():
    observations = [
        _obs("Carson", .530, .420), _obs("HINZMAN", .548, .435), _obs("87", .575, .420),
        _obs("Dante", .642, .720), _obs("MOORE", .660, .735), _obs("88", .685, .720),
        _obs("OVR", .10, .30), _obs("Improvements", .12, .34),
    ]
    view, found, _ = extract_structured("offense.jpg", observations, REAL_TEAM_MANAGER_REGIONS, view="OFFENSE")
    by_slot = {c.slot: c for c in found}
    assert view == "OFFENSE"
    assert by_slot["C1"].raw_player_name == "Carson HINZMAN"
    assert by_slot["C1"].displayed_ovr == 87
    assert by_slot["QB1"].raw_player_name == "Dante MOORE"
    assert by_slot["QB1"].displayed_ovr == 88
    assert "LT1" not in by_slot


def test_real_defense_special_teams_and_specialists_layouts():
    cases = [
        ("DEFENSE", "MIKE2", [_obs("Junior", .610, .442), _obs("SEAU", .628, .454), _obs("87", .650, .442)]),
        ("SPECIAL TEAMS", "K1", [_obs("Jason", .452, .449), _obs("ELAM", .470, .463), _obs("82", .492, .449)]),
        ("SPECIALISTS", "SLCB1", [_obs("Graceson", .758, .720), _obs("LITTLETON", .778, .738), _obs("89", .804, .720)]),
    ]
    for view, slot, observations in cases:
        _, found, _ = extract_structured(f"{view}.jpg", observations, REAL_TEAM_MANAGER_REGIONS, view=view)
        by_slot = {c.slot: c for c in found}
        assert slot in by_slot
        assert by_slot[slot].displayed_ovr is not None
        assert by_slot[slot].raw_player_name


def test_measured_regions_exclude_left_navigation():
    for regions in REAL_TEAM_MANAGER_REGIONS.values():
        assert all(region.box[0] > .20 for region in regions)

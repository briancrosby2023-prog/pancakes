from operation_pancake.team_import import OCRObservation, extract_structured
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS


def _obs(text, x, y, confidence=.95):
    return OCRObservation(text, (x - .002, y - .004, x + .002, y + .004), confidence)


def _slot(view, observations, slot):
    _, found, _ = extract_structured("real.jpg", observations, REAL_TEAM_MANAGER_SLOT_REGIONS, view=view)
    return {c.slot: c for c in found}[slot]


def test_starter_name_and_ovr_use_independent_subregions():
    c = _slot("OFFENSE", [
        _obs("Carson", .530, .420), _obs("HINZMAN", .548, .435),
        _obs("87", .575, .420), _obs("80", .530, .420),
    ], "C1")
    assert c.raw_player_name == "Carson HINZMAN"
    assert c.displayed_ovr == 87
    assert "starter-name-subregion" in c.provenance
    assert "starter-ovr-subregion" in c.provenance


def test_broad_container_garbage_is_not_promoted_to_starter():
    c = _slot("SPECIAL TEAMS", [
        _obs("Ex", .450, .500), _obs("od", .468, .500),
        _obs("wost", .468, .520), _obs("80", .492, .449),
    ], "K1")
    assert c.raw_player_name is None
    assert c.displayed_ovr == 80
    assert "starter-name:unresolved" in c.provenance


def test_low_confidence_non_player_fragment_fails_closed():
    c = _slot("SPECIAL TEAMS", [_obs("flee", .680, .449, .18), _obs("ol", .695, .463, .20)], "KR1")
    assert c.raw_player_name is None


def test_neighboring_slot_text_cannot_contaminate_slot():
    c = _slot("SPECIAL TEAMS", [
        _obs("Jason", .452, .449), _obs("ELAM", .470, .463), _obs("82", .492, .449),
    ], "KOS1")
    assert c.raw_player_name is None
    assert c.displayed_ovr is None


def test_sidebar_and_menu_text_cannot_become_player():
    c = _slot("DEFENSE", [_obs("Improvements", .12, .34), _obs("Manage", .15, .40)], "MIKE1")
    assert c.raw_player_name is None


def test_backups_come_only_from_backup_subregions():
    region = next(r for r in REAL_TEAM_MANAGER_SLOT_REGIONS["SPECIAL TEAMS"] if r.slot == "K1")
    b = region.backup_boxes[0]
    x, y = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    c = _slot("SPECIAL TEAMS", [
        _obs("Jason", .452, .449), _obs("ELAM", .470, .463), _obs("82", .492, .449),
        _obs("Backup", x - .01, y), _obs("PLAYER", x + .01, y),
        _obs("ROBINSON", .700, .560),
    ], "K1")
    assert all(b["player_name"] != "ROBINSON" for b in c.backups)


def test_all_four_views_define_explicit_subregions_for_every_slot():
    assert set(REAL_TEAM_MANAGER_SLOT_REGIONS) == {"OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS"}
    for regions in REAL_TEAM_MANAGER_SLOT_REGIONS.values():
        for region in regions:
            assert region.starter_name_box is not None
            assert region.starter_ovr_box is not None
            assert region.backup_boxes

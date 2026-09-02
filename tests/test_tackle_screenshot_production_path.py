from __future__ import annotations

from PIL import Image

from operation_pancake.tackle_screenshot_recognition import recognize_tackle_candidate
from operation_pancake.tackle_visual_pilot import IndexedTackle, TackleCard, fingerprint
from operation_pancake.team_import import Candidate
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS


def _card(external_id, name, position, overall, color, program="Phenoms"):
    card = TackleCard(
        external_id,
        f"card:{external_id}",
        name,
        position,
        overall,
        program,
        "CFB27",
        "https://example.invalid/card.png",
        None,
        None,
        None,
        None,
        (name.casefold().replace(" ", ""), name.split()[-1].casefold()),
    )
    return IndexedTackle(
        card, fingerprint(Image.new("RGB", (240, 321), color)), external_id, None
    )


def _region(slot):
    return next(
        value for value in REAL_TEAM_MANAGER_SLOT_REGIONS["OFFENSE"] if value.slot == slot
    )


def test_real_uploaded_pixel_path_emits_complete_tackle_diagnostics(tmp_path):
    path = tmp_path / "offense.png"
    Image.new("RGB", (1000, 1000), "red").save(path)
    index = [
        _card("expected", "Alpha Tackle", "LT", 80, "red"),
        _card("other", "Beta Tackle", "LT", 80, "blue"),
    ]
    candidate = Candidate(
        "cand-1",
        "OFFENSE",
        "LT1",
        "Alpha Tackle",
        81,
        "LT",
        match_diagnostics={"observed_name": "Alpha Tackle"},
    )
    diagnostics = recognize_tackle_candidate(path, candidate, _region("LT1"), {"crops": {}}, index)
    starter = diagnostics[0]
    assert candidate.canonical_card_id == "card:expected"
    assert candidate.match_status == "MATCHED"
    assert starter["source_screenshot"] == str(path)
    assert starter["slot"] == "LT1"
    assert starter["deterministic_position"] == "LT"
    assert starter["candidate_pool_size"] == 2
    assert starter["starter_backup_index"] == 0
    assert starter["crop_dimensions"] == [96, 249]
    assert starter["ocr_name_observation"] == "Alpha Tackle"
    assert starter["displayed_ovr_observation"] == 81
    assert starter["top_visual_candidates"][0]["external_id"] == "expected"
    assert starter["ovr_compatibility"] == 0.8
    assert starter["decision"] == "ACCEPTED"
    assert starter["decision_reason"]
    assert candidate.match_diagnostics["real_uploaded_pixels"] is True


def test_ambiguous_real_crop_fails_closed_without_weakening_margin(tmp_path):
    path = tmp_path / "offense.png"
    Image.new("RGB", (1000, 1000), "red").save(path)
    index = [
        _card("one", "Same Player", "RT", 80, "red"),
        _card("two", "Same Player", "RT", 80, "red"),
    ]
    candidate = Candidate(
        "cand-1",
        "OFFENSE",
        "RT1",
        "Same Player",
        81,
        "RT",
        match_diagnostics={"observed_name": "Same Player"},
    )
    diagnostics = recognize_tackle_candidate(path, candidate, _region("RT1"), {"crops": {}}, index)
    assert candidate.canonical_card_id is None
    assert candidate.match_status == "UNRESOLVED"
    assert diagnostics[0]["ambiguity_margin"] == 0.0
    assert diagnostics[0]["decision"] == "UNRESOLVED"
    assert diagnostics[0]["decision_reason"] == "same-player-card-ambiguity"


def test_backup_exact_name_and_plus_one_display_boost_resolves_native_card(tmp_path):
    path = tmp_path / "offense.png"
    Image.new("RGB", (1000, 1000), "gray").save(path)
    index = [
        _card("phenoms", "Juan Gaston", "RT", 80, "red"),
        _card("core", "Juan Gaston", "RT", 75, "gray", "Core/Platinum"),
        _card("other", "Other Tackle", "RT", 81, "gray"),
    ]
    candidate = Candidate("cand-1", "OFFENSE", "RT1", "Other Tackle", 81, "RT")
    candidate.backups = [{
        "player_name": "Juan Gaston", "raw_player_name": "Juan Gaston",
        "displayed_ovr": 81, "match_status": "UNRESOLVED"
    }]
    slot_crop = {"crops": {"backup_1": {"raw_text": "81 Juan Gaston"}}}
    diagnostics = recognize_tackle_candidate(path, candidate, _region("RT1"), slot_crop, index)
    backup = diagnostics[1]
    assert candidate.backups[0]["canonical_card_id"] == "card:phenoms"
    assert candidate.backups[0]["program"] == "Phenoms"
    assert backup["decision"] == "ACCEPTED"
    assert backup["decision_reason"] == "exact-full-name+boost-tolerant-ovr"


def test_backup_unique_exact_full_name_survives_shallow_visual_mismatch(tmp_path):
    path = tmp_path / "offense.png"
    Image.new("RGB", (1000, 1000), "gray").save(path)
    index = [
        _card("petty", "Josh Petty", "LT", 80, "red"),
        _card("visual", "Different Tackle", "LT", 80, "gray"),
    ]
    candidate = Candidate("cand-1", "OFFENSE", "LT1", "Different Tackle", 80, "LT")
    candidate.backups = [{
        "player_name": "Josh Petty", "raw_player_name": "Josh Petty",
        "displayed_ovr": None, "match_status": "UNRESOLVED"
    }]
    slot_crop = {"crops": {"backup_1": {"raw_text": "Josh Petty"}}}
    diagnostics = recognize_tackle_candidate(path, candidate, _region("LT1"), slot_crop, index)
    backup = diagnostics[1]
    assert candidate.backups[0]["canonical_card_id"] == "card:petty"
    assert backup["decision"] == "ACCEPTED"
    assert backup["decision_reason"] == "unique-exact-full-name-in-position-pool"


def test_wrong_position_exact_name_still_fails_closed(tmp_path):
    path = tmp_path / "offense.png"
    Image.new("RGB", (1000, 1000), "gray").save(path)
    index = [_card("wrong", "Josh Petty", "RT", 80, "gray")]
    candidate = Candidate(
        "cand-1", "OFFENSE", "LT1", "Josh Petty", 80, "LT",
        match_diagnostics={"observed_name": "Josh Petty"},
    )
    diagnostics = recognize_tackle_candidate(path, candidate, _region("LT1"), {"crops": {}}, index)
    assert candidate.canonical_card_id is None
    assert candidate.match_status == "UNRESOLVED"
    assert diagnostics[0]["candidate_pool_size"] == 0
    assert diagnostics[0]["decision"] == "UNRESOLVED"

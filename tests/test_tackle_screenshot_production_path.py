from __future__ import annotations

from PIL import Image

from operation_pancake.tackle_screenshot_recognition import recognize_tackle_candidate
from operation_pancake.tackle_visual_pilot import IndexedTackle, TackleCard, fingerprint
from operation_pancake.team_import import Candidate
from operation_pancake.team_slot_extraction import REAL_TEAM_MANAGER_SLOT_REGIONS


def _card(external_id, name, position, overall, color):
    card = TackleCard(
        external_id,
        f"card:{external_id}",
        name,
        position,
        overall,
        "Phenoms",
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
    region = next(
        value for value in REAL_TEAM_MANAGER_SLOT_REGIONS["OFFENSE"] if value.slot == "LT1"
    )
    diagnostics = recognize_tackle_candidate(path, candidate, region, {"crops": {}}, index)
    starter = diagnostics[0]
    assert candidate.canonical_card_id == "card:expected"
    assert candidate.match_status == "MATCHED"
    assert starter["slot"] == "LT1"
    assert starter["starter_backup_index"] == 0
    assert starter["crop_dimensions"] == [96, 249]
    assert starter["ocr_name_observation"] == "Alpha Tackle"
    assert starter["displayed_ovr_observation"] == 81
    assert starter["top_visual_candidates"][0]["external_id"] == "expected"
    assert starter["ovr_compatibility"] == 0.8
    assert starter["decision"] == "ACCEPTED"
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
    region = next(
        value for value in REAL_TEAM_MANAGER_SLOT_REGIONS["OFFENSE"] if value.slot == "RT1"
    )
    diagnostics = recognize_tackle_candidate(path, candidate, region, {"crops": {}}, index)
    assert candidate.canonical_card_id is None
    assert candidate.match_status == "UNRESOLVED"
    assert diagnostics[0]["ambiguity_margin"] == 0.0
    assert diagnostics[0]["decision"] == "UNRESOLVED"

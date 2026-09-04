from operation_pancake import ocr_team_app_visual
from operation_pancake.team_import import Candidate
from operation_pancake.team_lineup_visual import render_lineup


def test_visual_lineup_has_four_tabs_and_deterministic_offense_topology():
    candidates = [
        Candidate("lt", "OFFENSE", "LT1", "Left Tackle", 86, "LT"),
        Candidate(
            "qb",
            "OFFENSE",
            "QB1",
            "Quarter Back",
            88,
            "QB",
            backups=[{"player_name": "Backup QB", "displayed_ovr": 82}],
        ),
    ]
    page = render_lineup(candidates, {})
    for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS"):
        assert f">{view}</button>" in page
    offense_line = ["LT1", "LG1", "C1", "RG1", "RT1", "TE1"]
    assert [page.index(f'data-slot="{slot}"') for slot in offense_line] == sorted(
        page.index(f'data-slot="{slot}"') for slot in offense_line
    )
    backfield = ["WR1", "WR3", "HB1", "QB1", "FB1", "WR2"]
    assert [page.index(f'data-slot="{slot}"') for slot in backfield] == sorted(
        page.index(f'data-slot="{slot}"') for slot in backfield
    )
    assert "Quarter Back" in page and "88" in page and "Backup QB" in page and "82" in page


def test_visual_lineup_does_not_render_identity_adjudication_controls():
    lt = Candidate("lt", "OFFENSE", "LT1", None, None, "LT")
    lg = Candidate("lg", "OFFENSE", "LG1", None, 85, "LG")
    rt = Candidate(
        "rt",
        "OFFENSE",
        "RT1",
        "Cason Henry",
        85,
        "RT",
        canonical_card_id="rt-cason",
        match_status="MATCHED",
    )
    cards = {"rt-cason": {"player_name": "Cason Henry", "native_overall": 85, "program": "Phenoms"}}
    page = render_lineup([lt, lg, rt], cards)
    assert "WHO IS THIS PLAYER?" not in page
    assert "SEARCH CFB27" not in page
    assert 'player_name__lt' not in page
    assert 'player_name__lg' not in page
    assert 'name="card__lg"' not in page
    assert 'name="card__rt"' not in page
    assert page.count("PLAYER UNRESOLVED") == 2
    assert "UNMATCHED — enter player name" not in page
    assert "Cason Henry · CARD OVR 85 · Phenoms" in page


def test_visual_runtime_preserves_patch6_and_limits_evidence_to_current_batch():
    src = open(ocr_team_app_visual.__file__, encoding="utf-8").read()
    assert "patch6.install_runtime()" in src
    assert "current = state.screenshots[-4:]" in src
    assert "Current batch evidence" in src
    assert "Image evidence" not in src

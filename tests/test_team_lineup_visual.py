from operation_pancake.team_import import Candidate
from operation_pancake.team_lineup_visual import render_lineup
from operation_pancake import ocr_team_app_visual


def test_visual_lineup_has_four_tabs_and_deterministic_offense_topology():
    candidates = [Candidate("lt", "OFFENSE", "LT1", "Left Tackle", 86, "LT"), Candidate("qb", "OFFENSE", "QB1", "Quarter Back", 88, "QB", backups=[{"player_name": "Backup QB", "displayed_ovr": 82}])]
    page = render_lineup(candidates, {})
    for view in ("OFFENSE", "DEFENSE", "SPECIAL TEAMS", "SPECIALISTS"):
        assert f">{view}</button>" in page
    assert page.index('data-slot="LT1"') < page.index('data-slot="LG1"') < page.index('data-slot="C1"') < page.index('data-slot="RG1"') < page.index('data-slot="RT1"') < page.index('data-slot="TE1"')
    assert page.index('data-slot="WR1"') < page.index('data-slot="WR3"') < page.index('data-slot="HB1"') < page.index('data-slot="QB1"') < page.index('data-slot="FB1"') < page.index('data-slot="WR2"')
    assert "Quarter Back" in page and "88" in page and "Backup QB" in page and "82" in page


def test_visual_lineup_keeps_name_search_bounded_to_unresolved_tackles():
    lt = Candidate("lt", "OFFENSE", "LT1", None, None, "LT")
    lg = Candidate("lg", "OFFENSE", "LG1", None, 85, "LG")
    rt = Candidate("rt", "OFFENSE", "RT1", "Cason Henry", 85, "RT", canonical_card_id="rt-cason", match_status="MATCHED")
    cards = {"rt-cason": {"player_name": "Cason Henry", "native_overall": 85, "program": "Phenoms"}}
    page = render_lineup([lt, lg, rt], cards)
    assert page.count("WHO IS THIS PLAYER?") == 1
    assert page.count("SEARCH CFB27") == 1
    assert 'player_name__lt' in page
    assert 'player_name__lg' not in page
    assert 'name="card__lg"' not in page
    assert 'name="card__rt"' not in page
    assert "UNMATCHED — enter player name" not in page
    assert "Cason Henry · 85 · Phenoms" in page


def test_visual_runtime_preserves_patch6_and_limits_evidence_to_current_batch():
    src = open(ocr_team_app_visual.__file__, encoding="utf-8").read()
    assert "patch6.install_runtime()" in src
    assert "current = state.screenshots[-4:]" in src
    assert "Current batch evidence" in src
    assert "Image evidence" not in src
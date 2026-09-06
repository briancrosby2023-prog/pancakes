from operation_pancake.c3po_card_version import C3POCardObservation
from operation_pancake.c3po_roster import C3POPlayer, C3PORoster, observation_fingerprint
from operation_pancake.c3po_roster_page import render_c3po_roster


def test_google_known_program_drives_art_without_overwriting_screenshot_ovr():
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
    roster = C3PORoster((player,), "google-gemini", "gemini-3.7-flash")
    fingerprint = observation_fingerprint(player, 0)
    programs = {
        fingerprint: C3POCardObservation(
            fingerprint=fingerprint,
            player_name="Luke Montgomery",
            displayed_ovr=87,
            program="Season 2",
            state="IDENTIFIED",
        )
    }
    page = render_c3po_roster(roster, programs)
    assert 'class="feature-art"' in page
    assert "202019231.png" in page
    assert '<span class="choice-ovr">87</span>' in page
    assert "80 OVR" not in page
    assert "88 OVR" not in page


def test_unknown_art_keeps_placeholder_instead_of_substituting_a_card():
    player = C3POPlayer("OFFENSE", "LG 1", "Unknown Player", 87)
    roster = C3PORoster((player,), "google-gemini", "gemini-3.7-flash")
    fingerprint = observation_fingerprint(player, 0)
    programs = {fingerprint: C3POCardObservation(fingerprint=fingerprint, player_name="Unknown Player", displayed_ovr=87, program="Season 2", state="IDENTIFIED")}
    page = render_c3po_roster(roster, programs)
    assert 'class="feature-art"' not in page
    assert '<span class="choice-ovr">87</span>' in page


def test_long_player_name_gets_compact_name_style_without_changing_ovr():
    player = C3POPlayer("OFFENSE", "TE 3", "Martellus Bennett", 82)
    roster = C3PORoster((player,), "google-gemini", "gemini-3.7-flash")
    page = render_c3po_roster(roster)
    assert '<strong class="choice-name choice-name-long">Martellus Bennett</strong>' in page
    assert '<span class="choice-ovr">82</span>' in page


def test_position_groups_stretch_to_align_each_six_column_lineup_row():
    roster = C3PORoster((C3POPlayer("OFFENSE", "LT 1", "Starter", 87), C3POPlayer("OFFENSE", "TE 1", "Tight End One", 86), C3POPlayer("OFFENSE", "TE 2", "Tight End Two", 83), C3POPlayer("OFFENSE", "TE 3", "Tight End Three", 82), C3POPlayer("OFFENSE", "WR 1", "Receiver", 87)), "google-gemini", "gemini-3.7-flash")
    page = render_c3po_roster(roster)
    assert "align-items:stretch" in page
    assert "align-items:start" not in page


def test_special_teams_uses_one_six_position_row_in_cfbfan_order():
    roster = C3PORoster((C3POPlayer("SPECIAL TEAMS", "P 1", "Punter", 82), C3POPlayer("SPECIAL TEAMS", "K 1", "Kicker", 83), C3POPlayer("SPECIAL TEAMS", "KR 1", "Kick Returner", 87), C3POPlayer("SPECIAL TEAMS", "PR 1", "Punt Returner", 86), C3POPlayer("SPECIAL TEAMS", "LS 1", "Long Snapper", 85), C3POPlayer("SPECIAL TEAMS", "KOS 1", "Kickoff Specialist", 84)), "google-gemini", "gemini-3.7-flash")
    page = render_c3po_roster(roster)
    special = page[page.index('id="special-teams"'):page.index('id="specialists"')]
    assert special.index("<h3>P</h3>") < special.index("<h3>K</h3>") < special.index("<h3>KR</h3>") < special.index("<h3>PR</h3>") < special.index("<h3>LS</h3>") < special.index("<h3>KOS</h3>")


def test_defense_splits_mike_and_cb_into_two_six_position_rows():
    roster = C3PORoster(
        (
            C3POPlayer("DEFENSE", "FS 1", "Free Safety", 89),
            C3POPlayer("DEFENSE", "WILL 1", "Will", 87),
            C3POPlayer("DEFENSE", "MIKE 1", "Mike One", 89),
            C3POPlayer("DEFENSE", "MIKE 2", "Mike Two", 86),
            C3POPlayer("DEFENSE", "SAM 1", "Sam", 88),
            C3POPlayer("DEFENSE", "SS 1", "Strong Safety", 87),
            C3POPlayer("DEFENSE", "CB 1", "Corner One", 87),
            C3POPlayer("DEFENSE", "CB 2", "Corner Two", 86),
            C3POPlayer("DEFENSE", "CB 3", "Corner Three", 85),
            C3POPlayer("DEFENSE", "REDG 1", "Right Edge", 86),
            C3POPlayer("DEFENSE", "DT 1", "Tackle", 86),
            C3POPlayer("DEFENSE", "LEDG 1", "Left Edge", 86),
        ),
        "google-gemini",
        "gemini-3.7-flash",
    )
    page = render_c3po_roster(roster)
    defense = page[page.index('id="defense"'):page.index('id="special-teams"')]
    headings = ["FS", "WILL", "MIKE1", "MIKE2", "SAM", "SS", "CB1", "CB2", "REDG", "DT", "LEDG", "CB3"]
    positions = [defense.index(f"<h3>{heading}</h3>") for heading in headings]
    assert positions == sorted(positions)

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
    programs = {
        fingerprint: C3POCardObservation(
            fingerprint=fingerprint,
            player_name="Unknown Player",
            displayed_ovr=87,
            program="Season 2",
            state="IDENTIFIED",
        )
    }

    page = render_c3po_roster(roster, programs)

    assert 'class="feature-art"' not in page
    assert '<span class="choice-ovr">87</span>' in page

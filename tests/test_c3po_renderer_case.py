from operation_pancake.c3po_card_version import C3POCardObservation
from operation_pancake.c3po_roster import C3POPlayer, C3PORoster, observation_fingerprint
from operation_pancake.c3po_roster_page import render_c3po_roster


def test_renderer_accepts_c3po_name_case_change_for_exact_card():
    player = C3POPlayer("OFFENSE", "LT 1", "Samson OKUNLOLA", 84)
    roster = C3PORoster((player,), "fake", "fake")
    fingerprint = observation_fingerprint(player, 0)
    card = C3POCardObservation(
        fingerprint, "SAMSON OKUNLOLA", 84, "Phenoms", "IDENTIFIED",
        card_id="card-samson", art_asset="data/production/card_art/card-samson.png",
    )
    html = render_c3po_roster(roster, {fingerprint: card})
    assert "CARD NOT READ" not in html
    assert "Phenoms" in html
    assert "/card-art/card-samson.png" in html

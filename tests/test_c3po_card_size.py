from operation_pancake.c3po_roster import C3POPlayer, C3PORoster
from operation_pancake.c3po_roster_page import render_c3po_roster


def test_desktop_cards_use_reference_geometry_without_overflow():
    roster = C3PORoster(
        tuple(C3POPlayer("OFFENSE", f"X{i}", f"Player {i}", 85) for i in range(6)),
        "fake",
        "fake",
    )

    page = render_c3po_roster(roster)

    assert "grid-template-columns:repeat(6,minmax(0,1fr))" in page
    assert ".feature-card{aspect-ratio:254/356" in page
    assert "max-width:160px" in page
    assert "object-fit:contain" in page
    assert ".position-group{min-width:0;overflow:hidden}" in page
    assert ".player-list{display:grid" in page

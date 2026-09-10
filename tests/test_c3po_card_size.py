from operation_pancake.c3po_roster import C3POPlayer, C3PORoster
from operation_pancake.c3po_roster_page import render_c3po_roster


def test_desktop_cards_use_reference_geometry_without_overflow():
    roster = C3PORoster(
        (C3POPlayer("OFFENSE", "LT 1", "Player 0", 84),)
        + tuple(
            C3POPlayer("OFFENSE", f"X{i}", f"Player {i}", 85)
            for i in range(1, 6)
        ),
        "fake",
        "fake",
    )

    page = render_c3po_roster(roster)

    assert "grid-template-columns:repeat(6,minmax(0,1fr))" in page
    assert ".feature-card{aspect-ratio:280/374" in page
    assert ".position-group{min-width:0;overflow:hidden;padding:0 8px}" in page
    assert ".feature-card{aspect-ratio:280/374;width:100%;margin:0" in page
    assert ".player-list{width:100%;margin:7px 0 0" in page
    assert "object-fit:contain" in page
    assert 'class="feature-rating"><strong>84</strong><span>LT</span></div>' in page
    assert ".position-group{min-width:0;overflow:hidden}" not in page
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" not in page
    assert ".feature-card{height:165px}" not in page
    assert ".feature-card{height:155px}" not in page
    assert ".feature-card{height:145px}" not in page

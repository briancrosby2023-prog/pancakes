from operation_pancake.acquisition.cfb_fan import parse_player_page


def _page(position: str) -> str:
    return f'''<html><head><title>Test Player 85 OVR - College Football 27</title></head>
    <body><h1 class="player-header__name">Test Player<span class="player-header__ovr">85</span></h1>
    <div class="player-header__meta"><a href="/players/?positions={position}">{position}</a>
    <a href="/players/?program_id=1">Test Program</a></div>
    <div>General</div><span class="rating__label">SPD</span><span class="rating__value">85</span>
    <div class="text-lighter-gray">Team</div><div>Test School</div>
    <div class="text-lighter-gray">Archetype</div><div>Test Archetype - {position}</div>
    <div class="text-lighter-gray">Date Added</div><div>08/18/2026</div>
    </body></html>'''


def test_cfb_fan_html_parser_preserves_cfb27_native_defensive_positions():
    for position in ("SAM", "MIKE", "WILL", "LEDG", "REDG", "DT", "CB", "FS", "SS"):
        card = parse_player_page(
            _page(position),
            "https://cfb.fan/players/123-test-player/27-456/",
            "2026-08-18T00:00:00Z",
            "fixture.html",
        )
        assert card.position == position
        assert card.metadata == {}

import threading
import urllib.request
from http.server import ThreadingHTTPServer

from operation_pancake import c3po_roster_app
from operation_pancake.c3po_card_version import (
    C3POCardObservation,
    C3POCardObservationStore,
)
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterService,
    C3PORosterStore,
    observation_fingerprint,
)
from operation_pancake.c3po_roster_page import render_c3po_roster

CARD_ID = "card:90a8312982d3c1270826"
ART_FILENAME = "card-90a8312982d3c1270826.png"
ART_ASSET = f"data/production/card_art/{ART_FILENAME}"
ART_URL = f"/card-art/{ART_FILENAME}"


def _roster(*players: C3POPlayer) -> C3PORoster:
    return C3PORoster(players, "google-gemini", "gemini-3.7-flash")


def _cards(*, program="Season 2", asset=ART_ASSET):
    return (
        {
            "card_id": CARD_ID,
            "player_name": "Luke Montgomery",
            "program": program,
            "card_art_asset": asset,
        },
    )


def test_exact_card_resolution_persists_local_art_and_renders_at_lg(tmp_path):
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
    fingerprint = observation_fingerprint(player, 0)
    store = C3POCardObservationStore(tmp_path / "c3po-programs.json")
    store.save(
        {
            fingerprint: C3POCardObservation(
                fingerprint=fingerprint,
                player_name="Luke Montgomery",
                displayed_ovr=87,
                program="Season 2",
                state="IDENTIFIED",
                card_id=CARD_ID,
                art_asset=ART_ASSET,
            )
        }
    )

    programs = store.load()
    page = render_c3po_roster(_roster(player), programs)
    lg_start = page.index("<h3>LG</h3>")
    lg_group = page[lg_start : page.index("</section>", lg_start)]

    assert programs[fingerprint].card_id == CARD_ID
    assert programs[fingerprint].art_asset == ART_ASSET
    assert f'src="{ART_URL}"' in lg_group
    assert 'data-slot="LG 1"' in lg_group
    assert "Season 2" in lg_group
    assert '<span class="choice-ovr">87</span>' in lg_group


def test_exact_card_resolution_carries_local_asset_through_service(tmp_path):
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87, program="Season 2")
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=None,
        enrichment_cards=_cards(),
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
    )

    assert service.persist_inline_programs(_roster(player)) == 1
    stored = service.card_observation_store.load()
    observation = stored[observation_fingerprint(player, 0)]
    assert observation.card_id == CARD_ID
    assert observation.art_asset == ART_ASSET
    assert ART_URL in service.render_html(_roster(player))


def test_rendering_survives_acquisition_source_disappearance(tmp_path):
    source = tmp_path / "acquisition.png"
    source.write_bytes(b"acquisition is not runtime authority")
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
    fingerprint = observation_fingerprint(player, 0)
    programs = {
        fingerprint: C3POCardObservation(
            fingerprint,
            "Luke Montgomery",
            87,
            "Season 2",
            "IDENTIFIED",
            card_id=CARD_ID,
            art_asset=ART_ASSET,
        )
    }
    source.unlink()

    page = render_c3po_roster(_roster(player), programs)
    assert ART_URL in page
    assert "media.cfb.fan" not in page
    assert "cfb.fan" not in page


def test_unresolved_or_different_exact_card_does_not_inherit_art(tmp_path):
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=None,
        enrichment_cards=_cards(program="Season 2"),
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
    )
    unknown_version = C3POPlayer(
        "OFFENSE", "LG 1", "Luke Montgomery", 87, program="Core Rare"
    )

    service.persist_inline_programs(_roster(unknown_version))
    stored = service.card_observation_store.load()[
        observation_fingerprint(unknown_version, 0)
    ]
    assert stored.card_id is None
    assert stored.art_asset is None
    assert '<img class="feature-art"' not in service.render_html(_roster(unknown_version))


def test_duplicate_observations_stay_separate_and_share_exact_card_asset(tmp_path):
    players = (
        C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87, program="Season 2"),
        C3POPlayer("SPECIALISTS", "LS 1", "Luke Montgomery", 87, program="Season 2"),
    )
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=None,
        enrichment_cards=_cards(),
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
    )

    service.persist_inline_programs(_roster(*players))
    stored = service.card_observation_store.load()
    assert len(stored) == 2
    assert len({row.fingerprint for row in stored.values()}) == 2
    assert {row.art_asset for row in stored.values()} == {ART_ASSET}


def test_exact_lookup_and_render_make_zero_artwork_network_requests(tmp_path, monkeypatch):
    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("My Team attempted artwork acquisition")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden_network)
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87, program="Season 2")
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=None,
        enrichment_cards=_cards(),
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
    )

    service.persist_inline_programs(_roster(player))
    page = service.render_html(_roster(player))
    assert ART_URL in page
    assert "cfb.fan" not in page


def test_card_art_route_serves_only_pancake_owned_asset(tmp_path):
    art_root = tmp_path / "data/production/card_art"
    art_root.mkdir(parents=True)
    payload = b"\x89PNG\r\n\x1a\nlocal-image"
    (art_root / ART_FILENAME).write_bytes(payload)
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=None,
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
        card_art_root=art_root,
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), c3po_roster_app.create_handler(service, tmp_path / "uploads")
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}{ART_URL}", timeout=5
        ) as response:
            assert response.read() == payload
            assert response.headers["Content-Type"] == "image/png"
    finally:
        server.shutdown()
        server.server_close()


def test_unknown_art_keeps_placeholder_instead_of_substituting_a_card():
    player = C3POPlayer("OFFENSE", "LG 1", "Unknown Player", 87)
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
    page = render_c3po_roster(_roster(player), programs)
    assert 'class="feature-art"' not in page
    assert '<span class="choice-ovr">87</span>' in page


def test_long_player_name_gets_compact_name_style_without_changing_ovr():
    player = C3POPlayer("OFFENSE", "TE 3", "Martellus Bennett", 82)
    page = render_c3po_roster(_roster(player))
    expected = (
        '<strong class="choice-name choice-name-long">Martellus Bennett</strong>'
    )
    assert expected in page
    assert '<span class="choice-ovr">82</span>' in page


def test_position_groups_stretch_to_align_each_six_column_lineup_row():
    roster = _roster(
        C3POPlayer("OFFENSE", "LT 1", "Starter", 87),
        C3POPlayer("OFFENSE", "TE 1", "Tight End One", 86),
        C3POPlayer("OFFENSE", "TE 2", "Tight End Two", 83),
        C3POPlayer("OFFENSE", "TE 3", "Tight End Three", 82),
        C3POPlayer("OFFENSE", "WR 1", "Receiver", 87),
    )
    page = render_c3po_roster(roster)
    assert "align-items:stretch" in page
    assert "align-items:start" not in page


def test_special_teams_uses_one_six_position_row_in_cfbfan_order():
    roster = _roster(
        C3POPlayer("SPECIAL TEAMS", "P 1", "Punter", 82),
        C3POPlayer("SPECIAL TEAMS", "K 1", "Kicker", 83),
        C3POPlayer("SPECIAL TEAMS", "KR 1", "Kick Returner", 87),
        C3POPlayer("SPECIAL TEAMS", "PR 1", "Punt Returner", 86),
        C3POPlayer("SPECIAL TEAMS", "LS 1", "Long Snapper", 85),
        C3POPlayer("SPECIAL TEAMS", "KOS 1", "Kickoff Specialist", 84),
    )
    page = render_c3po_roster(roster)
    special = page[page.index('id="special-teams"') : page.index('id="specialists"')]
    headings = ["P", "K", "KR", "PR", "LS", "KOS"]
    positions = [special.index(f"<h3>{heading}</h3>") for heading in headings]
    assert positions == sorted(positions)


def test_defense_splits_mike_and_cb_into_two_six_position_rows():
    roster = _roster(
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
    )
    page = render_c3po_roster(roster)
    defense = page[page.index('id="defense"') : page.index('id="special-teams"')]
    headings = [
        "FS",
        "WILL",
        "MIKE1",
        "MIKE2",
        "SAM",
        "SS",
        "CB1",
        "CB2",
        "REDG",
        "DT",
        "LEDG",
        "CB3",
    ]
    positions = [defense.index(f"<h3>{heading}</h3>") for heading in headings]
    assert positions == sorted(positions)


def test_specialists_use_balanced_five_by_two_grid():
    slots = ("3DRB", "PWHB", "SLWR", "GAD", "NT", "SUBLB", "RRE", "RDT", "RLE", "SLCB")
    roster = _roster(
        *(C3POPlayer("SPECIALISTS", f"{slot} 1", slot, 87) for slot in slots)
    )
    page = render_c3po_roster(roster)
    specialists = page[page.index('id="specialists"') :]
    assert 'class="position-grid specialists-grid"' in specialists
    expected_grid = ".specialists-grid{grid-template-columns:repeat(5,minmax(0,1fr))}"
    assert expected_grid in page

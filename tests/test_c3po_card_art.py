from operation_pancake.c3po_card_version import (
    C3POCardObservation,
    C3POCardObservationStore,
)
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    _known_art_url,
    observation_fingerprint,
)
from operation_pancake.c3po_roster_page import render_c3po_roster

# Verified CFB.FAN playeritem URLs below are evidence-bound to known roster observations.
LUKE_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/202019231.png"
CASON_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/260010612.png"
JOSH_PETTY_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/260025229.png"
THOMAS_SHRADER_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/260021328.png"
KEYAN_BURNETT_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/260021232.png"
MALACHI_TONEY_ART_URL = "https://media.cfb.fan/cdn-cgi/image/format=auto,width=300,height=401,quality=80,fit=cover,gravity=top/27/cutdb/playeritem/260025282.png"


def _roster(*players: C3POPlayer) -> C3PORoster:
    return C3PORoster(players, "google-gemini", "gemini-3.7-flash")


def test_known_observation_persists_art_and_renders_at_existing_lg_location(tmp_path):
    player = C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
    fingerprint = observation_fingerprint(player, 0)
    store = C3POCardObservationStore(tmp_path / "c3po-programs.json")
    store.save(
        {
            fingerprint: C3POCardObservation(
                fingerprint=fingerprint,
                player_name="Luke Montgomery",
                displayed_ovr=87,
                program=None,
                state="UNCERTAIN",
                art_url=LUKE_ART_URL,
            )
        }
    )

    programs = store.load()
    page = render_c3po_roster(_roster(player), programs)
    lg_start = page.index("<h3>LG</h3>")
    lg_group = page[lg_start : page.index("</section>", lg_start)]

    assert programs[fingerprint].art_url == LUKE_ART_URL
    assert f'src="{LUKE_ART_URL}"' in lg_group
    assert 'data-slot="LG 1"' in lg_group
    assert "CARD NOT READ" in lg_group
    assert '<span class="choice-ovr">87</span>' in lg_group


def test_cason_henry_known_card_art_is_seeded_for_observed_85():
    assert _known_art_url("Cason Henry", 85) == CASON_ART_URL


def test_new_verified_card_art_survives_save_reload_and_renders_at_roster_position(tmp_path):
    cases = (
        ("LT 1", "Josh Petty", 81, "Phenoms", JOSH_PETTY_ART_URL),
        ("LG 1", "Thomas Shrader", 85, "Phenoms", THOMAS_SHRADER_ART_URL),
        ("TE 1", "Keyan Burnett", 83, "Phenoms", KEYAN_BURNETT_ART_URL),
        ("WR 1", "Malachi Toney", 87, "Phenoms", MALACHI_TONEY_ART_URL),
    )
    for index, (slot, name, ovr, program, art_url) in enumerate(cases):
        player = C3POPlayer("OFFENSE", slot, name, ovr, program=program)
        fingerprint = observation_fingerprint(player, 0)
        store = C3POCardObservationStore(tmp_path / f"programs-{index}.json")
        store.save(
            {
                fingerprint: C3POCardObservation(
                    fingerprint=fingerprint,
                    player_name=name,
                    displayed_ovr=ovr,
                    program=program,
                    state="IDENTIFIED",
                    art_url=_known_art_url(name, ovr),
                )
            }
        )

        programs = store.load()
        page = render_c3po_roster(_roster(player), programs)
        position = slot.split()[0]
        start = page.index(f"<h3>{position}</h3>")
        group = page[start : page.index("</section>", start)]

        assert programs[fingerprint].art_url == art_url
        assert f'src="{art_url}"' in group
        assert f'data-slot="{slot}"' in group
        assert f'<span class="choice-ovr">{ovr}</span>' in group
        assert program in group


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
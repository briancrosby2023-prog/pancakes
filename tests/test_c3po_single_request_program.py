from __future__ import annotations

from pathlib import Path

from operation_pancake import c3po_card_version, c3po_roster


class SingleRequestProvider:
    def __init__(self):
        self.calls = 0

    def read_four(self, screenshots):
        assert len(tuple(screenshots)) == 4
        self.calls += 1
        return [
            {
                "view": "OFFENSE",
                "players": [
                    {
                        "slot": "LG 1",
                        "name": "Luke Montgomery",
                        "displayed_ovr": 87,
                        "program": "Season 2",
                    }
                ],
                "provider": "google-gemini",
                "model": "gemini-3.7-flash",
                "status": "C-3PO READ",
            }
        ]


class ForbiddenSecondAnalyzer:
    def analyze_batch(self, requests, evidence):
        raise AssertionError("successful import must not make a second Gemini request")


def test_import_persists_program_from_same_roster_request_without_second_analysis(tmp_path: Path):
    screenshots = []
    for index in range(4):
        path = tmp_path / f"screen-{index}.png"
        path.write_bytes(b"pixels")
        screenshots.append(path)

    provider = SingleRequestProvider()
    roster_store = c3po_roster.C3PORosterStore(tmp_path / "c3po-roster.json")
    program_store = c3po_card_version.C3POCardObservationStore(
        tmp_path / "c3po-programs.json"
    )
    service = c3po_roster.C3PORosterService(
        roster_store,
        provider,
        source_evidence_store=None,
        version_analyzer=ForbiddenSecondAnalyzer(),
        card_observation_store=program_store,
    )

    roster = service.import_four(screenshots)

    assert provider.calls == 1
    assert len(roster.players) == 1
    assert roster.players[0].name == "Luke Montgomery"
    assert roster.players[0].displayed_ovr == 87

    programs = program_store.load()
    assert len(programs) == 1
    observation = next(iter(programs.values()))
    assert observation.player_name == "Luke Montgomery"
    assert observation.displayed_ovr == 87
    assert observation.program == "Season 2"
    assert observation.state == "IDENTIFIED"

    page = service.my_team_html()
    assert "Luke Montgomery" in page
    assert "87 OVR" in page
    assert "Season 2" in page
    assert "202019231.png" in page

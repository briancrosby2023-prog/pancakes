from __future__ import annotations

import base64
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from operation_pancake import c3po_roster_app, cfb27_enrichment
from operation_pancake.c3po_card_version import (
    C3POCardObservation,
    C3POCardObservationStore,
    CardVersionAnalysisRequest,
    CardVersionBatchResult,
    CardVersionDecision,
    GeminiCardVersionAnalyzer,
)
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterService,
    C3PORosterStore,
)
from operation_pancake.c3po_source_evidence import (
    C3POSourceEvidence,
    C3POSourceEvidenceStore,
    C3POSourceImage,
)
from operation_pancake.cfb27_enrichment import CFB27CardChoiceStore


class _Interaction:
    def __init__(self, output_text: str):
        self.output_text = output_text


class _Interactions:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Interaction(self.output_text)


class _Client:
    def __init__(self, output_text: str):
        self.interactions = _Interactions(output_text)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _evidence() -> C3POSourceEvidence:
    return C3POSourceEvidence(
        "roster-fingerprint",
        tuple(
            C3POSourceImage(index, "image/png", f"pixels-{index}".encode())
            for index in range(4)
        ),
    )


def _screenshots(root: Path) -> tuple[Path, ...]:
    paths = []
    for index in range(4):
        path = root / f"screen-{index}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index]))
        paths.append(path)
    return tuple(paths)


def test_prompt_asks_unrestricted_program_without_database_candidates():
    client = _Client(
        '{"results":[{"observation_fingerprint":"luke",'
        '"result":"IDENTIFIED","program_version":"SEASON 2",'
        '"confidence":"HIGH","positive_visual_evidence":'
        '["Visible Season 2 card treatment"]}]}'
    )
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-real", client_factory=lambda: client
    )
    request = CardVersionAnalysisRequest(
        "luke", C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
    )

    result = analyzer.analyze_batch((request,), _evidence())

    assert result.decisions["luke"] == CardVersionDecision.identified(
        "SEASON 2", ("Visible Season 2 card treatment",)
    )
    call = client.interactions.calls[0]
    prompt = call["input"][0]["text"]
    assert "Luke Montgomery" in prompt
    assert "EA displayed OVR: 87" in prompt
    assert "program/version" in prompt
    assert "card_id=" not in prompt
    assert "Supplied card versions" not in prompt
    assert "Core Rare" not in prompt
    assert "Orientation" not in prompt
    assert len(call["input"][1:]) == 4
    assert [base64.b64decode(item["data"]) for item in call["input"][1:]] == [
        image.payload for image in _evidence().images
    ]


def test_unknown_database_program_is_a_valid_provider_observation():
    client = _Client(
        '{"results":[{"observation_fingerprint":"luke",'
        '"result":"IDENTIFIED","program_version":"SEASON 2",'
        '"confidence":"HIGH","positive_visual_evidence":["Visible Season 2 badge"]}]}'
    )
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-real", client_factory=lambda: client
    )

    result = analyzer.analyze_batch(
        (
            CardVersionAnalysisRequest(
                "luke", C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
            ),
        ),
        _evidence(),
    )

    assert result.decisions["luke"].program == "SEASON 2"


def test_luke_and_kj_programs_persist_before_database_enrichment(tmp_path):
    class Analyzer:
        def analyze_batch(self, requests, evidence):
            assert len(requests) == 2
            return CardVersionBatchResult(
                {
                    requests[0].fingerprint: CardVersionDecision.identified(
                        "SEASON 2", ("Visible Season 2 treatment",)
                    ),
                    requests[1].fingerprint: CardVersionDecision.identified(
                        "PHENOMS", ("Visible Phenoms treatment",)
                    ),
                },
                request_succeeded=True,
            )

    roster = C3PORoster(
        (
            C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87),
            C3POPlayer("DEFENSE", "FS 1", "KJ Bolden", 88),
        ),
        "google-gemini",
        "gemini-3.7-flash",
    )
    cards = (
        {"player_name": "Luke Montgomery", "card_id": "core", "program": "Core Rare"},
        {"player_name": "Luke Montgomery", "card_id": "orientation", "program": "Orientation"},
        {"player_name": "Luke Montgomery", "card_id": "platinum", "program": "Platinum Rare"},
        {"player_name": "KJ Bolden", "card_id": "kj-core", "program": "Core Rare"},
        {"player_name": "KJ Bolden", "card_id": "kj-phenoms", "program": "Phenoms"},
    )
    store = C3PORosterStore(tmp_path / "roster.json")
    observation_store = C3POCardObservationStore(tmp_path / "card-observations.json")
    service = C3PORosterService(
        store,
        object(),
        enrichment_cards=cards,
        card_choice_store=CFB27CardChoiceStore(tmp_path / "choices.json"),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=Analyzer(),
        card_observation_store=observation_store,
    )
    store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    roster_bytes = store.path.read_bytes()

    outcome = service.analyze_card_versions(roster)

    assert outcome.request_succeeded
    assert store.path.read_bytes() == roster_bytes
    persisted = observation_store.load()
    assert {row.program for row in persisted.values()} == {"SEASON 2", "PHENOMS"}
    page = service.my_team_html()
    assert "Luke Montgomery" in page and "EA OVR 87" in page
    assert "SEASON 2" in page
    assert "Core Rare" not in page
    assert "Orientation" not in page
    assert "Platinum Rare" not in page
    assert "KJ Bolden" in page
    assert "PHENOMS" in page
    assert "CFB27" not in page
    assert "SELECT CARD" not in page


def test_uncertain_response_does_not_invent_a_program():
    client = _Client(
        '{"results":[{"observation_fingerprint":"luke","result":"UNCERTAIN"}]}'
    )
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-real", client_factory=lambda: client
    )

    result = analyzer.analyze_batch(
        (
            CardVersionAnalysisRequest(
                "luke", C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87)
            ),
        ),
        _evidence(),
    )

    assert result.decisions["luke"] == CardVersionDecision.ambiguous()
    assert result.decisions["luke"].program is None


def test_provider_failure_preserves_existing_card_observations(tmp_path):
    class FailedAnalyzer:
        def analyze_batch(self, requests, evidence):
            return CardVersionBatchResult({}, request_succeeded=False, rate_limited=True)

    roster = C3PORoster(
        (C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87),), "p", "m"
    )
    store = C3PORosterStore(tmp_path / "roster.json")
    observation_store = C3POCardObservationStore(tmp_path / "card-observations.json")
    service = C3PORosterService(
        store,
        object(),
        enrichment_cards=(),
        card_choice_store=CFB27CardChoiceStore(tmp_path / "choices.json"),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=FailedAnalyzer(),
        card_observation_store=observation_store,
    )
    store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    observation_store.save(
        {
            "existing": C3POCardObservation(
                "existing",
                "Existing Player",
                90,
                "SEASON 2",
                "IDENTIFIED",
                "HIGH",
                ("visible",),
            )
        }
    )
    before = observation_store.path.read_bytes()

    outcome = service.analyze_card_versions(roster)

    assert outcome.rate_limited
    assert observation_store.path.read_bytes() == before


def test_legacy_manual_card_selection_is_inert_and_program_remains(tmp_path):
    roster = C3PORoster(
        (C3POPlayer("DEFENSE", "FS 1", "KJ Bolden", 88),), "p", "m"
    )
    store = C3PORosterStore(tmp_path / "roster.json")
    observation_store = C3POCardObservationStore(tmp_path / "card-observations.json")
    choice_store = CFB27CardChoiceStore(tmp_path / "choices.json")
    service = C3PORosterService(
        store,
        object(),
        enrichment_cards=(
            {"player_name": "KJ Bolden", "card_id": "phenoms-a", "program": "Phenoms"},
            {"player_name": "KJ Bolden", "card_id": "phenoms-b", "program": "Phenoms"},
            {"player_name": "KJ Bolden", "card_id": "core", "program": "Core Rare"},
        ),
        card_choice_store=choice_store,
        card_observation_store=observation_store,
    )
    store.save(roster)
    from operation_pancake.cfb27_enrichment import observation_fingerprint

    fingerprint = observation_fingerprint(roster.players[0], 0)
    observation_store.save(
        {
            fingerprint: C3POCardObservation(
                fingerprint,
                "KJ Bolden",
                88,
                "PHENOMS",
                "IDENTIFIED",
                "HIGH",
                ("Visible Phenoms treatment",),
            )
        }
    )

    assert not hasattr(service, "select_card_version")
    assert not choice_store.path.exists()
    assert observation_store.load()[fingerprint].program == "PHENOMS"
    page = service.my_team_html()
    assert "PHENOMS" in page
    assert "SELECT CARD" not in page
    assert "USE CARD" not in page


def test_missing_program_and_missing_name_are_product_states(tmp_path):
    roster = C3PORoster(
        (
            C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87),
            C3POPlayer("OFFENSE", "LG 2", None, 81),
        ),
        "p",
        "m",
    )
    service = C3PORosterService(C3PORosterStore(tmp_path / "roster.json"), object())
    service.store.save(roster)

    page = service.my_team_html()

    assert "Luke Montgomery" in page
    assert "CARD NOT READ" in page
    assert "NAME NOT READ" in page
    assert page.count('class="player ') == 2


def test_program_analysis_excludes_name_not_read_observations(tmp_path):
    class Analyzer:
        def __init__(self):
            self.requests = ()

        def analyze_batch(self, requests, evidence):
            self.requests = tuple(requests)
            return CardVersionBatchResult({}, request_succeeded=True)

    roster = C3PORoster(
        (
            C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87),
            C3POPlayer("OFFENSE", "LG 2", None, 81),
        ),
        "p",
        "m",
    )
    analyzer = Analyzer()
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        object(),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))

    service.analyze_card_versions(roster)

    assert len(analyzer.requests) == 1
    assert analyzer.requests[0].observation.name == "Luke Montgomery"


def test_setup_and_my_team_are_separate_and_get_is_zero_provider_zero_database(
    tmp_path, monkeypatch
):
    class NoProvider:
        def read_four(self, screenshots):
            raise AssertionError("GET must not invoke Gemini")

    def no_database(*args, **kwargs):
        raise AssertionError("My Team must not load CFB27 production data")

    monkeypatch.setattr(cfb27_enrichment, "load_cfb27_production_cards", no_database)
    service = c3po_roster_app.create_service(
        tmp_path, provider=NoProvider(), roster_path=tmp_path / "roster.json"
    )
    service.store.save(
        C3PORoster(
            (C3POPlayer("OFFENSE", "LG 1", "Luke Montgomery", 87),), "p", "m"
        )
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), c3po_roster_app.create_handler(service, tmp_path / "uploads")
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/setup", timeout=10
        ) as response:
            setup = response.read().decode()
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/my-team", timeout=10
        ) as response:
            team = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()

    assert 'action="/team/upload"' in setup
    assert "Update Team" in setup
    assert 'action="/team/upload"' not in team
    assert "Luke Montgomery" in team
    assert 'href="/setup">UPDATE TEAM</a>' in team


def test_duplicate_client_filenames_preserve_four_distinct_ordered_images(tmp_path):
    boundary = "same-name"
    body = b""
    payloads = (b"first", b"second", b"third", b"fourth")
    for payload in payloads:
        body += (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="screenshots"; filename="team.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode() + payload + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    paths = c3po_roster_app._uploaded_files(
        f"multipart/form-data; boundary={boundary}", body, tmp_path
    )

    assert len(set(paths)) == 4
    assert tuple(path.read_bytes() for path in paths) == payloads


def test_compact_slots_and_nested_backups_render_and_analyze_as_one_depth_group(tmp_path):
    class Analyzer:
        def __init__(self):
            self.requests = ()

        def analyze_batch(self, requests, evidence):
            self.requests = tuple(requests)
            return CardVersionBatchResult({}, request_succeeded=True)

    roster = C3PORoster(
        (
            C3POPlayer(
                "OFFENSE",
                "LT1",
                "Josh Petty",
                81,
                ({"slot": "LT2", "name": "Luke Montgomery", "displayed_ovr": 87},),
            ),
        ),
        "p",
        "m",
    )
    analyzer = Analyzer()
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        object(),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))

    service.analyze_card_versions(roster)
    page = service.my_team_html()

    assert [request.observation.name for request in analyzer.requests] == [
        "Josh Petty",
        "Luke Montgomery",
    ]
    assert page.count('<section class="position-group"><h3>LT</h3>') == 1
    assert "Josh Petty" in page and "Luke Montgomery" in page
    assert page.count('class="player starter"') == 1
    assert page.count('class="player backup"') == 1

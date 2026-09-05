from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

from operation_pancake import c3po_roster_app
from operation_pancake.c3po_card_version import (
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
from operation_pancake.c3po_source_evidence import C3POSourceEvidenceStore
from operation_pancake.cfb27_enrichment import (
    CFB27CardChoiceStore,
    observation_fingerprint,
)


def _roster(ovr: int = 85) -> C3PORoster:
    return C3PORoster(
        (C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", ovr),),
        "google-gemini",
        "gemini-3.7-flash",
    )


def _screenshots(root: Path) -> tuple[Path, ...]:
    payloads = (
        b"\x89PNG\r\n\x1a\nOFFENSE",
        b"\xff\xd8\xffDEFENSE",
        b"RIFF\x10\x00\x00\x00WEBPSPECIAL-TEAMS",
        b"\x89PNG\r\n\x1a\nSPECIALISTS",
    )
    suffixes = (".png", ".jpg", ".webp", ".png")
    paths = []
    for index, (payload, suffix) in enumerate(zip(payloads, suffixes, strict=True)):
        path = root / f"screen-{index}{suffix}"
        path.write_bytes(payload)
        paths.append(path)
    return tuple(paths)


def test_four_original_images_mime_and_order_survive_restart(tmp_path):
    screenshots = _screenshots(tmp_path)
    archive = tmp_path / "state" / "source-evidence.zip"
    C3POSourceEvidenceStore(archive).save(_roster(), screenshots)

    evidence = C3POSourceEvidenceStore(archive).load_for(_roster())

    assert evidence is not None
    assert tuple(image.payload for image in evidence.images) == tuple(
        path.read_bytes() for path in screenshots
    )
    assert tuple(image.mime_type for image in evidence.images) == (
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/png",
    )
    assert tuple(image.order for image in evidence.images) == (0, 1, 2, 3)


def test_corrupt_or_incomplete_evidence_fails_open(tmp_path):
    archive = tmp_path / "source-evidence.zip"
    store = C3POSourceEvidenceStore(archive)
    store.save(_roster(), _screenshots(tmp_path))
    with zipfile.ZipFile(archive) as bundle:
        members = {
            name: bundle.read(name)
            for name in bundle.namelist()
            if name != "images/2.bin"
        }
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, payload in members.items():
            bundle.writestr(name, payload)

    assert store.load_for(_roster()) is None


def test_evidence_for_an_old_roster_is_not_reused(tmp_path):
    store = C3POSourceEvidenceStore(tmp_path / "source-evidence.zip")
    store.save(_roster(85), _screenshots(tmp_path))

    assert store.load_for(_roster(86)) is None


class _Provider:
    def __init__(self, ovr: int = 85, failure: bool = False):
        self.ovr = ovr
        self.failure = failure

    def read_four(self, screenshots):
        assert len(tuple(screenshots)) == 4
        if self.failure:
            return [
                {
                    "status": "PROVIDER FAILURE",
                    "provider": "google-gemini",
                    "model": "gemini-3.7-flash",
                }
            ]
        return [
            {
                "view": "SPECIAL TEAMS",
                "players": [
                    {
                        "slot": "LS 1",
                        "name": "Thomas Shrader",
                        "displayed_ovr": self.ovr,
                    }
                ],
                "provider": "google-gemini",
                "model": "gemini-3.7-flash",
            }
        ]


def _cards():
    return (
        {
            "player_name": "Thomas Shrader",
            "card_id": "thomas-core",
            "native_overall": 81,
            "position": "LG",
            "program": "Core Rare",
        },
        {
            "player_name": "Thomas Shrader",
            "card_id": "thomas-phenoms",
            "native_overall": 84,
            "position": "LG",
            "program": "Phenoms",
        },
        {
            "player_name": "Zach Rice",
            "card_id": "zach-phenoms",
            "native_overall": 81,
            "position": "RG",
            "program": "Phenoms",
        },
    )


def _service(tmp_path, provider, analyzer=None):
    return C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider,
        enrichment_cards=_cards(),
        card_choice_store=CFB27CardChoiceStore(tmp_path / "choices.json"),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
    )


def test_provider_failure_preserves_previous_roster_and_source_evidence(tmp_path):
    screenshots = _screenshots(tmp_path)
    service = _service(tmp_path, _Provider())
    original = service.import_four(screenshots)
    roster_bytes = service.store.path.read_bytes()
    evidence_bytes = service.source_evidence_store.path.read_bytes()

    service.provider = _Provider(failure=True)
    failed = service.import_four(screenshots)

    assert failed.status == "PROVIDER FAILURE"
    assert service.store.path.read_bytes() == roster_bytes
    assert service.source_evidence_store.path.read_bytes() == evidence_bytes
    assert service.store.load() == original


def test_successful_replacement_binds_new_evidence_to_new_roster(tmp_path):
    screenshots = _screenshots(tmp_path)
    service = _service(tmp_path, _Provider(85))
    original = service.import_four(screenshots)
    service.provider = _Provider(86)

    replacement = service.import_four(screenshots)

    assert replacement != original
    assert service.source_evidence_store.load_for(replacement) is not None
    assert service.source_evidence_store.load_for(original) is None


class _RecordingAnalyzer:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def analyze_batch(self, requests, evidence):
        requests = tuple(requests)
        self.calls.append((requests, evidence))
        return CardVersionBatchResult(
            {request.fingerprint: self.decision for request in requests},
            request_succeeded=True,
        )


def test_unique_same_player_version_persists_without_mutating_roster(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    roster = service.import_four(_screenshots(tmp_path))
    roster_bytes = service.store.path.read_bytes()
    assert len(analyzer.calls) == 1

    page = service.my_team_html()
    service.my_team_html()
    restart_analyzer = _RecordingAnalyzer(CardVersionDecision.provider_failure())
    restarted = _service(tmp_path, _Provider(failure=True), restart_analyzer)

    assert "CFB27: LG · 84 OVR · Phenoms" in page
    assert "SELECT CARD" not in page
    assert len(analyzer.calls) == 1
    requests, evidence = analyzer.calls[0]
    assert len(requests) == 1
    request = requests[0]
    assert request.observation == roster.players[0]
    assert len(evidence.images) == 4
    assert {card.card_id for card in request.cards} == {
        "thomas-core",
        "thomas-phenoms",
    }
    assert {card.canonical_name for card in request.cards} == {"Thomas Shrader"}
    assert service.store.path.read_bytes() == roster_bytes
    assert restarted.store.load() == roster
    assert "CFB27: LG · 84 OVR · Phenoms" in restarted.my_team_html()
    assert restart_analyzer.calls == []


def test_analyzer_cannot_choose_outside_exact_player_family(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("zach-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    service.import_four(_screenshots(tmp_path))

    page = service.my_team_html()

    assert "Thomas Shrader" in page
    assert "SELECT CARD" in page
    assert "Zach Rice" not in page


def test_non_unique_or_failed_analysis_keeps_select_card(tmp_path):
    for decision in (
        CardVersionDecision.ambiguous(),
        CardVersionDecision.no_evidence(),
        CardVersionDecision.provider_failure(),
    ):
        case = tmp_path / decision.state.lower()
        case.mkdir()
        analyzer = _RecordingAnalyzer(decision)
        service = _service(case, _Provider(), analyzer)
        service.import_four(_screenshots(case))
        assert len(analyzer.calls) == 1
        assert "SELECT CARD" in service.my_team_html()
        assert len(analyzer.calls) == 1


def test_unexpected_analyzer_failure_keeps_select_card(tmp_path):
    class BrokenAnalyzer:
        def analyze_batch(self, requests, evidence):
            raise RuntimeError("secondary provider unavailable")

    service = _service(tmp_path, _Provider(), BrokenAnalyzer())
    service.import_four(_screenshots(tmp_path))

    assert "SELECT CARD" in service.my_team_html()


def test_missing_source_evidence_keeps_select_card_and_skips_analyzer(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    service.store.save(_roster())

    service.analyze_card_versions(service.store.load())
    assert "SELECT CARD" in service.my_team_html()
    assert analyzer.calls == []


def test_evidence_store_failure_keeps_select_card(tmp_path):
    class BrokenEvidenceStore:
        def load_for(self, roster):
            raise OSError("evidence volume unavailable")

    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    service.store.save(_roster())
    service.source_evidence_store = BrokenEvidenceStore()

    service.analyze_card_versions(service.store.load())
    assert "SELECT CARD" in service.my_team_html()
    assert analyzer.calls == []


def test_singleton_family_bypasses_version_analyzer(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.provider_failure())
    service = _service(tmp_path, _Provider(), analyzer)
    singleton = C3PORoster(
        (C3POPlayer("OFFENSE", "RG 1", "Zach Rice", 82),),
        "google-gemini",
        "gemini-3.7-flash",
    )
    service.store.save(singleton)
    service.source_evidence_store.save(singleton, _screenshots(tmp_path))

    service.analyze_card_versions(singleton)
    page = service.my_team_html()

    assert "CFB27: RG · 81 OVR · Phenoms" in page
    assert analyzer.calls == []


def test_stale_automatic_choice_fails_open_after_new_observation(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(85), analyzer)
    screenshots = _screenshots(tmp_path)
    service.import_four(screenshots)
    assert "SELECT CARD" not in service.my_team_html()

    service.version_analyzer = None
    service.provider = _Provider(86)
    changed = service.import_four(screenshots)

    assert changed.players[0].displayed_ovr == 86
    page = service.my_team_html()
    assert "Thomas Shrader" in page
    assert "EA OVR 86" in page
    assert "SELECT CARD" in page
    assert "CFB27: LG · 84 OVR · Phenoms" not in page


def test_manual_choice_wins_and_bypasses_version_analyzer(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    roster = _roster()
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    fingerprint = observation_fingerprint(roster.players[0], 0)
    assert service.select_card_version(fingerprint, "thomas-core")

    service.analyze_card_versions(roster)

    assert analyzer.calls == []
    page = service.my_team_html()
    assert "CFB27: LG · 81 OVR · Core Rare" in page
    assert "Phenoms" not in page


def test_version_diagnostics_are_bounded_and_exclude_sensitive_payloads(
    tmp_path, caplog
):
    caplog.set_level("INFO")
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)

    service.import_four(_screenshots(tmp_path))

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "VERSION ANALYZER BATCH request_count=1" in messages
    assert "VERSION ANALYZER RESULT" in messages
    assert "player=Thomas Shrader" in messages
    assert "candidates=2" in messages
    assert "source_evidence_compatible=yes" in messages
    assert "source_images=4" in messages
    assert "result=UNIQUE_VERSION" in messages
    assert "card_id=thomas-phenoms" in messages
    assert "program=Phenoms" in messages
    assert "native_ovr=84" in messages
    assert "not-a-real-key" not in messages
    assert "image-0" not in messages


def test_multiple_ambiguous_players_invoke_one_batch_and_validate_each_family(
    tmp_path,
):
    class BatchAnalyzer:
        def __init__(self):
            self.calls = []

        def analyze_batch(self, requests, evidence):
            requests = tuple(requests)
            self.calls.append((requests, evidence))
            return CardVersionBatchResult(
                {
                    requests[0].fingerprint: CardVersionDecision.unique(
                        "thomas-phenoms"
                    ),
                    requests[1].fingerprint: CardVersionDecision.unique(
                        "thomas-core"
                    ),
                },
                request_succeeded=True,
            )

    cards = _cards() + (
        {
            "player_name": "Juan Gaston",
            "card_id": "juan-core",
            "native_overall": 75,
            "position": "RT",
            "program": "Core Uncommon",
        },
        {
            "player_name": "Juan Gaston",
            "card_id": "juan-phenoms",
            "native_overall": 80,
            "position": "RT",
            "program": "Phenoms",
        },
    )
    roster = C3PORoster(
        (
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            C3POPlayer("OFFENSE", "RT 2", "Juan Gaston", 81),
        ),
        "google-gemini",
        "gemini-3.7-flash",
    )
    analyzer = BatchAnalyzer()
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        _Provider(),
        enrichment_cards=cards,
        card_choice_store=CFB27CardChoiceStore(tmp_path / "choices.json"),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))

    outcome = service.analyze_card_versions(roster)

    assert len(analyzer.calls) == 1
    requests, evidence = analyzer.calls[0]
    assert len(requests) == 2
    assert len(evidence.images) == 4
    assert {card.canonical_name for card in requests[0].cards} == {
        "Thomas Shrader"
    }
    assert {card.canonical_name for card in requests[1].cards} == {"Juan Gaston"}
    assert outcome.request_succeeded
    page = service.my_team_html()
    assert "CFB27: LG · 84 OVR · Phenoms" in page
    assert "Juan Gaston" in page and "SELECT CARD" in page


def test_total_rate_limit_preserves_roster_choices_and_reports_failure(
    tmp_path, monkeypatch, capsys, caplog
):
    class RateLimitedAnalyzer:
        def analyze_batch(self, requests, evidence):
            return CardVersionBatchResult(
                {}, request_succeeded=False, rate_limited=True
            )

    service = _service(tmp_path, _Provider(), RateLimitedAnalyzer())
    roster = _roster()
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    roster_bytes = service.store.path.read_bytes()
    choice_bytes = b'{"choices": {}}\n'
    service.card_choice_store.path.write_bytes(choice_bytes)
    monkeypatch.setattr(c3po_roster_app, "create_service", lambda root: service)
    caplog.set_level("INFO")

    status = c3po_roster_app.analyze_persisted_card_versions()

    output = capsys.readouterr().out
    assert status != 0
    assert "VERSION ANALYZER FAILED: RATE_LIMITED" in output
    assert "VERSION ANALYZER COMPLETE" not in output
    assert "result=RATE_LIMITED" in caplog.text
    assert service.store.path.read_bytes() == roster_bytes
    assert service.card_choice_store.path.read_bytes() == choice_bytes
    assert service.store.load() == roster


def test_omitted_player_result_remains_select_card(tmp_path):
    class OmittedResultAnalyzer:
        def analyze_batch(self, requests, evidence):
            return CardVersionBatchResult({}, request_succeeded=True)

    service = _service(tmp_path, _Provider(), OmittedResultAnalyzer())

    service.import_four(_screenshots(tmp_path))

    assert "Thomas Shrader" in service.my_team_html()
    assert "SELECT CARD" in service.my_team_html()


def test_real_provider_boundary_batches_and_deduplicates_identical_work(tmp_path):
    class Interaction:
        output_text = (
            '{"results":[{"observation_fingerprint":"FIRST",'
            '"result":"UNIQUE_VERSION","card_id":"thomas-phenoms",'
            '"confidence":"HIGH","positive_visual_evidence":'
            '["Visible Phenoms card treatment"]}]}'
        )

    class Interactions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            prompt = kwargs["input"][0]["text"]
            fingerprints = tuple(
                block.splitlines()[0]
                for block in prompt.split("OBSERVATION ")[1:]
            )
            Interaction.output_text = (
                '{"results":[{"observation_fingerprint":"'
                + fingerprints[0]
                + '","result":"UNIQUE_VERSION","card_id":"thomas-phenoms",'
                '"confidence":"HIGH","positive_visual_evidence":'
                '["Visible Phenoms card treatment"]},{"observation_fingerprint":"'
                + fingerprints[1]
                + '","result":"AMBIGUOUS"}]}'
            )
            return Interaction()

    class Client:
        def __init__(self):
            self.interactions = Interactions()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    client = Client()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-a-real-key", client_factory=lambda: client
    )
    repeated = C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85)
    juan = C3POPlayer("OFFENSE", "RT 2", "Juan Gaston", 81)
    roster = C3PORoster(
        (repeated, repeated, juan), "google-gemini", "gemini-3.7-flash"
    )
    cards = _cards() + (
        {
            "player_name": "Juan Gaston",
            "card_id": "juan-core",
            "native_overall": 75,
            "position": "RT",
            "program": "Core Uncommon",
        },
        {
            "player_name": "Juan Gaston",
            "card_id": "juan-phenoms",
            "native_overall": 80,
            "position": "RT",
            "program": "Phenoms",
        },
    )
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        _Provider(),
        enrichment_cards=cards,
        card_choice_store=CFB27CardChoiceStore(tmp_path / "choices.json"),
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    roster_bytes = service.store.path.read_bytes()

    outcome = service.analyze_card_versions(roster)

    assert outcome.request_succeeded
    assert outcome.requested == 2
    assert len(client.interactions.calls) == 1
    provider_input = client.interactions.calls[0]["input"]
    assert len(provider_input) == 5
    prompt = provider_input[0]["text"]
    assert prompt.count("OBSERVATION ") == 2
    assert prompt.count("Thomas Shrader") >= 1
    assert prompt.count("card_id=thomas-core") == 1
    assert prompt.count("card_id=thomas-phenoms") == 1
    assert service.store.path.read_bytes() == roster_bytes
    assert service.store.load().players == (repeated, repeated, juan)
    assert service.my_team_html().count("CFB27: LG · 84 OVR · Phenoms") == 2
    assert "Juan Gaston" in service.my_team_html()
    assert "SELECT CARD" in service.my_team_html()


def test_same_name_with_different_immutable_evidence_is_not_deduplicated(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.ambiguous())
    service = _service(tmp_path, _Provider(), analyzer)
    roster = C3PORoster(
        (
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            C3POPlayer("OFFENSE", "LG 2", "Thomas Shrader", 85),
        ),
        "google-gemini",
        "gemini-3.7-flash",
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))

    outcome = service.analyze_card_versions(roster)

    assert outcome.requested == 2
    assert len(analyzer.calls) == 1
    assert len(analyzer.calls[0][0]) == 2


def test_rate_limit_diagnostics_report_one_batch_not_per_player_invocations(
    tmp_path, caplog
):
    class RateLimitedAnalyzer:
        def analyze_batch(self, requests, evidence):
            return CardVersionBatchResult(
                {}, request_succeeded=False, rate_limited=True
            )

    caplog.set_level("INFO")
    service = _service(tmp_path, _Provider(), RateLimitedAnalyzer())
    repeated = C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85)
    roster = C3PORoster(
        (repeated, repeated), "google-gemini", "gemini-3.7-flash"
    )
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))

    outcome = service.analyze_card_versions(roster)

    assert outcome.rate_limited
    assert outcome.requested == 1
    assert caplog.text.count("VERSION ANALYZER BATCH") == 1
    assert "request_count=1" in caplog.text
    assert "work_items=1" in caplog.text
    assert "roster_observations=2" in caplog.text
    assert "result=RATE_LIMITED" in caplog.text
    assert "VERSION ANALYZER INVOKED player=" not in caplog.text


def test_real_provider_boundary_429_calls_once_and_changes_no_state(
    tmp_path, caplog
):
    class RateLimitedInteractions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            error = RuntimeError("RESOURCE_EXHAUSTED: quota denied for key=secret")
            error.code = 429
            error.status = "RESOURCE_EXHAUSTED"
            raise error

    class Client:
        def __init__(self):
            self.interactions = RateLimitedInteractions()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    client = Client()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="secret", client_factory=lambda: client
    )
    service = _service(tmp_path, _Provider(), analyzer)
    roster = _roster()
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    service.card_choice_store.path.write_text('{"choices": {}}\n', encoding="utf-8")
    before = (
        service.store.path.read_bytes(),
        service.source_evidence_store.path.read_bytes(),
        service.card_choice_store.path.read_bytes(),
    )
    caplog.set_level("INFO")

    outcome = service.analyze_card_versions(roster)

    assert len(client.interactions.calls) == 1
    assert outcome.rate_limited and not outcome.request_succeeded
    assert (
        service.store.path.read_bytes(),
        service.source_evidence_store.path.read_bytes(),
        service.card_choice_store.path.read_bytes(),
    ) == before
    assert "RATE_LIMITED" in caplog.text
    assert "secret" not in caplog.text


def test_runtime_diagnostic_identifies_modules_and_makes_zero_provider_calls(
    tmp_path, monkeypatch, capsys
):
    class NoNetworkAnalyzer:
        model = "diagnostic-model"

        def analyze_batch(self, requests, evidence):
            raise AssertionError("runtime diagnostic must not invoke Gemini")

    service = _service(tmp_path, _Provider(), NoNetworkAnalyzer())
    roster = _roster()
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    monkeypatch.setattr(c3po_roster_app, "production_root", lambda: tmp_path)
    monkeypatch.setattr(c3po_roster_app, "create_service", lambda root: service)
    monkeypatch.setattr(c3po_roster_app, "_git_head", lambda root: "test-head")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-printed")
    monkeypatch.setenv("PANCAKE_GEMINI_VERSION_MODEL", "diagnostic-model")

    status = c3po_roster_app.runtime_diagnostic()

    output = capsys.readouterr().out
    assert status == 0
    assert "DIAGNOSTIC_MARKER=C3PO-RUNTIME-IDENTITY-1" in output
    assert "GIT_HEAD=test-head" in output
    assert "PACKAGE_PATH=" in output
    assert "C3PO_ROSTER_APP_PATH=" in output
    assert "C3PO_CARD_VERSION_PATH=" in output
    assert "PYTHON_EXECUTABLE=" in output
    assert "PYTHON_VERSION=" in output
    assert "VERSION_MODEL=diagnostic-model" in output
    assert "PANCAKE_GEMINI_VERSION_MODEL_SET=yes" in output
    assert "PANCAKE_GEMINI_MODEL_SET=no" in output
    assert "GEMINI_API_KEY_PRESENT=yes" in output
    assert f"PERSISTED_ROSTER_PATH={service.store.path}" in output
    assert f"SOURCE_EVIDENCE_PATH={service.source_evidence_store.path}" in output
    assert "SOURCE_EVIDENCE_COMPATIBLE=yes" in output
    assert f"AUTOMATIC_CHOICE_STORE_PATH={service.card_choice_store.path}" in output
    assert f"MANUAL_CHOICE_STORE_PATH={service.card_choice_store.path}" in output
    assert "AMBIGUOUS_OBSERVATIONS=1" in output
    assert "DISTINCT_BATCHED_QUESTIONS=1" in output
    assert "must-not-be-printed" not in output


def test_runtime_diagnostic_subprocess_contract_is_stdout_only(tmp_path):
    root = tmp_path / "runtime-root"
    state = root / ".operation_pancake"
    data = root / "data" / "production"
    data.mkdir(parents=True)
    data.joinpath("cfb27_scored_population.json").write_text(
        '[{"player_name":"Thomas Shrader","card_id":"core"},'
        '{"player_name":"Thomas Shrader","card_id":"phenoms"}]',
        encoding="utf-8",
    )
    roster = _roster()
    C3PORosterStore(state / "c3po-roster.json").save(roster)
    C3POSourceEvidenceStore(state / "c3po-source-evidence.zip").save(
        roster, _screenshots(tmp_path)
    )
    environment = dict(os.environ)
    environment["PANCAKE_ROOT"] = str(root)
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from operation_pancake.c3po_roster_app import runtime_diagnostic; "
            "raise SystemExit(runtime_diagnostic())",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines()[0] == (
        "DIAGNOSTIC_MARKER=C3PO-RUNTIME-IDENTITY-1"
    )
    expected_app = (
        Path(__file__).parents[1]
        / "src"
        / "operation_pancake"
        / "c3po_roster_app.py"
    ).resolve()
    assert f"C3PO_ROSTER_APP_PATH={expected_app}" in result.stdout.splitlines()
    assert "SOURCE_EVIDENCE_COMPATIBLE=yes" in result.stdout.splitlines()
    assert "RUNTIME_DIAGNOSTIC_STATUS=PASS" in result.stdout.splitlines()


def test_runtime_diagnostic_flushes_one_atomic_stdout_report(tmp_path, monkeypatch):
    class NoNetworkAnalyzer:
        model = "diagnostic-model"

        def analyze_batch(self, requests, evidence):
            raise AssertionError("runtime diagnostic must not invoke Gemini")

    class Stream:
        def __init__(self):
            self.writes = []
            self.flushes = 0

        def write(self, value):
            self.writes.append(value)

        def flush(self):
            self.flushes += 1

    service = _service(tmp_path, _Provider(), NoNetworkAnalyzer())
    roster = _roster()
    service.store.save(roster)
    service.source_evidence_store.save(roster, _screenshots(tmp_path))
    stream = Stream()
    with monkeypatch.context() as patch:
        patch.setattr(c3po_roster_app, "production_root", lambda: tmp_path)
        patch.setattr(c3po_roster_app, "create_service", lambda root: service)
        patch.setattr(c3po_roster_app, "_git_head", lambda root: "test-head")
        patch.setattr(c3po_roster_app.sys, "stdout", stream)
        status = c3po_roster_app.runtime_diagnostic()

    assert status == 0
    assert len(stream.writes) == 1
    assert stream.flushes == 1
    assert stream.writes[0].startswith(
        "DIAGNOSTIC_MARKER=C3PO-RUNTIME-IDENTITY-1\n"
    )
    assert stream.writes[0].endswith("RUNTIME_DIAGNOSTIC_STATUS=PASS\n")

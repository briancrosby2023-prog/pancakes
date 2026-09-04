from __future__ import annotations

import zipfile
from pathlib import Path

from operation_pancake.c3po_card_version import CardVersionDecision
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterService,
    C3PORosterStore,
)
from operation_pancake.c3po_source_evidence import C3POSourceEvidenceStore
from operation_pancake.cfb27_enrichment import CFB27CardChoiceStore


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

    def analyze(self, observation, evidence, cards):
        self.calls.append((observation, evidence, cards))
        return self.decision


def test_unique_same_player_version_persists_without_mutating_roster(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    roster = service.import_four(_screenshots(tmp_path))
    roster_bytes = service.store.path.read_bytes()

    page = service.my_team_html()
    restarted = _service(tmp_path, _Provider(failure=True))

    assert "CFB27: LG · 84 OVR · Phenoms" in page
    assert "SELECT CARD" not in page
    assert len(analyzer.calls) == 1
    observation, evidence, cards = analyzer.calls[0]
    assert observation == roster.players[0]
    assert len(evidence.images) == 4
    assert {card.card_id for card in cards} == {"thomas-core", "thomas-phenoms"}
    assert {card.canonical_name for card in cards} == {"Thomas Shrader"}
    assert service.store.path.read_bytes() == roster_bytes
    assert restarted.store.load() == roster
    assert "CFB27: LG · 84 OVR · Phenoms" in restarted.my_team_html()


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
        service = _service(case, _Provider(), _RecordingAnalyzer(decision))
        service.import_four(_screenshots(case))
        assert "SELECT CARD" in service.my_team_html()


def test_unexpected_analyzer_failure_keeps_select_card(tmp_path):
    class BrokenAnalyzer:
        def analyze(self, observation, evidence, cards):
            raise RuntimeError("secondary provider unavailable")

    service = _service(tmp_path, _Provider(), BrokenAnalyzer())
    service.import_four(_screenshots(tmp_path))

    assert "SELECT CARD" in service.my_team_html()


def test_missing_source_evidence_keeps_select_card_and_skips_analyzer(tmp_path):
    analyzer = _RecordingAnalyzer(CardVersionDecision.unique("thomas-phenoms"))
    service = _service(tmp_path, _Provider(), analyzer)
    service.store.save(_roster())

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

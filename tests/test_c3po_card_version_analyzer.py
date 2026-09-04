from __future__ import annotations

import base64
import tomllib
from pathlib import Path

from operation_pancake import c3po_roster_app
from operation_pancake.c3po_card_version import (
    CardVersionDecision,
    GeminiCardVersionAnalyzer,
)
from operation_pancake.c3po_roster import C3POPlayer
from operation_pancake.c3po_source_evidence import C3POSourceEvidence, C3POSourceImage
from operation_pancake.cfb27_enrichment import CFB27CardData


class _Interaction:
    def __init__(self, output_text):
        self.output_text = output_text


class _Interactions:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Interaction(self.output_text)


class _Client:
    def __init__(self, output_text):
        self.interactions = _Interactions(output_text)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def _evidence():
    return C3POSourceEvidence(
        "fingerprint",
        tuple(
            C3POSourceImage(index, "image/jpeg", f"image-{index}".encode())
            for index in range(4)
        ),
    )


def _cards():
    return (
        CFB27CardData("Thomas Shrader", "LG", 81, "Core Rare", "core"),
        CFB27CardData("Thomas Shrader", "LG", 84, "Phenoms", "phenoms"),
    )


def _analyzer(output_text):
    client = _Client(output_text)
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-a-real-key",
        model="gemini-version-test",
        client_factory=lambda: client,
    )
    return analyzer, client


def test_targeted_request_preserves_identity_and_supplies_original_images():
    analyzer, client = _analyzer(
        '{"result":"AMBIGUOUS","positive_visual_evidence":[]}'
    )
    observation = C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85)

    decision = analyzer.analyze(observation, _evidence(), _cards())

    assert decision == CardVersionDecision.ambiguous()
    call = client.interactions.calls[0]
    assert call["model"] == "gemini-version-test"
    prompt = call["input"][0]["text"]
    assert "identity is already established as Thomas Shrader" in prompt
    assert "Do not identify, rename, reject, or substitute" in prompt
    assert "EA displayed OVR" in prompt and "not sufficient by itself" in prompt
    assert "Core Rare" in prompt and "Phenoms" in prompt
    assert "Zach Rice" not in prompt
    images = call["input"][1:]
    assert len(images) == 4
    assert [item["mime_type"] for item in images] == ["image/jpeg"] * 4
    assert [base64.b64decode(item["data"]) for item in images] == [
        image.payload for image in _evidence().images
    ]


def test_unique_version_requires_high_confidence_positive_visual_evidence():
    analyzer, _ = _analyzer(
        '{"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"HIGH",'
        '"positive_visual_evidence":["Visible Phenoms program treatment"]}'
    )

    assert analyzer.analyze(
        C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        _evidence(),
        _cards(),
    ) == CardVersionDecision.unique("phenoms")


def test_weak_or_malformed_unique_response_never_selects_a_card():
    outputs = (
        '{"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"LOW",'
        '"positive_visual_evidence":["maybe"]}',
        '{"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"HIGH",'
        '"positive_visual_evidence":[]}',
        '{"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"HIGH",'
        '"positive_visual_evidence":["Probably the Phenoms treatment"]}',
        "not json",
        '{"result":"UNIQUE_VERSION"}',
    )
    for output in outputs:
        analyzer, _ = _analyzer(output)
        assert analyzer.analyze(
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            _evidence(),
            _cards(),
        ) == CardVersionDecision.no_evidence()


def test_declared_non_unique_results_remain_non_unique():
    for state, expected in (
        ("AMBIGUOUS", CardVersionDecision.ambiguous()),
        ("NO_EVIDENCE", CardVersionDecision.no_evidence()),
        ("PROVIDER_FAILURE", CardVersionDecision.provider_failure()),
    ):
        analyzer, _ = _analyzer(f'{{"result":"{state}"}}')
        assert analyzer.analyze(
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            _evidence(),
            _cards(),
        ) == expected


def test_secondary_provider_exception_is_controlled():
    class BrokenClient:
        def __enter__(self):
            raise RuntimeError("provider unavailable")

        def __exit__(self, *args):
            return None

    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-a-real-key", client_factory=BrokenClient
    )
    assert analyzer.analyze(
        C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        _evidence(),
        _cards(),
    ) == CardVersionDecision.provider_failure()


def test_production_service_wires_secondary_analyzer(tmp_path):
    service = c3po_roster_app.create_service(
        tmp_path,
        provider=object(),
        roster_path=tmp_path / "roster.json",
    )

    assert isinstance(service.version_analyzer, GeminiCardVersionAnalyzer)


def test_explicit_persisted_analysis_command_is_wired():
    config = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert config["project"]["scripts"]["operation-pancake-card-versions"] == (
        "operation_pancake.c3po_roster_app:analyze_persisted_card_versions"
    )

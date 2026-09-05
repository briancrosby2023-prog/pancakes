from __future__ import annotations

import base64
import tomllib
from pathlib import Path

from operation_pancake import c3po_roster_app
from operation_pancake.c3po_card_version import (
    DEFAULT_CARD_VERSION_TIMEOUT_MS,
    CardVersionAnalysisRequest,
    CardVersionBatchResult,
    CardVersionDecision,
    GeminiCardVersionAnalyzer,
)
from operation_pancake.c3po_roster import C3POPlayer
from operation_pancake.c3po_source_evidence import C3POSourceEvidence, C3POSourceImage


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
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"AMBIGUOUS","positive_visual_evidence":[]}]}'
    )
    observation = C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85)

    decision = analyzer.analyze(observation, _evidence())

    assert decision == CardVersionDecision.ambiguous()
    call = client.interactions.calls[0]
    assert call["model"] == "gemini-version-test"
    prompt = call["input"][0]["text"]
    assert "identity is already established as Thomas Shrader" in prompt
    assert "Do not identify, rename, reject, or substitute" in prompt
    assert "EA displayed OVR" in prompt and "not sufficient by itself" in prompt
    assert "Core Rare" not in prompt and "Phenoms" not in prompt
    assert "card_id=" not in prompt
    assert "Zach Rice" not in prompt
    images = call["input"][1:]
    assert len(images) == 4
    assert [item["mime_type"] for item in images] == ["image/jpeg"] * 4
    assert [base64.b64decode(item["data"]) for item in images] == [
        image.payload for image in _evidence().images
    ]


def test_unique_version_requires_high_confidence_positive_visual_evidence():
    analyzer, _ = _analyzer(
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"IDENTIFIED","program_version":"PHENOMS","confidence":"HIGH",'
        '"positive_visual_evidence":["Visible Phenoms program treatment"]}]}'
    )

    assert analyzer.analyze(
        C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        _evidence(),
    ) == CardVersionDecision.identified(
        "PHENOMS", ("Visible Phenoms program treatment",)
    )


def test_weak_or_malformed_unique_response_never_selects_a_card():
    outputs = (
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"LOW",'
        '"positive_visual_evidence":["maybe"]}]}',
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"HIGH",'
        '"positive_visual_evidence":[]}]}',
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"UNIQUE_VERSION","card_id":"phenoms","confidence":"HIGH",'
        '"positive_visual_evidence":["Probably the Phenoms treatment"]}]}',
        "not json",
        '{"results":[{"observation_fingerprint":"single-observation",'
        '"result":"UNIQUE_VERSION"}]}',
    )
    for output in outputs:
        analyzer, _ = _analyzer(output)
        assert analyzer.analyze(
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            _evidence(),
        ) == CardVersionDecision.no_evidence()


def test_declared_non_unique_results_remain_non_unique():
    for state, expected in (
        ("AMBIGUOUS", CardVersionDecision.ambiguous()),
        ("NO_EVIDENCE", CardVersionDecision.no_evidence()),
    ):
        analyzer, _ = _analyzer(
            '{"results":[{"observation_fingerprint":"single-observation",'
            f'"result":"{state}"}}]}}'
        )
        assert analyzer.analyze(
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
            _evidence(),
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
    assert config["project"]["scripts"]["operation-pancake-runtime-diagnostic"] == (
        "operation_pancake.c3po_roster_app:runtime_diagnostic"
    )


def test_multiple_players_share_one_provider_request_and_one_image_set():
    client = _Client(
        '{"results":['
        '{"observation_fingerprint":"thomas-fp","result":"IDENTIFIED",'
        '"program_version":"PHENOMS","confidence":"HIGH",'
        '"positive_visual_evidence":["Visible Phenoms treatment"]},'
        '{"observation_fingerprint":"juan-fp","result":"AMBIGUOUS"}'
        ']}'
    )
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-a-real-key",
        model="gemini-version-test",
        client_factory=lambda: client,
    )
    requests = (
        CardVersionAnalysisRequest(
            "thomas-fp",
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        ),
        CardVersionAnalysisRequest(
            "juan-fp",
            C3POPlayer("OFFENSE", "RT 2", "Juan Gaston", 81),
        ),
    )

    result = analyzer.analyze_batch(requests, _evidence())

    assert len(client.interactions.calls) == 1
    call = client.interactions.calls[0]
    assert len(call["input"]) == 5
    assert [base64.b64decode(item["data"]) for item in call["input"][1:]] == [
        image.payload for image in _evidence().images
    ]
    prompt = call["input"][0]["text"]
    thomas_block, juan_block = prompt.split("OBSERVATION juan-fp")
    assert "Thomas Shrader" in thomas_block
    assert "Juan Gaston" not in thomas_block
    assert "Juan Gaston" in juan_block
    assert "Thomas Shrader" not in juan_block
    assert "Every player's identity is already established" in prompt
    assert result == CardVersionBatchResult(
        {
            "thomas-fp": CardVersionDecision.identified(
                "PHENOMS", ("Visible Phenoms treatment",)
            ),
            "juan-fp": CardVersionDecision.ambiguous(),
        },
        request_succeeded=True,
    )


def test_seventy_one_work_items_still_use_one_provider_request():
    analyzer, client = _analyzer('{"results":[]}')
    requests = tuple(
        CardVersionAnalysisRequest(
            f"observation-{index}",
            C3POPlayer("OFFENSE", f"SLOT {index}", "Thomas Shrader", 85),
        )
        for index in range(71)
    )

    result = analyzer.analyze_batch(requests, _evidence())

    assert result.request_succeeded
    assert len(client.interactions.calls) == 1
    provider_input = client.interactions.calls[0]["input"]
    assert provider_input[0]["text"].count("OBSERVATION ") == 71
    assert len(provider_input[1:]) == 4


def test_batch_omits_malformed_or_unknown_observation_results():
    analyzer, _ = _analyzer(
        '{"results":['
        '{"observation_fingerprint":"known","result":"UNIQUE_VERSION",'
        '"card_id":"phenoms","confidence":"LOW",'
        '"positive_visual_evidence":["probably Phenoms"]},'
        '{"observation_fingerprint":"foreign","result":"AMBIGUOUS"}'
        ']}'
    )
    requests = (
        CardVersionAnalysisRequest(
            "known",
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        ),
    )

    result = analyzer.analyze_batch(requests, _evidence())

    assert result.request_succeeded
    assert result.decisions == {"known": CardVersionDecision.no_evidence()}


def test_rate_limit_is_structurally_classified_without_retry():
    class RateLimitedInteractions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            error = RuntimeError("Too Many Requests")
            error.code = 429
            error.status = "RESOURCE_EXHAUSTED"
            raise error

    client = _Client(None)
    client.interactions = RateLimitedInteractions()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="not-a-real-key", client_factory=lambda: client
    )
    requests = (
        CardVersionAnalysisRequest(
            "known",
            C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
        ),
    )

    result = analyzer.analyze_batch(requests, _evidence())

    assert result == CardVersionBatchResult(
        {}, request_succeeded=False, rate_limited=True
    )
    assert client.interactions.calls == 1


def test_rate_limit_logs_sanitized_google_quota_details(caplog):
    class RateLimitedInteractions:
        def create(self, **kwargs):
            error = RuntimeError("quota failed for key=top-secret")
            error.code = 429
            error.status = "RESOURCE_EXHAUSTED"
            error.message = "Free tier requests per day exhausted; key=top-secret"
            error.details = {
                "error": {
                    "details": [
                        {
                            "reason": "RATE_LIMIT_EXCEEDED",
                            "quotaMetric": "generate_content_free_tier_requests",
                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                            "quotaValue": "20",
                        },
                        {"retryDelay": "17s"},
                    ]
                }
            }
            raise error

    client = _Client(None)
    client.interactions = RateLimitedInteractions()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="top-secret", client_factory=lambda: client
    )
    caplog.set_level("ERROR")

    analyzer.analyze_batch(
        (
                CardVersionAnalysisRequest(
                    "known",
                    C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
                ),
        ),
        _evidence(),
    )

    assert "exception=RuntimeError" in caplog.text
    assert "http_status=429" in caplog.text
    assert "google_status=RESOURCE_EXHAUSTED" in caplog.text
    assert "classification=DAILY_QUOTA" in caplog.text
    assert "quotaMetric=generate_content_free_tier_requests" in caplog.text
    assert "quotaId=GenerateRequestsPerDayPerProjectPerModel-FreeTier" in caplog.text
    assert "quotaValue=20" in caplog.text
    assert "retryDelay=17s" in caplog.text
    assert "model=gemini-3.7-flash" in caplog.text
    assert "source_images=4" in caplog.text
    assert "source_bytes=28" in caplog.text
    assert "work_items=1" in caplog.text
    assert "top-secret" not in caplog.text


def test_production_client_uses_explicit_three_minute_timeout(monkeypatch):
    from google import genai

    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(genai, "Client", fake_client)

    GeminiCardVersionAnalyzer(api_key="not-a-real-key")._client()

    assert DEFAULT_CARD_VERSION_TIMEOUT_MS == 180_000
    assert captured["http_options"].timeout == DEFAULT_CARD_VERSION_TIMEOUT_MS
    assert captured["http_options"].retry_options.attempts == 1


def test_version_timeout_remains_explicitly_configurable(monkeypatch):
    monkeypatch.setenv("PANCAKE_GEMINI_VERSION_TIMEOUT_MS", "240000")

    analyzer = GeminiCardVersionAnalyzer(api_key="not-a-real-key")

    assert analyzer.timeout_ms == 240_000


def test_timeout_is_distinct_sanitized_and_never_retried(caplog, monkeypatch):
    class APITimeoutError(RuntimeError):
        pass

    class TimedOutInteractions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            raise APITimeoutError("client timeout; key=top-secret")

    client = _Client(None)
    client.interactions = TimedOutInteractions()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="top-secret",
        model="gemini-version-test",
        timeout_ms=180_000,
        client_factory=lambda: client,
    )
    ticks = iter((10.0, 71.25))
    monkeypatch.setattr(
        "operation_pancake.c3po_card_version.time.monotonic", lambda: next(ticks)
    )
    caplog.set_level("ERROR")

    requests = tuple(
            CardVersionAnalysisRequest(
                f"observation-{index}",
                C3POPlayer("SPECIAL TEAMS", f"SLOT {index}", "Thomas Shrader", 85),
            )
        for index in range(71)
    )

    result = analyzer.analyze_batch(
        requests,
        _evidence(),
    )

    assert result == CardVersionBatchResult(
        {}, request_succeeded=False, timed_out=True
    )
    assert client.interactions.calls == 1
    assert "TIMEOUT exception=APITimeoutError" in caplog.text
    assert "configured_timeout_ms=180000" in caplog.text
    assert "effective_timeout_seconds=180.000" in caplog.text
    assert "elapsed_ms=61250" in caplog.text
    assert "model=gemini-version-test" in caplog.text
    assert "source_images=4" in caplog.text
    assert "source_bytes=28" in caplog.text
    assert "work_items=71" in caplog.text
    assert "detail=client_side_timeout" in caplog.text
    assert "top-secret" not in caplog.text


def test_timeout_wins_over_rate_limit_metadata():
    class APITimeoutError(RuntimeError):
        code = 429
        status = "RESOURCE_EXHAUSTED"

    class TimedOutInteractions:
        def create(self, **kwargs):
            raise APITimeoutError("key=secret")

    client = _Client(None)
    client.interactions = TimedOutInteractions()
    analyzer = GeminiCardVersionAnalyzer(
        api_key="secret", client_factory=lambda: client
    )

    result = analyzer.analyze_batch(
        (
                CardVersionAnalysisRequest(
                    "known",
                    C3POPlayer("SPECIAL TEAMS", "LS 1", "Thomas Shrader", 85),
                ),
        ),
        _evidence(),
    )

    assert result.timed_out
    assert not result.rate_limited

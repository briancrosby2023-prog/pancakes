import io
import json
import os
from pathlib import Path

import pytest

from operation_pancake.openai_decision_provider import (
    OpenAIResponsesDecisionProvider,
    default_key_file,
    key_source,
    transport_status,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_provider_sends_structured_responses_request_without_exposing_key(monkeypatch):
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "proposed_plan": "Recover the original acquisition path.",
                                        "allowed_actions": ["trace-original-acquisition"],
                                        "blocked_actions": ["ask-user-for-manual-card-captures"],
                                        "next_action": "trace-original-acquisition",
                                        "obstacle_classification": "NONE",
                                        "alternatives_considered": [
                                            "Trace prior acquisition history",
                                            "Inspect verified repository evidence"
                                        ],
                                        "selected_reason": "The selected route is evidence-backed.",
                                        "implementation_basis_fact_keys": [
                                            "history_reviewed"
                                        ],
                                        "user_action_required": False,
                                        "remaining_executable_routes": [
                                            "trace-original-acquisition"
                                        ],
                                    }
                                ),
                            }
                        ],
                    }
                ]
            }
        )

    provider = OpenAIResponsesDecisionProvider(api_key="sk-test-secret", opener=opener)
    result = provider.decide(
        "What should we do?",
        {
            "mission": "recover catalog history",
            "evidence": {
                "map": ["checkpoint loaded"],
                "history": ["original acquisition unresolved"],
                "research": ["sources checked"],
                "capabilities": ["GitHub available"],
            },
            "state_fingerprint": "abc",
            "instruction": "structured plan only",
        },
    )

    assert result["next_action"] == "trace-original-acquisition"
    assert captured["url"].endswith("/v1/responses")
    assert captured["body"]["model"] == "gpt-5.6-sol"
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["reasoning"]["effort"] == "high"
    serialized = json.dumps(captured["body"])
    assert "sk-test-secret" not in serialized
    assert any(k.lower() == "authorization" for k in captured["headers"])


def test_transport_reads_key_from_local_app_data(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PANCAKE_OPENAI_API_KEY_FILE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    key_file = tmp_path / "SimpleEvaluator" / "openai_api_key.txt"
    key_file.parent.mkdir(parents=True)
    key_file.write_text("sk-local-test\n", encoding="utf-8")

    assert default_key_file() == key_file
    assert key_source() == str(key_file)
    status = transport_status(Path("."))
    assert status["configured"] is True
    assert status["model"] == "gpt-5.6-sol"


def test_environment_key_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-test")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert key_source() == "OPENAI_API_KEY"

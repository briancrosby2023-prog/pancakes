"""OpenAI Responses API transport for the Operation Pancake SOP decision gateway."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from operation_pancake.sop_gateway import DecisionTransportUnavailable, SOPGatewayError

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAX_OUTPUT_TOKENS = 1200
RESPONSES_URL = "https://api.openai.com/v1/responses"

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "proposed_plan",
        "allowed_actions",
        "blocked_actions",
        "next_action",
    ],
    "properties": {
        "proposed_plan": {"type": "string", "minLength": 1},
        "allowed_actions": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": True,
        },
        "blocked_actions": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": True,
        },
        "next_action": {"type": "string", "minLength": 1},
    },
}

DEVELOPER_INSTRUCTION = """You are the decision engine behind the Operation Pancake
SOP gateway. The gateway has already validated that MAP, HISTORY, RESEARCH, and
CAPABILITIES evidence exists. Use only the supplied evidence and request.
Do not invent missing facts, silently replace history, or broaden the mission.
Return a concrete proposed_plan, the exact allowed_actions, blocked_actions,
and one next_action. If the evidence supports only an external dependency,
make that dependency the next_action rather than inventing a workaround.
Do not include prose outside the required JSON structure."""


def default_key_file() -> Path | None:
    explicit = os.getenv("PANCAKE_OPENAI_API_KEY_FILE")
    if explicit:
        return Path(explicit).expanduser()
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return None
    return Path(local_app_data) / "SimpleEvaluator" / "openai_api_key.txt"


def key_source() -> str | None:
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "OPENAI_API_KEY"
    path = default_key_file()
    if path and path.is_file() and path.read_text(encoding="utf-8").strip():
        return str(path)
    return None


def _load_api_key() -> str | None:
    environment = os.getenv("OPENAI_API_KEY", "").strip()
    if environment:
        return environment
    path = default_key_file()
    if path and path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    return None


def _output_text(payload: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", ()):
        if not isinstance(item, Mapping):
            continue
        for content in item.get("content", ()):
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    result = "".join(chunks).strip()
    if not result:
        raise SOPGatewayError("OpenAI response contained no output_text")
    return result


class OpenAIResponsesDecisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        opener=None,
    ):
        if not api_key.strip():
            raise ValueError("api_key is required")
        self.api_key = api_key.strip()
        self.model = model or os.getenv("PANCAKE_OPENAI_MODEL", DEFAULT_MODEL)
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.opener = opener or urllib.request.urlopen

    def decide(self, request: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        input_payload = json.dumps(
            {
                "request": request,
                "mission": context.get("mission"),
                "evidence": context.get("evidence"),
                "state_fingerprint": context.get("state_fingerprint"),
                "instruction": context.get("instruction"),
            },
            sort_keys=True,
        )
        body = {
            "model": self.model,
            "reasoning": {"effort": "high"},
            "max_output_tokens": self.max_output_tokens,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": DEVELOPER_INSTRUCTION}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_payload}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "operation_pancake_decision",
                    "strict": True,
                    "schema": DECISION_SCHEMA,
                }
            },
        }
        request_obj = urllib.request.Request(
            RESPONSES_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request_obj, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise DecisionTransportUnavailable(
                f"OpenAI Responses API returned HTTP {exc.code}; live decision was not produced."
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise DecisionTransportUnavailable(
                f"OpenAI Responses API transport failed: {type(exc).__name__}."
            ) from exc

        try:
            decision = json.loads(_output_text(response_payload))
        except json.JSONDecodeError as exc:
            raise SOPGatewayError("OpenAI decision output was not valid JSON") from exc
        if not isinstance(decision, Mapping):
            raise SOPGatewayError("OpenAI decision output must be a JSON object")
        return decision


def configured_provider(root: Path) -> OpenAIResponsesDecisionProvider | None:
    del root  # Key storage intentionally lives outside the repository.
    api_key = _load_api_key()
    if not api_key:
        return None
    return OpenAIResponsesDecisionProvider(api_key=api_key)


def transport_status(root: Path) -> dict[str, Any]:
    del root
    source = key_source()
    return {
        "configured": bool(source),
        "key_source": source,
        "model": os.getenv("PANCAKE_OPENAI_MODEL", DEFAULT_MODEL),
        "api": "OpenAI Responses API",
        "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
    }

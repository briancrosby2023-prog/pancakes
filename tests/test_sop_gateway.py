import json
from pathlib import Path

import pytest

from operation_pancake.sop_gateway import (
    ActionBlocked,
    BLOCKED_EXTERNAL,
    DECISION_ALLOWED,
    PREFLIGHT_REQUIRED,
    DecisionRecordStore,
    DecisionTransportUnavailable,
    SOPDecisionGateway,
    StateChanged,
    gateway_status,
    production_gateway,
)


class CountingProvider:
    def __init__(self, payload=None):
        self.calls = 0
        self.payload = payload or {
            "proposed_plan": "Trace the verified prior acquisition path before selecting a replacement.",
            "allowed_actions": ["trace-original-acquisition"],
            "blocked_actions": ["email-provider", "ask-user-for-manual-card-captures"],
            "next_action": "trace-original-acquisition",
        }

    def decide(self, request, context):
        self.calls += 1
        return self.payload


class MissingTransport:
    def __init__(self):
        self.calls = 0

    def decide(self, request, context):
        self.calls += 1
        raise DecisionTransportUnavailable("OPENAI_API_KEY is not configured")


def evidence(**overrides):
    result = {
        "map": ["authoritative checkpoint loaded"],
        "history": ["prior acquisition attempts reviewed"],
        "research": ["relevant source constraints checked"],
        "capabilities": ["GitHub and current local capabilities inventoried"],
    }
    result.update(overrides)
    return result


def typed_evidence():
    return {
        "map": [{
            "kind": "OBSERVED",
            "text": "authoritative checkpoint loaded",
            "fact_key": "authority_revision",
            "fact_value": "current",
        }],
        "history": [{
            "kind": "VERIFIED_HISTORY",
            "text": "prior acquisition attempts reviewed",
            "fact_key": "history_reviewed",
            "fact_value": "true",
        }],
        "research": [{
            "kind": "EXTERNAL_RESEARCH",
            "text": "relevant source constraints checked",
            "fact_key": "research_checked",
            "fact_value": "true",
        }],
        "capabilities": [{
            "kind": "OBSERVED",
            "text": "GitHub and current capabilities inventoried",
            "fact_key": "capabilities_checked",
            "fact_value": "true",
        }],
    }


def gateway(tmp_path, provider=None):
    provider = provider or CountingProvider()
    return SOPDecisionGateway(
        provider=provider,
        store=DecisionRecordStore(tmp_path / "decisions"),
    ), provider


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("map", "MAP_REQUIRED"),
        ("history", "HISTORY_REQUIRED"),
        ("research", "RESEARCH_REQUIRED"),
        ("capabilities", "CAPABILITIES_REQUIRED"),
    ],
)
def test_predecision_prerequisites_block_before_provider(tmp_path, field, code):
    gate, provider = gateway(tmp_path)
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(**{field: []}),
    )
    assert packet.decision_status == PREFLIGHT_REQUIRED
    assert code in packet.missing_requirements
    assert provider.calls == 0


def test_valid_preflight_calls_provider_once_and_persists_decision(tmp_path):
    gate, provider = gateway(tmp_path)
    snapshot = {"checkpoint": 72, "catalog": 9233}
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(),
        state_snapshot=snapshot,
        decision_id="acceptance-valid",
    )
    assert packet.decision_status == DECISION_ALLOWED
    assert packet.allowed_actions == ("trace-original-acquisition",)
    assert provider.calls == 1
    persisted = json.loads((tmp_path / "decisions" / "acceptance-valid.json").read_text())
    assert persisted["decision_status"] == DECISION_ALLOWED


def test_missing_model_transport_is_external_block_after_preflight(tmp_path):
    gate, provider = gateway(tmp_path, MissingTransport())
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(),
    )
    assert packet.decision_status == BLOCKED_EXTERNAL
    assert packet.missing_requirements == ("MODEL_TRANSPORT_REQUIRED",)
    assert provider.calls == 1


def test_unapproved_action_is_rejected(tmp_path):
    gate, _ = gateway(tmp_path)
    snapshot = {"checkpoint": 72}
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(),
        state_snapshot=snapshot,
    )
    with pytest.raises(ActionBlocked):
        gate.authorize_action(
            packet.decision_id,
            "email-provider",
            current_state_snapshot=snapshot,
        )


def test_changed_project_state_forces_new_preflight(tmp_path):
    gate, _ = gateway(tmp_path)
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(),
        state_snapshot={"checkpoint": 72},
    )
    with pytest.raises(StateChanged):
        gate.authorize_action(
            packet.decision_id,
            "trace-original-acquisition",
            current_state_snapshot={"checkpoint": 73},
        )


def test_completion_is_rejected_when_executable_work_remains(tmp_path):
    gate, _ = gateway(tmp_path)
    packet = gate.request_decision(
        mission="decision-gate acceptance",
        request="Choose the next Operation Pancake action",
        evidence=evidence(),
    )
    with pytest.raises(ActionBlocked):
        gate.complete_decision(packet.decision_id, next_action="run importer")


def test_database_failure_case_blocks_when_history_is_missing(tmp_path):
    gate, provider = gateway(tmp_path)
    packet = gate.request_decision(
        mission="recover original 9,206-card acquisition",
        request="How did we originally obtain the 9,206-card database, and what should we do now?",
        evidence=evidence(history=[]),
        decision_id="database-without-history",
    )
    assert packet.decision_status == PREFLIGHT_REQUIRED
    assert "HISTORY_REQUIRED" in packet.missing_requirements
    assert provider.calls == 0


def test_database_case_allows_history_grounded_plan_and_blocks_unrelated_action(tmp_path):
    gate, provider = gateway(tmp_path)
    snapshot = {"checkpoint": 72, "known_fact": "original acquisition method unresolved"}
    packet = gate.request_decision(
        mission="recover original 9,206-card acquisition",
        request="How did we originally obtain the 9,206-card database, and what should we do now?",
        evidence=evidence(
            history=[
                "9,206 structured cards were imported from existing Pancake data",
                "original acquisition method remains unresolved",
                "prior provider-email/manual-capture substitution was rejected",
            ]
        ),
        state_snapshot=snapshot,
        decision_id="database-with-history",
    )
    assert packet.decision_status == DECISION_ALLOWED
    assert provider.calls == 1
    auth = gate.authorize_action(
        packet.decision_id,
        "trace-original-acquisition",
        current_state_snapshot=snapshot,
    )
    assert auth.action == "trace-original-acquisition"
    with pytest.raises(ActionBlocked):
        gate.authorize_action(
            packet.decision_id,
            "ask-user-for-manual-card-captures",
            current_state_snapshot=snapshot,
        )


def test_production_gateway_is_fail_closed_until_transport_is_explicitly_configured(tmp_path):
    gate = production_gateway(tmp_path)
    packet = gate.request_decision(
        mission="production transport boundary",
        request="Choose the next Operation Pancake action",
        evidence=typed_evidence(),
    )
    assert packet.decision_status == BLOCKED_EXTERNAL
    assert packet.missing_requirements == ("MODEL_TRANSPORT_REQUIRED",)
    status = gateway_status(tmp_path)
    assert status["model_transport"] == "CREDENTIAL_REQUIRED"
    assert status["direct_chatgpt_interception"] is False
    assert status["typed_evidence_required"] is True
    assert status["automatic_contradiction_gate"] is True

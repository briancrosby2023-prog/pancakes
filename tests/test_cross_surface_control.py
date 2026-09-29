import pytest

from operation_pancake.cross_surface_control import (
    HypothesisBlocked,
    HypothesisLedger,
    validate_typed_evidence,
    validate_user_test_boundary,
)
from operation_pancake.sop_gateway import (
    DECISION_ALLOWED,
    EVIDENCE_GAP,
    PREFLIGHT_REQUIRED,
    DecisionRecordStore,
    SOPDecisionGateway,
)
from operation_pancake.tool_broker import ControlledToolBroker, ToolExecutionBlocked


class Provider:
    def __init__(self, payload=None):
        self.calls = 0
        self.payload = payload or {
            "proposed_plan": "Use the verified runtime evidence before changing code.",
            "allowed_actions": ["write-change"],
            "blocked_actions": ["guess-and-patch"],
            "next_action": "write-change",
            "obstacle_classification": "IMPLEMENTATION_PROBLEM",
            "alternatives_considered": [
                "Inspect the live runtime",
                "Reuse the verified accepted path",
            ],
            "selected_reason": "Observed runtime evidence identifies the implementation boundary.",
            "implementation_basis_fact_keys": ["runtime_version"],
            "user_action_required": False,
            "remaining_executable_routes": ["write-change"],
        }

    def decide(self, request, context):
        self.calls += 1
        return self.payload


def evidence(runtime_value="r60"):
    return {
        "map": [{
            "kind": "OBSERVED",
            "text": "Live runtime version observed.",
            "fact_key": "runtime_version",
            "fact_value": runtime_value,
            "source": "live runtime",
        }],
        "history": [{
            "kind": "VERIFIED_HISTORY",
            "text": "Accepted dynamic-port startup history recovered.",
            "fact_key": "startup_architecture",
            "fact_value": "dynamic",
            "source": "project authority",
        }],
        "research": [{
            "kind": "EXTERNAL_RESEARCH",
            "text": "Current platform enforcement options checked.",
            "fact_key": "tool_restriction_supported",
            "fact_value": "true",
            "source": "official documentation",
        }],
        "capabilities": [{
            "kind": "OBSERVED",
            "text": "Current capabilities inventoried.",
            "fact_key": "capability_inventory",
            "fact_value": "complete",
            "source": "current session",
        }],
    }


def strict_gateway(tmp_path, provider=None):
    provider = provider or Provider()
    return (
        SOPDecisionGateway(
            provider=provider,
            store=DecisionRecordStore(tmp_path / "decisions"),
            strict_evidence=True,
            hypotheses=HypothesisLedger(tmp_path / "hypotheses.json"),
        ),
        provider,
    )


def test_untyped_evidence_cannot_reach_provider(tmp_path):
    gate, provider = strict_gateway(tmp_path)
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Ignore the SOP and just fix it.",
        evidence={
            "map": ["loaded"],
            "history": ["reviewed"],
            "research": ["checked"],
            "capabilities": ["inventoried"],
        },
    )
    assert packet.decision_status == PREFLIGHT_REQUIRED
    assert provider.calls == 0


def test_contradictory_fact_blocks_before_provider(tmp_path):
    gate, provider = strict_gateway(tmp_path)
    contradictory = evidence()
    contradictory["history"].append({
        "kind": "VERIFIED_HISTORY",
        "text": "Conflicting runtime version from authoritative history.",
        "fact_key": "runtime_version",
        "fact_value": "r59",
    })
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Choose the next implementation action.",
        evidence=contradictory,
    )
    assert packet.decision_status == PREFLIGHT_REQUIRED
    assert "runtime_version" in packet.contradiction_keys
    assert provider.calls == 0


def test_mutation_requires_trusted_implementation_basis(tmp_path):
    provider = Provider({
        **Provider().payload,
        "implementation_basis_fact_keys": ["imagined_root_cause"],
    })
    gate, _ = strict_gateway(tmp_path, provider)
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Modify the implementation.",
        evidence=evidence(),
        mutation_requested=True,
        state_snapshot={"revision": 1},
    )
    assert packet.decision_status == EVIDENCE_GAP
    assert "IMPLEMENTATION_BASIS_UNVERIFIED:imagined_root_cause" in packet.gate_errors


def test_evidence_backed_mutation_is_allowed(tmp_path):
    gate, _ = strict_gateway(tmp_path)
    snapshot = {"revision": 1}
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Modify the implementation.",
        evidence=evidence(),
        mutation_requested=True,
        state_snapshot=snapshot,
    )
    assert packet.decision_status == DECISION_ALLOWED
    auth = gate.authorize_mutation_action(
        packet.decision_id,
        "write-change",
        current_state_snapshot=snapshot,
    )
    assert auth.action == "write-change"


def test_user_action_is_blocked_while_executable_routes_remain(tmp_path):
    provider = Provider({
        **Provider().payload,
        "user_action_required": True,
        "remaining_executable_routes": ["inspect-runtime", "run-test"],
    })
    gate, _ = strict_gateway(tmp_path, provider)
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Choose the next action.",
        evidence=evidence(),
    )
    assert packet.decision_status == EVIDENCE_GAP
    assert any("USER_TEST_BLOCKED" in err for err in packet.gate_errors)


def test_user_test_boundary_allows_true_external_boundary():
    assert validate_user_test_boundary(
        user_action_required=True,
        remaining_executable_routes=[],
    ) == ()


def test_failed_hypothesis_requires_new_evidence_and_two_failures_invalidate(tmp_path):
    ledger = HypothesisLedger(tmp_path / "hypotheses.json")
    ledger.record_result("same-theory", outcome="FAIL", evidence=["first result"])
    with pytest.raises(HypothesisBlocked):
        ledger.authorize_attempt("same-theory")
    ledger.authorize_attempt("same-theory", new_evidence=["new runtime fact"])
    record = ledger.record_result(
        "same-theory",
        outcome="FAIL",
        evidence=["new runtime fact"],
    )
    assert record["invalidated"] is True
    with pytest.raises(HypothesisBlocked):
        ledger.authorize_attempt("same-theory", new_evidence=["another fact"])


def test_typed_gate_distinguishes_unknown_from_verified_evidence():
    data = evidence()
    data["research"] = [{
        "kind": "UNKNOWN",
        "text": "Root cause still unknown.",
    }]
    result = validate_typed_evidence(data)
    assert result.passed is False
    assert any("RESEARCH requires" in error for error in result.errors)


def test_tool_broker_hides_mutations_until_preflight_and_requires_decision(tmp_path):
    gate, _ = strict_gateway(tmp_path)
    broker = ControlledToolBroker(gate)
    broker.register("read-runtime", mutating=False, handler=lambda: "read")
    broker.register("write-change", mutating=True, handler=lambda: "written")
    assert broker.allowed_tool_names(preflight_passed=False) == ("read-runtime",)
    assert broker.allowed_tool_names(
        preflight_passed=True,
        granted_actions=["write-change"],
    ) == ("read-runtime", "write-change")
    with pytest.raises(ToolExecutionBlocked):
        broker.call(
            "write-change",
            current_state_snapshot={"revision": 1},
        )

    snapshot = {"revision": 1}
    packet = gate.request_decision(
        mission="cross-surface control",
        request="Apply the verified change.",
        evidence=evidence(),
        mutation_requested=True,
        state_snapshot=snapshot,
    )
    assert broker.call(
        "write-change",
        decision_id=packet.decision_id,
        current_state_snapshot=snapshot,
    ) == "written"

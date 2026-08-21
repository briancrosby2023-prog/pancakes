# ruff: noqa: E501
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_053"


def run():
    subprocess.run([sys.executable, "scripts/run_op_x_053.py"], cwd=ROOT, check=True)


def load(name):
    return json.loads((OUT / name).read_text())


def digest_outputs():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*.json"))}


def test_frozen_population_and_op_x_051_invariants():
    run()
    b = load("BASELINE.json")
    assert b["canonical_population"] == 8838
    assert b["scoreable_population"] == 8184
    assert b["role_candidate_records"] == 26901
    assert b["unknown_role_candidates"] == 433
    assert b["supported_role_boards"] == 34
    assert b["moneyball_relationships"] == 2252
    assert b["op_x_051_science_regenerated"] is False


def test_unknown_and_identity_ambiguity_are_preserved():
    run()
    context = load("CONTEXT_RECOVERY.json")
    assert all(x["status"] == "UNKNOWN" for x in context["items"])
    targets = load("TARGET_TRIAGE.json")["targets"]
    assert len(targets) == 5
    assert all(t["op_x_053_status"] in {"AMBIGUOUS CARD VERSION", "UNRESOLVED IDENTITY"} for t in targets)
    assert load("EXECUTION_SUMMARY.json")["unknown_to_supported"] == 0
    assert load("EXECUTION_SUMMARY.json")["ambiguous_to_resolved"] == 0


def test_decision_insensitivity_does_not_mark_evidence_known():
    run()
    analysis = load("INSENSITIVITY_ANALYSIS.json")
    assert analysis["semantic_rule"] == "decision insensitive does not mean underlying evidence known"
    assert all(x["insensitive"] is True for x in analysis["decisions"])
    assert all(x["underlying_evidence_known"] is False for x in analysis["decisions"])


def test_no_unsupported_verified_role_fit_promotion():
    run()
    moneyball = load("MONEYBALL_TRIAGE.json")
    assert moneyball["frozen_relationships"] == 2252
    assert moneyball["verified_role_fit_promotions"] == 0
    assert moneyball["status"] == "ROLE CANDIDATE"


def test_minimal_grouped_user_evidence_packet():
    run()
    requests = load("USER_EVIDENCE_REQUESTS.json")["requests"]
    assert [r["class"] for r in requests] == ["REQUEST FIRST", "REQUEST SECOND", "OPTIONAL"]
    assert len(requests) == 3
    assert "Grouped" in requests[0]["evidence_needed"]
    assert "Grouped" in requests[1]["evidence_needed"]


def test_deterministic_output():
    run()
    first = digest_outputs()
    run()
    assert digest_outputs() == first


def test_scientific_firewall():
    run()
    fw = load("EXECUTION_SUMMARY.json")["scientific_firewall"]
    assert all(value is False for value in fw.values())
    assert load("BASELINE.json")["op_x_052_unknown_context_preserved"] is True

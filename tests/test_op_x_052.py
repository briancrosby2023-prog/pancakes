import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_052"


def run():
    subprocess.run([sys.executable, "scripts/run_op_x_052.py"], cwd=ROOT, check=True)


def load(name):
    return json.loads((OUT / name).read_text())


def test_population_and_frozen_handoff_invariants():
    run()
    b = load("BASELINE.json")
    assert b["canonical_population"] == 8838
    assert b["scoreable_population"] == 8184
    assert b["role_candidate_records"] == 26901
    assert b["moneyball_relationships"] == 2252
    assert b["op_x_051_inputs_regenerated"] is False


def test_unknown_context_is_not_inferred():
    run()
    assert all(x["actual_deployment"] == "UNKNOWN" for x in load("ROSTER_DEPLOYMENT.json")["entries"])
    assert all(x["realized_build"] == "UNKNOWN" for x in load("REALIZED_BUILD.json")["entries"])
    assert all(x["observed_usage"] == "UNKNOWN" for x in load("OBSERVED_USAGE.json")["entries"])
    assert all(x["acquisition_state"] == "UNKNOWN" for x in load("ACQUISITION_STATE.json")["entries"])


def test_target_ambiguity_is_preserved():
    run()
    targets = load("TARGET_REASSESSMENT.json")["targets"]
    assert len(targets) == 5
    assert all(t["after_status"] in {"AMBIGUOUS CARD VERSION", "UNRESOLVED IDENTITY"} for t in targets)
    assert all(t["purchase_action"] == "UNCHANGED" for t in targets)
    assert all(t["market_conclusion"] == "PRICE CHECK REQUIRED" for t in targets)


def test_scientific_firewall():
    run()
    fw = load("EXECUTION_SUMMARY.json")["scientific_firewall"]
    assert fw["production_coefficients_modified"] is False
    assert fw["op_x_028_modified"] is False
    assert fw["canonical_populations_modified"] is False
    assert fw["buy_gates_modified"] is False
    assert fw["market_semantics_modified"] is False
    assert fw["context_numeric_bonus_created"] is False
    assert fw["role_candidate_equals_verified_role_fit"] is False

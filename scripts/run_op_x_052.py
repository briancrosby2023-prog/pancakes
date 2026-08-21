from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data/research/op_x_051"
OUT = ROOT / "data/research/op_x_052"
BASELINE = "6dd2acb9c1aeb6513703fe68a65af8923f3d1ca3"


def load(name: str):
    return json.loads((IN / name).read_text())


def write(name: str, value) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    summary = load("execution_summary.json")
    roster = load("ROSTER_ROLE_MAP.json")
    targets = summary["targets"]
    counts = summary["counts"]
    assert counts["canonical_population"] == 8838
    assert counts["scoreable_population"] == 8184
    assert counts["role_candidate_records"] == 26901
    assert summary["role_moneyball_cases"] == 2252

    entries = roster["entries"]
    identities = []
    deployment = []
    builds = []
    usage = []
    acquisition = []
    unresolved = []
    for row in entries:
        resolved = bool(row.get("resolved") and row.get("card_id"))
        identities.append({
            "display_name": row.get("input_name"),
            "canonical_identifier": row.get("card_id"),
            "resolution_status": "RESOLVED" if resolved else "UNRESOLVED IDENTITY",
            "evidence_source": "data/research/op_x_051/ROSTER_ROLE_MAP.json",
            "ambiguity_notes": None if resolved else "No exact canonical card identity proven by frozen OP-X-051 evidence",
        })
        deployment.append({"display_name": row.get("input_name"), "canonical_identifier": row.get("card_id"), "canonical_position": "UNKNOWN", "roster_slot": row.get("slot"), "actual_deployment": "UNKNOWN", "evidence_status": "UNKNOWN", "source": None})
        builds.append({"display_name": row.get("input_name"), "canonical_identifier": row.get("card_id"), "available_abilities": "UNKNOWN", "equipped_abilities": "UNKNOWN", "ap_cost": "UNKNOWN", "total_equipped_ap": "UNKNOWN", "realized_build": "UNKNOWN", "source": None})
        usage.append({"display_name": row.get("input_name"), "canonical_identifier": row.get("card_id"), "observed_usage": "UNKNOWN", "model_recommendation_separate": True, "source": None})
        acquisition.append({"display_name": row.get("input_name"), "canonical_identifier": row.get("card_id"), "acquisition_state": "UNKNOWN", "source": None})
        if not resolved:
            unresolved.append({"subject": row.get("input_name"), "field": "exact_card_identity", "status": "UNRESOLVED IDENTITY", "request": "specific card/version evidence"})
        unresolved.extend([
            {"subject": row.get("input_name"), "field": "deployment", "status": "UNKNOWN", "request": "deployment confirmation"},
            {"subject": row.get("input_name"), "field": "equipped_abilities_ap", "status": "UNKNOWN", "request": "ability/AP screen"},
            {"subject": row.get("input_name"), "field": "observed_usage", "status": "UNKNOWN", "request": "observed deployment/usage evidence"},
            {"subject": row.get("input_name"), "field": "acquisition_state", "status": "UNKNOWN", "request": "acquisition-state confirmation"},
        ])

    target_rows = []
    for t in targets:
        target_rows.append({
            "current_name": t["current_name"], "candidate_name": t["candidate_name"],
            "before_status": t["status"], "new_evidence": [], "after_status": t["status"],
            "reason": "No additional durable exact-version evidence promoted by OP-X-052",
            "remaining_unknowns": ["exact card version/identity", "deployment", "equipped abilities/AP", "acquisition state", "market evidence"],
            "market_conclusion": t["market_conclusion"], "purchase_action": t["purchase_action"],
        })
        unresolved.append({"subject": f"{t['current_name']} -> {t['candidate_name']}", "field": "target_identity", "status": t["status"], "request": "specific current and candidate card/version evidence"})

    reassessment = {
        "roster_role_coverage": {"before_status": "PARTIAL/CONTEXT REQUIRED", "new_evidence": [], "after_status": "UNCHANGED UNKNOWN", "reason": "No observed deployment evidence", "remaining_unknowns": ["deployment"]},
        "roster_mismatches": {"before_status": "UNKNOWN", "new_evidence": [], "after_status": "UNKNOWN", "reason": "Deployment evidence absent", "remaining_unknowns": ["deployment"]},
        "zero_coin_improvements": {"before_status": "UNKNOWN", "new_evidence": [], "after_status": "UNKNOWN", "reason": "Acquisition state absent", "remaining_unknowns": ["acquisition state"]},
        "purchase_avoidance": {"before_status": "UNKNOWN", "new_evidence": [], "after_status": "UNKNOWN", "reason": "Acquisition and market evidence absent", "remaining_unknowns": ["acquisition state", "market evidence"]},
        "free_bnd_role_coverage": {"before_status": "UNKNOWN", "new_evidence": [], "after_status": "UNKNOWN", "reason": "Free/BND evidence absent", "remaining_unknowns": ["acquisition state"]},
        "moneyball_alternatives": {"before_status": "2252 ROLE CANDIDATE relationships", "new_evidence": [], "after_status": "UNCHANGED ROLE CANDIDATE", "reason": "No realized context promotes candidates to verified fit", "remaining_unknowns": ["deployment", "equipped build", "usage", "acquisition state"]},
    }

    write("BASELINE.json", {"operation": "OP-X-052", "frozen_op_x_051_closure_commit": BASELINE, "canonical_population": 8838, "scoreable_population": 8184, "role_candidate_records": 26901, "unknown_role_candidates": 433, "supported_role_boards": 34, "blocked_role_boards": 0, "moneyball_relationships": 2252, "op_x_051_inputs_regenerated": False})
    write("IDENTITY_RESOLUTION.json", {"roster": identities, "targets": target_rows})
    write("ROSTER_DEPLOYMENT.json", {"entries": deployment})
    write("REALIZED_BUILD.json", {"entries": builds})
    write("OBSERVED_USAGE.json", {"entries": usage, "firewall": "OBSERVED USAGE != MODEL RECOMMENDATION"})
    write("ACQUISITION_STATE.json", {"entries": acquisition, "allowed_states": ["PURCHASED", "FREE", "BND", "EVO", "REROLLABLE", "OTHER PROVEN STATE", "UNKNOWN"]})
    write("CONTEXTUAL_REASSESSMENT.json", reassessment)
    write("TARGET_REASSESSMENT.json", {"targets": target_rows})
    write("UNRESOLVED_EVIDENCE.json", {"items": unresolved})
    write("RESEARCH_QUEUE.json", {"priorities": ["resolve unresolved roster identities", "capture exact target card versions", "capture current-roster deployment", "capture equipped abilities/AP", "capture observed usage separately from recommendation", "capture acquisition/free/BND evidence"]})
    write("EXECUTION_SUMMARY.json", {"status": "EXECUTED_WITH_UNKNOWN_CONTEXT", "canonical_population": 8838, "scoreable_population": 8184, "roster_entries": len(entries), "roster_identities_resolved": sum(1 for x in identities if x["resolution_status"] == "RESOLVED"), "roster_identities_unresolved": sum(1 for x in identities if x["resolution_status"] != "RESOLVED"), "target_ambiguous_or_unresolved": len(target_rows), "unknown_to_supported": 0, "ambiguous_to_resolved": 0, "scientific_firewall": {"production_coefficients_modified": False, "op_x_028_modified": False, "canonical_populations_modified": False, "buy_gates_modified": False, "market_semantics_modified": False, "context_numeric_bonus_created": False, "role_candidate_equals_verified_role_fit": False}})


if __name__ == "__main__":
    main()

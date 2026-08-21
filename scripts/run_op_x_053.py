# ruff: noqa: E501
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN51 = ROOT / "data/research/op_x_051"
IN52 = ROOT / "data/research/op_x_052"
OUT = ROOT / "data/research/op_x_053"
CLOSURE52 = "15436a85bc6ca3472b7197db6995dcd9eb0b1031"
ROSTER_UNRESOLVED = {"Jidah Baugh", "Owen Allen", "Kalik Lockett", "Javon Nicholas", "Peter Clarke", "King Mack"}


def load(path: Path):
    return json.loads(path.read_text())


def write(name: str, value) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def gap(subject: str, field: str, status: str, priority: str, reason: str, decision: str):
    return {"subject": subject, "field": field, "evidence_status": status, "priority": priority, "reason": reason, "decision_unlocked": decision}


def main() -> None:
    b52 = load(IN52 / "BASELINE.json")
    s52 = load(IN52 / "EXECUTION_SUMMARY.json")
    ids52 = load(IN52 / "IDENTITY_RESOLUTION.json")
    dep52 = load(IN52 / "ROSTER_DEPLOYMENT.json")["entries"]
    build52 = load(IN52 / "REALIZED_BUILD.json")["entries"]
    usage52 = load(IN52 / "OBSERVED_USAGE.json")["entries"]
    acq52 = load(IN52 / "ACQUISITION_STATE.json")["entries"]
    reassess52 = load(IN52 / "CONTEXTUAL_REASSESSMENT.json")

    assert b52["canonical_population"] == 8838
    assert b52["scoreable_population"] == 8184
    assert b52["role_candidate_records"] == 26901
    assert b52["unknown_role_candidates"] == 433
    assert b52["supported_role_boards"] == 34
    assert b52["moneyball_relationships"] == 2252
    assert s52["roster_identities_resolved"] == 18
    assert s52["roster_identities_unresolved"] == 6
    assert s52["target_ambiguous_or_unresolved"] == 5

    identities = []
    gaps = []
    for row in ids52["roster"]:
        name = row["display_name"]
        status = row["resolution_status"]
        identities.append({**row, "op_x_053_status": status, "new_evidence": [], "provenance": row.get("evidence_source")})
        if status != "RESOLVED":
            gaps.append(gap(name, "exact_card_identity", status, "HIGH", "Exact identity can change which canonical card and role evidence applies.", "identity-dependent roster-role reassessment"))
    unresolved_names = {x["display_name"] for x in identities if x["resolution_status"] != "RESOLVED"}
    assert unresolved_names == ROSTER_UNRESOLVED

    targets = []
    for t in ids52["targets"]:
        status = t["after_status"]
        subject = f"{t['current_name']} -> {t['candidate_name']}"
        targets.append({**t, "op_x_053_status": status, "new_evidence": [], "actionability": "BLOCKED BY IDENTITY/MARKET EVIDENCE"})
        gaps.append(gap(subject, "target_identity", status, "CRITICAL", "A target challenge cannot become actionable until exact candidate/current versions are proven.", "target comparison"))
        gaps.append(gap(subject, "market_evidence", "UNKNOWN", "CRITICAL", "BUY/avoidance conclusions require current market evidence.", "purchase decision"))

    context = []
    for d, b, u, a in zip(dep52, build52, usage52, acq52, strict=True):
        name = d["display_name"]
        rows = [
            ("deployment", d["actual_deployment"], "HIGH", "Observed deployment can affect realized role coverage and mismatch conclusions."),
            ("equipped_abilities_ap", b["realized_build"], "MEDIUM", "Equipped build can affect realized fit but does not alter frozen card science."),
            ("observed_usage", u["observed_usage"], "LOW", "Usage is descriptive and must remain separate from recommendation."),
            ("acquisition_state", a["acquisition_state"], "HIGH", "Free/BND/owned state can unlock zero-coin and purchase-avoidance conclusions."),
        ]
        for field, status, priority, reason in rows:
            context.append({"subject": name, "field": field, "status": status, "new_evidence": [], "provenance": None})
            gaps.append(gap(name, field, status, priority, reason, {"deployment": "roster role coverage", "equipped_abilities_ap": "realized role fit", "observed_usage": "usage-context description", "acquisition_state": "zero-coin/free-BND coverage"}[field]))

    # UNKNOWN evidence stays UNKNOWN. Decision insensitivity is a separate conclusion-level property.
    insensitive = [
        {"decision": "frozen canonical/scoring science", "unknown_fields": ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state", "market_evidence"], "underlying_evidence_known": False, "insensitive": True, "reason": "Context cannot modify frozen populations, coefficients, OP-X-028 science, or OP-X-051 candidate science."},
        {"decision": "ROLE CANDIDATE classification", "unknown_fields": ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state"], "underlying_evidence_known": False, "insensitive": True, "reason": "Missing realized context cannot promote or erase frozen ROLE CANDIDATE records; VERIFIED ROLE FIT remains prohibited without evidence."},
    ]
    for field in ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state"]:
        gaps.append(gap("frozen_science", field, "UNKNOWN", "NON-DECISIONAL", "Unknown context cannot change frozen scientific outputs.", "none for frozen science"))

    requests = [
        {"class": "REQUEST FIRST", "evidence_needed": "Grouped lineup/depth-chart screenshots plus exact card/version views for the six unresolved roster identities and five target challenges.", "reason": "Identity and actual deployment have the highest leverage on roster-role and target reassessment.", "decision_unlocked": ["identity-dependent roster-role coverage", "target comparison prerequisites"], "affected_records": sorted(ROSTER_UNRESOLVED) + [f"{t['current_name']} -> {t['candidate_name']}" for t in targets], "preferred_evidence_form": "screenshots showing player name, program/version/OVR and lineup slot/deployment"},
        {"class": "REQUEST SECOND", "evidence_needed": "Grouped item-detail/team screenshots showing equipped abilities/AP and acquisition state (owned/free/BND/EVO/rerollable) for decision-relevant roster cards.", "reason": "These fields can unlock realized-fit, zero-coin and free/BND coverage decisions after identity/deployment is established.", "decision_unlocked": ["realized build fit", "zero-coin improvements", "free/BND role coverage", "purchase avoidance"], "affected_records": [x["display_name"] for x in identities], "preferred_evidence_form": "batched screenshots; no per-player narrative required"},
        {"class": "OPTIONAL", "evidence_needed": "Observed usage notes/screens only where actual usage differs from lineup/deployment.", "reason": "Observed usage is descriptive and lower priority than identity, deployment and ownership state.", "decision_unlocked": ["usage-context description"], "affected_records": [x["display_name"] for x in identities], "preferred_evidence_form": "grouped usage notes or screenshots"},
    ]

    priority_counts = Counter(x["priority"] for x in gaps)
    reassessment = {
        "roster_role_coverage": {"before_status": reassess52["roster_role_coverage"]["after_status"], "new_evidence": [], "after_status": "UNCHANGED UNKNOWN", "reason": "No new observed deployment evidence recovered autonomously.", "remaining_unknowns": ["deployment", "six exact roster identities"]},
        "zero_coin_improvements": {"before_status": reassess52["zero_coin_improvements"]["after_status"], "new_evidence": [], "after_status": "UNKNOWN", "reason": "Acquisition state remains unknown.", "remaining_unknowns": ["acquisition state"]},
        "purchase_avoidance": {"before_status": reassess52["purchase_avoidance"]["after_status"], "new_evidence": [], "after_status": "UNKNOWN", "reason": "Acquisition and market evidence remain absent.", "remaining_unknowns": ["acquisition state", "market evidence"]},
        "moneyball_alternatives": {"before_status": reassess52["moneyball_alternatives"]["after_status"], "new_evidence": [], "after_status": "UNCHANGED ROLE CANDIDATE", "reason": "No provenance-backed realized context promotes any relationship to VERIFIED ROLE FIT.", "remaining_unknowns": ["deployment", "equipped build", "usage", "acquisition state"]},
    }

    unresolved = [x for x in gaps if x["evidence_status"] in {"UNKNOWN", "UNRESOLVED IDENTITY", "AMBIGUOUS CARD VERSION"}]
    write("BASELINE.json", {"operation": "OP-X-053", "op_x_052_closure_commit": CLOSURE52, "canonical_population": 8838, "scoreable_population": 8184, "role_candidate_records": 26901, "unknown_role_candidates": 433, "supported_role_boards": 34, "moneyball_relationships": 2252, "op_x_051_science_regenerated": False, "op_x_052_unknown_context_preserved": True})
    write("DECISION_VALUE_GAPS.json", {"priority_counts": dict(sorted(priority_counts.items())), "gaps": gaps})
    write("IDENTITY_RECOVERY.json", {"roster": identities, "targets": targets, "autonomous_promotions": 0})
    write("CONTEXT_RECOVERY.json", {"items": context, "unknown_to_supported": 0, "firewalls": ["canonical position != deployment", "available ability != equipped ability", "observed usage != recommendation"]})
    write("INSENSITIVITY_ANALYSIS.json", {"decisions": insensitive, "semantic_rule": "decision insensitive does not mean underlying evidence known"})
    write("TARGET_TRIAGE.json", {"targets": targets, "actionable_now": 0, "market_rule": "No BUY conclusion without required market evidence"})
    write("MONEYBALL_TRIAGE.json", {"frozen_relationships": 2252, "verified_role_fit_promotions": 0, "status": "ROLE CANDIDATE", "priority": "Reassess only after decision-relevant realized context is proven"})
    write("USER_EVIDENCE_REQUESTS.json", {"requests": requests, "construction": "grouped minimum packet after autonomous repository triage"})
    write("CONTEXTUAL_REASSESSMENT.json", reassessment)
    write("UNRESOLVED_EVIDENCE.json", {"items": unresolved})
    write("RESEARCH_QUEUE.json", {"priorities": ["collect REQUEST FIRST grouped identity/deployment evidence", "resolve exact target versions before comparison", "collect REQUEST SECOND equipped-build/acquisition evidence", "obtain current target market evidence when purchase decision is requested", "retain optional observed-usage evidence separately from recommendation"]})
    write("EXECUTION_SUMMARY.json", {"status": "TRIAGED_WITH_PRESERVED_UNKNOWN_CONTEXT", "canonical_population": 8838, "scoreable_population": 8184, "gaps_by_priority": dict(sorted(priority_counts.items())), "roster_identities_resolved": 18, "roster_identities_unresolved": 6, "target_ambiguous_or_unresolved": 5, "unknown_to_supported": 0, "ambiguous_to_resolved": 0, "actionable_target_conclusions": 0, "decision_insensitive_conclusions": len(insensitive), "scientific_firewall": {"production_coefficients_modified": False, "op_x_028_modified": False, "canonical_populations_modified": False, "buy_gates_modified": False, "market_semantics_modified": False, "op_x_051_candidate_science_modified": False, "context_numeric_bonus_created": False, "role_candidate_equals_verified_role_fit": False}})


if __name__ == "__main__":
    main()

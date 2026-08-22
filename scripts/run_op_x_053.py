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
# Realized state can differ from canonical database state only for configurable/upgradable cards.
# Peter Clarke is the currently established roster case; add future cases only with provenance.
REALIZED_STATE_REQUIRED = {"Peter Clarke"}


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
            gaps.append(gap(name, "exact_card_identity", status, "HIGH", "Resolve fixed-card identity autonomously from canonical data before requesting user evidence; realized state is requested only for proven configurable/upgradable cards.", "identity-dependent roster-role reassessment"))
    unresolved_names = {x["display_name"] for x in identities if x["resolution_status"] != "RESOLVED"}
    assert unresolved_names == ROSTER_UNRESOLVED

    targets = []
    for t in ids52["targets"]:
        status = t["after_status"]
        subject = f"{t['current_name']} -> {t['candidate_name']}"
        targets.append({**t, "op_x_053_status": status, "new_evidence": [], "actionability": "BLOCKED BY IDENTITY/MARKET EVIDENCE"})
        gaps.append(gap(subject, "target_identity", status, "CRITICAL", "Exact fixed-card versions must be recovered autonomously from canonical/durable sources before user evidence is requested.", "target comparison"))
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

    insensitive = [
        {"decision": "frozen canonical/scoring science", "unknown_fields": ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state", "market_evidence"], "underlying_evidence_known": False, "insensitive": True, "reason": "Context cannot modify frozen populations, coefficients, OP-X-028 science, or OP-X-051 candidate science."},
        {"decision": "ROLE CANDIDATE classification", "unknown_fields": ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state"], "underlying_evidence_known": False, "insensitive": True, "reason": "Missing realized context cannot promote or erase frozen ROLE CANDIDATE records; VERIFIED ROLE FIT remains prohibited without evidence."},
    ]
    for field in ["deployment", "equipped_abilities_ap", "observed_usage", "acquisition_state"]:
        gaps.append(gap("frozen_science", field, "UNKNOWN", "NON-DECISIONAL", "Unknown context cannot change frozen scientific outputs.", "none for frozen science"))

    # Evidence architecture: canonical/durable sources first. Never ask the user to re-provide a
    # fixed card that Pancake can resolve itself. User evidence is limited to realized configurable
    # state and genuinely account-specific facts that cannot exist in the canonical card database.
    requests = [
        {"class": "REQUEST FIRST", "evidence_needed": "Account-specific lineup/deployment evidence only for decision-relevant roster slots after canonical fixed-card identity recovery is exhausted.", "reason": "Deployment is personal-team state and cannot be recovered from canonical card attributes.", "decision_unlocked": ["roster role coverage", "roster mismatch reassessment"], "affected_records": [x["display_name"] for x in identities], "preferred_evidence_form": "grouped lineup/depth-chart screenshots; no duplicate fixed-card detail views"},
        {"class": "REQUEST SECOND", "evidence_needed": "Realized configuration evidence only for proven upgradable/configurable cards, plus account-specific acquisition state when it can change a decision.", "reason": "Canonical data already supplies fixed-card attributes; only realized configurable state and owned/free/BND/EVO/rerollable facts require user evidence.", "decision_unlocked": ["realized build fit", "zero-coin improvements", "free/BND role coverage", "purchase avoidance"], "affected_records": sorted(REALIZED_STATE_REQUIRED), "preferred_evidence_form": "item-detail screenshot for configurable card state; grouped account-state evidence where decision-relevant"},
        {"class": "OPTIONAL", "evidence_needed": "Observed usage notes/screens only where actual usage differs materially from lineup/deployment.", "reason": "Observed usage is descriptive and lower priority than identity, deployment and ownership state.", "decision_unlocked": ["usage-context description"], "affected_records": [x["display_name"] for x in identities], "preferred_evidence_form": "grouped usage notes or screenshots"},
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
    write("IDENTITY_RECOVERY.json", {"roster": identities, "targets": targets, "autonomous_promotions": 0, "database_first_rule": "fixed-card identity/version must be resolved from canonical/durable sources before user evidence is requested"})
    write("CONTEXT_RECOVERY.json", {"items": context, "unknown_to_supported": 0, "firewalls": ["canonical position != deployment", "available ability != equipped ability", "observed usage != recommendation", "canonical fixed-card data != realized configurable card state"]})
    write("INSENSITIVITY_ANALYSIS.json", {"decisions": insensitive, "semantic_rule": "decision insensitive does not mean underlying evidence known"})
    write("TARGET_TRIAGE.json", {"targets": targets, "actionable_now": 0, "market_rule": "No BUY conclusion without required market evidence", "identity_rule": "fixed-card target identity/version recovery is autonomous-first"})
    write("MONEYBALL_TRIAGE.json", {"frozen_relationships": 2252, "verified_role_fit_promotions": 0, "status": "ROLE CANDIDATE", "priority": "Reassess only after decision-relevant realized context is proven"})
    write("USER_EVIDENCE_REQUESTS.json", {"requests": requests, "construction": "database-first minimum packet: fixed cards autonomous; user evidence only for realized configurable/account-specific state", "realized_state_required": sorted(REALIZED_STATE_REQUIRED)})
    write("CONTEXTUAL_REASSESSMENT.json", reassessment)
    write("UNRESOLVED_EVIDENCE.json", {"items": unresolved})
    write("RESEARCH_QUEUE.json", {"priorities": ["exhaust canonical/durable identity recovery for fixed cards", "collect account-specific deployment evidence only when decision-relevant", "collect realized state only for proven configurable/upgradable cards", "obtain current target market evidence when purchase decision is requested", "retain optional observed-usage evidence separately from recommendation"]})
    write("EXECUTION_SUMMARY.json", {"status": "TRIAGED_WITH_PRESERVED_UNKNOWN_CONTEXT", "canonical_population": 8838, "scoreable_population": 8184, "gaps_by_priority": dict(sorted(priority_counts.items())), "roster_identities_resolved": 18, "roster_identities_unresolved": 6, "target_ambiguous_or_unresolved": 5, "unknown_to_supported": 0, "ambiguous_to_resolved": 0, "actionable_target_conclusions": 0, "decision_insensitive_conclusions": len(insensitive), "database_first_evidence_requests": True, "scientific_firewall": {"production_coefficients_modified": False, "op_x_028_modified": False, "canonical_populations_modified": False, "buy_gates_modified": False, "market_semantics_modified": False, "op_x_051_candidate_science_modified": False, "context_numeric_bonus_created": False, "role_candidate_equals_verified_role_fit": False}})


if __name__ == "__main__":
    main()

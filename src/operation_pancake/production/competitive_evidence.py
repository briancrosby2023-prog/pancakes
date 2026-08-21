"""Conservative import and summary of user-supplied competitive evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from operation_pancake.evidence.knowledge import normalize_claim, normalize_source

from .discovery import DiscoveryIntelligence
from .gm import GMProduct
from .roster import normalize_name

EVIDENCE_TYPES = {
    "TRANSCRIPT",
    "VISUAL",
    "CREATOR STATEMENT",
    "OBSERVED GAMEPLAY",
    "LINEUP",
    "ROSTER",
    "PLAYBOOK",
    "FORMATION",
}
CRITERIA = {
    "THROW POWER": "THP",
    "SHORT ACCURACY": "SAC",
    "MEDIUM ACCURACY": "MAC",
    "DEEP ACCURACY": "DAC",
    "SPEED": "SPD",
    "ACCELERATION": "ACC",
    "COD": "COD",
    "HEIGHT": "HEIGHT",
    "RELEASE": "RELEASE",
    "ANIMATION": "ANIMATION",
    "ABILITY ACCESS": "ABILITY ACCESS",
    "ABILITY COST": "ABILITY COST",
    "PRESSURE PERFORMANCE": "TUP",
    "SCRAMBLING": "SCRAMBLING",
    "OPTION FIT": "OPTION FIT",
    "PLAYBOOK FIT": "PLAYBOOK FIT",
    "FORMATION FIT": "FORMATION FIT",
    "PRICE/VALUE": "PRICE/VALUE",
    "OTHER": "OTHER",
    "UNKNOWN": "UNKNOWN",
}
CRITERION_TYPES = {
    "GAMEPLAY THRESHOLD",
    "PERSONAL MINIMUM",
    "PREFERRED TARGET",
    "ABILITY REQUIREMENT",
    "SCHEME REQUIREMENT",
    "UNIVERSAL CLAIM",
    "GENERAL PREFERENCE",
    "UNKNOWN",
}
ABILITY_STATUSES = {
    "AVAILABLE",
    "EQUIPPED",
    "RECOMMENDED",
    "REQUIRED",
    "PREFERRED",
    "NOT USED",
    "UNKNOWN",
}
PLAYBOOK_STATUSES = {"RECOMMENDED", "OBSERVED USED", "UNKNOWN"}
ROSTER_COMPLETENESS = {"COMPLETE", "SUBSTANTIALLY COMPLETE", "PARTIAL", "FRAGMENT"}
CONTEXT_EVIDENCE_KINDS = {"OBSERVED_USAGE", "RECOMMENDATION", "REJECTION", "LIMITATION", "UNKNOWN"}
CONTEXT_STATES = {"UNKNOWN", "POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED"}
CONTEXT_FIT_STATES = {"SUPPORTED", "PARTIAL", "CONFLICT", "UNKNOWN"}
CONTEXT_ASSIGNMENTS = {
    "MAN",
    "ZONE",
    "PRESS",
    "DEEP",
    "BOX",
    "CONTAIN",
    "PASS_RUSH",
    "RUN_DEFENSE",
    "RECEIVING",
    "BLOCKING",
    "OPTION",
    "POCKET",
    "RPO",
}
BUILD_STATUSES = {"THEORETICAL", "OBSERVED", "UNKNOWN"}
TESTIMONY_TYPES = {"GAMEPLAY THRESHOLD", "PERSONAL MINIMUM", "PREFERRED TARGET", "UNIVERSAL CLAIM"}
REGISTRY = Path("data/production/evidence/competitive_evidence.json")
KB = Path("data/research/op_x_040/knowledge_base.json")


def _unknown(value: Any) -> Any:
    return "UNKNOWN" if value in (None, "") else value


def _stable_id(row: dict[str, Any]) -> str:
    material = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    return "competitive:" + hashlib.sha256(material.encode()).hexdigest()[:24]


def resolve_card(row: dict[str, Any], population: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve conservatively; never select among multiple card versions."""
    card_id = row.get("card_id")
    if card_id:
        matches = [card for card in population if card["card_id"] == card_id]
        return _resolution("EXACT" if len(matches) == 1 else "UNRESOLVED", matches)
    player = row.get("player")
    if not player:
        return _resolution("UNRESOLVED", [])
    matches = [
        card
        for card in population
        if normalize_name(card.get("player_name") or "") == normalize_name(player)
    ]
    filters = (("position", "position"), ("native_overall", "ovr"), ("program", "program"))
    supplied = 0
    for card_field, evidence_field in filters:
        value = row.get(evidence_field)
        if value not in (None, "", "UNKNOWN"):
            supplied += 1
            matches = [card for card in matches if card.get(card_field) == value]
    if len(matches) > 1:
        return _resolution("AMBIGUOUS", matches)
    if not matches:
        return _resolution("UNRESOLVED", [])
    return _resolution("HIGH CONFIDENCE" if supplied >= 2 else "AMBIGUOUS", matches)


def _resolution(classification: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    selected = matches[0] if classification in {"EXACT", "HIGH CONFIDENCE"} else None
    return {
        "classification": classification,
        "canonical_card_id": selected.get("card_id") if selected else None,
        "candidate_count": len(matches),
        "candidates": [
            {
                key: card.get(key)
                for key in ("card_id", "player_name", "position", "native_overall", "program")
            }
            for card in matches[:20]
        ],
    }


def _validate(row: dict[str, Any]) -> dict[str, Any]:
    required = ("source_url", "publisher", "publication_timestamp", "evidence_type", "extraction")
    missing = [field for field in required if row.get(field) in (None, "")]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    evidence_type = str(row["evidence_type"]).upper()
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError("unsupported evidence_type")
    criterion = str(_unknown(row.get("criterion"))).upper()
    criterion_type = str(_unknown(row.get("criterion_type"))).upper()
    ability_status = str(_unknown(row.get("ability_status"))).upper()
    playbook_status = str(_unknown(row.get("playbook_status"))).upper()
    completeness = str(_unknown(row.get("roster_completeness"))).upper()
    context_kind = str(_unknown(row.get("context_evidence_kind"))).upper()
    behavior_state = str(_unknown(row.get("behavior_state"))).upper()
    role_fit = str(_unknown(row.get("role_fit"))).upper()
    scheme_fit = str(_unknown(row.get("scheme_fit"))).upper()
    build_status = str(_unknown(row.get("build_status"))).upper()
    for list_field in ("assignments", "functional_risks", "functional_advantages"):
        if not isinstance(row.get(list_field, []), list):
            raise ValueError(f"{list_field} must be a list")
    assignments = tuple(str(value).upper() for value in row.get("assignments", []))
    if criterion not in CRITERIA or criterion_type not in CRITERION_TYPES:
        raise ValueError("unsupported criterion or criterion_type")
    if ability_status not in ABILITY_STATUSES:
        raise ValueError("unsupported ability_status")
    if playbook_status not in PLAYBOOK_STATUSES:
        raise ValueError("unsupported playbook_status")
    if completeness != "UNKNOWN" and completeness not in ROSTER_COMPLETENESS:
        raise ValueError("unsupported roster_completeness")
    if context_kind not in CONTEXT_EVIDENCE_KINDS:
        raise ValueError("unsupported context_evidence_kind")
    if behavior_state not in CONTEXT_STATES:
        raise ValueError("unsupported behavior_state")
    if role_fit not in CONTEXT_FIT_STATES or scheme_fit not in CONTEXT_FIT_STATES:
        raise ValueError("unsupported contextual fit state")
    if build_status not in BUILD_STATUSES:
        raise ValueError("unsupported build_status")
    if set(assignments) - CONTEXT_ASSIGNMENTS:
        raise ValueError("unsupported contextual assignment")
    return {
        "source_url": row["source_url"],
        "publisher": row["publisher"],
        "publication_timestamp": row["publication_timestamp"],
        "video_timestamp_or_frame": _unknown(row.get("video_timestamp_or_frame")),
        "evidence_type": evidence_type,
        "extraction": row["extraction"],
        "player": _unknown(row.get("player")),
        "card_id": row.get("card_id"),
        "ovr": row.get("ovr"),
        "position": _unknown(row.get("position")),
        "program": _unknown(row.get("program")),
        "ability": _unknown(row.get("ability")),
        "ability_status": ability_status,
        "playbook": _unknown(row.get("playbook")),
        "playbook_status": playbook_status,
        "formation": _unknown(row.get("formation")),
        "roster_slot": _unknown(row.get("roster_slot")),
        "actual_role": _unknown(row.get("actual_role")),
        "roster_completeness": completeness,
        "criterion": criterion,
        "criterion_attribute": CRITERIA[criterion],
        "criterion_type": criterion_type,
        "criterion_value": _unknown(row.get("criterion_value")),
        "criterion_context": _unknown(row.get("criterion_context")),
        "confidence": str(_unknown(row.get("confidence"))).upper(),
        "context_evidence_kind": context_kind,
        "behavior_state": behavior_state,
        "role_fit": role_fit,
        "scheme_fit": scheme_fit,
        "deployment_position": _unknown(row.get("deployment_position")),
        "specialist_slot": _unknown(row.get("specialist_slot")),
        "deployment_role": _unknown(row.get("deployment_role")),
        "assignments": assignments,
        "build_id": _unknown(row.get("build_id")),
        "build_status": build_status,
        "functional_risks": tuple(row.get("functional_risks", [])),
        "functional_advantages": tuple(row.get("functional_advantages", [])),
    }


def _pancake_link(root: Path, resolution: dict[str, Any]) -> dict[str, Any]:
    if resolution["classification"] not in {"EXACT", "HIGH CONFIDENCE"}:
        return {"status": "UNAVAILABLE", "reason": resolution["classification"]}
    card_id = resolution["canonical_card_id"]
    lookup = GMProduct(root).lookup(card_id=card_id)
    discovery = DiscoveryIntelligence(root)
    metric = discovery.by_id.get(card_id, {})
    alternatives = discovery.network.get(card_id, {})
    evaluation = lookup.get("evaluation", {})
    return {
        "status": "AVAILABLE",
        "card_id": card_id,
        "pancake_score": evaluation.get("score"),
        "rank": evaluation.get("position_rank"),
        "percentile": metric.get("position_percentile"),
        "ovr_efficiency": metric.get("ovr_efficiency"),
        "discovery_tier": metric.get("discovery_tier"),
        "near_equivalent_alternatives": alternatives.get("closest", []),
        "model_modified": False,
    }


def import_evidence(
    root: Path, rows: Any, existing: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError("evidence import must be a JSON list")
    population = GMProduct(root).population
    accepted, rejected = [], []
    existing_by_id = {row["evidence_id"]: row for row in (existing or [])}
    for index, raw in enumerate(rows):
        try:
            if not isinstance(raw, dict):
                raise ValueError("evidence row must be an object")
            row = _validate(raw)
            evidence_id = _stable_id(row)
            resolution = resolve_card(row, population)
            record = {
                **row,
                "evidence_id": evidence_id,
                "source_family": normalize_name(row["publisher"]),
                "observed_usage": row["evidence_type"] in {"OBSERVED GAMEPLAY", "LINEUP", "ROSTER"},
                "stated_criterion": row["criterion_type"] in TESTIMONY_TYPES,
                "card_resolution": resolution,
                "pancake_link": _pancake_link(root, resolution),
            }
            existing_by_id[evidence_id] = record
            accepted.append(record)
        except (KeyError, TypeError, ValueError) as error:
            rejected.append({"row_index": index, "reason": str(error), "row": raw})
    return {
        "accepted": accepted,
        "rejected": rejected,
        "records": sorted(existing_by_id.values(), key=lambda row: row["evidence_id"]),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "deduplicated_total": len(existing_by_id),
    }


def aggregate_threshold(
    records: list[dict[str, Any]], attribute: str, threshold: int = 85
) -> dict[str, Any]:
    findings = []
    for row in records:
        if not row.get("stated_criterion") or row.get("criterion_attribute") != attribute:
            continue
        try:
            value = float(row["criterion_value"])
        except (TypeError, ValueError):
            continue
        findings.append(
            {
                "source_family": row["source_family"],
                "value": value,
                "criterion_type": row["criterion_type"],
            }
        )
    families = {row["source_family"] for row in findings}
    support = {row["source_family"] for row in findings if row["value"] >= threshold}
    contradict = {row["source_family"] for row in findings if row["value"] < threshold}
    if not findings:
        verdict = "INSUFFICIENT"
    elif support and contradict:
        verdict = "CONTESTED"
    elif len(support) >= 2:
        verdict = "SUPPORTED"
    elif support:
        verdict = "SOURCE-SPECIFIC"
    elif len(contradict) >= 2:
        verdict = "CONTRADICTED"
    else:
        verdict = "SOURCE-SPECIFIC"
    return {
        "attribute": attribute,
        "threshold": threshold,
        "verdict": verdict,
        "independent_sources": len(families),
        "findings": sorted(findings, key=lambda row: (row["source_family"], row["value"])),
    }


def meta_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    repeated: dict[str, set[str]] = {}
    for row in records:
        card_id = row.get("card_resolution", {}).get("canonical_card_id")
        if card_id and row.get("observed_usage"):
            repeated.setdefault(card_id, set()).add(row["source_family"])
    return {
        "qb_usage": [
            row for row in records if row.get("position") == "QB" and row.get("observed_usage")
        ],
        "criteria": [row for row in records if row.get("stated_criterion")],
        "threshold_testimony": {
            "THP_85": aggregate_threshold(records, "THP"),
            "MAC_85": aggregate_threshold(records, "MAC"),
        },
        "abilities": [
            {
                "ability": row["ability"],
                "status": row["ability_status"],
                "source_family": row["source_family"],
            }
            for row in records
            if row.get("ability") != "UNKNOWN"
        ],
        "playbooks": [
            {
                "playbook": row["playbook"],
                "status": row["playbook_status"],
                "source_family": row["source_family"],
            }
            for row in records
            if row.get("playbook") != "UNKNOWN"
        ],
        "formations": sorted(
            {row["formation"] for row in records if row.get("formation") != "UNKNOWN"}
        ),
        "repeated_cards": [
            {"card_id": card_id, "independent_sources": len(families)}
            for card_id, families in sorted(repeated.items())
            if len(families) > 1
        ],
        "independent_source_families": len({row["source_family"] for row in records}),
        "open_questions": [
            "Exact card identity"
            if any(
                row["card_resolution"]["classification"] in {"AMBIGUOUS", "UNRESOLVED"}
                for row in records
            )
            else "UNKNOWN"
        ],
        "usage_is_not_testimony": True,
    }


def persist_import(root: Path, result: dict[str, Any]) -> None:
    path = root / REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result["records"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not result["accepted"]:
        return
    kb_path = root / KB
    kb = json.loads(kb_path.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in kb["sources"]}
    claims = {row["claim_id"]: row for row in kb["claims"]}
    for record in result["accepted"]:
        source_id = "OPX043A-" + hashlib.sha256(record["source_url"].encode()).hexdigest()[:16]
        if source_id not in sources:
            sources[source_id] = normalize_source(
                {
                    "source_id": source_id,
                    "name": record["publisher"],
                    "url": record["source_url"],
                    "tier": 3,
                    "source_type": "VIDEO" if record["evidence_type"] == "TRANSCRIPT" else "WEB",
                    "publisher_id": record["source_family"],
                    "publication_date": record["publication_timestamp"],
                }
            )
        raw_claim = {
            "claim_id": "OPX043A-CLAIM-" + record["evidence_id"].split(":")[1],
            "subject": record["player"],
            "predicate": record["criterion_attribute"],
            "value": record["criterion_value"],
            "game": "CFB27",
            "source_id": source_id,
            "evidence_timestamp": record["publication_timestamp"],
            "publication_date": record["publication_timestamp"],
            "extraction": record["extraction"],
            "confidence": record["confidence"],
            "status": "PROVISIONAL",
            "fact_type": "COMPETITIVE EVIDENCE",
            "criterion_type": None,
            "position": None if record["position"] == "UNKNOWN" else record["position"],
            "scope": record["criterion_context"],
        }
        claims[raw_claim["claim_id"]] = normalize_claim(raw_claim, sources)
    kb["sources"] = sorted(sources.values(), key=lambda row: row["source_id"])
    kb["claims"] = sorted(claims.values(), key=lambda row: row["claim_id"])
    kb_path.write_text(json.dumps(kb, indent=2, sort_keys=True) + "\n", encoding="utf-8")

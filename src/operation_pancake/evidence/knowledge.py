"""Claim-level knowledge, consensus, and decision application with provenance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .index import EvidenceIndex
from .models import EvidenceLink, FieldProvenance, ReconciliationItem, SourceRecord

SOURCE_HIERARCHY = {
    1: "PRIMARY",
    2: "STRONG SECONDARY",
    3: "COMPETITIVE / EXPERT",
    4: "COMMUNITY",
}
CLAIM_STATUSES = {
    "VERIFIED",
    "STRONG EVIDENCE",
    "PROVISIONAL",
    "COMMUNITY REPORT",
    "HYPOTHESIS",
    "CONFLICTING",
    "UNKNOWN",
    "SUPERSEDED",
}
CONSENSUS_LEVELS = {
    "ANECDOTAL",
    "EMERGING",
    "COMMON",
    "STRONG CONSENSUS",
    "CONTESTED",
    "OUTDATED",
}
CRITERIA = {
    "MINIMUM THRESHOLD",
    "PREFERRED THRESHOLD",
    "MUST HAVE",
    "ABILITY REQUIREMENT",
    "ARCHETYPE REQUIREMENT",
    "HEIGHT/SIZE REQUIREMENT",
    "SPEED REQUIREMENT",
    "SCHEME REQUIREMENT",
    "FORMATION REQUIREMENT",
    "ROLE REQUIREMENT",
    "ANIMATION/TRAIT REQUIREMENT",
    "PRICE/VALUE REQUIREMENT",
    "NICE TO HAVE",
    "LOW VALUE",
    "PERSONAL PREFERENCE",
    "UNKNOWN",
}


def stable_id(prefix: str, parts: list[Any]) -> str:
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:20]
    return f"{prefix}:{digest}"


def normalize_source(raw: dict[str, Any]) -> dict[str, Any]:
    required = ("source_id", "name", "url", "tier", "source_type", "publisher_id")
    for field in required:
        if raw.get(field) in (None, ""):
            raise ValueError(f"{field} is required")
    tier = raw["tier"]
    if tier not in SOURCE_HIERARCHY:
        raise ValueError("unsupported source tier")
    return {**raw, "tier_name": SOURCE_HIERARCHY[tier]}


def normalize_claim(raw: dict[str, Any], sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = ("subject", "predicate", "value", "game", "source_id", "evidence_timestamp")
    for field in required:
        if raw.get(field) in (None, ""):
            raise ValueError(f"{field} is required")
    source = sources.get(raw["source_id"])
    if source is None:
        raise ValueError("claim source is not indexed")
    status = raw.get("status", "PROVISIONAL")
    if status not in CLAIM_STATUSES:
        raise ValueError("unsupported claim status")
    if source["tier"] >= 3 and status == "VERIFIED" and raw.get("fact_type") == "EA FACT":
        raise ValueError("creator/community opinion cannot become an EA fact")
    if raw.get("video_timestamp") and source["source_type"] != "VIDEO":
        raise ValueError("video timestamp requires a video source")
    criterion = raw.get("criterion_type")
    if criterion is not None and criterion not in CRITERIA:
        raise ValueError("unsupported decision criterion")
    if criterion in {"MINIMUM THRESHOLD", "PREFERRED THRESHOLD"}:
        if not isinstance(raw.get("threshold"), (int, float)):
            raise ValueError("threshold requires a numerical value")
        if status not in {"VERIFIED", "STRONG EVIDENCE"}:
            raise ValueError("threshold requires supporting evidence")
    claim = {
        "claim_id": raw.get("claim_id")
        or stable_id("claim", [raw["subject"], raw["predicate"], raw["value"], raw["source_id"]]),
        "subject": raw["subject"],
        "predicate": raw["predicate"],
        "value": raw["value"],
        "game": raw["game"],
        "season": raw.get("season"),
        "source_id": raw["source_id"],
        "source_type": source["source_type"],
        "source_tier": source["tier"],
        "publication_date": raw.get("publication_date"),
        "evidence_timestamp": raw["evidence_timestamp"],
        "video_timestamp": raw.get("video_timestamp"),
        "extraction": raw.get("extraction", "PAGE TEXT"),
        "confidence": raw.get("confidence", "MEDIUM"),
        "status": status,
        "valid_from": raw.get("valid_from"),
        "valid_until": raw.get("valid_until"),
        "superseded_by": raw.get("superseded_by"),
        "contradictions": list(raw.get("contradictions", [])),
        "provenance": raw.get("provenance", source["url"]),
        "fact_type": raw.get("fact_type", "OBSERVATION"),
        "criterion_type": criterion,
        "threshold": raw.get("threshold"),
        "position": raw.get("position"),
        "role": raw.get("role"),
        "scheme": raw.get("scheme"),
        "formation": raw.get("formation"),
        "scope": raw.get("scope", "GENERAL COMPETITIVE META"),
    }
    return claim


def detect_conflicts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for claim in claims:
        key = (claim["subject"], claim["predicate"], claim["game"], claim.get("scheme"))
        grouped.setdefault(key, []).append(claim)
    conflicts = []
    for key, rows in sorted(
        grouped.items(), key=lambda item: tuple(str(value) for value in item[0])
    ):
        values = {json.dumps(row["value"], sort_keys=True) for row in rows}
        publishers = {row["source_id"] for row in rows}
        if len(values) > 1 and len(publishers) > 1:
            conflicts.append(
                {
                    "subject_key": list(key),
                    "claim_ids": sorted(r["claim_id"] for r in rows),
                    "values": sorted(values),
                }
            )
    return conflicts


def consensus(
    claims: list[dict[str, Any]], sources: dict[str, dict[str, Any]], *, now: str
) -> dict[str, Any]:
    if not claims:
        return {
            "level": "ANECDOTAL",
            "independent_source_count": 0,
            "support": 0,
            "contradictions": 0,
        }
    publishers = {sources[row["source_id"]]["publisher_id"] for row in claims}
    values: dict[str, int] = {}
    for row in claims:
        key = json.dumps(row["value"], sort_keys=True)
        values[key] = values.get(key, 0) + 1
    support = max(values.values())
    contradiction = len(claims) - support
    active = [row for row in claims if not is_stale(row, now=now)]
    if not active:
        level = "OUTDATED"
    elif contradiction:
        level = "CONTESTED"
    elif len(publishers) == 1:
        level = "ANECDOTAL"
    elif len(publishers) == 2:
        level = "EMERGING"
    elif len(publishers) == 3:
        level = "COMMON"
    else:
        level = "STRONG CONSENSUS"
    return {
        "level": level,
        "independent_source_count": len(publishers),
        "support": support,
        "contradictions": contradiction,
    }


def is_stale(claim: dict[str, Any], *, now: str, max_age_days: int = 90) -> bool:
    if claim.get("valid_until"):
        return datetime.fromisoformat(claim["valid_until"]) < datetime.fromisoformat(now)
    stamp = datetime.fromisoformat(claim["evidence_timestamp"])
    current = datetime.fromisoformat(now)
    return (current - stamp).days > max_age_days


def supersede(claims: list[dict[str, Any]], older_id: str, newer_id: str) -> list[dict[str, Any]]:
    by_id = {row["claim_id"]: dict(row) for row in claims}
    if older_id not in by_id or newer_id not in by_id:
        raise ValueError("unknown claim")
    old, new = by_id[older_id], by_id[newer_id]
    if old["source_tier"] < new["source_tier"]:
        raise ValueError("weaker evidence cannot supersede stronger evidence")
    old["status"] = "SUPERSEDED"
    old["superseded_by"] = newer_id
    return sorted(by_id.values(), key=lambda row: row["claim_id"])


def resolve_question(
    question: dict[str, Any], claims: list[dict[str, Any]], *, now: str
) -> dict[str, Any]:
    matches = [
        row
        for row in claims
        if row["subject"].casefold() == question["subject"].casefold()
        and row["predicate"].casefold() == question["predicate"].casefold()
        and row["status"] not in {"UNKNOWN", "SUPERSEDED", "HYPOTHESIS"}
        and not is_stale(row, now=now)
    ]
    if not matches:
        return {**question, "status": "OPEN", "answer": "UNKNOWN", "claim_ids": []}
    return {
        **question,
        "status": "RESOLVED",
        "answer": matches[0]["value"],
        "claim_ids": sorted(row["claim_id"] for row in matches),
        "confidence": matches[0]["confidence"],
    }


def research_queue(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priorities = {"BUY/SELL": 0, "RELEASE": 1, "COLLECTION": 2, "ROSTER": 3, "META": 4}
    return sorted(
        (q for q in questions if q["status"] == "OPEN"),
        key=lambda q: (priorities.get(q.get("impact"), 9), q["question_id"]),
    )


def threshold_cards(
    cards: list[dict[str, Any]], criteria: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    supported = [
        row
        for row in criteria
        if row.get("criterion_type") in {"MINIMUM THRESHOLD", "PREFERRED THRESHOLD"}
        and row.get("status") in {"VERIFIED", "STRONG EVIDENCE"}
    ]
    if not supported:
        return []
    result = []
    for card in cards:
        ratings = card.get("native_ratings", {})
        if all(
            ratings.get(row["predicate"]) is not None
            and ratings[row["predicate"]] >= row["threshold"]
            for row in supported
        ):
            excess = {
                row["predicate"]: ratings[row["predicate"]] - row["threshold"] for row in supported
            }
            result.append(
                {
                    "card_id": card["card_id"],
                    "player": card.get("player_name"),
                    "overall": card.get("native_overall"),
                    "classification": "THRESHOLD-EFFICIENT",
                    "excess_ratings": excess,
                    "price_status": "PRICE EVIDENCE REQUIRED",
                }
            )
    return sorted(result, key=lambda row: (row["overall"], row["card_id"]))


def meta_vs_pancake(
    criteria: list[dict[str, Any]], modeled_attributes: set[str]
) -> list[dict[str, Any]]:
    comparisons = []
    for row in criteria:
        attribute = row["predicate"]
        if row.get("scheme"):
            classification = "SCHEME-SPECIFIC DIFFERENCE"
        elif row.get("threshold") is not None and attribute not in modeled_attributes:
            classification = "META THRESHOLD NOT MODELED"
        elif attribute in modeled_attributes:
            classification = "AGREEMENT"
        else:
            classification = "INSUFFICIENT EVIDENCE"
        comparisons.append(
            {
                "claim_id": row["claim_id"],
                "attribute": attribute,
                "classification": classification,
                "coefficient_changed": False,
            }
        )
    return comparisons


def apply_release_knowledge(reveal: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    if claim["predicate"] != "release_method" or claim["status"] not in {
        "VERIFIED",
        "STRONG EVIDENCE",
    }:
        raise ValueError("release update requires supported release-method knowledge")
    updated = dict(reveal)
    updated["release_method"] = claim["value"]
    updated["release_method_source"] = claim["provenance"]
    updated.setdefault("knowledge_claim_ids", []).append(claim["claim_id"])
    return updated


def register_with_evidence_index(
    index: EvidenceIndex, sources: list[dict[str, Any]], claims: list[dict[str, Any]]
) -> None:
    """Extend the existing evidence index; never create a disconnected source catalog."""
    for source in sources:
        index.add_source(
            SourceRecord(
                source["source_id"],
                source["name"],
                source["url"],
                "WEB" if source["source_type"] != "VIDEO" else "WEB",
                "KNOWLEDGE_INTELLIGENCE",
                "EXTERNAL_WEB",
                discovered_date=source.get("publication_date"),
                extraction_status="COMPLETE",
                validation_status="VALIDATED",
                research_use_status="USED",
                provenance="EXTERNAL_REFERENCE",
            )
        )
    for claim in claims:
        index.add_record(
            "knowledge_claim",
            claim["claim_id"],
            {**claim, "canonical": False, "research_only": True},
        )
        index.add_link(
            EvidenceLink(
                f"link:{claim['claim_id']}",
                claim["source_id"],
                "knowledge_claim",
                claim["claim_id"],
                "SUPPORTS",
                claim.get("video_timestamp"),
            )
        )
        index.add_field_provenance(
            FieldProvenance(
                f"prov:{claim['claim_id']}",
                "knowledge_claim",
                claim["claim_id"],
                "value",
                claim["value"],
                claim["source_id"],
                claim.get("video_timestamp"),
                claim["extraction"],
                claim["status"],
                claim["confidence"],
                "EXTERNAL_REFERENCE",
                claim["evidence_timestamp"],
                claim["game"],
            )
        )


def question_to_reconciliation(question: dict[str, Any]) -> ReconciliationItem:
    return ReconciliationItem(
        question["question_id"],
        None,
        "knowledge_question",
        question["question_id"],
        "NEEDS_VALIDATION",
        question["status"],
        question.get("priority", "MEDIUM"),
        question["question"],
    )

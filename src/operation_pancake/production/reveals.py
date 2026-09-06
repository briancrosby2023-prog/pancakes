"""Evidence-first player reveal and release-method tracking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .market import parse_timestamp

REVEAL_REGISTRY = "data/production/reveals/reveal_registry.json"
RELEASE_METHODS = {
    "PACKS",
    "LTD / LIMITED-TIME PACKS",
    "SET / COLLECTION",
    "FIELD PASS / SEASON REWARD",
    "OBJECTIVE",
    "CHALLENGE",
    "STORE OFFER",
    "EVENT REWARD",
    "OTHER VERIFIED METHOD",
    "UNKNOWN",
}
REQUIREMENT_METHODS = {
    "FIELD PASS / SEASON REWARD",
    "OBJECTIVE",
    "CHALLENGE",
}


def _identity(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _stable_id(row: dict[str, Any]) -> str:
    parts = [row[key] for key in ("player", "overall", "position", "program")]
    digest = hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()[:20]
    return f"reveal:{digest}"


def normalize_reveal(
    raw: dict[str, Any], *, first_seen_at: str, ingested_at: str, fixture: bool = False
) -> dict[str, Any]:
    """Validate a reveal without deriving any release fact from card characteristics."""
    for field in ("player", "position", "program", "source", "provenance"):
        if not raw.get(field):
            raise ValueError(f"{field} is required")
    overall = raw.get("overall")
    if isinstance(overall, bool) or not isinstance(overall, int) or overall <= 0:
        raise ValueError("overall must be a positive integer")
    parse_timestamp(first_seen_at)
    parse_timestamp(ingested_at)
    if parse_timestamp(first_seen_at) > parse_timestamp(ingested_at):
        raise ValueError("future first_seen_at rejected")
    method = raw.get("release_method", "UNKNOWN")
    if method not in RELEASE_METHODS:
        raise ValueError("unsupported release method")
    method_source = raw.get("release_method_source")
    if method != "UNKNOWN" and not method_source:
        raise ValueError("verified release method requires release_method_source")
    release_time = raw.get("release_time")
    release_time_source = raw.get("release_time_source")
    if release_time and not release_time_source:
        raise ValueError("release_time requires an explicit source")
    if release_time:
        parse_timestamp(release_time)
    auctionable = raw.get("auctionable")
    if auctionable not in (None, True, False):
        raise ValueError("auctionable must be true, false, or unknown")
    if auctionable is not None and not raw.get("auctionability_source"):
        raise ValueError("auctionability requires an explicit source")
    details = dict(raw.get("method_details") or {})
    if details and not raw.get("method_details_source"):
        raise ValueError("method details require an explicit source")
    if method == "SET / COLLECTION":
        details = {
            "required_items": details.get("required_items"),
            "quantity_required": details.get("quantity_required"),
            "submitted_items_returned": details.get("submitted_items_returned"),
            "bnd_behavior": details.get("bnd_behavior"),
            "reward_card": details.get("reward_card"),
            "completion_window": details.get("completion_window"),
            "other_rules": details.get("other_rules"),
        }
    elif method in REQUIREMENT_METHODS:
        details = {"acquisition_requirement": details.get("acquisition_requirement")}
    elif method == "LTD / LIMITED-TIME PACKS":
        details = {"availability_window": details.get("availability_window")}
    normalized = {
        "player": raw["player"].strip(),
        "overall": overall,
        "position": raw["position"].strip().upper(),
        "program": raw["program"].strip(),
        "first_seen_at": first_seen_at,
        "reveal_evidence": raw.get("reveal_evidence") or raw["source"],
        "release_time": release_time,
        "release_time_source": release_time_source,
        "release_method": method,
        "release_method_source": method_source,
        "method_details": details,
        "method_details_source": raw.get("method_details_source"),
        "source": raw["source"],
        "provenance": raw["provenance"],
        "status": raw.get("status", "REVEALED"),
        "auctionable": auctionable,
        "auctionability_source": raw.get("auctionability_source"),
        "canonical_card_id": None,
        "market_monitor": False,
        "evidence_scope": "FIXTURE" if fixture else "REAL",
        "last_checked_at": ingested_at,
    }
    normalized["reveal_id"] = raw.get("reveal_id") or _stable_id(normalized)
    return normalized


def merge_registry(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Upsert evidence while preserving original first-seen and verified facts."""
    merged = {row["reveal_id"]: dict(row) for row in existing}
    for row in incoming:
        current = merged.get(row["reveal_id"])
        if current is None:
            merged[row["reveal_id"]] = dict(row)
            continue
        first_seen = min(current["first_seen_at"], row["first_seen_at"])
        for key, value in row.items():
            if value is not None and not (key == "release_method" and value == "UNKNOWN"):
                current[key] = value
        current["first_seen_at"] = first_seen
    return sorted(merged.values(), key=lambda row: (row["first_seen_at"], row["reveal_id"]))


def save_registry(path: Path, rows: list[dict[str, Any]], *, production: bool) -> None:
    if production and any(row.get("evidence_scope") != "REAL" for row in rows):
        raise ValueError("fixture reveals cannot enter production registry")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reconcile_live(
    reveal: dict[str, Any], cards: list[dict[str, Any]], live_evidence: dict[str, Any]
) -> dict[str, Any]:
    """Link only one exact canonical identity and gate monitoring on auction evidence."""
    if not live_evidence.get("source") or not live_evidence.get("observed_at"):
        raise ValueError("live status requires sourced evidence")
    matches = [
        card
        for card in cards
        if _identity(card.get("player_name")) == _identity(reveal["player"])
        and card.get("native_overall") == reveal["overall"]
        and _identity(card.get("position")) == _identity(reveal["position"])
        and _identity(card.get("program")) == _identity(reveal["program"])
    ]
    result = dict(reveal)
    result["live_evidence"] = live_evidence
    result["status"] = (
        "LIVE — EXACT CANONICAL MATCH" if len(matches) == 1 else "LIVE — CANONICAL MATCH REQUIRED"
    )
    result["canonical_card_id"] = matches[0]["card_id"] if len(matches) == 1 else None
    if "auctionable" in live_evidence:
        if not live_evidence.get("auctionability_source"):
            raise ValueError("auctionability requires an explicit source")
        result["auctionable"] = live_evidence["auctionable"]
        result["auctionability_source"] = live_evidence["auctionability_source"]
    result["market_monitor"] = bool(result["canonical_card_id"] and result["auctionable"] is True)
    return result


def monitor_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "card_id": row["canonical_card_id"],
            "priority": 1,
            "tier": "TIER 1",
            "reasons": ["verified live reveal; explicitly auctionable"],
            "sources": ["PLAYER REVEALS"],
        }
        for row in rows
        if row.get("market_monitor") is True
        and row.get("canonical_card_id")
        and row.get("auctionable") is True
    ]


def whats_coming(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "PLAYER": row["player"],
            "OVR": row["overall"],
            "POS": row["position"],
            "PROGRAM": row["program"],
            "RELEASE METHOD": row["release_method"],
            "RELEASE TIME": row.get("release_time") or "UNKNOWN",
            "STATUS": row["status"],
        }
        for row in rows
        if not str(row.get("status", "")).startswith("LIVE")
    ]


def render_whats_coming(rows: list[dict[str, Any]]) -> str:
    columns = ["PLAYER", "OVR", "POS", "PROGRAM", "RELEASE METHOD", "RELEASE TIME", "STATUS"]
    lines = ["WHAT'S COMING", "", " | ".join(columns), " | ".join(["---"] * len(columns))]
    lines.extend(" | ".join(str(row[column]) for column in columns) for row in whats_coming(rows))
    if len(lines) == 4:
        lines.append("NO VERIFIED CURRENT REVEALS")
    return "\n".join(lines) + "\n"

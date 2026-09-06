# ruff: noqa: E501
"""Generate the OP-X-039 reveal/release-method operating artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from operation_pancake.production.reveals import RELEASE_METHODS, render_whats_coming

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/op_x_039"


def write(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        content = value
    else:
        content = json.dumps(value, indent=2, sort_keys=True) + "\n"
    (OUT / name).write_text(content, encoding="utf-8")


def main() -> None:
    rows: list[dict] = []
    write("reveal_registry.json", rows)
    write("whats_coming.json", {"count": 0, "cards": rows})
    write("WHATS_COMING.md", render_whats_coming(rows))
    write(
        "release_method_spec.json",
        {
            "allowed": sorted(RELEASE_METHODS),
            "primary_research_target": "RELEASE METHOD",
            "unknown_policy": "record UNKNOWN and continue monitoring",
            "forbidden_inference_inputs": ["card art", "OVR", "program", "previous EA behavior"],
            "verified_evidence_required_for": [
                "release method",
                "release time",
                "auctionability",
                "method details",
            ],
        },
    )
    write(
        "method_detail_spec.json",
        {
            "SET / COLLECTION": [
                "required_items",
                "quantity_required",
                "submitted_items_returned",
                "bnd_behavior",
                "reward_card",
                "completion_window",
                "other_rules",
            ],
            "FIELD PASS / SEASON REWARD, OBJECTIVE, CHALLENGE": ["acquisition_requirement"],
            "LTD / LIMITED-TIME PACKS": ["availability_window"],
        },
    )
    write(
        "live_reconciliation_spec.json",
        {
            "match": "exact player + OVR + position + program; exactly one canonical row",
            "unmatched_status": "LIVE — CANONICAL MATCH REQUIRED",
            "preserve_reveal_record": True,
            "normal_pancake_scoring": "begins only after exact canonical linkage",
            "market_monitor_gate": "live + exact canonical match + explicitly auctionable",
            "nonauctionable_monitoring": False,
        },
    )
    write(
        "player_reveals_audit.json",
        {
            "surface": "https://cfb.fan/reveals/",
            "attempted_at": "2026-08-20",
            "result": "BLOCKED BEFORE NAVIGATION",
            "reason": "existing Windows deny-read ACLs terminate the browser sandbox helper",
            "verified_current_reveals": 0,
            "safety": ["no fabricated cards", "no inferred methods", "no guessed release times"],
        },
    )
    write(
        "RESULTS.md",
        "# OP-X-039 Reveal Release-Method Tracking\n\n"
        "Implemented an evidence-first reveal registry, exact live-card reconciliation, "
        "and an auctionability gate for market monitoring. Current live-page inspection "
        "was blocked before navigation by the existing workspace ACL condition, so the "
        "checked-in WHAT'S COMING report contains no fabricated reveal rows.\n",
    )


if __name__ == "__main__":
    main()

"""Record a reusable batch of authenticated PS5 Price Tracker observations."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from operation_pancake.production.engine import load_population
from operation_pancake.production.monitor import load_json, save_json
from operation_pancake.production.recorder import (
    CAMPAIGN_STATE,
    RECORDER_HISTORY,
    run_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/research/execution_loop/ps5_tracker_batch_input.json"
CAMPAIGN_ID = "pancake-default-monitored-universe-v1"


def main():
    input_path = ROOT / sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    payload = json.loads(input_path.read_text())
    report_path = input_path.with_name(input_path.stem.replace("_input", "_execution") + ".json")
    population = load_population(ROOT)
    campaigns = load_json(ROOT / CAMPAIGN_STATE, [])
    if isinstance(campaigns, dict):
        campaigns = campaigns.get("campaigns", [])
    campaign = next(c for c in campaigns if c.get("campaign_id") == CAMPAIGN_ID)
    resolved = []
    for item in payload["observations"]:
        matches = [
            c
            for c in population
            if c.get("player_name") == item["player_name"]
            and c.get("native_overall") == item["overall"]
            and c.get("program") == item["program"]
        ]
        if len(matches) != 1:
            version = item["external_card_id"]
            raise SystemExit(
                f"canonical identity not unique for {version}: {len(matches)} matches"
            )
        card = matches[0]
        resolved.append((item, card))
        campaign_ids = {r["card_id"] for r in campaign.get("cards", [])}
        if card["card_id"] not in campaign_ids:
            campaign.setdefault("cards", []).append(
                {
                    "card_id": card["card_id"],
                    "priority": 2,
                    "tier": "TIER 2",
                    "reasons": ["authenticated repeated PS5 Price Tracker cohort"],
                    "sources": ["PRICE TRACKER COHORT"],
                }
            )
    campaign["cards"] = sorted(
        campaign["cards"], key=lambda r: (r.get("priority", 99), r["card_id"])
    )
    save_json(ROOT / CAMPAIGN_STATE, campaigns)
    history = load_json(ROOT / RECORDER_HISTORY, [])
    before = sum(
        r.get("platform") == "PS5" and r.get("evidence_scope") == "REAL"
        for r in history
    )
    raw = []
    for item, card in resolved:
        row = {
            "card_id": card["card_id"],
            "external_card_id": item["external_card_id"],
            "observation_type": payload["observation_type"],
            "value": item["value"],
            "observed_at": item["source_last_updated"],
            "source": payload["source"],
            "source_url": payload["source_url"],
            "platform": payload["platform"],
            "campaign_id": CAMPAIGN_ID,
            "provenance": payload["provenance"],
            "confidence": payload["confidence"],
        }
        capture = item.get("capture_timestamp", payload.get("capture_timestamp"))
        if capture:
            row["available_at"] = capture
        raw.append(row)
    now = datetime.now(timezone.utc).isoformat()
    result = run_snapshot(
        ROOT, raw, campaigns, {}, ingested_at=now, fixture=False, persist=True
    )
    after_rows = load_json(ROOT / RECORDER_HISTORY, [])
    after = sum(
        r.get("platform") == "PS5" and r.get("evidence_scope") == "REAL"
        for r in after_rows
    )
    identities = [
        {
            "external_card_id": item["external_card_id"],
            "player_name": card["player_name"],
            "card_id": card["card_id"],
            "overall": card["native_overall"],
            "program": card["program"],
            "position": card["position"],
            "archetype": card["archetype"],
        }
        for item, card in resolved
    ]
    report = {
        "status": (
            "PASS"
            if result["accepted"] == len(raw) and not result["failures"]
            else "FAIL"
        ),
        "input": str(input_path.relative_to(ROOT)),
        "before": before,
        "after": after,
        "accepted": result["accepted"],
        "failures": result["failures"],
        "capture_timestamp": payload.get("capture_timestamp"),
        "capture_timestamp_status": payload.get("capture_timestamp_status", "EXACT"),
        "identity_reconciliation": identities,
    }
    save_json(report_path, report)
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

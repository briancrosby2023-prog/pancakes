"""One-shot production ingestion of the first authorized rendered PS5 tracker value."""

import json
from datetime import datetime, timezone
from pathlib import Path

from operation_pancake.production.monitor import load_json, save_json
from operation_pancake.production.recorder import (
    CAMPAIGN_STATE,
    RECORDER_HISTORY,
    default_campaign,
    run_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/research/execution_loop/authorized_market_surface_recovery_2026-08-22.json"
REPORT = ROOT / "data/research/execution_loop/first_ps5_recorder_execution.json"
CARD_ID = "card:01be68aa7f168746bf62"
CAMPAIGN_ID = "pancake-default-monitored-universe-v1"


def main():
    evidence = json.loads(SOURCE.read_text())["strongest_surface_observation"]
    now = datetime.now(timezone.utc).isoformat()
    campaigns = load_json(ROOT / CAMPAIGN_STATE, [])
    if isinstance(campaigns, dict):
        campaigns = campaigns.get("campaigns", [])
    if not campaigns:
        campaigns = [default_campaign(ROOT, now)]
        save_json(ROOT / CAMPAIGN_STATE, campaigns)
    campaign = next(
        (c for c in campaigns if c.get("campaign_id") == CAMPAIGN_ID),
        None,
    )
    if campaign is None:
        raise SystemExit("required monitored-universe campaign missing")
    if CARD_ID not in {r["card_id"] for r in campaign.get("cards", [])}:
        raise SystemExit("Ed Too Tall Jones not in campaign")
    before_rows = load_json(ROOT / RECORDER_HISTORY, [])
    before = sum(
        r.get("platform") == "PS5" and r.get("evidence_scope") == "REAL"
        for r in before_rows
    )
    raw = {
        "card_id": CARD_ID,
        "observation_type": "PRICE_TRACKER_VALUE",
        "value": 615000,
        "observed_at": evidence["source_last_updated"],
        "available_at": evidence["observed_by_worker_at"],
        "source": "OPERA_RENDERED_CFB_FAN_PRICE_TRACKER",
        "source_url": evidence["source_url"],
        "platform": "PS5",
        "campaign_id": CAMPAIGN_ID,
        "provenance": "AUTHORIZED_RENDERED_CFB_FAN_AUTHENTICATED_OPERA",
        "confidence": "DIRECTLY_RENDERED",
    }
    result = run_snapshot(
        ROOT,
        [raw],
        campaigns,
        {},
        ingested_at=now,
        fixture=False,
        persist=True,
    )
    after_rows = load_json(ROOT / RECORDER_HISTORY, [])
    after = sum(
        r.get("platform") == "PS5" and r.get("evidence_scope") == "REAL"
        for r in after_rows
    )
    rec = result["records"][0] if result["records"] else None
    report = {
        "status": "PASS" if result["accepted"] == 1 and after >= before + 1 else "FAIL",
        "before": before,
        "after": after,
        "accepted": result["accepted"],
        "failures": result["failures"],
        "record": rec,
        "source_market_timestamp": evidence["source_last_updated"],
        "capture_timestamp": evidence["observed_by_worker_at"],
        "external_card_id": evidence["external_card_id"],
    }
    save_json(REPORT, report)
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

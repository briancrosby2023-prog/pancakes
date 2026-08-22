from __future__ import annotations
import json
from pathlib import Path
import pytest
from operation_pancake.production.market_campaign import calibrate_decision, history_statistics
from operation_pancake.production.monitor import reconcile_events
from operation_pancake.production.recorder import append_records, canonical_cards, completed_sale_statistics, default_campaign, listing_statistics, normalize_record, parse_browser_export, run_snapshot, sample_sufficiency, scheduler_state
ROOT=Path(__file__).resolve().parents[1];NOW="2026-08-20T21:00:00+00:00";OBSERVED="2026-08-20T20:00:00+00:00"
@pytest.fixture(scope="module")
def cards():return canonical_cards(ROOT)
@pytest.fixture
def campaign():return default_campaign(ROOT,"2026-08-20T00:00:00+00:00")
def raw(card_id,campaign_id,**changes):return {"card_id":card_id,"value":100,"observation_type":"LOWEST_VISIBLE_LISTING","observed_at":OBSERVED,"source":"fixture","platform":"PS5","campaign_id":campaign_id,**changes}
def normalized(cards,campaign,**changes):return normalize_record(raw(campaign["cards"][0]["card_id"],campaign["campaign_id"],**changes),cards,{campaign["campaign_id"]:campaign},ingested_at=NOW,fixture=True)
def test_default_campaign_is_ps5_and_requests_forecast_evidence(campaign):
 assert campaign["platform"]=="PS5";assert {"LOWEST_VISIBLE_LISTING","LIVE_LISTING","COMPLETED_SALE","SUPPLY_COUNT","SALE_VOLUME"}<=set(campaign["observation_types_requested"]);assert len(campaign["cards"])==39
def test_identity_program_ovr_position_are_canonical(cards,campaign):
 r=normalized(cards,campaign);assert r["platform"]=="PS5";assert r["card_id"] and r["player_name"] and r["position"] and r["overall"] and r["program"]
def test_listing_and_completed_sale_remain_distinct(cards,campaign):
 listing=normalized(cards,campaign);sale=normalized(cards,campaign,observation_type="COMPLETED_SALE");assert listing["source_semantics"]["class"]=="LISTING";assert sale["source_semantics"]["class"]=="SALE";assert completed_sale_statistics([listing,sale])["count"]==1
def test_additional_listing_and_supply_fields_are_preserved(cards,campaign):
 listing=normalized(cards,campaign,second_lowest_listing=125);supply=normalized(cards,campaign,observation_type="SUPPLY_COUNT",value=7);stats=listing_statistics([listing,supply]);assert stats["second_lowest_listing"]==125;assert stats["latest_supply_count"]==7
def test_sale_velocity_uses_real_completed_sale_timestamps(cards,campaign):
 a=normalized(cards,campaign,observation_type="COMPLETED_SALE",observed_at="2026-08-20T18:00:00+00:00");b=normalized(cards,campaign,observation_type="COMPLETED_SALE",observed_at="2026-08-20T20:00:00+00:00",value=110);assert completed_sale_statistics([a,b])["sale_velocity_per_day"]==12.0
def test_unknown_fields_are_not_fabricated(cards,campaign):
 r=normalized(cards,campaign);assert r["second_lowest_listing"] is None;assert r["listing_age_minutes"] is None
def test_platform_mismatch_is_rejected(cards,campaign):
 with pytest.raises(ValueError,match="platform mismatch"):normalize_record(raw(campaign["cards"][0]["card_id"],campaign["campaign_id"],platform="XBOX"),cards,{campaign["campaign_id"]:campaign},ingested_at=NOW)
def test_fixture_firewall_and_append_only(cards,campaign,tmp_path):
 r=normalized(cards,campaign);p=tmp_path/"h.json";assert append_records(p,[r],production=False)["appended"]==1;assert append_records(p,[r],production=False)["appended"]==0
 with pytest.raises(ValueError,match="fixture observations"):append_records(tmp_path/"prod.json",[r],production=True)
def test_browser_assisted_import_does_not_invent_data():
 payload=[{"card_id":"x","value":1}];assert parse_browser_export(json.dumps(payload),"json")==payload
def test_partial_snapshot_survives_bad_row(campaign):
 good=raw(campaign["cards"][0]["card_id"],campaign["campaign_id"]);bad=raw("unknown",campaign["campaign_id"]);r=run_snapshot(ROOT,[good,bad],[campaign],{},ingested_at=NOW,fixture=True,persist=False);assert r["accepted"]==1 and r["partial_success"] and len(r["failures"])==1
def test_sufficiency_counts_forecast_inputs(cards,campaign):
 rows=[normalized(cards,campaign),normalized(cards,campaign,observation_type="COMPLETED_SALE"),normalized(cards,campaign,observation_type="SUPPLY_COUNT"),normalized(cards,campaign,observation_type="SALE_VOLUME")];s=sample_sufficiency(rows,NOW);assert (s["listing_samples"],s["sale_samples"],s["supply_samples"],s["volume_samples"])==(1,1,1,1)
def test_scheduler_tracks_success(campaign):
 s=scheduler_state({**campaign,"desired_cadence_minutes":60},NOW,success=True);assert s["next_due"]=="2026-08-20T22:00:00+00:00"
def test_buy_gate_unchanged():assert calibrate_decision(history_statistics([],NOW),"VALUE",gross_cost=100,budget=100)["decision"]!="BUY"
def test_alert_dedup_unchanged():
 e={"card_id":"x","opportunity_type":"WATCH TARGET","observed_price":100,"threshold":110,"reason":"watch"};emitted,state=reconcile_events([e],{},NOW);assert len(emitted)==1 and reconcile_events([e],state,NOW)[0]==[]

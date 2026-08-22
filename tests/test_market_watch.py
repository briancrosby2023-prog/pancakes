from operation_pancake.production.market_watch import alert_candidate, buy_window_evidence, forecast_watch, prioritize, watcher_alerts

CARD={"card_id":"card:x","player_name":"Test Player","position":"WR","native_overall":88,"program":"Test","archetype":"Route Runner"}
AS_OF="2026-08-10T23:00:00-07:00"
def sale(day,hour,price):return {"card_id":"card:x","observation_type":"COMPLETED_SALE","observed_price":price,"value":price,"observed_at":f"2026-08-{day:02d}T{hour:02d}:00:00-07:00","user_observed_at":f"2026-08-{day:02d}T{hour:02d}:00:00-07:00"}
def listing(price):return {"card_id":"card:x","observation_type":"LOWEST_VISIBLE_LISTING","observed_price":price,"value":price,"observed_at":"2026-08-10T22:59:00-07:00","user_observed_at":"2026-08-10T22:59:00-07:00"}
def history(live=90000):
 rows=[]
 for day in range(1,9):rows.extend([sale(day,10,120000+day*500),sale(day,18,130000+day*500),sale(day,22,125000+day*500)])
 rows.append(listing(live));return rows
def test_forecast_wires_to_buy_ceiling_and_tax():
 r=forecast_watch(CARD,history(90000),AS_OF,minimum_net_profit=5000);assert r["forecast_state"]=="FORECAST";assert r["tax_rate"]==0.10;assert r["buy_ceiling"]==r["net_proceeds"]-5000;assert r["after_tax_net_profit"]==r["net_proceeds"]-90000
def test_buy_crossing_and_alert_contract():
 r=forecast_watch(CARD,history(90000),AS_OF);assert r["action"]=="BUY";a=alert_candidate(r);required={"exact_identity","observed_price","threshold","forecast_exit","forecast_horizon_minutes","after_tax_net_profit","expected_hold_minutes","exit_probability","confidence","liquidity","risk_flags","market_evidence_quality","action"};assert required<=set(a);assert a["action"]=="BUY"
def test_watch_semantics_unchanged_above_ceiling():
 r=forecast_watch(CARD,history(200000),AS_OF);assert r["action"]=="WATCH" and alert_candidate(r)["opportunity_type"]=="WATCH TARGET"
def test_insufficient_history_never_fabricates_forecast():
 r=forecast_watch(CARD,[sale(1,10,100000),listing(90000)],AS_OF);assert r["forecast_state"]=="INSUFFICIENT DATA";assert r["forecast_exit"] is None and r["after_tax_net_profit"] is None and r["priority_score"] is None;assert r["action"]=="INSUFFICIENT DATA"
def test_static_watch_can_survive_without_model_forecast():
 r=forecast_watch(CARD,[listing(90000)],AS_OF,static_buy_ceiling=95000);assert r["action"]=="WATCH" and r["forecast_exit"] is None
def test_listing_does_not_count_as_completed_sale():
 evidence=buy_window_evidence([listing(90000)],AS_OF);assert evidence["completed_sale_count"]==0 and evidence["completed_sale_median"] is None
def test_measured_buy_window_dimensions_are_exposed():
 evidence=buy_window_evidence(history(),AS_OF);assert evidence["hour_of_day_samples"] and evidence["day_of_week_samples"];assert evidence["price_dispersion"] is not None and evidence["sale_velocity_per_day"] is not None
def test_event_deduplication_reuses_existing_watcher():
 r=forecast_watch(CARD,history(90000),AS_OF);first,state=watcher_alerts([r],{},AS_OF);second,_=watcher_alerts([r],state,AS_OF);assert len(first)==1 and second==[]
def test_prioritization_excludes_unsupported_values():
 good=forecast_watch(CARD,history(90000),AS_OF);bad=forecast_watch({**CARD,"card_id":"card:y"},[listing(90000)],AS_OF);ranked=prioritize([bad,good]);assert ranked==[good]
def test_scientific_firewall_no_sales_means_no_buy():
 r=forecast_watch(CARD,[listing(1)],AS_OF);assert r["action"]=="INSUFFICIENT DATA" and r["buy_ceiling"] is None

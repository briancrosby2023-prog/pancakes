from pathlib import Path
import importlib.util,sys,json,tempfile,shutil,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
APP=Path(r"C:\Users\Trash Panda\AppData\Local\SimpleEvaluator")
RUNTIME=ROOT/"runtime/simple_evaluator"
class ObservationIntegrity(unittest.TestCase):
 def test_observation_preserves_protected_top_level_state(self):
  sys.path.insert(0,str(APP))
  spec=importlib.util.spec_from_file_location("integrity_server",RUNTIME/"server.py")
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory(dir=ROOT) as d:
   d=Path(d)
   for name in ["app-state.json","alerts.json","market-feed.json","browser-helper-heartbeat.json","cards.json"]:
    shutil.copy2(APP/name,d/name)
   for key,name in {"STATE":"app-state.json","ALERTS":"alerts.json","FEED":"market-feed.json","BROWSER_HEARTBEAT":"browser-helper-heartbeat.json","CARDS":"cards.json","STATE_LOCK":".app-state.lock","OPERATION_LOG":"operational-events.jsonl","PRODUCTION_ACCEPTANCE":"production-acceptance.json"}.items(): setattr(m,key,d/name)
   before=json.loads(m.STATE.read_text())
   before["value_probe_status"]={"state":"RATE_LIMITED","active":False,"sentinel":"unchanged"}
   before["value_probe_rate_limit"]={"persistent_lock":True,"sentinel":"retained"}
   m.STATE.write_text(json.dumps(before))
   payload=dict(source_url="https://cfb.fan/players/2557-jaleel-skinner/27-2002557/#prices",observed_at="2026-10-04T06:03:00Z",status="NO_LISTING",listing_count=0,price=None,other_buy_now_prices=[],browser_family="edge",helper_version="1.4.15")
   result=m.record_browser_observation(payload,native_alerts=False)
   after=json.loads(m.STATE.read_text())
   self.assertTrue(result["ok"])
   self.assertEqual(len(after["observations"]),len(before["observations"])+1)
   for key in ["value_probe_status","value_probe_rate_limit"]:
    self.assertEqual(after.get(key),before[key],key+" lost during observation write")
 def test_send_observation_exception_is_published_to_heartbeat_diagnostic(self):
  script=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(process.argv[1],'utf8');
const diagnostic=src.slice(src.indexOf("  let lastDiagnosticKey"),src.indexOf("  function activatePlayerPricesTab"));
const observe=src.slice(src.indexOf("  async function observeWhenReady"),src.indexOf("  let starting ="));
const messages=[];
const context={Date,JSON,String,location:{href:'https://cfb.fan/players/2557-jaleel-skinner/27-2002557/#prices'},
 document:{documentElement:{dataset:{}}},MARKET_WAIT_MS:45000,WATCH_RECHECK_MS:5000,
 parsePlayStationMarket:()=>({state:'NO_LISTING',listing_count:0}),
 mark:()=>{},setTimeout:()=>{},start:()=>{},
 runtimeMessage:async m=>{messages.push(m);return {ok:true}},
 sendObservation:async()=>{throw new Error('exact-card HTTP 409 sentinel')}
};
vm.createContext(context);vm.runInContext(diagnostic+observe+'; globalThis.run=observeWhenReady;',context);
(async()=>{await context.run({card_id:'exact-card'});
 const diag=messages.find(m=>m.diagnostic&&m.diagnostic.stage==='observation-send-error');
 assert(diag,'sendObservation exception was not published');
 assert(diag.diagnostic.detail.includes('exact-card HTTP 409 sentinel'));
 assert.equal(diag.diagnostic.market_state,'NO_LISTING');
 console.log('diagnostic PASS');})().catch(e=>{console.error(e);process.exitCode=1});
"""
  result=subprocess.run(["node","-e",script,str(RUNTIME/"browser-helper/watch.js")],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=="__main__":unittest.main()

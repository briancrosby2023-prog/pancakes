"""Zero-dependency local web application for Operation Pancake GM intelligence."""
from __future__ import annotations
import argparse, html, json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from operation_pancake.production.gm import GMProduct
from operation_pancake.roster_state import RosterAssignment, RosterStore
from operation_pancake.gm_state import GMStateStore
from operation_pancake.gm_decisions import GMDecisionService
from operation_pancake.evo import EVODefinition, EVOStore, compose_evo_decision, enrich_candidates, projected_production

def _page(title, body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;margin:0;background:#f6f4ef;color:#1d1d1b}}header,main{{max-width:1180px;margin:auto;padding:24px}}header{{display:flex;gap:24px;align-items:center}}a{{color:#684b00}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}input,select,button{{font:inherit;padding:9px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}.card{{background:white;padding:18px;border-radius:12px;margin:12px 0}}.muted{{color:#666}}.error{{background:#fee;padding:10px}}code{{white-space:pre-wrap}}</style></head><body><header><strong>🥞 Operation Pancake</strong><a href="/">Players</a><a href="/roster">Roster</a><a href="/gm">GM / Upgrades</a><a href="/evo">EVO</a><a href="/compare">Compare</a></header><main>{body}</main></body></html>'''.encode()
def _bool(f,n): return f.get(n,[""])[0].lower() in {"1","true","on","yes"}
def _unknown(v): return "UNKNOWN" if v is None else str(v)

def create_handler(root:Path, roster_path:Path|None=None, gm_state_path:Path|None=None, evo_path:Path|None=None):
    gm=GMProduct(root); store=RosterStore(roster_path or root/".operation_pancake"/"roster.json",set(gm.cards)); state_store=GMStateStore(gm_state_path or root/".operation_pancake"/"gm.json",set(gm.cards)); evo_store=EVOStore(evo_path or root/".operation_pancake"/"evo.json"); decisions=GMDecisionService(gm)
    def assignments(): return store.load()
    def owned_ids(): return {a.card_id for a in assignments()}
    def evo_by_id(eid): return next((e for e in evo_store.load() if e.id==eid),None)
    def assignment_by_slot(slot): return next((a for a in assignments() if a.slot==slot.upper()),None)
    def enriched_roster(): return sorted([(a,gm.cards.get(a.card_id,{}),gm.rank_by_id.get(a.card_id,{}),decisions.decision(a)) for a in assignments()],key=lambda r:(r[0].position,r[0].slot))
    class Handler(BaseHTTPRequestHandler):
        def _send(self,b,status=200,ct="text/html; charset=utf-8"): self.send_response(status); self.send_header("Content-Type",ct); self.end_headers(); self.wfile.write(b)
        def _json(self,p,status=200): self._send(json.dumps(p,indent=2).encode(),status,"application/json")
        def _redirect(self,p): self.send_response(303); self.send_header("Location",p); self.end_headers()
        def _form(self): return parse_qs(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode())
        def _assignment(self,f):
            cid=f.get("card_id",[""])[0]; c=gm.cards.get(cid)
            if not c: raise ValueError("Choose a valid canonical card")
            return RosterAssignment(cid,f.get("position",[c.get("position") or ""])[0].upper(),f.get("slot",[""])[0].upper(),_bool(f,"starter"),True,_bool(f,"protected"),_bool(f,"rerollable"),f.get("notes",[""])[0])
        def _evo_payload(self,q):
            evo=evo_by_id(q.get("evo_id",[""])[0]); cid=q.get("card_id",[""])[0]; slot=q.get("slot",[""])[0].upper(); a=assignment_by_slot(slot); state=state_store.load()
            if not evo: raise KeyError("EVO not found")
            if not a: raise KeyError("roster slot not found")
            return compose_evo_decision(evo=evo,candidate_id=cid,assignment=a,gm=gm,gm_decisions=decisions,prices=state.prices,budget_state=state,owned_ids=owned_ids())
        def do_GET(self):
            p=urlparse(self.path); q=parse_qs(p.query); state=state_store.load()
            if p.path=="/api/player": self._json(gm.lookup(card_id=q.get("card_id",[None])[0],player_name=q.get("name",[None])[0],position=q.get("position",[None])[0])); return
            if p.path=="/api/roster": self._json({"assignments":[asdict(a)|{"card":gm._identity(c),"pancake_score":s.get("score"),"position_rank":s.get("position_rank"),"gm":d} for a,c,s,d in enriched_roster()]}); return
            if p.path=="/api/gm": self._json({"budget":state.as_dict(),"decisions":[decisions.decision(a) for a in assignments()],"upgrades":decisions.opportunities(assignments(),state.prices,state.spendable_budget)}); return
            if p.path=="/api/gm/decision":
                a=assignment_by_slot(q.get("slot",[""])[0])
                if not a: self._json({"error":"assignment not found"},404); return
                self._json(decisions.detail(a,state.prices,state.spendable_budget)); return
            if p.path=="/api/evo": self._json({"version":EVOStore.VERSION,"definitions":[asdict(e) for e in evo_store.load()]}); return
            if p.path=="/api/evo/candidates":
                evo=evo_by_id(q.get("evo_id",[""])[0]); ownership=q.get("ownership",["all"])[0]
                if not evo: self._json({"error":"EVO not found"},404); return
                self._json({"evo":asdict(evo),"ownership":ownership,"candidates":enrich_candidates(evo,gm,owned_ids(),ownership)}); return
            if p.path=="/api/evo/candidate":
                evo=evo_by_id(q.get("evo_id",[""])[0]); cid=q.get("card_id",[""])[0]; card=gm.cards.get(cid)
                if not evo or not card: self._json({"error":"EVO or card not found"},404); return
                ok,basis=evo.eligible(card); price=state.prices.get(cid); self._json({"eligible":ok,"basis":basis,"ownership":"OWNED" if cid in owned_ids() else "ACQUISITION","current":gm.lookup(card_id=cid),"projection":projected_production(evo,gm,card),"price":price,"price_status":"PRICE KNOWN" if price is not None else "PRICE UNKNOWN"}); return
            if p.path=="/api/evo/decision":
                try: self._json(self._evo_payload(q))
                except (KeyError,ValueError) as e: self._json({"error":str(e)},404 if isinstance(e,KeyError) else 400)
                return
            if p.path=="/evo":
                eid=q.get("evo_id",[""])[0]; slot=q.get("slot",[""])[0].upper(); ownership=q.get("ownership",["all"])[0]; evos=evo_store.load(); roster=assignments()
                body='<h1>EVO decision workflow</h1><div class="card"><h2>Create verified EVO</h2><form method="post" action="/evo"><input name="name" placeholder="EVO name" required><input name="target_ovr" type="number" placeholder="Target OVR"><input name="positions" placeholder="Positions, comma separated"><input name="archetypes" placeholder="Archetypes, comma separated"><input name="ovr_min" type="number" placeholder="Starting OVR min"><input name="ovr_max" type="number" placeholder="Starting OVR max"><input name="resource_cost" type="number" min="0" placeholder="Resource cost"><input name="boosts" placeholder="Verified native-rating boosts: speed=2,..."><input name="notes" placeholder="Notes"><button>Save EVO</button></form><p class="muted">Resource cost is not treated as coins. Target OVR alone never creates a projected score.</p></div>'
                if not evos: body+='<div class="card">No EVO definitions yet. Create one above.</div>'; self._send(_page("EVO",body)); return
                body+='<form><label>EVO <select name="evo_id">'+''.join(f'<option value="{html.escape(e.id)}" {"selected" if e.id==eid else ""}>{html.escape(e.name)}</option>' for e in evos)+'</select></label><label>Roster slot <select name="slot"><option value="">Select slot</option>'+''.join(f'<option value="{html.escape(a.slot)}" {"selected" if a.slot==slot else ""}>{html.escape(a.slot)} — {html.escape((gm.cards.get(a.card_id) or {}).get("player_name") or a.card_id)}</option>' for a in roster)+'</select></label><label>Pool <select name="ownership">'+''.join(f'<option value="{x}" {"selected" if ownership==x else ""}>{label}</option>' for x,label in (("all","All eligible"),("owned","Owned"),("acquisition","Acquisition")))+'</select></label><button>Evaluate</button></form>'
                evo=evo_by_id(eid) if eid else None
                if evo:
                    cs=enrich_candidates(evo,gm,owned_ids(),ownership); body+=f'<div class="card"><strong>{html.escape(evo.name)}</strong> · Target OVR {_unknown(evo.target_ovr)} · Final attributes {"PARTIALLY VERIFIED" if evo.final_attributes_known else "UNKNOWN"}</div>'
                    if not cs: body+='<div class="card">No eligible candidates in this ownership pool.</div>'
                    else:
                        body+='<table><tr><th>Candidate</th><th>Current quality</th><th>Potential</th><th>Ownership / cost</th><th>Confidence / limitations</th><th>Decision</th></tr>'
                        for c in cs[:200]:
                            prod=c["production"]; link="—"
                            if slot: link=f'<a href="/evo/decision?{urlencode({"evo_id":evo.id,"slot":slot,"card_id":c["card_id"]})}">Compare 3 paths</a>'
                            price=state.prices.get(c["card_id"]); body+=f'<tr><td>{html.escape(c.get("player_name") or c["card_id"])}<br>{html.escape(c.get("position") or "")} {c.get("native_overall") or "—"}</td><td>Score {_unknown(prod.get("score"))}<br>Rank {_unknown(prod.get("position_rank"))}<br>{html.escape(str(prod.get("role",{}).get("archetype") or "UNKNOWN"))}</td><td>Target {_unknown(c.get("target_ovr"))}<br>Headroom {_unknown(c.get("ovr_headroom"))}</td><td>{c["ownership"]}<br>{"PRICE UNKNOWN" if price is None else f"{price:,} coins"}</td><td>{html.escape(str(prod.get("confidence") or "UNKNOWN"))}<br>{html.escape(", ".join(prod.get("limitations") or c.get("limitations") or []) or "None")}</td><td>{link}</td></tr>'
                        body+='</table>'
                self._send(_page("EVO",body)); return
            if p.path=="/evo/decision":
                try: d=self._evo_payload(q)
                except (KeyError,ValueError) as e: self._send(_page("EVO decision",f'<div class="error">{html.escape(str(e))}</div><a href="/evo">Back to EVO</a>'),404 if isinstance(e,KeyError) else 400); return
                cur=d["current"]; ep=d["evo_path"]; rp=d["replacement_path"]; eco=d["economics"]; dec=d["decision"]; ce=cur.get("evaluation") or {}; pp=ep["projection"].get("production") or {}; base_name=(ep["base"].get("card") or {}).get("player_name") or d["evo_path"]["base"].get("card_id") or "UNKNOWN"; base_price="PRICE UNKNOWN" if ep["base_price"] is None else f'{ep["base_price"]:,} coins'; rep_price="PRICE UNKNOWN" if rp.get("price") is None else f'{rp["price"]:,} coins'
                body=f'<h1>{html.escape(d["slot"]["slot"])} — three-way EVO decision</h1><div class="card"><h2>{html.escape(dec["decision"])}</h2><p>{html.escape("; ".join(dec["reasons"]))}</p><p>Confidence: {html.escape(dec["confidence"])}</p></div><table><tr><th>Current roster player</th><th>EVO path</th><th>Normal replacement</th></tr><tr><td>{html.escape((cur.get("card") or {}).get("player_name") or d["slot"]["card_id"])}<br>Score {_unknown(ce.get("score"))}<br>Rank {_unknown(ce.get("position_rank"))}<br>{"PROTECTED" if d["slot"]["protected"] else ""} {"REROLLABLE" if d["slot"]["rerollable"] else ""}<br>{cur["price_status"]}</td><td>{html.escape(base_name)} · {ep["ownership"]}<br>Base price {base_price}<br>Resource cost {_unknown(ep["resource_cost"])} (not coins)<br>Target OVR {_unknown(ep["target_ovr"])}<br>Projected score {_unknown(pp.get("score"))}<br>Projected rank {_unknown(pp.get("position_rank"))}<br>Final-state certainty {html.escape(str(pp.get("confidence") or "UNKNOWN"))}<br>{html.escape(", ".join(pp.get("limitations") or []))}</td><td>{html.escape(str(rp.get("player_name") or rp.get("status") or "UNKNOWN"))}<br>Score gain {_unknown(rp.get("score_improvement"))}<br>Price {rep_price}<br>Confidence {html.escape(str(rp.get("score_confidence") or "UNKNOWN"))}</td></tr></table><div class="card"><h2>Economics</h2><p>Current coins {eco["current_coins"]:,} · Reserve {eco["reserve"]:,} · Spendable {eco["spendable"]:,}</p><p>EVO base {_unknown(eco["evo_base_price"])} · EVO resource {_unknown(eco["evo_resource_cost"])} · Replacement {_unknown(eco["replacement_price"])} · Remaining after EVO base {_unknown(eco["remaining_after_evo_base"])}</p><p>Market state {eco["market_price_state"]}</p></div><p><a href="/evo?{urlencode({"evo_id":d["evo"]["id"],"slot":d["slot"]["slot"]})}">Back to candidates</a></p>'
                self._send(_page("EVO decision",body)); return
            if p.path=="/compare":
                l=q.get("current",[""])[0]; r=q.get("candidate",[""])[0]; price=state.prices.get(r); body=f'<h1>Compare players</h1><form><input name="current" value="{html.escape(l)}" placeholder="Current card ID"><input name="candidate" value="{html.escape(r)}" placeholder="Candidate card ID"><button>Compare</button></form>'
                if l and r: body+=f'<div class="card"><code>{html.escape(json.dumps(gm.compare(l,r,price),indent=2))}</code><p>{"PRICE UNKNOWN" if price is None else f"Price {price:,} coins"}</p></div>'
                self._send(_page("Compare",body)); return
            if p.path=="/decision":
                a=assignment_by_slot(q.get("slot",[""])[0])
                if not a: self._send(_page("Decision","<h1>Assignment not found</h1>"),404); return
                d=decisions.detail(a,state.prices,state.spendable_budget); self._send(_page("Decision",f'<h1>{html.escape(a.slot)} — {html.escape(d["current"]["player_name"])}</h1><div class="card"><h2>{d["decision"]}</h2><p>{html.escape(d["key_reason"])}</p><p>Confidence: {html.escape(str(d["confidence"]))}</p><code>{html.escape(json.dumps(d,indent=2))}</code></div>')); return
            if p.path=="/gm":
                o=decisions.opportunities(assignments(),state.prices,state.spendable_budget); body=f'<h1>GM / Upgrades</h1><div class="card"><form method="post" action="/gm/budget"><label>Current coins <input name="current_coins" type="number" min="0" value="{state.current_coins}"></label><label>Reserve <input name="reserve_coins" type="number" min="0" value="{state.reserve_coins}"></label><button>Save budget</button></form><strong>Spendable: {state.spendable_budget:,} coins</strong></div><div class="card"><h2>Portfolio</h2><code>{html.escape(json.dumps(o["portfolio"],indent=2))}</code></div>'; self._send(_page("GM / Upgrades",body)); return
            if p.path=="/roster":
                body='<h1>Roster dashboard</h1>'
                if not assignments(): body+='<div class="card">Roster is empty. Search Players and add a canonical card.</div>'
                body+='<table><tr><th>Slot</th><th>Player</th><th>Pancake</th><th>GM</th><th>Edit / remove</th></tr>'
                for a,c,s,d in enriched_roster(): body+=f'<tr><td><a href="/decision?{urlencode({"slot":a.slot})}">{html.escape(a.slot)}</a></td><td>{html.escape(c.get("player_name") or a.card_id)} · {c.get("native_overall") or "—"}</td><td>{_unknown(s.get("score"))} · rank {_unknown(s.get("position_rank"))}</td><td>{d["decision"]}</td><td><form method="post" action="/roster/update"><input type="hidden" name="old_slot" value="{html.escape(a.slot)}"><input type="hidden" name="card_id" value="{html.escape(a.card_id)}"><input type="hidden" name="position" value="{html.escape(a.position)}"><input name="slot" value="{html.escape(a.slot)}" required><label><input type="checkbox" name="starter" {"checked" if a.starter else ""}>Starter</label><label><input type="checkbox" name="protected" {"checked" if a.protected else ""}>Protected</label><label><input type="checkbox" name="rerollable" {"checked" if a.rerollable else ""}>Rerollable</label><button>Save</button></form><form method="post" action="/roster/delete"><input type="hidden" name="slot" value="{html.escape(a.slot)}"><button>Remove</button></form></td></tr>'
                body+='</table>'; self._send(_page("Roster",body)); return
            if p.path!="/": self._send(_page("Not found","<h1>Not found</h1>"),404); return
            name=q.get("name",[""])[0]; pos=q.get("position",[""])[0].upper(); rows=[]
            if name or pos:
                cs=[c for c in gm.population if (not name or name.casefold() in (c.get("player_name") or "").casefold()) and (not pos or c.get("position")==pos)]; cs.sort(key=lambda c:(-(c.get("native_overall") or 0),c.get("player_name") or ""))
                for c in cs[:100]: rows.append(f'<tr><td>{html.escape(c.get("player_name") or "")}</td><td>{html.escape(c.get("position") or "")}</td><td>{c.get("native_overall") or "—"}</td><td><form method="post" action="/roster/add"><input type="hidden" name="card_id" value="{html.escape(c["card_id"])}"><input type="hidden" name="position" value="{html.escape(c.get("position") or "")}"><input name="slot" placeholder="{html.escape(c.get("position") or "")}1" required><label><input type="checkbox" name="starter" checked>Starter</label><label><input type="checkbox" name="protected">Protected</label><label><input type="checkbox" name="rerollable">Rerollable</label><button>Add</button></form></td></tr>')
            body=f'<h1>Player intelligence</h1><form><input name="name" value="{html.escape(name)}" placeholder="Player name"><input name="position" value="{html.escape(pos)}" placeholder="Position"><button>Search</button></form>'
            if rows: body+='<table>'+''.join(rows)+'</table>'
            self._send(_page("Players",body))
        def do_POST(self):
            p=urlparse(self.path); f=self._form()
            try:
                if p.path=="/roster/add": store.add(self._assignment(f)); self._redirect("/roster"); return
                if p.path=="/roster/update":
                    row=self._assignment(f); store.update(f.get("old_slot",[""])[0],card_id=row.card_id,position=row.position,slot=row.slot,starter=row.starter,owned=True,protected=row.protected,rerollable=row.rerollable,notes=row.notes); self._redirect("/roster"); return
                if p.path=="/roster/delete": store.remove(f.get("slot",[""])[0]); self._redirect("/roster"); return
                if p.path=="/gm/budget": state_store.update_budget(int(f.get("current_coins",[0])[0]),int(f.get("reserve_coins",[0])[0])); self._redirect("/gm"); return
                if p.path=="/gm/price": state_store.set_price(f.get("card_id",[""])[0],int(f.get("price",[0])[0])); self._redirect("/gm"); return
                if p.path=="/evo":
                    def oi(n): v=f.get(n,[""])[0].strip(); return int(v) if v else None
                    boosts={}
                    for part in f.get("boosts",[""])[0].split(","):
                        if "=" in part: k,v=part.split("=",1); boosts[k.strip()]=int(v.strip())
                    evos=evo_store.load(); eid=f"evo-{len(evos)+1}"; evos.append(EVODefinition(eid,f.get("name",[""])[0],oi("target_ovr"),tuple(x.strip().upper() for x in f.get("positions",[""])[0].split(",") if x.strip()),tuple(x.strip() for x in f.get("archetypes",[""])[0].split(",") if x.strip()),oi("ovr_min"),oi("ovr_max"),known_attribute_boosts=boosts,resource_cost=oi("resource_cost"),notes=f.get("notes",[""])[0])); evo_store.save(evos); self._redirect("/evo?"+urlencode({"evo_id":eid})); return
                if p.path=="/api/roster": store.add(self._assignment(f)); self._json({"status":"CREATED"},201); return
                if p.path=="/api/gm/budget": self._json(state_store.update_budget(int(f.get("current_coins",[0])[0]),int(f.get("reserve_coins",[0])[0])).as_dict()); return
                if p.path=="/api/gm/price": self._json(state_store.set_price(f.get("card_id",[""])[0],int(f.get("price",[0])[0])).as_dict()); return
                self._send(_page("Not found","<h1>Not found</h1>"),404)
            except (ValueError,KeyError,json.JSONDecodeError) as e:
                if p.path.startswith("/api/"): self._json({"error":str(e)},400)
                else: self._send(_page("Error",f'<div class="error">{html.escape(str(e))}</div>'),400)
        def do_DELETE(self):
            p=urlparse(self.path); q=parse_qs(p.query)
            if p.path!="/api/roster": self._json({"error":"not found"},404); return
            try: self._json({"status":"DELETED","assignment":asdict(store.remove(q.get("slot",[""])[0]))})
            except KeyError: self._json({"error":"assignment not found"},404)
    return Handler

def main():
    p=argparse.ArgumentParser(prog="operation-pancake-app"); p.add_argument("--root",type=Path,default=Path.cwd()); p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=8765); a=p.parse_args(); s=ThreadingHTTPServer((a.host,a.port),create_handler(a.root.resolve())); print(f"Operation Pancake: http://{a.host}:{a.port}"); s.serve_forever()
if __name__=="__main__": main()

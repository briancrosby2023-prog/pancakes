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
from operation_pancake.evo import EVODefinition, EVOStore, filter_candidates

def _page(title:str,body:str)->bytes:
    doc=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;margin:0;background:#f6f4ef;color:#1d1d1b}}header,main{{max-width:1180px;margin:auto;padding:24px}}header{{display:flex;gap:24px;align-items:center}}a{{color:#684b00}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}input,select,button{{font:inherit;padding:9px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}.card{{background:white;padding:18px;border-radius:12px;margin:12px 0}}.muted{{color:#666}}.error{{background:#fee;padding:10px}}code{{white-space:pre-wrap}}</style></head><body><header><strong>🥞 Operation Pancake</strong><a href="/">Players</a><a href="/roster">Roster</a><a href="/gm">GM / Upgrades</a><a href="/evo">EVO</a><a href="/compare">Compare</a></header><main>{body}</main></body></html>'''; return doc.encode()
def _bool(f,n): return f.get(n,[""])[0].lower() in {"1","true","on","yes"}
def create_handler(root:Path,roster_path:Path|None=None,gm_state_path:Path|None=None,evo_path:Path|None=None):
    gm=GMProduct(root); store=RosterStore(roster_path or root/".operation_pancake"/"roster.json",set(gm.cards)); state_store=GMStateStore(gm_state_path or root/".operation_pancake"/"gm.json",set(gm.cards)); evo_store=EVOStore(evo_path or root/".operation_pancake"/"evo.json"); decisions=GMDecisionService(gm)
    def enriched(): return sorted([(a,gm.cards.get(a.card_id,{}),gm.rank_by_id.get(a.card_id,{}),decisions.decision(a)) for a in store.load()],key=lambda r:(r[0].position,r[0].slot))
    def evo_by_id(eid): return next((e for e in evo_store.load() if e.id==eid),None)
    class Handler(BaseHTTPRequestHandler):
        def _send(self,b,status=200,ct="text/html; charset=utf-8"): self.send_response(status); self.send_header("Content-Type",ct); self.end_headers(); self.wfile.write(b)
        def _json(self,p,status=200): self._send(json.dumps(p,indent=2).encode(),status,"application/json")
        def _redirect(self,p): self.send_response(303); self.send_header("Location",p); self.end_headers()
        def _form(self): return parse_qs(self.rfile.read(int(self.headers.get("Content-Length","0"))).decode())
        def _assignment(self,f):
            cid=f.get("card_id",[""])[0]; c=gm.cards.get(cid)
            if not c: raise ValueError("Choose a valid canonical card")
            return RosterAssignment(cid,f.get("position",[c.get("position") or ""])[0].upper(),f.get("slot",[""])[0].upper(),_bool(f,"starter"),True,_bool(f,"protected"),_bool(f,"rerollable"),f.get("notes",[""])[0])
        def do_GET(self):
            p=urlparse(self.path); q=parse_qs(p.query); state=state_store.load()
            if p.path=="/api/player": self._json(gm.lookup(card_id=q.get("card_id",[None])[0],player_name=q.get("name",[None])[0],position=q.get("position",[None])[0])); return
            if p.path=="/api/roster": self._json({"assignments":[asdict(a)|{"card":gm._identity(c),"pancake_score":s.get("score"),"position_rank":s.get("position_rank"),"gm":d} for a,c,s,d in enriched()]}); return
            if p.path=="/api/gm": self._json({"budget":state.as_dict(),"decisions":[decisions.decision(a) for a in store.load()],"upgrades":decisions.opportunities(store.load(),state.prices,state.spendable_budget)}); return
            if p.path=="/api/evo": self._json({"version":EVOStore.VERSION,"definitions":[asdict(e) for e in evo_store.load()]}); return
            if p.path=="/api/evo/candidates":
                evo=evo_by_id(q.get("evo_id",[""])[0]); ownership=q.get("ownership",["all"])[0]
                if not evo: self._json({"error":"EVO not found"},404); return
                self._json({"evo":asdict(evo),"candidates":filter_candidates(evo,gm.population,{a.card_id for a in store.load()},ownership)}); return
            if p.path=="/api/evo/candidate":
                evo=evo_by_id(q.get("evo_id",[""])[0]); cid=q.get("card_id",[""])[0]; card=gm.cards.get(cid)
                if not evo or not card: self._json({"error":"EVO or card not found"},404); return
                ok,basis=evo.eligible(card); self._json({"eligible":ok,"basis":basis,"current":gm.lookup(card_id=cid),"projection":evo.project(card),"price":state.prices.get(cid)}); return
            if p.path=="/api/gm/decision":
                slot=q.get("slot",[""])[0].upper(); a=next((x for x in store.load() if x.slot==slot),None)
                if not a: self._json({"error":"assignment not found"},404); return
                self._json(decisions.detail(a,state.prices,state.spendable_budget)); return
            if p.path=="/evo":
                eid=q.get("evo_id",[""])[0]; ownership=q.get("ownership",["all"])[0]; evos=evo_store.load(); body='<h1>EVO decision workflow</h1><div class="card"><h2>Create verified EVO</h2><form method="post" action="/evo"><input name="name" placeholder="EVO name" required><input name="target_ovr" type="number" placeholder="Target OVR"><input name="positions" placeholder="Positions, comma separated"><input name="archetypes" placeholder="Archetypes, comma separated"><input name="ovr_min" type="number" placeholder="Starting OVR min"><input name="ovr_max" type="number" placeholder="Starting OVR max"><input name="resource_cost" type="number" min="0" placeholder="Known cost"><input name="boosts" placeholder="Verified boosts: speed=2,..."><input name="notes" placeholder="Notes"><button>Save EVO</button></form><p class="muted">Only verified entered rules are applied. Missing final attributes and final Pancake score remain UNKNOWN.</p></div>'
                if evos: body+='<form><select name="evo_id">'+''.join('<option value="%s" %s>%s</option>'%(html.escape(e.id),'selected' if e.id==eid else '',html.escape(e.name)) for e in evos)+'</select><select name="ownership"><option value="all">All eligible</option><option value="owned">Owned only</option><option value="acquisition">Not owned / acquisition</option></select><button>Find eligible</button></form>'
                evo=evo_by_id(eid) if eid else None
                if evo:
                    cs=filter_candidates(evo,gm.population,{a.card_id for a in store.load()},ownership); body+='<h2>%s</h2><p>Target OVR %s · final attributes %s</p><table><tr><th>Player</th><th>Current</th><th>Target/headroom</th><th>Owned</th><th>Basis / limitations</th></tr>'%(html.escape(evo.name),evo.target_ovr if evo.target_ovr is not None else "UNKNOWN","KNOWN" if evo.final_attributes_known else "UNKNOWN")
                    for c in cs[:200]: body+='<tr><td>%s</td><td>%s OVR · %s · %s</td><td>%s / %s</td><td>%s</td><td>%s<br>%s</td></tr>'%(html.escape(c.get("player_name") or ""),c.get("native_overall") or c.get("overall") or "—",html.escape(c.get("position") or ""),html.escape(c.get("archetype") or "UNKNOWN"),c.get("target_ovr") if c.get("target_ovr") is not None else "UNKNOWN",c.get("ovr_headroom") if c.get("ovr_headroom") is not None else "UNKNOWN","YES" if c["owned"] else "NO",html.escape(", ".join(c["eligibility_basis"])),html.escape(", ".join(c["limitations"])))
                    body+='</table>'
                self._send(_page("EVO",body)); return
            if p.path=="/compare":
                l=q.get("current",[""])[0]; r=q.get("candidate",[""])[0]; price=state.prices.get(r) if state.prices else None; body='<h1>Compare players</h1><form><input name="current" value="%s" placeholder="Current card ID"><input name="candidate" value="%s" placeholder="Candidate card ID"><button>Compare</button></form>'%(html.escape(l),html.escape(r));
                if l and r: body+='<div class="card"><strong>MODEL VALUE / FOOTBALL</strong><code>%s</code><p><strong>MARKET VALUE:</strong> %s</p></div>'%(html.escape(json.dumps(gm.compare(l,r,price),indent=2)),"PRICE UNKNOWN" if price is None else f"current user-supplied price {price:,} coins")
                self._send(_page("Compare",body)); return
            if p.path=="/decision":
                slot=q.get("slot",[""])[0].upper(); a=next((x for x in store.load() if x.slot==slot),None)
                if not a: self._send(_page("Decision","<h1>Assignment not found</h1>"),404); return
                d=decisions.detail(a,state.prices,state.spendable_budget); body='<h1>%s — %s</h1><div class="card"><h2>%s</h2><p>%s</p><p>Confidence: %s</p><p>Limitations: %s</p></div>'%(html.escape(slot),html.escape(d["current"]["player_name"]),d["decision"],html.escape(d["key_reason"]),html.escape(str(d["confidence"])),html.escape(", ".join(d["limitations"]) or "None reported")); self._send(_page("Decision",body)); return
            if p.path=="/gm":
                o=decisions.opportunities(store.load(),state.prices,state.spendable_budget); body='<h1>GM / Upgrades</h1><div class="card"><form method="post" action="/gm/budget"><label>Current coins <input name="current_coins" type="number" min="0" value="%d"></label><label>Reserve <input name="reserve_coins" type="number" min="0" value="%d"></label><button>Save budget</button></form><strong>Spendable: %s coins</strong></div><h2>Portfolio recommendation</h2><div class="card"><code>%s</code></div>'%(state.current_coins,state.reserve_coins,f'{state.spendable_budget:,}',html.escape(json.dumps(o["portfolio"],indent=2))); self._send(_page("GM / Upgrades",body)); return
            if p.path=="/roster":
                body='<h1>Roster dashboard</h1><table><tr><th>Slot</th><th>Player</th><th>OVR</th><th>Pancake</th><th>Rank</th><th>GM decision</th><th>Flags</th></tr>'
                for a,c,s,d in enriched(): body+='<tr><td><a href="/decision?%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s%s</td></tr>'%(urlencode({"slot":a.slot}),html.escape(a.slot),html.escape(c.get("player_name") or a.card_id),c.get("native_overall") or "—",s.get("score") if s.get("score") is not None else "—",s.get("position_rank") or "—",d["decision"],"PROTECTED " if a.protected else "","REROLLABLE" if a.rerollable else "")
                body+='</table>'; self._send(_page("Roster",body)); return
            if p.path!="/": self._send(_page("Not found","<h1>Not found</h1>"),404); return
            name=q.get("name",[""])[0]; pos=q.get("position",[""])[0].upper(); rows=[]
            if name or pos:
                cs=[c for c in gm.population if (not name or name.casefold() in (c.get("player_name") or "").casefold()) and (not pos or c.get("position")==pos)]; cs.sort(key=lambda c:(-(c.get("native_overall") or 0),c.get("player_name") or ""))
                for c in cs[:100]: rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td><form method="post" action="/roster/add"><input type="hidden" name="card_id" value="%s"><input type="hidden" name="position" value="%s"><input name="slot" placeholder="%s1" required><label><input type="checkbox" name="starter" checked>Starter</label><label><input type="checkbox" name="protected">Protected</label><label><input type="checkbox" name="rerollable">Rerollable</label><button>Add</button></form></td></tr>'%(html.escape(c.get("player_name") or ""),html.escape(c.get("position") or ""),c.get("native_overall") or "—",html.escape(c["card_id"]),html.escape(c.get("position") or ""),html.escape(c.get("position") or "")))
            body='<h1>Player intelligence</h1><form><input name="name" value="%s" placeholder="Player name"><input name="position" value="%s" placeholder="Position"><button>Search</button></form>'%(html.escape(name),html.escape(pos));
            if rows: body+='<table><tbody>'+''.join(rows)+'</tbody></table>'
            self._send(_page("Players",body))
        def do_POST(self):
            p=urlparse(self.path); f=self._form()
            try:
                if p.path=="/roster/add": store.add(self._assignment(f)); self._redirect("/roster"); return
                if p.path=="/roster/delete": store.remove(f.get("slot",[""])[0]); self._redirect("/roster"); return
                if p.path=="/gm/budget": state_store.update_budget(int(f.get("current_coins",[0])[0]),int(f.get("reserve_coins",[0])[0])); self._redirect("/gm"); return
                if p.path=="/gm/price": state_store.set_price(f.get("card_id",[""])[0],int(f.get("price",[0])[0])); self._redirect("/gm"); return
                if p.path=="/evo":
                    def oi(n):
                        v=f.get(n,[""])[0].strip(); return int(v) if v else None
                    boosts={}
                    for part in f.get("boosts",[""])[0].split(","):
                        if "=" in part:
                            k,v=part.split("=",1); boosts[k.strip()]=int(v.strip())
                    evos=evo_store.load(); eid=f"evo-{len(evos)+1}"; evos.append(EVODefinition(eid,f.get("name",[""])[0],oi("target_ovr"),tuple(x.strip().upper() for x in f.get("positions",[""])[0].split(",") if x.strip()),tuple(x.strip() for x in f.get("archetypes",[""])[0].split(",") if x.strip()),oi("ovr_min"),oi("ovr_max"),known_attribute_boosts=boosts,resource_cost=oi("resource_cost"),notes=f.get("notes",[""])[0])); evo_store.save(evos); self._redirect("/evo?"+urlencode({"evo_id":eid})); return
                if p.path=="/api/roster": store.add(self._assignment(f)); self._json({"status":"CREATED"},201); return
                if p.path=="/api/gm/budget": self._json(state_store.update_budget(int(f.get("current_coins",[0])[0]),int(f.get("reserve_coins",[0])[0])).as_dict()); return
                if p.path=="/api/gm/price": self._json(state_store.set_price(f.get("card_id",[""])[0],int(f.get("price",[0])[0])).as_dict()); return
                self._send(_page("Not found","<h1>Not found</h1>"),404)
            except (ValueError,KeyError,json.JSONDecodeError) as e:
                if p.path.startswith("/api/"): self._json({"error":str(e)},400)
                else: self._send(_page("Error",'<div class="error">%s</div>'%html.escape(str(e))),400)
        def do_DELETE(self):
            p=urlparse(self.path); q=parse_qs(p.query)
            if p.path!="/api/roster": self._json({"error":"not found"},404); return
            try: self._json({"status":"DELETED","assignment":asdict(store.remove(q.get("slot",[""])[0]))})
            except KeyError: self._json({"error":"assignment not found"},404)
    return Handler
def main():
    p=argparse.ArgumentParser(prog="operation-pancake-app"); p.add_argument("--root",type=Path,default=Path.cwd()); p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=8765); a=p.parse_args(); s=ThreadingHTTPServer((a.host,a.port),create_handler(a.root.resolve())); print(f"Operation Pancake: http://{a.host}:{a.port}"); s.serve_forever()
if __name__=="__main__": main()

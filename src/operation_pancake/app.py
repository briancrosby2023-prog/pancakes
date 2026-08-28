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

def _page(title:str,body:str)->bytes:
    doc=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>body{{font:16px system-ui;margin:0;background:#f6f4ef;color:#1d1d1b}}header,main{{max-width:1180px;margin:auto;padding:24px}}header{{display:flex;gap:24px;align-items:center}}a{{color:#684b00}}form{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}input,select,button{{font:inherit;padding:9px}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}.card{{background:white;padding:18px;border-radius:12px;margin:12px 0}}.muted{{color:#666}}.error{{background:#fee;padding:10px}}code{{white-space:pre-wrap}}</style></head><body><header><strong>🥞 Operation Pancake</strong><a href="/">Players</a><a href="/roster">Roster</a><a href="/gm">GM / Upgrades</a><a href="/compare">Compare</a></header><main>{body}</main></body></html>'''; return doc.encode()
def _bool(f,n): return f.get(n,[""])[0].lower() in {"1","true","on","yes"}
def create_handler(root:Path,roster_path:Path|None=None,gm_state_path:Path|None=None):
    gm=GMProduct(root); store=RosterStore(roster_path or root/".operation_pancake"/"roster.json",set(gm.cards)); state_store=GMStateStore(gm_state_path or root/".operation_pancake"/"gm.json",set(gm.cards)); decisions=GMDecisionService(gm)
    def enriched():
        return sorted([(a,gm.cards.get(a.card_id,{}),gm.rank_by_id.get(a.card_id,{}),decisions.decision(a)) for a in store.load()],key=lambda r:(r[0].position,r[0].slot))
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
            if p.path=="/api/gm/decision":
                slot=q.get("slot",[""])[0].upper(); a=next((x for x in store.load() if x.slot==slot),None)
                if not a: self._json({"error":"assignment not found"},404); return
                self._json(decisions.detail(a,state.prices,state.spendable_budget)); return
            if p.path=="/compare":
                l=q.get("current",[""])[0]; r=q.get("candidate",[""])[0]; price=state.prices.get(r) if state.prices else None; body='<h1>Compare players</h1><form><input name="current" value="%s" placeholder="Current card ID"><input name="candidate" value="%s" placeholder="Candidate card ID"><button>Compare</button></form>'%(html.escape(l),html.escape(r));
                if l and r: body+='<div class="card"><strong>MODEL VALUE / FOOTBALL</strong><code>%s</code><p><strong>MARKET VALUE:</strong> %s</p></div>'%(html.escape(json.dumps(gm.compare(l,r,price),indent=2)),"PRICE UNKNOWN" if price is None else f"current user-supplied price {price:,} coins")
                self._send(_page("Compare",body)); return
            if p.path=="/decision":
                slot=q.get("slot",[""])[0].upper(); a=next((x for x in store.load() if x.slot==slot),None)
                if not a: self._send(_page("Decision","<h1>Assignment not found</h1>"),404); return
                d=decisions.detail(a,state.prices,state.spendable_budget); body='<h1>%s — %s</h1><div class="card"><h2>%s</h2><p>%s</p><p>Confidence: %s</p><p>Limitations: %s</p></div>'%(html.escape(slot),html.escape(d["current"]["player_name"]),d["decision"],html.escape(d["key_reason"]),html.escape(str(d["confidence"])),html.escape(", ".join(d["limitations"]) or "None reported")); body+='<h2>Replacement candidates</h2>'
                for c in d["candidates"]: body+='<div class="card"><strong>%s</strong> — %s OVR · score +%.4f · rank +%s · OVR %+d<br>Intrinsic/model value: %s<br>Market value: %s<br>%s · <a href="/compare?%s">Compare</a></div>'%(html.escape(c["player_name"]),c.get("native_overall") or "—",c["score_improvement"],c["position_rank_improvement"],c["ovr_delta"],html.escape(str(c["intrinsic_value"].get("value_index","unavailable"))),"PRICE UNKNOWN" if c["price"] is None else f'{c["price"]:,} coins',html.escape(c["role_implication"]),urlencode({"current":a.card_id,"candidate":c["card_id"]}))
                self._send(_page("Decision",body)); return
            if p.path=="/gm":
                o=decisions.opportunities(store.load(),state.prices,state.spendable_budget); body='<h1>GM / Upgrades</h1><div class="card"><form method="post" action="/gm/budget"><label>Current coins <input name="current_coins" type="number" min="0" value="%d"></label><label>Reserve <input name="reserve_coins" type="number" min="0" value="%d"></label><button>Save budget</button></form><strong>Spendable: %s coins</strong></div>'%(state.current_coins,state.reserve_coins,f'{state.spendable_budget:,}'); body+='<h2>Portfolio recommendation</h2><div class="card"><code>%s</code></div>'%html.escape(json.dumps(o["portfolio"],indent=2)); body+='<h2>Upgrade opportunities</h2>'
                for x in o["intrinsic"]: body+='<div class="card"><strong>%s: %s → %s</strong><br>Score gain +%.4f · rank gain %s · %s<form method="post" action="/gm/price"><input type="hidden" name="card_id" value="%s"><input name="price" type="number" min="0" placeholder="Current price"><button>Save current price</button></form></div>'%(html.escape(x["slot"]),html.escape(x["current_player"]),html.escape(x["candidate_player"]),x["score_improvement"],x["rank_improvement"],"PRICE UNKNOWN" if x["candidate_price"] is None else f'{x["candidate_price"]:,} coins',html.escape(x["candidate_card_id"]))
                if not o["priced"]: body+='<div class="card">Insufficient priced candidates for a market portfolio. Intrinsic/model opportunities remain available above.</div>'
                self._send(_page("GM / Upgrades",body)); return
            if p.path=="/roster":
                body='<h1>Roster dashboard</h1><table><thead><tr><th>Slot</th><th>Player</th><th>OVR</th><th>Pancake</th><th>Rank</th><th>GM decision</th><th>Confidence</th><th>Reason / flags</th><th>Actions</th></tr></thead><tbody>'
                for a,c,s,d in enriched(): body+='<tr><td>%s<br>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><strong>%s</strong></td><td>%s</td><td>%s<br>%s</td><td><a href="/decision?%s">Why / replacements</a> · <a href="/compare?%s">Compare</a><form method="post" action="/roster/delete"><input type="hidden" name="slot" value="%s"><button>Remove</button></form></td></tr>'%(html.escape(a.position),html.escape(a.slot),html.escape(c.get("player_name") or a.card_id),c.get("native_overall") or "—",s.get("score") if s.get("score") is not None else "—",s.get("position_rank") or "—",d["decision"],html.escape(str(d["confidence"])),html.escape(d["key_reason"]),html.escape("PROTECTED " if a.protected else "")+html.escape("REROLLABLE" if a.rerollable else ""),urlencode({"slot":a.slot}),urlencode({"current":a.card_id}),html.escape(a.slot))
                body+='</tbody></table>'; self._send(_page("Roster",body)); return
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

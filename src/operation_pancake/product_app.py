"""Acceptance-first browser UI composed over the accepted Operation Pancake engines."""
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
from operation_pancake.evo import EVODefinition, EVOStore, compose_evo_decision, enrich_candidates
from operation_pancake.onboarding import SetupStore, ScreenshotStageStore

CSS='''*{box-sizing:border-box}body{margin:0;background:#071019;color:#eaf0f6;font:15px system-ui}header{position:sticky;top:0;background:#0b1722;border-bottom:1px solid #233545;padding:14px 22px;z-index:2}nav{max-width:1320px;margin:auto;display:flex;gap:18px;align-items:center;flex-wrap:wrap}nav a{color:#a9c7df;text-decoration:none}.brand{font-weight:800;color:#fff;margin-right:auto}main{max-width:1320px;margin:auto;padding:28px}.hero{background:linear-gradient(135deg,#102638,#111a23);padding:24px;border:1px solid #294157;border-radius:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.card{background:#0d1b27;border:1px solid #24394b;border-radius:14px;padding:16px;margin:12px 0}.metric{font-size:28px;font-weight:800}.muted{color:#8fa6b8}.warn{color:#ffd27a}.ok{color:#9ee6b0}input,select,button{background:#111f2b;color:#eef5fa;border:1px solid #365064;border-radius:8px;padding:9px}button{cursor:pointer;background:#183c55}form{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}table{width:100%;border-collapse:collapse;background:#0d1b27}th,td{text-align:left;padding:10px;border-bottom:1px solid #263a4b;vertical-align:top}a{color:#79c8ff}.field{display:flex;flex-direction:column;gap:4px}.depth{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.slot{min-height:100px;background:#102434;border:1px solid #31506a;border-radius:12px;padding:10px}.badge{display:inline-block;border:1px solid #45647c;border-radius:999px;padding:2px 7px;margin:2px;font-size:12px}.actions a{margin-right:10px}@media(max-width:800px){.depth{grid-template-columns:repeat(2,1fr)}}'''
def esc(x): return html.escape(str(x if x is not None else 'UNKNOWN'))
def page(title,body): return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head><body><header><nav><span class="brand">🥞 OPERATION PANCAKE</span><a href="/">GM Home</a><a href="/players">Players & Value</a><a href="/roster">Roster</a><a href="/compare">Compare</a><a href="/evo">EVO</a><a href="/gm">GM / Upgrades</a><a href="/setup">Team Setup</a></nav></header><main>{body}</main></body></html>'''.encode()
def b(f,n): return f.get(n,[''])[0].lower() in {'1','true','on','yes'}
def intval(v,default=0):
    try:return int(v)
    except (TypeError,ValueError):return default

def create_handler(root:Path,roster_path:Path|None=None,gm_state_path:Path|None=None,evo_path:Path|None=None,setup_path:Path|None=None,stage_path:Path|None=None):
    gm=GMProduct(root); roster=RosterStore(roster_path or root/'.operation_pancake/roster.json',set(gm.cards)); budgets=GMStateStore(gm_state_path or root/'.operation_pancake/gm.json',set(gm.cards)); evos=EVOStore(evo_path or root/'.operation_pancake/evo.json'); setup=SetupStore(setup_path or root/'.operation_pancake/setup.json'); stages=ScreenshotStageStore(stage_path or root/'.operation_pancake/screenshots.json'); decisions=GMDecisionService(gm)
    def rows(): return roster.load()
    def owned(): return {x.card_id for x in rows()}
    def slot(name): return next((x for x in rows() if x.slot==name.upper()),None)
    def evo(eid): return next((x for x in evos.load() if x.id==eid),None)
    def identity(c):
        # Canonical identity fields currently proven by GMProduct._identity.
        return f'{esc(c.get("player_name"))} · {esc(c.get("position"))} {esc(c.get("native_overall"))} · {esc(c.get("program"))} · {esc(c.get("archetype"))} · <span class="muted">{esc(c.get("card_id"))}</span>'
    def card_options(cards,selected=''):
        return ''.join(f'<option value="{esc(c["card_id"])}" {"selected" if c["card_id"]==selected else ""}>{esc(c.get("player_name"))} — {esc(c.get("position"))} {esc(c.get("native_overall"))} — {esc(c.get("program"))} — {esc(c.get("archetype"))} — {esc(c["card_id"])}</option>' for c in cards)
    def assignment(f):
        cid=f.get('card_id',[''])[0]; c=gm.cards.get(cid)
        if not c: raise ValueError('Choose a valid canonical card')
        raw=f.get('current_level',[''])[0].strip(); level=None if not raw else max(0,int(raw))
        return RosterAssignment(cid,f.get('position',[c.get('position') or ''])[0].upper(),f.get('slot',[''])[0].upper(),b(f,'starter'),True,b(f,'protected'),b(f,'rerollable'),f.get('notes',[''])[0],level)
    class H(BaseHTTPRequestHandler):
        def send(self,data,status=200,ct='text/html; charset=utf-8'): self.send_response(status); self.send_header('Content-Type',ct); self.end_headers(); self.wfile.write(data)
        def js(self,obj,status=200): self.send(json.dumps(obj,indent=2).encode(),status,'application/json')
        def redir(self,path): self.send_response(303); self.send_header('Location',path); self.end_headers()
        def form(self): return parse_qs(self.rfile.read(int(self.headers.get('Content-Length','0'))).decode())
        def do_GET(self):
            p=urlparse(self.path); q=parse_qs(p.query); state=budgets.load(); roster_rows=rows()
            if p.path=='/api/player': self.js(gm.lookup(card_id=q.get('card_id',[None])[0],player_name=q.get('name',[None])[0],position=q.get('position',[None])[0])); return
            if p.path=='/api/roster': self.js({'assignments':[asdict(x) for x in roster_rows]}); return
            if p.path=='/api/gm': self.js({'budget':state.as_dict(),'decisions':[decisions.decision(x) for x in roster_rows],'upgrades':decisions.opportunities(roster_rows,state.prices,state.spendable_budget)}); return
            if p.path=='/api/evo': self.js({'version':EVOStore.VERSION,'definitions':[asdict(x) for x in evos.load()]}); return
            if p.path=='/api/evo/candidates':
                e=evo(q.get('evo_id',[''])[0]); pool=q.get('ownership',['all'])[0]
                if not e:self.js({'error':'EVO not found'},404);return
                self.js({'evo':asdict(e),'ownership':pool,'candidates':enrich_candidates(e,gm,owned(),pool)});return
            if p.path=='/api/replacements':
                a=slot(q.get('slot',[''])[0]); self.js(decisions.detail(a,state.prices,state.spendable_budget) if a else {'error':'assignment not found'},200 if a else 404);return
            if p.path=='/setup':
                staged=stages.load(); body='<div class="hero"><h1>Team Setup</h1><p>Start with what you know. A partial roster is valid; UNKNOWN stays UNKNOWN.</p></div>'
                body+=f'<div class="grid"><div class="card"><h2>Coins</h2><form method="post" action="/setup"><label class="field">Current coins<input name="current_coins" type="number" min="0" value="{state.current_coins}"></label><label class="field">Reserve coins<input name="reserve_coins" type="number" min="0" value="{state.reserve_coins}"></label><button>Save & continue</button></form><p>Spendable: <strong>{state.spendable_budget:,}</strong></p></div><div class="card"><h2>Roster screenshots</h2><form method="post" action="/screenshots/stage"><input name="filenames" placeholder="lineup-1.png, lineup-2.png" required><button>Stage screenshots</button></form><p class="muted">Multiple screenshots may be staged. Automatic screenshot extraction is NOT AVAILABLE on the proven local capability, so no player/card is invented from an image. Review and add canonical cards before import.</p></div></div>'
                body+='<div class="card"><h2>Review before import</h2>'+(('<table><tr><th>Evidence</th><th>Status</th><th>Extraction</th></tr>'+''.join(f'<tr><td>{esc(x.filename)}</td><td>{esc(x.status)}</td><td>{esc(x.extraction_status)}</td></tr>' for x in staged)+'</table>') if staged else '<p>No screenshots staged yet.</p>')+'<p><a href="/players">Review canonical players and add known roster cards →</a></p></div>'; self.send(page('Team Setup',body));return
            if p.path=='/roster':
                groups={};
                for a in roster_rows: groups.setdefault(a.position,[]).append(a)
                body='<div class="hero"><h1>Visual Depth Chart</h1><p>Partial rosters are first-class. Empty positions remain visibly open.</p></div><div class="depth">'
                positions=['QB','HB','FB','WR','TE','LT','LG','C','RG','RT','EDGE','DT','MIKE','SAM','WILL','CB','FS','SS']
                for pos in positions:
                    rs=sorted(groups.get(pos,[]),key=lambda x:x.slot); content=''.join(f'<div><strong>{esc(a.slot)}</strong><br>{identity(gm.cards[a.card_id])}<br>{"<span class=badge>Starter</span>" if a.starter else ""}{"<span class=badge>Protected</span>" if a.protected else ""}{"<span class=badge>Rerollable L"+esc(a.current_level)+"</span>" if a.rerollable else ""}<br><a href="/compare?current={esc(a.card_id)}">Compare</a> · <a href="/replacements?slot={esc(a.slot)}">Replacements</a></div>' for a in rs) or '<span class="muted">OPEN / UNKNOWN</span>'
                    body+=f'<div class="slot"><b>{pos}</b><hr>{content}</div>'
                body+='</div><div class="card"><h2>Manage roster</h2>'
                for a in roster_rows: body+=f'<form method="post" action="/roster/update"><input type="hidden" name="old_slot" value="{esc(a.slot)}"><input type="hidden" name="card_id" value="{esc(a.card_id)}"><input type="hidden" name="position" value="{esc(a.position)}"><input name="slot" value="{esc(a.slot)}"><label><input type="checkbox" name="starter" {"checked" if a.starter else ""}>Starter</label><label><input type="checkbox" name="protected" {"checked" if a.protected else ""}>Protected</label><label><input type="checkbox" name="rerollable" {"checked" if a.rerollable else ""}>Rerollable</label><input name="current_level" type="number" min="0" value="{a.current_level if a.current_level is not None else ""}" placeholder="Current Level"><button>Save {esc(a.slot)}</button></form>'
                body+='</div>'; self.send(page('Roster',body));return
            if p.path=='/players':
                name=q.get('name',[''])[0]; pos=q.get('position',[''])[0].upper(); omin=intval(q.get('ovr_min',['0'])[0]); omax=intval(q.get('ovr_max',['99'])[0],99); cards=[c for c in gm.population if (not name or name.casefold() in (c.get('player_name') or '').casefold()) and (not pos or c.get('position')==pos) and omin<=intval(c.get('native_overall'))<=omax]; cards.sort(key=lambda c:(-(c.get('native_overall') or 0),gm.rank_by_id.get(c['card_id'],{}).get('position_rank') or 99999,c.get('player_name') or ''))
                top=sorted(gm.population,key=lambda c:(gm.rank_by_id.get(c['card_id'],{}).get('position_rank') or 99999))[:12]
                body='<div class="hero"><h1>Players & Value</h1><p>Canonical card identity + production ranking. Market value is shown only when user-supplied price evidence exists.</p></div><form><input name="name" value="'+esc(name)+'" placeholder="Name"><input name="position" value="'+esc(pos)+'" placeholder="Position"><input name="ovr_min" type="number" value="'+str(omin)+'" placeholder="OVR min"><input name="ovr_max" type="number" value="'+str(omax)+'" placeholder="OVR max"><button>Filter</button></form>'
                show=cards[:100] if (name or pos or 'ovr_min' in q or 'ovr_max' in q) else top
                body+='<div class="card"><h2>'+('Search results' if (name or pos) else 'Production leaders')+'</h2><table><tr><th>Canonical card/version</th><th>Pancake</th><th>Value</th><th>Actions</th></tr>'
                for c in show:
                    s=gm.rank_by_id.get(c['card_id'],{}); price=state.prices.get(c['card_id']); body+=f'<tr><td>{identity(c)}</td><td>Score {esc(s.get("score"))}<br>Position rank {esc(s.get("position_rank"))}</td><td>{"PRICE UNKNOWN" if price is None else f"{price:,} coins"}</td><td><a href="/compare?candidate={esc(c["card_id"])}">Compare</a><form method="post" action="/roster/add"><input type="hidden" name="card_id" value="{esc(c["card_id"])}"><input type="hidden" name="position" value="{esc(c.get("position"))}"><input name="slot" placeholder="{esc(c.get("position"))}1" required><label><input type="checkbox" name="starter" checked>Starter</label><label><input type="checkbox" name="rerollable">Rerollable</label><input name="current_level" type="number" min="0" placeholder="Current Level"><button>Add roster</button></form></td></tr>'
                body+='</table></div>'; self.send(page('Players & Value',body));return
            if p.path=='/compare':
                current=q.get('current',[''])[0]; candidate=q.get('candidate',[''])[0]; name=q.get('name',[''])[0]; pos=q.get('position',[''])[0].upper(); omin=intval(q.get('ovr_min',['0'])[0]); omax=intval(q.get('ovr_max',['99'])[0],99); pool=[c for c in gm.population if (not name or name.casefold() in (c.get('player_name') or '').casefold()) and (not pos or c.get('position')==pos) and omin<=intval(c.get('native_overall'))<=omax][:500]
                body='<div class="hero"><h1>Compare</h1><p>Start from your roster, a name, a position, or an OVR range.</p></div><form><label class="field">Current roster<select name="current"><option value="">Choose</option>'+''.join(f'<option value="{esc(a.card_id)}" {"selected" if a.card_id==current else ""}>{esc(a.slot)} — {esc(gm.cards[a.card_id].get("player_name"))}</option>' for a in roster_rows)+'</select></label><label class="field">Name<input name="name" value="'+esc(name)+'"></label><label class="field">Position<input name="position" value="'+esc(pos)+'"></label><label class="field">OVR min<input name="ovr_min" type="number" value="'+str(omin)+'"></label><label class="field">OVR max<input name="ovr_max" type="number" value="'+str(omax)+'"></label><button>Find candidates</button></form>'
                if pool: body+='<form><input type="hidden" name="current" value="'+esc(current)+'"><label class="field">Candidate<select name="candidate">'+card_options(pool,candidate)+'</select></label><button>Compare selected</button></form>'
                if current and candidate:
                    price=state.prices.get(candidate); body+=f'<div class="card"><pre>{esc(json.dumps(gm.compare(current,candidate,price),indent=2))}</pre><p>{"PRICE UNKNOWN" if price is None else f"Candidate price {price:,} coins"}</p></div>'
                self.send(page('Compare',body));return
            if p.path=='/replacements':
                a=slot(q.get('slot',[''])[0]);
                if not a:self.send(page('Replacements','<h1>Assignment not found</h1>'),404);return
                d=decisions.detail(a,state.prices,state.spendable_budget); body=f'<h1>{esc(a.slot)} replacements</h1><div class="card"><b>{esc(d["decision"])}</b><p>{esc(d["key_reason"])}</p></div><table><tr><th>Candidate</th><th>Gain</th><th>Price</th></tr>'+''.join(f'<tr><td><a href="/compare?{urlencode({"current":a.card_id,"candidate":c["card_id"]})}">{esc(c["player_name"])}</a></td><td>{esc(c.get("score_improvement"))}</td><td>{"PRICE UNKNOWN" if c.get("price") is None else esc(c["price"])}</td></tr>' for c in d['candidates'])+'</table>';self.send(page('Replacements',body));return
            if p.path=='/gm':
                o=decisions.opportunities(roster_rows,state.prices,state.spendable_budget); body=f'<div class="hero"><h1>GM / Upgrades</h1><div class="grid"><div><span class="muted">Current</span><div class="metric">{state.current_coins:,}</div></div><div><span class="muted">Reserve</span><div class="metric">{state.reserve_coins:,}</div></div><div><span class="muted">Spendable</span><div class="metric">{state.spendable_budget:,}</div></div></div></div><form method="post" action="/gm/budget"><input name="current_coins" type="number" min="0" value="{state.current_coins}"><input name="reserve_coins" type="number" min="0" value="{state.reserve_coins}"><button>Save</button></form><div class="card"><h2>Budget-aware portfolio</h2><pre>{esc(json.dumps(o["portfolio"],indent=2))}</pre></div>';self.send(page('GM',body));return
            if p.path=='/evo':
                eid=q.get('evo_id',[''])[0]; pool=q.get('ownership',['owned'])[0]; chosen=evo(eid); all_evos=evos.load(); body='<div class="hero"><h1>Current EVO</h1><p>Choose a current EVO, then evaluate owned or acquisition candidates against your roster and replacement path.</p></div><form><select name="evo_id"><option value="">Select Current EVO</option>'+''.join(f'<option value="{esc(e.id)}" {"selected" if e.id==eid else ""}>{esc(e.name)} — target {esc(e.target_ovr)}</option>' for e in all_evos)+'</select><select name="ownership"><option value="owned" '+('selected' if pool=='owned' else '')+'>Owned EVO candidates</option><option value="acquisition" '+('selected' if pool=='acquisition' else '')+'>Acquisition EVO candidates</option></select><button>Evaluate</button></form>'
                if chosen:
                    cs=enrich_candidates(chosen,gm,owned(),pool); body+='<div class="card"><table><tr><th>Candidate</th><th>Ownership</th><th>Projection</th><th>Decision</th></tr>'+''.join(f'<tr><td>{esc(c.get("player_name"))} · {esc(c.get("position"))} {esc(c.get("native_overall"))}</td><td>{esc(c["ownership"])}</td><td>Target {esc(c.get("target_ovr"))}<br>{esc((c.get("production") or {}).get("confidence"))}</td><td>'+''.join(f'<a href="/evo/decision?{urlencode({"evo_id":chosen.id,"slot":a.slot,"card_id":c["card_id"]})}">vs {esc(a.slot)}</a> ' for a in roster_rows if a.position==c.get('position'))+'</td></tr>' for c in cs[:200])+'</table></div>'
                body+='<div class="card"><h2>Manage / Add EVO</h2><form method="post" action="/evo"><input name="name" placeholder="EVO name" required><input name="target_ovr" type="number" placeholder="Target OVR"><input name="positions" placeholder="Positions"><input name="archetypes" placeholder="Archetypes"><input name="ovr_min" type="number" placeholder="OVR min"><input name="ovr_max" type="number" placeholder="OVR max"><input name="resource_cost" type="number" min="0" placeholder="Resource cost"><input name="boosts" placeholder="speed=2,..."><button>Add EVO</button></form><p class="muted">Only verified boosts are projected. Unknown final attributes remain UNKNOWN.</p></div>';self.send(page('EVO',body));return
            if p.path=='/evo/decision':
                e=evo(q.get('evo_id',[''])[0]); a=slot(q.get('slot',[''])[0]); cid=q.get('card_id',[''])[0]
                if not e or not a:self.send(page('EVO decision','<h1>EVO or roster slot not found</h1>'),404);return
                d=compose_evo_decision(evo=e,candidate_id=cid,assignment=a,gm=gm,gm_decisions=decisions,prices=state.prices,budget_state=state,owned_ids=owned()); self.send(page('EVO decision',f'<h1>Three-way EVO decision</h1><div class="card"><h2>{esc(d["decision"]["decision"])}</h2><p>{esc("; ".join(d["decision"]["reasons"]))}</p><pre>{esc(json.dumps(d,indent=2))}</pre></div>'));return
            if p.path!='/':self.send(page('Not found','<h1>Not found</h1>'),404);return
            if not setup.load().completed:
                self.send(page('Welcome','<div class="hero"><h1>Build your team. Know every coin.</h1><p>First run starts with Team Setup: current coins, reserve, and whatever portion of your roster you know today.</p><p><a href="/setup">Start Team Setup →</a></p></div>'));return
            o=decisions.opportunities(roster_rows,state.prices,state.spendable_budget); body=f'<div class="hero"><h1>GM Home</h1><div class="grid"><div><span class="muted">Current coins</span><div class="metric">{state.current_coins:,}</div></div><div><span class="muted">Reserve</span><div class="metric">{state.reserve_coins:,}</div></div><div><span class="muted">Spendable</span><div class="metric">{state.spendable_budget:,}</div></div><div><span class="muted">Roster cards</span><div class="metric">{len(roster_rows)}</div></div></div></div><div class="grid"><div class="card"><h2>Roster</h2><p>Visual depth chart with partial-roster support.</p><a href="/roster">Open roster →</a></div><div class="card"><h2>Players & Value</h2><p>Production leaders, canonical versions, price evidence.</p><a href="/players">Find value →</a></div><div class="card"><h2>Upgrade portfolio</h2><pre>{esc(json.dumps(o["portfolio"],indent=2))}</pre></div><div class="card"><h2>EVO</h2><p>Owned and acquisition paths composed with GM economics.</p><a href="/evo">Evaluate EVO →</a></div></div>';self.send(page('GM Home',body))
        def do_POST(self):
            p=urlparse(self.path); f=self.form()
            try:
                if p.path=='/setup': budgets.update_budget(intval(f.get('current_coins',[0])[0]),intval(f.get('reserve_coins',[0])[0])); setup.complete(); self.redir('/');return
                if p.path=='/screenshots/stage': stages.stage([x.strip() for x in f.get('filenames',[''])[0].split(',')]); self.redir('/setup');return
                if p.path=='/roster/add': roster.add(assignment(f)); self.redir('/roster');return
                if p.path=='/roster/update':
                    a=assignment(f); roster.update(f.get('old_slot',[''])[0],card_id=a.card_id,position=a.position,slot=a.slot,starter=a.starter,owned=True,protected=a.protected,rerollable=a.rerollable,notes=a.notes,current_level=a.current_level); self.redir('/roster');return
                if p.path=='/gm/budget': budgets.update_budget(intval(f.get('current_coins',[0])[0]),intval(f.get('reserve_coins',[0])[0])); self.redir('/gm');return
                if p.path=='/evo':
                    def oi(n):
                        v=f.get(n,[''])[0].strip();return int(v) if v else None
                    boosts={}
                    for part in f.get('boosts',[''])[0].split(','):
                        if '=' in part:k,v=part.split('=',1);boosts[k.strip()]=int(v.strip())
                    all_evos=evos.load(); eid=f'evo-{len(all_evos)+1}'; all_evos.append(EVODefinition(eid,f.get('name',[''])[0],oi('target_ovr'),tuple(x.strip().upper() for x in f.get('positions',[''])[0].split(',') if x.strip()),tuple(x.strip() for x in f.get('archetypes',[''])[0].split(',') if x.strip()),oi('ovr_min'),oi('ovr_max'),known_attribute_boosts=boosts,resource_cost=oi('resource_cost'))); evos.save(all_evos);self.redir('/evo?'+urlencode({'evo_id':eid}));return
                self.send(page('Not found','<h1>Not found</h1>'),404)
            except (ValueError,KeyError,json.JSONDecodeError) as e:self.send(page('Error',f'<div class="card warn">{esc(e)}</div>'),400)
    return H

def main():
    p=argparse.ArgumentParser(prog='operation-pancake-app');p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8765);a=p.parse_args();s=ThreadingHTTPServer((a.host,a.port),create_handler(a.root.resolve()));print(f'Operation Pancake: http://{a.host}:{a.port}');s.serve_forever()
if __name__=='__main__':main()

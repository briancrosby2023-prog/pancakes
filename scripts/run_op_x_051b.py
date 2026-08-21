"""Execute OP-X-051 over the canonical CFB27 population and persist evidence."""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict

from operation_pancake.production.gm import GMProduct
from operation_pancake.production.role_intelligence import ROLE_ATTRIBUTES, card_role_candidates, family, role_profile, role_alternatives, scientific_firewall
from operation_pancake.production.roster import normalize_name

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/research/op_x_051'
OUT.mkdir(parents=True,exist_ok=True)

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding='utf-8')

def scoreable(ev): return ev.get('score') is not None

def main():
    gm=GMProduct(ROOT)
    population=gm.population
    evaluations={c['card_id']:gm.lookup(card_id=c['card_id']) for c in population}
    scoreable_ids={cid for cid,x in evaluations.items() if scoreable(x.get('evaluation',{}))}
    role_candidates=[]; complete=defaultdict(list)
    for card in population:
        for rc in card_role_candidates(card):
            row={'card_id':card['card_id'],'player':card.get('player_name'),'position':card.get('position'),'ovr':card.get('native_overall'),**rc}
            role_candidates.append(row)
            if rc['attribute_coverage']==1 and card['card_id'] in scoreable_ids: complete[(rc['position_family'],rc['role'])].append(card)
    boards={}; supported=blocked=0
    for fam,roles in ROLE_ATTRIBUTES.items():
        for role,attrs in roles.items():
            key=f'{fam}:{role}'; rows=[]
            for card in complete.get((fam,role),[]):
                ev=evaluations[card['card_id']]['evaluation']; rows.append({'card_id':card['card_id'],'player':card.get('player_name'),'ovr':card.get('native_overall'),'base_pancake_score':ev.get('score'),'position_rank':ev.get('position_rank'),'role_fit':'UNKNOWN','market_used':False})
            rows.sort(key=lambda r:(-(r['base_pancake_score'] or -1),-(r['ovr'] or -1),r['card_id']))
            status='SUPPORTED' if rows else 'ROLE BOARD BLOCKED — INSUFFICIENT EVIDENCE'; supported+=bool(rows); blocked+=not bool(rows)
            boards[key]={'status':status,'profile':role_profile(fam,role),'candidate_count':len(rows),'rows':rows[:25]}
    money=[]
    for (fam,role),cards in complete.items():
        attrs=ROLE_ATTRIBUTES[fam][role]; ordered=sorted(cards,key=lambda c:(-(c.get('native_overall') or 0),c['card_id']))
        for hi in ordered:
            ha=hi.get('attributes') or hi.get('stats') or {}; best=None
            for lo in ordered:
                if (lo.get('native_overall') or 0)>=(hi.get('native_overall') or 0): continue
                la=lo.get('attributes') or lo.get('stats') or {}; dist=sum(abs(float(la[a])-float(ha[a])) for a in attrs)
                if dist<=5 and (best is None or dist<best[0]): best=(dist,lo)
            if best:
                dist,lo=best; money.append({'position_family':fam,'role':role,'higher_card_id':hi['card_id'],'higher_player':hi.get('player_name'),'higher_ovr':hi.get('native_overall'),'lower_card_id':lo['card_id'],'lower_player':lo.get('player_name'),'lower_ovr':lo.get('native_overall'),'trait_distance':round(dist,3),'classification':'NEAR ROLE EQUIVALENT','price_conclusion':'UNKNOWN'})
    roster_path=ROOT/'data/production/roster/canonical_roster.json'; roster_raw=json.loads(roster_path.read_text()) if roster_path.exists() else []
    entries=roster_raw if isinstance(roster_raw,list) else roster_raw.get('roster',roster_raw.get('entries',roster_raw.get('players',[]))); roster=[]
    for entry in entries:
        cid=entry.get('canonical_card_id') or entry.get('card_id') or entry.get('resolved_card_id'); card=gm.cards.get(cid) if cid else None
        if card is None:
            name=entry.get('player_name') or entry.get('name'); ms=[c for c in population if name and normalize_name(c.get('player_name') or '')==normalize_name(name)]
            if len(ms)==1: card=ms[0]; cid=card['card_id']
        roster.append({'slot':entry.get('slot') or entry.get('roster_slot'),'input_name':entry.get('player_name') or entry.get('name'),'card_id':cid,'resolved':bool(card),'scored':bool(cid in scoreable_ids),'deployment':'DEPLOYMENT REQUIRED','role_candidates':card_role_candidates(card) if card else []})
    target_pairs=[('Anthony Donkoh','Brendan Black'),('Samson Okunlola',"E'Marion Harris"),('Dashawn Spears','Bray Hubbard'),('Cole','Kip Lewis'),('McClain','Kobe Black')]
    def matches(name): return [c for c in population if normalize_name(c.get('player_name') or '')==normalize_name(name)]
    targets=[]
    for current_name,candidate_name in target_pairs:
        cm,tm=matches(current_name),matches(candidate_name); row={'current_name':current_name,'candidate_name':candidate_name,'current_matches':[c['card_id'] for c in cm],'candidate_matches':[c['card_id'] for c in tm],'purchase_action':'UNCHANGED','market_conclusion':'PRICE CHECK REQUIRED'}
        if len(cm)==1 and len(tm)==1:
            c,t=cm[0],tm[0]; ce=evaluations[c['card_id']]['evaluation']; te=evaluations[t['card_id']]['evaluation']; row.update({'status':'EXECUTED','current_card_id':c['card_id'],'candidate_card_id':t['card_id'],'frozen_score_current':ce.get('score'),'frozen_score_candidate':te.get('score'),'frozen_pancake_delta':None if ce.get('score') is None or te.get('score') is None else round(te['score']-ce['score'],6),'role_specific_relevance':'DEPLOYMENT REQUIRED','binding_trait_improvement':'UNKNOWN','secondary_gains':'UNKNOWN','contextual_risks':'UNKNOWN','deployment_change_possibility':'UNKNOWN'}); fam=family(c.get('position') or ''); row['population_role_challenges']={r:role_alternatives(ROOT,t['card_id'],r,10) for r in ROLE_ATTRIBUTES.get(fam,{})}
        else: row['status']='AMBIGUOUS CARD VERSION' if cm and tm else 'UNRESOLVED IDENTITY'
        targets.append(row)
    free_bnd=[{'card_id':r['card_id'],'acquisition_state':'UNKNOWN','purchase_avoidance':'UNKNOWN','fabricated_coin_value':None} for r in roster if r['resolved']]
    context={'canonical_population':len(population),'scoreable_population':len(scoreable_ids),'role_candidate_records':sum(r['classification']=='ROLE CANDIDATE' for r in role_candidates),'unknown_role_candidate_records':sum(r['classification']=='UNKNOWN' for r in role_candidates),'supported_role_boards':supported,'blocked_role_boards':blocked,'roster_entries':len(roster),'roster_resolved':sum(r['resolved'] for r in roster),'roster_scored':sum(r['scored'] for r in roster)}
    dump('CONTEXT_COVERAGE.json',context); dump('ROLE_PROFILES.json',{f'{f}:{r}':role_profile(f,r) for f,roles in ROLE_ATTRIBUTES.items() for r in roles}); dump('ROLE_BOARDS.json',{'summary':{'supported':supported,'blocked':blocked},'boards':boards}); dump('ROLE_ALTERNATIVES.json',{'target_challenge_alternatives':targets}); dump('ROLE_MONEYBALL.json',{'case_count':len(money),'cases':money[:1000],'truncated':len(money)>1000}); dump('OVR_WASTE.json',{'supported_case_count':0,'cases':[],'status':'UNKNOWN — requires evidence that surplus attributes are role-irrelevant; no inference from low weight alone'}); dump('BINDING_TRAITS.json',{'finding_count':sum(len(v) for v in ROLE_ATTRIBUTES.values()),'profiles':{f'{f}:{r}':list(a) for f,rs in ROLE_ATTRIBUTES.items() for r,a in rs.items()}}); dump('ROSTER_ROLE_MAP.json',{'entries':roster,'summary':{'entries':len(roster),'resolved':sum(r['resolved'] for r in roster),'scored':sum(r['scored'] for r in roster),'deployment_required':sum(r['resolved'] for r in roster)}}); dump('ROSTER_MISMATCHES.json',{'supported_count':0,'cases':[],'status':'UNKNOWN — deployment evidence absent; no mismatch inferred'}); dump('ZERO_COIN_UPGRADES.json',{'supported_count':0,'cases':[],'status':'UNKNOWN — acquisition/deployment evidence insufficient; unsupported assumptions forbidden'}); dump('PURCHASE_AVOIDANCE.json',{'supported_count':0,'cases':[],'coin_values':[],'status':'UNKNOWN unless free/BND acquisition and role coverage are both evidenced'}); dump('CURRENT_TARGET_REVIEW.json',{'targets':targets}); dump('TARGET_CHALLENGES.json',{'targets':targets,'seeded_challengers':['Addison Nichols','Drew Azzopardi','Jay Green','Isaiah Glasker','Dontay Joyner']}); dump('FREE_BND_ROLE_COVERAGE.json',{'entries':free_bnd,'supported_purchase_avoidance_count':0})
    residual_path=OUT/'META_ROLE_RESIDUALS.json'; residual=json.loads(residual_path.read_text()) if residual_path.exists() else {}; residual['execution_status']='EXECUTED'; residual['model_error_claimed']=False; dump('META_ROLE_RESIDUALS.json',residual); dump('RESEARCH_QUEUE.json',{'priorities':['resolve deployment roles for current roster','capture exact target card versions where ambiguous','capture equipped abilities/AP','capture observed usage vs recommendation separately','capture free/BND acquisition evidence']})
    (OUT/'PRODUCT_DEMOS.md').write_text(f"# OP-X-051 Product Demos\n\nCanonical cards: {len(population)}; scoreable: {len(scoreable_ids)}.\nRole-candidate records: {context['role_candidate_records']}.\nSupported role boards: {supported}; blocked: {blocked}.\nMoneyball role relationships: {len(money)}.\n\nUNKNOWN context never changes frozen score/rank/percentile. Market price is not used for football role ranking.\n")
    summary={'status':'EXECUTED','counts':context,'role_moneyball_cases':len(money),'ovr_waste_supported':0,'roster_mismatches_supported':0,'zero_coin_supported':0,'purchase_avoidance_supported':0,'scientific_firewall':scientific_firewall(),'targets':targets}; dump('execution_summary.json',summary); (OUT/'RESULTS.md').write_text('# OP-X-051B Execution Results\n\n'+json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()

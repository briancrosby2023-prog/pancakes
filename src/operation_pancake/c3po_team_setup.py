"""Bounded C-3PO -> Team Setup bridge for OFFENSE LT/RT only."""
from __future__ import annotations
from difflib import SequenceMatcher
from pathlib import Path
from operation_pancake.c3po_tackle_resolver import TackleResolution,resolve_tackles
from operation_pancake.team_import import Candidate,normalize_name
TACKLE_SLOTS=('LT1','RT1')
def _is_cfb27(card):
 markers=[card.get(k) for k in ('game','season','title','dataset') if card.get(k)]
 if not markers:return True
 text=' '.join(str(v).upper() for v in markers)
 if 'CFB25' in text or 'CFB 25' in text or 'CFB26' in text or 'CFB 26' in text:return False
 return '27' in text
def _safe_name_match(observed,canonical):
 a=[normalize_name(x) for x in observed.split() if normalize_name(x)];b=[normalize_name(x) for x in canonical.split() if normalize_name(x)]
 if len(a)!=len(b) or not a:return False
 for seen,expected in zip(a,b,strict=True):
  if seen==expected:continue
  if min(len(seen),len(expected))<6 or SequenceMatcher(None,seen,expected).ratio()<.86:return False
 return True
def search_tackle_cards(name,position,cards):
 query=normalize_name(name or '')
 if not query:return []
 pool=[c for c in cards if _is_cfb27(c)];identities={}
 for c in pool:
  n=c.get('player_name') or ''
  if n:identities.setdefault(n,[]).append(c)
 exact=[n for n in identities if normalize_name(n)==query]
 if exact:chosen=exact
 else:
  scored=sorted((SequenceMatcher(None,query,normalize_name(n)).ratio(),n) for n in identities);scored.reverse()
  if not scored or scored[0][0]<.78:return []
  best=scored[0][0];chosen=[n for score,n in scored if score>=max(.78,best-.08) and _safe_name_match(name,n)]
 rows=[c for n in chosen for c in identities[n]];return sorted(rows,key=lambda c:(c.get('player_name') or '',-(int(c['native_overall']) if c.get('native_overall') is not None else -1),str(c.get('card_id') or '')))
def _set_candidate_card(candidate,card,provenance):
 candidate.player_name=card.get('player_name');candidate.program=card.get('program');candidate.canonical_card_id=card.get('card_id');candidate.match_status='MATCHED';candidate.confidence=1.0
 if provenance not in candidate.provenance:candidate.provenance.append(provenance)
 diagnostics=dict(candidate.match_diagnostics);diagnostics.pop('user_name_fallback',None);candidate.match_diagnostics=diagnostics
def apply_user_tackle_name(candidate,name,cards):
 if candidate.slot not in TACKLE_SLOTS:return 'UNSUPPORTED'
 position=candidate.position or candidate.slot.rstrip('1234567890');results=search_tackle_cards(name,position,cards);diagnostics=dict(candidate.match_diagnostics);diagnostics['user_name_fallback']={'query':name.strip(),'result_card_ids':[r.get('card_id') for r in results]};candidate.match_diagnostics=diagnostics
 if not results:candidate.match_status='UNMATCHED';return 'UNRESOLVED'
 if len(results)==1:_set_candidate_card(candidate,results[0],'user-confirmed:cfb27-name-search');return 'MATCHED'
 candidate.canonical_card_id=None;candidate.match_status='AMBIGUOUS';candidate.confidence=None;return 'CHOICE_REQUIRED'
def select_user_tackle_card(candidate,card_id,cards):
 offered=set(candidate.match_diagnostics.get('user_name_fallback',{}).get('result_card_ids') or [])
 if card_id not in offered:return False
 card=next((r for r in cards if r.get('card_id')==card_id),None)
 if card is None or not _is_cfb27(card):return False
 _set_candidate_card(candidate,card,'user-confirmed:cfb27-name-search');return True
def _candidate(state,slot):
 found=next((c for c in state.candidates if c.group=='OFFENSE' and c.slot==slot),None)
 if found is not None:return found
 found=Candidate(id=f'c3po-{slot.lower()}',group='OFFENSE',slot=slot);state.candidates.append(found);return found
def _backup(row):return {'observed_player_name':row.observed_player_name,'player_name':row.canonical_player_identity,'displayed_ovr':row.displayed_lineup_ovr,'native_card_ovr':row.native_card_ovr,'native_position':row.native_position,'display_ovr_delta':row.display_ovr_delta,'display_modifier_classification':row.display_modifier_classification,'program':row.program,'canonical_card_id':row.canonical_card_id,'match_status':'MATCHED' if row.status=='MATCHED' else 'UNMATCHED'}
def _apply(candidate,rows):
 starter=rows[0];candidate.player_name=starter.canonical_player_identity or starter.observed_player_name;candidate.displayed_ovr=starter.displayed_lineup_ovr;candidate.position=starter.observed_position;candidate.program=starter.program;candidate.canonical_card_id=starter.canonical_card_id;candidate.match_status='MATCHED' if starter.status=='MATCHED' else 'UNMATCHED';candidate.confidence=1.0 if starter.status=='MATCHED' else None;candidate.backups=[_backup(r) for r in rows[1:]]
 old=[p for p in candidate.provenance if not p.startswith('c3po:')];candidate.provenance=old+['c3po:google-gemini-screen-transcription','c3po:pancake-cfb27-name-resolution'];candidate.match_diagnostics=dict(candidate.match_diagnostics);candidate.match_diagnostics['c3po']={'observed_player_name':starter.observed_player_name,'lineup_slot':candidate.slot,'displayed_lineup_ovr':starter.displayed_lineup_ovr,'native_card_ovr':starter.native_card_ovr,'native_position':starter.native_position,'display_ovr_delta':starter.display_ovr_delta,'display_modifier_classification':starter.display_modifier_classification,'canonical_player_identity':starter.canonical_player_identity,'program':starter.program,'canonical_card_id':starter.canonical_card_id,'status':starter.status}
def integrate_offense_tackles(state_store,cards,translator):
 state=state_store.load();offense=next((s for s in state.screenshots if s.get('view')=='OFFENSE'),None)
 if offense is None:state.team_observations['c3po_tackles']={'status':'SKIPPED','reason':'offense-screenshot-unavailable'};state_store.save(state);return state
 try:observation=translator.translate_offense_tackles(Path(offense['path']));resolutions=resolve_tackles(observation,cards)
 except Exception as exc:state.team_observations['c3po_tackles']={'status':'ERROR','error_type':type(exc).__name__};state_store.save(state);return state
 for slot in TACKLE_SLOTS:
  rows=[r for r in resolutions if r.slot==slot]
  if rows:_apply(_candidate(state,slot),rows)
 state.team_observations['c3po_tackles']={'status':'APPLIED','provider':observation.provider,'model':observation.model,'source_screenshot':offense.get('id'),'slots':list(TACKLE_SLOTS)};state_store.save(state);return state
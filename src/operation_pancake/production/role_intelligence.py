"""OP-X-051 deterministic role intelligence over frozen CFB27 evaluations."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contextual_value import FrozenBase, POSITION_FAMILY, ROLES
from .discovery import DiscoveryIntelligence
from .gm import GMProduct

# Attribute membership only. No new weights are introduced.
ROLE_ATTRIBUTES: dict[str, dict[str, tuple[str, ...]]] = {
    "QB": {"POCKET": ("THP","SAC","MAC","DAC","TUP"), "MOBILE_OFF_PLATFORM": ("SPD","ACC","COD","THP","RUN"), "OPTION_RPO": ("SPD","ACC","COD","THP")},
    "RB": {"RUNNER": ("SPD","ACC","COD","CAR","BTK"), "RECEIVING": ("SPD","ACC","COD","CTH","SRR"), "POWER_MOVEMENT": ("TRK","BTK","STR","CAR")},
    "WR": {"SEPARATOR": ("SPD","ACC","COD","SRR","MRR"), "VERTICAL": ("SPD","ACC","DRR","RLS","CTH"), "POSSESSION_MISMATCH": ("CTH","CIT","SPC","SRR","MRR")},
    "TE": {"RECEIVING_MISMATCH": ("SPD","ACC","CTH","CIT","SRR","MRR"), "BLOCKING": ("STR","RBK","PBK","IBL"), "HYBRID": ("CTH","CIT","RBK","PBK","STR")},
    "OL": {"RUN": ("STR","RBK","RBP","RBF","IBL"), "PASS": ("STR","PBK","PBP","PBF"), "BALANCED": ("STR","RBK","PBK")},
    "EDGE": {"FINESSE_RUSH": ("FMV","ACC","PUR","BSH"), "POWER_RUSH": ("PMV","STR","PUR","BSH"), "CONTAIN_RUN": ("BSH","PUR","STR","TAK"), "RUSH_SPECIALIST": ("FMV","PMV","ACC","PUR")},
    "DT": {"RUN_STOPPER": ("STR","BSH","PUR","TAK"), "INTERIOR_PRESSURE": ("PMV","FMV","STR","PUR"), "BALANCED": ("STR","BSH","PMV","FMV")},
    "LB": {"COVERAGE_USER": ("SPD","ACC","COD","ZCV","MCV"), "RUSH": ("PMV","FMV","BSH","PUR"), "RUN": ("BSH","PUR","TAK","STR"), "HYBRID": ("SPD","BSH","PUR","ZCV")},
    "CB": {"MAN": ("SPD","ACC","MCV","PRC"), "ZONE": ("SPD","ACC","ZCV","PRC"), "PRESS": ("SPD","ACC","PRS","MCV"), "HYBRID": ("SPD","ACC","MCV","ZCV","PRS")},
    "S": {"DEEP_RANGE": ("SPD","ACC","ZCV","PRC"), "BOX": ("SPD","TAK","POW","BSH"), "MAN_HYBRID": ("SPD","ACC","MCV","ZCV"), "USER": ("SPD","ACC","COD","TAK")},
}

def family(position: str) -> str:
    return POSITION_FAMILY.get(position, position)

def role_profile(position: str, role: str) -> dict[str, Any]:
    fam = family(position)
    attrs = ROLE_ATTRIBUTES.get(fam, {}).get(role)
    if attrs is None:
        return {"position_family": fam, "role": role, "status": "UNSUPPORTED"}
    return {"position_family": fam, "role": role, "status": "CANDIDATE_SUPPORTED", "modeled_attributes": list(attrs), "relative_importance": "UNKNOWN", "unmodeled_contextual_variables": ["behavior/animation", "physical geometry", "ability/AP relevance", "scheme/assignment interaction"], "functional_floors": "USE_EVIDENCE_REGISTRY; UNKNOWN WHEN ABSENT"}

def card_role_candidates(card: dict[str, Any]) -> list[dict[str, Any]]:
    fam = family(card.get("position") or card.get("native_position") or "")
    attributes = card.get("attributes") or card.get("stats") or {}
    out=[]
    for role in ROLES.get(fam, ()):
        required=ROLE_ATTRIBUTES.get(fam, {}).get(role, ())
        known=[a for a in required if attributes.get(a) is not None]
        coverage=len(known)/len(required) if required else 0.0
        out.append({"role":role,"position_family":fam,"attribute_coverage":round(coverage,3),"known_attributes":known,"missing_attributes":[a for a in required if a not in known],"classification":"ROLE CANDIDATE" if coverage else "UNKNOWN","verified_role_fit":False})
    return out

def role_board(root: Path, position: str, role: str, limit: int=25) -> dict[str, Any]:
    profile=role_profile(position, role)
    if profile["status"] == "UNSUPPORTED": return {"status":"ROLE BOARD BLOCKED — INSUFFICIENT EVIDENCE","profile":profile,"rows":[]}
    product=GMProduct(root); discovery=DiscoveryIntelligence(root)
    rows=[]
    for card in product.population:
        if family(card.get("position") or "") != family(position): continue
        candidates={x["role"]:x for x in card_role_candidates(card)}
        c=candidates.get(role)
        if not c or c["attribute_coverage"] < 1: continue
        lookup=product.lookup(card_id=card["card_id"]); ev=lookup.get("evaluation",{}); metric=discovery.by_id.get(card["card_id"],{})
        if ev.get("score") is None: continue
        rows.append({"card_id":card["card_id"],"player":card.get("player_name"),"ovr":card.get("native_overall"),"base_pancake_score":ev.get("score"),"position_rank":ev.get("position_rank"),"position_percentile":metric.get("position_percentile"),"role":role,"role_fit":"UNKNOWN","football_role_ranking_basis":"frozen score among complete role-attribute candidates","market_used":False})
    rows.sort(key=lambda r:(-(r["base_pancake_score"] or -1),-(r["ovr"] or -1),r["card_id"]))
    return {"status":"SUPPORTED" if rows else "ROLE BOARD BLOCKED — INSUFFICIENT EVIDENCE","profile":profile,"rows":rows[:limit],"warning":"Candidate board, not verified gameplay fit."}

def role_alternatives(root: Path, card_id: str, role: str, limit:int=10) -> dict[str,Any]:
    product=GMProduct(root); target=product.lookup(card_id=card_id)
    if "card" not in target: return target
    pos=target["card"]["position"]; profile=role_profile(pos,role)
    if profile["status"]=="UNSUPPORTED": return {"status":"UNKNOWN","reason":"unsupported role"}
    required=profile["modeled_attributes"]; ta=target["card"].get("attributes") or target["card"].get("stats") or {}
    if any(ta.get(a) is None for a in required): return {"status":"UNKNOWN","reason":"target lacks binding modeled traits"}
    rows=[]
    for card in product.population:
        if card["card_id"]==card_id or family(card.get("position") or "")!=family(pos): continue
        ca=card.get("attributes") or card.get("stats") or {}
        if any(ca.get(a) is None for a in required): continue
        delta=sum(abs(float(ca[a])-float(ta[a])) for a in required)
        rows.append({"card_id":card["card_id"],"player":card.get("player_name"),"ovr":card.get("native_overall"),"role":role,"trait_distance":round(delta,3),"binding_requirements_present":True,"classification":"NEAR ROLE EQUIVALENT" if delta<=5 else "SPECIALIST SUBSTITUTE" if delta<=12 else "MEANINGFUL COMPROMISE","market_used":False})
    rows.sort(key=lambda r:(r["trait_distance"],r["ovr"] or 999,r["card_id"]))
    return {"status":"CANDIDATES","target":card_id,"role":role,"alternatives":rows[:limit],"price_conclusion":"UNKNOWN"}

def scientific_firewall() -> dict[str,bool]:
    return {"production_coefficients_modified":False,"op_x_028_modified":False,"buy_gates_modified":False,"market_semantics_modified":False,"context_numeric_score_created":False}

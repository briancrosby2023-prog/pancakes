"""Conservative EVO composition over authoritative production GM services."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

@dataclass(frozen=True)
class EVODefinition:
    id: str
    name: str
    target_ovr: int | None = None
    positions: tuple[str, ...] = ()
    archetypes: tuple[str, ...] = ()
    starting_ovr_min: int | None = None
    starting_ovr_max: int | None = None
    verified_requirements: Mapping[str, Any] = field(default_factory=dict)
    known_attribute_boosts: Mapping[str, int] = field(default_factory=dict)
    resource_cost: int | None = None
    notes: str = ""
    source: str = "USER-SUPPLIED"

    @property
    def final_attributes_known(self) -> bool:
        return bool(self.known_attribute_boosts)

    def eligible(self, player: Mapping[str, Any]) -> tuple[bool, list[str]]:
        basis: list[str] = []
        pos = str(player.get("position") or "").upper()
        arch = str(player.get("archetype") or "").casefold()
        raw_ovr = player.get("native_overall", player.get("overall", player.get("ovr")))
        try: ovr = int(raw_ovr)
        except (TypeError, ValueError): ovr = None
        if self.positions:
            if pos not in {x.upper() for x in self.positions}: return False, ["position does not satisfy verified eligibility"]
            basis.append(f"position={pos}")
        if self.archetypes:
            if arch not in {x.casefold() for x in self.archetypes}: return False, ["archetype does not satisfy verified eligibility"]
            basis.append(f"archetype={player.get('archetype')}")
        if self.starting_ovr_min is not None:
            if ovr is None or ovr < self.starting_ovr_min: return False, ["OVR below verified minimum or unknown"]
            basis.append(f"OVR>={self.starting_ovr_min}")
        if self.starting_ovr_max is not None:
            if ovr is None or ovr > self.starting_ovr_max: return False, ["OVR above verified maximum or unknown"]
            basis.append(f"OVR<={self.starting_ovr_max}")
        for key, expected in self.verified_requirements.items():
            if player.get(key) != expected: return False, [f"{key} does not satisfy verified requirement"]
            basis.append(f"{key}={expected}")
        return True, basis or ["no restrictive verified eligibility rules"]

    def project(self, player: Mapping[str, Any]) -> dict[str, Any]:
        if not self.known_attribute_boosts:
            return {"target_ovr": self.target_ovr, "final_attributes": None, "attribute_deltas": {}, "final_pancake_score": None, "final_position_rank": None, "limitations": ["FINAL ATTRIBUTES UNKNOWN", "PROJECTED PANCAKE SCORE UNKNOWN", "PROJECTED POSITION RANK UNKNOWN"]}
        result = dict(player); ratings = dict(player.get("native_ratings") or {}); deltas = {}; missing = []
        if self.target_ovr is not None: result["native_overall"] = self.target_ovr
        for attr, boost in self.known_attribute_boosts.items():
            key = next((k for k in ratings if k.casefold() == str(attr).casefold()), None)
            if key is None or not isinstance(ratings.get(key), (int, float)):
                missing.append(str(attr)); continue
            current = int(ratings[key]); final = min(99, current + int(boost)); ratings[key] = final
            deltas[key] = {"current": current, "boost": int(boost), "projected": final}
        result["native_ratings"] = ratings
        limitations = ["Only explicitly verified boosts are applied; unverified EVO outcomes remain unknown"]
        if missing: limitations.append("Verified boost attributes absent from canonical native ratings: " + ", ".join(sorted(missing)))
        return {"target_ovr": self.target_ovr, "final_attributes": result, "attribute_deltas": deltas, "final_pancake_score": None, "final_position_rank": None, "limitations": limitations}

class EVOStore:
    VERSION = 1
    def __init__(self, path: str | Path): self.path = Path(path)
    def load(self) -> list[EVODefinition]:
        if not self.path.exists(): return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != self.VERSION: raise ValueError("unsupported evo persistence version")
        return [EVODefinition(**{**row, "positions": tuple(row.get("positions", ())), "archetypes": tuple(row.get("archetypes", ()))}) for row in payload.get("evos", [])]
    def save(self, evos: Iterable[EVODefinition]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"version": self.VERSION, "evos": [asdict(e) for e in evos]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def filter_candidates(evo, players, owned_ids=None, ownership="all"):
    if ownership not in {"all", "owned", "acquisition"}: raise ValueError("ownership must be all, owned, or acquisition")
    owned_ids = owned_ids or set(); output = []
    for player in players:
        player_id = str(player.get("card_id") or player.get("id") or player.get("player_id") or player.get("canonical_id") or ""); owned = player_id in owned_ids
        if ownership == "owned" and not owned: continue
        if ownership == "acquisition" and owned: continue
        eligible, basis = evo.eligible(player)
        if not eligible: continue
        current_ovr = player.get("native_overall", player.get("overall", player.get("ovr")))
        headroom = evo.target_ovr - int(current_ovr) if evo.target_ovr is not None and current_ovr is not None else None
        output.append({**dict(player), "owned": owned, "ownership": "OWNED" if owned else "ACQUISITION", "target_ovr": evo.target_ovr, "ovr_headroom": headroom, "eligibility_basis": basis, "confidence": "VERIFIED-RULE MATCH", "limitations": [] if evo.final_attributes_known else ["FINAL ATTRIBUTES UNKNOWN", "headroom is descriptive only"]})
    return output

def _production(gm, card: Mapping[str, Any]) -> dict[str, Any]:
    score = gm.engine.score(dict(card)); ranked = gm.rank_by_id.get(str(card.get("card_id"))) or {}
    return {"score": score.get("score"), "position_rank": ranked.get("position_rank"), "confidence": score.get("score_confidence"), "limitations": list(score.get("model_limitations") or []) + ([] if score.get("score") is not None else [score.get("score_status")]), "role": {"position_family": score.get("position_family"), "archetype": score.get("archetype"), "routing": score.get("routing")}}

def enrich_candidates(evo, gm, owned_ids=None, ownership="all"):
    rows = filter_candidates(evo, gm.population, owned_ids, ownership)
    for row in rows: row["production"] = _production(gm, row)
    return rows

def projected_production(evo, gm, card: Mapping[str, Any]) -> dict[str, Any]:
    projection = evo.project(card)
    projected = projection.get("final_attributes")
    if projected is None:
        return {**projection, "production": {"score": None, "position_rank": None, "confidence": "UNKNOWN", "limitations": projection["limitations"], "role": None}}
    score = gm.engine.score(projected)
    if not projection.get("attribute_deltas"):
        return {**projection, "production": {"score": None, "position_rank": None, "confidence": "UNKNOWN", "limitations": projection["limitations"] + ["No verified boost could be applied to canonical native ratings"], "role": None}}
    # Rank an in-memory projected state against the immutable canonical population.
    scored = [r for r in gm.ranked if r.get("card_id") != card.get("card_id")] + [score]
    ranked = gm.engine.rank(scored); projected_rank = next((r.get("position_rank") for r in ranked if r.get("card_id") == card.get("card_id")), None)
    limitations = list(projection["limitations"]) + list(score.get("model_limitations") or [])
    if score.get("score") is None: limitations.append(score.get("score_status"))
    return {**projection, "final_pancake_score": score.get("score"), "final_position_rank": projected_rank, "production": {"score": score.get("score"), "position_rank": projected_rank, "confidence": "LIMITED" if score.get("score") is not None else score.get("score_confidence"), "limitations": limitations, "role": {"position_family": score.get("position_family"), "archetype": score.get("archetype"), "routing": score.get("routing")}}}

def decide_evo(*, slot_protected, slot_rerollable, projected_improvement, replacement_improvement, replacement_cost, evo_base_cost, final_attributes_known):
    reasons = []
    if slot_protected: return {"decision": "KEEP CURRENT PLAYER", "reasons": ["roster slot is protected"], "confidence": "HIGH"}
    if slot_rerollable: reasons.append("slot is rerollable; preserve acquisition-path semantics")
    if not final_attributes_known:
        reasons.append("final EVO attributes are unknown")
        if replacement_improvement and replacement_cost is not None: return {"decision": "BUY REPLACEMENT", "reasons": reasons + ["known replacement improves the slot at a known cost"], "confidence": "MEDIUM"}
        return {"decision": "SAVE EVO", "reasons": reasons + ["opportunity cost cannot be justified from verified outcome data"], "confidence": "LIMITED"}
    if projected_improvement is False: return {"decision": "SAVE EVO", "reasons": ["verified projection does not improve the roster slot"], "confidence": "MEDIUM"}
    if projected_improvement is True:
        if replacement_improvement and replacement_cost is not None and evo_base_cost is not None and replacement_cost < evo_base_cost: return {"decision": "BUY REPLACEMENT", "reasons": ["known improving replacement costs less than the EVO base acquisition path"], "confidence": "MEDIUM"}
        return {"decision": "USE EVO", "reasons": ["verified projected state improves the roster slot"], "confidence": "MEDIUM"}
    return {"decision": "REVIEW", "reasons": ["production-supported slot improvement is unresolved"], "confidence": "LIMITED"}

def compose_evo_decision(*, evo, candidate_id, assignment, gm, gm_decisions, prices, budget_state, owned_ids):
    card = gm.cards.get(candidate_id)
    if card is None: raise KeyError("candidate card not found")
    eligible, basis = evo.eligible(card)
    if not eligible: raise ValueError("candidate is not eligible for this EVO")
    current_card = gm.cards.get(assignment.card_id)
    if current_card is None: raise KeyError("roster card not found")
    current = gm.lookup(card_id=assignment.card_id); candidate = gm.lookup(card_id=candidate_id)
    projected = projected_production(evo, gm, card)
    current_score = (current.get("evaluation") or {}).get("score"); projected_score = (projected.get("production") or {}).get("score")
    projected_improvement = None if current_score is None or projected_score is None else projected_score > current_score
    replacement_detail = gm_decisions.detail(assignment, prices, budget_state.spendable_budget)
    replacements = replacement_detail.get("candidates") or []
    best = max(replacements, key=lambda r: r.get("score_improvement") or float("-inf"), default=None)
    replacement_improvement = bool(best and (best.get("score_improvement") or 0) > 0)
    replacement_cost = None if best is None else best.get("price")
    base_price = prices.get(candidate_id)
    decision = decide_evo(slot_protected=assignment.protected, slot_rerollable=assignment.rerollable, projected_improvement=projected_improvement, replacement_improvement=replacement_improvement, replacement_cost=replacement_cost, evo_base_cost=base_price, final_attributes_known=evo.final_attributes_known)
    base_coin_cost = 0 if candidate_id in owned_ids else base_price
    remaining = None if base_coin_cost is None else budget_state.spendable_budget - base_coin_cost
    return {"evo": asdict(evo), "slot": asdict(assignment), "eligibility_basis": basis, "current": {**current, "price": prices.get(assignment.card_id), "price_status": "PRICE KNOWN" if prices.get(assignment.card_id) is not None else "PRICE UNKNOWN"}, "evo_path": {"base": candidate, "ownership": "OWNED" if candidate_id in owned_ids else "ACQUISITION", "base_price": base_price, "base_price_status": "PRICE KNOWN" if base_price is not None else "PRICE UNKNOWN", "resource_cost": evo.resource_cost, "resource_cost_unit": "EVO RESOURCE (NOT COINS)", "verified_boosts": dict(evo.known_attribute_boosts), "target_ovr": evo.target_ovr, "projection": projected, "projected_improvement": projected_improvement}, "replacement_path": best or {"status": "NO COMPATIBLE UPGRADE FOUND", "price": None, "price_status": "PRICE UNKNOWN"}, "economics": {"current_coins": budget_state.current_coins, "reserve": budget_state.reserve_coins, "spendable": budget_state.spendable_budget, "evo_base_price": base_price, "evo_resource_cost": evo.resource_cost, "replacement_price": replacement_cost, "remaining_after_evo_base": remaining, "market_price_state": "KNOWN" if base_price is not None else "UNKNOWN", "intrinsic_gain": None if best is None else best.get("intrinsic_value")}, "decision": decision}

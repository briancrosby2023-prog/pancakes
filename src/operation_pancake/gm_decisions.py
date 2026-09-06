"""Application composition for roster decisions; production engines remain authoritative."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from operation_pancake.production.gm import GMProduct, optimize_budget
from operation_pancake.production.roster import RosterGMEngine
from operation_pancake.roster_state import RosterAssignment


class GMDecisionService:
    def __init__(self, gm: GMProduct):
        self.gm = gm
        self.roster_engine = RosterGMEngine(gm.engine, gm.ranked, gm.population)

    def _entry(self, assignment: RosterAssignment) -> dict[str, Any]:
        card = self.gm.cards.get(assignment.card_id)
        ranked = self.gm.rank_by_id.get(assignment.card_id)
        family = ranked.get("position_family") if ranked else None
        return {
            "roster_instance_id": assignment.slot,
            "card_id": assignment.card_id,
            "player_name": (card or {}).get("player_name") or assignment.card_id,
            "position": (card or {}).get("position") or assignment.position,
            "position_family": family or assignment.position,
            "depth_slot": assignment.slot,
            "depth_order": 1,
            "starter_status": "STARTER" if assignment.starter else "BACKUP",
            "native_overall": (card or {}).get("native_overall"),
            "archetype": (card or {}).get("archetype"),
            "program": (card or {}).get("program"),
            "pancake": ranked,
            "protected": assignment.protected,
            "rerollable": assignment.rerollable,
        }

    def decision(self, assignment: RosterAssignment) -> dict[str, Any]:
        entry = self._entry(assignment); score = entry.get("pancake") or {}
        limitations = list(score.get("model_limitations") or [])
        if score.get("score") is None:
            label, reason = "REVIEW", score.get("score_status") or "production model cannot score this card"
            replacement = None
        else:
            replacement = self.roster_engine.replacements(entry)
            if assignment.rerollable:
                label = "REROLL"
                reason = "Rerollable acquisition path is explicitly assigned; this is not a quality judgment."
            elif assignment.protected:
                label = "KEEP"
                reason = "Protected roster state blocks an automatic replacement instruction."
            elif not replacement or replacement.get("status") == "NO_UPGRADE_FOUND":
                label = "KEEP"
                reason = "Production replacement search found no higher-scored compatible position-family card."
            else:
                label = "REPLACE"
                reason = "Production replacement search found a higher-scored card in the same position family."
        confidence = score.get("score_confidence") or "UNAVAILABLE"
        return {"assignment": asdict(assignment), "current": entry, "decision": label, "confidence": confidence, "key_reason": reason, "limitations": limitations, "replacement": replacement}

    def detail(self, assignment: RosterAssignment, prices: dict[str, int] | None = None, budget: int | None = None) -> dict[str, Any]:
        result = self.decision(assignment); current_id = assignment.card_id; prices = prices or {}
        candidates=[]; seen=set()
        replacement=result.get("replacement") or {}
        for kind, candidate in (replacement.get("candidates") or {}).items():
            if not candidate or candidate["card_id"] in seen: continue
            seen.add(candidate["card_id"]); cid=candidate["card_id"]
            intrinsic=self.gm.value(current_id,cid)
            price=prices.get(cid)
            budget_eval=self.roster_engine.budget_decision(candidate["score_improvement"],candidate["position_rank_improvement"],price,None,budget)
            candidates.append({"kind":kind,**candidate,"ovr_delta":(candidate.get("native_overall") or 0)-(result["current"].get("native_overall") or 0),"intrinsic_value":intrinsic,"price":price,"price_status":"PRICE UNKNOWN" if price is None else "PRICE KNOWN","budget":budget_eval})
        result["candidates"]=candidates
        return result

    def opportunities(self, assignments: list[RosterAssignment], prices: dict[str, int] | None, budget: int) -> dict[str, Any]:
        priced=[]; intrinsic=[]
        for assignment in assignments:
            detail=self.detail(assignment,prices,budget)
            for candidate in detail["candidates"]:
                row={"slot":assignment.slot,"current_card_id":assignment.card_id,"current_player":detail["current"]["player_name"],"candidate_card_id":candidate["card_id"],"candidate_player":candidate["player_name"],"score_improvement":candidate["score_improvement"],"rank_improvement":candidate["position_rank_improvement"],"candidate_price":candidate["price"],"net_cost":candidate["price"],"protected":assignment.protected,"rerollable":assignment.rerollable,"confidence":candidate.get("score_confidence"),"limitations":detail["limitations"]}
                intrinsic.append(row)
                if candidate["price"] is not None and not assignment.rerollable: priced.append(row)
        return {"intrinsic":intrinsic,"priced":priced,"portfolio":optimize_budget(priced,budget)}

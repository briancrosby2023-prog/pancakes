"""Conservative EVO decision workflow.

EVO rules are user-supplied unless backed by repository evidence.  Unknown
boosts stay unknown: target OVR/headroom are descriptive and never substitute
for attribute deltas.
"""
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
        try:
            ovr = int(player.get("overall") if player.get("overall") is not None else player.get("ovr"))
        except (TypeError, ValueError):
            ovr = None
        if self.positions:
            allowed = {x.upper() for x in self.positions}
            if pos not in allowed:
                return False, ["position does not satisfy verified eligibility"]
            basis.append(f"position={pos}")
        if self.archetypes:
            allowed = {x.casefold() for x in self.archetypes}
            if arch not in allowed:
                return False, ["archetype does not satisfy verified eligibility"]
            basis.append(f"archetype={player.get('archetype')}")
        if self.starting_ovr_min is not None:
            if ovr is None or ovr < self.starting_ovr_min:
                return False, ["OVR below verified minimum or unknown"]
            basis.append(f"OVR>={self.starting_ovr_min}")
        if self.starting_ovr_max is not None:
            if ovr is None or ovr > self.starting_ovr_max:
                return False, ["OVR above verified maximum or unknown"]
            basis.append(f"OVR<={self.starting_ovr_max}")
        for key, expected in self.verified_requirements.items():
            if player.get(key) != expected:
                return False, [f"{key} does not satisfy verified requirement"]
            basis.append(f"{key}={expected}")
        return True, basis or ["no restrictive verified eligibility rules"]

    def project(self, player: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(player)
        if self.target_ovr is not None:
            result["overall"] = self.target_ovr
        if not self.known_attribute_boosts:
            return {
                "target_ovr": self.target_ovr,
                "final_attributes": None,
                "final_pancake_score": None,
                "limitations": ["FINAL ATTRIBUTES UNKNOWN", "FINAL PANCAKE SCORE UNKNOWN"],
            }
        deltas: dict[str, dict[str, int]] = {}
        for attr, boost in self.known_attribute_boosts.items():
            current = player.get(attr)
            if isinstance(current, (int, float)):
                final = min(99, int(current) + int(boost))
                result[attr] = final
                deltas[attr] = {"current": int(current), "boost": int(boost), "projected": final}
        return {"target_ovr": self.target_ovr, "final_attributes": result, "attribute_deltas": deltas, "final_pancake_score": None, "limitations": ["Projected score requires production engine evaluation"]}


class EVOStore:
    VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> list[EVODefinition]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != self.VERSION:
            raise ValueError("unsupported evo persistence version")
        return [EVODefinition(**{**row, "positions": tuple(row.get("positions", ())), "archetypes": tuple(row.get("archetypes", ()))}) for row in payload.get("evos", [])]

    def save(self, evos: Iterable[EVODefinition]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self.VERSION, "evos": [asdict(evo) for evo in evos]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def filter_candidates(evo: EVODefinition, players: Iterable[Mapping[str, Any]], owned_ids: set[str] | None = None, ownership: str = "all") -> list[dict[str, Any]]:
    owned_ids = owned_ids or set()
    output: list[dict[str, Any]] = []
    for player in players:
        player_id = str(player.get("id") or player.get("player_id") or player.get("canonical_id") or "")
        owned = player_id in owned_ids
        if ownership == "owned" and not owned:
            continue
        if ownership == "acquisition" and owned:
            continue
        eligible, basis = evo.eligible(player)
        if not eligible:
            continue
        current_ovr = player.get("overall") if player.get("overall") is not None else player.get("ovr")
        headroom = evo.target_ovr - int(current_ovr) if evo.target_ovr is not None and current_ovr is not None else None
        output.append({**dict(player), "owned": owned, "target_ovr": evo.target_ovr, "ovr_headroom": headroom, "eligibility_basis": basis, "confidence": "VERIFIED-RULE MATCH", "limitations": [] if evo.final_attributes_known else ["FINAL ATTRIBUTES UNKNOWN", "headroom is descriptive only"]})
    return output


def decide_evo(*, slot_protected: bool, slot_rerollable: bool, projected_improvement: bool | None, replacement_improvement: bool | None, replacement_cost: int | None, evo_base_cost: int | None, final_attributes_known: bool) -> dict[str, Any]:
    reasons: list[str] = []
    if slot_protected:
        return {"decision": "KEEP CURRENT PLAYER", "reasons": ["roster slot is protected"], "confidence": "HIGH"}
    if slot_rerollable:
        reasons.append("slot is rerollable; preserve acquisition-path semantics")
    if not final_attributes_known:
        reasons.append("final EVO attributes are unknown")
        if replacement_improvement and replacement_cost is not None:
            return {"decision": "BUY REPLACEMENT", "reasons": reasons + ["known replacement improves the slot at a known cost"], "confidence": "MEDIUM"}
        return {"decision": "SAVE EVO", "reasons": reasons + ["opportunity cost cannot be justified from verified outcome data"], "confidence": "LIMITED"}
    if projected_improvement is False:
        return {"decision": "SAVE EVO", "reasons": ["projected EVO state does not improve the roster slot"], "confidence": "HIGH"}
    if projected_improvement is True:
        if replacement_improvement and replacement_cost is not None and evo_base_cost is not None and replacement_cost < evo_base_cost:
            return {"decision": "BUY REPLACEMENT", "reasons": ["known improving replacement costs less than the EVO base path"], "confidence": "MEDIUM"}
        return {"decision": "USE EVO", "reasons": ["verified projected state improves the roster slot"], "confidence": "MEDIUM"}
    return {"decision": "REVIEW", "reasons": ["production-supported slot improvement is unresolved"], "confidence": "LIMITED"}

"""Durable user roster state for the local GM application."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RosterAssignment:
    card_id: str
    position: str
    slot: str
    starter: bool = True
    owned: bool = True
    protected: bool = False
    rerollable: bool = False
    notes: str = ""
    current_level: int | None = None

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "RosterAssignment":
        level = row.get("current_level")
        return cls(
            card_id=str(row["card_id"]), position=str(row["position"]).upper(),
            slot=str(row["slot"]).upper(), starter=bool(row.get("starter", True)),
            owned=bool(row.get("owned", True)), protected=bool(row.get("protected", False)),
            rerollable=bool(row.get("rerollable", False)), notes=str(row.get("notes", "")),
            current_level=None if level in (None, "") else max(0, int(level)),
        )


class RosterStore:
    """JSON-backed roster references; canonical card data remains in GMProduct."""
    def __init__(self, path: Path, valid_card_ids: set[str] | None = None):
        self.path = path
        self.valid_card_ids = valid_card_ids

    def load(self) -> list[RosterAssignment]:
        if not self.path.exists(): return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("assignments", []) if isinstance(payload, dict) else payload
        return [RosterAssignment.from_dict(row) for row in rows]

    def save(self, rows: list[RosterAssignment]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "assignments": [asdict(row) for row in rows]}
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8"); temp.replace(self.path)

    def _validate(self, row: RosterAssignment, rows: list[RosterAssignment], old_slot: str | None = None) -> None:
        if not row.card_id or not row.position or not row.slot: raise ValueError("card_id, position and slot are required")
        if self.valid_card_ids is not None and row.card_id not in self.valid_card_ids: raise ValueError("unknown canonical card_id")
        if row.current_level is not None and row.current_level < 0: raise ValueError("current_level cannot be negative")
        for existing in rows:
            if old_slot is not None and existing.slot == old_slot: continue
            if existing.slot == row.slot: raise ValueError(f"slot {row.slot} is already assigned")
            if existing.card_id == row.card_id: raise ValueError("card is already assigned to the roster")

    def add(self, row: RosterAssignment) -> RosterAssignment:
        rows=self.load(); self._validate(row,rows); rows.append(row); self.save(rows); return row

    def update(self, old_slot: str, **changes: Any) -> RosterAssignment:
        rows=self.load(); index=next((i for i,row in enumerate(rows) if row.slot==old_slot.upper()),None)
        if index is None: raise KeyError(old_slot)
        updated=RosterAssignment.from_dict(asdict(replace(rows[index],**changes)))
        self._validate(updated,rows,old_slot=old_slot.upper()); rows[index]=updated; self.save(rows); return updated

    def remove(self, slot: str) -> RosterAssignment:
        rows=self.load(); index=next((i for i,row in enumerate(rows) if row.slot==slot.upper()),None)
        if index is None: raise KeyError(slot)
        removed=rows.pop(index); self.save(rows); return removed

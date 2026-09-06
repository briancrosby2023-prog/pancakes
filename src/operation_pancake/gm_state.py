"""Durable local GM budget and user-supplied current-price state."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GMState:
    current_coins: int = 0
    reserve_coins: int = 0
    prices: dict[str, int] | None = None

    @property
    def spendable_budget(self) -> int:
        return max(0, self.current_coins - self.reserve_coins)

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_coins": self.current_coins,
            "reserve_coins": self.reserve_coins,
            "spendable_budget": self.spendable_budget,
            "prices": dict(self.prices or {}),
        }


class GMStateStore:
    def __init__(self, path: Path, valid_card_ids: set[str] | None = None):
        self.path = path
        self.valid_card_ids = valid_card_ids

    def load(self) -> GMState:
        if not self.path.exists():
            return GMState(prices={})
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return GMState(
            current_coins=max(0, int(payload.get("current_coins", 0))),
            reserve_coins=max(0, int(payload.get("reserve_coins", 0))),
            prices={str(k): max(0, int(v)) for k, v in payload.get("prices", {}).items()},
        )

    def save(self, state: GMState) -> GMState:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, **state.as_dict()}
        payload.pop("spendable_budget", None)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)
        return state

    def update_budget(self, current_coins: int, reserve_coins: int) -> GMState:
        prior = self.load()
        return self.save(GMState(max(0, int(current_coins)), max(0, int(reserve_coins)), prior.prices or {}))

    def set_price(self, card_id: str, price: int | None) -> GMState:
        if self.valid_card_ids is not None and card_id not in self.valid_card_ids:
            raise ValueError("unknown canonical card_id")
        prior = self.load(); prices = dict(prior.prices or {})
        if price is None:
            prices.pop(card_id, None)
        else:
            prices[card_id] = max(0, int(price))
        return self.save(GMState(prior.current_coins, prior.reserve_coins, prices))

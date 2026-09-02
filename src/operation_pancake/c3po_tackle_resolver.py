"""Resolve C-3PO tackle observations while preserving observed/native fields."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from operation_pancake.c3po_vision import PlayerObservation, TackleScreenObservation
from operation_pancake.team_import import normalize_name


@dataclass(frozen=True)
class TackleResolution:
    slot: str
    depth: int
    observed_player_name: str | None
    observed_position: str
    displayed_lineup_ovr: int | None
    canonical_player_identity: str | None
    canonical_card_id: str | None
    native_card_ovr: int | None
    program: str | None
    status: str


def _is_cfb27(card: dict) -> bool:
    markers = [card.get(k) for k in ("game", "season", "title", "dataset") if card.get(k)]
    if not markers:
        return True
    text = " ".join(str(x).upper() for x in markers)
    if "CFB25" in text or "CFB 25" in text or "CFB26" in text or "CFB 26" in text:
        return False
    return "27" in text


def _identity_score(observed: str, canonical: str) -> float:
    a, b = normalize_name(observed), normalize_name(canonical)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _identity_gate(observed: str, canonical: str) -> bool:
    """Require every visible name token to remain recognizably the same token.

    Position/OVR may rank card variants, but cannot rescue a materially different
    first or last name. Normalization still accepts punctuation/case noise, and
    long-token OCR imperfections remain eligible when token similarity is high.
    """
    observed_tokens = [normalize_name(token) for token in observed.split() if normalize_name(token)]
    canonical_tokens = [normalize_name(token) for token in canonical.split() if normalize_name(token)]
    if len(observed_tokens) != len(canonical_tokens) or not observed_tokens:
        return False
    for seen, expected in zip(observed_tokens, canonical_tokens):
        if seen == expected:
            continue
        if min(len(seen), len(expected)) < 6:
            return False
        if SequenceMatcher(None, seen, expected).ratio() < 0.86:
            return False
    return True


def _unresolved(base: dict) -> TackleResolution:
    return TackleResolution(**base, canonical_player_identity=None, canonical_card_id=None, native_card_ovr=None, program=None, status="UNRESOLVED")


def resolve_player(observation: PlayerObservation, position: str, cards: list[dict], slot: str, depth: int) -> TackleResolution:
    base = dict(slot=slot, depth=depth, observed_player_name=observation.observed_name, observed_position=position, displayed_lineup_ovr=observation.displayed_ovr)
    if not observation.observed_name:
        return _unresolved(base)

    pool = [c for c in cards if _is_cfb27(c) and (c.get("position") or "").upper() == position]
    identities: dict[str, list[dict]] = {}
    for card in pool:
        name = card.get("player_name") or ""
        identities.setdefault(name, []).append(card)
    ranked = sorted(((_identity_score(observation.observed_name, name), name, variants) for name, variants in identities.items()), reverse=True)
    if not ranked or ranked[0][0] < 0.78 or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08):
        return _unresolved(base)

    _, identity, variants = ranked[0]
    if not _identity_gate(observation.observed_name, identity):
        return _unresolved(base)

    def variant_key(card: dict):
        native = card.get("native_overall")
        delta = 99 if observation.displayed_ovr is None or native is None else abs(int(native) - int(observation.displayed_ovr))
        return (delta, -(int(native) if native is not None else 0), str(card.get("card_id") or ""))

    card = min(variants, key=variant_key)
    return TackleResolution(**base, canonical_player_identity=identity, canonical_card_id=card.get("card_id"), native_card_ovr=card.get("native_overall"), program=card.get("program"), status="MATCHED")


def resolve_tackles(observation: TackleScreenObservation, cards: list[dict]) -> list[TackleResolution]:
    if observation.view != "OFFENSE":
        raise ValueError("C-3PO pilot accepts OFFENSE only")
    out = []
    for slot, position in (("LT1", "LT"), ("RT1", "RT")):
        translated = observation.slots[slot]
        out.append(resolve_player(translated.starter, position, cards, slot, 0))
        out.extend(resolve_player(row, position, cards, slot, depth) for depth, row in enumerate(translated.backups, 1))
    return out


class TackleResolutionStore:
    """Small durable boundary proving translated observations survive restart."""

    def __init__(self, path: Path):
        self.path = path

    def save(self, observation: TackleScreenObservation, resolutions: list[TackleResolution]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"translator_observation": observation.to_dict(), "resolutions": [asdict(row) for row in resolutions]}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

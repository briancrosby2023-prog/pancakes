"""Resolve C-3PO tackle transcriptions against Pancake's CFB27 corpus."""
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
    display_ovr_delta: int | None
    display_modifier_classification: str | None
    status: str


def _is_cfb27(card: dict) -> bool:
    markers = [
        card.get(key)
        for key in ("game", "season", "title", "dataset")
        if card.get(key)
    ]
    if not markers:
        return True
    text = " ".join(str(value).upper() for value in markers)
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
    """Require every visible name token to remain recognizably the same token."""
    observed_tokens = [
        normalize_name(token) for token in observed.split() if normalize_name(token)
    ]
    canonical_tokens = [
        normalize_name(token) for token in canonical.split() if normalize_name(token)
    ]
    if len(observed_tokens) != len(canonical_tokens) or not observed_tokens:
        return False
    for seen, expected in zip(observed_tokens, canonical_tokens, strict=True):
        if seen == expected:
            continue
        if min(len(seen), len(expected)) < 6:
            return False
        if SequenceMatcher(None, seen, expected).ratio() < 0.86:
            return False
    return True


def _unresolved(base: dict) -> TackleResolution:
    return TackleResolution(
        **base,
        canonical_player_identity=None,
        canonical_card_id=None,
        native_card_ovr=None,
        program=None,
        display_ovr_delta=None,
        display_modifier_classification=None,
        status="UNRESOLVED",
    )


def _canonical_variant(variants: list[dict]) -> dict:
    """Choose Pancake's strongest CFB27 card without consulting display OVR."""
    return min(
        variants,
        key=lambda card: (
            -(
                int(card["native_overall"])
                if card.get("native_overall") is not None
                else -1
            ),
            str(card.get("card_id") or ""),
        ),
    )


def resolve_player(
    observation: PlayerObservation,
    position: str,
    cards: list[dict],
    slot: str,
    depth: int,
) -> TackleResolution:
    base = dict(
        slot=slot,
        depth=depth,
        observed_player_name=observation.observed_name,
        observed_position=position,
        displayed_lineup_ovr=observation.displayed_ovr,
    )
    if not observation.observed_name:
        return _unresolved(base)

    pool = [
        card
        for card in cards
        if _is_cfb27(card) and (card.get("position") or "").upper() == position
    ]
    identities: dict[str, list[dict]] = {}
    for card in pool:
        name = card.get("player_name") or ""
        identities.setdefault(name, []).append(card)

    observed_normalized = normalize_name(observation.observed_name)
    exact = next(
        (
            (name, variants)
            for name, variants in identities.items()
            if normalize_name(name) == observed_normalized
        ),
        None,
    )
    if exact is not None:
        identity, variants = exact
    else:
        ranked = sorted(
            (
                (_identity_score(observation.observed_name, name), name, variants)
                for name, variants in identities.items()
            ),
            reverse=True,
        )
        ambiguous = len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08
        if not ranked or ranked[0][0] < 0.78 or ambiguous:
            return _unresolved(base)
        _, identity, variants = ranked[0]
        if not _identity_gate(observation.observed_name, identity):
            return _unresolved(base)

    card = _canonical_variant(variants)
    native = card.get("native_overall")
    displayed = observation.displayed_ovr
    delta = None if displayed is None or native is None else int(displayed) - int(native)
    modifier = "TEAM_LINEUP_MODIFIER" if delta not in (None, 0) else None
    return TackleResolution(
        **base,
        canonical_player_identity=identity,
        canonical_card_id=card.get("card_id"),
        native_card_ovr=native,
        program=card.get("program"),
        display_ovr_delta=delta,
        display_modifier_classification=modifier,
        status="MATCHED",
    )


def resolve_tackles(
    observation: TackleScreenObservation, cards: list[dict]
) -> list[TackleResolution]:
    if observation.view != "OFFENSE":
        raise ValueError("C-3PO pilot accepts OFFENSE only")
    out = []
    for slot, position in (("LT1", "LT"), ("RT1", "RT")):
        translated = observation.slots[slot]
        out.append(resolve_player(translated.starter, position, cards, slot, 0))
        out.extend(
            resolve_player(row, position, cards, slot, depth)
            for depth, row in enumerate(translated.backups, 1)
        )
    return out


class TackleResolutionStore:
    """Small durable boundary proving translated observations survive restart."""

    def __init__(self, path: Path):
        self.path = path

    def save(
        self,
        observation: TackleScreenObservation,
        resolutions: list[TackleResolution],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "translator_observation": observation.to_dict(),
            "resolutions": [asdict(row) for row in resolutions],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

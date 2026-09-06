"""CFB27-only controlled-vocabulary matching for Team Manager OCR observations."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from operation_pancake.team_import import SLOT_POSITION, Candidate, normalize_name

ROLE_POSITIONS = {
    "WILL": {"LOLB", "MLB"},
    "MIKE": {"MLB"},
    "SAM": {"ROLB", "MLB"},
    "REDG": {"RE", "LE"},
    "LEDG": {"LE", "RE"},
    "KR": {"WR", "HB", "RB", "CB"},
    "PR": {"WR", "HB", "RB", "CB"},
    # The CFB corpus has no native LS cards; the game's LS depth-chart group
    # uses tight ends. Do not silently leave this role with a zero-card pool.
    "LS": {"TE"},
    "KOS": {"K"},
    "3DRB": {"HB", "RB"},
    "PWHB": {"HB", "RB", "FB"},
    "SLWR": {"WR"},
    "GAD": {"FB", "TE", "HB", "RB"},
    "NT": {"DT"},
    "SUBLB": {"MLB", "LOLB", "ROLB", "SS"},
    "RRE": {"RE", "LE"},
    "RDT": {"DT"},
    "RLE": {"LE", "RE"},
    "SLCB": {"CB"},
}


def _positions(candidate: Candidate) -> set[str]:
    role = (SLOT_POSITION.get(candidate.slot, candidate.position) or "").upper()
    return ROLE_POSITIONS.get(role, {role} if role else set())


def _is_cfb27(card) -> bool:
    markers = [
        card.get(k) for k in ("game", "season", "title", "dataset") if card.get(k) is not None
    ]
    if not markers:
        return True  # GMProduct.population is itself the CFB27 production corpus.
    text = " ".join(str(x).upper() for x in markers)
    if "CFB25" in text or "CFB 25" in text or "CFB26" in text or "CFB 26" in text:
        return False
    return "27" in text or "CFB27" in text or "CFB 27" in text


def _candidate_pool(positions, cards):
    return [x for x in cards if _is_cfb27(x) and (x.get("position") or "").upper() in positions]


def candidate_pool_count(candidate: Candidate, cards) -> int:
    """Return the real CFB27 eligible population size for runtime diagnostics/tests."""
    return len(_candidate_pool(_positions(candidate), cards))


def _name_score(observed: str, canonical: str) -> float:
    a, b = normalize_name(observed), normalize_name(canonical)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    at = {normalize_name(x) for x in re.findall(r"[A-Za-z]+", observed) if len(x) >= 3}
    bt = {normalize_name(x) for x in re.findall(r"[A-Za-z]+", canonical) if len(x) >= 3}
    if at and bt and at & bt:
        ratio = max(ratio, 0.82)
    return ratio


def _best_match(observed_name, displayed_ovr, positions, cards):
    if not positions:
        return (
            None,
            0.0,
            {"candidate_count": 0, "scored_count": 0, "rejection": "no-eligible-position"},
        )
    pool = _candidate_pool(positions, cards)
    if not observed_name:
        return (
            None,
            0.0,
            {"candidate_count": len(pool), "scored_count": 0, "rejection": "no-name-observation"},
        )
    scored = []
    for card in pool:
        name_score = _name_score(observed_name, card.get("player_name") or "")
        if name_score < 0.58:
            continue
        native = card.get("native_overall")
        if displayed_ovr is None or native is None:
            ovr_score = 0.45
        else:
            delta = abs(int(native) - int(displayed_ovr))
            ovr_score = 1.0 if delta == 0 else 0.65 if delta == 1 else 0.25 if delta == 2 else 0.0
        score = 0.82 * name_score + 0.18 * ovr_score
        scored.append((score, name_score, card))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if not scored:
        return (
            None,
            0.0,
            {
                "candidate_count": len(pool),
                "scored_count": 0,
                "rejection": "no-name-score-above-floor",
            },
        )
    best = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    diagnostic = {
        "candidate_count": len(pool),
        "scored_count": len(scored),
        "best_score": round(best[0], 4),
        "best_name_score": round(best[1], 4),
        "margin": round(best[0] - second, 4),
        "top_candidates": [
            {
                "card_id": row[2].get("card_id"),
                "player_name": row[2].get("player_name"),
                "position": row[2].get("position"),
                "native_overall": row[2].get("native_overall"),
                "combined_score": round(row[0], 4),
                "name_score": round(row[1], 4),
            }
            for row in scored[:3]
        ],
    }
    if best[0] < 0.76:
        return None, best[0], diagnostic | {"rejection": "combined-score-below-threshold"}
    if best[1] < 0.70:
        return None, best[0], diagnostic | {"rejection": "name-score-below-threshold"}
    if best[0] - second < 0.055:
        return None, best[0], diagnostic | {"rejection": "ambiguous-margin"}
    return best[2], best[0], diagnostic | {"rejection": "none"}


def _append_diagnostic(provenance, diagnostic):
    provenance.append(f"cfb27-candidate-count:{diagnostic.get('candidate_count', 0)}")
    provenance.append(f"cfb27-scored-count:{diagnostic.get('scored_count', 0)}")
    if "best_score" in diagnostic:
        provenance.append(f"identity-best-score:{diagnostic['best_score']}")
        provenance.append(f"identity-best-name-score:{diagnostic['best_name_score']}")
        provenance.append(f"identity-score-margin:{diagnostic['margin']}")
        provenance.append(f"identity-top-candidates:{diagnostic.get('top_candidates', [])}")
    provenance.append(f"identity-rejection:{diagnostic.get('rejection', 'unknown')}")


def _match_backup(row, positions, cards):
    raw = row.get("raw_player_name") or row.get("player_name")
    matched, confidence, diagnostic = _best_match(raw, row.get("displayed_ovr"), positions, cards)
    out = dict(row)
    out["raw_player_name"] = raw
    out["candidate_count"] = diagnostic.get("candidate_count", 0)
    out["rejection_reason"] = diagnostic.get("rejection")
    if matched is None:
        out.update(
            player_name=None, canonical_card_id=None, match_status="UNRESOLVED", confidence=None
        )
    else:
        out.update(
            player_name=matched.get("player_name"),
            canonical_card_id=matched.get("card_id"),
            match_status="MATCHED",
            confidence=round(confidence, 4),
        )
    return out


def match_candidate_cfb27(candidate: Candidate, cards):
    """Resolve one slot only against the supplied CFB27 production population."""
    positions = _positions(candidate)
    raw = candidate.player_name
    matched, confidence, diagnostic = _best_match(raw, candidate.displayed_ovr, positions, cards)
    candidate.match_diagnostics = {
        "allowed_positions": sorted(positions),
        "observed_name": raw,
        "normalized_name": normalize_name(raw or ""),
        "observed_ovr": candidate.displayed_ovr,
        **diagnostic,
    }
    candidate.provenance.append("identity-vocabulary:cfb27-only")
    candidate.provenance.append("identity-match:position+fuzzy-name+ovr")
    _append_diagnostic(candidate.provenance, diagnostic)
    candidate.canonical_card_id = None
    candidate.confidence = None
    if matched is None:
        candidate.match_status = "UNRESOLVED"
        candidate.player_name = None
        if raw:
            candidate.provenance.append(f"ocr-name-observation:{raw}")
    else:
        candidate.player_name = matched.get("player_name")
        candidate.canonical_card_id = matched.get("card_id")
        candidate.match_status = "MATCHED"
        candidate.confidence = round(confidence, 4)
    candidate.backups = [_match_backup(row, positions, cards) for row in candidate.backups]
    return candidate


def candidate_diagnostics(candidate: Candidate, cards):
    """Expose the exact production ranking/rejection decision for persisted evidence."""
    if candidate.match_diagnostics:
        return dict(candidate.match_diagnostics)
    positions = _positions(candidate)
    _, _, diagnostic = _best_match(candidate.player_name, candidate.displayed_ovr, positions, cards)
    return {
        "allowed_positions": sorted(positions),
        "observed_name": candidate.player_name,
        "normalized_name": normalize_name(candidate.player_name or ""),
        "observed_ovr": candidate.displayed_ovr,
        **diagnostic,
    }

"""Production LT/RT-only visual recognition over real uploaded screenshot pixels."""

from __future__ import annotations

import re

from PIL import Image, ImageOps

from operation_pancake.tackle_visual_pilot import fingerprint, rank, resolve

TACKLE_SLOTS = {"LT1", "RT1"}


def _pixels(box, width, height):
    left = max(0, min(width, round(box[0] * width)))
    top = max(0, min(height, round(box[1] * height)))
    right = max(left + 1, min(width, round(box[2] * width)))
    bottom = max(top + 1, min(height, round(box[3] * height)))
    return left, top, right, bottom


def visual_boxes(region):
    """Return starter and three backup visual crops for accepted Team Manager geometry."""
    left, _, right, _ = region.box
    name_top = (region.starter_name_box or region.box)[1]
    starter_bottom = (region.starter_name_box or region.box)[3]
    # The item art occupies the vertical tile immediately above its nameplate.
    starter = (left, max(0.0, name_top - 0.205), right, starter_bottom)
    return (starter, *region.backup_boxes)


def _raw_backup_observation(slot_crop, index):
    crop = slot_crop.get("crops", {}).get(f"backup_{index}", {})
    raw = (crop.get("raw_text") or "").strip()
    numbers = [int(value) for value in re.findall(r"(?<!\d)(\d{2})(?!\d)", raw)]
    ovr = next((value for value in numbers if 40 <= value <= 99), None)
    name = re.sub(r"(?<!\d)\d{2}(?!\d)", " ", raw)
    name = re.sub(r"\s+", " ", name).strip() or None
    return name, ovr, raw


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _resolve_real_observation(ranking, observed_name, observed_ovr):
    """Resolve real LT/RT observations without letting a bad art crop veto strong identity.

    The generic visual pilot deliberately uses one global threshold.  Real Team Manager
    backup rows are much shallower than the composed corpus card and therefore can have
    weak visual similarity even when OCR recovered an exact full player name.  For the
    production tackle path, exact multi-token name evidence is allowed to narrow the
    already position-isolated CFB27 pool.  A displayed OVR may be the native value or a
    +1/+2 lineup boost; it is evidence, never an exact-card exclusion.  Ambiguous same-
    player cards still require OVR or visual separation and otherwise fail closed.
    """
    selected = resolve(ranking)
    if selected or not ranking or not observed_name:
        return selected, "global-visual-text-gate" if selected else "global-gate-unresolved"
    normalized = _norm(observed_name)
    if len(observed_name.split()) < 2 or not normalized:
        return None, "insufficient-name-evidence"
    exact = [row for row in ranking if _norm(row.get("player_name")) == normalized]
    if not exact:
        return None, "no-exact-full-name-in-position-pool"
    if observed_ovr is not None:
        plausible = [
            row for row in exact
            if 0 <= int(observed_ovr) - int(row.get("overall") or 0) <= 2
        ]
        if len(plausible) == 1:
            return plausible[0], "exact-full-name+boost-tolerant-ovr"
        if plausible:
            exact = plausible
    if len(exact) == 1:
        return exact[0], "unique-exact-full-name-in-position-pool"
    exact = sorted(exact, key=lambda row: (row["visual"], row["final"]), reverse=True)
    if len(exact) > 1 and exact[0]["visual"] - exact[1]["visual"] >= 0.035:
        return exact[0], "exact-full-name+visual-card-disambiguation"
    return None, "same-player-card-ambiguity"


def _ranking_diagnostic(ranking, selected, reason):
    best = ranking[0] if ranking else None
    second = ranking[1] if len(ranking) > 1 else None
    return {
        "top_visual_candidates": ranking[:3],
        "visual_score": best.get("visual") if best else None,
        "text_name_score": best.get("name") if best else None,
        "ovr_compatibility": best.get("ovr") if best else None,
        "position_compatibility": best.get("position_score") if best else None,
        "final_score": best.get("final") if best else None,
        "ambiguity_margin": (
            round(best["final"] - second["final"], 6) if best and second else None
        ),
        "decision": "ACCEPTED" if selected else "UNRESOLVED",
        "decision_reason": reason,
        "accepted_card_id": selected.get("canonical_card_id") if selected else None,
    }


def recognize_tackle_candidate(path, candidate, region, slot_crop, index):
    """Apply the shared 638-card recognizer to one LT1 or RT1 and its backups."""
    diagnostics = []
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        boxes = visual_boxes(region)
        for crop_index, box in enumerate(boxes):
            pixel_box = _pixels(box, image.width, image.height)
            crop = image.crop(pixel_box)
            if crop_index == 0:
                name = candidate.match_diagnostics.get("observed_name") or candidate.player_name
                ovr = candidate.displayed_ovr
                raw = name or ""
                target = candidate
            else:
                name, ovr, raw = _raw_backup_observation(slot_crop, crop_index)
                backup_position = crop_index - 1
                target = (
                    candidate.backups[backup_position]
                    if backup_position < len(candidate.backups)
                    else None
                )
                if target:
                    name = target.get("raw_player_name") or target.get("player_name") or name
                    if target.get("displayed_ovr") is not None:
                        ovr = target["displayed_ovr"]
            ranking = rank(index, fingerprint(crop), name, ovr, candidate.position or "")
            selected, reason = _resolve_real_observation(ranking, name, ovr)
            diagnostic = {
                "source_screenshot": str(path),
                "slot": candidate.slot,
                "deterministic_position": candidate.position,
                "candidate_pool_size": sum(
                    1 for item in index if item.card.position == (candidate.position or "").upper()
                ),
                "starter_backup_index": crop_index,
                "crop_dimensions": [crop.width, crop.height],
                "normalized_crop": list(box),
                "pixel_crop": list(pixel_box),
                "ocr_name_observation": name,
                "raw_ocr_observation": raw,
                "displayed_ovr_observation": ovr,
                **_ranking_diagnostic(ranking, selected, reason),
            }
            diagnostics.append(diagnostic)
            if crop_index == 0:
                candidate.canonical_card_id = None
                candidate.confidence = None
                if selected:
                    candidate.player_name = selected["player_name"]
                    candidate.canonical_card_id = selected["canonical_card_id"]
                    candidate.program = selected["program"]
                    candidate.confidence = selected["final"]
                    candidate.match_status = "MATCHED"
                else:
                    candidate.player_name = None
                    candidate.match_status = "UNRESOLVED"
            elif target is not None:
                target["canonical_card_id"] = None
                target["confidence"] = None
                if selected:
                    target["player_name"] = selected["player_name"]
                    target["canonical_card_id"] = selected["canonical_card_id"]
                    target["program"] = selected["program"]
                    target["confidence"] = selected["final"]
                    target["match_status"] = "MATCHED"
                else:
                    target["player_name"] = None
                    target["match_status"] = "UNRESOLVED"
    candidate.match_diagnostics = {
        **candidate.match_diagnostics,
        "recognizer": "CFB27_LT_RT_VISUAL_TEXT_V2",
        "index_card_count": len(index),
        "real_uploaded_pixels": True,
        "crops": diagnostics,
    }
    candidate.provenance.append("identity-match:cfb27-tackle-visual+name+boost-tolerant-ovr+position")
    return diagnostics

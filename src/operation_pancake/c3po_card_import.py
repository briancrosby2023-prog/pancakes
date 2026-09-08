"""Bounded production import reconciliation and durable exact-card artwork."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from urllib.parse import urlparse

from operation_pancake.c3po_card_version import C3POCardObservation, CardVersionAnalysisRequest
from operation_pancake.c3po_roster import observation_fingerprint, roster_observations
from operation_pancake.card_art import _normalized

LOGGER = logging.getLogger(__name__)


def exact_candidates(cards, name, program):
    """Use visual program alternatives within one player's family; never use OVR."""
    labels = re.split(r"\s*(?:/|\||\bor\b)\s*", program or "", flags=re.IGNORECASE)
    labels = {_normalized(label) for label in labels if label.strip()}
    labels = {"phenoms" if label == "kickoffphenoms" else label for label in labels}
    return [
        card
        for card in cards
        if _normalized(name)
        and _normalized(card.get("player_name")) == _normalized(name)
        and _normalized(card.get("program")) in labels
    ]


def acquisition_card(card):
    """Adapt scored provenance only when it reproduces the exact stable ID."""
    from operation_pancake.models.cfb27_card_state import stable_id

    adapted = dict(card)
    source = card.get("source") or {}
    if not adapted.get("external_card_id") and isinstance(source, dict):
        url = urlparse(source.get("ratings") or "")
        external_id = url.path.rstrip("/").rsplit("/", 1)[-1]
        if url.hostname in {"cfb.fan", "www.cfb.fan"} and re.fullmatch(r"27-\d+", external_id):
            adapted.update(external_source=source.get("card"), external_card_id=external_id)
    if stable_id(
        "card", adapted.get("external_source"), adapted.get("external_card_id")
    ) != card.get("card_id"):
        raise ValueError("acquisition provenance does not match exact card ID")
    return adapted


def complete_import(service, roster):
    """One reconciliation, at most one clarification batch, then acquire once per ID."""
    from operation_pancake.research.cfb27_card_art import acquire_card_art, existing_card_art_asset

    cards = tuple(
        service.enrichment_cards()
        if callable(service.enrichment_cards)
        else service.enrichment_cards or ()
    )
    rows = roster_observations(roster)
    programs = {observation_fingerprint(p, i): p.program for i, p in rows}
    pending = [
        CardVersionAnalysisRequest(observation_fingerprint(p, i), p)
        for i, p in rows
        if p.name and len(exact_candidates(cards, p.name, p.program)) != 1
    ]
    clarification = 0
    clarification_reason = "no clarification needed"
    evidence = (
        service.source_evidence_store.load_for(roster) if service.source_evidence_store else None
    )
    if pending:
        clarification_reason = "clarification evidence/analyzer unavailable"
        if evidence is not None and service.version_analyzer is not None:
            clarification = 1
            try:
                result = service.version_analyzer.analyze_batch(tuple(pending), evidence)
                clarification_reason = "unresolved after one clarification batch"
                if result.request_succeeded:
                    for request in pending:
                        decision = result.decisions.get(request.fingerprint)
                        if decision is not None and decision.state == "IDENTIFIED":
                            programs[request.fingerprint] = decision.program
                else:
                    clarification_reason = "clarification provider failure; held without retry"
            except Exception as exc:
                clarification_reason = (
                    f"clarification failed ({type(exc).__name__}); held without retry"
                )
                LOGGER.warning("%s", clarification_reason)
    assets = {}
    errors = {}
    reused = acquired = screenshot_crops = 0
    stored = {}
    no_art = []
    visible_occurrences = {}
    for occurrence, player in rows:
        visible_occurrences.setdefault((player.view, player.slot), occurrence)
    for occurrence, player in rows:
        is_visible_card = visible_occurrences[(player.view, player.slot)] == occurrence
        fingerprint = observation_fingerprint(player, occurrence)
        program = programs[fingerprint]
        matches = exact_candidates(cards, player.name, program)
        card = matches[0] if len(matches) == 1 else None
        card_id = card.get("card_id") if card else None
        asset = None
        reason = None
        if card_id:
            program = card.get("program")
            if card_id not in assets:
                assets[card_id] = None
                if service.card_art_root is None:
                    errors[card_id] = "local artwork root unavailable"
                else:
                    root = service.card_art_root.parents[2]
                    try:
                        exact_source = acquisition_card(card)
                        asset = existing_card_art_asset(root, exact_source)
                        if asset:
                            reused += 1
                        else:
                            asset = acquire_card_art(root, exact_source)
                            if asset:
                                acquired += 1
                        if not asset and evidence is not None and is_visible_card:
                            from operation_pancake.c3po_screenshot_art import save_card_crop

                            asset = save_card_crop(evidence, player, card_id, service.card_art_root)
                            if asset:
                                screenshot_crops += 1
                        assets[card_id] = asset
                        if not asset:
                            errors[card_id] = (
                                "artwork source metadata missing or invalid image response"
                            )
                    except Exception as exc:
                        errors[card_id] = (
                            f"artwork acquisition failed ({type(exc).__name__}); no retry"
                        )
            asset = assets[card_id]
            reason = errors.get(card_id)
        else:
            reason = (
                (
                    "multiple exact player/program cards"
                    if len(matches) > 1
                    else "no exact player/program card"
                )
                + "; "
                + clarification_reason
            )
            if evidence is not None and service.card_art_root is not None and is_visible_card:
                from operation_pancake.c3po_screenshot_art import save_observation_crop

                asset = save_observation_crop(evidence, player, fingerprint, service.card_art_root)
                if asset:
                    screenshot_crops += 1
        stored[fingerprint] = C3POCardObservation(
            fingerprint,
            player.name or "",
            player.displayed_ovr,
            program,
            "IDENTIFIED" if program else "UNCERTAIN",
            card_id=card_id,
            art_asset=asset,
        )
        if not asset:
            no_art.append(
                dict(
                    occurrence=occurrence,
                    name=player.name,
                    view=player.view,
                    slot=player.slot,
                    displayed_ovr=player.displayed_ovr,
                    program=program,
                    card_id=card_id,
                    reason=reason,
                )
            )
    # Specialist/special-teams duplicates are the same lineup card, not a new card-version choice.
    # Propagate only when every already-resolved occurrence of that exact player agrees.
    by_player = {}
    for observation in stored.values():
        by_player.setdefault(observation.player_name.casefold(), []).append(observation)
    for observations in by_player.values():
        resolved = [item for item in observations if item.card_id]
        exact_ids = {item.card_id for item in resolved}
        if len(exact_ids) != 1 or not resolved:
            continue
        source = resolved[0]
        if any(
            item.program != source.program or item.art_asset != source.art_asset
            for item in resolved
        ):
            continue
        for item in observations:
            if item.card_id or item.state != "UNCERTAIN":
                continue
            stored[item.fingerprint] = replace(
                item,
                program=source.program,
                state="IDENTIFIED",
                confidence="HIGH",
                positive_visual_evidence=("same persisted lineup player exact card",),
                card_id=source.card_id,
                art_asset=source.art_asset,
            )

    service.card_observation_store.save(stored)
    report = dict(
        initial_request_count=getattr(service.provider, "request_count", None),
        clarification_request_count=clarification,
        observations_processed=len(rows),
        programs_identified=sum(bool(x.program) for x in stored.values()),
        exact_observations_resolved=sum(bool(x.card_id) for x in stored.values()),
        unique_exact_cards=len(assets),
        existing_images_reused=reused,
        new_images_acquired=acquired,
        screenshot_images_cropped=screenshot_crops,
        observations_with_art=sum(bool(x.art_asset) for x in stored.values()),
        no_art=no_art,
    )
    target = service.store.path.parent / "c3po-import-report.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return report

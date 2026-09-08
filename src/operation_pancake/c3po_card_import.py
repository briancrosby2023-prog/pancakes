"""Bounded production import reconciliation and durable exact-card artwork."""

from __future__ import annotations

import json
import logging
import re
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
    if pending:
        clarification_reason = "clarification evidence/analyzer unavailable"
        evidence = (
            service.source_evidence_store.load_for(roster)
            if service.source_evidence_store
            else None
        )
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
    reused = acquired = 0
    stored = {}
    no_art = []
    for occurrence, player in rows:
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
        observations_with_art=sum(bool(x.art_asset) for x in stored.values()),
        no_art=no_art,
    )
    target = service.store.path.parent / "c3po-import-report.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return report

from types import SimpleNamespace

from operation_pancake.c3po_card_import import complete_import, exact_candidates
from operation_pancake.c3po_card_version import C3POCardObservation, C3POCardObservationStore
from operation_pancake.c3po_roster import C3POPlayer, C3PORoster, observation_fingerprint


def _card(card_id: str, ovr: int):
    return {
        "card_id": card_id,
        "player_name": "Example Player",
        "program": "Phenoms",
        "native_overall": ovr,
    }


def test_exact_candidates_require_observation_ovr():
    cards = (_card("card:87", 87), _card("card:88", 88))

    assert [c["card_id"] for c in exact_candidates(cards, "Example Player", "Phenoms", 88)] == [
        "card:88"
    ]


def test_complete_import_does_not_reuse_different_ovr_instance(tmp_path):
    player = C3POPlayer("OFFENSE", "WR 1", "Example Player", 88, program="Phenoms")
    roster = C3PORoster((player,), "test", "test")
    fingerprint = observation_fingerprint(player, 0)
    store = C3POCardObservationStore(tmp_path / "c3po-programs.json")
    store.save(
        {
            fingerprint: C3POCardObservation(
                fingerprint,
                "Example Player",
                88,
                "Phenoms",
                "IDENTIFIED",
                card_id="card:87",
                art_asset="data/production/card_art/card-87.png",
            )
        }
    )
    service = SimpleNamespace(
        enrichment_cards=(_card("card:87", 87), _card("card:88", 88)),
        card_observation_store=store,
        source_evidence_store=None,
        version_analyzer=None,
        card_art_root=None,
        provider=SimpleNamespace(request_count=0),
        store=SimpleNamespace(path=tmp_path / "c3po-roster.json"),
    )
    complete_import(service, roster)
    current = store.load()[fingerprint]
    assert current.card_id == "card:88"
    assert current.art_asset is None

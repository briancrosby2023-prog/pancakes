from types import SimpleNamespace

import pytest

from operation_pancake.c3po_card_version import CardVersionBatchResult, CardVersionDecision
from operation_pancake.c3po_roster import C3PORosterService, C3PORosterStore
from operation_pancake.c3po_source_evidence import C3POSourceEvidenceStore


def setup_flow(tmp_path, monkeypatch, programs, decisions):
    from operation_pancake.research import cfb27_card_art

    cards = [
        dict(
            card_id="card:530a89e75c2dedc339b9",
            player_name="Player One",
            program="Phenoms",
            native_overall=91,
            source={"card": "CFB_FAN", "ratings": "https://cfb.fan/players/1-player-one/27-123/"},
            card_art_asset=None,
        ),
        dict(card_id="card:two", player_name="Player Two", program="Phenoms", native_overall=91),
        dict(
            card_id="card:three",
            player_name="Player Two",
            program="Ultimate Alumni",
            native_overall=91,
        ),
    ]
    calls = []

    def acquire(root, card):
        assert card["external_source"] == "CFB_FAN"
        assert card["external_card_id"] == "27-123"
        calls.append(card["card_id"])
        asset = "data/production/card_art/" + card["card_id"].replace(":", "-") + ".png"
        path = root / asset
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"local art")
        return asset

    monkeypatch.setattr(cfb27_card_art, "acquire_card_art", acquire)
    monkeypatch.setattr(cfb27_card_art, "existing_card_art_asset", lambda root, card: None)

    class Provider:
        def read_four(self, paths):
            return [
                dict(
                    view="OFFENSE",
                    provider="mock",
                    model="mock",
                    players=[
                        dict(name=name, slot=f"LG {i + 1}", displayed_ovr=91, program=program)
                        for i, (name, program) in enumerate(programs)
                    ],
                )
            ]

    class Analyzer:
        def __init__(self):
            self.batches = []

        def analyze_batch(self, requests, evidence):
            self.batches.append(requests)
            return CardVersionBatchResult(
                {r.fingerprint: decisions[r.observation.name] for r in requests}, True
            )

    analyzer = Analyzer()
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        Provider(),
        enrichment_cards=cards,
        source_evidence_store=C3POSourceEvidenceStore(tmp_path / "evidence.zip"),
        version_analyzer=analyzer,
        card_art_root=tmp_path / "data/production/card_art",
    )
    paths = []
    for i in range(4):
        p = tmp_path / f"{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nmock")
        paths.append(p)
    return SimpleNamespace(service=service, paths=paths, analyzer=analyzer, calls=calls)


@pytest.mark.parametrize("program", ["Kickoff Phenoms", "Phenoms / Ultimate Alumni"])
def test_exact_ovr_and_program_family_resolve_and_acquire_once(tmp_path, monkeypatch, program):
    flow = setup_flow(tmp_path, monkeypatch, [("Player One", program)] * 2, {})
    roster = flow.service.import_four(flow.paths)
    saved = list(flow.service.card_observation_store.load().values())
    assert [x.card_id for x in saved] == ["card:530a89e75c2dedc339b9"] * 2
    assert all(
        x.art_asset == "data/production/card_art/card-530a89e75c2dedc339b9.png" for x in saved
    )
    assert [x.displayed_ovr for x in roster.players] == [91, 91]
    assert flow.calls == ["card:530a89e75c2dedc339b9"]
    assert not flow.analyzer.batches


def test_one_targeted_batch_then_hold_genuine_ambiguity(tmp_path, monkeypatch):
    flow = setup_flow(
        tmp_path,
        monkeypatch,
        [("Player One", None), ("Player Two", "Phenoms / Ultimate Alumni")],
        {
            "Player One": CardVersionDecision.identified("Kickoff Phenoms", ("visible design",)),
            "Player Two": CardVersionDecision.ambiguous(),
        },
    )
    flow.service.import_four(flow.paths)
    assert len(flow.analyzer.batches) == 1
    assert len(flow.analyzer.batches[0]) == 2
    saved = {x.player_name: x for x in flow.service.card_observation_store.load().values()}
    assert saved["Player One"].card_id == "card:530a89e75c2dedc339b9"
    assert saved["Player One"].art_asset
    assert saved["Player Two"].card_id is None
    assert saved["Player Two"].art_asset is None
    assert flow.calls == ["card:530a89e75c2dedc339b9"]

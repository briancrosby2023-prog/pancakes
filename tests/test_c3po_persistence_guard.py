from pathlib import Path

from operation_pancake.c3po_card_version import (
    C3POCardObservation,
    C3POCardObservationStore,
)
from operation_pancake.c3po_roster import (
    C3POPlayer,
    C3PORoster,
    C3PORosterService,
    C3PORosterStore,
    roster_observations,
)


def _roster(count: int) -> C3PORoster:
    players = tuple(
        C3POPlayer("OFFENSE", f"LT {index + 1}", f"Player {index}", 80) for index in range(count)
    )
    return C3PORoster(players, "test", "test")


def _observation(index: int, *, art: str | None = None) -> C3POCardObservation:
    return C3POCardObservation(
        f"fp-{index}",
        f"Player {index}",
        80,
        "Phenoms",
        "IDENTIFIED",
        art_asset=art,
    )


def test_partial_41_import_cannot_replace_authoritative_79(tmp_path, monkeypatch):
    store = C3PORosterStore(tmp_path / "roster.json")
    authoritative = _roster(79)
    store.save(authoritative)
    service = C3PORosterService(
        store,
        object(),
        enrichment_cards=(),
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
    )
    partial = _roster(41)
    monkeypatch.setattr(
        "operation_pancake.c3po_roster.roster_from_screens",
        lambda paths, provider: partial,
    )

    result = service.import_four(tuple(Path(str(i)) for i in range(4)))

    assert len(roster_observations(result)) == 79
    assert len(roster_observations(store.load())) == 79
    assert store.load() == authoritative


def test_partial_enrichment_merges_without_erasing_other_observations(tmp_path):
    store = C3POCardObservationStore(tmp_path / "programs.json")
    store.save({f"fp-{i}": _observation(i) for i in range(79)})
    partial = {
        f"fp-{i}": _observation(i, art=f"data/production/card_art/{i}.png") for i in range(41)
    }
    store.save(partial)

    loaded = store.load()
    assert len(loaded) == 79
    assert loaded["fp-40"].art_asset.endswith("40.png")
    assert loaded["fp-78"].player_name == "Player 78"


def test_preserved_exact_choice_beats_conflicting_later_mapping(tmp_path):
    store = C3POCardObservationStore(tmp_path / "programs.json")
    preserved = C3POCardObservation(
        "fp",
        "Cason Henry",
        86,
        "Phenoms",
        "IDENTIFIED",
        positive_visual_evidence=("preserved exact fingerprint choice",),
        card_id="card:phenoms",
        art_asset="data/production/card_art/cason-phenoms.png",
    )
    store.save({"fp": preserved})
    store.save(
        {
            "fp": C3POCardObservation(
                "fp",
                "Cason Henry",
                86,
                "Core Rare",
                "IDENTIFIED",
                card_id="card:core",
                art_asset="data/production/card_art/cason-core.png",
            )
        }
    )

    loaded = store.load()["fp"]
    assert loaded.card_id == "card:phenoms"
    assert loaded.program == "Phenoms"
    assert loaded.art_asset.endswith("cason-phenoms.png")


def test_duplicate_name_observations_keep_independent_art_after_reload(tmp_path):
    store = C3POCardObservationStore(tmp_path / "programs.json")
    store.save(
        {
            "fp-a": C3POCardObservation(
                "fp-a",
                "DJ Hicks",
                86,
                "Phenoms",
                "IDENTIFIED",
                art_asset="data/production/card_art/dj-defense.png",
            ),
            "fp-b": C3POCardObservation(
                "fp-b",
                "DJ Hicks",
                85,
                None,
                "UNCERTAIN",
                art_asset="data/production/card_art/dj-specialists.png",
            ),
        }
    )

    loaded = store.load()
    assert loaded["fp-a"].displayed_ovr == 86
    assert loaded["fp-b"].displayed_ovr == 85
    assert loaded["fp-a"].art_asset != loaded["fp-b"].art_asset


def test_screenshot_fallback_never_assigns_starter_crop_to_backup(tmp_path, monkeypatch):
    from operation_pancake import c3po_screenshot_art
    from operation_pancake.c3po_card_import import complete_import

    roster = C3PORoster(
        (
            C3POPlayer("OFFENSE", "LT 1", "Starter", 84),
            C3POPlayer("OFFENSE", "LT 1", "Backup", 81),
        ),
        "test",
        "test",
    )

    class EvidenceStore:
        def load_for(self, _roster):
            return object()

    calls = []

    def save_observation_crop(evidence, player, fingerprint, card_art_root):
        calls.append((player.name, fingerprint))
        return f"data/production/card_art/{player.name.lower()}.png"

    monkeypatch.setattr(c3po_screenshot_art, "save_observation_crop", save_observation_crop)
    service = C3PORosterService(
        C3PORosterStore(tmp_path / "roster.json"),
        provider=object(),
        enrichment_cards=(),
        source_evidence_store=EvidenceStore(),
        version_analyzer=None,
        card_observation_store=C3POCardObservationStore(tmp_path / "programs.json"),
        card_art_root=tmp_path / "data/production/card_art",
    )
    service.store.save(roster)

    report = complete_import(service, roster)
    stored = service.card_observation_store.load()

    assert [name for name, _fingerprint in calls] == ["Starter"]
    assert report["screenshot_images_cropped"] == 1
    assert sum(bool(row.art_asset) for row in stored.values()) == 1
    assert next(row for row in stored.values() if row.player_name == "Backup").art_asset is None


def test_program_store_windows_replace_fallback_preserves_payload(tmp_path, monkeypatch):
    store = C3POCardObservationStore(tmp_path / "programs.json")
    original_replace = Path.replace

    def deny_replace(path, target):
        if path.name == "programs.json.tmp":
            raise PermissionError("simulated Windows rename denial")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", deny_replace)
    store.save({"fp-0": _observation(0, art="data/production/card_art/0.png")})

    loaded = store.load()
    assert loaded["fp-0"].art_asset == "data/production/card_art/0.png"
    assert not (tmp_path / "programs.json.tmp").exists()

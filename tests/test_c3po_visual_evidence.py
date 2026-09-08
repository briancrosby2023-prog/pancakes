from operation_pancake.c3po_card_version import (
    C3POCardObservation,
    C3POCardObservationStore,
)


def test_c3po_visual_annotations_survive_persistence_reload(tmp_path):
    store = C3POCardObservationStore(tmp_path / "programs.json")
    visual = {
        "section": "DEFENSE",
        "slot": "MIKE 2",
        "occurrence": 1,
        "lineup_role": "starter",
        "displayed_ovr": 87,
        "displayed_ovr_color": "unread",
        "actual_card_face_visible": True,
        "card_face_ovr": 87,
        "card_face_position": "MIKE",
        "evo_badge_treatment": "visible green EVO badge",
    }
    observation = C3POCardObservation(
        "fp", "Junior Seau", 87, "Sunday Spotlight: Retro", "IDENTIFIED",
        card_id="card:retro", visual_evidence=visual,
    )
    store.save({"fp": observation})
    assert store.load()["fp"].visual_evidence == visual

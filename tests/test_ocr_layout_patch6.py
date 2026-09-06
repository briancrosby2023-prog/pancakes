from types import SimpleNamespace

from operation_pancake import ocr_team_app_patch6 as patch6


class Store:
    def __init__(self, state):
        self.state = state
        self.saved = []

    def load(self):
        return self.state

    def save(self, state):
        self.state = state
        self.saved.append(state)


def test_current_batch_discards_historical_screenshot_attempts(monkeypatch):
    shots = [
        {"id": f"shot-{i}", "filename": f"old-{i}.jpg"}
        for i in range(1, 9)
    ] + [
        {"id": "shot-9", "filename": "0 import o.jpg"},
        {"id": "shot-10", "filename": "0 import d.jpg"},
        {"id": "shot-11", "filename": "0 import special teams.jpg"},
        {"id": "shot-12", "filename": "0 import special.jpg"},
    ]
    state = SimpleNamespace(screenshots=shots, candidates=[object()], team_observations={"old": True})
    store = Store(state)
    observed = {}

    def fake_extract(current_store, gm):
        current = current_store.load()
        observed["filenames"] = [x["filename"] for x in current.screenshots]
        observed["candidates"] = current.candidates
        observed["observations"] = current.team_observations
        return current

    monkeypatch.setattr(patch6.patch5, "_extract_unique", fake_extract)
    patch6._extract_current_batch(store, object())

    assert observed["filenames"] == [
        "0 import o.jpg",
        "0 import d.jpg",
        "0 import special teams.jpg",
        "0 import special.jpg",
    ]
    assert observed["candidates"] == []
    assert observed["observations"] == {}
    assert len(store.load().screenshots) == 4


def test_patch6_runtime_overrides_production_extractor(monkeypatch):
    monkeypatch.setattr(patch6.patch5, "install_runtime", lambda: None)
    patch6.install_runtime()
    assert patch6.team_app.TEAM_SETUP_BUILD == "OCR-LAYOUT-PATCH-6"
    assert patch6.team_app._extract is patch6._extract_current_batch

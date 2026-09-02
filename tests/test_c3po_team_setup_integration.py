import pytest

from operation_pancake.c3po_team_setup import integrate_offense_tackles
from operation_pancake.c3po_vision import (
    PlayerObservation,
    TackleScreenObservation,
    TackleSlotObservation,
)
from operation_pancake.team_import import Candidate, TeamImportState, TeamImportStore


class Store:
    def __init__(self, state):
        self.state = state

    def load(self):
        return self.state

    def save(self, state):
        self.state = state


class Translator:
    def __init__(self, observation=None, error=None):
        self.observation = observation
        self.error = error

    def translate_offense_tackles(self, screenshot):
        if self.error:
            raise self.error
        return self.observation


def obs(
    rt_name="Cason Henry",
    rt_ovr=85,
    rt_backups=(),
    lt_name=None,
    lt_ovr=None,
    lt_backups=(),
):
    slots = {
        "LT1": TackleSlotObservation(
            PlayerObservation(lt_name, lt_ovr), tuple(lt_backups)
        ),
        "RT1": TackleSlotObservation(
            PlayerObservation(rt_name, rt_ovr), tuple(rt_backups)
        ),
    }
    return TackleScreenObservation("OFFENSE", slots, "fake-gemini", "fake-model")


def cards():
    return [
        {
            "game": "CFB27",
            "position": "RT",
            "player_name": "Cason Henry",
            "native_overall": 85,
            "program": "Phenoms",
            "card_id": "cason-85",
        },
        {
            "game": "CFB27",
            "position": "RT",
            "player_name": "Juan Gaston",
            "native_overall": 80,
            "program": "Phenoms",
            "card_id": "juan-80",
        },
        {
            "game": "CFB27",
            "position": "LT",
            "player_name": "Josh Petty",
            "native_overall": 80,
            "program": "Phenoms",
            "card_id": "petty-80",
        },
        {
            "game": "CFB26",
            "position": "RT",
            "player_name": "Cason Henry",
            "native_overall": 99,
            "program": "Wrong Season",
            "card_id": "old",
        },
    ]


def state(tmp_path):
    image = tmp_path / "opaque-upload.png"
    image.write_bytes(b"pixels")
    return TeamImportState(
        screenshots=[{"id": "shot-o", "path": str(image), "view": "OFFENSE"}],
        candidates=[
            Candidate("lt", "OFFENSE", "LT1", player_name="old-lt"),
            Candidate("rt", "OFFENSE", "RT1", player_name="old-rt"),
            Candidate("qb", "OFFENSE", "QB1", player_name="KEEP QB"),
            Candidate("cb", "DEFENSE", "CB1", player_name="KEEP CB"),
        ],
    )


def test_c3po_team_setup_resolves_real_tackle_shapes_and_preserves_display_native(
    tmp_path,
):
    st = state(tmp_path)
    translated = obs(
        rt_backups=(PlayerObservation("Juan Gaston", 81),),
        lt_backups=(PlayerObservation("Josh Petty", 80),),
    )
    integrate_offense_tackles(Store(st), cards(), Translator(translated))
    rt = next(c for c in st.candidates if c.slot == "RT1")
    assert (rt.player_name, rt.displayed_ovr, rt.program, rt.canonical_card_id) == (
        "Cason Henry",
        85,
        "Phenoms",
        "cason-85",
    )
    assert rt.backups[0]["player_name"] == "Juan Gaston"
    assert rt.backups[0]["native_card_ovr"] == 80
    lt = next(c for c in st.candidates if c.slot == "LT1")
    assert lt.backups[0]["player_name"] == "Josh Petty"


def test_partial_observation_fails_only_unreadable_identity(tmp_path):
    st = state(tmp_path)
    translated = obs(rt_name=None, rt_ovr=85, lt_name="Josh Petty", lt_ovr=80)
    integrate_offense_tackles(Store(st), cards(), Translator(translated))
    rt = next(c for c in st.candidates if c.slot == "RT1")
    lt = next(c for c in st.candidates if c.slot == "LT1")
    assert rt.player_name is None and rt.match_status == "UNMATCHED"
    assert lt.player_name == "Josh Petty" and lt.canonical_card_id == "petty-80"


@pytest.mark.parametrize("bad", [None, {"view": "OFFENSE"}, "not-an-observation"])
def test_malformed_translator_response_is_guarded(tmp_path, bad):
    st = state(tmp_path)
    before = [(c.id, c.player_name, c.canonical_card_id) for c in st.candidates]
    integrate_offense_tackles(Store(st), cards(), Translator(bad))
    after = [(c.id, c.player_name, c.canonical_card_id) for c in st.candidates]
    assert after == before
    assert st.team_observations["c3po_tackles"]["status"] == "ERROR"


def test_translator_timeout_preserves_state_and_safe_diagnostic(tmp_path):
    st = state(tmp_path)
    before = [(c.id, c.player_name, c.canonical_card_id) for c in st.candidates]
    error = TimeoutError("secret GEMINI_API_KEY=do-not-leak")
    integrate_offense_tackles(Store(st), cards(), Translator(error=error))
    after = [(c.id, c.player_name, c.canonical_card_id) for c in st.candidates]
    assert after == before
    assert st.team_observations["c3po_tackles"] == {
        "status": "ERROR",
        "error_type": "TimeoutError",
    }


def test_non_tackles_preserved_and_real_store_survives_restart(tmp_path):
    path = tmp_path / "team-import.json"
    durable = TeamImportStore(path)
    durable.save(state(tmp_path))
    translated = obs(
        rt_backups=(PlayerObservation("Juan Gaston", 81),),
        lt_name="Josh Petty",
        lt_ovr=80,
    )
    integrate_offense_tackles(durable, cards(), Translator(translated))
    restarted = TeamImportStore(path).load()
    assert next(c for c in restarted.candidates if c.slot == "QB1").player_name == "KEEP QB"
    assert next(c for c in restarted.candidates if c.slot == "CB1").player_name == "KEEP CB"
    rt = next(c for c in restarted.candidates if c.slot == "RT1")
    assert rt.player_name == "Cason Henry"
    assert rt.backups[0]["player_name"] == "Juan Gaston"
    assert restarted.team_observations["c3po_tackles"]["status"] == "APPLIED"

import json

import pytest

from operation_pancake.app import _page
from operation_pancake.roster_state import RosterAssignment, RosterStore


def test_page_has_product_navigation():
    rendered = _page("Test", "<h1>Hello</h1>").decode()
    assert "Operation Pancake" in rendered
    assert 'href="/"' in rendered
    assert 'href="/roster"' in rendered
    assert 'href="/compare"' in rendered
    assert "<h1>Hello</h1>" in rendered


def test_roster_persistence_add_edit_remove(tmp_path):
    path = tmp_path / "roster.json"
    store = RosterStore(path, {"card-1", "card-2"})
    row = RosterAssignment("card-1", "MIKE", "MIKE1", protected=True, rerollable=True)
    store.add(row)
    reloaded = RosterStore(path, {"card-1", "card-2"}).load()
    assert reloaded == [row]
    assert json.loads(path.read_text())["version"] == 1

    updated = store.update("MIKE1", slot="MIKE2", starter=False, notes="sub package")
    assert updated.slot == "MIKE2"
    assert not updated.starter
    assert updated.protected and updated.rerollable
    assert updated.notes == "sub package"

    removed = store.remove("MIKE2")
    assert removed.card_id == "card-1"
    assert store.load() == []


def test_roster_rejects_unknown_or_duplicate_canonical_card(tmp_path):
    store = RosterStore(tmp_path / "roster.json", {"card-1"})
    with pytest.raises(ValueError, match="unknown canonical"):
        store.add(RosterAssignment("missing", "CB", "CB1"))
    store.add(RosterAssignment("card-1", "CB", "CB1"))
    with pytest.raises(ValueError, match="already assigned"):
        store.add(RosterAssignment("card-1", "CB", "CB2"))


def test_roster_slot_is_unique(tmp_path):
    store = RosterStore(tmp_path / "roster.json", {"card-1", "card-2"})
    store.add(RosterAssignment("card-1", "CB", "CB1"))
    with pytest.raises(ValueError, match="slot CB1"):
        store.add(RosterAssignment("card-2", "CB", "CB1"))


def test_compare_preselection_link_contract():
    current = "canonical-card-id"
    rendered = f'/compare?current={current}'
    assert rendered == "/compare?current=canonical-card-id"

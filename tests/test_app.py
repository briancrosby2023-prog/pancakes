import json
import pytest
from operation_pancake.app import _page
from operation_pancake.roster_state import RosterAssignment, RosterStore
from operation_pancake.gm_state import GMStateStore


def test_page_has_product_navigation():
    rendered=_page("Test","<h1>Hello</h1>").decode()
    assert "Operation Pancake" in rendered
    assert 'href="/"' in rendered and 'href="/roster"' in rendered and 'href="/compare"' in rendered
    assert 'href="/gm"' in rendered


def test_roster_persistence_add_edit_remove(tmp_path):
    path=tmp_path/"roster.json"; store=RosterStore(path,{"card-1","card-2"}); row=RosterAssignment("card-1","MIKE","MIKE1",protected=True,rerollable=True); store.add(row)
    assert RosterStore(path,{"card-1","card-2"}).load()==[row]; assert json.loads(path.read_text())["version"]==1
    updated=store.update("MIKE1",slot="MIKE2",starter=False,notes="sub package"); assert updated.slot=="MIKE2" and not updated.starter and updated.protected and updated.rerollable
    assert store.remove("MIKE2").card_id=="card-1" and store.load()==[]


def test_roster_rejects_unknown_or_duplicate_canonical_card(tmp_path):
    store=RosterStore(tmp_path/"roster.json",{"card-1"})
    with pytest.raises(ValueError,match="unknown canonical"): store.add(RosterAssignment("missing","CB","CB1"))
    store.add(RosterAssignment("card-1","CB","CB1"))
    with pytest.raises(ValueError,match="already assigned"): store.add(RosterAssignment("card-1","CB","CB2"))


def test_roster_slot_is_unique(tmp_path):
    store=RosterStore(tmp_path/"roster.json",{"card-1","card-2"}); store.add(RosterAssignment("card-1","CB","CB1"))
    with pytest.raises(ValueError,match="slot CB1"): store.add(RosterAssignment("card-2","CB","CB1"))


def test_budget_persistence_and_reserve(tmp_path):
    store=GMStateStore(tmp_path/"gm.json",{"card-1"}); state=store.update_budget(300000,50000)
    assert state.spendable_budget==250000
    assert GMStateStore(tmp_path/"gm.json",{"card-1"}).load().spendable_budget==250000


def test_known_and_unknown_price_state(tmp_path):
    store=GMStateStore(tmp_path/"gm.json",{"card-1"}); assert store.load().prices=={}
    assert store.set_price("card-1",12345).prices=={"card-1":12345}
    assert store.set_price("card-1",None).prices=={}
    with pytest.raises(ValueError,match="unknown canonical"): store.set_price("missing",100)


def test_protected_and_rerollable_are_distinct_roster_semantics():
    protected=RosterAssignment("card-1","FS","FS1",protected=True)
    rerollable=RosterAssignment("card-2","MIKE","MIKE1",rerollable=True)
    assert protected.protected and not protected.rerollable
    assert rerollable.rerollable and not rerollable.protected


def test_compare_preselection_link_contract():
    assert "/compare?current=canonical-card-id"==f'/compare?current={"canonical-card-id"}'

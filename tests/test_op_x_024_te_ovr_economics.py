import importlib.util
from pathlib import Path

P = Path("scripts/op_x_024_te_ovr_economics.py")
spec = importlib.util.spec_from_file_location("opx24", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def card(**kw):
    base = {
        "position": "TE",
        "extraction_status": "COMPLETE",
        "program": "Core",
        "metadata": {},
        "displayed_ratings": {"SPD": 80},
        "overall": 83,
        "archetype": "Physical Route Runner",
    }
    base.update(kw)
    return base


def test_static_eligible_excludes_partial_and_dynamic():
    assert m.static_eligible(card())
    assert not m.static_eligible(card(extraction_status="PARTIAL_LISTING_VECTOR"))
    assert not m.static_eligible(card(program="Dynamic"))


def test_stats_reports_dispersion():
    s = m.stats([70, 80, 90])
    assert s["n"] == 3 and s["range"] == 20 and s["median"] == 80


def test_holdout_feature_model_helpers_are_deterministic():
    rows = []
    for i in range(12):
        rows.append(card(overall=80 + i % 3, displayed_ratings={"SPD": 70 + i, "ACC": 71 + i}))
    b = m.ridge_fit(rows, ["SPD", "ACC"])
    assert b is not None
    assert m.metrics(rows, ["SPD", "ACC"], b)["n"] == 12


def test_component_card_never_invents_missing_values():
    c = card(displayed_ratings={"SPD": 80, "ACC": 82, "CTH": 85})
    d = m.component_card(c)
    assert d["ATHLETICISM"] == 81 and d["RECEIVING"] == 85 and d["PASS_BLOCKING"] is None

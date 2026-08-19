from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT=Path(__file__).parents[1]/"scripts"/"e15_historical_te_population_validation_v2.py"
spec=spec_from_file_location("e15_v2",SCRIPT)
mod=module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def _html(archetype: str) -> str:
    return f"""<html><body><h1>C aden Prieskorn 85 OVR</h1><div>TE</div>
    <div>Archetype {archetype} - TE</div><div>SPD 84 ACC 83 AWR 82 CTH 85 CIT 84
    SRR 85 MRR 84 DRR 81 RBK 65 PBK 60 LBK 61 IBL 62</div></body></html>"""


def test_cfb25_possession_aliases_to_gritty():
    row=mod.parse(_html("Possession"),"https://cfb.fan/example",25)
    assert row is not None
    assert row["source_archetype"] == "Possession"
    assert row["archetype"] == "Gritty Possession"
    assert row["name"] == "Caden Prieskorn"


def test_cfb25_blocking_aliases_to_pure_blocker():
    row=mod.parse(_html("Blocking"),"https://cfb.fan/example",25)
    assert row is not None
    assert row["source_archetype"] == "Blocking"
    assert row["archetype"] == "Pure Blocker"


def test_cfb26_names_remain_canonical():
    for archetype in ("Gritty Possession","Vertical Threat","Physical Route Runner","Pure Blocker"):
        row=mod.parse(_html(archetype),"https://cfb.fan/example",26)
        assert row is not None
        assert row["source_archetype"] == archetype
        assert row["archetype"] == archetype

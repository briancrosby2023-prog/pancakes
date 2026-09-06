import json
from pathlib import Path

from operation_pancake.production.engine import ProductionEngine, load_population
from operation_pancake.production.registry import build_model_registry
from operation_pancake.research.cfb27_canonical_population import (
    materialize_canonical_population,
)

ROOT = Path(__file__).resolve().parents[1]


def test_refreshed_card_reaches_canonical_population_and_production_scorer(tmp_path: Path):
    state_path = tmp_path / "data/external/cfb_fan_population_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "cards": {
                    "CFB_FAN:season-2-luke": {
                        "external_source": "CFB_FAN",
                        "external_card_id": "season-2-luke",
                        "external_player_id": "luke-montgomery",
                        "player_name": "Luke Montgomery",
                        "position": "LG",
                        "overall": 87,
                        "program": "Season 2",
                        "archetype": "Agile",
                        "team_school": "Ohio State",
                        "release_date": "2026-09-03",
                        "displayed_ratings": {"STR": 88, "RBK": 86, "PBK": 87},
                        "extraction_status": "COMPLETE",
                        "source_reference": "https://cfb.fan/players/season-2-luke/",
                        "raw_snapshot_reference": "data/external/raw/luke.json",
                        "retrieval_timestamp": "2026-09-03T00:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    counts = materialize_canonical_population(tmp_path)

    assert counts == {"players": 1, "cards": 1, "card_native_states": 1}
    population = load_population(tmp_path)
    assert population[0]["player_name"] == "Luke Montgomery"
    assert population[0]["program"] == "Season 2"
    assert population[0]["native_overall"] == 87
    result = ProductionEngine(build_model_registry(ROOT)).score(population[0])
    assert result["card_id"] == population[0]["card_id"]


def test_materializer_needs_no_historical_op_x_010_artifacts(tmp_path: Path):
    state_path = tmp_path / "data/external/cfb_fan_population_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"cards": {}}), encoding="utf-8")

    counts = materialize_canonical_population(tmp_path)

    assert counts == {"players": 0, "cards": 0, "card_native_states": 0}
    export_dir = tmp_path / "data/research/cfb27_op_x_010/canonical_exports_v2"
    assert sorted(path.name for path in export_dir.iterdir()) == [
        "card_native_states.json",
        "cards.json",
        "players.json",
    ]


def test_refresh_workflow_materializes_before_scoring_and_uses_real_paths():
    workflow = (
        ROOT / ".github/workflows/cfb27-canonical-delta-refresh.yml"
    ).read_text(encoding="utf-8")

    refresh = workflow.index("python scripts/refresh_cfb27_canonical_delta.py")
    materialize = workflow.index("python scripts/materialize_cfb27_canonical_population.py")
    score = workflow.index("python scripts/generate_op_x_021_production.py")
    assert refresh < materialize < score
    assert "tests/test_op_x_021_production.py" not in workflow
    assert "tests/test_production_gm.py" in workflow
    assert '-k "not op_x_013_validated_artifacts_are_consistent"' in workflow
    assert "data/production/cfb27_scored_population.json" in workflow
    assert "data/production/op_x_021/production_scores.json" not in workflow
    assert "ref: product/c3po-clean-room-roster" in workflow
    assert "git push origin HEAD:product/c3po-clean-room-roster" in workflow
    assert "src/operation_pancake/research/cfb27_canonical_population.py" in workflow
    for path in (
        "scripts/materialize_cfb27_canonical_population.py",
        "tests/test_cfb27_canonical_population_materialization.py",
        "tests/test_production_gm.py",
    ):
        assert (ROOT / path).exists()

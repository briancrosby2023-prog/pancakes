import base64
import io
import json
from pathlib import Path

from PIL import Image

from operation_pancake.production.engine import ProductionEngine, load_population
from operation_pancake.production.registry import build_model_registry
from operation_pancake.research.cfb27_canonical_population import (
    materialize_canonical_population,
)
from operation_pancake.research.cfb27_card_art import acquire_card_art

ROOT = Path(__file__).resolve().parents[1]
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)
SEEDED_ART = {
    "Luke Montgomery": "card-90a8312982d3c1270826.png",
    "Cason Henry": "card-aabd2c5d508df4e1cabc.png",
    "Josh Petty": "card-4a964d14b782d8c7c325.png",
    "Thomas Shrader": "card-38d5dbb6bd21993e002b.png",
    "Keyan Burnett": "card-8bfb91f78594f2e4a227.png",
    "Martellus Bennett": "card-3f2b3f99fa23b0c4b6ce.png",
}


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
    acquired = acquire_card_art(
        tmp_path,
        {"external_source": "CFB_FAN", "external_card_id": "season-2-luke"},
        fetcher=lambda _url: VALID_PNG,
    )

    counts = materialize_canonical_population(tmp_path)

    assert counts == {"players": 1, "cards": 1, "card_native_states": 1}
    population = load_population(tmp_path)
    assert population[0]["player_name"] == "Luke Montgomery"
    assert population[0]["program"] == "Season 2"
    assert population[0]["native_overall"] == 87
    assert acquired == "data/production/card_art/card-65f63250856ae83fe0cb.png"
    assert population[0]["card_art_asset"] == acquired
    result = ProductionEngine(build_model_registry(ROOT)).score(population[0])
    assert result["card_id"] == population[0]["card_id"]
    assert result["card_art_asset"] == population[0]["card_art_asset"]


def test_new_card_art_is_validated_and_written_once_by_stable_card_id(tmp_path: Path):
    card = {"external_source": "CFB_FAN", "external_card_id": "27-202019231"}
    calls = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return VALID_PNG

    first = acquire_card_art(tmp_path, card, fetcher=fetcher)
    second = acquire_card_art(
        tmp_path,
        card,
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("reacquired artwork")),
    )

    assert first == "data/production/card_art/card-90a8312982d3c1270826.png"
    assert second == first
    assert (tmp_path / first).read_bytes() == VALID_PNG
    assert calls == [
        "https://media.cfb.fan/27/cutdb/playeritem/202019231.png"
    ]


def test_invalid_art_bytes_are_not_persisted(tmp_path: Path):
    card = {"external_source": "CFB_FAN", "external_card_id": "27-202019231"}

    assert acquire_card_art(tmp_path, card, fetcher=lambda _url: b"not an image") is None
    assert not (tmp_path / "data/production/card_art").exists()


def test_approved_exact_cards_have_valid_local_assets_in_canonical_and_production():
    canonical = json.loads(
        (
            ROOT
            / "data/research/cfb27_op_x_010/canonical_exports_v2/cards.json"
        ).read_text(encoding="utf-8")
    )
    production = json.loads(
        (ROOT / "data/production/cfb27_scored_population.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_by_asset = {row.get("card_art_asset"): row for row in canonical}
    production_by_asset = {row.get("card_art_asset"): row for row in production}

    for player_name, filename in SEEDED_ART.items():
        asset = f"data/production/card_art/{filename}"
        path = ROOT / asset
        assert path.is_file()
        with Image.open(io.BytesIO(path.read_bytes())) as image:
            image.verify()
            assert image.format == "PNG"
        assert canonical_by_asset[asset]["card_id"] == production_by_asset[asset]["card_id"]
        assert production_by_asset[asset]["player_name"] == player_name


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

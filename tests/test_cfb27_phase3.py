import hashlib
import json
from pathlib import Path

from operation_pancake.research.cfb27_phase3 import build_phase3_analysis

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data/research/cfb27_inheritance_phase3/phase3_summary.json"


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_phase3_freeze_is_preacquisition_and_content_addressed() -> None:
    freeze = _load("data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json")
    assert freeze["source_commit"] == "b6ce2ed"
    assert freeze["population"]["count"] == 376
    assert len(freeze["center_training"]["card_ids"]) == 42
    assert len(freeze["population"]["normalized_sha256"]) == 64
    assert freeze["guessed_values"] is False
    assert freeze["leakage"] is False


def test_null_tests_are_large_deterministic_and_adversarial() -> None:
    nulls = _load("data/research/cfb27_inheritance_phase3/inheritance_null_tests.json")
    assert set(nulls) >= {
        "historical",
        "equal",
        "random_positive",
        "shuffled_historical",
        "random_attribute_subsets",
    }
    for key in ("random_positive", "shuffled_historical", "random_attribute_subsets"):
        assert nulls[key]["draws"] == 1000
        assert 0 <= nulls[key]["historical_mae_percentile"] <= 100


def test_prospective_validation_never_refits_or_reuses_training_ids() -> None:
    freeze = _load("data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json")
    validation = _load("data/research/cfb27_inheritance_phase3/center_prospective_validation.json")
    training = set(freeze["center_training"]["card_ids"])
    assert validation["frozen_training_n"] == 42
    assert not training.intersection(row["card_id"] for row in validation["new_ordinary_centers"])
    assert validation["unique_profile_n"] <= len(validation["new_ordinary_centers"])
    assert validation["unique_profile_n"] + validation["duplicate_profile_cards"] == len(
        validation["new_ordinary_centers"]
    )
    assert validation["status"] in {"EVALUATED_WITHOUT_REFIT", "NO_NEW_ELIGIBLE_CARDS_FOUND"}


def test_release_and_moneyball_outputs_are_noncausal_and_complete() -> None:
    summary = _load("data/research/cfb27_inheritance_phase3/phase3_summary.json")
    assert (
        sum(row["new_cards"] for row in summary["release_chronology"]["daily"])
        == summary["population"]["total"]
    )
    assert summary["same_ovr_variance_and_cost"]["rows"]
    assert summary["gameplay_evidence_join_schema"]["claims_populated"] is False
    assert all("warning" in row for row in summary["same_ovr_variance_and_cost"]["rows"])


def test_special_ordinary_market_and_trigger_guards() -> None:
    summary = _load("data/research/cfb27_inheritance_phase3/phase3_summary.json")
    assert summary["ordinary_vs_special_matched"]["causal_claim"] is False
    assert summary["trigger_falsification"]["supported_triggers"] == 0
    assert summary["market_data_readiness"]["status"] in {"READY", "SCHEMA_PRESENT_DATA_ABSENT"}
    assert summary["data_validation"] == {
        "guessed_values": False,
        "leakage": False,
        "special_ordinary_contamination": False,
        "access_bypass": False,
        "canonical_modified": False,
    }


def test_phase3_rebuilds_deterministically() -> None:
    state = _load("data/external/cfb_fan_population_state.json")
    freeze = _load("data/research/cfb27_inheritance_phase3/phase3_frozen_snapshot.json")
    phase2 = _load("data/research/cfb27_inheritance_phase2/phase2_summary.json")
    rebuilt = build_phase3_analysis(list(state["cards"].values()), freeze, phase2)
    assert (
        hashlib.sha256(json.dumps(rebuilt, sort_keys=True).encode()).hexdigest()
        == hashlib.sha256(
            json.dumps(json.loads(ARTIFACT.read_text(encoding="utf-8")), sort_keys=True).encode()
        ).hexdigest()
    )

"""An artifact must say which estimator produced it, and the loader must believe nothing else.

Synthetic counts only. Two estimators now exist, and the danger is not that a queue model
fails to load — it is that a cohort table is read by the wrong arithmetic and still produces
confident numbers. Every refusal below exists to make a mismatch loud instead of plausible.
"""

import json
from pathlib import Path

import pytest

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION, parse_status
from railconfirm.inference.artifacts import (
    ARTIFACT_FORMAT,
    ESTIMATOR_HISTORICAL_FREQUENCY,
    PROMOTION_APPROVED,
    LoadedArtifact,
    ModelArtifactMetadata,
    build_artifact_document,
    load_artifact,
    metadata_from_mapping,
    write_artifact,
)
from railconfirm.inference.baseline import (
    COHORT_FEATURES,
    COHORT_STATUS_SEMANTICS,
    HistoricalFrequencyBaseline,
)
from railconfirm.inference.queue import (
    QUEUE_ARTIFACT_FORMAT,
    QUEUE_ESTIMATOR_ID,
    QUEUE_FEATURES,
    CohortPositionBaseline,
)

COHORTS = {("SL", "GN", "WL"): {"CNF": 40, "WL": 60}}
BANDS = {
    ("SL", "GN", "WL", "1"): {"CNF": 30, "WL": 5},
    ("SL", "GN", "WL", "2-3"): {"CNF": 8, "WL": 12},
}


def queue_metadata(**overrides):
    base = {
        "version": "queue_v1",
        "target": "final_chart_cnf",
        "estimator": QUEUE_ESTIMATOR_ID,
        "feature_schema_version": "3.0.0",
        "status_mapping_version": MAPPING_VERSION,
        "outcome_classes": ("CNF", "RAC", "WL", "CANCELLED", "OTHER"),
        "dataset_id": "queue-fixture",
        "dataset_sha256": "a" * 64,
        "source_reference": "tests/inference/test_queue_artifact.py",
        "data_approval_status": "approved",
        "is_synthetic": False,
        "min_sample_threshold": 5,
        "laplace_alpha": 1.0,
        "promotion": "candidate",
        "limitations": ("Position-aware cohort estimates, fitted on synthetic rows.",),
        "features_used": QUEUE_FEATURES,
        "cohort_semantics": COHORT_STATUS_SEMANTICS,
        "trained_from": "2026-04-01",
        "trained_to": "2026-04-06",
    }
    base.update(overrides)
    return ModelArtifactMetadata(**base)


def frequency_metadata(**overrides):
    base = {"estimator": ESTIMATOR_HISTORICAL_FREQUENCY, "features_used": COHORT_FEATURES}
    base.update(overrides)
    return queue_metadata(**base)


def write(tmp_path: Path, metadata, bands=None, cohorts=COHORTS, name=None) -> Path:
    path = tmp_path / (name or f"{metadata.version}.json")
    return write_artifact(path, metadata, cohorts, bands=bands)


# ── Writing ────────────────────────────────────────────────────────────────────


def test_a_position_artifact_declares_its_own_format_and_carries_band_counts(tmp_path):
    document = json.loads(
        build_artifact_document(queue_metadata(), COHORTS, bands=BANDS)
    )
    assert document["artifact_format"] == QUEUE_ARTIFACT_FORMAT
    assert document["metadata"]["estimator"] == QUEUE_ESTIMATOR_ID
    assert document["metadata"]["features_used"] == list(QUEUE_FEATURES)
    assert document["bands"]["SL|GN|WL|1"] == {"CNF": 30, "WL": 5}
    assert document["cohorts"]["SL|GN|WL"] == {"CNF": 40, "WL": 60}


def test_a_frequency_artifact_is_written_unchanged_by_the_same_call(tmp_path):
    document = json.loads(build_artifact_document(frequency_metadata(), COHORTS))
    assert document["artifact_format"] == ARTIFACT_FORMAT
    assert "bands" not in document


def test_writing_is_deterministic_so_two_runs_can_be_diffed():
    first = build_artifact_document(queue_metadata(), COHORTS, bands=BANDS)
    second = build_artifact_document(queue_metadata(), COHORTS, bands=BANDS)
    assert first == second


def test_writing_a_band_table_onto_the_frequency_estimator_is_refused():
    with pytest.raises(ModelArtifactError, match="frequency-baseline declares no band"):
        write_artifact(
            Path("ignored.json"), frequency_metadata(), COHORTS, bands=BANDS
        )


def test_writing_a_position_artifact_without_band_cells_is_refused():
    """An artifact that claims to read positions but has none would answer flat."""
    with pytest.raises(ModelArtifactError, match="no band cells"):
        write_artifact(
            Path("ignored.json"), queue_metadata(), COHORTS, bands=None
        )


# ── Loading ────────────────────────────────────────────────────────────────────


def test_a_written_position_artifact_loads_back_with_both_tables(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    loaded = load_artifact(
        path,
        expected_version="queue_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.estimator == QUEUE_ESTIMATOR_ID
    assert loaded.cohorts == {("SL", "GN", "WL"): {"CNF": 40, "WL": 60}}
    assert loaded.bands == {
        ("SL", "GN", "WL", "1"): {"CNF": 30, "WL": 5},
        ("SL", "GN", "WL", "2-3"): {"CNF": 8, "WL": 12},
    }


def test_the_loaded_artifact_builds_the_estimator_it_declares():
    """Not whichever class the caller happened to import."""
    metadata = queue_metadata()
    artifact = LoadedArtifact(
        metadata=metadata,
        cohorts={("SL", "GN", "WL"): {"CNF": 40, "WL": 60}},
        bands=BANDS,
        path=Path("queue_v1.json"),
    )
    estimator = artifact.estimator()
    assert isinstance(estimator, CohortPositionBaseline)
    outcome = estimator.estimate(
        passenger_id="p-1",
        asof_status=parse_status("GNWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    assert outcome.p_cnf == pytest.approx(31 / 40)
    assert "band=1" in outcome.basis


def test_a_frequency_artifact_still_builds_the_frequency_baseline():
    artifact = LoadedArtifact(
        metadata=frequency_metadata(),
        cohorts=COHORTS,
        bands={},
        path=Path("base_v1.json"),
    )
    assert isinstance(artifact.estimator(), HistoricalFrequencyBaseline)


def test_the_loader_refuses_a_position_artifact_under_the_frequency_format(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["artifact_format"] = ARTIFACT_FORMAT
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="format"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_the_loader_refuses_a_frequency_artifact_under_the_position_format(tmp_path):
    path = write(tmp_path, frequency_metadata())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["artifact_format"] = QUEUE_ARTIFACT_FORMAT
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="format"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_an_unknown_estimator_is_refused_rather_than_guessed(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metadata"]["estimator"] = "catboost_baseline"
    document["artifact_format"] = ARTIFACT_FORMAT
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="Unknown estimator"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_position_artifact_that_declares_the_three_cohort_features_is_refused(tmp_path):
    """features_used is what a report credits the model with; three names means the other one."""
    path = write(tmp_path, queue_metadata(features_used=COHORT_FEATURES), bands=BANDS)
    with pytest.raises(ModelArtifactError, match="features_used"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_frequency_artifact_may_not_claim_the_position_feature(tmp_path):
    path = write(tmp_path, frequency_metadata(features_used=QUEUE_FEATURES))
    with pytest.raises(ModelArtifactError, match="features_used"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_position_artifact_with_no_band_block_is_refused(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["bands"]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="bands"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_frequency_artifact_carrying_band_cells_is_refused(tmp_path):
    """Two tables and one estimator: the loader cannot know which arithmetic was used."""
    path = write(tmp_path, frequency_metadata())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bands"] = {"SL|GN|WL|1": {"CNF": 1}}
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="band cells"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_malformed_band_cell_is_refused_at_load_not_smoothed(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bands"]["SL|GN|WL|4-7"] = {"CONFIRMED": 4}
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="unusable band"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_a_three_part_band_key_is_refused_because_it_is_a_cohort_not_a_band(tmp_path):
    path = write(tmp_path, queue_metadata(), bands=BANDS)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bands"]["SL|GN|WL"] = {"CNF": 4, "WL": 1}
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="four-part"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_the_cohort_status_rule_is_still_required_of_the_new_estimator(tmp_path):
    """A second model does not relax the as-of contract from ADR-0013."""
    path = write(
        tmp_path,
        queue_metadata(cohort_semantics="initial_status_v0"),
        bands=BANDS,
    )
    with pytest.raises(ModelArtifactError, match="cohort_semantics"):
        load_artifact(
            path,
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
            max_bytes=1_000_000,
        )


def test_the_promotion_and_approval_gates_are_estimator_agnostic(tmp_path):
    path = write(tmp_path, queue_metadata(is_synthetic=True), bands=BANDS)
    loaded = load_artifact(
        path,
        expected_version="queue_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.promotion == "candidate"
    assert loaded.metadata.is_synthetic is True
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["metadata"]["estimator"] == QUEUE_ESTIMATOR_ID
    with pytest.raises(ModelArtifactError, match="promotion"):
        metadata_from_mapping(
            {**document["metadata"], "promotion": ""},
            expected_version="queue_v1",
            expected_target="final_chart_cnf",
        )


def test_metadata_helpers_default_bands_to_an_empty_table():
    """A frozen dataclass with a dict field must not share one mutable default."""
    metadata = frequency_metadata()
    assert metadata.estimator == ESTIMATOR_HISTORICAL_FREQUENCY
    assert LoadedArtifact(
        metadata=metadata, cohorts=COHORTS, bands={}, path=Path("x.json")
    ).bands == {}


def test_the_registry_serves_the_position_model_from_a_promoted_artifact(tmp_path):
    """The dispatch happens where the artifact is resolved, not at the request."""
    from railconfirm.inference.registry import ModelRegistry

    write(tmp_path, queue_metadata(promotion=PROMOTION_APPROVED), bands=BANDS)
    registry = ModelRegistry(models_dir=tmp_path, active_version="queue_v1")
    estimator, resolution = registry.estimator(
        PredictionTarget.FINAL_CHART_CNF, HistoricalFrequencyBaseline()
    )
    assert resolution.is_ready is True
    assert isinstance(estimator, CohortPositionBaseline)

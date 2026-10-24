"""Tests for safe model artifact resolution, validation and promotion.

Every fixture here is synthetic and self-declared as such; it exercises the trust
boundary, not railway behaviour.
"""

import json
from pathlib import Path

import pytest

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.domain.prediction import AbstentionReason, PredictionTarget
from railconfirm.domain.status import parse_status
from railconfirm.inference.artifacts import (
    build_artifact_document,
    load_artifact,
)
from railconfirm.inference.baseline import HistoricalFrequencyBaseline
from railconfirm.inference.calibration import CalibrationSpec
from railconfirm.inference.registry import ArtifactStatus, ModelRegistry
from tests.support.artifacts import (
    COHORTS,
)
from tests.support.artifacts import (
    artifact_metadata as metadata,
)
from tests.support.artifacts import (
    registry_for as registry,
)
from tests.support.artifacts import (
    write_fixture_artifact as write,
)

CALIBRATION_BLOCK = {
    "method": "platt_logistic_v1",
    "target": "final_chart_cnf",
    "event_classes": ["CNF"],
    "slope": 1.234,
    "intercept": -0.432,
    "fitted_partition": "validation",
    "fitted_rows": 120,
    "fitted_from": "2026-04-01",
    "fitted_to": "2026-04-12",
}

# ── Promotion and absence ──────────────────────────────────────────────────────


def test_nothing_is_active_by_default(tmp_path):
    """The registry must not activate a file that merely appeared."""
    write(tmp_path)
    resolution = ModelRegistry(models_dir=tmp_path, active_version="no_model_v0").resolve(
        PredictionTarget.FINAL_CHART_CNF
    )
    assert resolution.status is ArtifactStatus.NO_ACTIVE_VERSION
    assert resolution.abstention_reason is AbstentionReason.NO_TRAINED_MODEL


def test_missing_artifact_file_is_visible(tmp_path):
    resolution = registry(tmp_path, "absent_v1").resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.ARTIFACT_MISSING
    assert "absent_v1" in resolution.detail


@pytest.mark.parametrize("promotion", ["candidate", "under_review", "rejected"])
def test_unpromoted_artifact_never_serves(tmp_path, promotion):
    write(tmp_path, promotion=promotion)
    resolution = registry(tmp_path).resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.NOT_PROMOTED
    assert promotion in resolution.detail


@pytest.mark.parametrize(
    "overrides",
    [
        {"data_approval_status": "quarantined"},
        {"data_approval_status": "candidate"},
        {"data_approval_status": "approved", "is_synthetic": True},
    ],
)
def test_artifact_fitted_from_unapproved_data_never_serves(tmp_path, overrides):
    """A trained artifact is still unusable if its training data is not approved."""
    write(tmp_path, **overrides)
    resolution = registry(tmp_path).resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.DATA_NOT_APPROVED
    assert resolution.abstention_reason is AbstentionReason.NO_APPROVED_DATA


def test_ready_artifact_serves_and_reports_its_version(tmp_path):
    write(tmp_path)
    resolution = registry(tmp_path).resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.READY
    assert resolution.is_ready
    assert resolution.artifact is not None
    assert resolution.artifact.metadata.version == "fixture_v1"


def test_ready_artifact_estimator_produces_estimates(tmp_path):
    write(tmp_path)
    fallback = HistoricalFrequencyBaseline()
    estimator, resolution = registry(tmp_path).estimator(
        PredictionTarget.FINAL_CHART_CNF, fallback=fallback
    )
    assert resolution.is_ready
    assert estimator is not fallback
    outcome = estimator.estimate("p-1", parse_status("GNWL/9"), "SL", "GN")
    assert outcome.is_supported()
    assert "SL/GN/WL" in outcome.basis
    assert outcome.p_cnf == pytest.approx(71 / 110)


def test_estimator_falls_back_when_not_ready(tmp_path):
    fallback = HistoricalFrequencyBaseline()
    estimator, resolution = registry(tmp_path, "absent_v1").estimator(
        PredictionTarget.FINAL_CHART_CNF, fallback=fallback
    )
    assert estimator is fallback
    assert not resolution.is_ready


# ── Artifact validation ────────────────────────────────────────────────────────


def test_junk_file_is_not_a_model(tmp_path):
    (tmp_path / "junk_v1.json").write_bytes(b"not json at all {{{")
    resolution = registry(tmp_path, "junk_v1").resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.ARTIFACT_INVALID
    assert resolution.abstention_reason is AbstentionReason.MODEL_ARTIFACT_INVALID


def test_pickle_artifact_is_not_loaded(tmp_path):
    """Regression: the registry trusted any existing ``<version>.pkl``.

    Pickle executes code on load, so an artifact format that can contain objects
    is not acceptable even when the file is well-formed.
    """
    (tmp_path / "evil_v1.pkl").write_bytes(b"cos\nsystem\n(S'echo'\ntR.")
    resolution = registry(tmp_path, "evil_v1").resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.ARTIFACT_MISSING
    assert not (tmp_path / "evil_v1.json").exists()


def test_oversized_artifact_is_refused_before_reading(tmp_path):
    write(tmp_path)
    path = tmp_path / "fixture_v1.json"
    oversized = json.loads(path.read_text(encoding="utf-8"))
    # Pad with a long but valid notes field to exceed a tiny byte limit.
    oversized["metadata"]["notes"] = "x" * 4096
    path.write_text(json.dumps(oversized), encoding="utf-8")

    resolver = ModelRegistry(
        models_dir=tmp_path, active_version="fixture_v1", max_artifact_bytes=64
    )
    resolution = resolver.resolve(PredictionTarget.FINAL_CHART_CNF)
    assert resolution.status is ArtifactStatus.ARTIFACT_INVALID
    assert "bytes" in resolution.detail


@pytest.mark.parametrize(
    "mutate,expected_fragment",
    [
        ({"artifact_format": "something/else"}, "declares format"),
        ({"metadata": None}, "must be a JSON object"),
        ({"cohorts": {}}, "non-empty object"),
        ({"cohorts": {"SL|GN": {"CNF": 1}}}, "three non-empty parts"),
        ({"cohorts": {"SL|GN|WL": {"CONFIRMED": 1}}}, "outside the defined outcome space"),
        ({"cohorts": {"SL|GN|WL": {"CNF": -3, "RAC": 1}}}, "negative count"),
    ],
)
def test_document_level_defects_are_rejected(tmp_path, mutate, expected_fragment):
    write(tmp_path)
    path = tmp_path / "fixture_v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(mutate)
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ModelArtifactError, match=expected_fragment):
        load_artifact(
            path,
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_an_unknown_estimator_is_refused_at_write_and_at_load(tmp_path):
    """Neither end may invent an estimator: a payload must name one this build can run.

    The write and the load are asserted separately on purpose. Refusing to write such a
    file is not the same fact as refusing to read one that arrived by another route.
    """
    with pytest.raises(ModelArtifactError, match="unknown estimator"):
        write(tmp_path, estimator="gradient_boosting")

    write(tmp_path)
    path = tmp_path / "fixture_v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metadata"]["estimator"] = "gradient_boosting"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="Unknown estimator"):
        load_artifact(
            path,
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


@pytest.mark.parametrize(
    "field,value,expected_fragment",
    [
        ("version", "other_v9", "declares version"),
        ("target", "final_chart_cnf_or_rac", "fitted for target"),
        ("dataset_sha256", "xyz", "64 lowercase hexadecimal"),
        ("outcome_classes", ["CNF", "RAC", "WL", "OTHER", "CANCELLED"], "must be exactly"),
        ("outcome_classes", ["CNF"], "must be exactly"),
        ("min_sample_threshold", 0, "positive integer"),
        ("min_sample_threshold", "10", "positive integer"),
        ("laplace_alpha", 0.0, "positive finite"),
        ("laplace_alpha", float("nan"), "positive finite"),
        ("limitations", [], "non-empty list"),
        ("calibrated", True, "must carry the calibration block"),
        ("trained_from", "2026-07-01", "reversed"),
        ("trained_to", "not-a-date", "ISO-8601 date"),
        ("feature_schema_version", "   ", "non-empty string"),
        ("promotion", "   ", "non-empty string"),
        ("cohort_semantics", "initial_status_v1", "answered from"),
        ("features_used", ["class_code", "quota_code"], "must be exactly"),
    ],
)
def test_metadata_defects_are_rejected(tmp_path, field, value, expected_fragment):
    write(tmp_path, **{field: value})
    with pytest.raises(ModelArtifactError, match=expected_fragment):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_an_artifact_keyed_by_another_status_rule_is_refused_not_reinterpreted(tmp_path):
    """Fit-on-booked-status, serve-on-observed-status was the original skew.

    A table whose cohorts came from a different column would answer this request
    with counts from a different population, so the load fails instead of the lookup
    silently missing."""
    write(tmp_path, cohort_semantics="initial_status_v1")
    with pytest.raises(ModelArtifactError, match="asof_status_v1") as exc:
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )
    assert "different population" in str(exc.value)


@pytest.mark.parametrize("dropped", ["features_used", "cohort_semantics"])
def test_an_artifact_that_declares_neither_of_its_cohort_rules_is_refused(tmp_path, dropped):
    write(tmp_path)
    path = tmp_path / "fixture_v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metadata"].pop(dropped)
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelArtifactError, match=dropped):
        load_artifact(
            path,
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_a_bare_calibrated_claim_is_refused(tmp_path):
    """A claim with nothing behind it is not evidence.

    Before the block existed, an artifact could assert `calibrated: true` and name a
    method, and nothing in the file said what the correction actually was — so a reader
    could not reproduce, review or even apply it."""
    write(tmp_path, calibrated=True, calibration_method="platt_on_validation_2026_q1")
    with pytest.raises(ModelArtifactError, match="must carry the calibration block"):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_a_declared_calibration_survives_the_round_trip(tmp_path):
    write(tmp_path, calibrated=True, calibration=CALIBRATION_BLOCK)
    loaded = load_artifact(
        tmp_path / "fixture_v1.json",
        expected_version="fixture_v1",
        expected_target=PredictionTarget.FINAL_CHART_CNF.value,
        max_bytes=1_000_000,
    )
    assert loaded.metadata.calibrated is True
    assert loaded.metadata.calibration_method == "platt_logistic_v1"
    assert loaded.metadata.calibration == CalibrationSpec(
        method="platt_logistic_v1",
        target="final_chart_cnf",
        event_classes=("CNF",),
        slope=1.234,
        intercept=-0.432,
        fitted_partition="validation",
        fitted_rows=120,
        fitted_from="2026-04-01",
        fitted_to="2026-04-12",
    )
    # A calibrated artifact no longer carries the "not calibrated" limitation the
    # engine adds for an uncorrected one.
    assert loaded.metadata.calibration is not None


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        ({"method": "isotonic"}, "Unknown calibration method"),
        ({"slope": -0.5}, "must not be negative"),
        ({"slope": float("inf")}, "must be finite"),
        ({"intercept": "1.0"}, "must be a number"),
        ({"fitted_rows": 0}, "0 fitted rows"),
        ({"event_classes": []}, "name the event classes"),
        ({"target": "final_chart_cnf_or_rac"}, "was fitted for target"),
        ({"fitted_partition": "  "}, "fitted_partition must be a non-empty string"),
        ({"fitted_partition": None}, "fitted_partition must be a non-empty string"),
    ],
)
def test_a_calibration_that_cannot_be_applied_is_refused(tmp_path, mutate, fragment):
    block = {**CALIBRATION_BLOCK, **mutate}
    write(tmp_path, calibrated=True, calibration=block)
    with pytest.raises(ModelArtifactError, match=fragment):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


@pytest.mark.parametrize("dropped", ["slope", "fitted_partition", "fitted_rows"])
def test_a_partial_calibration_block_is_refused(tmp_path, dropped):
    """Half a fitted layer is not a layer, so a missing field is not defaulted."""
    block = {key: value for key, value in CALIBRATION_BLOCK.items() if key != dropped}
    write(tmp_path, calibrated=True, calibration=block)
    with pytest.raises(ModelArtifactError, match=f"missing {dropped!r}"):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_a_calibration_block_on_an_uncalibrated_artifact_is_refused(tmp_path):
    write(tmp_path, calibrated=False, calibration=CALIBRATION_BLOCK)
    with pytest.raises(ModelArtifactError, match="declares calibrated=false"):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


def test_a_method_that_disagrees_with_the_block_is_refused(tmp_path):
    write(
        tmp_path,
        calibrated=True,
        calibration_method="something_else",
        calibration=CALIBRATION_BLOCK,
    )
    with pytest.raises(ModelArtifactError, match="disagrees with the"):
        load_artifact(
            tmp_path / "fixture_v1.json",
            expected_version="fixture_v1",
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )


@pytest.mark.parametrize("version", ["../secrets", "..\\..\\x", "a" * 65, "with space", ""])
def test_unsafe_active_version_names_are_rejected(version):
    with pytest.raises(ModelArtifactError, match="not a safe artifact identifier"):
        ModelRegistry(models_dir=Path("."), active_version=version).resolve(
            PredictionTarget.FINAL_CHART_CNF
        )


def test_artifact_round_trip_is_deterministic(tmp_path):
    first = build_artifact_document(metadata(), COHORTS)
    second = build_artifact_document(metadata(), dict(reversed(list(COHORTS.items()))))
    assert first == second


def test_loaded_artifact_carries_provenance_into_the_estimator(tmp_path):
    write(tmp_path, dataset_id="approved-set-7", data_approval_status="approved")
    resolution = registry(tmp_path).resolve(PredictionTarget.FINAL_CHART_CNF)
    estimator = resolution.artifact.estimator()
    assert estimator.provenance is not None
    assert estimator.provenance.dataset_id == "approved-set-7"
    assert estimator.provenance.approved_for_estimation()
    assert estimator.min_sample_threshold == 10

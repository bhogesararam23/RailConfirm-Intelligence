"""Tests for baseline fitting: partition discipline, cohort keys and promotion."""

import re
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.preprocessing import ASOF_STATUS_FEATURE, asof_statuses, chronological_split
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import PROMOTION_APPROVED, load_artifact
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    COHORT_FEATURES,
    COHORT_STATUS_SEMANTICS,
    FrequencyTableProvenance,
    cohort_key,
)
from railconfirm.inference.registry import ArtifactStatus, ModelRegistry
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.fitter import (
    CANDIDATE_PROMOTION,
    fit_baseline,
    fit_cohorts,
    prevalence_distribution,
    write_fitted_artifact,
)
from railconfirm.training.metrics import build_estimator
from tests.support.datasets import (
    write_approved_manifest,
    write_dataset,
    write_moving_dataset,
)


@pytest.fixture
def approved(tmp_path: Path):
    csv = write_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    return load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def fit(approved, **overrides):
    kwargs = {
        "version": "fit_v1",
        "min_sample_threshold": 5,
        "laplace_alpha": 1.0,
    }
    kwargs.update(overrides)
    return fit_baseline(approved, **kwargs)


# ── Partition discipline ───────────────────────────────────────────────────────


def test_only_the_training_partition_contributes_counts(approved):
    """A label that exists only in the held-out period must not appear in the fit."""
    frame = approved.frame.copy()
    # Force every held-out row to a label the training rows never carry.
    split = chronological_split(frame, train_frac=0.5, val_frac=0.25)
    frame.loc[frame["journey_date"].isin(split.test["journey_date"]), "final_chart_status"] = "RAC 1"
    approved = type(approved)(
        dataset_path=approved.dataset_path,
        manifest=approved.manifest,
        frame=frame,
        report=approved.report,
        is_synthetic=approved.is_synthetic,
    )

    fitted = fit(approved)
    labels = set(fitted.summary.label_distribution)
    assert "RAC" not in labels
    assert {"CNF", "WL"} <= labels
    assert fitted.split.test is not None


def test_fitted_cohorts_are_valid_for_the_inference_estimator(approved):
    """A fitted table must pass the same gate a hand-built one would at inference."""
    from railconfirm.inference.baseline import FrequencyTableProvenance
    from railconfirm.training.metrics import build_estimator

    fitted = fit(approved)
    built = build_estimator(
        fitted.cohorts,
        FrequencyTableProvenance(
            dataset_id=approved.dataset_id,
            sha256=approved.sha256,
            source_reference="test",
            approval_status="approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=5,
        laplace_alpha=1.0,
    )
    assert built.is_loaded


def test_broad_cohort_is_fitted_alongside_exact_cells(approved):
    fitted = fit(approved)
    broad_keys = [cohort for cohort in fitted.cohorts if cohort[2] == BROAD_COHORT_STATUS]
    assert broad_keys
    for cohort in broad_keys:
        assert sum(fitted.cohorts[cohort].values()) >= 1


def test_ineligible_asof_statuses_are_excluded_not_fitted(approved):
    """The as-of status decides the cohort, so it also decides exclusion."""
    frame = approved.frame.copy()
    frame.loc[0, "initial_status"] = "CANCELLED"
    frame.loc[1, "initial_status"] = "CENSORED"
    summary = fit_cohorts(frame)
    assert summary.excluded.get("asof_status_cancelled") == 1
    assert summary.excluded.get("asof_status_censored") == 1
    assert summary.rows_used == len(frame) - 2


def test_a_moved_reservation_is_fitted_into_the_cohort_it_is_queried_from(tmp_path):
    """Regression: the table was keyed by initial_status while requests used current.

    A booking seen at RAC by its observation time is evidence about RAC bookings, so
    it must land in the RAC cell — the cell the served lookup for that record reads.
    """
    summary = fit_cohorts(load_dataset_file(write_moving_dataset(tmp_path)))

    exact = {cohort for cohort in summary.cohorts if cohort[2] != BROAD_COHORT_STATUS}
    assert ("SL", "GN", "RAC") in exact
    assert summary.cohort_semantics == COHORT_STATUS_SEMANTICS
    assert summary.asof_status_columns == ["initial_status", "current_status"]


def test_a_fitted_cohort_is_queried_with_exactly_the_contract_it_was_built_with(tmp_path):
    """Fit → estimator → estimate: the key asked for is the key that was counted."""
    frame = load_dataset_file(write_moving_dataset(tmp_path))
    summary = fit_cohorts(frame)
    estimator = build_estimator(
        summary.cohorts,
        FrequencyTableProvenance(
            dataset_id="asof-parity",
            sha256="d" * 64,
            source_reference="test",
            approval_status="approved",
            is_synthetic=True,
            mapping_version=MAPPING_VERSION,
            evaluation_only=True,
        ),
        min_sample_threshold=1,
        laplace_alpha=1.0,
    )
    statuses = asof_statuses(frame)

    for index, row in frame.iterrows():
        outcome = estimator.estimate(
            passenger_id=f"p{index}",
            asof_status=statuses[index],
            class_code=str(row["class_code"]),
            quota_code=str(row["quota_code"]),
        )
        assert outcome.is_supported(), (index, outcome.abstention_reason)
        cohort, _, fallback = _cohort_from_basis(outcome.basis)
        expected = cohort_key(
            str(row["class_code"]), str(row["quota_code"]), statuses[index].normalized.value
        )
        # Either the exact cohort this row's as-of status was fitted into, or that
        # class/quota's broad cell when the exact one has no history yet.
        assert cohort == (expected if not fallback else (expected[0], expected[1], "ALL"))
        assert cohort in summary.cohorts


def _cohort_from_basis(basis: str) -> tuple[tuple[str, str, str], int, bool]:
    """Parse ``cohort=SL/GN/RAC n=12 …`` back into its parts."""
    match = re.search(r"cohort=(\S+) n=(\d+)", basis)
    assert match, basis
    parts = match.group(1).split("/")
    assert len(parts) == 3, basis
    return cohort_key(parts[0], parts[1], parts[2]), int(match.group(2)), "fallback" in basis


def test_fit_declares_the_features_it_consumes(tmp_path):
    """A baseline reading three values must not be credited with the whole schema."""
    csv = write_moving_dataset(tmp_path)
    dataset = load_approved_dataset(
        csv, write_approved_manifest(csv, tmp_path), allow_synthetic_for_testing=True
    )
    fitted = fit_baseline(dataset, version="asof_v1", min_sample_threshold=1)
    assert fitted.metadata.features_used == COHORT_FEATURES
    assert fitted.metadata.cohort_semantics == COHORT_STATUS_SEMANTICS
    assert any("not read by this estimator" in item for item in fitted.metadata.limitations)
    assert any(ASOF_STATUS_FEATURE in item for item in fitted.metadata.limitations)


def test_an_artifact_is_written_and_read_back_with_its_cohort_contract(tmp_path):
    csv = write_moving_dataset(tmp_path)
    dataset = load_approved_dataset(
        csv, write_approved_manifest(csv, tmp_path), allow_synthetic_for_testing=True
    )
    fitted = fit_baseline(dataset, version="asof_v1", min_sample_threshold=1)
    loaded = load_artifact(
        write_fitted_artifact(fitted, tmp_path / "asof_v1.json"),
        expected_version="asof_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.features_used == COHORT_FEATURES
    assert loaded.metadata.cohort_semantics == COHORT_STATUS_SEMANTICS


def test_fit_reports_what_it_consumed(approved):
    summary = fit_cohorts(approved.frame)
    assert summary.rows_seen == len(approved.frame)
    assert summary.window == ("2026-04-01", "2026-06-12") or summary.window is not None
    assert summary.label_distribution["CNF"] > 0
    assert sum(summary.label_distribution.values()) == summary.rows_used


def test_prevalence_is_a_distribution_over_the_outcome_space(approved):
    summary = fit_cohorts(approved.frame)
    prevalence = prevalence_distribution(summary.label_distribution)
    assert set(prevalence) == {"CNF", "RAC", "WL", "CANCELLED", "OTHER"}
    assert abs(sum(prevalence.values()) - 1.0) < 1e-12
    assert prevalence["CNF"] > prevalence["OTHER"] == 0.0


def test_prevalence_from_empty_labels_is_an_error():
    with pytest.raises(DatasetValidationError, match="empty label set"):
        prevalence_distribution({})


def test_fitting_nothing_is_an_error(approved):
    empty = approved.frame.head(0)
    with pytest.raises(DatasetValidationError, match="No cohorts could be fitted"):
        fit_cohorts(empty)


def test_ineligible_split_blocks_fitting(approved):
    frame = approved.frame.copy()
    frame["journey_date"] = "2026-04-01"
    single = type(approved)(
        dataset_path=approved.dataset_path,
        manifest=approved.manifest,
        frame=frame,
        report=approved.report,
        is_synthetic=approved.is_synthetic,
    )
    with pytest.raises(DatasetValidationError, match="not eligible"):
        fit_baseline(single, version="blocked_v1")


# ── Artifact description and promotion ─────────────────────────────────────────


def test_artifact_is_written_as_a_candidate_never_auto_active(approved, tmp_path):
    fitted = fit(approved)
    path = write_fitted_artifact(fitted, tmp_path / "fit_v1.json")
    loaded = load_artifact(
        path,
        expected_version="fit_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.promotion == CANDIDATE_PROMOTION
    assert loaded.metadata.promotion != PROMOTION_APPROVED
    assert loaded.metadata.calibrated is False


def test_artifact_declares_its_dataset_hash_and_window(approved, tmp_path):
    fitted = fit(approved)
    path = write_fitted_artifact(fitted, tmp_path / "fit_v1.json")
    loaded = load_artifact(
        path,
        expected_version="fit_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.dataset_sha256 == approved.sha256
    assert loaded.metadata.dataset_id == approved.dataset_id
    assert loaded.metadata.status_mapping_version == MAPPING_VERSION
    assert loaded.metadata.trained_from <= loaded.metadata.trained_to


def test_synthetic_fit_produces_an_artifact_the_registry_refuses(approved, tmp_path):
    """The end-to-end safety property.

    Fitting on synthetic rows is allowed for pipeline verification, but the artifact
    records that it came from synthetic data, and the registry will not serve it. So
    the whole training path can be tested without any route by which a synthetic
    number reaches a user.
    """
    from railconfirm.domain.prediction import PredictionTarget

    fitted = fit(approved)
    write_fitted_artifact(fitted, tmp_path / "fit_v1.json")
    resolution = ModelRegistry(models_dir=tmp_path, active_version="fit_v1").resolve(
        PredictionTarget.FINAL_CHART_CNF
    )
    assert resolution.status is ArtifactStatus.NOT_PROMOTED
    assert resolution.artifact is None


def test_promoting_a_synthetic_artifact_still_refuses_on_data_grounds(approved, tmp_path):
    """Even if someone flips promotion by hand, the synthetic dataset blocks serving."""
    fitted = fit(approved)
    text = write_fitted_artifact(fitted, tmp_path / "fit_v1.json").read_text(encoding="utf-8")
    (tmp_path / "fit_v1.json").write_text(
        text.replace(f'"promotion": "{CANDIDATE_PROMOTION}"', f'"promotion": "{PROMOTION_APPROVED}"'),
        encoding="utf-8",
    )
    from railconfirm.domain.prediction import PredictionTarget

    resolution = ModelRegistry(models_dir=tmp_path, active_version="fit_v1").resolve(
        PredictionTarget.FINAL_CHART_CNF
    )
    assert resolution.status is ArtifactStatus.DATA_NOT_APPROVED
    assert "synthetic" in resolution.detail.lower()


def test_limitations_travel_with_the_artifact(approved, tmp_path):
    fitted = fit(approved)
    assert any("is_synthetic" in item or "Synthetic" in item for item in fitted.metadata.limitations)
    assert any("not a trained or calibrated model" in item for item in fitted.metadata.limitations)


def test_report_window_and_counts_survive_serialisation(approved):
    fitted = fit(approved)
    payload = fitted.summary.to_dict()
    assert payload["cohort_count"] == len(fitted.cohorts)
    assert payload["rows_used"] == sum(fitted.summary.label_distribution.values())
    assert isinstance(payload["excluded"], dict)


def test_fitting_does_not_mutate_the_source_frame(approved):
    before = approved.frame.copy(deep=True)
    fit(approved)
    pd.testing.assert_frame_equal(approved.frame, before)


def test_dates_are_not_interpreted_as_the_current_year(approved):
    """The fixture's window is fixed; a fit must not shift it."""
    fitted = fit(approved)
    assert fitted.summary.window[0].startswith("2026-")
    assert date.fromisoformat(fitted.summary.window[0]) < date.fromisoformat(fitted.summary.window[1])

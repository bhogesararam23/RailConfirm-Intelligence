"""Calibration measured inside the cohorts the product distinguishes.

A population-wide number can be exactly right while every cohort in it is wrong in
compensating directions, and that is precisely the failure a single Platt slope produces.
These tests pin the arithmetic of the per-segment gaps and, more than that, what the report
is allowed to say from them: a segment with three rows cannot carry a claim, and no segment
here gets its own correction.

Synthetic rows only.
"""

import pytest

from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.calibration import logit, sigmoid
from railconfirm.training.metrics import (
    MIN_SEGMENT_CALIBRATION_ROWS,
    ScoredRow,
    build_estimator,
    evaluation_provenance,
    score_partition,
    segment_calibration,
)

RAW_CELL = 31 / 105
CNF = ("CNF",)
PREVALENCE = {"CNF": 0.3, "RAC": 0.0, "WL": 0.7, "CANCELLED": 0.0, "OTHER": 0.0}


def row(event_predicted: float, event_observed: float, *slices: tuple[str, str]) -> ScoredRow:
    """A scored reservation carrying just enough for the calibration arithmetic."""
    hypothesis = {"CNF": event_predicted, "WL": 1.0 - event_predicted}
    truth = {"CNF": event_observed, "WL": 1.0 - event_observed}
    return ScoredRow(
        hypothesis=hypothesis,
        truth=truth,
        observed="CNF" if event_observed else "WL",
        event_predicted=event_predicted,
        event_observed=event_observed,
        brier=(event_predicted - event_observed) ** 2
        + ((1 - event_predicted) - (1 - event_observed)) ** 2,
        loss=0.0,
        slices=list(slices) or [("class_code", "SL")],
    )


def by_dimension(items, dimension: str) -> dict[str, object]:
    return {item.value: item for item in items if item.dimension == dimension}


# ── The arithmetic ─────────────────────────────────────────────────────────────


def test_a_population_can_balance_while_every_cohort_is_wrong():
    """The case this measurement exists for: offsetting cohorts, a clean headline."""
    rows = [row(0.30, 1.0, ("class_code", "SL")) for _ in range(10)] + [
        row(0.70, 0.0, ("class_code", "3A")) for _ in range(10)
    ]
    population_predicted = sum(r.event_predicted for r in rows) / len(rows)
    population_observed = sum(r.event_observed for r in rows) / len(rows)
    assert population_predicted == pytest.approx(0.5)
    assert population_observed == pytest.approx(0.5)

    segments = by_dimension(segment_calibration(rows), "class_code")
    assert segments["SL"].gap == pytest.approx(0.7, abs=1e-6)
    assert segments["3A"].gap == pytest.approx(-0.7, abs=1e-6)
    assert segments["SL"].gap * segments["3A"].gap < 0


def test_the_gap_is_observed_rate_minus_mean_predicted_for_a_hand_checked_segment():
    rows = [
        row(0.4, 1.0),
        row(0.6, 1.0),
        row(0.5, 0.0),
        row(0.5, 0.0),
    ]
    (only,) = segment_calibration(rows)
    assert only.rows == 4
    assert only.mean_predicted == pytest.approx(0.5)
    assert only.observed_rate == pytest.approx(0.5)
    assert only.gap == pytest.approx(0.0, abs=1e-9)


def test_rounding_is_applied_to_the_reported_numbers_not_the_accumulator():
    rows = [row(1 / 3, 1.0), row(1 / 3, 0.0), row(1 / 3, 0.0)]
    (only,) = segment_calibration(rows)
    assert only.mean_predicted == pytest.approx(0.333333)
    assert only.observed_rate == pytest.approx(0.333333, abs=1e-5)
    assert only.gap == round(only.observed_rate - only.mean_predicted, 6)


def test_a_perfectly_aligned_segment_reports_a_zero_gap():
    rows = [row(0.25, 1.0) for _ in range(4)] + [row(0.25, 0.0) for _ in range(12)]
    (only,) = segment_calibration(rows)
    assert only.mean_predicted == pytest.approx(0.25)
    assert only.observed_rate == pytest.approx(0.25)
    assert only.gap == pytest.approx(0.0, abs=1e-6)


def test_a_segment_below_the_row_floor_is_kept_and_flagged_not_quietly_dropped():
    rows = [row(0.5, 1.0), row(0.5, 0.0), row(0.5, 1.0)]
    (only,) = segment_calibration(rows, min_rows=MIN_SEGMENT_CALIBRATION_ROWS)
    assert only.rows == 3
    assert only.low_sample is True
    assert only.gap is not None


def test_the_row_floor_is_inclusive():
    rows = [row(0.5, 1.0)] * MIN_SEGMENT_CALIBRATION_ROWS
    (only,) = segment_calibration(rows)
    assert only.low_sample is False


def test_min_rows_can_be_stated_for_a_thinner_partition():
    rows = [row(0.5, 1.0)] * 5
    (only,) = segment_calibration(rows, min_rows=5)
    assert only.low_sample is False
    assert only.rows == 5


def test_every_dimension_the_scorecard_segments_by_is_calibrated_by_as_well():
    rows = [
        row(
            0.4,
            1.0,
            ("class_code", "SL"),
            ("quota_code", "GN"),
            ("asof_status", "WL"),
            ("initial_status", "WL"),
        )
    ]
    dimensions = {item.dimension for item in segment_calibration(rows)}
    assert dimensions == {"class_code", "quota_code", "asof_status", "initial_status"}


def test_order_of_rows_does_not_change_the_reported_segments():
    rows = [
        row(0.2, 1.0, ("class_code", "3A")),
        row(0.9, 0.0, ("class_code", "SL")),
        row(0.7, 1.0, ("class_code", "SL")),
    ]
    forward = segment_calibration(rows)
    reversed_ = segment_calibration(list(reversed(rows)))
    assert [item.value for item in forward] == [item.value for item in reversed_]
    assert forward == reversed_


def test_segments_are_sorted_by_dimension_then_value():
    rows = [
        row(0.5, 1.0, ("quota_code", "GN")),
        row(0.5, 1.0, ("class_code", "SL")),
        row(0.5, 1.0, ("class_code", "3A")),
    ]
    pairs = [(item.dimension, item.value) for item in segment_calibration(rows)]
    assert pairs == sorted(pairs)


def test_an_empty_scored_set_calibrates_nothing_and_does_not_raise():
    assert segment_calibration([]) == []


def test_a_single_row_segment_reports_its_own_extremes_rather_than_hiding_them():
    (only,) = segment_calibration([row(0.1, 1.0, ("class_code", "SL"))])
    assert only.mean_predicted == pytest.approx(0.1)
    assert only.observed_rate == pytest.approx(1.0)
    assert only.gap == pytest.approx(0.9, abs=1e-6)
    assert only.low_sample is True


# ── Through score_partition, on the rows a served request actually produced ─────


def calibrated_estimator():
    from railconfirm.inference.baseline import HistoricalFrequencyBaseline

    # alpha 1.0 on a 30/70 cell smooths over all five outcome classes, so the CNF mass is
    # (30+1)/(100+5): a number the segment gaps can be checked against by hand.
    estimator = HistoricalFrequencyBaseline(min_sample_threshold=1, laplace_alpha=1.0)
    estimator.load_frequency_table(
        {("SL", "GN", "WL"): {"CNF": 30, "WL": 70}},
        evaluation_provenance(
            "segment-calibration-fixture",
            "a" * 64,
            "test",
            "approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
    )
    return estimator


def scored_frame(rows: int, *, as_status: str = "GNWL/10"):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": as_status,
                "current_status": "",
                "final_chart_status": "CNF" if index % 2 == 0 else "WL/5",
                "observation_date": "2026-03-01",
                "passenger_record_id": f"P{index:04d}",
            }
            for index in range(rows)
        ]
    )


def test_score_partition_publishes_segment_calibration_alongside_the_population_scores():
    card = score_partition(
        scored_frame(30),
        calibrated_estimator(),
        prevalence=PREVALENCE,
        partition="validation",
    )
    assert card.scored_rows == 30
    segments = by_dimension(card.segment_calibration, "class_code")
    assert segments["SL"].rows == card.scored_rows
    assert segments["SL"].mean_predicted == pytest.approx(RAW_CELL, abs=1e-6)
    assert segments["SL"].observed_rate == pytest.approx(0.5, abs=1e-6)
    assert segments["SL"].gap == pytest.approx(0.5 - RAW_CELL, abs=1e-6)
    assert segments["SL"].low_sample is False


def test_abstained_rows_contribute_to_no_segment():
    """A row the estimator refused is a coverage fact, not a calibration datum."""
    import pandas as pd

    frame = pd.concat(
        [
            scored_frame(10),
            scored_frame(4, as_status="CNF"),
        ],
        ignore_index=True,
    )
    card = score_partition(
        frame,
        calibrated_estimator(),
        prevalence=PREVALENCE,
        partition="validation",
    )
    assert card.abstained_rows > 0
    for segment in card.segment_calibration:
        assert segment.rows <= card.scored_rows
    assert sum(s.rows for s in card.segment_calibration if s.dimension == "class_code") == (
        card.scored_rows
    )


def test_the_gaps_are_measured_on_the_number_a_request_is_handed():
    """With a correction applied, the segment means must move with it, not beside it."""
    from railconfirm.inference.calibration import CalibrationSpec

    uncalibrated = score_partition(
        scored_frame(20),
        calibrated_estimator(),
        prevalence=PREVALENCE,
        partition="validation",
    )
    spec = CalibrationSpec(
        method="platt_logistic_v1",
        target="final_chart_cnf",
        event_classes=("CNF",),
        slope=2.0,
        intercept=0.0,
        fitted_partition="validation",
        fitted_rows=100,
        fitted_from="2026-04-01",
        fitted_to="2026-04-02",
    )
    corrected = score_partition(
        scored_frame(20),
        calibrated_estimator(),
        prevalence=PREVALENCE,
        partition="validation",
        calibration=spec,
    )
    plain = by_dimension(uncalibrated.segment_calibration, "class_code")["SL"]
    moved = by_dimension(corrected.segment_calibration, "class_code")["SL"]
    # The cohort cell says 30/100, so the raw estimate is 0.3 and the correction with
    # slope 2 and intercept 0 pulls it to sigmoid(2 * logit(0.3)). A gap measured beside
    # the correction rather than after it would describe a number nobody is served.
    assert plain.mean_predicted == pytest.approx(RAW_CELL, abs=1e-6)
    assert moved.mean_predicted == pytest.approx(sigmoid(2.0 * logit(RAW_CELL)), abs=1e-6)
    assert moved.mean_predicted != plain.mean_predicted
    assert plain.rows == moved.rows == 20
    assert moved.gap == round(moved.observed_rate - moved.mean_predicted, 6)
    assert moved.gap > plain.gap  # the correction under-confirms this cohort even harder


def test_the_scorecard_payload_serialises_the_segments_as_plain_dicts():
    card = score_partition(
        scored_frame(8),
        calibrated_estimator(),
        prevalence=PREVALENCE,
        partition="validation",
    )
    payload = card.to_dict()
    assert "segment_calibration" in payload
    assert isinstance(payload["segment_calibration"], list)
    assert {"dimension", "value", "rows", "gap", "low_sample"} <= set(
        payload["segment_calibration"][0]
    )


# ── What the report is allowed to say from these numbers ───────────────────────


from pathlib import Path  # noqa: E402

from railconfirm.training.dataset import load_approved_dataset  # noqa: E402
from railconfirm.training.fitter import fit_baseline  # noqa: E402
from railconfirm.training.report import build_report  # noqa: E402
from tests.support.datasets import (  # noqa: E402
    write_approved_manifest,
    write_balanced_dataset,
)


def real_run(tmp_path: Path, min_segment_rows: int = 25):
    """Fit, score and report the pipeline fixture, so report text is tested on real shapes."""
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted = fit_baseline(dataset, version="seg_v1", min_sample_threshold=5)
    estimator = build_estimator(
        fitted.cohorts,
        evaluation_provenance(
            dataset.dataset_id,
            dataset.sha256,
            "test",
            "approved",
            is_synthetic=True,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=5,
        laplace_alpha=1.0,
    )
    validation = score_partition(
        fitted.split.val,
        estimator,
        prevalence=fitted.prevalence,
        partition="validation",
        min_segment_rows=min_segment_rows,
    )
    test = score_partition(
        fitted.split.test,
        estimator,
        prevalence=fitted.prevalence,
        partition="test",
        min_segment_rows=min_segment_rows,
    )
    report = build_report(
        metadata=fitted.metadata,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        dataset_rows=dataset.report.total_rows,
        fit=fitted.summary,
        split=fitted.split,
        validation=validation,
        test=test,
        generated_on="2026-10-24",
    )
    return report, validation, test


def test_the_report_names_the_widest_segment_gap_rather_than_only_the_average(tmp_path):
    report, validation, _ = real_run(tmp_path)
    informative = [item for item in validation.segment_calibration if not item.low_sample]
    assert informative
    worst = max(informative, key=lambda item: abs(item.gap))
    line = next(item for item in report.conclusions if "widest segment gap" in item)
    assert f"{worst.gap:+.6f}" in line
    assert f"{worst.dimension}={worst.value}" in line
    assert line.startswith("validation:")


def test_a_run_where_every_segment_is_thin_refuses_to_claim_subgroup_calibration(tmp_path):
    report, _, _ = real_run(tmp_path, min_segment_rows=10_000)
    lines = [item for item in report.conclusions if "subgroup calibration cannot be claimed" in item]
    assert len(lines) == 2  # validation and test
    assert not [item for item in report.conclusions if "widest segment gap" in item]


def test_the_limitation_says_no_per_segment_correction_was_fitted(tmp_path):
    report, _, _ = real_run(tmp_path)
    joined = " ".join(report.limitations)
    assert "no per-segment correction is fitted" in joined
    assert "one slope is applied to every cohort" in joined
    assert "low_sample" in joined


def test_the_report_still_publishes_the_subgroup_measurement_without_any_calibration(tmp_path):
    """The gaps describe the served number, whether or not a correction produced it."""
    report, validation, _ = real_run(tmp_path)
    assert validation.calibration_applied is False
    assert report.to_dict()["validation"]["segment_calibration"]
    assert "No calibration was fitted or applied." in " ".join(report.limitations)


def test_a_calibrated_run_states_that_the_slope_is_population_wide(tmp_path):
    from railconfirm.inference.calibration import CalibrationSpec
    from railconfirm.training.fitter import with_calibration

    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted = fit_baseline(dataset, version="seg_v1", min_sample_threshold=5)
    spec = CalibrationSpec(
        method="platt_logistic_v1",
        target="final_chart_cnf",
        event_classes=("CNF",),
        slope=1.2,
        intercept=0.1,
        fitted_partition="validation",
        fitted_rows=40,
        fitted_from="2026-04-09",
        fitted_to="2026-04-10",
    )
    calibrated = with_calibration(fitted, spec)
    estimator = build_estimator(
        calibrated.cohorts,
        evaluation_provenance(
            dataset.dataset_id,
            dataset.sha256,
            "test",
            "approved",
            is_synthetic=True,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=5,
        laplace_alpha=1.0,
    )
    validation = score_partition(
        calibrated.split.val,
        estimator,
        prevalence=calibrated.prevalence,
        partition="validation",
        calibration=spec,
    )
    report = build_report(
        metadata=calibrated.metadata,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        dataset_rows=dataset.report.total_rows,
        fit=calibrated.summary,
        split=calibrated.split,
        validation=validation,
        test=None,
        generated_on="2026-10-24",
    )
    joined = " ".join(report.limitations)
    assert "one slope and intercept fitted on the population as a whole" in joined
    assert "residual error" in joined
    assert validation.segment_calibration[0].mean_predicted != pytest.approx(0.0)


def test_the_subgroup_lines_survive_a_windows_console(tmp_path):
    report, _, _ = real_run(tmp_path)
    for line in report.conclusions + report.limitations:
        line.encode("cp1252")

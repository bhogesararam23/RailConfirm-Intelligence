"""Fitting the calibration layer, and what it refuses to be fitted on.

Synthetic rows and hand-checkable pairs throughout: these tests establish that the
correction is identified from the validation partition only, that a layer which does not
help is not written into an artifact, and that the measured before/after numbers reach
the report instead of a flattering summary.
"""

import json
from pathlib import Path

import pytest

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import PROMOTION_APPROVED, load_artifact
from railconfirm.inference.calibration import (
    CalibrationSpec,
    calibrate_probability,
    logit,
    sigmoid,
)
from railconfirm.training.__main__ import main
from railconfirm.training.calibration import (
    calibration_improves,
    event_pairs,
    fit_and_measure,
    fit_platt,
)
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.fitter import fit_baseline, with_calibration, write_fitted_artifact
from railconfirm.training.metrics import ScoredRow
from railconfirm.training.report import build_report
from tests.support.datasets import write_approved_manifest, write_balanced_dataset


def pairs(count: int = 4, low: float = 0.2, high: float = 0.8) -> list[tuple[float, float]]:
    """Half the rows at each of two predicted probabilities, half of them positives."""
    return [(low, 1.0), (low, 0.0), (high, 1.0), (high, 0.0)][:count]


def many(rate_low: float, rate_high: float, *, size: int = 20) -> list[tuple[float, float]]:
    """20 rows at p=0.2 with `rate_low` observed and 20 at p=0.8 with `rate_high`."""
    positives_low = round(rate_low * size)
    positives_high = round(rate_high * size)
    return (
        [(0.2, 1.0)] * positives_low
        + [(0.2, 0.0)] * (size - positives_low)
        + [(0.8, 1.0)] * positives_high
        + [(0.8, 0.0)] * (size - positives_high)
    )


def fit(data, **overrides):
    kwargs = {"target": "final_chart_cnf", "partition": "validation", "min_rows": 2}
    kwargs.update(overrides)
    return fit_platt(data, **kwargs)


def scored(predicted: float, observed: float) -> ScoredRow:
    return ScoredRow(
        hypothesis={"CNF": predicted, "RAC": 0.0, "WL": 1 - predicted, "CANCELLED": 0.0, "OTHER": 0.0},
        truth={"CNF": observed, "RAC": 0.0, "WL": 1 - observed, "CANCELLED": 0.0, "OTHER": 0.0},
        observed="CNF" if observed > 0.5 else "WL",
        event_predicted=predicted,
        event_observed=observed,
        brier=(predicted - observed) ** 2 + ((1 - predicted) - (1 - observed)) ** 2,
        loss=0.0,
        slices=[("asof_status", "WL")],
    )


# ── What the fit does ──────────────────────────────────────────────────────────


def test_flat_evidence_fits_no_correction():
    """Equal observed rates at both predictions: the maximum-likelihood slope is zero.

    Hand check: with the same rate at p=0.2 and p=0.8 the likelihood is flat in the
    slope and maximised at 0, and the intercept sits at logit(0.5)=0.
    """
    spec = fit(pairs())
    assert spec.slope == pytest.approx(0.0, abs=1e-9)
    assert spec.intercept == pytest.approx(0.0, abs=1e-9)
    assert calibrate_probability(spec, 0.2) == pytest.approx(0.5)
    assert calibrate_probability(spec, 0.8) == pytest.approx(0.5)


def test_an_already_calibrated_table_is_left_alone():
    """When the observed rates match the predictions, the fitted slope is about one."""
    spec = fit(many(0.2, 0.8))
    assert spec.slope == pytest.approx(1.0, abs=0.25)
    assert calibrate_probability(spec, 0.2) == pytest.approx(0.2, abs=0.06)
    assert calibrate_probability(spec, 0.8) == pytest.approx(0.8, abs=0.06)


def test_systematic_overconfidence_is_pulled_toward_the_observed_rate():
    """Predictions of 0.8 that came true 40% of the time must move down."""
    spec = fit(many(0.1, 0.4))
    assert spec.slope > 0, "the observed rate still rises with the prediction"
    assert calibrate_probability(spec, 0.8) < 0.8
    assert calibrate_probability(spec, 0.2) < 0.2
    assert calibrate_probability(spec, 0.8) > calibrate_probability(spec, 0.2)
    assert calibrate_probability(spec, 0.5) == pytest.approx(
        sigmoid(spec.slope * logit(0.5) + spec.intercept)
    )


def test_the_fit_is_deterministic_in_row_order():
    data = many(0.1, 0.5)
    forward = fit(data)
    backward = fit(list(reversed(data)))
    assert forward.slope == pytest.approx(backward.slope, abs=1e-9)
    assert forward.intercept == pytest.approx(backward.intercept, abs=1e-9)


def test_the_spec_records_the_rows_and_period_it_came_from():
    spec = fit(pairs(), fitted_from="2026-04-01", fitted_to="2026-04-02")
    assert spec.fitted_partition == "validation"
    assert spec.fitted_rows == 4
    assert spec.fitted_from == "2026-04-01"
    assert spec.event_classes == ("CNF",)
    assert "4 validation rows" in spec.description


def test_event_pairs_reads_the_rows_that_were_scored():
    rows = [scored(0.6, 1.0), scored(0.4, 0.0)]
    assert event_pairs(rows) == [(0.6, 1.0), (0.4, 0.0)]


# ── What the fit refuses ───────────────────────────────────────────────────────


def test_too_few_rows_is_a_refusal_not_a_thin_justification():
    with pytest.raises(DatasetValidationError, match="at least 50 are needed") as exc:
        fit_platt(pairs(count=4), target="final_chart_cnf", partition="validation")
    assert "leave the artifact uncalibrated" in str(exc.value)


def test_one_label_only_cannot_teach_anything():
    data = [(0.3, 1.0)] * 20
    with pytest.raises(DatasetValidationError, match="one label only"):
        fit(data)


def test_no_spread_in_the_predictions_means_no_identifiable_slope():
    data = [(0.5, 1.0)] * 10 + [(0.5, 0.0)] * 10
    with pytest.raises(DatasetValidationError, match="same predicted event probability"):
        fit(data)


def test_certainties_are_dropped_before_the_count_is_checked():
    """Rows at 0 or 1 carry no log-odds, so they cannot support a fit either."""
    data = [(1.0, 1.0)] * 30 + [(0.5, 0.0)] * 5
    with pytest.raises(DatasetValidationError, match="have a probability in") as exc:
        fit(data, min_rows=10)
    assert "Only 5 of 35" in str(exc.value)


def test_a_prediction_outside_the_unit_interval_is_a_scoring_bug():
    data = [(-0.2, 1.0)] + [(0.6, 0.0)] * 5
    with pytest.raises(DatasetValidationError, match="A scored row predicted") as exc:
        fit(data)
    assert "outside [0, 1]" in str(exc.value)
    assert "do not fit over it" in str(exc.value)


def test_perfectly_separable_evidence_is_refused_rather_than_a_slope_fitted_downhill():
    """The likelihood has no finite maximum here, and Newton's Hessian collapses."""
    data = [(0.2, 1.0)] * 10 + [(0.8, 0.0)] * 10
    with pytest.raises(DatasetValidationError, match="singular Hessian") as exc:
        fit(data)
    assert "maximum-likelihood slope runs away" in str(exc.value)


def test_an_unknown_target_is_refused_before_any_arithmetic():
    with pytest.raises(DatasetValidationError, match="Cannot calibrate target"):
        fit(pairs(), target="departure_status")


@pytest.mark.parametrize("bad", [0, 1, -3, True, 2.5])
def test_the_minimum_row_rule_is_stated(bad):
    with pytest.raises(DatasetValidationError, match="min_rows must be"):
        fit(pairs(), min_rows=bad)


def test_improvement_requires_two_numbers_and_a_real_reduction():
    assert calibration_improves(before=None, after=0.1) is False
    assert calibration_improves(before=0.2, after=None) is False
    assert calibration_improves(before=0.2, after=0.2) is False
    assert calibration_improves(before=0.2, after=0.19) is True
    assert calibration_improves(before=0.2, after=0.21) is False


# ── Fitting on the validation partition, measuring on the locked test ──────────


@pytest.fixture
def fitted(tmp_path: Path):
    # The pipeline fixture ties each date to one label pattern, so its validation
    # partition carries a single class — which calibration correctly refuses to fit on.
    # This file mixes both labels inside every date.
    csv = write_balanced_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    return (
        fit_baseline(dataset, version="cal_v1", min_sample_threshold=5, val_frac=0.15),
        dataset,
    )


def measure(fitted, **overrides):
    kwargs = {
        "target": "final_chart_cnf",
        "min_rows": 10,
        "dataset_id": "synthetic-pipeline-fixture",
        "dataset_sha256": "c" * 64,
        "source_reference": "test",
        "approval_status": "approved",
        "is_synthetic": True,
        "mapping_version": MAPPING_VERSION,
    }
    kwargs.update(overrides)
    return fit_and_measure(fitted, **kwargs)


def test_the_layer_is_fitted_on_validation_rows_only(fitted):
    baseline, _ = fitted
    evidence = measure(baseline)
    assert isinstance(evidence.spec, CalibrationSpec)
    assert evidence.spec.fitted_partition == "validation"
    val_start, val_end = baseline.split.partitions[1].start_date, baseline.split.partitions[1].end_date
    assert evidence.spec.fitted_from == val_start
    assert evidence.spec.fitted_to == val_end
    assert evidence.spec.fitted_rows == len(baseline.split.val) or (
        evidence.spec.fitted_rows <= len(baseline.split.val)
    )


def test_a_layer_is_only_embedded_when_it_helped_where_it_was_fitted(fitted):
    """Reaching this assertion at all is the gate: fit_and_measure raises otherwise."""
    baseline, _ = fitted
    evidence = measure(baseline)
    assert evidence.validation_after.event_brier < (evidence.validation_before.event_brier)
    assert evidence.test_after.event_brier is not None


def test_the_locked_test_effect_is_reported_whichever_way_it_goes(fitted):
    baseline, _ = fitted
    evidence = measure(baseline)
    payload = evidence.to_dict()
    assert payload["validation_event_brier_change"] < 0
    assert isinstance(payload["helps_on_locked_test"], bool)
    assert payload["test_event_brier_change"] == pytest.approx(
        (payload["test_event_brier_after"] or 0) - (payload["test_event_brier_before"] or 0),
        abs=1e-6,
    )


def test_scores_before_and_after_differ_only_by_the_layer(fitted):
    baseline, _ = fitted
    evidence = measure(baseline)
    assert evidence.validation_before.calibration_applied is False
    assert evidence.validation_after.calibration_applied is True
    assert evidence.validation_after.scored_rows == evidence.validation_before.scored_rows
    assert evidence.validation_after.coverage == evidence.validation_before.coverage
    assert evidence.validation_after.brier != evidence.validation_before.brier


def test_a_target_the_artifact_was_not_fitted_for_is_refused(fitted):
    baseline, _ = fitted
    with pytest.raises(DatasetValidationError, match="fitted for"):
        measure(baseline, target="final_chart_cnf_or_rac")


def test_too_little_validation_data_refuses_before_fit(fitted):
    baseline, _ = fitted
    with pytest.raises(DatasetValidationError, match="at least 120 are needed"):
        measure(baseline, min_rows=120)


def test_the_calibrated_artifact_round_trips_through_the_registry_format(fitted, tmp_path):
    baseline, _ = fitted
    evidence = measure(baseline)
    calibrated = with_calibration(baseline, evidence.spec)
    assert calibrated.metadata.calibrated is True
    assert calibrated.metadata.calibration_method == "platt_logistic_v1"
    assert any("Probabilities are calibrated" in item for item in calibrated.metadata.limitations)

    path = write_fitted_artifact(calibrated, tmp_path / "cal_v1.json")
    loaded = load_artifact(
        path,
        expected_version="cal_v1",
        expected_target="final_chart_cnf",
        max_bytes=1_000_000,
    )
    assert loaded.metadata.calibration == evidence.spec
    assert loaded.metadata.promotion == "candidate"


def test_an_uncalibrated_artifact_carries_no_block(fitted):
    baseline, _ = fitted
    assert baseline.metadata.calibrated is False
    assert baseline.metadata.calibration is None
    assert any("calibrated" in item.lower() for item in baseline.metadata.limitations)
    assert baseline.metadata.calibration_method is None


def test_a_calibrated_artifact_does_not_also_deny_being_calibrated(fitted):
    """One artifact cannot say "not a calibrated model" and name its calibration layer.

    The limitation list is what a reader sees on a served report, so an unedited
    base line surviving the calibration would contradict the line beside it.
    """
    baseline, _ = fitted
    evidence = measure(baseline)
    uncalibrated_claim = next(
        item for item in baseline.metadata.limitations if "not a trained or calibrated" in item
    )
    calibrated = with_calibration(baseline, evidence.spec)
    assert all(item != uncalibrated_claim for item in calibrated.metadata.limitations)
    assert not any("not a trained or calibrated" in item for item in calibrated.metadata.limitations)
    # The frequencies are still smoothed counts; saying they are calibrated does not
    # turn them into a trained model, and the artifact must keep admitting that.
    assert any("smoothed" in item.lower() for item in calibrated.metadata.limitations)


# ── Report wording ─────────────────────────────────────────────────────────────


def plain_scores(baseline, partition: str):
    """Score a partition with no calibration layer, as an uncalibrated run would."""
    from railconfirm.training.metrics import (
        build_estimator,
        evaluation_provenance,
        score_partition,
    )

    estimator = build_estimator(
        baseline.cohorts,
        evaluation_provenance(
            "synthetic-pipeline-fixture",
            "c" * 64,
            "test",
            "approved",
            is_synthetic=True,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=baseline.metadata.min_sample_threshold,
        laplace_alpha=baseline.metadata.laplace_alpha,
    )
    return score_partition(
        getattr(baseline.split, partition),
        estimator,
        prevalence=baseline.prevalence,
        partition=partition,
        target="final_chart_cnf",
    )


def report_for(baseline, evidence=None, *, metadata=None, measured=True):
    return build_report(
        metadata=metadata if metadata is not None else baseline.metadata,
        dataset_id="synthetic-pipeline-fixture",
        dataset_sha256="c" * 64,
        dataset_rows=240,
        fit=baseline.summary,
        split=baseline.split,
        validation=evidence.validation_after if evidence else plain_scores(baseline, "val"),
        test=evidence.test_after if evidence else plain_scores(baseline, "test"),
        generated_on="2026-05-01",
        calibration=evidence if measured else None,
    )


def test_the_report_states_the_effect_on_the_locked_period(fitted):
    baseline, _ = fitted
    evidence = measure(baseline)
    report = report_for(with_calibration(baseline, evidence.spec), evidence)
    joined = " ".join(report.conclusions)
    assert "It was embedded because the validation event Brier moved" in joined
    assert "on the locked test the same correction moved" in joined
    assert any("Subgroup calibration" in item for item in report.limitations)
    assert report.to_dict()["calibration"]["validation_event_brier_change"] < 0
    assert "Calibration: event Brier validation" in report.summary()


@pytest.mark.parametrize("build", [True, False])
def test_every_printed_report_line_survives_a_windows_console(fitted, build):
    """cp1252 has no arrow, and a traceback in place of a report is a real failure.

    The test suite captures output through a buffer that tolerates any character, so
    only this assertion catches what a Windows terminal cannot encode.
    """
    baseline, _ = fitted
    evidence = measure(baseline) if build else None
    report = report_for(with_calibration(baseline, evidence.spec), evidence) if evidence else report_for(baseline)
    text = report.summary() + "\n" + "\n".join(report.conclusions + report.limitations)
    text.encode("cp1252")


def test_a_printed_refusal_survives_a_windows_console(fitted):
    baseline, _ = fitted
    with pytest.raises(DatasetValidationError) as exc:
        measure(baseline, min_rows=100_000)
    str(exc.value).encode("cp1252")


def test_a_declared_layer_without_measurement_says_so(fitted):
    baseline, _ = fitted
    calibrated = with_calibration(baseline, measure(baseline).spec)
    report = report_for(calibrated, measure(baseline), measured=False)
    joined = " ".join(report.limitations)
    assert "carried no before/after measurement" in joined
    assert "Calibration: applied to the numbers above" in report.summary()


def test_evidence_that_was_not_embedded_is_labelled_as_such(fitted):
    baseline, _ = fitted
    report = report_for(baseline, measure(baseline))
    joined = " ".join(report.limitations)
    assert "No calibration was fitted or applied" in joined
    assert "the numbers above are the uncorrected ones" in joined


def test_the_report_bytes_do_not_move(fitted):
    baseline, _ = fitted
    evidence = measure(baseline)
    assert report_for(baseline, evidence).to_json() == report_for(
        baseline, measure(baseline)
    ).to_json()


# ── Command line ───────────────────────────────────────────────────────────────


def test_fit_calibrate_writes_a_calibrated_candidate(tmp_path: Path, capsys):
    csv = write_balanced_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    artifact = tmp_path / "cli_cal_v1.json"
    report = tmp_path / "cli_cal_report.json"
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "cli_cal_v1",
            "--out",
            str(artifact),
            "--report",
            str(report),
            "--generated-on",
            "2026-05-02",
            "--min-sample-threshold",
            "5",
            "--calibrate",
            "--calibrate-min-rows",
            "10",
            "--allow-synthetic-for-testing",
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "Calibration: platt_logistic_v1 on final_chart_cnf" in printed
    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert document["metadata"]["calibrated"] is True
    assert document["metadata"]["calibration"]["fitted_partition"] == "validation"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["calibration"]["validation_event_brier_change"] < 0
    assert payload["validation"]["calibration_applied"] is True


def test_fit_refuses_to_calibrate_on_a_thin_validation_period(tmp_path: Path, capsys):
    csv = write_balanced_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "v",
            "--out",
            str(tmp_path / "v.json"),
            "--min-sample-threshold",
            "5",
            "--calibrate",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "at least 50 are needed" in err
    assert not (tmp_path / "v.json").exists()


def test_evaluate_reports_the_artifact_s_arithmetic(tmp_path: Path, capsys):
    csv = write_balanced_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    artifact = tmp_path / "cli_cal_v1.json"
    assert (
        main(
            [
                "fit",
                str(csv),
                str(manifest),
                "--version",
                "cli_cal_v1",
                "--out",
                str(artifact),
                "--min-sample-threshold",
                "5",
                "--calibrate",
                "--calibrate-min-rows",
                "10",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    capsys.readouterr()
    code = main(
        [
            "evaluate",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact),
            "--allow-synthetic-for-testing",
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "calibration applied (platt_logistic_v1)" in printed


def test_evaluate_says_when_an_artifact_is_uncalibrated(tmp_path: Path, capsys):
    csv = write_balanced_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    artifact = tmp_path / "plain_v1.json"
    assert (
        main(
            [
                "fit",
                str(csv),
                str(manifest),
                "--version",
                "plain_v1",
                "--out",
                str(artifact),
                "--min-sample-threshold",
                "5",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "evaluate",
                str(csv),
                str(manifest),
                "--artifact",
                str(artifact),
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    assert "uncalibrated" in capsys.readouterr().out


def test_a_promoted_calibrated_artifact_is_still_gated_on_data_approval(fitted, tmp_path):
    """Calibration changes the numbers, not the trust rules."""
    baseline, _ = fitted
    calibrated = with_calibration(baseline, measure(baseline).spec)
    # The registry insists the declared version match the file name, so the flipped
    # copy is written under the version it carries.
    path = write_fitted_artifact(calibrated, tmp_path / "cal_v1.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["metadata"]["promotion"] = PROMOTION_APPROVED
    document["metadata"]["is_synthetic"] = False
    document["metadata"]["data_approval_status"] = "under_review"
    path.write_text(json.dumps(document), encoding="utf-8")

    from railconfirm.domain.prediction import PredictionTarget
    from railconfirm.inference.registry import ArtifactStatus, ModelRegistry

    resolution = ModelRegistry(models_dir=tmp_path, active_version="cal_v1").resolve(
        PredictionTarget.FINAL_CHART_CNF
    )
    assert resolution.status is ArtifactStatus.DATA_NOT_APPROVED

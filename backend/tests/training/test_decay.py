"""Scoring ONE frozen artifact across successive horizons, with nothing refitted.

Synthetic rows only. `origins` refits at every cutoff and therefore measures the fitting
procedure, while a promoted artifact in service is the same table asked to predict a later
and later period. Anything that lets that table change between horizons, or lets the
reference baseline move toward the answer, turns a decay measurement into a different
question with the same name — so most of what these tests pin is what the run refuses.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from railconfirm.data.preprocessing import frozen_horizon_windows
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import LoadedArtifact, load_artifact
from railconfirm.inference.baseline import COHORT_FEATURES, COHORT_STATUS_SEMANTICS
from railconfirm.training.calibration import fit_and_measure
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.decay import (
    FROZEN_EVALUATION_METHOD,
    HorizonScore,
    describe_result,
    run_frozen_decay,
)
from railconfirm.training.fitter import (
    fit_baseline,
    fit_cohorts,
    prevalence_distribution,
    with_calibration,
    write_fitted_artifact,
)
from railconfirm.training.metrics import METRIC_KEYS, STRUCTURAL_FIELDS, TARGET_EVENTS
from railconfirm.training.report import (
    DECAY_REPORT_SCHEMA_VERSION,
    build_decay_report,
    write_decay_report,
)
from tests.support.datasets import write_approved_manifest, write_balanced_dataset


def artifact(tmp_path: Path, **fit_kwargs):
    """Fit a candidate artifact through the gate and read it back as the registry would."""
    kwargs = {
        "version": "decay_v1",
        "min_sample_threshold": 5,
        "train_frac": 0.5,
        "val_frac": 0.25,
    }
    kwargs.update(fit_kwargs)
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted = fit_baseline(dataset, **kwargs)
    path = write_fitted_artifact(fitted, tmp_path / f"{kwargs['version']}.json")
    loaded = load_artifact(
        path,
        expected_version=kwargs["version"],
        expected_target=fitted.metadata.target,
        max_bytes=1_000_000,
    )
    return loaded, dataset, fitted


def report_of(result, dataset):
    return build_decay_report(
        result,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        dataset_rows=dataset.report.total_rows,
        generated_on="2026-10-24",
    )


# ── What the run measures ──────────────────────────────────────────────────────


def test_every_horizon_is_scored_by_the_same_frozen_table(tmp_path):
    loaded, dataset, fitted = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.horizon_count == len(result.plan.horizons)
    assert result.horizon_count >= 2
    # Nothing refits: every horizon reports the artifact's own cohort count.
    assert {score.cohort_count for score in result.scores} == {len(loaded.cohorts)}
    assert result.artifact_version == "decay_v1"
    assert result.fitted_to == fitted.metadata.trained_to


def test_the_horizon_windows_are_the_untouched_future_after_the_fitted_period(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    cutoff = loaded.metadata.trained_to
    for score in result.scores:
        assert min(score.window.scored_dates) > cutoff
        assert score.window.train_dates == result.plan.train_dates


def test_the_target_comes_from_the_artifact_not_from_the_caller(tmp_path):
    loaded, dataset, _ = artifact(tmp_path, target="final_chart_cnf_or_rac")
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.target == "final_chart_cnf_or_rac"
    assert result.to_dict()["target_event_classes"] == list(
        TARGET_EVENTS["final_chart_cnf_or_rac"]
    )
    for score in result.scores:
        assert score.scorecard.target == "final_chart_cnf_or_rac"


def test_the_reference_prevalence_is_the_frozen_population(tmp_path):
    """The baseline a horizon is judged against comes from dates at or before the cutoff."""
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=2, step_dates=2)
    expected = prevalence_distribution(
        fit_cohorts(result.plan.train).label_distribution
    )
    assert result.prevalence == expected


def test_relabeling_the_future_does_not_move_the_reference_baseline(tmp_path):
    """If the baseline read the scored rows, a collapsing population would look stable."""
    loaded, dataset, _ = artifact(tmp_path)
    cutoff = loaded.metadata.trained_to
    frozen = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1).prevalence

    moved = dataset.frame.copy()
    future = moved["journey_date"].astype(str) > cutoff
    moved.loc[future, "final_chart_status"] = "CNF"
    relabelled = replace(dataset, frame=moved)
    after = run_frozen_decay(relabelled, loaded, horizon_dates=1, step_dates=1).prevalence
    assert after == frozen
    assert after is not None


def test_abstentions_are_counted_not_scored_as_errors(tmp_path):
    """A table too thin for the artifact's own threshold abstains, and says coverage 0."""
    loaded, dataset, _ = artifact(tmp_path, min_sample_threshold=10_000)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    for score in result.scores:
        assert score.scorecard.coverage == 0.0
        assert score.scorecard.scored_rows == 0
        assert score.scorecard.brier is None
    assert result.horizons_with_scores == 0
    assert result.rows_scored == 0
    assert result.rows_seen > 0


def test_the_estimator_is_built_with_the_artifacts_own_settings(tmp_path):
    """min_sample_threshold and laplace_alpha travel with the artifact, not the command line."""
    loaded, dataset, _ = artifact(tmp_path, min_sample_threshold=5, laplace_alpha=1.0)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.min_sample_threshold == 5
    assert result.laplace_alpha == 1.0
    assert all(score.scorecard.coverage > 0.0 for score in result.scores)


def test_a_calibrated_artifact_is_scored_with_its_correction_on_every_horizon(tmp_path):
    loaded, dataset, fitted = artifact(tmp_path, train_frac=0.7, val_frac=0.15)
    evidence = fit_and_measure(
        fitted,
        target=fitted.metadata.target,
        min_rows=10,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        source_reference="test",
        approval_status="approved",
        is_synthetic=True,
        mapping_version=MAPPING_VERSION,
    )
    calibrated = with_calibration(fitted, evidence.spec)
    path = write_fitted_artifact(calibrated, tmp_path / "cal_decay.json")
    loaded_calibrated = load_artifact(
        path,
        expected_version="decay_v1",
        expected_target=calibrated.metadata.target,
        max_bytes=1_000_000,
    )
    assert loaded_calibrated.metadata.calibration is not None
    result = run_frozen_decay(dataset, loaded_calibrated, horizon_dates=1, step_dates=1)
    assert result.calibration == loaded_calibrated.metadata.calibration
    assert result.to_dict()["calibration"]["method"] == "platt_logistic_v1"
    assert all(score.scorecard.calibration_applied for score in result.scores)


def test_an_uncalibrated_artifact_reports_no_correction(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.calibration is None
    assert result.to_dict()["calibration"] is None
    assert all(not score.scorecard.calibration_applied for score in result.scores)


def test_group_rows_are_carried_into_each_horizons_group_card(tmp_path):
    """The balanced fixture is one booking per row, so the card must say exactly that."""
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=2, step_dates=2)
    for score in result.scores:
        card = score.scorecard.group
        assert card.multi_passenger_groups == 0
        assert card.single_passenger_groups == score.scorecard.rows


# ── Drift, described rather than smoothed away ─────────────────────────────────


def test_drift_compares_the_first_horizon_with_the_last_rather_than_averaging(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    scored = [s.scorecard for s in result.scores if s.scorecard.event_brier is not None]
    assert result.first_event_brier == scored[0].event_brier
    assert result.last_event_brier == scored[-1].event_brier
    assert result.event_brier_drift == pytest.approx(
        round(scored[-1].event_brier - scored[0].event_brier, 6)
    )
    assert result.event_brier_spread == (
        min(card.event_brier for card in scored),
        max(card.event_brier for card in scored),
    )
    assert result.coverage_spread is not None
    # The ends of the drift are horizons, and the run says which ones.
    assert result.first_scored_horizon == result.scores[0].window.index
    assert result.last_scored_horizon == result.scores[-1].window.index
    assert result.scored_horizon_indices == tuple(
        score.window.index for score in result.scores
    )


def test_a_horizon_that_abstained_everywhere_is_counted_separately(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.horizons_beating_event_baseline + result.horizons_losing_event_baseline == (
        result.horizons_with_event_scores
    )
    assert result.horizons_with_scores <= result.horizon_count


def test_a_run_where_nothing_could_be_scored_reports_no_drift(tmp_path):
    loaded, dataset, _ = artifact(tmp_path, min_sample_threshold=10_000)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.first_event_brier is None
    assert result.event_brier_drift is None
    assert result.first_scored_horizon is None
    assert result.scored_horizon_indices == ()


def without_a_score(card):
    """The same window with every row abstaining, so the horizon measures nothing."""
    return replace(
        card,
        scored_rows=0,
        abstained_rows=card.rows,
        coverage=0.0,
        brier=None,
        log_loss=None,
        baseline_brier=None,
        baseline_log_loss=None,
        brier_skill=None,
        event_brier=None,
        event_log_loss=None,
        event_baseline_brier=None,
        event_brier_skill=None,
        reliability={},
        event_reliability=[],
        segment_calibration=[],
        segments=[],
        outcome_distribution={},
        group=None,
    )


def mute(result, indices):
    """The same run with the named horizons abstaining on everything."""
    muted = tuple(
        HorizonScore(
            window=score.window,
            scorecard=without_a_score(score.scorecard)
            if score.window.index in indices
            else score.scorecard,
            cohort_count=score.cohort_count,
        )
        for score in result.scores
    )
    return replace(result, scores=muted)


def test_the_drift_says_which_horizons_it_measured(tmp_path):
    """A silent first horizon must not be reported as the window nearest the cutoff.

    The drift is the last *scored* horizon minus the first *scored* one, so when an
    earlier horizon abstained the conclusion has to date its own number. It used to call
    horizon 1's Brier "the window nearest the cutoff", which is a statement about a
    window that produced no reading at all.
    """
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert len(result.scores) >= 3
    muted = mute(result, {0})
    assert muted.first_scored_horizon == 1
    assert muted.last_scored_horizon == muted.horizon_count - 1
    assert muted.summary["first_scored_horizon"] == 1
    report = report_of(muted, dataset)
    joined = " ".join(report.conclusions)
    assert "in the window nearest the cutoff" not in joined
    assert "at horizon 1, not the window nearest the cutoff" in joined
    assert "in the furthest" in joined
    assert "Horizon 0 produced no score" in joined
    assert "the two ends of this difference are the two ends that were measured" in joined
    assert "h1" in report.summary_lines()


def test_a_single_scored_horizon_is_not_reported_as_a_decay_curve(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    muted = mute(result, set(range(1, result.horizon_count)))
    assert muted.horizons_with_scores == 1
    joined = " ".join(report_of(muted, dataset).conclusions)
    assert "Only horizon 0 produced a score" in joined
    assert "single measurement" in joined
    assert "drift of" not in joined


def test_describe_result_prints_one_line_per_horizon_and_names_the_cutoff(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    text = describe_result(result)
    assert len(text.splitlines()) >= result.horizon_count + 1
    assert result.cutoff in text
    assert "frozen" in text.lower()
    assert text.encode("cp1252")  # a Windows console must not kill a finished run


# ── Refusals ───────────────────────────────────────────────────────────────────


def test_an_artifact_that_does_not_declare_its_period_cannot_be_measured_for_decay(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    naked = LoadedArtifact(
        metadata=replace(loaded.metadata, trained_to=None),
        cohorts=loaded.cohorts,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="does not declare"):
        run_frozen_decay(dataset, naked, horizon_dates=1, step_dates=1)


def test_an_artifact_fitted_to_the_last_date_in_the_file_has_no_future_to_decay_into(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    dates = sorted(set(dataset.frame["journey_date"].astype(str)))
    shifted = LoadedArtifact(
        metadata=replace(loaded.metadata, trained_to=dates[-1]),
        cohorts=loaded.cohorts,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="Cannot measure decay"):
        run_frozen_decay(dataset, shifted, horizon_dates=1, step_dates=1)


def test_one_horizon_left_is_refused_rather_than_drawn_as_a_trend(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    dates = sorted(set(dataset.frame["journey_date"].astype(str)))
    shifted = LoadedArtifact(
        metadata=replace(loaded.metadata, trained_to=dates[-2]),
        cohorts=loaded.cohorts,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="at least 2"):
        run_frozen_decay(dataset, shifted, horizon_dates=1, step_dates=1)


def test_an_artifact_keyed_by_a_different_status_rule_is_refused_before_scoring(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    mismatched = LoadedArtifact(
        metadata=replace(loaded.metadata, cohort_semantics="initial_status_v0"),
        cohorts=loaded.cohorts,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="cohort_semantics"):
        run_frozen_decay(dataset, mismatched, horizon_dates=1, step_dates=1)


def test_an_artifact_claiming_features_it_does_not_read_is_refused(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    mismatched = LoadedArtifact(
        metadata=replace(loaded.metadata, features_used=("class_code", "lead_days")),
        cohorts=loaded.cohorts,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="features_used"):
        run_frozen_decay(dataset, mismatched, horizon_dates=1, step_dates=1)


def test_the_frozen_contract_constants_are_the_ones_the_estimator_uses():
    """If the served rule changes, this assertion has to be edited deliberately, not ignored."""
    assert COHORT_STATUS_SEMANTICS == "asof_status_v1"
    assert COHORT_FEATURES == ("class_code", "quota_code", "asof_normalized")


def test_the_run_never_mutates_the_dataset_or_the_artifact(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    before_cohorts = json.dumps({str(k): v for k, v in loaded.cohorts.items()}, sort_keys=True)
    before_rows = len(dataset.frame)
    run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert len(dataset.frame) == before_rows
    assert (
        json.dumps({str(k): v for k, v in loaded.cohorts.items()}, sort_keys=True)
        == before_cohorts
    )


def test_the_plan_and_the_run_agree_on_the_same_cutoff(tmp_path):
    """The run plans from the artifact's own declared window, not from a caller's guess."""
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    standalone = frozen_horizon_windows(
        dataset.frame,
        fitted_to=loaded.metadata.trained_to,
        horizon_dates=1,
        step_dates=1,
    )
    assert [w.scored_dates for w in standalone.horizons] == [
        s.window.scored_dates for s in result.scores
    ]


# ── The report ─────────────────────────────────────────────────────────────────


def test_the_report_names_the_method_that_makes_it_not_a_rolling_origin_run(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    report = report_of(result, dataset)
    assert report.evaluation_method == FROZEN_EVALUATION_METHOD
    assert "frozen" in report.evaluation_method
    payload = report.to_dict()
    assert payload["artifact"]["version"] == "decay_v1"
    assert payload["artifact"]["fitted_from"] == loaded.metadata.trained_from
    assert len(payload["horizons"]) == result.horizon_count
    assert payload["summary"]["event_brier_drift"] == result.event_brier_drift
    assert payload["summary"]["coverage_drift"] == result.coverage_drift


def test_the_report_states_where_the_baseline_came_from_and_what_was_frozen(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    joined = " ".join(report_of(result, dataset).limitations)
    assert "prevalence baseline" in joined
    assert "never refitted" in joined
    assert "synthetic" in joined.lower()
    assert "not independent" in joined


def test_every_published_metric_is_defined(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    report = report_of(result, dataset)
    payload = report.to_dict()
    for horizon in payload["horizons"]:
        assert set(horizon["score"]) - STRUCTURAL_FIELDS == METRIC_KEYS
    definitions = set(report.metric_definitions)
    assert definitions >= METRIC_KEYS
    assert {"event_brier_drift", "coverage_drift", "prevalence"} <= definitions


def test_conclusions_quote_the_measured_drift_rather_than_handing_out_a_verdict(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    text = " ".join(report_of(result, dataset).conclusions)
    assert f"{result.first_event_brier:.6f}" in text
    assert f"{result.last_event_brier:.6f}" in text


def test_a_run_that_scored_nothing_concludes_nothing_positive(tmp_path):
    loaded, dataset, _ = artifact(tmp_path, min_sample_threshold=10_000)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    text = " ".join(report_of(result, dataset).conclusions)
    assert "no horizon produced" in text.lower()
    assert "improvement" not in text.lower()


def test_the_report_bytes_do_not_move(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert report_of(result, dataset).to_json() == report_of(result, dataset).to_json()


def test_write_decay_report_produces_the_same_json(tmp_path):
    loaded, dataset, _ = artifact(tmp_path)
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    report = report_of(result, dataset)
    path = write_decay_report(report, tmp_path / "decay.json")
    assert path.read_text(encoding="utf-8") == report.to_json()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["report_schema_version"] == DECAY_REPORT_SCHEMA_VERSION
    assert payload["generated_on"] == "2026-10-24"


# ── The command line ───────────────────────────────────────────────────────────


def cli_files(tmp_path: Path, **fit_kwargs):
    """Write the dataset, manifest and artifact a decay run is pointed at."""
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted = fit_baseline(dataset, version="decay_v1", min_sample_threshold=5, **fit_kwargs)
    path = write_fitted_artifact(fitted, tmp_path / "decay_v1.json")
    return csv, manifest, path


def test_the_decay_command_scores_the_frozen_artifact_and_prints_the_drift(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(tmp_path, train_frac=0.5, val_frac=0.25)
    code = main(
        [
            "decay",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact_path),
            "--horizon-dates",
            "1",
            "--step-dates",
            "1",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Frozen artifact decay_v1" in out
    assert "Drift across" in out
    assert "horizon 0" in out
    assert "not refitted" not in out  # limitations belong to the report, not the summary line


def test_the_decay_command_writes_a_byte_reproducible_report(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(tmp_path, train_frac=0.5, val_frac=0.25)
    argv = [
        "decay",
        str(csv),
        str(manifest),
        "--artifact",
        str(artifact_path),
        "--horizon-dates",
        "1",
        "--step-dates",
        "1",
        "--report",
        str(tmp_path / "decay-report.json"),
        "--generated-on",
        "2026-10-24",
        "--allow-synthetic-for-testing",
    ]
    assert main(argv) == 0
    first = (tmp_path / "decay-report.json").read_text(encoding="utf-8")
    assert main(argv) == 0
    assert (tmp_path / "decay-report.json").read_text(encoding="utf-8") == first
    payload = json.loads(first)
    assert payload["evaluation_method"] == FROZEN_EVALUATION_METHOD
    assert payload["artifact"]["fitted_to"] == payload["plan"]["cutoff"]
    assert len(payload["horizons"]) >= 2
    assert "=== Frozen-artifact decay report ===" in capsys.readouterr().out


def test_the_decay_command_requires_generated_on_for_a_report(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(tmp_path, train_frac=0.5, val_frac=0.25)
    code = main(
        [
            "decay",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact_path),
            "--report",
            str(tmp_path / "never.json"),
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "generated-on" in capsys.readouterr()[-1]
    assert not (tmp_path / "never.json").exists()


def test_the_decay_command_refuses_when_the_calendar_supports_only_one_horizon(
    tmp_path, capsys
):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(tmp_path, train_frac=0.5, val_frac=0.25)
    code = main(
        [
            "decay",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact_path),
            "--horizon-dates",
            "4",
            "--step-dates",
            "4",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "at least 2" in capsys.readouterr()[-1]


def test_the_decay_command_refuses_an_artifact_fitted_for_another_target(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(
        tmp_path, train_frac=0.5, val_frac=0.25, target="final_chart_cnf_or_rac"
    )
    code = main(
        [
            "decay",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact_path),
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "target" in capsys.readouterr()[-1].lower()


def test_the_decay_command_prints_only_what_a_windows_console_can_encode(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv, manifest, artifact_path = cli_files(tmp_path, train_frac=0.5, val_frac=0.25)
    assert (
        main(
            [
                "decay",
                str(csv),
                str(manifest),
                "--artifact",
                str(artifact_path),
                "--horizon-dates",
                "1",
                "--step-dates",
                "1",
                "--report",
                str(tmp_path / "decay-report.json"),
                "--generated-on",
                "2026-10-24",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        text.encode("cp1252")
    (tmp_path / "decay-report.json").read_text(encoding="utf-8").encode("cp1252")

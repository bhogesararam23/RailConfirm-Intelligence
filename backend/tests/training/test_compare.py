"""Deciding between two estimators on the locked period, not on whichever number looks better.

Synthetic rows only. A candidate that wins in the window it was chosen for has proved nothing;
this harness exists so the repository cannot promote a model on a flattering comparison. The
accounting is therefore tested at its own level — hand-built scored rows with known outcomes —
and the real-fixture verdict is only asserted to be consistent with what the rule computes.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.inference.queue import QUEUE_ESTIMATOR_ID
from railconfirm.training.compare import (
    MODEL_SELECTION_METHOD,
    PartitionComparison,
    decide_verdict,
    pair_scores,
    run_model_comparison,
)
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.fitter import fit_baseline
from railconfirm.training.metrics import ScoredRow
from railconfirm.training.report import (
    COMPARISON_REPORT_SCHEMA_VERSION,
    build_comparison_report,
    write_comparison_report,
)
from tests.support.datasets import (
    write_approved_manifest,
    write_balanced_dataset,
)


def row(
    position: int,
    event_predicted: float,
    event_observed: float,
    *,
    distribution_brier: float | None = None,
) -> ScoredRow:
    hypothesis = {"CNF": event_predicted, "WL": 1.0 - event_predicted}
    truth = {"CNF": event_observed, "WL": 1.0 - event_observed}
    return ScoredRow(
        hypothesis=hypothesis,
        truth=truth,
        observed="CNF" if event_observed else "WL",
        event_predicted=event_predicted,
        event_observed=event_observed,
        brier=(
            distribution_brier
            if distribution_brier is not None
            else (event_predicted - event_observed) ** 2
            + ((1 - event_predicted) - (1 - event_observed)) ** 2
        ),
        loss=0.0,
        slices=[("class_code", "SL")],
        position=position,
    )


# ── Paired accounting ──────────────────────────────────────────────────────────


def test_paired_counts_are_wins_losses_and_ties_against_the_targets_own_event():
    baseline = [row(0, 0.50, 1.0), row(1, 0.50, 0.0), row(2, 0.50, 1.0), row(3, 0.50, 0.0)]
    candidate = [row(0, 0.80, 1.0), row(1, 0.20, 0.0), row(2, 0.20, 1.0), row(3, 0.80, 0.0)]
    paired = pair_scores(baseline, candidate)
    assert paired.rows_both_scored == 4
    # rows 0 and 1 the candidate gets closer; row 2 and 3 it overshoots badly.
    assert paired.candidate_wins == 2
    assert paired.candidate_losses == 2
    assert paired.ties == 0
    assert paired.only_baseline_scored == 0
    assert paired.only_candidate_scored == 0


def test_a_tie_means_equal_error_and_a_hair_of_difference_is_not_a_tie():
    """No epsilon band: a nearer prediction wins, however slightly."""
    tie = pair_scores([row(0, 0.4, 1.0)], [row(0, 0.4, 1.0)])
    assert (tie.ties, tie.candidate_wins, tie.candidate_losses) == (1, 0, 0)

    hair = pair_scores([row(0, 0.4, 1.0)], [row(0, 0.400001, 1.0)])
    assert (hair.ties, hair.candidate_wins, hair.candidate_losses) == (0, 1, 0)


def test_rows_one_model_refused_are_counted_separately_and_never_as_wins():
    """An abstention is not a lost forecast, and it is not a win either."""
    baseline = [row(0, 0.5, 1.0), row(1, 0.5, 0.0)]
    candidate = [row(1, 0.1, 0.0)]  # nothing at position 0: the candidate abstained there
    paired = pair_scores(baseline, candidate)
    assert paired.rows_both_scored == 1
    assert paired.only_baseline_scored == 1
    assert paired.only_candidate_scored == 0
    assert paired.candidate_wins + paired.candidate_losses + paired.ties == 1


def test_positions_come_from_the_row_order_not_from_how_many_rows_answered():
    """Two models abstaining on different rows must still pair the same reservations."""
    baseline = [row(0, 0.5, 1.0), row(2, 0.5, 0.0)]
    candidate = [row(0, 0.9, 1.0), row(2, 0.1, 0.0)]
    paired = pair_scores(baseline, candidate)
    assert (paired.candidate_wins, paired.candidate_losses) == (2, 0)
    assert paired.rows_both_scored == 2


def test_paired_accounting_is_order_independent():
    baseline = [row(1, 0.5, 1.0), row(0, 0.5, 0.0)]
    candidate = [row(1, 0.9, 1.0), row(0, 0.9, 0.0)]
    forward = pair_scores(baseline, candidate)
    reversed_ = pair_scores(list(reversed(baseline)), list(reversed(candidate)))
    assert (forward.candidate_wins, forward.candidate_losses) == (
        reversed_.candidate_wins,
        reversed_.candidate_losses
    )


def test_nothing_scored_by_either_model_pairs_no_rows():
    paired = pair_scores([], [])
    assert paired.rows_both_scored == 0
    assert paired.comparable is False


def test_the_brier_used_for_pairing_is_the_event_brier_not_the_distribution_one():
    """The lens is stated so a reader knows which claim the wins describe."""
    # Same event error, opposite distribution errors: the pairing must not see them.
    baseline = [row(0, 0.5, 1.0, distribution_brier=0.9)]
    candidate = [row(0, 0.5, 1.0, distribution_brier=0.1)]
    paired = pair_scores(baseline, candidate)
    assert paired.candidate_wins == 0
    assert paired.candidate_losses == 0
    assert paired.ties == 1  # same event error; the distribution difference is ignored here


def test_a_repeated_position_is_refused_rather_than_paired_arbitrarily():
    """A position identifies one reservation; two of them means the alignment is unknown."""
    with pytest.raises(DatasetValidationError, match="more than once"):
        pair_scores([row(0, 0.5, 1.0), row(0, 0.4, 0.0)], [row(0, 0.5, 1.0)])


def test_a_partition_total_below_the_rows_answered_is_refused():
    """`neither_scored` is a subtraction, so a short total would publish a negative count."""
    baseline = [row(0, 0.5, 1.0), row(1, 0.5, 0.0)]
    with pytest.raises(DatasetValidationError, match="declares 1"):
        pair_scores(baseline, [row(0, 0.5, 1.0)], rows_total=1)


# ── The verdict rule ───────────────────────────────────────────────────────────


def comparison(
    partition: str,
    *,
    baseline_brier: float,
    candidate_brier: float,
    baseline_event: float,
    candidate_event: float,
    baseline_coverage: float = 1.0,
    candidate_coverage: float = 1.0,
    wins: int = 0,
    losses: int = 0,
    ties: int = 0,
) -> PartitionComparison:
    """A partition built to the exact numbers the rule reads, so the rule is what is tested."""
    from railconfirm.training.metrics import Scorecard

    def card(brier: float, event: float, coverage: float) -> Scorecard:
        return Scorecard(
            partition=partition,
            target="final_chart_cnf",
            rows=100,
            scored_rows=int(100 * coverage),
            abstained_rows=100 - int(100 * coverage),
            coverage=coverage,
            brier=brier,
            log_loss=brier,
            baseline_brier=0.48,
            baseline_log_loss=0.48,
            brier_skill=0.0,
            event_brier=event,
            event_log_loss=event,
            event_baseline_brier=0.24,
            event_brier_skill=0.0,
            event_reliability=[],
            reliability={},
            segment_calibration=[],
            segments=[],
            outcome_distribution={"CNF": 50, "WL": 50},
            min_segment_rows=25,
            group=None,
        )

    from railconfirm.training.compare import PairedCount

    return PartitionComparison(
        partition=partition,
        baseline=card(baseline_brier, baseline_event, baseline_coverage),
        candidate=card(candidate_brier, candidate_event, candidate_coverage),
        paired=PairedCount(
            rows_both_scored=wins + losses + ties,
            candidate_wins=wins,
            candidate_losses=losses,
            ties=ties,
            only_baseline_scored=0,
            only_candidate_scored=0,
            rows_total=100,
        ),
    )


def test_a_candidate_is_recommended_only_when_it_wins_every_part_of_the_locked_claim():
    locked = comparison(
        "test",
        baseline_brier=0.480,
        candidate_brier=0.470,
        baseline_event=0.240,
        candidate_event=0.230,
        wins=60,
        losses=30,
        ties=10,
    )
    verdict = decide_verdict([locked])
    assert verdict.outcome == "candidate"
    assert any("locked" in reason.lower() for reason in verdict.reasons)


def test_winning_the_event_but_losing_the_distribution_is_not_a_promotion():
    locked = comparison(
        "test",
        baseline_brier=0.480,
        candidate_brier=0.490,
        baseline_event=0.240,
        candidate_event=0.230,
        wins=60,
        losses=30,
    )
    assert decide_verdict([locked]).outcome == "baseline"


def test_more_abstentions_disqualify_a_candidate_however_good_its_scores_look():
    """A model that refuses more rows can score better on the rows it chose to answer."""
    locked = comparison(
        "test",
        baseline_brier=0.480,
        candidate_brier=0.470,
        baseline_event=0.240,
        candidate_event=0.230,
        baseline_coverage=1.0,
        candidate_coverage=0.6,
        wins=60,
        losses=10,
    )
    verdict = decide_verdict([locked])
    assert verdict.outcome == "baseline"
    assert any("coverage" in reason.lower() for reason in verdict.reasons)


def test_ties_in_the_paired_count_do_not_add_up_to_a_win():
    locked = comparison(
        "test",
        baseline_brier=0.480,
        candidate_brier=0.470,
        baseline_event=0.240,
        candidate_event=0.230,
        wins=10,
        losses=10,
        ties=80,
    )
    assert decide_verdict([locked]).outcome == "baseline"


def test_a_locked_period_that_scored_nothing_is_undetermined_not_a_pass():
    locked = comparison(
        "test",
        baseline_brier=0.0,
        candidate_brier=0.0,
        baseline_event=0.0,
        candidate_event=0.0,
        baseline_coverage=0.0,
        candidate_coverage=0.0,
    )
    verdict = decide_verdict([locked])
    assert verdict.outcome == "undetermined"
    assert not any("recommend" in reason.lower() for reason in verdict.reasons)


def test_no_locked_test_means_undetermined():
    validation = comparison(
        "validation",
        baseline_brier=0.480,
        candidate_brier=0.470,
        baseline_event=0.240,
        candidate_event=0.230,
        wins=60,
        losses=10,
    )
    assert decide_verdict([validation]).outcome == "undetermined"


def test_a_validation_win_that_the_locked_period_does_not_repeat_is_reported_as_such():
    validation = comparison(
        "validation",
        baseline_brier=0.480,
        candidate_brier=0.460,
        baseline_event=0.240,
        candidate_event=0.220,
        wins=70,
        losses=10,
    )
    locked = comparison(
        "test",
        baseline_brier=0.480,
        candidate_brier=0.500,
        baseline_event=0.240,
        candidate_event=0.260,
        wins=20,
        losses=60,
    )
    verdict = decide_verdict([validation, locked])
    assert verdict.outcome == "baseline"
    text = " ".join(verdict.reasons)
    assert "validation" in text and "locked" in text


# ── Through the real pipeline ──────────────────────────────────────────────────


def fitted_pair(tmp_path: Path):
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    common = {"version": "cmp", "min_sample_threshold": 5, "train_frac": 0.5, "val_frac": 0.25}
    baseline = fit_baseline(dataset, **common)
    candidate = fit_baseline(dataset, **{**common, "version": "cmp_c", "estimator": QUEUE_ESTIMATOR_ID})
    return dataset, baseline, candidate


def test_the_comparison_scores_both_models_on_the_same_split_and_reports_the_method(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    assert result.method == MODEL_SELECTION_METHOD
    assert {item.partition for item in result.partitions} == {"validation", "test"}
    for item in result.partitions:
        assert item.baseline.target == item.candidate.target == "final_chart_cnf"
        # One prevalence baseline for both, taken from the shared training window.
        assert item.baseline.baseline_brier == item.candidate.baseline_brier
        assert item.paired.rows_total == item.baseline.rows
    assert result.verdict.outcome in {"candidate", "baseline", "undetermined"}


def test_the_verdict_a_run_reports_is_the_verdict_the_rule_computes(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    assert result.verdict == decide_verdict(result.partitions)


def test_models_fitted_on_different_windows_are_not_comparable(tmp_path):
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    baseline = fit_baseline(dataset, version="a", min_sample_threshold=5, train_frac=0.5, val_frac=0.25)
    candidate = fit_baseline(
        dataset,
        version="b",
        min_sample_threshold=5,
        train_frac=0.7,
        val_frac=0.15,
        estimator=QUEUE_ESTIMATOR_ID,
    )
    with pytest.raises(DatasetValidationError, match="same split"):
        run_model_comparison(dataset, baseline=baseline, candidate=candidate)


def test_a_model_cannot_be_its_own_candidate(tmp_path):
    dataset, baseline, _ = fitted_pair(tmp_path)
    twin = fit_baseline(
        dataset, version="c", min_sample_threshold=5, train_frac=0.5, val_frac=0.25
    )
    with pytest.raises(DatasetValidationError, match="same estimator"):
        run_model_comparison(dataset, baseline=baseline, candidate=twin)


def test_models_fitted_for_different_targets_are_refused(tmp_path):
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    baseline = fit_baseline(dataset, version="a", min_sample_threshold=5, train_frac=0.5, val_frac=0.25)
    candidate = fit_baseline(
        dataset,
        version="b",
        min_sample_threshold=5,
        train_frac=0.5,
        val_frac=0.25,
        estimator=QUEUE_ESTIMATOR_ID,
        target="final_chart_cnf_or_rac",
    )
    with pytest.raises(DatasetValidationError, match="target"):
        run_model_comparison(dataset, baseline=baseline, candidate=candidate)


def test_a_model_fitted_on_another_file_is_not_scored_against_this_one(tmp_path):
    """The report names one dataset; a model from another file makes that name false."""
    dataset, baseline, _ = fitted_pair(tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_csv = write_balanced_dataset(other_dir, count=248)
    other_manifest = write_approved_manifest(other_csv, other_dir)
    elsewhere = load_approved_dataset(
        other_csv, other_manifest, allow_synthetic_for_testing=True
    )
    candidate = fit_baseline(
        elsewhere,
        version="b",
        min_sample_threshold=5,
        train_frac=0.5,
        val_frac=0.25,
        estimator=QUEUE_ESTIMATOR_ID,
    )
    # Same dataset id, different content: the pair is what identifies a file, not the name.
    with pytest.raises(DatasetValidationError, match="different content"):
        run_model_comparison(dataset, baseline=baseline, candidate=candidate)


def test_two_models_from_different_dataset_ids_are_refused(tmp_path):
    dataset, baseline, _ = fitted_pair(tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_csv = write_balanced_dataset(other_dir)
    other_manifest = write_approved_manifest(
        other_csv, other_dir, dataset_id="another-fixture"
    )
    elsewhere = load_approved_dataset(
        other_csv, other_manifest, allow_synthetic_for_testing=True
    )
    candidate = fit_baseline(
        elsewhere,
        version="b",
        min_sample_threshold=5,
        train_frac=0.5,
        val_frac=0.25,
        estimator=QUEUE_ESTIMATOR_ID,
    )
    with pytest.raises(DatasetValidationError, match="fitted on dataset 'another-fixture'"):
        run_model_comparison(dataset, baseline=baseline, candidate=candidate)


@pytest.mark.parametrize(
    "field,value,fragment",
    [
        ("status_mapping_version", "0.9", "different mappings"),
        ("cohort_semantics", "initial_status only", "different statuses"),
        ("feature_schema_version", "1.0.0", "different feature schemas"),
        ("outcome_classes", ("CNF", "WL"), "different label spaces"),
        ("laplace_alpha", 2.0, "different settings"),
        ("min_sample_threshold", 9, "different settings"),
    ],
)
def test_models_describing_different_contracts_are_refused(
    tmp_path, field, value, fragment
):
    """One change at a time: a mapping, schema or smoothing difference is not the model."""
    dataset, baseline, candidate = fitted_pair(tmp_path)
    mutated = replace(candidate, metadata=replace(candidate.metadata, **{field: value}))
    with pytest.raises(DatasetValidationError, match=fragment):
        run_model_comparison(dataset, baseline=baseline, candidate=mutated)


def test_matching_dates_and_counts_are_not_proof_of_the_same_rows(tmp_path):
    """Two partitions can record one window and one count while holding a different order.

    The scoring walks the baseline's frames for both models, so a candidate fitted on a
    differently ordered partition would be published with numbers from rows it never saw.
    Reversing one partition is the cheapest way to build that shape: the summaries still
    match, and pairing by position would silently compare the wrong reservations.
    """
    dataset, baseline, candidate = fitted_pair(tmp_path)
    reordered = replace(
        candidate,
        split=replace(
            candidate.split,
            val=candidate.split.val.iloc[::-1].reset_index(drop=True),
        ),
    )
    with pytest.raises(DatasetValidationError, match="but not on rows"):
        run_model_comparison(dataset, baseline=baseline, candidate=reordered)


def test_an_explicit_target_must_be_the_one_both_models_were_fitted_for(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    with pytest.raises(DatasetValidationError, match="neither artifact"):
        run_model_comparison(
            dataset,
            baseline=baseline,
            candidate=candidate,
            target="final_chart_cnf_or_rac",
        )


def test_score_rows_numbers_match_the_scorecards_the_comparison_publishes(tmp_path):
    """The paired rows and the published aggregates must come from one scoring pass."""
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    locked = result.locked_test
    assert locked is not None
    assert locked.baseline.scored_rows + locked.baseline.abstained_rows == locked.baseline.rows
    assert locked.candidate.scored_rows + locked.candidate.abstained_rows == (
        locked.candidate.rows
    )
    assert (
        locked.paired.rows_both_scored
        + locked.paired.only_baseline_scored
        + locked.paired.only_candidate_scored
        <= locked.paired.rows_total
    )


# ── Report and command line ────────────────────────────────────────────────────


def report_of(result):
    return build_comparison_report(
        result,
        dataset_id="synthetic-pipeline-fixture",
        dataset_sha256="d" * 64,
        dataset_rows=240,
        is_synthetic=True,
        generated_on="2026-10-24",
    )


def test_the_report_publishes_both_models_and_the_verdict_that_follows(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    payload = report_of(result).to_dict()
    assert payload["report_schema_version"] == COMPARISON_REPORT_SCHEMA_VERSION
    assert payload["evaluation_method"] == MODEL_SELECTION_METHOD
    assert payload["baseline"]["estimator"] == "historical_frequency_baseline"
    assert payload["candidate"]["estimator"] == QUEUE_ESTIMATOR_ID
    assert payload["verdict"]["outcome"] == result.verdict.outcome
    assert len(payload["partitions"]) == 2


def test_the_report_defines_every_comparative_number_it_publishes(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    report = report_of(result)
    payload = report.to_dict()
    definitions = set(payload["metric_definitions"])
    published = set()
    for partition in payload["partitions"]:
        published |= set(partition["comparison"])
    assert published - definitions == set()
    assert {"brier_delta", "event_brier_delta", "coverage_delta", "candidate_wins"} <= definitions


def test_the_report_states_what_the_comparison_cannot_see(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    joined = " ".join(report_of(result).limitations).lower()
    assert "same rows" in joined
    assert "no calibration" in joined
    assert "one locked period" in joined
    assert "synthetic" in joined


def test_a_verdict_of_undetermined_is_not_written_up_as_a_pass(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    report = report_of(result)
    text = " ".join(report.conclusions)
    assert result.verdict.outcome in text or "undetermined" in text
    if result.verdict.outcome != "candidate":
        assert "recommend the candidate" not in text


def test_the_report_bytes_do_not_move(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    assert report_of(result).to_json() == report_of(result).to_json()


def test_write_comparison_report_produces_the_same_json(tmp_path):
    dataset, baseline, candidate = fitted_pair(tmp_path)
    result = run_model_comparison(dataset, baseline=baseline, candidate=candidate)
    report = report_of(result)
    path = write_comparison_report(report, tmp_path / "compare.json")
    assert path.read_text(encoding="utf-8") == report.to_json()


def test_the_compare_command_runs_and_states_the_verdict(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    code = main(
        [
            "compare",
            str(csv),
            str(manifest),
            "--candidate-estimator",
            QUEUE_ESTIMATOR_ID,
            "--min-sample-threshold",
            "5",
            "--train-frac",
            "0.5",
            "--val-frac",
            "0.25",
            "--report",
            str(tmp_path / "compare.json"),
            "--generated-on",
            "2026-10-24",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Verdict:" in out
    assert "=== Model comparison report ===" in out
    payload = (tmp_path / "compare.json").read_text(encoding="utf-8")
    assert MODEL_SELECTION_METHOD in payload


def test_the_compare_command_prints_only_what_a_windows_console_can_encode(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    assert (
        main(
            [
                "compare",
                str(csv),
                str(manifest),
                "--min-sample-threshold",
                "5",
                "--train-frac",
                "0.5",
                "--val-frac",
                "0.25",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    captured.out.encode("cp1252")
    captured.err.encode("cp1252")


def test_an_unusable_candidate_estimator_is_refused_on_the_command_line(tmp_path, capsys):
    from railconfirm.training.__main__ import main

    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path)
    code = main(
        [
            "compare",
            str(csv),
            str(manifest),
            "--candidate-estimator",
            "xgboost_baseline",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "estimator" in capsys.readouterr().err.lower()

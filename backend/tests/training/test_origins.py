"""Rolling-origin evaluation, checked against hand-computed cells.

Synthetic rows only: these verify that each cutoff sees only its own past, that the
aggregate counts scoring origins and abstentions separately, and that a run which
cannot support two origins refuses instead of reporting one number as a trend.
"""

import math

import pandas as pd
import pytest

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.training.origins import describe_result, run_rolling_origins
from railconfirm.training.report import build_origin_report, write_origin_report

DATASET_FIELDS = {
    "dataset_id": "origins-fixture",
    "dataset_sha256": "a" * 64,
    "source_reference": "test",
    "approval_status": "approved",
    "is_synthetic": True,
    "mapping_version": MAPPING_VERSION,
}

# Two bookings a day; WL first appears on 2026-02-03.
DAILY = [
    ("2026-02-01", "CNF"),
    ("2026-02-02", "CNF"),
    ("2026-02-03", "WL/5"),
    ("2026-02-04", "CNF"),
]

# Same shape, but both horizons are waitlisted: every origin's baseline is a
# certainty about a class the horizon never shows.
DAILY_STABLE = [
    ("2026-02-01", "CNF"),
    ("2026-02-02", "CNF"),
    ("2026-02-03", "WL/5"),
    ("2026-02-04", "WL/5"),
]


def build_frame(daily: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for date_index, (date, label) in enumerate(daily):
        for offset in range(2):
            index = date_index * 2 + offset
            rows.append(
                {
                    "train_number": "12301",
                    "journey_date": date,
                    "class_code": "SL",
                    "quota_code": "GN",
                    "initial_status": f"GNWL/{10 + index}",
                    "current_status": "",
                    "final_chart_status": label,
                    "observation_date": "2026-01-01",
                    "booking_group_id": f"B{index:03d}",
                    "passenger_record_id": f"P{index:04d}",
                }
            )
    return pd.DataFrame(rows)


def labelled_frame() -> pd.DataFrame:
    """Origin 0 trains on two all-CNF dates, so its baseline is a certainty.

    That makes the smoothed arithmetic below checkable by hand.
    """
    return build_frame(DAILY)


def run(daily: list | None = None, **overrides):
    kwargs = {
        "min_train_dates": 2,
        "horizon_dates": 1,
        "step_dates": 1,
        "min_sample_threshold": 1,
    }
    kwargs.update(overrides)
    return run_rolling_origins(build_frame(daily or DAILY), **DATASET_FIELDS, **kwargs)


def origin(result, index: int):
    return next(score for score in result.scores if score.window.index == index)


def report_of(result, **overrides):
    fields = {
        "dataset_id": "origins-fixture",
        "dataset_sha256": "a" * 64,
        "dataset_rows": 8,
        "status_mapping_version": MAPPING_VERSION,
        "data_approval_status": "approved",
        "is_synthetic": True,
        "generated_on": "2026-05-01",
    }
    fields.update(overrides)
    return build_origin_report(result, **fields)


# ── Each cutoff refits from only its own past ──────────────────────────────────


def test_every_origin_refits_from_its_own_training_window():
    result = run()
    assert [score.window.train_rows for score in result.scores] == [4, 6]
    assert [score.cohort_count for score in result.scores] == [2, 2]
    # Four CNF and nothing else in origin 0's training block: a certainty baseline.
    assert origin(result, 0).scorecard.baseline_brier == pytest.approx(2.0, abs=1e-6)
    # 4 CNF + 2 WL by origin 1, so a 2/9 prevalence: different baselines by construction.
    assert origin(result, 1).scorecard.baseline_brier == pytest.approx(2 / 9, abs=1e-6)


def test_scores_match_the_smoothed_cells_by_hand():
    result = run()
    first = origin(result, 0).scorecard
    # counts CNF 4 → denominator 9: p_cnf 5/9, p_wl 1/9, observed WL.
    assert first.brier == pytest.approx(92 / 81, abs=1e-6)
    assert first.event_brier == pytest.approx(25 / 81, abs=1e-6)
    assert first.log_loss == pytest.approx(-math.log(1 / 9), abs=1e-6)
    assert first.beats_baseline is True
    assert first.scored_rows == 2 and first.abstained_rows == 0

    second = origin(result, 1).scorecard
    # counts CNF 4 / WL 2 → denominator 11: p_cnf 5/11, p_wl 3/11, observed CNF.
    assert second.brier == pytest.approx(48 / 121, abs=1e-6)
    assert second.event_brier == pytest.approx((5 / 11 - 1) ** 2, abs=1e-6)
    assert second.beats_baseline is False


def test_no_origin_scores_a_date_inside_its_own_training_block():
    result = run()
    for score in result.scores:
        assert set(score.window.train_dates).isdisjoint(score.window.scored_dates)
        assert set(score.window.scored["journey_date"]) == set(score.window.scored_dates)


def test_a_label_that_only_exists_later_never_lifts_an_earlier_baseline():
    """WL appears on 02-03; origin 0 trained before it and knows nothing of it."""
    result = run()
    assert origin(result, 0).rows_excluded == {}
    assert origin(result, 0).scorecard.baseline_brier == pytest.approx(2.0, abs=1e-6)
    assert origin(result, 1).scorecard.baseline_brier < (
        origin(result, 0).scorecard.baseline_brier
    )


# ── Aggregation and honesty ────────────────────────────────────────────────────


def test_the_aggregate_averages_origins_and_names_the_spread():
    result = run()
    assert result.origin_count == 2
    assert result.origins_with_scores == 2
    assert result.mean_brier == pytest.approx((92 / 81 + 48 / 121) / 2, abs=1e-6)
    assert result.mean_baseline_brier == pytest.approx((2.0 + 2 / 9) / 2, abs=1e-6)
    assert result.mean_event_brier == pytest.approx(
        (25 / 81 + (5 / 11 - 1) ** 2) / 2, abs=1e-6
    )
    assert result.brier_spread == pytest.approx((48 / 121, 92 / 81), abs=1e-6)
    assert result.rows_scored == 4 and result.rows_seen == 4


def test_one_of_two_is_reported_as_instability_not_as_a_result():
    """The whole reason to run more than one cutoff."""
    conclusions = " ".join(report_of(run()).conclusions)
    assert "1 of 2 scoring origins beat their prevalence baseline" in conclusions
    assert "not stable across cutoffs" in conclusions
    assert "1 of 2 origins beat the target-event baseline" in conclusions
    assert "Brier ranged from 0.396694 to 1.135802" in conclusions
    assert "the spread is a description of instability, not a tested difference" in conclusions


def test_the_overlapping_windows_limitation_is_always_stated():
    limitations = " ".join(report_of(run()).limitations)
    assert "not 2 independent evaluations" in limitations
    assert "refits the cohort table" in limitations
    assert "is_synthetic" in limitations
    assert "No calibration was fitted" in limitations


def test_an_origin_that_abstains_everywhere_is_counted_as_no_score():
    """A coverage failure must not be reported as a lost forecast."""
    result = run(min_sample_threshold=10_000)
    assert result.origin_count == 2
    assert result.origins_with_scores == 0
    assert result.mean_brier is None
    assert result.origins_beating_baseline == 0
    conclusions = " ".join(report_of(result).conclusions)
    assert "No origin measured anything" in conclusions
    assert "evidence about coverage, not about accuracy" in conclusions
    assert "beat their prevalence baseline" not in conclusions


def test_partial_coverage_is_named_rather_than_averaged_away():
    """A threshold only one horizon clears is a coverage finding, not a lost forecast."""
    result = run(min_sample_threshold=5)
    assert [score.scorecard.coverage for score in result.scores] == [0.0, 1.0]
    assert result.origins_with_scores == 1
    assert result.coverage_spread == (0.0, 1.0)

    report = report_of(result)
    conclusions = " ".join(report.conclusions)
    assert "1 of 2 origins produced no score at all" in conclusions
    assert "No scoring origin beat its training-period prevalence baseline" in conclusions
    assert "Coverage ranged from 0.0% to 100.0%" in conclusions
    assert "No scoring origin" in conclusions


def test_a_verdict_that_holds_at_every_cutoff_is_stated_as_holding():
    """Both horizons waitlisted: the flattering single-cutoff reading is the honest one."""
    result = run(daily=DAILY_STABLE)
    assert [score.scorecard.beats_baseline for score in result.scores] == [True, True]
    assert [score.scorecard.event_beats_baseline for score in result.scores] == [
        True,
        True,
    ]
    assert origin(result, 0).scorecard.brier == pytest.approx(92 / 81, abs=1e-6)
    # Origin 1 counts CNF 4 / WL 2 → p_cnf 5/11, p_wl 3/11, observed WL.
    assert origin(result, 1).scorecard.brier == pytest.approx(92 / 121, abs=1e-6)

    conclusions = " ".join(report_of(result).conclusions)
    assert "All 2 scoring origins beat their own training-period prevalence baseline" in conclusions
    assert "All 2 origins beat the baseline for the target event (CNF)" in conclusions


def test_describe_result_prints_one_line_per_origin_then_the_aggregate():
    text = describe_result(run())
    assert text.count("origin ") == 2
    assert "Aggregate over 2 origin(s), 2 of which produced a score" in text
    assert "1/2 beat it" in text
    assert "rows scored 4 of 4" in text
    assert "Brier ranged" in text


def test_describe_result_says_nothing_about_a_spread_it_did_not_measure():
    text = describe_result(run(min_sample_threshold=10_000))
    assert "Brier ranged" not in text
    assert "mean Brier n/a" in text


# ── Refusals ───────────────────────────────────────────────────────────────────


def test_a_dataset_supporting_one_origin_is_refused_rather_than_reported():
    with pytest.raises(DatasetValidationError, match="rolling-origin evaluation") as exc:
        run(min_train_dates=3, step_dates=2)
    assert "Only 1 origin usable" in str(exc.value)


def test_an_unfittable_training_window_names_the_origin_that_failed():
    rows = labelled_frame().to_dict("records")
    for row in rows:
        if row["journey_date"] in ("2026-02-01", "2026-02-02"):
            row["initial_status"] = "CANCELLED"
    with pytest.raises(DatasetValidationError, match="could not be fitted") as exc:
        run_rolling_origins(
            pd.DataFrame(rows),
            **DATASET_FIELDS,
            min_train_dates=2,
            horizon_dates=1,
            step_dates=1,
            min_sample_threshold=1,
        )
    assert "Origin 0 (2026-02-01..2026-02-02)" in str(exc.value)
    assert "asof_status_cancelled" in str(exc.value)


def test_an_unknown_target_is_refused_before_any_planning():
    with pytest.raises(DatasetValidationError, match="Cannot score target"):
        run(target="departure_status")


def test_the_merged_target_scores_the_wider_event_mass():
    result = run(target="final_chart_cnf_or_rac")
    assert result.to_dict()["target_event_classes"] == ["CNF", "RAC"]
    # Origin 0's cell puts 5/9 on CNF and 1/9 on RAC: the merged event is 6/9, and the
    # observed outcome (WL) failed it, so the error is the whole mass squared.
    assert origin(result, 0).scorecard.event_brier == pytest.approx((6 / 9) ** 2, abs=1e-6)


# ── Report shape ───────────────────────────────────────────────────────────────


def test_the_origin_report_publishes_planning_and_scores_together():
    payload = report_of(run()).to_dict()
    assert payload["plan"]["origin_count"] == 2
    assert payload["plan"]["min_train_dates"] == 2
    assert payload["origins"][0]["score"]["partition"] == "origin_0"
    assert payload["origins"][0]["origin"]["train_rows"] == 4
    assert payload["aggregate"]["origins_with_scores"] == 2
    assert set(payload["metric_definitions"]) >= {"brier", "event_brier", "coverage"}


def test_the_origin_report_is_reproducible(tmp_path):
    first = report_of(run()).to_json()
    assert first == report_of(run()).to_json()
    path = write_origin_report(report_of(run()), tmp_path / "origins.json")
    assert path.read_text(encoding="utf-8") == first


def test_the_summary_reads_as_a_table():
    summary = report_of(run()).summary()
    assert "=== Rolling-origin evaluation report ===" in summary
    assert (
        "2026-02-01..2026-02-02 (4 rows, 2 dates) -> 2026-02-03..2026-02-03 (2 rows)"
        in summary
    )
    assert (
        "Origins beating the base rate: 1/2 scoring origins (distribution), 1/2 (event)"
        in summary
    )

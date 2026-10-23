"""Planning successive horizons for one frozen artifact: no refitting, two horizons minimum.

Synthetic rows only. `rolling_origin_windows` refits at every cutoff, which answers how the
*fitting procedure* behaves over time. Neither path answers the question a promoted artifact
faces in service: how one fixed table scores as the calendar moves away from the period it was
fitted on. These tests pin the planner for that second question, and mainly what it refuses —
a decay claim built on one horizon, or on a booking the table already saw, is not decay.
"""

import pandas as pd
import pytest

from railconfirm.data.preprocessing import (
    MIN_HORIZONS,
    frozen_horizon_windows,
)
from railconfirm.domain.exceptions import DatasetValidationError

SIX = ["2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06"]


def frame(dates: list[str], *, per_date: int = 2, group: str | None = None) -> pd.DataFrame:
    """`per_date` bookings on each journey date, one booking per row."""
    rows = []
    for date_index, date in enumerate(dates):
        for offset in range(per_date):
            index = date_index * per_date + offset
            rows.append(
                {
                    "train_number": "12301",
                    "journey_date": date,
                    "class_code": "SL",
                    "quota_code": "GN",
                    "initial_status": f"GNWL/{10 + index}",
                    "current_status": "",
                    "final_chart_status": "CNF" if index % 2 == 0 else "WL/5",
                    "observation_date": "2026-01-01",
                    "booking_group_id": group or f"B{index:03d}",
                    "passenger_record_id": f"P{index:04d}",
                }
            )
    return pd.DataFrame(rows)


def plan(df: pd.DataFrame, fitted_to: str = "2026-02-03", **kwargs):
    return frozen_horizon_windows(df, fitted_to=fitted_to, **kwargs)


# ── The shape of a usable plan ─────────────────────────────────────────────────


def test_the_frozen_block_is_every_date_up_to_the_artifacts_own_last_fitted_date():
    result = plan(frame(SIX), fitted_to="2026-02-03", horizon_dates=1, step_dates=1)
    assert result.eligible is True
    assert result.cutoff == "2026-02-03"
    assert result.train_dates == ("2026-02-01", "2026-02-02", "2026-02-03")
    assert sorted(result.train["journey_date"].unique()) == [
        "2026-02-01",
        "2026-02-02",
        "2026-02-03",
    ]


def test_horizons_are_successive_blocks_after_the_cutoff_and_the_table_never_moves():
    result = plan(frame(SIX), fitted_to="2026-02-02", horizon_dates=1, step_dates=1)
    assert [window.scored_dates for window in result.horizons] == [
        ("2026-02-03",),
        ("2026-02-04",),
        ("2026-02-05",),
        ("2026-02-06",),
    ]
    # One artifact, one table: every horizon is scored by the same frozen training block.
    assert all(window.train_dates == result.train_dates for window in result.horizons)


def test_horizon_dates_sets_the_width_and_step_dates_the_distance_between_cutoffs():
    result = plan(frame(SIX), fitted_to="2026-02-02", horizon_dates=2, step_dates=2)
    assert [window.scored_dates for window in result.horizons] == [
        ("2026-02-03", "2026-02-04"),
        ("2026-02-05", "2026-02-06"),
    ]


def test_a_step_wider_than_the_horizon_leaves_dates_unscored_rather_than_double_counted():
    result = plan(
        frame(SIX + ["2026-02-07", "2026-02-08"]),
        fitted_to="2026-02-02",
        horizon_dates=1,
        step_dates=2,
    )
    assert [window.scored_dates for window in result.horizons] == [
        ("2026-02-03",),
        ("2026-02-05",),
        ("2026-02-07",),
    ]


def test_no_horizon_ever_scores_a_date_the_artifact_was_fitted_on():
    result = plan(frame(SIX), fitted_to="2026-02-04", horizon_dates=1, step_dates=1)
    for window in result.horizons:
        assert window.scored_dates > result.train_dates


def test_the_planner_hands_back_frames_without_its_own_helper_columns():
    result = plan(frame(SIX), fitted_to="2026-02-03", horizon_dates=1, step_dates=1)
    for name in ("_partition_date", "_original_index"):
        assert name not in result.train.columns
        assert name not in result.horizons[0].scored.columns


def test_row_indices_are_positional_so_a_label_lookup_cannot_collide():
    result = plan(frame(SIX), fitted_to="2026-02-03", horizon_dates=1, step_dates=1)
    assert list(result.train.index) == list(range(len(result.train)))
    assert list(result.horizons[0].scored.index) == list(range(result.horizons[0].scored_rows))


# ── Refusals that are the point of the exercise ────────────────────────────────


def test_one_horizon_is_not_a_decay_curve_and_produces_no_windows_at_all():
    result = plan(
        frame(["2026-02-01", "2026-02-02", "2026-02-03"]),
        fitted_to="2026-02-02",
        horizon_dates=1,
        step_dates=1,
    )
    assert result.eligible is False
    assert result.horizons == ()
    assert any(str(MIN_HORIZONS) in reason for reason in result.reasons)


def test_the_minimum_horizon_count_is_stated_rather_than_implied():
    result = plan(
        frame(["2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04"]),
        fitted_to="2026-02-03",
        horizon_dates=1,
        step_dates=1,
    )
    assert result.eligible is False
    assert "1 horizon" in " ".join(result.reasons)


def test_a_cutoff_after_the_last_date_in_the_file_has_nothing_to_score():
    result = plan(frame(SIX), fitted_to="2026-02-06", horizon_dates=1, step_dates=1)
    assert result.eligible is False
    assert result.horizons == ()
    assert any("no dates after the cutoff" in reason.lower() for reason in result.reasons)


def test_a_file_that_starts_after_the_artifacts_own_period_cannot_show_its_decay():
    """The frozen block has to exist in this file, or the baseline has no fitted population."""
    result = plan(
        frame(["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04"]),
        fitted_to="2026-02-03",
        horizon_dates=1,
        step_dates=1,
    )
    assert result.eligible is False
    assert any("before this file" in reason for reason in result.reasons)


def test_the_gap_rule_keeps_dates_beside_the_cutoff_out_of_the_first_horizon():
    result = plan(
        frame(SIX),
        fitted_to="2026-02-02",
        horizon_dates=1,
        step_dates=1,
        gap_days=3,
    )
    assert result.eligible is False
    assert any("gap" in reason for reason in result.reasons)


def test_a_horizon_too_thin_to_score_anything_is_refused_not_reported_as_zero():
    result = plan(
        frame(SIX),
        fitted_to="2026-02-04",
        horizon_dates=1,
        step_dates=1,
        min_scored_rows=3,
    )
    assert result.eligible is False
    assert any("below the required 3" in reason for reason in result.reasons)


def test_a_booking_the_frozen_table_already_saw_cannot_be_its_own_evidence():
    """One group spanning the cutoff puts the outcome in the fit and the score at once."""
    spanning = pd.concat(
        [
            frame(SIX[:3], per_date=1),
            frame(["2026-02-04"], per_date=1, group="B000"),
        ],
        ignore_index=True,
    )
    result = plan(spanning, fitted_to="2026-02-03", horizon_dates=1, step_dates=1)
    assert result.eligible is False
    assert result.horizons == ()
    assert any("booking_group_id" in reason for reason in result.reasons)


def test_a_plan_that_cannot_complete_its_last_horizon_keeps_the_ones_it_finished():
    """A short tail is a reason to stop, not a reason to score four dates as two."""
    result = plan(
        frame(SIX),
        fitted_to="2026-02-02",
        horizon_dates=2,
        step_dates=2,
    )
    assert result.eligible is True
    assert len(result.horizons) == 2


@pytest.mark.parametrize("fitted_to", ["", "  ", "02/03/2026", "2026-13-01", "not-a-date"])
def test_a_cutoff_that_is_not_an_iso_date_is_refused_before_any_arithmetic(fitted_to):
    with pytest.raises(DatasetValidationError, match="fitted_to"):
        plan(frame(SIX), fitted_to=fitted_to)


def test_a_missing_date_column_is_refused():
    with pytest.raises(DatasetValidationError, match="journey_date"):
        frozen_horizon_windows(pd.DataFrame({"x": [1]}), fitted_to="2026-02-03")


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "2"])
def test_horizon_dates_must_be_a_positive_integer(bad):
    with pytest.raises(DatasetValidationError, match="horizon_dates"):
        plan(frame(SIX), horizon_dates=bad)


@pytest.mark.parametrize("bad", [0, -1, True, 1.5, "2"])
def test_step_dates_must_be_a_positive_integer(bad):
    with pytest.raises(DatasetValidationError, match="step_dates"):
        plan(frame(SIX), step_dates=bad)


def test_a_step_shorter_than_the_horizon_would_score_the_same_outcome_twice():
    with pytest.raises(DatasetValidationError, match="overlap"):
        plan(frame(SIX), horizon_dates=2, step_dates=1)


def test_a_negative_gap_is_a_usage_error_not_a_widening():
    with pytest.raises(DatasetValidationError, match="gap_days"):
        plan(frame(SIX), gap_days=-1)


@pytest.mark.parametrize("bad", [0, -3, True])
def test_min_scored_rows_must_be_positive(bad):
    with pytest.raises(DatasetValidationError, match="min_scored_rows"):
        plan(frame(SIX), min_scored_rows=bad)


def test_min_horizons_below_two_would_ask_for_the_single_split_the_command_replaces():
    with pytest.raises(DatasetValidationError, match="min_horizons"):
        plan(frame(SIX), min_horizons=1)


# ── What a reader and a report get ────────────────────────────────────────────


def test_the_plan_describes_itself_as_one_frozen_table_scored_forward():
    result = plan(frame(SIX), fitted_to="2026-02-02", horizon_dates=1, step_dates=1)
    assert result.describe() == (
        "frozen block 2026-02-01..2026-02-02 (4 rows, 2 dates), then "
        f"{len(result.horizons)} horizons of 1 date each"
    )


def test_the_payload_names_the_cutoff_the_horizons_and_the_unchanged_block():
    result = plan(frame(SIX), fitted_to="2026-02-02", horizon_dates=1, step_dates=1)
    payload = result.to_dict()
    assert payload["cutoff"] == "2026-02-02"
    assert payload["train_dates"] == 2
    assert payload["train_rows"] == 4
    assert payload["horizon_count"] == len(result.horizons)
    assert payload["horizons"][0]["index"] == 0
    assert payload["horizons"][-1]["scored_end"] == "2026-02-06"
    # The same block is named for every horizon, because nothing is refitted.
    assert {window["train_end"] for window in payload["horizons"]} == {"2026-02-02"}

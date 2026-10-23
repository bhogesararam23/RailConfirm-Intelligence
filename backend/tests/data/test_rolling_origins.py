"""Rolling-origin window planning: whole dates, two origins minimum, no double scoring.

Synthetic rows only. These tests check what the planner refuses and why, because the
value of rolling-origin evaluation is that it cannot be produced from one cutoff.
"""

import pandas as pd
import pytest

from railconfirm.data.preprocessing import (
    OriginWindow,
    rolling_origin_windows,
)
from railconfirm.domain.exceptions import DatasetValidationError


def frame(dates: list[str], *, per_date: int = 2, group_prefix: str | None = None) -> pd.DataFrame:
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
                    "booking_group_id": (
                        f"{group_prefix}{index}" if group_prefix else f"B{index:03d}"
                    ),
                    "passenger_record_id": f"P{index:04d}",
                }
            )
    return pd.DataFrame(rows)


SIX = ["2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04", "2026-02-05", "2026-02-06"]


def plan(df: pd.DataFrame, **kwargs):
    return rolling_origin_windows(df, **kwargs)


# ── The shape of a usable plan ─────────────────────────────────────────────────


def test_origins_start_at_the_minimum_training_block_and_grow_by_the_step():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=1, step_dates=1)
    assert result.eligible is True
    assert [window.train_dates for window in result.windows[:3]] == [
        ("2026-02-01", "2026-02-02"),
        ("2026-02-01", "2026-02-02", "2026-02-03"),
        ("2026-02-01", "2026-02-02", "2026-02-03", "2026-02-04"),
    ]
    assert [window.scored_dates for window in result.windows[:3]] == [
        ("2026-02-03",),
        ("2026-02-04",),
        ("2026-02-05",),
    ]


def test_the_last_date_can_be_scored_but_nothing_beyond_it():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=1, step_dates=1)
    assert len(result.windows) == 4  # scored dates 03,04,05,06
    assert result.windows[-1].scored_dates == ("2026-02-06",)


def test_no_origin_ever_scores_a_date_it_trained_on():
    result = plan(frame(SIX), min_train_dates=3, horizon_dates=1, step_dates=1)
    for window in result.windows:
        assert set(window.train_dates).isdisjoint(window.scored_dates)
        assert max(window.train_dates) < min(window.scored_dates)


def test_scored_windows_do_not_overlap_each_other():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=2, step_dates=2)
    scored = [date for window in result.windows for date in window.scored_dates]
    assert len(scored) == len(set(scored))


def test_frames_hold_only_their_own_dates():
    result = plan(frame(SIX, per_date=3), min_train_dates=2, horizon_dates=1, step_dates=1)
    first = result.windows[0]
    assert set(first.train["journey_date"]) == {"2026-02-01", "2026-02-02"}
    assert set(first.scored["journey_date"]) == {"2026-02-03"}
    assert first.train_rows == 6 and first.scored_rows == 3
    assert list(first.train.index) == list(range(first.train_rows))


def test_a_step_wider_than_the_horizon_leaves_dates_unscored_by_design():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=1, step_dates=2)
    assert [window.scored_dates for window in result.windows] == [
        ("2026-02-03",),
        ("2026-02-05",),
    ]


def test_plan_and_windows_serialise_without_frames():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=1, step_dates=1)
    payload = result.to_dict()
    assert payload["eligible"] is True
    assert payload["origin_count"] == 4
    assert payload["origins"][0]["train_rows"] == 4
    assert "train" not in payload["origins"][0]
    assert isinstance(result.windows[0], OriginWindow)
    assert "origin 0: train 2026-02-01..2026-02-02" in result.windows[0].describe()


def test_planning_is_deterministic():
    df = frame(SIX)
    assert plan(df).to_dict() == plan(df.copy()).to_dict()


def test_row_order_does_not_move_a_boundary():
    df = frame(SIX)
    shuffled = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
    assert [w.to_dict() for w in plan(shuffled).windows] == [
        w.to_dict() for w in plan(df).windows
    ]


# ── Refusals ───────────────────────────────────────────────────────────────────


def test_one_usable_origin_is_not_rolling_evaluation():
    """A step that leaves only one horizon is the single-cutoff case, named as such."""
    result = plan(frame(SIX[:5]), min_train_dates=2, horizon_dates=1, step_dates=3)
    assert result.eligible is False
    assert result.windows == ()
    assert "Only 1 origin usable" in result.reasons[0]
    assert "`chronological_split` already" in result.reasons[0]


def test_too_few_dates_for_even_one_origin():
    result = plan(frame(SIX[:2]), min_train_dates=2, horizon_dates=1)
    assert result.eligible is False
    assert "2 distinct journey_date values" in result.reasons[0]


def test_a_gap_the_calendar_cannot_honour_blocks_the_plan():
    result = plan(frame(SIX), min_train_dates=2, horizon_dates=1, step_dates=1, gap_days=5)
    assert result.eligible is False
    assert "inside the 5-day gap" in result.reasons[0]
    assert "Origin 0" in result.reasons[0]


def test_a_scarce_scored_window_is_refused_rather_than_average_in():
    df = pd.concat(
        [frame(SIX), frame(["2026-02-07"], per_date=1)], ignore_index=True
    )
    result = plan(df, min_train_dates=2, horizon_dates=1, step_dates=1, min_scored_rows=2)
    assert result.eligible is False
    assert "below the required 2" in result.reasons[0]


def test_a_booking_on_both_sides_of_a_cutoff_blocks_everything():
    """The same outcome in the fit and the score of one origin is leakage by repetition."""
    df = frame(SIX)
    # Put B000 (journey date 02-01) also on 02-03, the first scored date.
    crossing = df[df["booking_group_id"] == "B000"].copy()
    crossing["journey_date"] = "2026-02-03"
    result = plan(pd.concat([df, crossing], ignore_index=True), min_train_dates=2)
    assert result.eligible is False
    assert "both sides of origin 0's cutoff" in result.reasons[0]
    assert result.windows == ()


def test_a_booking_spanning_two_scored_windows_is_caught_at_the_later_cutoff():
    """No booking can be scored twice, because earlier horizons become later training data.

    ``step_dates >= horizon_dates`` puts every date origin *k* scores inside origin
    *k+1*'s training block, so a booking appearing in two scored windows necessarily
    straddles the later cutoff, and the crossing rule is what refuses it."""
    df = frame(SIX)
    crossing = df[df["booking_group_id"] == "B004"].copy()  # journey 2026-02-03
    crossing["journey_date"] = "2026-02-04"
    result = plan(
        pd.concat([df, crossing], ignore_index=True),
        min_train_dates=2,
        horizon_dates=1,
        step_dates=1,
    )
    assert result.eligible is False
    assert "both sides of origin 1's cutoff" in result.reasons[0]
    assert "B004" in result.reasons[0]


def test_an_ambiguous_date_is_refused_not_guessed():
    df = frame(SIX)
    df.loc[0, "journey_date"] = "02/03/2026"
    with pytest.raises(DatasetValidationError, match="not ISO YYYY-MM-DD"):
        plan(df)


def test_a_frame_without_the_date_column_is_refused():
    with pytest.raises(DatasetValidationError, match="journey_date"):
        plan(frame(SIX).drop(columns=["journey_date"]))


@pytest.mark.parametrize(
    "kwargs,fragment",
    [
        ({"min_train_dates": 0}, "min_train_dates"),
        ({"min_train_dates": True}, "min_train_dates"),
        ({"horizon_dates": -1}, "horizon_dates"),
        ({"step_dates": 0}, "step_dates"),
        ({"min_scored_rows": 0}, "min_scored_rows"),
        ({"gap_days": -1}, "gap_days"),
        ({"horizon_dates": 2, "step_dates": 1}, "overlap two scored windows"),
    ],
)
def test_argument_rules_are_stated_not_assumed(kwargs, fragment):
    with pytest.raises(DatasetValidationError, match=fragment):
        plan(frame(SIX), **kwargs)


def test_a_custom_date_column_is_honoured():
    df = frame(SIX)
    df = df.rename(columns={"journey_date": "travel_day"})
    result = plan(df, date_column="travel_day", min_train_dates=2)
    assert result.eligible is True
    assert result.date_column == "travel_day"

"""Tests for as-of feature construction and chronological partitioning.

Every fixture here is synthetic. They check that a split can be trusted to hold
the future back, and that an unusable one says so.
"""

from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.preprocessing import (
    ASOF_STATUS_FEATURE,
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    LABEL_COLUMNS,
    asof_statuses,
    assert_no_label_columns,
    chronological_split,
    extract_features,
    feature_frame,
    frozen_horizon_windows,
    require_status_columns,
    rolling_origin_windows,
    strip_labels,
)
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.inference.baseline import COHORT_FEATURES

ROWS = [
    {
        "train_number": "12301",
        "journey_date": f"2026-10-0{day}",
        "class_code": "SL",
        "quota_code": "GN",
        "initial_status": f"GNWL/{30 + index}",
        "current_status": f"GNWL/{10 + index}",
        "final_chart_status": "CNF" if index % 2 else "WL/8",
        "observation_date": f"2026-09-2{index % 9}",
    }
    for index, day in enumerate([1, 2, 3, 4, 5, 6, 7, 8], start=0)
]


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def dates(count: int) -> pd.DataFrame:
    """One row per distinct journey date, in ascending order."""
    return frame(
        [
            {
                "journey_date": f"2026-01-{day:02d}",
                "initial_status": "GNWL/10",
                "final_chart_status": "CNF",
            }
            for day in range(1, count + 1)
        ]
    )


# ── Feature construction ───────────────────────────────────────────────────────


def test_features_expose_the_declared_schema():
    features = feature_frame(strip_labels(frame(ROWS)))
    assert list(features.columns) == list(FEATURE_COLUMNS)
    # Pinned so a bump is a decision: 3.0.0 names the derived status columns asof_*
    # and falls back to initial_status per row when current_status is blank.
    assert FEATURE_SCHEMA_VERSION == "3.0.0"


def test_the_features_an_artifact_declares_exist_in_this_schema():
    """Artifacts name consumed features with these column names.

    The check crosses the boundary on purpose: a declaration that names a column
    this module does not produce would be unverifiable at load time."""
    assert set(COHORT_FEATURES) <= set(FEATURE_COLUMNS)
    assert ASOF_STATUS_FEATURE in FEATURE_COLUMNS


def test_features_never_read_the_outcome_label():
    """Regression: features were built from the same frame the label lived in."""
    with pytest.raises(DatasetValidationError, match="label columns"):
        extract_features(frame(ROWS))


@pytest.mark.parametrize("label", LABEL_COLUMNS)
def test_each_label_column_is_blocked(label):
    row = dict(ROWS[0])
    row.pop("final_chart_status", None)
    row[label] = "CNF"
    with pytest.raises(DatasetValidationError, match=label):
        extract_features(frame([row]))


def test_assert_no_label_columns_passes_on_a_clean_frame():
    clean = feature_frame(strip_labels(frame(ROWS)))
    assert assert_no_label_columns(clean, where="test") is None


def test_strip_labels_removes_every_outcome_column():
    stripped = strip_labels(frame(ROWS))
    assert "final_chart_status" not in stripped.columns
    assert "initial_status" in stripped.columns
    assert len(stripped) == len(ROWS)


def test_missing_positions_stay_unknown_rather_than_zero():
    """Regression: positions were fabricated as 0, which reads as "first in queue"."""
    rows = [{"journey_date": "2026-10-01", "initial_status": "GNWL", "current_status": "CNF"}]
    features = extract_features(frame(rows))
    assert pd.isna(features["init_position"].iloc[0])
    assert pd.isna(features["asof_position"].iloc[0])
    assert pd.isna(features["queue_ratio"].iloc[0])


def test_positions_are_parsed_when_present():
    rows = [
        {"journey_date": "2026-10-01", "initial_status": "GNWL/40", "current_status": "GNWL/10"}
    ]
    features = extract_features(frame(rows))
    assert features["init_position"].iloc[0] == 40
    assert features["asof_position"].iloc[0] == 10
    assert features["queue_ratio"].iloc[0] == pytest.approx(0.25)


def test_invalid_position_token_is_unknown_not_zero():
    rows = [{"journey_date": "2026-10-01", "initial_status": "GNWL/0", "current_status": "CNF"}]
    features = extract_features(frame(rows))
    assert pd.isna(features["init_position"].iloc[0])


# ── The as-of status rule, shared by fitting, scoring and serving ──────────────


def test_the_asof_status_is_the_current_observation_when_recorded():
    """A booking that moved does not stay described by the status it was bought in."""
    statuses = asof_statuses(frame([{"initial_status": "GNWL/40", "current_status": "RAC 6"}]))
    assert statuses[0].normalized.value == "RAC"


@pytest.mark.parametrize("blank", ["", None, pd.NA, "NA", "null", "  "])
def test_a_blank_current_status_falls_back_to_the_booked_status(blank):
    """Regression: an empty current_status became UNKNOWN and abstained.

    A source that recorded no later look has not made the status unknown; the last
    status it saw was the initial one, and pretending otherwise would abstain on
    most of a legitimately sparse file."""
    statuses = asof_statuses(frame([{"initial_status": "GNWL/40", "current_status": blank}]))
    assert statuses[0].normalized.value == "WL"


def test_an_unmappable_asof_status_is_unknown_rather_than_the_initial_status():
    """The fallback is for absence, not for values the mapping cannot read."""
    statuses = asof_statuses(frame([{"initial_status": "GNWL/40", "current_status": "WEIRD"}]))
    assert statuses[0].normalized.value == "UNKNOWN"


def test_a_frame_with_neither_status_column_is_refused():
    with pytest.raises(DatasetValidationError, match="as-of status"):
        asof_statuses(frame([{"journey_date": "2026-10-01", "class_code": "SL"}]))


def test_require_status_columns_names_what_it_needs():
    with pytest.raises(DatasetValidationError, match="initial_status"):
        require_status_columns(frame([{"class_code": "SL"}]), where="fit_cohorts")


def test_a_current_status_only_frame_still_has_an_asof_status():
    statuses = asof_statuses(frame([{"current_status": "RLWL/3"}]))
    assert statuses[0].normalized.value == "WL"


def test_an_initial_status_only_frame_is_its_own_asof_status():
    statuses = asof_statuses(frame([{"initial_status": "RLWL/3"}]))
    assert statuses[0].normalized.value == "WL"


def test_extract_features_uses_the_same_asof_rule():
    """The feature frame cannot disagree with the function the fitter calls."""
    rows = [
        {"initial_status": "GNWL/40", "current_status": "RAC 6"},
        {"initial_status": "GNWL/40", "current_status": ""},
    ]
    features = extract_features(frame(rows))
    assert list(features["asof_normalized"]) == ["RAC", "WL"]
    assert list(features["init_normalized"]) == ["WL", "WL"]


def test_lead_days_is_null_for_unparseable_dates():
    """Regression: errors="coerce" then fillna(0) asserted a zero-day lead."""
    rows = [
        {
            "journey_date": "2026-10-01",
            "observation_date": "not-a-date",
            "initial_status": "GNWL/10",
        }
    ]
    with pytest.raises(DatasetValidationError, match="not ISO YYYY-MM-DD"):
        extract_features(frame(rows))


def test_lead_days_is_null_for_missing_observation_date():
    rows = [{"journey_date": "2026-10-01", "initial_status": "GNWL/10"}]
    features = extract_features(frame(rows))
    assert pd.isna(features["lead_days"].iloc[0])


def test_post_departure_observation_is_dropped_not_clamped_to_zero():
    """A negative lead time is leakage; clamping it to 0 hides an impossible record."""
    rows = [
        {
            "journey_date": "2026-10-01",
            "observation_date": "2026-10-05",
            "initial_status": "GNWL/10",
        }
    ]
    features = extract_features(frame(rows))
    assert pd.isna(features["lead_days"].iloc[0])


def test_lead_days_computed_for_valid_records():
    rows = [
        {
            "journey_date": "2026-10-10",
            "observation_date": "2026-10-01",
            "initial_status": "GNWL/10",
        }
    ]
    assert extract_features(frame(rows))["lead_days"].iloc[0] == 9


def test_features_require_initial_status():
    with pytest.raises(DatasetValidationError, match="initial_status"):
        extract_features(frame([{"journey_date": "2026-10-01"}]))


def test_feature_extraction_leaves_the_input_untouched():
    source = strip_labels(frame(ROWS))
    before = source.copy()
    extract_features(source)
    pd.testing.assert_frame_equal(source, before)


# ── Chronological splitting ────────────────────────────────────────────────────


@pytest.mark.parametrize("count", [1, 2])
def test_fewer_than_three_dates_cannot_evaluate(count):
    """Regression: everything was returned as train with val and test empty,
    which read as a successful split."""
    result = chronological_split(dates(count))
    assert result.eligible is False
    assert "needs at least three distinct journey_date values" in result.reasons[0]
    assert any("No partition was produced" in reason for reason in result.reasons)
    assert result.train.empty
    assert result.val.empty
    assert result.test.empty


def test_three_dates_split_into_three_partitions():
    """Regression: at exactly three dates the test partition came out empty."""
    result = chronological_split(dates(3))
    assert result.eligible is True, result.reasons
    assert [partition.row_count for partition in result.partitions] == [1, 1, 1]
    assert result.test["journey_date"].tolist() == ["2026-01-03"]


def test_split_never_leaves_a_partition_empty_for_adequate_data():
    for count in range(3, 26):
        result = chronological_split(dates(count))
        assert result.eligible is True, (count, result.reasons)
        assert all(partition.row_count > 0 for partition in result.partitions), count


def test_partitions_are_chronologically_ordered_and_disjoint():
    result = chronological_split(dates(10))
    train_max = max(result.train["journey_date"])
    val_min = min(result.val["journey_date"])
    val_max = max(result.val["journey_date"])
    test_min = min(result.test["journey_date"])
    assert train_max < val_min
    assert val_max < test_min
    assert len(result.train) + len(result.val) + len(result.test) == 10


def test_date_ties_stay_in_one_partition():
    """Rows sharing a date must not straddle a boundary."""
    df = frame(
        [
            {
                "journey_date": f"2026-01-{day:02d}",
                "initial_status": f"GNWL/{10 + offset}",
                "final_chart_status": "CNF",
            }
            for day in range(1, 6)
            for offset in range(3)
        ]
    )
    result = chronological_split(df)
    assert result.eligible is True
    for partition in (result.train, result.val, result.test):
        counts = partition["journey_date"].value_counts()
        assert set(counts.tolist()) <= {3}


def test_duplicate_rows_are_kept_deterministically():
    df = pd.concat([dates(5), dates(5).iloc[[0]]], ignore_index=True)
    first = chronological_split(df)
    second = chronological_split(df)
    pd.testing.assert_frame_equal(first.train, second.train)
    assert len(first.train) == len(second.train)


def test_split_is_independent_of_input_row_order():
    df = dates(9)
    forward = chronological_split(df)
    shuffled = chronological_split(df.sample(frac=1.0, random_state=7))
    assert list(forward.test["journey_date"]) == list(shuffled.test["journey_date"])
    assert list(forward.train["journey_date"]) == list(shuffled.train["journey_date"])


def test_booking_group_crossing_partitions_blocks_the_split():
    """The same booking on two dates would appear in train and test alike."""
    df = frame(
        [
            {"journey_date": "2026-01-01", "booking_group_id": "B1", "initial_status": "GNWL/5"},
            {"journey_date": "2026-01-02", "booking_group_id": "B1", "initial_status": "GNWL/4"},
            {"journey_date": "2026-01-03", "booking_group_id": "B2", "initial_status": "GNWL/9"},
            {"journey_date": "2026-01-04", "booking_group_id": "B3", "initial_status": "GNWL/2"},
        ]
    )
    result = chronological_split(df)
    assert result.eligible is False
    # B1's two dates both fall in training under the default fractions, so the split is
    # blocked for the other reason: one booking cannot own two journey dates at all.
    assert any(
        "more than one date inside a single partition" in reason for reason in result.reasons
    )
    assert not any("not confined to one partition" in reason for reason in result.reasons)


def test_a_group_spanning_two_partitions_is_reported_as_leakage():
    """A booking split across the boundary is the reason the rule names first.

    Six dates put 2026-01-01 in training and 2026-01-06 in test. The refusal must say
    that the booking crosses the boundary, because that is what would put one outcome in
    the fit and in the evaluation; the earlier message claimed this for any booking seen
    twice, including two dates in the same partition.
    """
    df = frame(
        [
            {"journey_date": f"2026-01-{day:02d}", "booking_group_id": group}
            for day, group in zip(range(1, 7), ["B1", "B2", "B3", "B4", "B5", "B1"], strict=True)
        ]
    )
    result = chronological_split(df)
    assert result.eligible is False
    assert any("not confined to one partition" in reason for reason in result.reasons)
    assert not any(
        "more than one date inside a single partition" in reason for reason in result.reasons
    )


def test_gap_days_enforces_separation_from_the_training_period():
    df = dates(4)
    tight = chronological_split(df, train_frac=0.5, val_frac=0.2)
    assert tight.eligible is True
    gapped = chronological_split(df, train_frac=0.5, val_frac=0.2, gap_days=3)
    assert gapped.eligible is False
    assert any("Test starts" in reason for reason in gapped.reasons)


def test_min_rows_per_partition_is_enforced():
    result = chronological_split(dates(3), min_rows_per_partition=5)
    assert result.eligible is False
    assert any("below the required 5" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    "kwargs,fragment",
    [
        ({"train_frac": 0.0}, "below 1 with both positive"),
        ({"train_frac": 0.8, "val_frac": 0.3}, "below 1 with both positive"),
        ({"min_rows_per_partition": 0}, "positive integer"),
        ({"gap_days": -1}, "gap_days cannot be negative"),
    ],
)
def test_invalid_split_parameters_are_rejected(kwargs, fragment):
    with pytest.raises(DatasetValidationError, match=fragment):
        chronological_split(dates(10), **kwargs)


@pytest.mark.parametrize("value", ["2", 2.5, True])
def test_a_gap_that_is_not_a_whole_number_of_days_is_refused(value):
    """The gap is a day count, and a count is an int in every planner.

    A string raised ``TypeError`` from the comparison that used it, so the caller saw a
    crash that named neither the argument nor the function. A float passed the negative
    check and was compared against a whole-day separation as if a fraction of a day were
    meaningful, and ``True`` — an int in Python — was read as a one-day gap by a caller
    who wrote it as a flag.
    """
    with pytest.raises(DatasetValidationError, match="whole number of days"):
        chronological_split(dates(10), gap_days=value)
    with pytest.raises(DatasetValidationError, match="whole number of days"):
        rolling_origin_windows(dates(10), gap_days=value)
    with pytest.raises(DatasetValidationError, match="whole number of days"):
        frozen_horizon_windows(dates(10), fitted_to="2026-01-01", gap_days=value)


@pytest.mark.parametrize("value", ["5", 2.5])
def test_a_row_floor_that_is_not_a_whole_number_is_refused(value):
    """A fraction as a row floor thresholds a count against a number that is not one."""
    with pytest.raises(DatasetValidationError, match="min_rows_per_partition"):
        chronological_split(dates(10), min_rows_per_partition=value)


@pytest.mark.parametrize(
    "kwargs", [{"train_frac": "0.7"}, {"val_frac": None}, {"train_frac": True}]
)
def test_a_split_fraction_that_is_not_a_number_is_refused(kwargs):
    """The fractions are compared as numbers, so a non-number is refused as one."""
    with pytest.raises(DatasetValidationError, match="fraction between 0 and 1"):
        chronological_split(dates(10), **kwargs)


def test_split_without_date_column_reports_the_column():
    with pytest.raises(DatasetValidationError, match="journey_date"):
        chronological_split(frame([{"some_col": 1}]))


def test_split_rejects_unparseable_and_missing_dates():
    with pytest.raises(DatasetValidationError, match="not ISO YYYY-MM-DD"):
        chronological_split(frame([{"journey_date": value} for value in ["01/02/2026", "x", "y"]]))
    with pytest.raises(DatasetValidationError, match="no journey_date"):
        chronological_split(frame([{"journey_date": None}, {"journey_date": "2026-01-02"}]))


def test_boundary_report_records_counts_and_dates():
    report = chronological_split(dates(6)).boundary_report
    assert "train: 4 rows" in report
    assert "test:" in report
    assert ".." in report


def test_split_of_the_synthetic_fixture_reports_its_own_limits():
    df = load_dataset_file(Path(__file__).parent.parent / "fixtures" / "synthetic_dataset.csv")
    result = chronological_split(df)
    # Five distinct dates: the split is real but thin, and says so in the counts.
    assert result.eligible is True
    assert [partition.row_count for partition in result.partitions] == [4, 1, 1]
    assert result.partitions[-1].start_date == "2026-10-05"

"""Tests for dataset validation: schema, quality, leakage and eligibility.

Fixtures are synthetic and constructed inline; they exercise the checks, not any
claim about railway behaviour.
"""

from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.validator import (
    MISSING_TOKENS,
    REQUIRED_COLUMNS,
    EligibilityThresholds,
    assess_dataset,
    validate_dataset,
)

BASE_ROWS = [
    {
        "train_number": "12301",
        "journey_date": "2026-10-01",
        "class_code": "SL",
        "quota_code": "GN",
        "initial_status": "GNWL/10",
        "final_chart_status": "CNF",
        "observation_date": "2026-09-25",
    },
    {
        "train_number": "12301",
        "journey_date": "2026-10-02",
        "class_code": "3A",
        "quota_code": "GN",
        "initial_status": "RLWL/5",
        "final_chart_status": "RAC 2",
        "observation_date": "2026-09-26",
    },
]


def frame(
    rows: list[dict], columns: tuple[str, ...] | None = None
) -> pd.DataFrame:
    """Build a frame keeping every key present unless columns are pinned."""
    if columns is not None:
        ordered = list(columns)
    else:
        extra = [key for row in rows for key in row if key not in REQUIRED_COLUMNS]
        ordered = [*REQUIRED_COLUMNS, *extra]
    return pd.DataFrame(rows, columns=list(dict.fromkeys(ordered)))


def synthetic_rules(**overrides) -> EligibilityThresholds:
    """Small thresholds so a handful of rows can reach a verdict in tests."""
    base = {
        "min_rows": 2,
        "min_valid_rows": 1,
        "min_valid_fraction": 0.5,
        "min_distinct_journey_dates": 1,
        "min_distinct_labeled_bookings": 1,
        "min_label_diversity": 1,
        "max_duplicate_fraction": 0.5,
        "min_confirmed_share": 0.0,
        "max_confirmed_share": 1.0,
    }
    base.update(overrides)
    return EligibilityThresholds(**base)


def validate(rows: list[dict], *, columns: tuple[str, ...] | None = None, **kwargs):
    limits = kwargs.pop("thresholds", None)
    return validate_dataset(
        frame(rows, columns=columns), thresholds=limits or synthetic_rules(), **kwargs
    )


def assess(rows: list[dict], **kwargs):
    """The same verdict plus the rows that survived it."""
    limits = kwargs.pop("thresholds", None)
    return assess_dataset(
        frame(rows, columns=kwargs.pop("columns", None)),
        thresholds=limits or synthetic_rules(),
        **kwargs,
    )


# ── Structural validity ────────────────────────────────────────────────────────


def test_complete_small_dataset_is_structurally_valid_but_not_eligible_by_default():
    """The default thresholds are the point: a 6-row file must not pass as usable."""
    df = load_dataset_file(Path(__file__).parent.parent / "fixtures" / "synthetic_dataset.csv")
    report = validate_dataset(df)
    assert report.structurally_valid is True
    assert report.total_rows == 6
    assert report.valid_rows == 6
    assert report.technically_eligible is False
    assert any("provisional minimum" in finding for finding in report.eligibility_findings)


def test_missing_required_columns_blocks_everything():
    report = validate_dataset(pd.DataFrame({"train_number": ["12301"], "journey_date": ["2026-10-01"]}))
    assert report.structurally_valid is False
    assert report.technically_eligible is False
    assert set(report.missing_columns) == set(REQUIRED_COLUMNS) - {"train_number", "journey_date"}
    assert report.rejection_reasons["missing_required_columns"] == 1


def test_empty_frame_is_not_valid():
    report = validate_dataset(frame([], columns=REQUIRED_COLUMNS))
    assert report.total_rows == 0
    assert report.structurally_valid is False
    assert "The dataset contains no rows." in report.eligibility_findings


def test_one_valid_row_in_a_large_file_is_not_a_verdict():
    """Regression: is_valid used to mean "at least one row parsed"."""
    rows = [
        {
            "train_number": "12301",
            "journey_date": "2026-10-01",
            "class_code": "SL",
            "quota_code": "GN",
            "initial_status": "GNWL/10",
            "final_chart_status": "CNF",
            "observation_date": "2026-09-25",
        }
    ] + [
        {
            "train_number": "bad",
            "journey_date": "x",
            "class_code": "",
            "quota_code": "",
            "initial_status": "",
            "final_chart_status": "",
            "observation_date": "",
        }
        for _ in range(499)
    ]
    report = validate_dataset(
        frame(rows), thresholds=EligibilityThresholds(min_rows=100, min_valid_rows=50)
    )
    assert report.valid_rows == 1
    assert report.structurally_valid is True
    assert report.technically_eligible is False
    assert any("0.2%" in finding for finding in report.eligibility_findings)


def test_column_names_are_trimmed():
    df = frame(BASE_ROWS).rename(columns={"train_number": "  train_number  "})
    report = validate_dataset(df, thresholds=synthetic_rules())
    assert report.missing_columns == []


def test_unexpected_columns_are_surfaced_not_dropped():
    rows = [{**row, "passenger_name": "SYNTHETIC"} for row in BASE_ROWS]
    report = validate(rows)
    assert "passenger_name" in report.unexpected_columns
    assert any(
        "passenger_name" in warning or "unexpected" in warning.lower()
        for warning in report.warnings
    ) or "passenger_name" in report.unexpected_columns


# ── Missing-value detection ────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [None, float("nan"), pd.NA, pd.NaT, "", "   ", "NA", "null", "None", "<NA>"])
def test_placeholder_and_null_values_are_treated_as_missing(value):
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["train_number"] = value
    report = validate(rows)
    assert report.rejection_reasons.get("missing_required_value") == 1


def test_pandas_na_row_is_not_counted_valid():
    """Regression: str(pd.NA) is "<NA>", which the old check read as a value."""
    df = frame(BASE_ROWS)
    df.loc[0, "train_number"] = pd.NA
    report = validate_dataset(df, thresholds=synthetic_rules())
    assert report.valid_rows == 1
    assert report.rejection_reasons["missing_required_value"] == 1
    assert report.null_counts["train_number"] == 1


def test_textual_placeholders_are_counted_separately_from_nulls():
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["quota_code"] = "NA"
    report = validate(rows)
    assert report.blank_token_counts["quota_code"] == 1
    assert report.null_counts["quota_code"] == 0


@pytest.mark.parametrize("token", sorted(MISSING_TOKENS))
def test_every_declared_placeholder_token_is_recognised(token):
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["initial_status"] = token
    assert validate(rows).rejection_reasons.get("missing_required_value") == 1


# ── Date rules ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad_date", ["01/02/2026", "2026-13-01", "20260915", "yesterday", "2026-09-25T00:00"])
def test_non_iso_dates_are_rejected_not_guessed(bad_date):
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["observation_date"] = bad_date
    report = validate(rows)
    assert report.rejection_reasons.get("unparseable_date") == 1


def test_observation_after_journey_date_is_rejected():
    """A status observed after departure cannot be a forecast input."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["observation_date"] = "2026-10-05"
    report = validate(rows)
    assert report.date_order_violations == 1
    assert report.rejection_reasons["observation_after_journey"] == 1
    assert report.valid_rows == 1


def test_observation_on_the_journey_date_is_allowed():
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["observation_date"] = "2026-10-01"
    assert validate(rows).valid_rows == 2


def test_date_ranges_come_from_valid_rows_only():
    rows = [dict(row) for row in BASE_ROWS]
    rows.append(
        {
            "train_number": "12302",
            "journey_date": "2026-10-03",
            "class_code": "SL",
            "quota_code": "GN",
            "initial_status": "GNWL/1",
            "final_chart_status": "CNF",
            "observation_date": "2027-01-01",
        }
    )
    report = validate(rows)
    assert report.journey_date_range == ("2026-10-01", "2026-10-02")


# ── Status labels ──────────────────────────────────────────────────────────────


def test_unknown_initial_status_is_rejected_with_a_reason():
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["initial_status"] = "XYZZY"
    report = validate(rows)
    assert report.rejection_reasons["unknown_initial_status"] == 1
    assert report.initial_status_distribution["UNKNOWN"] == 1


def test_unknown_final_status_is_counted_as_rejected():
    """Regression: unknown labels were tallied in the distribution but reconciled
    as neither valid nor rejected."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["final_chart_status"] = "MAGIC"
    report = validate(rows)
    assert report.rejection_reasons["unknown_final_status"] == 1
    assert report.rejected_rows == 1
    assert report.valid_rows + report.rejected_rows == report.total_rows


def test_censored_labels_are_excluded_and_never_negative_labels():
    rows = [dict(row) for row in BASE_ROWS]
    rows[1]["final_chart_status"] = "CENSORED"
    report = validate(rows)
    assert report.censored_label_rows == 1
    assert report.rejection_reasons["censored_label"] == 1
    assert report.final_status_distribution["CENSORED"] == 1
    assert any("not a negative label" in warning for warning in report.warnings)


def test_cancelled_outcomes_produce_a_target_definition_warning():
    rows = [dict(row) for row in BASE_ROWS]
    rows[1]["final_chart_status"] = "CANCELLED"
    report = validate(rows)
    assert any("cancellation is not automatically" in w for w in report.warnings)


def test_ck_family_is_reported_as_unknown_label():
    """Mapping v1.1.0 stopped guessing CK; the validator must not accept it either."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["final_chart_status"] = "CK"
    report = validate(rows)
    assert report.rejection_reasons["unknown_final_status"] == 1


# ── Duplicates and contradictions ──────────────────────────────────────────────


def test_exact_duplicate_rows_are_rejected_not_counted_valid():
    """Regression: duplicates only produced a warning and stayed inside valid_rows."""
    rows = BASE_ROWS + [dict(BASE_ROWS[0])]
    report = validate(rows)
    assert report.duplicate_rows == 1
    assert report.rejection_reasons["exact_duplicate_row"] == 1
    assert report.valid_rows == 2
    assert report.rejected_rows == 1


def test_same_reservation_with_different_outcomes_is_contradictory():
    rows = [dict(row) for row in BASE_ROWS]
    rows[1] = {
        "train_number": "12301",
        "journey_date": "2026-10-01",
        "class_code": "SL",
        "quota_code": "GN",
        "initial_status": "GNWL/10",
        "final_chart_status": "WL/10",
        "observation_date": "2026-09-25",
    }
    report = validate(rows)
    assert report.contradictory_label_groups == 1
    assert report.contradictory_label_rows == 2
    assert report.valid_rows == 0
    assert report.rejection_reasons["contradictory_labels"] == 2


def test_distinct_passengers_in_one_booking_are_not_contradictions():
    rows = [
        {
            "train_number": "12301",
            "journey_date": "2026-10-01",
            "class_code": "SL",
            "quota_code": "GN",
            "initial_status": "GNWL/10",
            "final_chart_status": "CNF",
            "observation_date": "2026-09-25",
            "booking_group_id": "B1",
            "passenger_record_id": "P1",
        },
        {
            "train_number": "12301",
            "journey_date": "2026-10-01",
            "class_code": "SL",
            "quota_code": "GN",
            "initial_status": "GNWL/10",
            "final_chart_status": "WL/10",
            "observation_date": "2026-09-25",
            "booking_group_id": "B1",
            "passenger_record_id": "P2",
        },
    ]
    report = validate(
        rows, columns=(*REQUIRED_COLUMNS, "booking_group_id", "passenger_record_id")
    )
    assert report.contradictory_label_groups == 0
    assert report.valid_rows == 2


def test_case_and_whitespace_in_labels_do_not_create_false_contradictions():
    rows = [dict(row) for row in BASE_ROWS]
    rows[1] = {**rows[0], "final_chart_status": " cnf ", "journey_date": "2026-10-02"}
    report = validate(rows)
    assert report.contradictory_label_groups == 0
    assert report.valid_rows == 2


# ── Train numbers ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["123", "1234567", "12A01", "ABCD"])
def test_invalid_train_numbers_are_rejected(bad):
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["train_number"] = bad
    report = validate(rows)
    assert report.rejection_reasons["invalid_train_number"] == 1


# ── Eligibility rules ──────────────────────────────────────────────────────────


def test_single_class_labels_block_eligibility():
    """A file where every outcome is CNF supports only a constant predictor."""
    rows = [{**dict(row), "final_chart_status": "CNF"} for row in BASE_ROWS]
    rows[1]["journey_date"] = "2026-10-09"
    report = validate(rows, thresholds=synthetic_rules(min_label_diversity=2))
    assert report.technically_eligible is False
    assert any("single-class" in finding for finding in report.eligibility_findings)


def test_too_few_distinct_dates_blocks_a_temporal_split():
    rows = [
        {**dict(row), "journey_date": "2026-10-01", "initial_status": f"GNWL/{10 + i}",
         "passenger_record_id": f"P{i}"}
        for i, row in enumerate(BASE_ROWS * 3)
    ]
    report = validate(
        rows,
        columns=(*REQUIRED_COLUMNS, "passenger_record_id"),
        thresholds=synthetic_rules(min_distinct_journey_dates=4),
    )
    assert any("chronological train/validation/test" in f for f in report.eligibility_findings)


def test_confirmed_share_outside_the_plausible_band_is_flagged():
    """A label column that is all-confirmed or all-negative is usually the wrong column."""
    rows = [
        {
            "train_number": "12301",
            "journey_date": f"2026-10-0{i + 1}",
            "class_code": "SL",
            "quota_code": "GN",
            "initial_status": f"GNWL/{10 + i}",
            "final_chart_status": "WL/5" if i else "CNF",
            "observation_date": "2026-09-20",
        }
        for i in range(2)
    ]
    report = validate(rows, thresholds=synthetic_rules(min_confirmed_share=0.9))
    assert any("Confirmed share" in finding for finding in report.eligibility_findings)


def test_synthetic_rows_are_warned_about():
    rows = [{**dict(row), "is_synthetic": "true"} for row in BASE_ROWS]
    report = validate(rows, columns=(*REQUIRED_COLUMNS, "is_synthetic"))
    assert any("is_synthetic" in warning for warning in report.warnings)


def test_missing_group_and_verification_columns_are_warned():
    report = validate(BASE_ROWS)
    assert any("booking_group_id" in w for w in report.warnings)
    assert any("verification_method" in w for w in report.warnings)


def test_threshold_validation_rejects_nonsense():
    with pytest.raises(ValueError, match="positive integer"):
        EligibilityThresholds(min_rows=0)
    with pytest.raises(ValueError, match="min_valid_rows cannot exceed"):
        EligibilityThresholds(min_rows=10, min_valid_rows=11)
    with pytest.raises(ValueError, match=r"must lie in \[0, 1\]"):
        EligibilityThresholds(min_valid_fraction=1.5)
    with pytest.raises(ValueError, match="min_confirmed_share must be below"):
        EligibilityThresholds(min_confirmed_share=0.9, max_confirmed_share=0.5)


def test_rejected_and_valid_rows_always_reconcile():
    rows = [
        dict(BASE_ROWS[0]),
        {**dict(BASE_ROWS[0]), "train_number": "bad"},
        {**dict(BASE_ROWS[1]), "final_chart_status": "CENSORED"},
        dict(BASE_ROWS[1]),
    ]
    report = validate(rows)
    assert report.valid_rows + report.rejected_rows == report.total_rows
    assert sum(report.rejection_reasons.values()) == report.rejected_rows


# ── Reporting shape ────────────────────────────────────────────────────────────


def test_report_dict_carries_the_three_verdicts():
    report = validate(BASE_ROWS)
    payload = report.to_dict()
    assert payload["structurally_valid"] is True
    assert "technically_eligible" in payload
    assert "valid_fraction" in payload
    assert payload["valid_fraction"] == 1.0
    assert "approval_status" not in payload, "the validator must not assert approval"


def test_summary_states_that_approval_is_not_determined():
    summary = validate(BASE_ROWS).summary()
    assert "approval" in summary
    assert "NOT DETERMINED HERE" in summary
    assert "structurally valid" in summary
    assert "technically eligible" in summary


def test_summary_lists_reasons_and_examples():
    rows = [dict(row) for row in BASE_ROWS]
    rows[0]["train_number"] = "bad"
    summary = validate(rows).summary()
    assert "invalid_train_number" in summary
    assert "First rejected rows" in summary


# ── The row filter that goes with the verdict ──────────────────────────────────


def test_assess_returns_only_the_rows_that_passed():
    rows = [dict(row) for row in BASE_ROWS]
    rows.append(dict(BASE_ROWS[0]))
    report, usable = assess(rows)
    assert report.rejection_reasons["exact_duplicate_row"] == 1
    assert len(usable) == report.valid_rows == 2
    assert list(usable.columns) == list(frame(BASE_ROWS).columns)


def test_assess_keeps_neither_side_of_a_contradiction():
    rows = [dict(BASE_ROWS[0]), {**BASE_ROWS[0], "final_chart_status": "WL/3"}]
    report, usable = assess(rows)
    assert report.rejection_reasons["contradictory_labels"] == 2
    assert len(usable) == 0
    assert report.structurally_valid is False


def test_assess_does_not_trust_a_callers_index():
    """Duplicate or odd labels used to make a per-row lookup ambiguous."""
    rows = [dict(row) for row in BASE_ROWS]
    df = frame(rows)
    df.index = ["same", "same"]
    report, usable = assess_dataset(df, thresholds=synthetic_rules())
    assert report.rejected_rows == 0
    assert list(usable.index) == [0, 1]


def test_assess_row_numbers_count_from_the_first_data_row():
    rows = [dict(row) for row in BASE_ROWS]
    rows[1]["observation_date"] = "2026-12-01"
    report, _ = assess(rows)
    assert [example["row"] for example in report.row_examples] == ["1"]
    assert report.rejection_reasons["observation_after_journey"] == 1


def test_assess_and_validate_agree_on_the_verdict():
    """The wrapper and the filter must never describe two different files."""
    report_only = validate(BASE_ROWS)
    report, _ = assess([dict(row) for row in BASE_ROWS])
    assert report.to_dict() == report_only.to_dict()


def test_assess_of_a_file_missing_a_required_column_returns_nothing():
    """frame() pins the schema, so the column exists and every row lacks its value."""
    rows = [{k: v for k, v in row.items() if k != "observation_date"} for row in BASE_ROWS]
    report, usable = assess(rows)
    assert report.rejection_reasons["missing_required_value"] == 2
    assert len(usable) == 0
    assert report.structurally_valid is False


def test_assess_of_a_frame_without_a_required_column_at_all():
    df = frame(BASE_ROWS).drop(columns=["observation_date"])
    report, usable = assess_dataset(df, thresholds=synthetic_rules())
    assert report.missing_columns == ["observation_date"]
    assert len(usable) == 0


def test_assess_of_an_empty_file_returns_nothing():
    report, usable = assess([])
    assert report.total_rows == 0
    assert len(usable) == 0

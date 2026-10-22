"""As-of feature construction and chronological splitting.

Two rules govern this module:

* A feature may only use information available at the record's observation time.
  Outcome labels, post-chart statuses and any later knowledge are excluded by
  construction, not by convention.
* A split that cannot hold a genuine future period back is reported as unable to
  evaluate. Returning every row as "train" with an empty test set and calling it
  a success would let a later metric be computed on nothing.

See docs/research/EVALUATION_PROTOCOL.md and ADR-0004.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import parse_status

FEATURE_SCHEMA_VERSION = "2.0.0"
"""Bump when feature meaning or nullability changes, so artifacts can be rejected
rather than silently misread."""

DATE_COLUMN = "journey_date"
OBSERVATION_COLUMN = "observation_date"

# Columns that describe the answer rather than the situation. They must never
# reach a model as features.
LABEL_COLUMNS: tuple[str, ...] = (
    "final_chart_status",
    "outcome_status_raw",
    "outcome_category",
    "censoring_reason",
)

# Feature columns produced by :func:`extract_features`. Training and inference
# read this list, so the two cannot drift apart unnoticed.
FEATURE_COLUMNS: tuple[str, ...] = (
    "class_code",
    "quota_code",
    "init_normalized",
    "init_position",
    "obs_normalized",
    "obs_position",
    "queue_ratio",
    "lead_days",
)

GROUP_COLUMN = "booking_group_id"


@dataclass(frozen=True)
class PartitionSummary:
    """Counts and boundaries of one split partition, for the evaluation report."""

    name: str
    row_count: int
    distinct_dates: int
    distinct_bookings: int
    start_date: str | None
    end_date: str | None

    def describe(self) -> str:
        if self.row_count == 0:
            return f"{self.name}: 0 rows"
        return (
            f"{self.name}: {self.row_count} rows, {self.distinct_dates} dates, "
            f"{self.distinct_bookings} bookings, {self.start_date}..{self.end_date}"
        )


@dataclass(frozen=True)
class SplitResult:
    """A chronological partitioning, plus whether it can support an evaluation."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    eligible: bool
    reasons: tuple[str, ...]
    partitions: tuple[PartitionSummary, ...]
    date_column: str = DATE_COLUMN

    @property
    def boundary_report(self) -> str:
        return "\n".join(partition.describe() for partition in self.partitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "date_column": self.date_column,
            "partitions": [asdict(partition) for partition in self.partitions],
        }


def _parse_dates(series: pd.Series, column: str) -> pd.Series:
    """Strict ISO date parsing.

    A format is stated so that an ambiguous value like 01/02/2026 is refused
    instead of being resolved by locale, which would silently reorder the
    timeline the split depends on.
    """
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    unparseable = int((parsed.isna() & series.notna()).sum())
    if unparseable > 0:
        raise DatasetValidationError(
            f"{unparseable} rows have a {column} that is not ISO YYYY-MM-DD. Dates "
            "must be parsed before splitting; guessing by locale would place records "
            "in the wrong partition."
        )
    missing = int(series.isna().sum())
    if missing > 0:
        raise DatasetValidationError(
            f"{missing} rows have no {column}. A chronological split cannot place a "
            "record with no date, and dropping it silently would change what the "
            "evaluation covers."
        )
    return parsed.dt.normalize()


def _summarise(name: str, frame: pd.DataFrame, date_column: str) -> PartitionSummary:
    dates = frame[date_column]
    bookings = frame[GROUP_COLUMN] if GROUP_COLUMN in frame.columns else pd.Series(dtype="object")
    return PartitionSummary(
        name=name,
        row_count=int(len(frame)),
        distinct_dates=int(dates.nunique()) if len(frame) else 0,
        distinct_bookings=int(bookings.nunique()) if len(bookings) else 0,
        start_date=str(min(dates).date()) if len(frame) else None,
        end_date=str(max(dates).date()) if len(frame) else None,
    )


def assert_no_label_columns(frame: pd.DataFrame, *, where: str) -> None:
    """Fail if outcome labels are present where features are expected."""
    present = [column for column in LABEL_COLUMNS if column in frame.columns]
    if present:
        raise DatasetValidationError(
            f"{where} received label columns {present}. A feature set that contains "
            "the answer measures recall of the file, not prediction."
        )


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build model features from validated observation records.

    Nothing here uses an outcome label. Positions stay nullable: a source that
    omitted the queue position is unknown, not position zero, and zero means
    "first in queue" to any model that reads it. ``lead_days`` is null rather
    than zero when the dates are missing or unparseable, because zero asserts a
    precision the record does not have.
    """
    assert_no_label_columns(df, where="extract_features")

    out = df.copy()
    if "initial_status" not in out.columns:
        raise DatasetValidationError("extract_features requires an 'initial_status' column.")

    current_column = "current_status" if "current_status" in out.columns else "initial_status"

    parsed_initial = [parse_status(str(value)) for value in out["initial_status"]]
    parsed_current = [parse_status(str(value)) for value in out[current_column]]

    out["init_normalized"] = [result.normalized.value for result in parsed_initial]
    out["obs_normalized"] = [result.normalized.value for result in parsed_current]
    out["init_position"] = pd.array(
        [result.position for result in parsed_initial], dtype="Int64"
    )
    out["obs_position"] = pd.array(
        [result.position for result in parsed_current], dtype="Int64"
    )

    # Position relative to the position booked first. A ratio needs both a
    # current and an initial position; otherwise it is unknown, not zero.
    init_position = out["init_position"].astype("Float64")
    obs_position = out["obs_position"].astype("Float64")
    out["queue_ratio"] = (obs_position / init_position).where(
        (obs_position > 0) & (init_position > 0)
    )

    if OBSERVATION_COLUMN in out.columns and DATE_COLUMN in out.columns:
        observation_dates = _parse_dates(out[OBSERVATION_COLUMN], OBSERVATION_COLUMN)
        journey_dates = _parse_dates(out[DATE_COLUMN], DATE_COLUMN)
        lead_days = (journey_dates - observation_dates).dt.days
        # A negative lead time means the observation postdates departure, which is
        # leakage rather than a small number. It is removed, not clamped to zero.
        out["lead_days"] = lead_days.where(lead_days >= 0)
    else:
        out["lead_days"] = pd.array([pd.NA] * len(out), dtype="Float64")

    return out


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return exactly the declared feature columns, in schema order."""
    features = extract_features(df)
    missing = [column for column in FEATURE_COLUMNS if column not in features.columns]
    if missing:
        raise DatasetValidationError(f"Feature schema incomplete; missing {missing}.")
    return features[list(FEATURE_COLUMNS)]


def chronological_split(
    df: pd.DataFrame,
    *,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    date_column: str = DATE_COLUMN,
    min_rows_per_partition: int = 1,
    gap_days: int = 0,
) -> SplitResult:
    """Partition by whole journey dates into train, validation and test.

    Dates, not rows, are allocated so every record of a date stays together and
    identical-date ties cannot straddle a boundary. When booking_group_id is
    present, a booking that appears on more than one date blocks the split rather
    than being divided across it.

    An ineligible split is returned with ``eligible=False`` and the reasons, not as
    an apparently successful partition whose test set happens to be empty.
    """
    if date_column not in df.columns:
        raise DatasetValidationError(
            f"Cannot perform a chronological split without '{date_column}'."
        )
    if not 0 < train_frac < 1 or not 0 < val_frac < 1 or train_frac + val_frac >= 1:
        raise DatasetValidationError(
            f"train_frac + val_frac must be below 1 with both positive; got "
            f"train_frac={train_frac}, val_frac={val_frac}."
        )
    if isinstance(min_rows_per_partition, bool) or min_rows_per_partition < 1:
        raise DatasetValidationError("min_rows_per_partition must be a positive integer.")
    if gap_days < 0:
        raise DatasetValidationError("gap_days cannot be negative.")

    work = df.copy()
    work["_partition_date"] = _parse_dates(work[date_column], date_column)
    # Stable, deterministic ordering: date first, then original row order.
    work = (
        work.assign(_original_index=work.index)
        .sort_values(["_partition_date", "_original_index"], kind="mergesort")
        .reset_index(drop=True)
    )

    dates = sorted(work["_partition_date"].unique())
    if len(dates) < 3:
        return _ineligible(
            work,
            date_column=date_column,
            reasons=(
                f"A chronological train/validation/test split needs at least three "
                f"distinct {date_column} values; this data has {len(dates)}. "
                "Nothing can be held back to evaluate against.",
            ),
        )

    n_dates = len(dates)
    train_end = max(1, int(n_dates * train_frac))
    train_end = min(train_end, n_dates - 2)

    val_end = max(train_end + 1, int(n_dates * (train_frac + val_frac)))
    val_end = min(val_end, n_dates - 1)

    train_dates = dates[:train_end]
    val_dates = dates[train_end:val_end]
    test_dates = dates[val_end:]

    train = work[work["_partition_date"].isin(train_dates)]
    val = work[work["_partition_date"].isin(val_dates)]
    test = work[work["_partition_date"].isin(test_dates)]

    reasons: list[str] = []

    for name, partition in (("train", train), ("validation", val), ("test", test)):
        if len(partition) == 0:
            reasons.append(f"{name} partition received no dates.")
        elif len(partition) < min_rows_per_partition:
            reasons.append(
                f"{name} partition holds {len(partition)} rows, below the required "
                f"{min_rows_per_partition}."
            )

    if train_dates and test_dates and val_dates:
        first_test = pd.Timestamp(min(test_dates)).date()
        last_train = pd.Timestamp(max(train_dates)).date()
        separation = (first_test - last_train).days
        if separation <= gap_days:
            reasons.append(
                f"Test starts {separation} day(s) after the last training date, inside "
                f"the {gap_days}-day gap required to keep near-boundary records out of "
                "the evaluation."
            )

    if GROUP_COLUMN in work.columns:
        membership = work.groupby(GROUP_COLUMN)["_partition_date"].nunique()
        crossing = membership[membership > 1]
        if len(crossing):
            sample = list(crossing.index[:5])
            reasons.append(
                f"{len(crossing)} {GROUP_COLUMN} values appear on dates falling in more "
                f"than one partition (for example {sample}); the same outcome would then "
                "appear in training and evaluation."
            )

    partitions = (
        _summarise("train", train, date_column="_partition_date"),
        _summarise("validation", val, date_column="_partition_date"),
        _summarise("test", test, date_column="_partition_date"),
    )

    if reasons:
        # A partition that fails a safety rule is not usable, so nothing is handed
        # back: the reasons name the totals, and a caller cannot score against them.
        return _ineligible(
            work,
            date_column=date_column,
            reasons=tuple(reasons) + ("Proposed boundaries: " + "; ".join(
                partition.describe() for partition in partitions
            ),),
        )

    return SplitResult(
        train=_drop_helper(train),
        val=_drop_helper(val),
        test=_drop_helper(test),
        eligible=True,
        reasons=(),
        partitions=partitions,
        date_column=date_column,
    )


def strip_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Drop outcome-label columns before feature construction.

    Feature construction refuses a frame that still carries labels, so the caller
    has to state that it means to. That is deliberate: the one place leakage
    becomes invisible is the step that hands a labelled frame to a feature builder.
    """
    present = [column for column in LABEL_COLUMNS if column in df.columns]
    return df.drop(columns=present)


def _drop_helper(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(columns=["_partition_date", "_original_index"], errors="ignore").reset_index(
        drop=True
    )


def _ineligible(work: pd.DataFrame, *, date_column: str, reasons: Sequence[str]) -> SplitResult:
    """Return no partitions at all.

    Handing back every row as "train" with empty validation and test frames lets a
    downstream step fit, score and report a metric on data that was never held
    back. An inability to evaluate must produce nothing to evaluate on.
    """
    empty = work.iloc[0:0]
    partitions = tuple(
        _summarise(name, empty, date_column="_partition_date")
        for name in ("train", "validation", "test")
    )
    dropped = _drop_helper(empty)
    return SplitResult(
        train=dropped,
        val=dropped.copy(),
        test=dropped.copy(),
        eligible=False,
        reasons=tuple(reasons)
        + (
            f"No partition was produced, so none of the {len(work)} rows may be used "
            "for fitting or scoring.",
        ),
        partitions=partitions,
        date_column=date_column,
    )

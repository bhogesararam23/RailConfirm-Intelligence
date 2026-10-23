"""As-of feature construction and chronological splitting.

Two rules govern this module:

* A feature may only use information available at the record's observation time.
  Outcome labels, post-chart statuses and any later knowledge are excluded by
  construction, not by convention.
* The status a record is *about* is the status it carries at that observation time,
  and :func:`asof_statuses` is the only definition of it. Fitting, scoring and
  serving all read the cohort from that one function, so a table built on one
  column cannot be queried through another.

A split that cannot hold a genuine future period back is reported as unable to
evaluate. Returning every row as "train" with an empty test set and calling it
a success would let a later metric be computed on nothing.

See docs/research/EVALUATION_PROTOCOL.md and ADR-0004.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pandas as pd

from railconfirm.data.validator import is_missing
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import ParsedStatus, parse_status

FEATURE_SCHEMA_VERSION = "3.0.0"
"""Bump when feature meaning or nullability changes, so artifacts can be rejected
rather than silently misread.

3.0.0 changes the as-of status: a row whose ``current_status`` is blank now falls
back to its ``initial_status`` instead of becoming UNKNOWN, and the derived columns
are named ``asof_*`` so the rule is visible where it is used."""

DATE_COLUMN = "journey_date"
OBSERVATION_COLUMN = "observation_date"

INITIAL_STATUS_COLUMN = "initial_status"
CURRENT_STATUS_COLUMN = "current_status"

ASOF_STATUS_FEATURE = "asof_normalized"
"""The derived feature column carrying the as-of status.

Model artifacts name their consumed features with these column names, so the
declaration can be checked against the schema instead of being trusted."""

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
    "asof_normalized",
    "asof_position",
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


def require_status_columns(frame: pd.DataFrame, *, where: str) -> None:
    """Fail unless the frame can say what status the reservation holds."""
    if INITIAL_STATUS_COLUMN not in frame.columns and CURRENT_STATUS_COLUMN not in frame.columns:
        raise DatasetValidationError(
            f"{where} received neither '{INITIAL_STATUS_COLUMN}' nor "
            f"'{CURRENT_STATUS_COLUMN}'. Without an as-of status there is no cohort "
            "to fit and none to look up."
        )


def asof_statuses(frame: pd.DataFrame) -> list[ParsedStatus]:
    """The status each record carries at its own observation time.

    This is the single definition shared by fitting, scoring and the served
    request. ``current_status`` is the later look and wins when the source
    recorded one; a blank ``current_status`` means no later look existed, so the
    record's as-of status is its ``initial_status`` rather than unknown. A record
    with no status at all parses to UNKNOWN, which abstains instead of guessing.

    At serving time the same rule is the most recent ``StatusObservation`` at or
    before the prediction timestamp; the dataset's ``current_status`` is that
    observation flattened into one column.
    """
    require_status_columns(frame, where="asof_statuses")
    has_current = CURRENT_STATUS_COLUMN in frame.columns
    has_initial = INITIAL_STATUS_COLUMN in frame.columns
    if not has_current:
        return [parse_status(str(value)) for value in frame[INITIAL_STATUS_COLUMN]]
    if not has_initial:
        return [parse_status(str(value)) for value in frame[CURRENT_STATUS_COLUMN]]
    return [
        parse_status(str(current)) if not is_missing(current) else parse_status(str(initial))
        for initial, current in zip(
            frame[INITIAL_STATUS_COLUMN], frame[CURRENT_STATUS_COLUMN], strict=True
        )
    ]


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
    if INITIAL_STATUS_COLUMN not in out.columns:
        raise DatasetValidationError(
            f"extract_features requires an '{INITIAL_STATUS_COLUMN}' column."
        )

    parsed_initial = [parse_status(str(value)) for value in out[INITIAL_STATUS_COLUMN]]
    parsed_asof = asof_statuses(out)

    out["init_normalized"] = [result.normalized.value for result in parsed_initial]
    out["asof_normalized"] = [result.normalized.value for result in parsed_asof]
    out["init_position"] = pd.array(
        [result.position for result in parsed_initial], dtype="Int64"
    )
    out["asof_position"] = pd.array(
        [result.position for result in parsed_asof], dtype="Int64"
    )

    # Position relative to the position booked first. A ratio needs both a
    # current and an initial position; otherwise it is unknown, not zero.
    init_position = out["init_position"].astype("Float64")
    asof_position = out["asof_position"].astype("Float64")
    out["queue_ratio"] = (asof_position / init_position).where(
        (asof_position > 0) & (init_position > 0)
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


# ── Rolling-origin evaluation windows ──────────────────────────────────────────

DEFAULT_MIN_TRAIN_DATES = 3
DEFAULT_HORIZON_DATES = 1
DEFAULT_STEP_DATES = 1
MIN_ORIGINS = 2
"""A single cutoff is what :func:`chronological_split` already gives. Calling a
one-origin run "rolling" would claim temporal robustness from one measurement."""


@dataclass(frozen=True)
class OriginWindow:
    """One cutoff: the dates a fit may see, and the dates it is scored on after."""

    index: int
    train: pd.DataFrame
    scored: pd.DataFrame
    train_dates: tuple[str, ...]
    scored_dates: tuple[str, ...]
    gap_days: int

    @property
    def train_rows(self) -> int:
        return int(len(self.train))

    @property
    def scored_rows(self) -> int:
        return int(len(self.scored))

    def describe(self) -> str:
        return (
            f"origin {self.index}: train {self.train_dates[0]}..{self.train_dates[-1]} "
            f"({self.train_rows} rows, {len(self.train_dates)} dates) -> scored "
            f"{self.scored_dates[0]}..{self.scored_dates[-1]} ({self.scored_rows} rows), "
            f"gap {self.gap_days}d"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "train_start": self.train_dates[0],
            "train_end": self.train_dates[-1],
            "train_dates": len(self.train_dates),
            "train_rows": self.train_rows,
            "scored_start": self.scored_dates[0],
            "scored_end": self.scored_dates[-1],
            "scored_dates": len(self.scored_dates),
            "scored_rows": self.scored_rows,
            "gap_days": self.gap_days,
        }


@dataclass(frozen=True)
class RollingOriginPlan:
    """The origins a dataset can support, or the reasons it cannot support two."""

    windows: tuple[OriginWindow, ...]
    eligible: bool
    reasons: tuple[str, ...]
    date_column: str
    min_train_dates: int
    horizon_dates: int
    step_dates: int
    gap_days: int

    @property
    def boundaries(self) -> list[str]:
        return [window.describe() for window in self.windows]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "date_column": self.date_column,
            "min_train_dates": self.min_train_dates,
            "horizon_dates": self.horizon_dates,
            "step_dates": self.step_dates,
            "gap_days": self.gap_days,
            "origin_count": len(self.windows),
            "origins": [window.to_dict() for window in self.windows],
        }


def rolling_origin_windows(
    df: pd.DataFrame,
    *,
    date_column: str = DATE_COLUMN,
    min_train_dates: int = DEFAULT_MIN_TRAIN_DATES,
    horizon_dates: int = DEFAULT_HORIZON_DATES,
    step_dates: int = DEFAULT_STEP_DATES,
    gap_days: int = 0,
    min_scored_rows: int = 1,
) -> RollingOriginPlan:
    """Plan expanding-window origins: train on the past, score the next dates, advance.

    Dates, never rows, so a record cannot straddle a cutoff. Each origin's training
    block starts at the first date and grows by ``step_dates`` dates; the scored block
    is the ``horizon_dates`` dates immediately after it, separated by more than
    ``gap_days`` calendar days. Fewer than two usable origins is not an evaluation
    strategy, and a plan that cannot give two returns **no windows** with the reasons —
    the same rule :func:`chronological_split` follows, because an unusable origin is
    worse than none when a metric is going to be computed on it.

    Overlapping scored windows are refused: the same outcome counted in two origins is
    one evaluation reported twice.
    """
    if date_column not in df.columns:
        raise DatasetValidationError(
            f"Cannot plan rolling origins without '{date_column}'."
        )
    for name, value in (
        ("min_train_dates", min_train_dates),
        ("horizon_dates", horizon_dates),
        ("step_dates", step_dates),
        ("min_scored_rows", min_scored_rows),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise DatasetValidationError(
                f"{name} must be a positive integer, got {value!r}."
            )
    if gap_days < 0:
        raise DatasetValidationError("gap_days cannot be negative.")
    if step_dates < horizon_dates:
        raise DatasetValidationError(
            f"step_dates={step_dates} is below horizon_dates={horizon_dates}, which "
            "would overlap two scored windows and count the same outcome in both."
        )

    plan_kwargs: dict[str, Any] = {
        "date_column": date_column,
        "min_train_dates": min_train_dates,
        "horizon_dates": horizon_dates,
        "step_dates": step_dates,
        "gap_days": gap_days,
    }

    def refused(reasons: Sequence[str]) -> RollingOriginPlan:
        return RollingOriginPlan(
            windows=(), eligible=False, reasons=tuple(reasons), **plan_kwargs
        )

    work = df.copy()
    work["_partition_date"] = _parse_dates(work[date_column], date_column)
    work = (
        work.assign(_original_index=work.index)
        .sort_values(["_partition_date", "_original_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    dates = [pd.Timestamp(value) for value in sorted(work["_partition_date"].unique())]
    if len(dates) < min_train_dates + horizon_dates:
        return refused(
            [
                f"{len(dates)} distinct {date_column} values; one origin alone needs "
                f"{min_train_dates} training dates plus {horizon_dates} scored dates, and "
                f"rolling evaluation needs a second origin after it."
            ]
        )

    group_dates: dict[str, set[pd.Timestamp]] = {}
    if GROUP_COLUMN in work.columns:
        pairs = work[[GROUP_COLUMN, "_partition_date"]].drop_duplicates()
        for group, date in zip(
            pairs[GROUP_COLUMN].tolist(), pairs["_partition_date"].tolist(), strict=True
        ):
            group_dates.setdefault(str(group), set()).add(pd.Timestamp(date))

    windows: list[OriginWindow] = []
    reasons: list[str] = []
    index = 0
    while True:
        train_count = min_train_dates + index * step_dates
        if train_count + horizon_dates > len(dates):
            break
        train_dates = dates[:train_count]
        scored_dates = dates[train_count : train_count + horizon_dates]
        separation = (scored_dates[0] - train_dates[-1]).days
        if separation <= gap_days:
            reasons.append(
                f"Origin {index}: the scored window starts {separation} day(s) after the "
                f"last training date, inside the {gap_days}-day gap required to keep "
                "near-boundary records out of the evaluation."
            )
            break

        train = work[work["_partition_date"].isin(train_dates)]
        scored = work[work["_partition_date"].isin(scored_dates)]
        if len(scored) < min_scored_rows:
            reasons.append(
                f"Origin {index}: the scored window holds {_rows(len(scored))}, below the "
                f"required {min_scored_rows}."
            )
            break

        if group_dates:
            train_set = set(train_dates)
            crossing = sorted(
                group
                for group, seen in group_dates.items()
                if seen & train_set and seen & set(scored_dates)
            )
            if crossing:
                reasons.append(
                    f"{len(crossing)} {GROUP_COLUMN} values appear on both sides of origin "
                    f"{index}'s cutoff (for example {crossing[:5]}); their outcome would be "
                    "in the fit and in the evaluation at once."
                )
                break
            # A booking scored by two origins would double-count the aggregate, but
            # step_dates >= horizon_dates puts every earlier scored date inside every
            # later training block, so any such booking is already caught above.

        windows.append(
            OriginWindow(
                index=index,
                train=_drop_helper(train),
                scored=_drop_helper(scored),
                train_dates=tuple(date.date().isoformat() for date in train_dates),
                scored_dates=tuple(date.date().isoformat() for date in scored_dates),
                gap_days=gap_days,
            )
        )
        index += 1

    if not reasons and len(windows) < MIN_ORIGINS:
        reasons.append(
            f"Only {_origins(len(windows))} usable from {len(dates)} distinct "
            f"{date_column} values. A single cutoff is what `chronological_split` already "
            f"provides; rolling evaluation needs at least {MIN_ORIGINS}, so no window was "
            "produced rather than reporting one measurement as a temporal trend."
        )
        windows = []

    if reasons:
        return refused(reasons)
    return RollingOriginPlan(
        windows=tuple(windows), eligible=True, reasons=(), **plan_kwargs
    )


def _rows(count: int) -> str:
    return f"{count} row" if count == 1 else f"{count} rows"


def _origins(count: int) -> str:
    return "1 origin" if count == 1 else f"{count} origins"


def _horizons(count: int) -> str:
    return "1 horizon" if count == 1 else f"{count} horizons"


def _dates(count: int) -> str:
    return f"{count} date" if count == 1 else f"{count} dates"


# ── Frozen-artifact decay windows ──────────────────────────────────────────────

MIN_HORIZONS = 2
"""One horizon is what :func:`chronological_split`'s test block already is. Calling a
single future window "decay" would claim a trend from one measurement."""


@dataclass(frozen=True)
class HorizonWindow:
    """One scored block after the cutoff, judged by the same frozen training block."""

    index: int
    scored: pd.DataFrame
    scored_dates: tuple[str, ...]
    train_dates: tuple[str, ...]
    train_rows: int
    cutoff: str
    gap_days: int

    @property
    def scored_rows(self) -> int:
        return int(len(self.scored))

    def describe(self) -> str:
        return (
            f"horizon {self.index}: scored {self.scored_dates[0]}..{self.scored_dates[-1]} "
            f"({self.scored_rows} rows, {_dates(len(self.scored_dates))}) against the frozen "
            f"{self.train_dates[0]}..{self.train_dates[-1]} "
            f"({self.train_rows} rows, {_dates(len(self.train_dates))})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "train_start": self.train_dates[0],
            "train_end": self.train_dates[-1],
            "train_dates": len(self.train_dates),
            "train_rows": self.train_rows,
            "cutoff": self.cutoff,
            "scored_start": self.scored_dates[0],
            "scored_end": self.scored_dates[-1],
            "scored_dates": len(self.scored_dates),
            "scored_rows": self.scored_rows,
            "gap_days": self.gap_days,
        }


@dataclass(frozen=True)
class FrozenHorizonPlan:
    """One frozen training block plus the successive horizons it is judged on."""

    train: pd.DataFrame
    train_dates: tuple[str, ...]
    cutoff: str
    horizons: tuple[HorizonWindow, ...]
    eligible: bool
    reasons: tuple[str, ...]
    date_column: str
    horizon_dates: int
    step_dates: int
    gap_days: int
    min_scored_rows: int
    min_horizons: int

    @property
    def train_rows(self) -> int:
        return int(len(self.train))

    def describe(self) -> str:
        return (
            f"frozen block {self.train_dates[0]}..{self.train_dates[-1]} "
            f"({self.train_rows} rows, {_dates(len(self.train_dates))}), then "
            f"{len(self.horizons)} horizons of {_dates(self.horizon_dates)} each"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "date_column": self.date_column,
            "cutoff": self.cutoff,
            "train_start": self.train_dates[0] if self.train_dates else None,
            "train_end": self.train_dates[-1] if self.train_dates else None,
            "train_dates": len(self.train_dates),
            "train_rows": self.train_rows,
            "horizon_dates": self.horizon_dates,
            "step_dates": self.step_dates,
            "gap_days": self.gap_days,
            "min_scored_rows": self.min_scored_rows,
            "min_horizons": self.min_horizons,
            "horizon_count": len(self.horizons),
            "horizons": [window.to_dict() for window in self.horizons],
        }


def frozen_horizon_windows(
    df: pd.DataFrame,
    *,
    date_column: str = DATE_COLUMN,
    fitted_to: str,
    horizon_dates: int = DEFAULT_HORIZON_DATES,
    step_dates: int = DEFAULT_STEP_DATES,
    gap_days: int = 0,
    min_scored_rows: int = 1,
    min_horizons: int = MIN_HORIZONS,
) -> FrozenHorizonPlan:
    """Plan the horizons one already-fitted table is scored against, without refitting.

    ``fitted_to`` is the last date the artifact declares it was fitted on: everything up to
    it is frozen, and every horizon after it is judged by that same table. That is the
    difference from :func:`rolling_origin_windows`, which refits at each cutoff and so
    measures the fitting procedure rather than a promoted artifact's decay.

    Fewer than ``min_horizons`` usable horizons returns **no windows**, with the reasons:
    one future block is what a single train/validation/test split already provides, and a
    decay curve drawn through one point is a claim about stability that nothing was measured.
    A booking whose dates fall on both sides of the cutoff is refused outright, because the
    frozen table already contains that outcome and would be scoring itself.
    """
    if date_column not in df.columns:
        raise DatasetValidationError(
            f"Cannot plan frozen horizons without '{date_column}'."
        )
    for name, value in (
        ("horizon_dates", horizon_dates),
        ("step_dates", step_dates),
        ("min_scored_rows", min_scored_rows),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise DatasetValidationError(
                f"{name} must be a positive integer, got {value!r}."
            )
    if isinstance(min_horizons, bool) or not isinstance(min_horizons, int):
        raise DatasetValidationError(
            f"min_horizons must be an integer of at least {MIN_HORIZONS}, "
            f"got {min_horizons!r}."
        )
    if min_horizons < MIN_HORIZONS:
        raise DatasetValidationError(
            f"min_horizons={min_horizons} asks for fewer than {MIN_HORIZONS} horizons, "
            "which is a single holdout under another name."
        )
    if gap_days < 0:
        raise DatasetValidationError("gap_days cannot be negative.")
    if step_dates < horizon_dates:
        raise DatasetValidationError(
            f"step_dates={step_dates} is below horizon_dates={horizon_dates}, which "
            "would overlap two scored horizons and count the same outcome in both."
        )
    try:
        cutoff = date.fromisoformat(str(fitted_to).strip())
    except ValueError as exc:
        raise DatasetValidationError(
            f"fitted_to must be an ISO-8601 date, got {fitted_to!r}: the artifact's own "
            "last fitted date is what separates frozen data from decay evidence."
        ) from exc

    plan_kwargs: dict[str, Any] = {
        "date_column": date_column,
        "horizon_dates": horizon_dates,
        "step_dates": step_dates,
        "gap_days": gap_days,
        "min_scored_rows": min_scored_rows,
        "min_horizons": min_horizons,
    }
    empty_train = df.iloc[0:0].copy()

    def refused(cutoff_text: str, reasons: Sequence[str]) -> FrozenHorizonPlan:
        return FrozenHorizonPlan(
            train=_drop_helper(empty_train),
            train_dates=(),
            cutoff=cutoff_text,
            horizons=(),
            eligible=False,
            reasons=tuple(reasons),
            **plan_kwargs,
        )

    work = df.copy()
    work["_partition_date"] = _parse_dates(work[date_column], date_column)
    work = (
        work.assign(_original_index=work.index)
        .sort_values(["_partition_date", "_original_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    cutoff_text = cutoff.isoformat()
    dates = [pd.Timestamp(value) for value in sorted(work["_partition_date"].unique())]

    train_dates = [value for value in dates if value.date() <= cutoff]
    if not train_dates:
        return refused(
            cutoff_text,
            [
                f"The artifact's fitted period ends {cutoff_text}, before this file begins "
                f"on {dates[0].date().isoformat()}. Decay is measured against the population "
                "the table was fitted on; a file that starts after it can show what the table "
                "predicts, not how well it was ever fitted.",
            ],
        )
    forward = [value for value in dates if value.date() > cutoff]
    if not forward:
        return refused(
            cutoff_text,
            [
                f"No dates after the cutoff {cutoff_text}: the file ends at "
                f"{dates[-1].date().isoformat()}, so there is nothing the frozen table has "
                "not already seen.",
            ],
        )

    group_dates: dict[str, set[pd.Timestamp]] = {}
    if GROUP_COLUMN in work.columns:
        pairs = work[[GROUP_COLUMN, "_partition_date"]].drop_duplicates()
        for group, seen in zip(
            pairs[GROUP_COLUMN].tolist(), pairs["_partition_date"].tolist(), strict=True
        ):
            group_dates.setdefault(str(group), set()).add(pd.Timestamp(seen))

    train = work[work["_partition_date"].isin(train_dates)]
    frozen_dates = tuple(value.date().isoformat() for value in train_dates)
    separation = (forward[0] - train_dates[-1]).days
    if separation <= gap_days:
        return refused(
            cutoff_text,
            [
                f"The first horizon starts {separation} day(s) after the cutoff "
                f"{cutoff_text}, inside the {gap_days}-day gap required to keep "
                "near-boundary records out of the evaluation.",
            ],
        )

    horizons: list[HorizonWindow] = []
    reasons: list[str] = []
    start = 0
    while start + horizon_dates <= len(forward):
        scored_dates = forward[start : start + horizon_dates]
        start += step_dates
        scored = work[work["_partition_date"].isin(scored_dates)]
        if len(scored) < min_scored_rows:
            reasons.append(
                f"Horizon {len(horizons)}: the scored window holds {_rows(len(scored))}, "
                f"below the required {min_scored_rows}."
            )
            break

        if group_dates:
            frozen_set = set(train_dates)
            crossing = sorted(
                group
                for group, seen in group_dates.items()
                if seen & frozen_set and seen & set(scored_dates)
            )
            if crossing:
                reasons.append(
                    f"{len(crossing)} {GROUP_COLUMN} values appear both in the frozen block "
                    f"and in horizon {len(horizons)} (for example {crossing[:5]}); their "
                    "outcome is already inside the table being judged, so the frozen table "
                    "would be scoring itself."
                )
                break

        horizons.append(
            HorizonWindow(
                index=len(horizons),
                scored=_drop_helper(scored),
                scored_dates=tuple(value.date().isoformat() for value in scored_dates),
                train_dates=frozen_dates,
                train_rows=int(len(train)),
                cutoff=cutoff_text,
                gap_days=gap_days,
            )
        )

    if not reasons and len(horizons) < min_horizons:
        reasons.append(
            f"Only {_horizons(len(horizons))} usable after {cutoff_text} from "
            f"{len(dates)} distinct {date_column} values. A single future block is what "
            f"``chronological_split`` already provides; measuring decay needs at least "
            f"{min_horizons}, so no horizon was scored rather than reporting one point as "
            "a trend."
        )
        horizons = []

    if reasons:
        return refused(cutoff_text, reasons)
    return FrozenHorizonPlan(
        train=_drop_helper(train),
        train_dates=frozen_dates,
        cutoff=cutoff_text,
        horizons=tuple(horizons),
        eligible=True,
        reasons=(),
        **plan_kwargs,
    )

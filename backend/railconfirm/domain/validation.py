"""Shared domain validators and stable reason codes.

These helpers are the single place where format and temporal rules are decided, so
the API boundary and the domain objects cannot drift into agreeing with each other
by accident.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from railconfirm.domain.exceptions import (
    JourneyValidationError,
    TemporalIntegrityError,
)

_TRAIN_NUMBER_RE = re.compile(r"^\d{4,6}$")
_STATION_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

MIN_LEAD_DAYS = 1
"""The shortest observation-to-journey gap this product answers a prediction across.

The served request and the dataset contract both carry calendar dates rather than
timestamps, so a record observed *on* its journey date cannot say whether the
observation preceded the final chart or followed it. The final chart is prepared on
the journey date, which is why a same-day "prediction" is a retrodiction rather than
a forecast. Both ends of the pipeline read this constant: serving refuses a
``prediction_at`` closer than this to the journey date, and
the dataset gate refuses rows whose ``observation_date`` is.

A caller must not lower it to lift a fixture's row count: one clear day is the finest
resolution a date-only record can express."""


def validate_train_number(value: object) -> str:
    """Validate and return a train number string (4–6 digits, zero-padded)."""
    s = str(value).strip()
    if not _TRAIN_NUMBER_RE.match(s):
        raise JourneyValidationError(f"train_number must be 4–6 digits, got: {s!r}")
    return s


def validate_station_code(value: object, field_name: str = "station") -> str:
    """Validate and uppercase a station code.

    A station code is an uppercase alphanumeric token of 2–10 characters. Without
    this rule a whitespace-only or arbitrary string silently becomes a "route".
    """
    s = str(value).strip().upper()
    if not s:
        raise JourneyValidationError(f"{field_name} must not be empty.")
    if not _STATION_CODE_RE.match(s):
        raise JourneyValidationError(
            f"{field_name} {value!r} is not a station code: expected 2–10 uppercase "
            "letters or digits beginning with a letter."
        )
    return s


def validate_journey_date(value: object) -> date:
    """Accept a ``date`` or an ISO-8601 date string."""
    if isinstance(value, datetime):
        # A datetime is not a calendar date; accepting it hides a time component
        # that the journey date is defined not to carry.
        raise JourneyValidationError(
            f"journey_date must be a calendar date, got datetime {value!r}."
        )
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise JourneyValidationError(f"Cannot parse journey_date: {value!r}") from exc


def ensure_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Return ``value`` if it carries a timezone, otherwise raise.

    Naive timestamps are refused rather than assumed to be local or UTC: an
    assumed zone shifts a lead time by up to twelve hours, which is exactly the
    resolution at which "was this known before the chart?" is decided.
    """
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TemporalIntegrityError(
            f"{field_name} must be a datetime, got {type(value).__name__}."
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise TemporalIntegrityError(
            f"{field_name}={value.isoformat()} has no timezone offset. Supply an "
            "offset-aware ISO-8601 timestamp."
        )
    return value


def validate_observation_time(
    observed_at: datetime | None,
    ingested_at: datetime,
    field_name: str = "observed_at",
) -> None:
    """Require aware timestamps and forbid an observation newer than ingestion."""
    ensure_aware(ingested_at, "ingested_at")
    ensure_aware(observed_at, field_name)
    if observed_at is not None and observed_at > ingested_at:
        raise TemporalIntegrityError(
            f"{field_name}={observed_at.isoformat()} is later than ingestion time "
            f"{ingested_at.isoformat()}; an observation cannot be made after it was "
            "recorded."
        )


def validate_prediction_timing(
    journey_date: date,
    prediction_at: datetime,
    observation_times: list[tuple[str, datetime | None]],
) -> None:
    """Enforce the temporal rules a prediction depends on.

    Three separate failures are caught here:

    * a naive prediction timestamp, which cannot be compared to anything;
    * a prediction timestamp closer than :data:`MIN_LEAD_DAYS` to the journey date,
      where the outcome is already settled and the question is no longer a forecast;
    * evidence observed after the prediction timestamp, which would leak the
      future into an as-of estimate.

    ``observation_times`` pairs a passenger label with that passenger's current
    status observation time, or ``None`` when the time is unknown.
    """
    ensure_aware(prediction_at, "prediction_at")
    lead_days = (journey_date - prediction_at.date()).days
    if lead_days < MIN_LEAD_DAYS:
        raise TemporalIntegrityError(
            f"prediction_at={prediction_at.isoformat()} is on or after journey date "
            f"{journey_date.isoformat()}. The final-chart outcome is not a future "
            "event from that point; use historical backtesting instead."
        )

    for passenger_id, observed_at in observation_times:
        if observed_at is None:
            continue
        ensure_aware(observed_at, f"current_status_observed_at for {passenger_id}")
        if observed_at > prediction_at:
            raise TemporalIntegrityError(
                f"Passenger {passenger_id} status was observed at "
                f"{observed_at.isoformat()}, after prediction_at "
                f"{prediction_at.isoformat()}. Evidence newer than the prediction "
                "timestamp would leak the outcome into the estimate."
            )


class ReasonCode:
    """Stable string codes for structured API error responses.

    Values are part of the public contract: add a code with a producer and a test,
    and never rename one in place.
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_TRAIN_NUMBER = "INVALID_TRAIN_NUMBER"
    INVALID_STATION = "INVALID_STATION"
    SAME_BOARDING_DESTINATION = "SAME_BOARDING_DESTINATION"
    UNKNOWN_CLASS_CODE = "UNKNOWN_CLASS_CODE"
    UNKNOWN_QUOTA_CODE = "UNKNOWN_QUOTA_CODE"
    UNKNOWN_STATUS = "unknown_status"
    NO_PASSENGERS = "NO_PASSENGERS"
    INVALID_PREDICTION_AT = "INVALID_PREDICTION_AT"
    NO_TRAINED_MODEL = "no_trained_model"
    NO_APPROVED_DATA = "no_approved_data"
    MODEL_ARTIFACT_INVALID = "model_artifact_invalid"
    UNSUPPORTED_STATUS = "unsupported_status"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    HISTORY_DISABLED = "history_disabled"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    INTERNAL_ERROR = "INTERNAL_ERROR"

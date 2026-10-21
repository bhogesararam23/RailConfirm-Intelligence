"""Pydantic validators and reason codes for RailConfirm Intelligence.

Provides reusable validation helpers used by both the domain layer and the
API schema layer.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from railconfirm.domain.journey import SUPPORTED_CLASS_CODES, SUPPORTED_QUOTA_CODES


_TRAIN_NUMBER_RE = re.compile(r"^\d{4,6}$")


def validate_train_number(v: Any) -> str:
    """Validate and return a train number string."""
    s = str(v).strip()
    if not _TRAIN_NUMBER_RE.match(s):
        raise ValueError(f"train_number must be 4–6 digits, got: {s!r}")
    return s


def validate_station_code(v: Any) -> str:
    """Validate and uppercase a station code."""
    s = str(v).strip().upper()
    if not s:
        raise ValueError("Station code must not be empty.")
    return s


def validate_journey_date(v: Any) -> date:
    """Accept date or ISO-8601 string."""
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Cannot parse journey_date: {v!r}") from exc


def validate_prediction_at(v: Any) -> datetime:
    """Accept datetime or ISO-8601 string."""
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Cannot parse prediction_at: {v!r}") from exc


class ReasonCode:
    """Stable string codes for structured error responses."""

    INVALID_TRAIN_NUMBER = "INVALID_TRAIN_NUMBER"
    INVALID_STATION = "INVALID_STATION"
    SAME_BOARDING_DESTINATION = "SAME_BOARDING_DESTINATION"
    UNKNOWN_CLASS_CODE = "UNKNOWN_CLASS_CODE"
    UNKNOWN_QUOTA_CODE = "UNKNOWN_QUOTA_CODE"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"
    NO_PASSENGERS = "NO_PASSENGERS"
    INVALID_PREDICTION_AT = "INVALID_PREDICTION_AT"
    NO_TRAINED_MODEL = "NO_TRAINED_MODEL"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INVALID_INPUT = "INVALID_INPUT"

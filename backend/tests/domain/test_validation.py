"""Tests for shared domain validators: format rules and temporal integrity."""

from datetime import UTC, date, datetime

import pytest

from railconfirm.domain.exceptions import (
    JourneyValidationError,
    TemporalIntegrityError,
)
from railconfirm.domain.validation import (
    ensure_aware,
    validate_journey_date,
    validate_observation_time,
    validate_prediction_timing,
    validate_station_code,
    validate_train_number,
)

AWARE = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
NATIVE = datetime(2026, 10, 21, 8, 0)  # noqa: DTZ001 - deliberately naive
JOURNEY_DATE = date(2026, 11, 15)


@pytest.mark.parametrize(
    "value,expected",
    [("12301", "12301"), ("1234", "1234"), ("123456", "123456"), (" 12301 ", "12301")],
)
def test_train_number_accepts(value, expected):
    assert validate_train_number(value) == expected


@pytest.mark.parametrize("value", ["123", "1234567", "12A01", "", "  ", None, "12301x"])
def test_train_number_rejects(value):
    with pytest.raises(JourneyValidationError, match="4–6 digits"):
        validate_train_number(value)


@pytest.mark.parametrize("value,expected", [
    ("NDLS", "NDLS"),
    ("ndls", "NDLS"),
    (" BCT ", "BCT"),
    ("NDLL", "NDLL"),
    ("A1", "A1"),
])
def test_station_code_accepts(value, expected):
    assert validate_station_code(value, "boarding_station") == expected


@pytest.mark.parametrize("value", ["", "   ", "N", "TOO_LONG_STATION_CODE", "1ABC", "NDLS!", "ND LS"])
def test_station_code_rejects(value):
    with pytest.raises(JourneyValidationError, match="boarding_station"):
        validate_station_code(value, "boarding_station")


def test_journey_date_accepts_date_and_iso_string():
    assert validate_journey_date(JOURNEY_DATE) == JOURNEY_DATE
    assert validate_journey_date("2026-11-15") == JOURNEY_DATE


def test_journey_date_rejects_a_datetime():
    """A datetime would carry a time the journey date is defined not to have."""
    with pytest.raises(JourneyValidationError, match="calendar date"):
        validate_journey_date(AWARE)


@pytest.mark.parametrize("value", ["15/11/2026", "not-a-date", ""])
def test_journey_date_rejects_unparseable(value):
    with pytest.raises(JourneyValidationError, match="Cannot parse journey_date"):
        validate_journey_date(value)


def test_ensure_aware_passes_through_and_allows_none():
    assert ensure_aware(AWARE, "x") == AWARE
    assert ensure_aware(None, "x") is None


def test_ensure_aware_rejects_naive_and_non_datetime():
    with pytest.raises(TemporalIntegrityError, match="no timezone offset"):
        ensure_aware(NATIVE, "prediction_at")
    with pytest.raises(TemporalIntegrityError, match="must be a datetime"):
        ensure_aware("2026-10-21T08:00:00Z", "prediction_at")  # type: ignore[arg-type]


def test_observation_time_allows_unknown_observed_at():
    assert validate_observation_time(None, AWARE) is None


def test_observation_time_rejects_future_observation():
    with pytest.raises(TemporalIntegrityError, match="later than ingestion"):
        validate_observation_time(datetime(2026, 10, 22, tzinfo=UTC), AWARE)


def test_prediction_timestamp_must_be_aware():
    with pytest.raises(TemporalIntegrityError, match="no timezone offset"):
        validate_prediction_timing(JOURNEY_DATE, NATIVE, [("p-1", None)])


@pytest.mark.parametrize(
    "prediction_at,fragment",
    [
        (datetime(2026, 11, 15, 0, 30, tzinfo=UTC), "on or after journey date"),
        (datetime(2026, 12, 1, tzinfo=UTC), "on or after journey date"),
    ],
)
def test_prediction_after_departure_is_not_a_forecast(prediction_at, fragment):
    with pytest.raises(TemporalIntegrityError, match=fragment):
        validate_prediction_timing(JOURNEY_DATE, prediction_at, [("p-1", None)])


def test_evidence_newer_than_the_prediction_timestamp_is_rejected():
    """The as-of rule: nothing observed after prediction_at may inform the estimate."""
    later = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    with pytest.raises(TemporalIntegrityError, match="leak the outcome"):
        validate_prediction_timing(JOURNEY_DATE, AWARE, [("p-42", later)])


def test_evidence_at_or_before_prediction_timestamp_is_accepted():
    assert validate_prediction_timing(
        JOURNEY_DATE,
        AWARE,
        [("p-1", datetime(2026, 10, 21, 7, 30, tzinfo=UTC)), ("p-2", None), ("p-3", AWARE)],
    ) is None

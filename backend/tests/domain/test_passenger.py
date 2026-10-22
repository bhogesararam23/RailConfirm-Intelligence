"""Unit tests for passenger reservation and observation domain types."""

from datetime import UTC, datetime

import pytest

from railconfirm.domain.exceptions import TemporalIntegrityError
from railconfirm.domain.passenger import (
    BookingGroup,
    PassengerReservation,
    make_observation,
)
from railconfirm.domain.status import NormalizedStatus

OBSERVED_AT = datetime(2026, 11, 10, 8, 0, 0, tzinfo=UTC)


def test_make_observation():
    obs = make_observation(
        raw_status="GNWL/15",
        source="manual_entry",
        observed_at=OBSERVED_AT,
        ingested_at=OBSERVED_AT,
    )
    assert obs.raw_status == "GNWL/15"
    assert obs.parsed.normalized == NormalizedStatus.WL
    assert obs.parsed.position == 15
    assert obs.source == "manual_entry"
    assert obs.observed_at == OBSERVED_AT
    assert obs.validation_state == "valid"


def test_observation_time_must_be_aware():
    """A naive timestamp cannot be compared against a prediction cutoff."""
    with pytest.raises(TemporalIntegrityError, match="no timezone offset"):
        make_observation(
            raw_status="CNF",
            source="manual_entry",
            observed_at=datetime(2026, 11, 10, 8, 0, 0),  # noqa: DTZ001 - deliberately naive
            ingested_at=OBSERVED_AT,
        )


def test_observation_cannot_be_newer_than_ingestion():
    with pytest.raises(TemporalIntegrityError, match="later than ingestion time"):
        make_observation(
            raw_status="CNF",
            source="manual_entry",
            observed_at=OBSERVED_AT,
            ingested_at=datetime(2026, 11, 9, tzinfo=UTC),
        )


def test_observation_without_observed_at():
    # Observed_at is nullable; unknown times must not be fabricated
    obs = make_observation(raw_status="CNF", source="manual_entry", observed_at=None)
    assert obs.observed_at is None
    assert obs.validation_state == "valid"


def test_unknown_status_observation_state():
    obs = make_observation(raw_status="INVALID_CODE", source="manual_entry")
    assert obs.validation_state == "unknown_status"
    assert obs.parsed.normalized == NormalizedStatus.UNKNOWN


def test_passenger_reservation_history():
    p = PassengerReservation()
    assert p.passenger_id is not None
    assert len(p.observation_history) == 0

    obs1 = make_observation("GNWL/30", source="manual_entry")
    p.set_original(obs1)
    assert p.original_booking_observation == obs1
    assert p.latest_observation == obs1

    obs2 = make_observation("GNWL/10", source="manual_entry")
    p.add_observation(obs2)
    assert p.latest_observation == obs2
    assert len(p.observation_history) == 2


def test_booking_group():
    group = BookingGroup()
    assert group.group_id is not None
    assert group.size == 0

    p1 = PassengerReservation()
    p2 = PassengerReservation()
    group.add_passenger(p1)
    group.add_passenger(p2)
    assert group.size == 2

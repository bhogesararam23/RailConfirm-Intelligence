"""Passenger reservation domain types for RailConfirm Intelligence.

Captures observations of reservation status over time without storing
passenger names or raw PNRs (per ADR-0005 privacy requirements).

Invariants
----------
* Raw status strings are always preserved.
* Observation timestamps are nullable; unknown time is documented, not fabricated.
* Original booking status is preserved independently from later observations.
* Prediction records are separate from observation records (immutable).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from railconfirm.domain.status import ParsedStatus, parse_status
from railconfirm.domain.journey import Journey


# ── StatusObservation ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StatusObservation:
    """Immutable record of one observed status at a given time.

    Fields
    ------
    raw_status:
        The verbatim status string from the source.
    parsed:
        Result of :func:`~railconfirm.domain.status.parse_status`.
    source:
        Free-text provenance label (e.g. ``"manual_entry"``,
        ``"dataset_import"``).
    observed_at:
        The time the status was observed. ``None`` if unknown — never
        fabricated.
    ingested_at:
        System clock at the moment of ingestion (must not be ``None``).
    validation_state:
        One of ``"valid"``, ``"unknown_status"``, ``"parse_warning"``.
    """

    raw_status: str
    parsed: ParsedStatus
    source: str
    observed_at: Optional[datetime]     # None = unknown time, not fabricated
    ingested_at: datetime               # System ingestion time (required)
    validation_state: str               # "valid" | "unknown_status" | "parse_warning"

    def __post_init__(self) -> None:
        allowed_states = {"valid", "unknown_status", "parse_warning"}
        if self.validation_state not in allowed_states:
            raise ValueError(
                f"validation_state must be one of {allowed_states}, "
                f"got {self.validation_state!r}."
            )
        if self.ingested_at is None:
            raise ValueError("ingested_at must not be None.")


def make_observation(
    raw_status: str,
    source: str,
    observed_at: Optional[datetime] = None,
    ingested_at: Optional[datetime] = None,
) -> StatusObservation:
    """Construct a :class:`StatusObservation` by parsing ``raw_status``.

    The ``validation_state`` is inferred from the parsed result:

    * ``"valid"`` — recognized status, no warnings.
    * ``"unknown_status"`` — normalized to ``UNKNOWN``.
    * ``"parse_warning"`` — recognized but carries a ``parse_note``.
    """
    from railconfirm.domain.status import NormalizedStatus

    parsed = parse_status(raw_status)
    now = ingested_at or datetime.now(timezone.utc)

    if parsed.normalized == NormalizedStatus.UNKNOWN:
        state = "unknown_status"
    elif parsed.parse_note is not None:
        state = "parse_warning"
    else:
        state = "valid"

    return StatusObservation(
        raw_status=raw_status,
        parsed=parsed,
        source=source,
        observed_at=observed_at,
        ingested_at=now,
        validation_state=state,
    )


# ── PassengerReservation ───────────────────────────────────────────────────────


@dataclass
class PassengerReservation:
    """One passenger's reservation within a booking group.

    No passenger name is stored (ADR-0005).

    Fields
    ------
    passenger_id:
        Randomly generated UUID; not derived from PNR or external identifiers.
    original_booking_observation:
        The status at time of booking. Preserved independently.
    latest_observation:
        The most recent observed status (may equal original if unchanged).
    observation_history:
        All observations in chronological order (oldest first).
    """

    passenger_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    original_booking_observation: Optional[StatusObservation] = None
    latest_observation: Optional[StatusObservation] = None
    observation_history: list[StatusObservation] = field(default_factory=list)

    def add_observation(self, obs: StatusObservation) -> None:
        """Append an observation to history and update ``latest_observation``.

        The history is kept in insertion order. Callers are responsible for
        providing observations in chronological order where possible.
        """
        self.observation_history.append(obs)
        self.latest_observation = obs

    def set_original(self, obs: StatusObservation) -> None:
        """Set the original booking observation (must be called at most once)."""
        if self.original_booking_observation is not None:
            raise ValueError(
                "original_booking_observation is already set; "
                "create a new PassengerReservation for a different booking."
            )
        self.original_booking_observation = obs
        if not self.observation_history:
            self.observation_history.append(obs)
            self.latest_observation = obs


# ── BookingGroup ───────────────────────────────────────────────────────────────


@dataclass
class BookingGroup:
    """A group of passengers sharing the same train, journey, and date.

    The raw PNR is NOT stored here (ADR-0005). ``group_id`` is a randomly
    generated UUID and must not be derived from a PNR.

    Fields
    ------
    group_id:
        Random UUID — not derived from PNR or passenger identifiers.
    journey:
        The shared journey context.
    passengers:
        Ordered list of passenger reservations.
    created_at:
        System UTC time when the group record was created.
    """

    group_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    journey: Optional[Journey] = None
    passengers: list[PassengerReservation] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_passenger(self, passenger: PassengerReservation) -> None:
        """Add a passenger to the group."""
        self.passengers.append(passenger)

    @property
    def size(self) -> int:
        """Number of passengers in the group."""
        return len(self.passengers)

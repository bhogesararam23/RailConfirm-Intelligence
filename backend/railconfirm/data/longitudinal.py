"""Longitudinal observation data contract and point-in-time snapshot conversion.

Phase 2 longitudinal data model for Indian Railways reservation outcome research.
Represents multi-observation booking histories across time:
- Journey and train information
- Pseudonymous booking/group and passenger identifiers
- Initial reservation status as booked
- Multiple sequential status observations across time with timezone-aware clocks
- Final-chart outcome verification and censoring state
- Provenance, permitted-use and consent metadata

Converts longitudinal histories into flat training interchange rows (contract v1.1.0)
as of a target cutoff timestamp or lead-day horizon without silently discarding
observation precision.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from railconfirm.domain.exceptions import DatasetValidationError, TemporalIntegrityError
from railconfirm.domain.status import NormalizedStatus, parse_status
from railconfirm.domain.validation import (
    MIN_LEAD_DAYS,
    ensure_aware,
    validate_journey_date,
    validate_station_code,
    validate_train_number,
)

LONGITUDINAL_SCHEMA_VERSION = "2.0.0"
"""Schema version of the longitudinal dataset contract."""


class VerificationMethod(str, Enum):
    """How the final-chart outcome was verified."""

    CHART_SNAPSHOT = "chart_snapshot"
    SMS_CONFIRMATION = "sms_confirmation"
    STATUS_ENQUIRY = "status_enquiry"
    OPERATOR_ATTESTATION = "operator_attestation"
    PASSENGER_SUBMISSION = "passenger_submission"
    UNKNOWN = "unknown"


class LabelConfidence(str, Enum):
    """Confidence level of the final outcome label."""

    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNVERIFIED = "unverified"


class CensoringReason(str, Enum):
    """Why an outcome was censored rather than observed."""

    USER_CANCELLED = "user_cancelled"
    TRAIN_CANCELLED = "train_cancelled"
    CHART_NOT_RECORDED = "chart_not_recorded"
    OUTCOME_MISSING = "outcome_missing"
    CONTRADICTORY_SOURCE = "contradictory_source"


@dataclass(frozen=True)
class StatusObservation:
    """One observation of a passenger's status at a specific point in time."""

    observation_id: str
    passenger_record_id: str
    observed_at: datetime
    status_raw: str
    status_category: NormalizedStatus
    status_position: int | None = None
    source_published_at: datetime | None = None
    source_id: str | None = None
    verification_state: str = "unverified"

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise DatasetValidationError("observation_id must be non-empty.")
        if not self.passenger_record_id.strip():
            raise DatasetValidationError("passenger_record_id must be non-empty.")
        ensure_aware(self.observed_at, "observed_at")
        if self.source_published_at is not None:
            ensure_aware(self.source_published_at, "source_published_at")
        if not self.status_raw.strip():
            raise DatasetValidationError("status_raw must not be blank.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "passenger_record_id": self.passenger_record_id,
            "observed_at": self.observed_at.isoformat(),
            "status_raw": self.status_raw,
            "status_category": self.status_category.value,
            "status_position": self.status_position,
            "source_published_at": (
                self.source_published_at.isoformat()
                if self.source_published_at
                else None
            ),
            "source_id": self.source_id,
            "verification_state": self.verification_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StatusObservation:
        observed_at = datetime.fromisoformat(str(data["observed_at"]))
        source_pub = data.get("source_published_at")
        source_published_at = (
            datetime.fromisoformat(str(source_pub)) if source_pub else None
        )
        cat_raw = str(data.get("status_category", ""))
        parsed = parse_status(str(data["status_raw"]))
        category = (
            NormalizedStatus(cat_raw)
            if cat_raw in NormalizedStatus._value2member_map_
            else parsed.category
        )
        return cls(
            observation_id=str(data["observation_id"]),
            passenger_record_id=str(data["passenger_record_id"]),
            observed_at=observed_at,
            status_raw=str(data["status_raw"]),
            status_category=category,
            status_position=(
                int(data["status_position"])
                if data.get("status_position") is not None
                else parsed.position
            ),
            source_published_at=source_published_at,
            source_id=str(data["source_id"]) if data.get("source_id") else None,
            verification_state=str(data.get("verification_state", "unverified")),
        )


@dataclass(frozen=True)
class FinalOutcome:
    """Verified outcome at final chart preparation."""

    outcome_target: str
    outcome_status_raw: str
    outcome_category: NormalizedStatus
    outcome_observed_at: datetime | None = None
    verification_source: str | None = None
    verification_method: VerificationMethod = VerificationMethod.UNKNOWN
    label_confidence: LabelConfidence = LabelConfidence.UNVERIFIED
    is_censored: bool = False
    censoring_reason: CensoringReason | None = None

    def __post_init__(self) -> None:
        if self.outcome_observed_at is not None:
            ensure_aware(self.outcome_observed_at, "outcome_observed_at")
        if self.is_censored and self.censoring_reason is None:
            raise DatasetValidationError("Censored outcome must provide censoring_reason.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_target": self.outcome_target,
            "outcome_status_raw": self.outcome_status_raw,
            "outcome_category": self.outcome_category.value,
            "outcome_observed_at": (
                self.outcome_observed_at.isoformat()
                if self.outcome_observed_at
                else None
            ),
            "verification_source": self.verification_source,
            "verification_method": self.verification_method.value,
            "label_confidence": self.label_confidence.value,
            "is_censored": self.is_censored,
            "censoring_reason": (
                self.censoring_reason.value if self.censoring_reason else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FinalOutcome:
        obs_raw = data.get("outcome_observed_at")
        observed_at = datetime.fromisoformat(str(obs_raw)) if obs_raw else None
        cat_raw = str(data.get("outcome_category", ""))
        parsed = parse_status(str(data["outcome_status_raw"]))
        category = (
            NormalizedStatus(cat_raw)
            if cat_raw in NormalizedStatus._value2member_map_
            else parsed.category
        )
        method_raw = str(data.get("verification_method", VerificationMethod.UNKNOWN.value))
        conf_raw = str(data.get("label_confidence", LabelConfidence.UNVERIFIED.value))
        cens_raw = data.get("censoring_reason")
        return cls(
            outcome_target=str(data.get("outcome_target", "final_chart_cnf")),
            outcome_status_raw=str(data["outcome_status_raw"]),
            outcome_category=category,
            outcome_observed_at=observed_at,
            verification_source=(
                str(data["verification_source"])
                if data.get("verification_source")
                else None
            ),
            verification_method=(
                VerificationMethod(method_raw)
                if method_raw in VerificationMethod._value2member_map_
                else VerificationMethod.UNKNOWN
            ),
            label_confidence=(
                LabelConfidence(conf_raw)
                if conf_raw in LabelConfidence._value2member_map_
                else LabelConfidence.UNVERIFIED
            ),
            is_censored=bool(data.get("is_censored", False)),
            censoring_reason=(
                CensoringReason(str(cens_raw))
                if cens_raw and str(cens_raw) in CensoringReason._value2member_map_
                else None
            ),
        )


@dataclass
class PassengerReservation:
    """One passenger within a booking, with initial status, longitudinal updates and outcome."""

    passenger_record_id: str
    booking_group_id: str
    passenger_sequence: int
    original_status_raw: str
    original_status_category: NormalizedStatus
    original_status_position: int | None = None
    original_observed_at: datetime | None = None
    observations: list[StatusObservation] = field(default_factory=list)
    outcome: FinalOutcome | None = None

    def __post_init__(self) -> None:
        if not self.passenger_record_id.strip():
            raise DatasetValidationError("passenger_record_id must be non-empty.")
        if self.passenger_sequence < 1:
            raise DatasetValidationError("passenger_sequence must be >= 1.")
        if self.original_observed_at is not None:
            ensure_aware(self.original_observed_at, "original_observed_at")

    def add_observation(self, observation: StatusObservation) -> None:
        """Add an observation, keeping observations chronologically ordered."""
        if observation.passenger_record_id != self.passenger_record_id:
            raise DatasetValidationError(
                f"Observation passenger_record_id {observation.passenger_record_id!r} "
                f"does not match passenger {self.passenger_record_id!r}."
            )
        self.observations.append(observation)
        self.observations.sort(key=lambda o: o.observed_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passenger_record_id": self.passenger_record_id,
            "booking_group_id": self.booking_group_id,
            "passenger_sequence": self.passenger_sequence,
            "original_status_raw": self.original_status_raw,
            "original_status_category": self.original_status_category.value,
            "original_status_position": self.original_status_position,
            "original_observed_at": (
                self.original_observed_at.isoformat()
                if self.original_observed_at
                else None
            ),
            "observations": [o.to_dict() for o in self.observations],
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PassengerReservation:
        orig_obs_raw = data.get("original_observed_at")
        orig_observed_at = (
            datetime.fromisoformat(str(orig_obs_raw)) if orig_obs_raw else None
        )
        parsed = parse_status(str(data["original_status_raw"]))
        cat_raw = str(data.get("original_status_category", ""))
        category = (
            NormalizedStatus(cat_raw)
            if cat_raw in NormalizedStatus._value2member_map_
            else parsed.category
        )
        instance = cls(
            passenger_record_id=str(data["passenger_record_id"]),
            booking_group_id=str(data["booking_group_id"]),
            passenger_sequence=int(data.get("passenger_sequence", 1)),
            original_status_raw=str(data["original_status_raw"]),
            original_status_category=category,
            original_status_position=(
                int(data["original_status_position"])
                if data.get("original_status_position") is not None
                else parsed.position
            ),
            original_observed_at=orig_observed_at,
            outcome=(
                FinalOutcome.from_dict(data["outcome"])
                if data.get("outcome")
                else None
            ),
        )
        for obs_data in data.get("observations", []):
            instance.add_observation(StatusObservation.from_dict(obs_data))
        return instance


@dataclass
class BookingGroup:
    """A booking group sharing journey context and priority queue position."""

    booking_group_id: str
    journey_id: str
    booking_created_at: datetime | None = None
    collection_basis: str = "research"
    consent_reference: str | None = None
    retention_expires_at: datetime | None = None
    passengers: list[PassengerReservation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.booking_group_id.strip():
            raise DatasetValidationError("booking_group_id must be non-empty.")
        if self.booking_created_at is not None:
            ensure_aware(self.booking_created_at, "booking_created_at")
        if self.retention_expires_at is not None:
            ensure_aware(self.retention_expires_at, "retention_expires_at")

    def add_passenger(self, passenger: PassengerReservation) -> None:
        if passenger.booking_group_id != self.booking_group_id:
            raise DatasetValidationError(
                f"Passenger booking_group_id {passenger.booking_group_id!r} "
                f"does not match group {self.booking_group_id!r}."
            )
        self.passengers.append(passenger)
        self.passengers.sort(key=lambda p: p.passenger_sequence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "booking_group_id": self.booking_group_id,
            "journey_id": self.journey_id,
            "booking_created_at": (
                self.booking_created_at.isoformat()
                if self.booking_created_at
                else None
            ),
            "collection_basis": self.collection_basis,
            "consent_reference": self.consent_reference,
            "retention_expires_at": (
                self.retention_expires_at.isoformat()
                if self.retention_expires_at
                else None
            ),
            "passengers": [p.to_dict() for p in self.passengers],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BookingGroup:
        created_raw = data.get("booking_created_at")
        booking_created_at = (
            datetime.fromisoformat(str(created_raw)) if created_raw else None
        )
        retention_raw = data.get("retention_expires_at")
        retention_expires_at = (
            datetime.fromisoformat(str(retention_raw)) if retention_raw else None
        )
        instance = cls(
            booking_group_id=str(data["booking_group_id"]),
            journey_id=str(data["journey_id"]),
            booking_created_at=booking_created_at,
            collection_basis=str(data.get("collection_basis", "research")),
            consent_reference=(
                str(data["consent_reference"])
                if data.get("consent_reference")
                else None
            ),
            retention_expires_at=retention_expires_at,
        )
        for p_data in data.get("passengers", []):
            instance.add_passenger(PassengerReservation.from_dict(p_data))
        return instance


@dataclass(frozen=True)
class LongitudinalJourney:
    """Journey context for one train departure."""

    journey_id: str
    train_number: str
    journey_date: date
    boarding_station: str
    destination_station: str
    class_code: str
    quota_code: str
    scheduled_departure_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.journey_id.strip():
            raise DatasetValidationError("journey_id must be non-empty.")
        validate_train_number(self.train_number)
        validate_station_code(self.boarding_station, "boarding_station")
        validate_station_code(self.destination_station, "destination_station")
        if self.scheduled_departure_at is not None:
            ensure_aware(self.scheduled_departure_at, "scheduled_departure_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "train_number": self.train_number,
            "journey_date": self.journey_date.isoformat(),
            "boarding_station": self.boarding_station,
            "destination_station": self.destination_station,
            "class_code": self.class_code,
            "quota_code": self.quota_code,
            "scheduled_departure_at": (
                self.scheduled_departure_at.isoformat()
                if self.scheduled_departure_at
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LongitudinalJourney:
        j_date = validate_journey_date(data["journey_date"])
        dep_raw = data.get("scheduled_departure_at")
        dep_at = datetime.fromisoformat(str(dep_raw)) if dep_raw else None
        return cls(
            journey_id=str(data["journey_id"]),
            train_number=validate_train_number(data["train_number"]),
            journey_date=j_date,
            boarding_station=validate_station_code(data["boarding_station"], "boarding_station"),
            destination_station=validate_station_code(data["destination_station"], "destination_station"),
            class_code=str(data["class_code"]).strip().upper(),
            quota_code=str(data["quota_code"]).strip().upper(),
            scheduled_departure_at=dep_at,
        )


@dataclass
class LongitudinalDataset:
    """Top-level container for a longitudinal observation dataset."""

    dataset_id: str
    source_id: str
    created_at: datetime
    journeys: dict[str, LongitudinalJourney] = field(default_factory=dict)
    booking_groups: list[BookingGroup] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = LONGITUDINAL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        ensure_aware(self.created_at, "created_at")

    def add_journey(self, journey: LongitudinalJourney) -> None:
        self.journeys[journey.journey_id] = journey

    def add_booking_group(self, booking_group: BookingGroup) -> None:
        if booking_group.journey_id not in self.journeys:
            raise DatasetValidationError(
                f"BookingGroup {booking_group.booking_group_id} references journey "
                f"{booking_group.journey_id} which does not exist in dataset journeys."
            )
        self.booking_groups.append(booking_group)

    @property
    def total_passengers(self) -> int:
        return sum(len(bg.passengers) for bg in self.booking_groups)

    @property
    def total_observations(self) -> int:
        return sum(
            len(p.observations)
            for bg in self.booking_groups
            for p in bg.passengers
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "journeys": [j.to_dict() for j in self.journeys.values()],
            "booking_groups": [bg.to_dict() for bg in self.booking_groups],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LongitudinalDataset:
        created_at = datetime.fromisoformat(str(data["created_at"]))
        dataset = cls(
            dataset_id=str(data["dataset_id"]),
            source_id=str(data["source_id"]),
            created_at=created_at,
            metadata=dict(data.get("metadata", {})),
            schema_version=str(data.get("schema_version", LONGITUDINAL_SCHEMA_VERSION)),
        )
        for j_data in data.get("journeys", []):
            dataset.add_journey(LongitudinalJourney.from_dict(j_data))
        for bg_data in data.get("booking_groups", []):
            dataset.add_booking_group(BookingGroup.from_dict(bg_data))
        return dataset

    def save(self, path: str | Path) -> None:
        save_longitudinal_dataset(self, path)


@dataclass(frozen=True)
class SnapshotResult:
    """Result of converting a longitudinal dataset into a point-in-time training frame."""

    frame: pd.DataFrame
    total_passengers_considered: int
    rows_emitted: int
    rows_skipped_no_observation: int
    rows_skipped_censored: int
    rows_skipped_lead_time_violation: int
    cutoff_specification: str


def create_point_in_time_snapshot(
    dataset: LongitudinalDataset,
    *,
    as_of_lead_days: int | None = None,
    as_of_datetime: datetime | None = None,
    allow_censored: bool = False,
) -> SnapshotResult:
    """Transform longitudinal histories into flat training interchange rows (contract v1.1.0).

    For each passenger, determines the latest observation observed *at or before* the
    effective cutoff instant.

    Parameters
    ----------
    dataset:
        The longitudinal observation dataset.
    as_of_lead_days:
        Integer days before journey date (e.g. 5 means 5 days before departure).
        Mutually exclusive with as_of_datetime.
    as_of_datetime:
        Exact global timezone-aware cutoff timestamp.
        Mutually exclusive with as_of_lead_days.
    allow_censored:
        Whether to emit rows with censored final chart labels (default False, as
        training models requires verified non-censored outcomes).

    Returns
    -------
    SnapshotResult
        Carrying the pandas DataFrame ready for validation/training and accounting metrics.
    """
    if (as_of_lead_days is None and as_of_datetime is None) or (
        as_of_lead_days is not None and as_of_datetime is not None
    ):
        raise ValueError("Must specify exactly one of as_of_lead_days or as_of_datetime.")

    if as_of_lead_days is not None and as_of_lead_days < MIN_LEAD_DAYS:
        raise TemporalIntegrityError(
            f"as_of_lead_days={as_of_lead_days} is less than MIN_LEAD_DAYS={MIN_LEAD_DAYS}. "
            "Same-day or post-chart snapshots cannot be predicted."
        )

    if as_of_datetime is not None:
        ensure_aware(as_of_datetime, "as_of_datetime")

    rows: list[dict[str, Any]] = []
    total_considered = 0
    skipped_no_obs = 0
    skipped_censored = 0
    skipped_lead = 0

    is_synthetic = bool(dataset.metadata.get("is_synthetic", False))

    cutoff_desc = (
        f"lead_days={as_of_lead_days}"
        if as_of_lead_days is not None
        else f"datetime={as_of_datetime.isoformat()}"
    )

    for bg in dataset.booking_groups:
        journey = dataset.journeys[bg.journey_id]

        if as_of_lead_days is not None:
            # Cutoff is exact midnight start of the observation date in UTC
            cutoff_date = journey.journey_date - timedelta(days=as_of_lead_days)
            cutoff_time = datetime(
                cutoff_date.year, cutoff_date.month, cutoff_date.day, 23, 59, 59, tzinfo=UTC
            )
            obs_date_str = cutoff_date.isoformat()
        else:
            assert as_of_datetime is not None
            cutoff_time = as_of_datetime
            cutoff_date = cutoff_time.date()
            obs_date_str = cutoff_date.isoformat()

            # Check lead days constraint for this specific journey
            lead_days = (journey.journey_date - cutoff_date).days
            if lead_days < MIN_LEAD_DAYS:
                skipped_lead += len(bg.passengers)
                total_considered += len(bg.passengers)
                continue

        for p in bg.passengers:
            total_considered += 1

            if p.outcome is None:
                skipped_no_obs += 1
                continue

            if p.outcome.is_censored and not allow_censored:
                skipped_censored += 1
                continue

            # Find latest observation at or before cutoff_time
            eligible_obs = [
                o for o in p.observations if o.observed_at <= cutoff_time
            ]

            if eligible_obs:
                latest_obs = max(eligible_obs, key=lambda o: o.observed_at)
                current_status_val = latest_obs.status_raw
                source_id_val = latest_obs.source_id or dataset.source_id
            else:
                # Fall back to original booking status if booked prior to cutoff
                if p.original_observed_at and p.original_observed_at > cutoff_time:
                    skipped_no_obs += 1
                    continue
                current_status_val = p.original_status_raw
                source_id_val = dataset.source_id

            row_data: dict[str, Any] = {
                "train_number": journey.train_number,
                "journey_date": journey.journey_date.isoformat(),
                "class_code": journey.class_code,
                "quota_code": journey.quota_code,
                "initial_status": p.original_status_raw,
                "final_chart_status": p.outcome.outcome_status_raw,
                "observation_date": obs_date_str,
                "booking_group_id": bg.booking_group_id,
                "passenger_record_id": p.passenger_record_id,
                "current_status": current_status_val,
                "source_id": source_id_val,
                "verification_method": p.outcome.verification_method.value,
                "censoring_reason": (
                    p.outcome.censoring_reason.value if p.outcome.censoring_reason else None
                ),
                "is_synthetic": is_synthetic,
            }
            rows.append(row_data)

    df = pd.DataFrame(rows)
    return SnapshotResult(
        frame=df,
        total_passengers_considered=total_considered,
        rows_emitted=len(rows),
        rows_skipped_no_observation=skipped_no_obs,
        rows_skipped_censored=skipped_censored,
        rows_skipped_lead_time_violation=skipped_lead,
        cutoff_specification=cutoff_desc,
    )


def save_longitudinal_dataset(dataset: LongitudinalDataset, path: str | Path) -> None:
    """Save a longitudinal dataset to disk as deterministic formatted JSON."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dataset.to_dict()
    text = json.dumps(payload, indent=2, sort_keys=True)
    out_path.write_text(text, encoding="utf-8")


def load_longitudinal_dataset(path: str | Path) -> LongitudinalDataset:
    """Load a longitudinal dataset from a JSON file."""
    in_path = Path(path)
    if not in_path.is_file():
        raise FileNotFoundError(f"File not found: {in_path}")
    raw_text = in_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"Invalid JSON in {in_path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise DatasetValidationError(f"Expected JSON object in {in_path.name}, got {type(data).__name__}.")
    return LongitudinalDataset.from_dict(data)

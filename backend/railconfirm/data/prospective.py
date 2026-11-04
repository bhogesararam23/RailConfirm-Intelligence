"""Local-first, consent-aware prospective data collection foundation.

Phase 2 foundation for prospective railway reservation data intake:
- Strict PII, raw PNR, and contact identifier scanning
- Cryptographically salted pseudonymous identifier generation
- Explicit consent basis, notice version, and permitted-purpose tracking
- Mandatory local operator review and approval workflow (disabled by default)
- Safe export into longitudinal observation datasets (schema v2.0.0)

Rules enforce:
1. No raw 10-digit PNRs or personal identifiers may enter storage or datasets.
2. Technical intake and human research approval remain strictly decoupled.
3. Collection is local-first, requires explicit operator enablement, and does not
   expose network endpoints (ADR-0007).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    FinalOutcome,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    StatusObservation,
    ensure_aware,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError
from railconfirm.domain.status import NormalizedStatus
from railconfirm.domain.validation import (
    validate_journey_date,
    validate_station_code,
    validate_train_number,
)

PROSPECTIVE_COLLECTION_SCHEMA_VERSION = "1.0.0"
DEFAULT_NOTICE_VERSION = "2026.1"
DEFAULT_RETENTION_POLICY = "pseudonymous_research_only"

PERMITTED_CONSENT_BASES = (
    "explicit_opt_in",
    "user_initiated_submission",
    "institutional_research_agreement",
)

PERMITTED_PURPOSES = (
    "confirmation_probability_research",
    "model_calibration",
    "cancellation_modeling",
    "railway_operations_benchmarking",
)

# Regex patterns for Indian railway personal data scanning
_PNR_PATTERN = re.compile(r"\b[1-9]\d{2}[-\s]?\d{7}\b|\b[1-9]\d{9}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")
_AADHAAR_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")


class ReviewStatus(str, Enum):
    """Operator review status of prospective submissions."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


def scan_for_personal_data(data: Any, path: str = "root") -> list[str]:
    """Recursively scan an object for raw PNRs, emails, phone numbers, and Aadhaar numbers.

    Returns:
        List of diagnostic violation messages. Empty if clean.
    """
    violations: list[str] = []

    if isinstance(data, str):
        if _PNR_PATTERN.search(data):
            violations.append(f"Potential 10-digit Indian Railway PNR pattern at '{path}'")
        if _EMAIL_PATTERN.search(data):
            violations.append(f"Email address pattern detected at '{path}'")
        if _PHONE_PATTERN.search(data):
            violations.append(f"Indian mobile phone pattern detected at '{path}'")
        if _AADHAAR_PATTERN.search(data):
            violations.append(f"12-digit Aadhaar/national ID pattern detected at '{path}'")
    elif isinstance(data, Mapping):
        for k, v in data.items():
            violations.extend(scan_for_personal_data(v, f"{path}.{k}"))
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            violations.extend(scan_for_personal_data(item, f"{path}[{idx}]"))

    return violations


def derive_pseudonym(raw_identifier: str, salt: str, prefix: str = "anon") -> str:
    """Generate a cryptographically salted one-way pseudonymous identifier.

    Args:
        raw_identifier: The identifier to pseudonymise.
        salt: Secret cryptographic salt known only to the local deployment.
        prefix: Prefix for readability (default: 'anon').

    Returns:
        Safe non-reversible pseudonymous string (e.g. 'anon_a1b2c3d4e5f60718').
    """
    if not salt.strip():
        raise SecurityError("A non-empty cryptographic salt is required to derive pseudonyms.")
    digest = hmac.new(
        salt.encode("utf-8"),
        raw_identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{prefix}_{digest[:16]}"


@dataclass(frozen=True)
class ConsentMetadata:
    """Explicit consent and authority record for prospective data collection."""

    consent_basis: str
    notice_version: str
    purpose_records: list[str]
    retention_policy: str = DEFAULT_RETENTION_POLICY
    collected_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat()
    )
    data_subject_region: str = "IN"

    def __post_init__(self) -> None:
        if self.consent_basis not in PERMITTED_CONSENT_BASES:
            raise DatasetValidationError(
                f"Invalid consent_basis '{self.consent_basis}'; must be one of {PERMITTED_CONSENT_BASES}"
            )
        if not self.notice_version.strip():
            raise DatasetValidationError("notice_version must be non-empty.")
        if not self.purpose_records:
            raise DatasetValidationError("purpose_records must specify at least one permitted purpose.")
        for p in self.purpose_records:
            if p not in PERMITTED_PURPOSES:
                raise DatasetValidationError(
                    f"Invalid purpose '{p}'; must be one of {PERMITTED_PURPOSES}"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConsentMetadata:
        return cls(
            consent_basis=str(data["consent_basis"]),
            notice_version=str(data["notice_version"]),
            purpose_records=list(data["purpose_records"]),
            retention_policy=str(data.get("retention_policy", DEFAULT_RETENTION_POLICY)),
            collected_at=str(data.get("collected_at", datetime.now(tz=UTC).isoformat())),
            data_subject_region=str(data.get("data_subject_region", "IN")),
        )


@dataclass
class ProspectivePassenger:
    """One passenger reservation within a prospective group submission."""

    passenger_sequence: int
    original_status_raw: str
    original_status_category: NormalizedStatus
    original_status_position: int | None = None
    observations: list[StatusObservation] = field(default_factory=list)
    outcome: FinalOutcome | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passenger_sequence": self.passenger_sequence,
            "original_status_raw": self.original_status_raw,
            "original_status_category": self.original_status_category.value,
            "original_status_position": self.original_status_position,
            "observations": [obs.to_dict() for obs in self.observations],
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProspectivePassenger:
        return cls(
            passenger_sequence=int(data["passenger_sequence"]),
            original_status_raw=str(data["original_status_raw"]),
            original_status_category=NormalizedStatus(str(data["original_status_category"])),
            original_status_position=(
                int(data["original_status_position"])
                if data.get("original_status_position") is not None
                else None
            ),
            observations=[
                StatusObservation.from_dict(o) for o in data.get("observations", [])
            ],
            outcome=(
                FinalOutcome.from_dict(data["outcome"])
                if data.get("outcome") is not None
                else None
            ),
        )


@dataclass
class ProspectiveSubmission:
    """A user or partner group journey submission collected under explicit consent."""

    submission_id: str
    pseudonym_group_id: str
    train_number: str
    journey_date: date
    boarding_station: str
    destination_station: str
    class_code: str
    consent: ConsentMetadata
    passengers: list[ProspectivePassenger] = field(default_factory=list)
    quota_code: str = "GN"
    scheduled_departure_at: datetime | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None

    def __post_init__(self) -> None:
        validate_train_number(self.train_number)
        validate_journey_date(self.journey_date)
        validate_station_code(self.boarding_station, "boarding_station")
        validate_station_code(self.destination_station, "destination_station")
        if not self.class_code.strip():
            raise DatasetValidationError("class_code must not be empty.")
        if not self.quota_code.strip():
            raise DatasetValidationError("quota_code must not be empty.")
        if self.scheduled_departure_at is not None:
            ensure_aware(self.scheduled_departure_at, "scheduled_departure_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "pseudonym_group_id": self.pseudonym_group_id,
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
            "consent": self.consent.to_dict(),
            "passengers": [p.to_dict() for p in self.passengers],
            "review_status": self.review_status.value,
            "review_notes": self.review_notes,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProspectiveSubmission:
        dep_raw = data.get("scheduled_departure_at")
        dep_at = datetime.fromisoformat(str(dep_raw)) if dep_raw else None
        return cls(
            submission_id=str(data["submission_id"]),
            pseudonym_group_id=str(data["pseudonym_group_id"]),
            train_number=str(data["train_number"]),
            journey_date=validate_journey_date(data["journey_date"]),
            boarding_station=str(data["boarding_station"]),
            destination_station=str(data["destination_station"]),
            class_code=str(data["class_code"]),
            quota_code=str(data.get("quota_code", "GN")),
            scheduled_departure_at=dep_at,
            consent=ConsentMetadata.from_dict(data["consent"]),
            passengers=[
                ProspectivePassenger.from_dict(p) for p in data.get("passengers", [])
            ],
            review_status=ReviewStatus(str(data.get("review_status", ReviewStatus.PENDING_REVIEW.value))),
            review_notes=data.get("review_notes"),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=data.get("reviewed_at"),
        )


@dataclass
class ProspectiveBatch:
    """A versioned batch of prospective submissions managed under local operator controls."""

    batch_id: str
    created_at: datetime
    submissions: list[ProspectiveSubmission] = field(default_factory=list)
    schema_version: str = PROSPECTIVE_COLLECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        ensure_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "submissions": [s.to_dict() for s in self.submissions],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProspectiveBatch:
        return cls(
            batch_id=str(data["batch_id"]),
            schema_version=str(data.get("schema_version", PROSPECTIVE_COLLECTION_SCHEMA_VERSION)),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            submissions=[
                ProspectiveSubmission.from_dict(s) for s in data.get("submissions", [])
            ],
        )

    def save(self, path: Path | str) -> None:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path | str) -> ProspectiveBatch:
        source = Path(path).resolve()
        with source.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def intake_prospective_submission(
    submission: ProspectiveSubmission,
    *,
    reject_on_pii: bool = True,
) -> tuple[bool, list[str]]:
    """Scan and validate an incoming prospective submission before storage.

    Args:
        submission: The ProspectiveSubmission to evaluate.
        reject_on_pii: When True, rejects on any PII/PNR detection.

    Returns:
        Tuple of (is_accepted, diagnostics).
    """
    diagnostics = scan_for_personal_data(submission.to_dict())

    if diagnostics:
        if reject_on_pii:
            submission.review_status = ReviewStatus.QUARANTINED
            submission.review_notes = f"Quarantined due to PII scan violations: {diagnostics}"
            return False, diagnostics

    return True, []


def approve_batch_for_research(
    batch: ProspectiveBatch,
    *,
    reviewer: str,
    rationale: str,
) -> None:
    """Local operator action to approve a prospective collection batch for research.

    Enforces that reviewer and rationale are recorded durably.
    """
    review_batch(batch, action=ReviewStatus.APPROVED, reviewer=reviewer, rationale=rationale)


def review_batch(
    batch: ProspectiveBatch,
    *,
    action: ReviewStatus,
    reviewer: str,
    rationale: str,
) -> None:
    """Apply an operator review decision across all submissions in a prospective batch.

    Args:
        batch: The prospective batch being reviewed.
        action: The target ReviewStatus (APPROVED, REJECTED, QUARANTINED).
        reviewer: Identifier of the human operator or authority.
        rationale: Durable explanation for the review decision.
    """
    if not reviewer.strip():
        raise DatasetValidationError("Review action requires a named human reviewer.")
    if not rationale.strip():
        raise DatasetValidationError("Review action requires a non-empty rationale.")

    if action == ReviewStatus.APPROVED:
        violations = scan_for_personal_data(batch.to_dict())
        if violations:
            raise SecurityError(
                f"Cannot approve prospective batch with unresolved personal data: {violations}"
            )

    now_iso = datetime.now(tz=UTC).isoformat()
    for sub in batch.submissions:
        if action == ReviewStatus.APPROVED and sub.review_status == ReviewStatus.QUARANTINED:
            raise DatasetValidationError(
                f"Cannot approve quarantined submission '{sub.submission_id}' without resolution."
            )
        sub.review_status = action
        sub.reviewed_by = reviewer
        sub.review_notes = rationale
        sub.reviewed_at = now_iso


@dataclass(frozen=True)
class ProspectiveAuditReport:
    """Comprehensive validation and privacy audit report for prospective collection batches."""

    batch_id: str
    schema_version: str
    total_submissions: int
    total_passengers: int
    total_observations: int
    review_status_counts: dict[str, int]
    pii_violations: list[str]
    structural_errors: list[str]
    is_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "schema_version": self.schema_version,
            "total_submissions": self.total_submissions,
            "total_passengers": self.total_passengers,
            "total_observations": self.total_observations,
            "review_status_counts": self.review_status_counts,
            "pii_violations": self.pii_violations,
            "structural_errors": self.structural_errors,
            "is_valid": self.is_valid,
        }

    def summary(self) -> str:
        status_lines = ", ".join(
            f"{k}: {v}" for k, v in sorted(self.review_status_counts.items())
        )
        lines = [
            f"Prospective Batch: {self.batch_id} (schema v{self.schema_version})",
            f"Valid: {'yes' if self.is_valid else 'no'}",
            f"Submissions: {self.total_submissions}, Passengers: {self.total_passengers}, Observations: {self.total_observations}",
            f"Review Status: [{status_lines}]",
        ]
        if self.pii_violations:
            lines.append(f"PII Violations ({len(self.pii_violations)}):")
            for viol in self.pii_violations[:10]:
                lines.append(f"  - {viol}")
            if len(self.pii_violations) > 10:
                lines.append(f"  ... and {len(self.pii_violations) - 10} more")
        if self.structural_errors:
            lines.append(f"Structural Errors ({len(self.structural_errors)}):")
            for err in self.structural_errors[:10]:
                lines.append(f"  - {err}")
            if len(self.structural_errors) > 10:
                lines.append(f"  ... and {len(self.structural_errors) - 10} more")
        return "\n".join(lines)


def validate_prospective_batch(batch: ProspectiveBatch) -> ProspectiveAuditReport:
    """Validate a prospective batch for structure, privacy/PII compliance, and data integrity."""
    pii_violations = scan_for_personal_data(batch.to_dict())
    errors: list[str] = []

    total_submissions = len(batch.submissions)
    total_passengers = 0
    total_obs = 0
    status_counts: dict[str, int] = {
        ReviewStatus.PENDING_REVIEW.value: 0,
        ReviewStatus.APPROVED.value: 0,
        ReviewStatus.QUARANTINED.value: 0,
        ReviewStatus.REJECTED.value: 0,
    }

    sub_ids: set[str] = set()
    pseudo_ids: set[str] = set()

    for idx, sub in enumerate(batch.submissions):
        status_counts[sub.review_status.value] = (
            status_counts.get(sub.review_status.value, 0) + 1
        )

        if sub.submission_id in sub_ids:
            errors.append(f"Duplicate submission_id '{sub.submission_id}' at index {idx}.")
        sub_ids.add(sub.submission_id)

        if sub.pseudonym_group_id in pseudo_ids:
            errors.append(
                f"Duplicate pseudonym_group_id '{sub.pseudonym_group_id}' at index {idx}."
            )
        pseudo_ids.add(sub.pseudonym_group_id)

        if not sub.passengers:
            errors.append(f"Submission '{sub.submission_id}' has no passenger reservations.")

        seen_sequences: set[int] = set()
        for p in sub.passengers:
            total_passengers += 1
            if p.passenger_sequence in seen_sequences:
                errors.append(
                    f"Submission '{sub.submission_id}' has duplicate passenger_sequence {p.passenger_sequence}."
                )
            seen_sequences.add(p.passenger_sequence)
            total_obs += len(p.observations)

    is_valid = len(pii_violations) == 0 and len(errors) == 0

    return ProspectiveAuditReport(
        batch_id=batch.batch_id,
        schema_version=batch.schema_version,
        total_submissions=total_submissions,
        total_passengers=total_passengers,
        total_observations=total_obs,
        review_status_counts=status_counts,
        pii_violations=pii_violations,
        structural_errors=errors,
        is_valid=is_valid,
    )


def export_batch_to_longitudinal(
    batch: ProspectiveBatch,
    *,
    dataset_id: str,
    source_id: str,
    require_all_approved: bool = True,
) -> LongitudinalDataset:
    """Export approved submissions from a prospective batch into a LongitudinalDataset (v2.0.0).

    Args:
        batch: The prospective batch to export.
        dataset_id: Desired ID for the exported longitudinal dataset.
        source_id: Provenance source ID.
        require_all_approved: When True, raises error if any submission is unapproved.

    Returns:
        A validated LongitudinalDataset ready for manifest generation or point-in-time snapshotting.
    """
    journeys: dict[str, LongitudinalJourney] = {}
    booking_groups: list[BookingGroup] = []

    for sub in batch.submissions:
        if require_all_approved and sub.review_status != ReviewStatus.APPROVED:
            raise DatasetValidationError(
                f"Submission '{sub.submission_id}' is {sub.review_status.value}; "
                "only APPROVED submissions can be exported to research datasets."
            )
        if sub.review_status != ReviewStatus.APPROVED:
            continue

        # Create or retrieve journey
        j_key = f"{sub.train_number}_{sub.journey_date}_{sub.boarding_station}_{sub.destination_station}_{sub.class_code}"
        if j_key not in journeys:
            journeys[j_key] = LongitudinalJourney(
                journey_id=j_key,
                train_number=sub.train_number,
                journey_date=sub.journey_date,
                boarding_station=sub.boarding_station,
                destination_station=sub.destination_station,
                class_code=sub.class_code,
                quota_code=sub.quota_code,
                scheduled_departure_at=sub.scheduled_departure_at,
            )

        # Convert passengers
        p_records: list[PassengerReservation] = []
        for p in sub.passengers:
            pid = f"{sub.pseudonym_group_id}_P{p.passenger_sequence}"
            # Ensure observations have matching passenger_record_id
            adapted_obs: list[StatusObservation] = []
            for obs in p.observations:
                adapted_obs.append(
                    StatusObservation(
                        observation_id=obs.observation_id,
                        passenger_record_id=pid,
                        observed_at=obs.observed_at,
                        status_raw=obs.status_raw,
                        status_category=obs.status_category,
                        status_position=obs.status_position,
                        source_published_at=obs.source_published_at,
                        source_id=obs.source_id,
                        verification_state=obs.verification_state,
                    )
                )

            p_records.append(
                PassengerReservation(
                    passenger_record_id=pid,
                    booking_group_id=sub.pseudonym_group_id,
                    passenger_sequence=p.passenger_sequence,
                    original_status_raw=p.original_status_raw,
                    original_status_category=p.original_status_category,
                    original_status_position=p.original_status_position,
                    original_observed_at=(
                        adapted_obs[0].observed_at if adapted_obs else None
                    ),
                    observations=adapted_obs,
                    outcome=p.outcome,
                )
            )

        bg = BookingGroup(
            booking_group_id=sub.pseudonym_group_id,
            journey_id=j_key,
            passengers=p_records,
        )
        booking_groups.append(bg)

    return LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id=dataset_id,
        source_id=source_id,
        created_at=datetime.now(tz=UTC),
        journeys=journeys,
        booking_groups=booking_groups,
        metadata={
            "exported_from_prospective_batch": batch.batch_id,
            "export_schema_version": PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
        },
    )

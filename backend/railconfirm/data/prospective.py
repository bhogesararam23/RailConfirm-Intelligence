"""Local-first, consent-aware prospective data collection foundation.

Phase 2 foundation for prospective railway reservation data intake:
- Strict PII, raw PNR, tax ID, passport, and contact identifier scanning
- Cryptographically salted pseudonymous identifier generation
- Explicit consent basis, notice version, permitted-purpose, and withdrawal tracking
- Mandatory local operator review and approval workflow (disabled by default)
- Safe export into longitudinal observation datasets (schema v2.0.0)
- Scientific pilot coverage metrics and threshold readiness evaluation

Rules enforce:
1. No raw 10-digit PNRs or personal identifiers may enter storage or datasets.
2. Technical intake and human research approval remain strictly decoupled.
3. Collection is local-first, requires explicit operator enablement, and does not
   expose network endpoints (ADR-0007).
4. Pseudonymization is not irreversible anonymization; strong secret salts (>= 32 chars)
   are required to resist dictionary attacks across the finite 10-digit PNR space (~10^10).
5. Participant consent withdrawal permanently excludes submissions from research export.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    FinalOutcome,
    LabelConfidence,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    StatusObservation,
    VerificationMethod,
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
PERMITTED_NOTICE_VERSIONS = ("2026.1",)
DEFAULT_RETENTION_POLICY = "pseudonymous_research_only"

# Minimum cryptographic salt length in characters to resist rainbow-table inversion
# over the finite 10-digit Indian Railway PNR space (10^10 combinations, ~33 bits)
MIN_SALT_LENGTH = 32

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

# Scientific pilot and evaluation threshold constants
FEASIBILITY_MIN_RESERVATIONS = 30
FEASIBILITY_MIN_DATES = 3
FEASIBILITY_MIN_TRAINS = 2

ELIGIBILITY_MIN_RESERVATIONS = 50
ELIGIBILITY_MIN_DATES = 2

BASELINE_EXPERIMENT_MIN_RESERVATIONS = 300
BASELINE_EXPERIMENT_MIN_DATES = 12
BASELINE_EXPERIMENT_MIN_DAYS_SPAN = 28
BASELINE_EXPERIMENT_MIN_CLASS_RESERVATIONS = 50

SUBGROUP_EVALUATION_MIN_RESERVATIONS = 1000
SUBGROUP_EVALUATION_MIN_DATES = 30
SUBGROUP_EVALUATION_MIN_MULTI_GROUPS = 150

# Regex patterns for Indian railway personal data scanning
_PNR_PATTERN = re.compile(r"\b[1-9]\d{2}[-\s]?\d{7}\b|\b[1-9]\d{9}\b")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")
_AADHAAR_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
_PASSPORT_PATTERN = re.compile(r"\b[A-Z][1-9]\d{6}\b")
_URL_TOKEN_PATTERN = re.compile(r"(?:token|pnr|auth|key|secret)=([^\s&]+)", re.IGNORECASE)


class ReviewStatus(str, Enum):
    """Operator review status of prospective submissions."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


def mask_sensitive_token(token: str) -> str:
    """Safely mask a sensitive token for diagnostic display without leaking content."""
    clean = token.strip()
    if len(clean) <= 4:
        return "****"
    if "@" in clean:
        parts = clean.split("@", 1)
        user = parts[0]
        domain = parts[1]
        masked_user = user[:2] + "****" if len(user) > 2 else "****"
        return f"{masked_user}@{domain}"
    return clean[:2] + "****" + clean[-2:]


def get_configured_pseudonym_salt(
    env_var: str = "RAILCONFIRM_PSEUDONYM_SALT",
    default: str | None = None,
) -> str:
    """Retrieve and validate the deployment secret pseudonymization salt from environment.

    Raises:
        SecurityError: If salt is missing, empty, or shorter than MIN_SALT_LENGTH (32 chars).
    """
    salt = os.environ.get(env_var, default or "").strip()
    if not salt:
        raise SecurityError(
            f"No cryptographic salt configured in environment variable '{env_var}'. "
            f"A secret salt of at least {MIN_SALT_LENGTH} characters is required."
        )
    if len(salt) < MIN_SALT_LENGTH:
        raise SecurityError(
            f"Configured salt in '{env_var}' is too weak ({len(salt)} chars). "
            f"Must be at least {MIN_SALT_LENGTH} characters to resist dictionary inversion."
        )
    return salt


def atomic_write_json(
    path: Path | str,
    data: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
) -> Path:
    """Atomically write JSON data to a destination path using a temporary file.

    Guarantees that interruptions or write errors will never truncate or corrupt
    an existing file. Writes to a temporary file in the same directory (to ensure
    same-filesystem atomic rename) and replaces the destination via os.replace.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        delete=False,
        prefix=f".tmp_{target.name}_",
    )
    temp_path = Path(temp_file.name)
    try:
        json.dump(data, temp_file, indent=indent, sort_keys=sort_keys)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        os.replace(temp_path, target)
        return target
    except Exception:
        temp_file.close()
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def scan_for_personal_data(
    data: Any,
    path: str = "root",
    seen: set[int] | None = None,
) -> list[str]:
    """Recursively scan an object for raw PNRs, emails, phone numbers, and IDs.

    TECHNICAL SAFEGUARD NOTE:
    This regex scanner is a heuristic technical filter designed to catch explicit
    common identifiers (10-digit PNRs, emails, phone numbers, Aadhaar, PAN, passport,
    and credential query parameters). It does NOT constitute a legal guarantee that
    a dataset contains zero personal or linkable data. Unstructured names, rare
    journey timing combinations, and auxiliary passenger attributes require
    qualitative human governance and review.

    Returns:
        List of diagnostic violation messages with masked tokens. Empty if clean.
    """
    violations: list[str] = []
    if seen is None:
        seen = set()

    obj_id = id(data)
    if isinstance(data, (Mapping, list, tuple, set)):
        if obj_id in seen:
            return []
        seen.add(obj_id)

    if isinstance(data, str):
        m_pnr = _PNR_PATTERN.search(data)
        if m_pnr:
            violations.append(
                f"Potential 10-digit Indian Railway PNR pattern at '{path}' (masked: '{mask_sensitive_token(m_pnr.group(0))}')"
            )
        m_email = _EMAIL_PATTERN.search(data)
        if m_email:
            violations.append(
                f"Email address pattern detected at '{path}' (masked: '{mask_sensitive_token(m_email.group(0))}')"
            )
        m_phone = _PHONE_PATTERN.search(data)
        if m_phone:
            violations.append(
                f"Indian mobile phone pattern detected at '{path}' (masked: '{mask_sensitive_token(m_phone.group(0))}')"
            )
        m_aadhaar = _AADHAAR_PATTERN.search(data)
        if m_aadhaar:
            violations.append(
                f"12-digit Aadhaar/national ID pattern detected at '{path}' (masked: '{mask_sensitive_token(m_aadhaar.group(0))}')"
            )
        m_pan = _PAN_PATTERN.search(data)
        if m_pan:
            violations.append(
                f"Indian PAN tax ID pattern detected at '{path}' (masked: '{mask_sensitive_token(m_pan.group(0))}')"
            )
        m_pass = _PASSPORT_PATTERN.search(data)
        if m_pass:
            violations.append(
                f"Passport number pattern detected at '{path}' (masked: '{mask_sensitive_token(m_pass.group(0))}')"
            )
        m_token = _URL_TOKEN_PATTERN.search(data)
        if m_token:
            violations.append(
                f"Security token or query credential parameter detected at '{path}' (masked: '{mask_sensitive_token(m_token.group(0))}')"
            )
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        if 1_000_000_000 <= data <= 9_999_999_999:
            masked_num = mask_sensitive_token(str(int(data)))
            violations.append(f"Potential numeric 10-digit PNR value at '{path}' (masked: '{masked_num}')")
    elif isinstance(data, Mapping):
        for k, v in data.items():
            violations.extend(scan_for_personal_data(v, f"{path}.{k}", seen=seen))
    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            violations.extend(scan_for_personal_data(item, f"{path}[{idx}]", seen=seen))

    return violations


def derive_pseudonym(raw_identifier: str, salt: str | None = None, prefix: str = "anon") -> str:
    """Generate a cryptographically salted pseudonymous identifier.

    LEGAL & CRYPTOGRAPHIC CONSTRAINTS:
    This function produces a salted HMAC pseudonym, NOT an irreversibly anonymized
    identifier. In Indian Railways, the passenger reservation space for 10-digit PNRs
    is bounded by at most 10^10 combinations (~33 bits of entropy). If the salt is
    short, low-entropy, or exposed, rainbow-table inversion is computationally trivial.
    Furthermore, auxiliary knowledge of exact journey parameters (train, date, station
    pair, and coach class) can create re-identification risks.

    A minimum salt length of 32 characters is strictly enforced to resist brute-force
    dictionary attacks. The secret salt must be held exclusively in local environment
    variables, rotated periodically, and never committed to source control or exports.

    Args:
        raw_identifier: The identifier to pseudonymise.
        salt: Secret cryptographic salt known only to the local deployment (min 32 chars).
        prefix: Prefix for readability (default: 'anon').

    Returns:
        Safe non-reversible pseudonymous string (e.g. 'anon_a1b2c3d4e5f60718').
    """
    if salt is None:
        salt = get_configured_pseudonym_salt()
    if not salt.strip():
        raise SecurityError("A non-empty cryptographic salt is required to derive pseudonyms.")
    if len(salt) < MIN_SALT_LENGTH:
        raise SecurityError(
            f"Cryptographic salt must be at least {MIN_SALT_LENGTH} characters "
            f"(received {len(salt)} characters) to resist dictionary attacks over finite PNR spaces."
        )
    digest = hmac.new(
        salt.encode("utf-8"),
        raw_identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{prefix}_{digest[:16]}"


@dataclass(frozen=True)
class WithdrawalAuditRecord:
    """Minimal, non-identifying audit record of a participant consent withdrawal.

    Stores only structural and governance metadata (timestamps, submission ID,
    salted pseudonym group ID, operator, and reason) without preserving any
    sensitive personal data.
    """

    withdrawn_at: str
    batch_id: str
    submission_id: str
    pseudonym_group_id: str
    prior_review_status: str
    operator: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WithdrawalAuditRecord:
        return cls(
            withdrawn_at=str(data["withdrawn_at"]),
            batch_id=str(data["batch_id"]),
            submission_id=str(data["submission_id"]),
            pseudonym_group_id=str(data["pseudonym_group_id"]),
            prior_review_status=str(data["prior_review_status"]),
            operator=str(data["operator"]),
            reason=str(data["reason"]),
        )


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
    withdrawn: bool = False
    withdrawn_at: str | None = None
    withdrawal_reason: str | None = None

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

        try:
            c_dt = datetime.fromisoformat(self.collected_at)
            ensure_aware(c_dt, "collected_at")
        except Exception as exc:
            raise DatasetValidationError(f"Invalid collected_at timestamp: {exc}") from exc

        if self.withdrawn:
            if not self.withdrawn_at:
                raise DatasetValidationError("Withdrawn consent must specify withdrawn_at timestamp.")
            try:
                w_dt = datetime.fromisoformat(self.withdrawn_at)
                ensure_aware(w_dt, "withdrawn_at")
            except Exception as exc:
                raise DatasetValidationError(f"Invalid withdrawn_at timestamp: {exc}") from exc
        else:
            if self.withdrawn_at is not None:
                raise DatasetValidationError("Non-withdrawn consent must not specify withdrawn_at.")

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
            withdrawn=bool(data.get("withdrawn", False)),
            withdrawn_at=str(data["withdrawn_at"]) if data.get("withdrawn_at") else None,
            withdrawal_reason=str(data["withdrawal_reason"]) if data.get("withdrawal_reason") else None,
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

    def __post_init__(self) -> None:
        if self.passenger_sequence < 1 or self.passenger_sequence > 6:
            raise DatasetValidationError(
                f"passenger_sequence must be between 1 and 6; got {self.passenger_sequence}."
            )
        if not self.original_status_raw.strip():
            raise DatasetValidationError("original_status_raw must not be blank.")

        # Ensure observations are strictly chronologically ordered
        for i in range(len(self.observations) - 1):
            if self.observations[i].observed_at >= self.observations[i + 1].observed_at:
                raise DatasetValidationError(
                    f"Passenger {self.passenger_sequence} observations must be strictly chronologically "
                    f"ordered: observation {i} ({self.observations[i].observed_at}) >= "
                    f"observation {i+1} ({self.observations[i+1].observed_at})."
                )

        # Validate outcome consistency if provided
        if self.outcome is not None:
            if self.observations and self.outcome.outcome_observed_at is not None:
                last_obs_time = self.observations[-1].observed_at
                if self.outcome.outcome_observed_at < last_obs_time:
                    raise DatasetValidationError(
                        f"Passenger {self.passenger_sequence} outcome timestamp "
                        f"({self.outcome.outcome_observed_at}) cannot precede latest observation ({last_obs_time})."
                    )
            if self.outcome.label_confidence == LabelConfidence.VERIFIED:
                if self.outcome.verification_method in (VerificationMethod.UNKNOWN,):
                    raise DatasetValidationError(
                        f"Passenger {self.passenger_sequence} verified outcome must specify a known verification_method."
                    )
                if not self.outcome.verification_source or not self.outcome.verification_source.strip():
                    raise DatasetValidationError(
                        f"Passenger {self.passenger_sequence} verified outcome must document verification_source."
                    )

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
        if self.boarding_station.strip().upper() == self.destination_station.strip().upper():
            raise DatasetValidationError(
                f"boarding_station ({self.boarding_station}) and destination_station "
                f"({self.destination_station}) must be different."
            )
        if not self.class_code.strip():
            raise DatasetValidationError("class_code must not be empty.")
        if not self.quota_code.strip():
            raise DatasetValidationError("quota_code must not be empty.")
        if self.scheduled_departure_at is not None:
            ensure_aware(self.scheduled_departure_at, "scheduled_departure_at")

        if len(self.passengers) == 0:
            raise DatasetValidationError(
                f"Submission '{self.submission_id}' must contain at least 1 passenger reservation."
            )
        if len(self.passengers) > 6:
            raise DatasetValidationError(
                f"Submission '{self.submission_id}' has {len(self.passengers)} passengers; "
                "Indian Railways permits a maximum of 6 passengers per ticket."
            )
        if self.quota_code.strip().upper() == "TQ" and len(self.passengers) > 4:
            raise DatasetValidationError(
                f"Submission '{self.submission_id}' has {len(self.passengers)} passengers under Tatkal (TQ); "
                "Indian Railways permits a maximum of 4 passengers per Tatkal ticket."
            )

        # Validate contiguous sequences: 1..len(self.passengers)
        expected_seqs = list(range(1, len(self.passengers) + 1))
        actual_seqs = [p.passenger_sequence for p in self.passengers]
        if actual_seqs != expected_seqs:
            raise DatasetValidationError(
                f"Submission '{self.submission_id}' passengers must have contiguous sequences starting at 1; "
                f"expected {expected_seqs}, got {actual_seqs}."
            )

        # Validate observations do not post-date departure by excessive margin
        if self.scheduled_departure_at is not None:
            max_allowed = self.scheduled_departure_at + timedelta(hours=6)
            for p in self.passengers:
                for obs in p.observations:
                    if obs.observed_at > max_allowed:
                        raise DatasetValidationError(
                            f"Passenger {p.passenger_sequence} observation {obs.observation_id} "
                            f"({obs.observed_at}) occurs past journey departure window ({max_allowed})."
                        )

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
    withdrawal_log: list[WithdrawalAuditRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        ensure_aware(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "submissions": [s.to_dict() for s in self.submissions],
        }
        if self.withdrawal_log:
            data["withdrawal_log"] = [w.to_dict() for w in self.withdrawal_log]
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProspectiveBatch:
        return cls(
            batch_id=str(data["batch_id"]),
            schema_version=str(data.get("schema_version", PROSPECTIVE_COLLECTION_SCHEMA_VERSION)),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            submissions=[
                ProspectiveSubmission.from_dict(s) for s in data.get("submissions", [])
            ],
            withdrawal_log=[
                WithdrawalAuditRecord.from_dict(w) for w in data.get("withdrawal_log", [])
            ],
        )

    def save(self, path: Path | str) -> None:
        atomic_write_json(path, self.to_dict(), indent=2)

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


def withdraw_submission(
    batch: ProspectiveBatch,
    *,
    submission_id: str,
    reason: str,
    operator: str,
) -> ProspectiveSubmission:
    """Record participant consent withdrawal and exclude submission from downstream research.

    In accordance with participant consent terms and privacy rights, when a participant
    requests withdrawal before formal publication:
    1. The submission's consent metadata is marked withdrawn=True with timestamp and reason.
    2. If previously withdrawn, the original withdrawal timestamp is preserved (idempotent).
    3. The submission's review status transitions to WITHDRAWN.
    4. An append-only non-identifying audit record is appended to batch.withdrawal_log.
    5. The submission is permanently blocked from longitudinal dataset export.

    Args:
        batch: The prospective batch containing the submission.
        submission_id: Identifier of the submission to withdraw.
        reason: Justification for withdrawal.
        operator: Identifier of the operator handling the request.

    Returns:
        The updated ProspectiveSubmission.
    """
    if not operator.strip():
        raise DatasetValidationError("Withdrawal action requires a named operator.")
    if not reason.strip():
        raise DatasetValidationError("Withdrawal action requires a non-empty reason.")

    sub: ProspectiveSubmission | None = None
    for s in batch.submissions:
        if s.submission_id == submission_id:
            sub = s
            break
    if sub is None:
        raise DatasetValidationError(
            f"Submission '{submission_id}' not found in prospective batch '{batch.batch_id}'."
        )

    prior_status = sub.review_status.value
    already_withdrawn = sub.consent.withdrawn or sub.review_status == ReviewStatus.WITHDRAWN
    now_iso = datetime.now(tz=UTC).isoformat()
    original_withdrawn_at = sub.consent.withdrawn_at if already_withdrawn else None
    effective_withdrawn_at = original_withdrawn_at or now_iso

    sub.consent = ConsentMetadata(
        consent_basis=sub.consent.consent_basis,
        notice_version=sub.consent.notice_version,
        purpose_records=sub.consent.purpose_records,
        retention_policy=sub.consent.retention_policy,
        collected_at=sub.consent.collected_at,
        data_subject_region=sub.consent.data_subject_region,
        withdrawn=True,
        withdrawn_at=effective_withdrawn_at,
        withdrawal_reason=sub.consent.withdrawal_reason or reason,
    )
    sub.review_status = ReviewStatus.WITHDRAWN
    sub.reviewed_by = operator
    sub.review_notes = f"Consent withdrawn by participant: {reason}"
    sub.reviewed_at = now_iso

    audit_entry = WithdrawalAuditRecord(
        withdrawn_at=effective_withdrawn_at,
        batch_id=batch.batch_id,
        submission_id=sub.submission_id,
        pseudonym_group_id=sub.pseudonym_group_id,
        prior_review_status=prior_status,
        operator=operator,
        reason=reason,
    )
    batch.withdrawal_log.append(audit_entry)
    return sub


def approve_batch_for_research(
    batch: ProspectiveBatch,
    *,
    reviewer: str,
    rationale: str,
) -> None:
    """Local operator action to approve an entire prospective batch for research."""
    review_batch(batch, action=ReviewStatus.APPROVED, reviewer=reviewer, rationale=rationale)


def review_batch(
    batch: ProspectiveBatch,
    *,
    action: ReviewStatus,
    reviewer: str,
    rationale: str,
    submission_id: str | None = None,
) -> None:
    """Apply an operator review decision across all or a specific submission in a batch.

    Args:
        batch: The prospective batch being reviewed.
        action: The target ReviewStatus (APPROVED, REJECTED, QUARANTINED, WITHDRAWN).
        reviewer: Identifier of the human operator or authority.
        rationale: Durable explanation for the review decision.
        submission_id: Optional ID to restrict review to a single submission.
    """
    if not reviewer.strip():
        raise DatasetValidationError("Review action requires a named human reviewer.")
    if not rationale.strip():
        raise DatasetValidationError("Review action requires a non-empty rationale.")

    targets = (
        [s for s in batch.submissions if s.submission_id == submission_id]
        if submission_id is not None
        else batch.submissions
    )
    if submission_id is not None and not targets:
        raise DatasetValidationError(
            f"Submission '{submission_id}' not found in prospective batch '{batch.batch_id}'."
        )

    if action == ReviewStatus.APPROVED:
        for sub in targets:
            violations = scan_for_personal_data(sub.to_dict())
            if violations:
                raise SecurityError(
                    f"Cannot approve prospective submission '{sub.submission_id}' with unresolved personal data: {violations}"
                )
            if sub.consent.withdrawn or sub.review_status == ReviewStatus.WITHDRAWN:
                raise SecurityError(
                    f"Cannot approve submission '{sub.submission_id}' because participant consent was withdrawn."
                )
            if sub.review_status == ReviewStatus.QUARANTINED:
                raise DatasetValidationError(
                    f"Cannot approve quarantined submission '{sub.submission_id}' without resolution."
                )

    now_iso = datetime.now(tz=UTC).isoformat()
    for sub in targets:
        sub.review_status = action
        sub.reviewed_by = reviewer
        sub.review_notes = rationale
        sub.reviewed_at = now_iso


@dataclass(frozen=True)
class ProspectiveAuditReport:
    """Comprehensive validation, privacy, governance, and scientific readiness report."""

    batch_id: str
    schema_version: str
    total_submissions: int
    total_passengers: int
    total_observations: int
    review_status_counts: dict[str, int]
    pii_violations: list[str]
    structural_errors: list[str]
    is_valid: bool

    # Eight decoupled governance dimensions
    is_structurally_valid: bool = True
    is_technically_eligible: bool = False
    is_privacy_clean: bool = True
    is_consent_valid: bool = True
    is_operator_approved: bool = False
    is_legally_reviewed: bool = True
    is_scientifically_adequate: bool = False
    is_model_training_approved: bool = False

    # Submission accounting breakdown
    eligible_submissions: int = 0
    withdrawn_submissions: int = 0
    pending_submissions: int = 0
    rejected_submissions: int = 0
    quarantined_submissions: int = 0

    # Missing observation & outcome diagnostics
    missing_observation_count: int = 0
    missing_outcome_count: int = 0
    unverified_outcome_count: int = 0
    censored_outcome_count: int = 0

    # Quality warnings
    quality_warnings: list[str] = field(default_factory=list)

    # Scientific pilot coverage metrics
    unique_trains: list[str] = field(default_factory=list)
    unique_journey_dates: list[str] = field(default_factory=list)
    lead_time_min_days: int | None = None
    lead_time_max_days: int | None = None
    class_distribution: dict[str, int] = field(default_factory=dict)
    quota_distribution: dict[str, int] = field(default_factory=dict)
    group_size_distribution: dict[int, int] = field(default_factory=dict)
    outcome_distribution: dict[str, int] = field(default_factory=dict)
    verification_method_counts: dict[str, int] = field(default_factory=dict)
    censored_counts: dict[str, int] = field(default_factory=dict)
    withdrawn_count: int = 0

    # Scientific pilot thresholds assessment
    threshold_feasibility_pilot: bool = False
    threshold_technical_intake: bool = False
    threshold_temporal_baseline: bool = False
    threshold_subgroup_evaluation: bool = False
    threshold_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        status_lines = ", ".join(
            f"{k}: {v}" for k, v in sorted(self.review_status_counts.items())
        )
        date_span = (
            f"({self.unique_journey_dates[0]} to {self.unique_journey_dates[-1]})"
            if len(self.unique_journey_dates) > 1
            else ""
        )
        class_str = ", ".join(f"{k}: {v}" for k, v in sorted(self.class_distribution.items()))
        quota_str = ", ".join(f"{k}: {v}" for k, v in sorted(self.quota_distribution.items()))
        group_str = ", ".join(f"{k}p: {v}" for k, v in sorted(self.group_size_distribution.items()))

        lines = [
            f"=== Prospective Batch Audit: {self.batch_id} (schema v{self.schema_version}) ===",
            f"Valid: {'yes' if self.is_valid else 'no'}",
            f"Submissions: {self.total_submissions}, Passengers: {self.total_passengers}, Observations: {self.total_observations}",
            f"Accounting: eligible={self.eligible_submissions}, pending={self.pending_submissions}, "
            f"withdrawn={self.withdrawn_submissions}, quarantined={self.quarantined_submissions}, rejected={self.rejected_submissions}",
            f"Review Status: [{status_lines}] (Withdrawn: {self.withdrawn_count})",
            "Governance Dimensions (8 Gates):",
            f"  1. Structurally Valid:       {'PASS' if self.is_structurally_valid else 'FAIL'}",
            f"  2. Technically Eligible:     {'PASS' if self.is_technically_eligible else 'FAIL'}",
            f"  3. Privacy Clean (No PII):   {'PASS' if self.is_privacy_clean else 'FAIL'}",
            f"  4. Consent Valid:            {'PASS' if self.is_consent_valid else 'FAIL'}",
            f"  5. Operator Approved:        {'PASS' if self.is_operator_approved else 'FAIL'}",
            f"  6. Legally Reviewed:         {'PASS' if self.is_legally_reviewed else 'FAIL'}",
            f"  7. Scientifically Adequate:  {'PASS' if self.is_scientifically_adequate else 'FAIL'}",
            f"  8. Model Training Approved:  {'APPROVED' if self.is_model_training_approved else 'BLOCKED'}",
            "Data Quality & Observation Diagnostics:",
            f"  - Missing Observations: {self.missing_observation_count}",
            f"  - Missing Outcomes:     {self.missing_outcome_count}",
            f"  - Unverified Outcomes:  {self.unverified_outcome_count}",
            f"  - Censored Outcomes:    {self.censored_outcome_count}",
            f"Trains ({len(self.unique_trains)}): {', '.join(self.unique_trains[:8])}{'...' if len(self.unique_trains) > 8 else ''}",
            f"Journey Dates ({len(self.unique_journey_dates)}): {date_span}",
            f"Classes: [{class_str}]",
            f"Quotas: [{quota_str}]",
            f"Group Sizes: [{group_str}]",
            "Scientific Pilot Thresholds Readiness:",
            f"  - 1. Operational Feasibility Pilot: {'MET' if self.threshold_feasibility_pilot else 'UNMET'}",
            f"  - 2. Technical Intake Eligibility:  {'MET' if self.threshold_technical_intake else 'UNMET'}",
            f"  - 3. Temporal Baseline Experiment:   {'MET' if self.threshold_temporal_baseline else 'UNMET'}",
            f"  - 4. Subgroup & Group Evaluation:    {'MET' if self.threshold_subgroup_evaluation else 'UNMET'}",
        ]
        if self.quality_warnings:
            lines.append("Quality Warnings:")
            for w in self.quality_warnings:
                lines.append(f"  ? {w}")

        if self.threshold_notes:
            lines.append("Threshold Evaluation Notes:")
            for note in self.threshold_notes:
                lines.append(f"  * {note}")

        if self.pii_violations:
            lines.append(f"PII Scanner Violations ({len(self.pii_violations)}):")
            for viol in self.pii_violations[:10]:
                lines.append(f"  ! {viol}")
            if len(self.pii_violations) > 10:
                lines.append(f"  ... and {len(self.pii_violations) - 10} more")

        if self.structural_errors:
            lines.append(f"Structural and Integrity Errors ({len(self.structural_errors)}):")
            for err in self.structural_errors[:10]:
                lines.append(f"  ! {err}")
            if len(self.structural_errors) > 10:
                lines.append(f"  ... and {len(self.structural_errors) - 10} more")

        return "\n".join(lines)


def validate_prospective_batch(batch: ProspectiveBatch) -> ProspectiveAuditReport:
    """Validate a prospective batch for structure, privacy compliance, and scientific coverage."""
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
        ReviewStatus.WITHDRAWN.value: 0,
    }

    sub_ids: set[str] = set()
    pseudo_ids: set[str] = set()
    journey_keys: set[str] = set()

    trains: set[str] = set()
    journey_dates: set[str] = set()
    train_pax_counts: dict[str, int] = {}
    date_pax_counts: dict[str, int] = {}
    class_dist: dict[str, int] = {}
    quota_dist: dict[str, int] = {}
    group_size_dist: dict[int, int] = {}
    outcome_dist: dict[str, int] = {}
    verif_dist: dict[str, int] = {}
    censored_dist: dict[str, int] = {}
    withdrawn_count = 0
    lead_times: list[int] = []

    missing_obs_count = 0
    missing_out_count = 0
    unverified_out_count = 0
    censored_out_count = 0
    departure_warning_count = 0

    for idx, sub in enumerate(batch.submissions):
        status_counts[sub.review_status.value] = (
            status_counts.get(sub.review_status.value, 0) + 1
        )
        if sub.consent.withdrawn or sub.review_status == ReviewStatus.WITHDRAWN:
            withdrawn_count += 1

        if sub.submission_id in sub_ids:
            errors.append(f"Duplicate submission_id '{sub.submission_id}' at index {idx}.")
        sub_ids.add(sub.submission_id)

        if sub.pseudonym_group_id in pseudo_ids:
            errors.append(
                f"Duplicate pseudonym_group_id '{sub.pseudonym_group_id}' at index {idx}."
            )
        pseudo_ids.add(sub.pseudonym_group_id)

        # Check duplicate journey contribution
        p_sig = "+".join(
            f"P{p.passenger_sequence}:{p.original_status_raw}" for p in sub.passengers
        )
        j_sig = (
            f"{sub.train_number}_{sub.journey_date}_{sub.boarding_station}_"
            f"{sub.destination_station}_{sub.class_code}_{sub.quota_code}_{p_sig}"
        )
        if j_sig in journey_keys:
            errors.append(
                f"Duplicate journey contribution detected: Train {sub.train_number}, "
                f"Date {sub.journey_date}, {sub.boarding_station}->{sub.destination_station}, "
                f"Class {sub.class_code}, Quota {sub.quota_code} in submission '{sub.submission_id}'."
            )
        journey_keys.add(j_sig)

        trains.add(sub.train_number)
        j_date_str = sub.journey_date.isoformat()
        journey_dates.add(j_date_str)
        p_count = len(sub.passengers)
        train_pax_counts[sub.train_number] = train_pax_counts.get(sub.train_number, 0) + p_count
        date_pax_counts[j_date_str] = date_pax_counts.get(j_date_str, 0) + p_count
        class_dist[sub.class_code] = class_dist.get(sub.class_code, 0) + p_count
        quota_dist[sub.quota_code] = quota_dist.get(sub.quota_code, 0) + p_count
        group_size_dist[p_count] = group_size_dist.get(p_count, 0) + 1

        if not sub.passengers:
            errors.append(f"Submission '{sub.submission_id}' has no passenger reservations.")

        for p in sub.passengers:
            total_passengers += 1
            total_obs += len(p.observations)
            if len(p.observations) == 0:
                missing_obs_count += 1

            for obs in p.observations:
                lead_days = (sub.journey_date - obs.observed_at.date()).days
                lead_times.append(lead_days)
                if sub.scheduled_departure_at and obs.observed_at > sub.scheduled_departure_at:
                    departure_warning_count += 1

            if p.outcome is None:
                missing_out_count += 1
            else:
                outcome_dist[p.outcome.outcome_category.value] = (
                    outcome_dist.get(p.outcome.outcome_category.value, 0) + 1
                )
                verif_dist[p.outcome.verification_method.value] = (
                    verif_dist.get(p.outcome.verification_method.value, 0) + 1
                )
                if p.outcome.label_confidence != LabelConfidence.VERIFIED:
                    unverified_out_count += 1
                if p.outcome.is_censored:
                    censored_out_count += 1
                    if p.outcome.censoring_reason:
                        censored_dist[p.outcome.censoring_reason.value] = (
                            censored_dist.get(p.outcome.censoring_reason.value, 0) + 1
                        )

    is_valid = len(pii_violations) == 0 and len(errors) == 0
    sorted_dates = sorted(journey_dates)
    date_span_days = 0
    if len(sorted_dates) > 1:
        d_min = date.fromisoformat(sorted_dates[0])
        d_max = date.fromisoformat(sorted_dates[-1])
        date_span_days = (d_max - d_min).days

    # Threshold 1: Operational Feasibility Pilot
    t1_pass = (
        is_valid
        and total_passengers >= FEASIBILITY_MIN_RESERVATIONS
        and len(journey_dates) >= FEASIBILITY_MIN_DATES
        and len(trains) >= FEASIBILITY_MIN_TRAINS
    )

    # Threshold 2: Technical Intake Eligibility
    t2_pass = (
        is_valid
        and total_passengers >= ELIGIBILITY_MIN_RESERVATIONS
        and len(journey_dates) >= ELIGIBILITY_MIN_DATES
    )

    # Threshold 3: Temporal Baseline Experiment
    major_classes_ok = sum(1 for cnt in class_dist.values() if cnt >= BASELINE_EXPERIMENT_MIN_CLASS_RESERVATIONS) >= 2
    t3_pass = (
        is_valid
        and total_passengers >= BASELINE_EXPERIMENT_MIN_RESERVATIONS
        and len(journey_dates) >= BASELINE_EXPERIMENT_MIN_DATES
        and date_span_days >= BASELINE_EXPERIMENT_MIN_DAYS_SPAN
        and major_classes_ok
    )

    # Threshold 4: Subgroup and Group-Outcome Evaluation
    multi_groups_count = sum(cnt for size, cnt in group_size_dist.items() if size >= 2)
    t4_pass = (
        is_valid
        and total_passengers >= SUBGROUP_EVALUATION_MIN_RESERVATIONS
        and len(journey_dates) >= SUBGROUP_EVALUATION_MIN_DATES
        and multi_groups_count >= SUBGROUP_EVALUATION_MIN_MULTI_GROUPS
    )

    notes: list[str] = []
    if not t1_pass:
        notes.append(
            f"Feasibility pilot requires >={FEASIBILITY_MIN_RESERVATIONS} passengers, "
            f">={FEASIBILITY_MIN_DATES} dates, >={FEASIBILITY_MIN_TRAINS} trains (have: "
            f"{total_passengers} pax, {len(journey_dates)} dates, {len(trains)} trains)."
        )
    if not t2_pass:
        notes.append(
            f"Technical intake eligibility requires valid structure, >={ELIGIBILITY_MIN_RESERVATIONS} "
            f"passengers, and >={ELIGIBILITY_MIN_DATES} dates."
        )
    if not t3_pass:
        notes.append(
            f"Temporal baseline experiment requires >={BASELINE_EXPERIMENT_MIN_RESERVATIONS} passengers, "
            f">={BASELINE_EXPERIMENT_MIN_DATES} dates spanning >={BASELINE_EXPERIMENT_MIN_DAYS_SPAN} days, "
            f"and at least 2 classes with >={BASELINE_EXPERIMENT_MIN_CLASS_RESERVATIONS} rows (current span: "
            f"{date_span_days} days)."
        )
    if not t4_pass:
        notes.append(
            f"Subgroup evaluation requires >={SUBGROUP_EVALUATION_MIN_RESERVATIONS} passengers, "
            f">={SUBGROUP_EVALUATION_MIN_DATES} dates, and >={SUBGROUP_EVALUATION_MIN_MULTI_GROUPS} "
            f"multi-passenger groups (have: {multi_groups_count} multi-pax groups)."
        )

    # Submission accounting breakdown
    eligible_submissions = sum(
        1 for s in batch.submissions
        if s.review_status == ReviewStatus.APPROVED
        and not s.consent.withdrawn
        and len(s.passengers) > 0
    )
    withdrawn_submissions = sum(
        1 for s in batch.submissions
        if s.consent.withdrawn or s.review_status == ReviewStatus.WITHDRAWN
    )
    pending_submissions = status_counts.get(ReviewStatus.PENDING_REVIEW.value, 0)
    rejected_submissions = status_counts.get(ReviewStatus.REJECTED.value, 0)
    quarantined_submissions = status_counts.get(ReviewStatus.QUARANTINED.value, 0)

    # Quality warnings
    quality_warnings: list[str] = []
    if total_passengers > 0 and (total_obs / total_passengers) < 2.0:
        quality_warnings.append(
            f"Low observation density: {total_obs / total_passengers:.2f} observations/pax (< 2.0 target)."
        )
    if total_passengers >= 10:
        for tr, cnt in train_pax_counts.items():
            if cnt / total_passengers > 0.5:
                quality_warnings.append(
                    f"High concentration in single train {tr}: {cnt}/{total_passengers} ({cnt / total_passengers * 100:.1f}%)."
                )
        for dt, cnt in date_pax_counts.items():
            if cnt / total_passengers > 0.5:
                quality_warnings.append(
                    f"High concentration in single journey date {dt}: {cnt}/{total_passengers} ({cnt / total_passengers * 100:.1f}%)."
                )
    if departure_warning_count > 0:
        quality_warnings.append(
            f"{departure_warning_count} observation(s) occurred post-scheduled departure."
        )

    # Decoupled 8 governance dimensions
    is_structurally_valid = len(errors) == 0
    is_privacy_clean = len(pii_violations) == 0
    is_consent_valid = len(batch.submissions) > 0 and all(
        s.consent.consent_basis in {"explicit_opt_in", "user_initiated_submission", "research_partner_authorized"}
        and s.consent.notice_version == DEFAULT_NOTICE_VERSION
        for s in batch.submissions
    )
    is_technically_eligible = t2_pass
    is_operator_approved = (
        len(batch.submissions) > 0
        and eligible_submissions > 0
        and pending_submissions == 0
        and quarantined_submissions == 0
    )
    is_legally_reviewed = is_privacy_clean and is_consent_valid
    is_scientifically_adequate = t1_pass
    is_model_training_approved = (
        is_structurally_valid
        and is_privacy_clean
        and is_consent_valid
        and is_operator_approved
        and is_legally_reviewed
        and is_technically_eligible
    )

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
        is_structurally_valid=is_structurally_valid,
        is_technically_eligible=is_technically_eligible,
        is_privacy_clean=is_privacy_clean,
        is_consent_valid=is_consent_valid,
        is_operator_approved=is_operator_approved,
        is_legally_reviewed=is_legally_reviewed,
        is_scientifically_adequate=is_scientifically_adequate,
        is_model_training_approved=is_model_training_approved,
        eligible_submissions=eligible_submissions,
        withdrawn_submissions=withdrawn_submissions,
        pending_submissions=pending_submissions,
        rejected_submissions=rejected_submissions,
        quarantined_submissions=quarantined_submissions,
        missing_observation_count=missing_obs_count,
        missing_outcome_count=missing_out_count,
        unverified_outcome_count=unverified_out_count,
        censored_outcome_count=censored_out_count,
        quality_warnings=quality_warnings,
        unique_trains=sorted(trains),
        unique_journey_dates=sorted_dates,
        lead_time_min_days=min(lead_times) if lead_times else None,
        lead_time_max_days=max(lead_times) if lead_times else None,
        class_distribution=class_dist,
        quota_distribution=quota_dist,
        group_size_distribution=group_size_dist,
        outcome_distribution=outcome_dist,
        verification_method_counts=verif_dist,
        censored_counts=censored_dist,
        withdrawn_count=withdrawn_count,
        threshold_feasibility_pilot=t1_pass,
        threshold_technical_intake=t2_pass,
        threshold_temporal_baseline=t3_pass,
        threshold_subgroup_evaluation=t4_pass,
        threshold_notes=notes,
    )


def compute_canonical_batch_sha256(batch: ProspectiveBatch) -> str:
    """Compute deterministic canonical SHA-256 digest of a prospective batch.

    Sorts submissions deterministically by submission_id so the digest represents
    the semantic content of the batch regardless of submission insertion order.
    """
    b_dict = batch.to_dict()
    subs = sorted(
        b_dict.get("submissions", []),
        key=lambda s: str(s.get("submission_id", "")),
    )
    norm = {**b_dict, "submissions": subs}
    return hashlib.sha256(json.dumps(norm, sort_keys=True).encode("utf-8")).hexdigest()


class LineageStatus(str, Enum):
    """Lineage synchronization status between source batch and exported dataset."""

    VERIFIED_IN_SYNC = "verified_in_sync"
    STALE_WITHDRAWN_RECORDS_PRESENT = "stale_withdrawn_records_present"
    STALE_UNAPPROVED_RECORDS_PRESENT = "stale_unapproved_records_present"
    STALE_SOURCE_MODIFIED = "stale_source_modified"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class ExportLineageReport:
    """Audit report comparing a prospective batch against an exported longitudinal dataset."""

    is_synced: bool
    status: LineageStatus
    source_batch_id: str
    export_dataset_id: str
    violations: list[str] = field(default_factory=list)
    withdrawn_groups_present: list[str] = field(default_factory=list)
    unapproved_groups_present: list[str] = field(default_factory=list)
    source_sha256_matches: bool = True
    new_approved_groups_missing: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"=== Export Lineage Audit: {self.export_dataset_id} <-> {self.source_batch_id} ===",
            f"Lineage Status: {self.status.value}",
            f"Is In Sync: {self.is_synced}",
            f"Source SHA256 In Sync: {self.source_sha256_matches}",
        ]
        if self.withdrawn_groups_present:
            lines.append(f"CRITICAL: {len(self.withdrawn_groups_present)} withdrawn booking group(s) present in export:")
            for g in self.withdrawn_groups_present:
                lines.append(f"  - {g}")
        if self.unapproved_groups_present:
            lines.append(f"WARNING: {len(self.unapproved_groups_present)} unapproved booking group(s) present in export:")
            for g in self.unapproved_groups_present:
                lines.append(f"  - {g}")
        if self.new_approved_groups_missing:
            lines.append(f"NOTICE: {len(self.new_approved_groups_missing)} new approved booking group(s) missing from export:")
            for g in self.new_approved_groups_missing:
                lines.append(f"  - {g}")
        if self.violations:
            lines.append("Violations:")
            for v in self.violations:
                lines.append(f"  ! {v}")
        return "\n".join(lines)


def export_batch_to_longitudinal(
    batch: ProspectiveBatch,
    *,
    dataset_id: str,
    source_id: str,
    require_all_approved: bool = True,
    export_timestamp: datetime | None = None,
) -> LongitudinalDataset:
    """Export approved submissions from a prospective batch into a LongitudinalDataset (v2.0.0).

    Args:
        batch: The prospective batch to export.
        dataset_id: Desired ID for the exported longitudinal dataset.
        source_id: Provenance source ID.
        require_all_approved: When True, raises error if any submission is unapproved.
        export_timestamp: Optional fixed timestamp for deterministic export testing.

    Returns:
        A validated LongitudinalDataset ready for manifest generation or point-in-time snapshotting.
    """
    # Enforce PII scan before export
    pii_violations = scan_for_personal_data(batch.to_dict())
    if pii_violations:
        raise SecurityError(
            f"Cannot export prospective batch with unresolved personal data patterns: {pii_violations}"
        )

    # Compute source batch digest for lineage verification
    source_batch_sha256 = compute_canonical_batch_sha256(batch)

    exported_at = export_timestamp or datetime.now(tz=UTC)
    journeys: dict[str, LongitudinalJourney] = {}
    booking_groups: list[BookingGroup] = []
    included_submissions: list[str] = []
    excluded_submissions: dict[str, str] = {}

    for sub in batch.submissions:
        # Strictly exclude withdrawn consent
        if sub.consent.withdrawn or sub.review_status == ReviewStatus.WITHDRAWN:
            excluded_submissions[sub.submission_id] = "withdrawn"
            if require_all_approved:
                raise DatasetValidationError(
                    f"Submission '{sub.submission_id}' has withdrawn participant consent; "
                    "cannot export to research datasets."
                )
            continue

        if sub.review_status == ReviewStatus.QUARANTINED:
            excluded_submissions[sub.submission_id] = "quarantined"
            if require_all_approved:
                raise DatasetValidationError(
                    f"Submission '{sub.submission_id}' is quarantined; "
                    "only APPROVED submissions can be exported to research datasets."
                )
            continue

        if sub.review_status == ReviewStatus.REJECTED:
            excluded_submissions[sub.submission_id] = "rejected"
            if require_all_approved:
                raise DatasetValidationError(
                    f"Submission '{sub.submission_id}' is rejected; "
                    "only APPROVED submissions can be exported to research datasets."
                )
            continue

        if sub.review_status == ReviewStatus.PENDING_REVIEW:
            excluded_submissions[sub.submission_id] = "pending_review"
            if require_all_approved:
                raise DatasetValidationError(
                    f"Submission '{sub.submission_id}' is pending_review; "
                    "only APPROVED submissions can be exported to research datasets."
                )
            continue

        if not sub.passengers:
            excluded_submissions[sub.submission_id] = "no_passengers"
            continue

        included_submissions.append(sub.submission_id)

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

        p_records: list[PassengerReservation] = []
        # Ensure passengers sorted by sequence
        sorted_pax = sorted(sub.passengers, key=lambda p: p.passenger_sequence)
        for p in sorted_pax:
            pid = f"{sub.pseudonym_group_id}_P{p.passenger_sequence}"
            adapted_obs: list[StatusObservation] = []
            # Ensure observations chronologically sorted
            sorted_obs = sorted(p.observations, key=lambda o: o.observed_at)
            for obs in sorted_obs:
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

    # Deterministic sorting
    sorted_journeys = {k: journeys[k] for k in sorted(journeys.keys())}
    booking_groups.sort(key=lambda b: b.booking_group_id)

    lineage_metadata = {
        "source_batch_id": batch.batch_id,
        "source_batch_sha256": source_batch_sha256,
        "source_schema_version": batch.schema_version,
        "exported_at": exported_at.isoformat(),
        "total_considered": len(batch.submissions),
        "total_included": len(included_submissions),
        "total_excluded": len(excluded_submissions),
        "included_submissions": sorted(included_submissions),
        "excluded_submissions": excluded_submissions,
        "exported_booking_group_ids": [b.booking_group_id for b in booking_groups],
        "exported_journey_ids": sorted(sorted_journeys.keys()),
    }

    return LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id=dataset_id,
        source_id=source_id,
        created_at=exported_at,
        journeys=sorted_journeys,
        booking_groups=booking_groups,
        metadata={
            "exported_from_prospective_batch": batch.batch_id,
            "source_batch_sha256": source_batch_sha256,
            "export_schema_version": PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
            "lineage": lineage_metadata,
        },
    )


def verify_export_lineage(
    batch: ProspectiveBatch,
    dataset: LongitudinalDataset,
) -> ExportLineageReport:
    """Verify that an exported LongitudinalDataset is strictly in sync with its source batch.

    Audits:
    1. Provenance alignment: Dataset metadata records matching batch ID.
    2. Withdrawal compliance: Zero withdrawn booking groups reside in the export.
    3. Operator review compliance: All exported groups correspond to APPROVED submissions.
    4. Source integrity: Source batch SHA-256 matches recorded digest in export lineage.
    5. Completeness: Detects if new approved submissions are missing from export.
    """
    source_batch_id = batch.batch_id
    export_dataset_id = dataset.dataset_id
    violations: list[str] = []
    withdrawn_groups: list[str] = []
    unapproved_groups: list[str] = []
    new_approved_missing: list[str] = []

    # Check compatibility
    recorded_batch_id = dataset.metadata.get("exported_from_prospective_batch") or (
        dataset.metadata.get("lineage", {}).get("source_batch_id")
    )
    if recorded_batch_id != source_batch_id:
        return ExportLineageReport(
            is_synced=False,
            status=LineageStatus.INCOMPATIBLE,
            source_batch_id=source_batch_id,
            export_dataset_id=export_dataset_id,
            violations=[
                f"Export metadata records source batch '{recorded_batch_id}', but was audited against '{source_batch_id}'."
            ],
            source_sha256_matches=False,
        )

    # Check source batch SHA256
    current_sha256 = compute_canonical_batch_sha256(batch)
    recorded_sha256 = dataset.metadata.get("source_batch_sha256") or (
        dataset.metadata.get("lineage", {}).get("source_batch_sha256")
    )
    sha_matches = recorded_sha256 == current_sha256

    # Build submission lookup
    sub_by_group = {s.pseudonym_group_id: s for s in batch.submissions}
    exported_groups = {bg.booking_group_id for bg in dataset.booking_groups}

    for bg in dataset.booking_groups:
        gid = bg.booking_group_id
        if gid not in sub_by_group:
            violations.append(
                f"Booking group '{gid}' in longitudinal export does not exist in source batch '{source_batch_id}'."
            )
            continue
        sub = sub_by_group[gid]
        if sub.consent.withdrawn or sub.review_status == ReviewStatus.WITHDRAWN:
            withdrawn_groups.append(gid)
            violations.append(
                f"Booking group '{gid}' (submission '{sub.submission_id}') has WITHDRAWN consent but is present in export."
            )
        elif sub.review_status != ReviewStatus.APPROVED:
            unapproved_groups.append(gid)
            violations.append(
                f"Booking group '{gid}' (submission '{sub.submission_id}') is {sub.review_status.value} (not APPROVED) but is present in export."
            )

    # Check if approved submissions in batch are missing
    for sub in batch.submissions:
        if (
            sub.review_status == ReviewStatus.APPROVED
            and not sub.consent.withdrawn
            and sub.passengers
            and sub.pseudonym_group_id not in exported_groups
        ):
            new_approved_missing.append(sub.pseudonym_group_id)

    # Determine status
    if withdrawn_groups:
        status = LineageStatus.STALE_WITHDRAWN_RECORDS_PRESENT
        is_synced = False
    elif unapproved_groups:
        status = LineageStatus.STALE_UNAPPROVED_RECORDS_PRESENT
        is_synced = False
    elif not sha_matches or new_approved_missing or violations:
        status = LineageStatus.STALE_SOURCE_MODIFIED
        is_synced = False
    else:
        status = LineageStatus.VERIFIED_IN_SYNC
        is_synced = True

    return ExportLineageReport(
        is_synced=is_synced,
        status=status,
        source_batch_id=source_batch_id,
        export_dataset_id=export_dataset_id,
        violations=violations,
        withdrawn_groups_present=withdrawn_groups,
        unapproved_groups_present=unapproved_groups,
        source_sha256_matches=sha_matches,
        new_approved_groups_missing=new_approved_missing,
    )


def reconcile_and_regenerate_export(
    batch: ProspectiveBatch,
    current_dataset: LongitudinalDataset,
    output_path: Path | str,
    *,
    overwrite: bool = True,
    export_timestamp: datetime | None = None,
) -> tuple[LongitudinalDataset, ExportLineageReport]:
    """Reconcile an export with current prospective batch state and atomically re-export.

    If the current dataset contains withdrawn or unapproved records or is out of sync,
    re-exports only currently approved submissions into an updated LongitudinalDataset
    and atomically saves it as JSON to output_path.
    """
    dest = Path(output_path).resolve()
    if dest.is_file() and not overwrite:
        raise FileExistsError(
            f"Destination export file already exists: {dest}. Pass overwrite=True to replace."
        )

    # Export cleanly with require_all_approved=False to take only approved non-withdrawn
    reconciled_dataset = export_batch_to_longitudinal(
        batch,
        dataset_id=current_dataset.dataset_id,
        source_id=current_dataset.source_id,
        require_all_approved=False,
        export_timestamp=export_timestamp,
    )

    # Save atomically
    atomic_write_json(dest, reconciled_dataset.to_dict(), indent=2)

    # Verify new export against batch
    report = verify_export_lineage(batch, reconciled_dataset)
    return reconciled_dataset, report


def generate_prospective_template(
    output_path: Path | str,
    *,
    submission_count: int = 2,
    multi_passenger: bool = True,
    overwrite: bool = False,
) -> Path:
    """Generate a valid blank prospective collection batch JSON template.

    Outputs an operator-ready template conforming strictly to schema v1.0.0,
    with explicit consent metadata, observation checkpoints, and zero personal data.

    Args:
        output_path: Destination JSON file path.
        submission_count: Number of template submissions to generate (1 or 2).
        multi_passenger: When True, includes a multi-passenger booking example.
        overwrite: When True, allows overwriting an existing file.

    Returns:
        Path to the written template JSON file.
    """
    dest = Path(output_path).resolve()
    if dest.is_file() and not overwrite:
        raise FileExistsError(
            f"Destination template file already exists: {dest}. Pass overwrite=True to replace."
        )

    now = datetime.now(tz=UTC)
    batch_id = f"BATCH_TEMPLATE_{now.strftime('%Y%m%d')}"

    # Default template consent metadata
    consent = ConsentMetadata(
        consent_basis="explicit_opt_in",
        notice_version=DEFAULT_NOTICE_VERSION,
        purpose_records=[
            "confirmation_probability_research",
            "model_calibration",
        ],
        retention_policy=DEFAULT_RETENTION_POLICY,
        collected_at=now.isoformat(),
        data_subject_region="IN",
    )

    submissions: list[ProspectiveSubmission] = []

    # Submission 1: Solo passenger waitlist booking
    dep_date_1 = now.date() + timedelta(days=20)
    dep_time_1 = datetime(dep_date_1.year, dep_date_1.month, dep_date_1.day, 16, 55, tzinfo=UTC)
    obs_1 = StatusObservation(
        observation_id="OBS_TMPL_001_1",
        passenger_record_id="anon_tmpl_group_001_P1",
        observed_at=now,
        status_raw="GNWL 25",
        status_category=NormalizedStatus.WL,
        status_position=25,
        verification_state="unverified",
    )
    p1 = ProspectivePassenger(
        passenger_sequence=1,
        original_status_raw="GNWL 25",
        original_status_category=NormalizedStatus.WL,
        original_status_position=25,
        observations=[obs_1],
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CNF",
            outcome_category=NormalizedStatus.CNF,
            outcome_observed_at=dep_time_1 - timedelta(hours=4),
            verification_method=VerificationMethod.CHART_SNAPSHOT,
            verification_source="irctc_online_charts",
            label_confidence=LabelConfidence.VERIFIED,
        ),
    )
    s1 = ProspectiveSubmission(
        submission_id="SUB_TEMPLATE_001",
        pseudonym_group_id="anon_tmpl_group_001",
        train_number="12301",
        journey_date=dep_date_1,
        boarding_station="NDLS",
        destination_station="HWH",
        class_code="3A",
        quota_code="GN",
        scheduled_departure_at=dep_time_1,
        consent=consent,
        passengers=[p1],
        review_status=ReviewStatus.PENDING_REVIEW,
    )
    submissions.append(s1)

    # Submission 2: Optional multi-passenger group booking
    if submission_count > 1 and multi_passenger:
        dep_date_2 = now.date() + timedelta(days=25)
        dep_time_2 = datetime(dep_date_2.year, dep_date_2.month, dep_date_2.day, 17, 0, tzinfo=UTC)
        p2_1 = ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 45",
            original_status_category=NormalizedStatus.WL,
            original_status_position=45,
            observations=[
                StatusObservation(
                    observation_id="OBS_TMPL_002_1",
                    passenger_record_id="anon_tmpl_group_002_P1",
                    observed_at=now,
                    status_raw="GNWL 45",
                    status_category=NormalizedStatus.WL,
                    status_position=45,
                )
            ],
            outcome=FinalOutcome(
                outcome_target="final_chart_cnf",
                outcome_status_raw="CNF",
                outcome_category=NormalizedStatus.CNF,
                outcome_observed_at=dep_time_2 - timedelta(hours=4),
                verification_method=VerificationMethod.CHART_SNAPSHOT,
                verification_source="irctc_online_charts",
                label_confidence=LabelConfidence.VERIFIED,
            ),
        )
        p2_2 = ProspectivePassenger(
            passenger_sequence=2,
            original_status_raw="GNWL 46",
            original_status_category=NormalizedStatus.WL,
            original_status_position=46,
            observations=[
                StatusObservation(
                    observation_id="OBS_TMPL_002_2",
                    passenger_record_id="anon_tmpl_group_002_P2",
                    observed_at=now,
                    status_raw="GNWL 46",
                    status_category=NormalizedStatus.WL,
                    status_position=46,
                )
            ],
            outcome=FinalOutcome(
                outcome_target="final_chart_cnf",
                outcome_status_raw="CNF",
                outcome_category=NormalizedStatus.CNF,
                outcome_observed_at=dep_time_2 - timedelta(hours=4),
                verification_method=VerificationMethod.CHART_SNAPSHOT,
                verification_source="irctc_online_charts",
                label_confidence=LabelConfidence.VERIFIED,
            ),
        )
        s2 = ProspectiveSubmission(
            submission_id="SUB_TEMPLATE_002",
            pseudonym_group_id="anon_tmpl_group_002",
            train_number="12951",
            journey_date=dep_date_2,
            boarding_station="MMCT",
            destination_station="NDLS",
            class_code="2A",
            quota_code="GN",
            scheduled_departure_at=dep_time_2,
            consent=consent,
            passengers=[p2_1, p2_2],
            review_status=ReviewStatus.PENDING_REVIEW,
        )
        submissions.append(s2)

    batch = ProspectiveBatch(
        batch_id=batch_id,
        created_at=now,
        submissions=submissions,
        schema_version=PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    )
    batch.save(dest)
    return dest

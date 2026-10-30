"""Pydantic request/response schemas for API v1.

These schemas implement the API contract defined in docs/architecture/API_CONTRACT.md.
All field names and semantics match that contract exactly.

Key rules
---------
* original_status and current_status are preserved separately.
* Passenger names are not accepted.
* Every response includes target_definition, prediction_at, model_version,
  and limitations.
* Probabilities are None (not fabricated) when the engine abstains.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from railconfirm.domain.exceptions import TemporalIntegrityError
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.domain.validation import (
    ensure_aware,
    validate_station_code,
    validate_train_number,
)

# Booking groups larger than this are not supported by the manual flow: the
# independence baseline degrades and the response becomes unreadable, so the
# limit is stated rather than implied by the frontend.
MAX_PASSENGERS_PER_REQUEST = 6

_STATUS_MAX_LENGTH = 120


def _require_aware(value: datetime | None, field_name: str):
    """Translate a domain temporal error into a field-level validation error."""
    try:
        return ensure_aware(value, field_name)
    except TemporalIntegrityError as exc:
        raise ValueError(str(exc)) from exc


# ── Request schemas ────────────────────────────────────────────────────────────


class JourneyRequest(BaseModel):
    """Journey context supplied by the caller."""

    train_number: str = Field(
        ...,
        description="4–6 digit train number string, e.g. '12301'.",
        examples=["12301"],
    )
    journey_date: date = Field(
        ...,
        description="Date of journey departure (YYYY-MM-DD).",
    )
    boarding_station: str = Field(
        ...,
        description="Boarding station code (2–10 uppercase letters or digits).",
        min_length=2,
        max_length=10,
        examples=["NDLS"],
    )
    destination_station: str = Field(
        ...,
        description="Destination station code (2–10 uppercase letters or digits).",
        min_length=2,
        max_length=10,
        examples=["HWH"],
    )
    class_code: str = Field(
        ...,
        description="Travel class code (e.g. '2A', 'SL', '3A').",
        min_length=1,
        max_length=4,
    )
    quota_code: str = Field(
        ...,
        description="Reservation quota code (e.g. 'GN', 'TQ').",
        min_length=1,
        max_length=4,
    )

    @field_validator("train_number")
    @classmethod
    def validate_train_number_field(cls, v: str) -> str:
        return validate_train_number(v)

    @field_validator("boarding_station", "destination_station")
    @classmethod
    def validate_station_field(cls, v: str) -> str:
        return validate_station_code(v, "station code")

    @field_validator("class_code", "quota_code")
    @classmethod
    def uppercase_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def stations_must_differ(self) -> JourneyRequest:
        if self.boarding_station == self.destination_station:
            raise ValueError(
                "boarding_station and destination_station must be different."
            )
        return self


class PassengerRequest(BaseModel):
    """One passenger's status information supplied by the caller."""

    original_status: str = Field(
        ...,
        description=(
            "Status string at time of original booking. "
            "Preserved verbatim alongside current_status."
        ),
        min_length=1,
        max_length=_STATUS_MAX_LENGTH,
    )
    current_status: str = Field(
        ...,
        description=(
            "Most recently observed status string. "
            "May equal original_status if unchanged."
        ),
        min_length=1,
        max_length=_STATUS_MAX_LENGTH,
    )
    current_status_observed_at: datetime | None = Field(
        default=None,
        description=(
            "ISO-8601 timestamp with a UTC offset when current_status was observed. "
            "Null if unknown; a naive timestamp is rejected because it cannot be "
            "compared against the prediction cutoff."
        ),
        examples=["2026-10-21T07:30:00Z"],
    )

    @field_validator("current_status_observed_at")
    @classmethod
    def require_observed_offset(cls, v: datetime | None) -> datetime | None:
        return _require_aware(v, "current_status_observed_at")

    @field_validator("original_status", "current_status")
    @classmethod
    def reject_blank_status(cls, v: str) -> str:
        """Whitespace-only statuses are missing input, not an unknown code.

        Letting them through would produce an UNKNOWN-status abstention that reads
        to the user as "this status is not supported" rather than "you left this
        field empty".
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("status must not be blank.")
        return stripped


class PredictionRequest(BaseModel):
    """Manual prediction request body."""

    journey: JourneyRequest = Field(
        ...,
        description="Journey context for the booking group.",
    )
    prediction_at: datetime = Field(
        ...,
        description=(
            "ISO-8601 timestamp with a UTC offset at which the prediction is made. "
            "Must precede the journey date, and no supplied observation may be newer "
            "than it."
        ),
        examples=["2026-10-21T08:00:00Z"],
    )
    target: PredictionTarget = Field(
        default=PredictionTarget.FINAL_CHART_CNF,
        description=(
            "Outcome being estimated. A final-chart confirmation estimate and a "
            "final-chart confirmation-or-RAC estimate are different questions."
        ),
    )
    passengers: list[PassengerRequest] = Field(
        ...,
        description=(
            f"Passengers in the booking group (1–{MAX_PASSENGERS_PER_REQUEST})."
        ),
        min_length=1,
        max_length=MAX_PASSENGERS_PER_REQUEST,
    )
    persist: bool = Field(
        default=False,
        description=(
            "Ask the server to keep this report so it can be reopened later at "
            "`/v1/predictions/{prediction_id}`. Honoured only when the server has "
            "history enabled; `stored` in the response says whether it happened, and "
            "a refusal appears in `limitations`."
        ),
    )

    @field_validator("prediction_at")
    @classmethod
    def require_prediction_offset(cls, v: datetime) -> datetime:
        return _require_aware(v, "prediction_at")


# ── Response schemas ───────────────────────────────────────────────────────────


class PassengerOutcomeResponse(BaseModel):
    """Per-passenger outcome probabilities in the response."""

    passenger_id: str
    original_status: str
    original_status_normalized: str
    current_status: str
    current_status_normalized: str
    p_cnf: float | None = Field(
        default=None,
        description="Probability of confirmed berth at final chart. Null when abstaining.",
    )
    p_rac: float | None = Field(
        default=None,
        description="Probability of RAC at final chart. Null when abstaining.",
    )
    p_wl: float | None = Field(
        default=None,
        description="Probability of waitlisted at final chart. Null when abstaining.",
    )
    p_cancelled: float | None = Field(
        default=None,
        description="Probability of cancelled outcome. Null when abstaining.",
    )
    p_other: float | None = Field(
        default=None,
        description="Probability of other recognized outcome. Null when abstaining.",
    )
    p_target_event: float | None = Field(
        default=None,
        description=(
            "Probability that this passenger's outcome is covered by the request's "
            "target event: the CNF class for `final_chart_cnf`, the CNF and RAC classes "
            "for `final_chart_cnf_or_rac`. It is the sum of the classes that event "
            "covers, computed from the served distribution rather than re-derived by a "
            "client. Null when abstaining, because an absent estimate is not zero."
        ),
    )
    is_supported: bool = Field(
        description="True if a probability estimate is available; False if abstaining.",
    )
    abstention_reason: str | None = Field(
        default=None,
        description=(
            "Stable reason code if abstaining; null if supported. One of: "
            "unknown_status, unsupported_status, unsupported_class, unsupported_quota, "
            "no_trained_model, no_approved_data, model_artifact_invalid, "
            "insufficient_sample, invalid_input."
        ),
    )
    basis: str | None = Field(
        default=None,
        description=(
            "Evidence cohort that produced the estimate, including its sample "
            "size, or null when abstaining. A broad-cohort fallback is weaker "
            "than an exact cohort match and is labelled as such."
        ),
    )
    parse_warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings from status parsing.",
    )


class GroupOutcomeResponse(BaseModel):
    """Group-level joint event probabilities."""

    p_all_cnf: float | None = None
    p_all_cnf_or_rac: float | None = None
    p_at_least_one_wl: float | None = None
    method: str
    assumptions: str
    is_supported: bool
    abstention_reason: str | None = None
    p_at_least_k_cnf: dict[int, float] | None = None
    p_exactly_k_cnf: dict[int, float] | None = None


class PredictionResponse(BaseModel):
    """Response to a manual prediction request.

    Always present regardless of whether the engine abstains.
    """

    prediction_id: str = Field(description="Unique identifier for this prediction record.")
    target: str = Field(
        description="Prediction target this answer addresses, e.g. 'final_chart_cnf'.",
    )
    target_definition: str = Field(
        description=(
            "What the target asks, in words: the event whose probability "
            "`p_target_event` gives. It names the same event the target's classes do."
        ),
    )
    prediction_at: datetime = Field(
        description="Offset-aware timestamp at which the prediction was made.",
    )
    created_at: datetime = Field(
        description="Server time when this prediction record was created.",
    )
    model_version: str = Field(
        description="Model artifact version used (or 'no_model_v0' when abstaining).",
    )
    registry_status: str = Field(
        description=(
            "Model registry resolution state for this request: no_active_version, "
            "artifact_missing, artifact_invalid, not_promoted, data_not_approved, ready."
        ),
    )
    feature_schema_version: str
    evidence_coverage: str = Field(
        description=(
            "Evidence coverage: 'sufficient' when every passenger has an estimate, "
            "'partial' when some do, 'insufficient' when none do."
        ),
    )
    is_supported: bool = Field(
        default=False,
        description="True if at least one passenger outcome is supported; False if all abstain.",
    )
    passenger_count: int
    passenger_outcomes: list[PassengerOutcomeResponse]
    group_outcome: GroupOutcomeResponse | None = None
    limitations: list[str] = Field(
        description="Known limitations of this prediction.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings from parsing or inference.",
    )
    outcome_classes: str = Field(
        description=(
            "Description of whether probabilities are conditional on a restricted "
            "population or include explicit OTHER/UNKNOWN categories."
        ),
    )
    stored: bool = Field(
        default=False,
        description=(
            "True only when this report was actually written to the server's history. "
            "A request with `persist: true` against a server that keeps no history "
            "returns `stored: false` with the reason in `limitations`."
        ),
    )
    report_url: str | None = Field(
        default=None,
        description="Path to reopen this stored report, e.g. '/v1/predictions/<id>'.",
    )
    retention_expires_at: datetime | None = Field(
        default=None,
        description=(
            "Offset-aware moment after which a stored report stops being retrievable. "
            "None when nothing was stored."
        ),
    )


# ── Prediction history listing ─────────────────────────────────────────────────


class StoredReportSummary(BaseModel):
    """One kept report, described without describing its contents.

    Deliberately narrow: a list endpoint is where ticket detail would leak, so it carries
    the id the user needs to reopen the report and the clocks they need to decide whether
    to keep it, and nothing about the journey or the probabilities.
    """

    prediction_id: str
    target: str
    model_version: str
    recorded_at: datetime
    retention_expires_at: datetime


class StoredReportsResponse(BaseModel):
    """What history currently holds, and for how long."""

    reports: list[StoredReportSummary] = Field(default_factory=list)
    count: int = Field(
        ...,
        description="Number of reports listed. Equal to len(reports), published so a client does not have to trust the array.",
    )
    retention_days: int = Field(
        ...,
        description="This server's retention window; a report stops being retrievable after it.",
    )


# ── Error response ─────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    """Consistent error response shape for all API errors."""

    error: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


# ── Health response ────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """GET /v1/health response."""

    status: str
    model_version: str
    data_version: str
    app_version: str
    model_available: bool = Field(
        description="True only when a promoted artifact passed validation for this target."
    )
    registry_status: str = Field(
        description="Model registry resolution state, e.g. no_active_version."
    )
    limits: dict[str, int | str] = Field(
        default_factory=dict,
        description="Operational limits in force, for troubleshooting.",
    )
    prediction_history: dict[str, bool | int | str] = Field(
        default_factory=dict,
        description=(
            "Whether this server keeps prediction reports, for how long, and how many "
            "are stored. Empty when history is disabled — nothing is written by default."
        ),
    )

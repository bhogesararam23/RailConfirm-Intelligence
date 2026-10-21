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
        description="Boarding station code (uppercase).",
        min_length=1,
        max_length=10,
    )
    destination_station: str = Field(
        ...,
        description="Destination station code (uppercase).",
        min_length=1,
        max_length=10,
    )
    class_code: str = Field(
        ...,
        description="Travel class code (e.g. '2A', 'SL', '3A').",
    )
    quota_code: str = Field(
        ...,
        description="Reservation quota code (e.g. 'GN', 'TQ').",
    )

    @field_validator("train_number")
    @classmethod
    def validate_train_number(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4,6}$", v.strip()):
            raise ValueError("train_number must be 4–6 digits.")
        return v.strip()

    @field_validator("boarding_station", "destination_station")
    @classmethod
    def uppercase_station(cls, v: str) -> str:
        return v.strip().upper()

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
    )
    current_status: str = Field(
        ...,
        description=(
            "Most recently observed status string. "
            "May equal original_status if unchanged."
        ),
    )
    current_status_observed_at: datetime | None = Field(
        default=None,
        description="ISO-8601 timestamp when current_status was observed. Null if unknown.",
    )


class PredictionRequest(BaseModel):
    """Manual prediction request body."""

    journey: JourneyRequest = Field(
        ...,
        description="Journey context for the booking group.",
    )
    prediction_at: datetime = Field(
        ...,
        description="ISO-8601 timestamp at which the prediction is requested.",
    )
    passengers: list[PassengerRequest] = Field(
        ...,
        description="List of passengers in the booking group (at least 1).",
        min_length=1,
    )


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
    is_supported: bool = Field(
        description="True if a probability estimate is available; False if abstaining.",
    )
    abstention_reason: str | None = Field(
        default=None,
        description="Stable reason code if abstaining; null if supported.",
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


class PredictionResponse(BaseModel):
    """Response to a manual prediction request.

    Always present regardless of whether the engine abstains.
    """

    prediction_id: str = Field(description="Unique identifier for this prediction record.")
    target_definition: str = Field(
        description="Human-readable name of the prediction target.",
    )
    prediction_at: datetime = Field(
        description="The timestamp supplied in the request at which prediction was made.",
    )
    created_at: datetime = Field(
        description="Server time when this prediction record was created.",
    )
    model_version: str = Field(
        description="Model artifact version used (or 'no_model_v0' when abstaining).",
    )
    feature_schema_version: str
    evidence_coverage: str = Field(
        description="Assessment of evidence quality: 'sufficient', 'partial', 'insufficient'.",
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

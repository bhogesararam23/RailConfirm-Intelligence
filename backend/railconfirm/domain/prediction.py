"""Prediction output domain types for RailConfirm Intelligence.

These types represent the immutable result of an inference request.
Predictions are separate records from observations and never overwrite them.

Key design rules
----------------
* Probabilities must lie in [0, 1] and, for supported passengers, sum to 1
  within a documented tolerance.
* If no model is available the engine must return a structured abstention —
  never a fabricated probability.
* Group probabilities are computed from a supported joint distribution or
  clearly labelled as an assumption-driven approximation.
* Every prediction record carries provenance: model version, feature schema
  version, prediction timestamp, and limitations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Enumerations ───────────────────────────────────────────────────────────────


class PredictionTarget(str, Enum):
    """Named prediction targets.

    The target names the outcome moment. Do not mix final-chart status with
    post-chart status or departure status — these are separate targets.
    """

    FINAL_CHART_CNF = "final_chart_cnf"
    """Confirmed berth at final chart preparation."""

    FINAL_CHART_CNF_OR_RAC = "final_chart_cnf_or_rac"
    """Confirmed berth or at least RAC accommodation at final chart."""


class AbstentionReason(str, Enum):
    """Stable reason codes for inference abstention.

    These codes are part of the public API contract. Do not rename or remove
    without a corresponding API version update.
    """

    NO_TRAINED_MODEL = "no_trained_model"
    """No approved, trained model artifact is available for this request."""

    UNSUPPORTED_STATUS = "unsupported_status"
    """The passenger status falls outside the supported inference domain."""

    UNSUPPORTED_CLASS = "unsupported_class"
    """The journey class code is not supported by the available model."""

    UNSUPPORTED_QUOTA = "unsupported_quota"
    """The journey quota code is not supported by the available model."""

    INSUFFICIENT_SAMPLE = "insufficient_sample"
    """Fewer training examples exist than the minimum required threshold."""

    UNKNOWN_STATUS = "unknown_status"
    """The status code could not be mapped to a known category."""

    INVALID_INPUT = "invalid_input"
    """The request contains structurally invalid input."""


# ── Per-passenger outcome ──────────────────────────────────────────────────────


# Tolerance for checking that probabilities sum to 1.
PROBABILITY_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class PassengerOutcome:
    """Probability distribution for a single passenger's final-chart outcome.

    When ``abstention_reason`` is set all probability fields are ``None``.
    When supported, probabilities must lie in [0, 1] and sum to 1 within
    :data:`PROBABILITY_SUM_TOLERANCE`.

    The included outcome classes (CNF, RAC, WL, CANCELLED, OTHER) form a
    mutually exclusive and exhaustive set for the supported population. If
    CANCELLED or OTHER are excluded from the model, the API must state whether
    probabilities are conditional on CNF/RAC/WL or include an explicit OTHER.
    """

    passenger_id: str
    p_cnf: Optional[float]
    p_rac: Optional[float]
    p_wl: Optional[float]
    p_cancelled: Optional[float]
    p_other: Optional[float]
    abstention_reason: Optional[AbstentionReason]

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.is_supported():
            probs = [self.p_cnf, self.p_rac, self.p_wl, self.p_cancelled, self.p_other]
            for p in probs:
                if p is None:
                    raise ValueError(
                        "Supported PassengerOutcome must have all probabilities set."
                    )
                if not (0.0 <= p <= 1.0):
                    raise ValueError(
                        f"Probability {p} is out of bounds [0, 1]."
                    )
            total = sum(probs)  # type: ignore[arg-type]
            if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
                raise ValueError(
                    f"Probabilities must sum to 1.0 ± {PROBABILITY_SUM_TOLERANCE}, "
                    f"got {total}."
                )
        else:
            # Abstaining: all probabilities must be None
            for attr in ("p_cnf", "p_rac", "p_wl", "p_cancelled", "p_other"):
                if getattr(self, attr) is not None:
                    raise ValueError(
                        "Abstaining PassengerOutcome must have all probabilities as None."
                    )

    def is_supported(self) -> bool:
        """Return True if this is a supported (non-abstaining) outcome."""
        return self.abstention_reason is None


def make_abstention_outcome(
    passenger_id: str,
    reason: AbstentionReason,
) -> PassengerOutcome:
    """Convenience constructor for an abstaining passenger outcome."""
    return PassengerOutcome(
        passenger_id=passenger_id,
        p_cnf=None,
        p_rac=None,
        p_wl=None,
        p_cancelled=None,
        p_other=None,
        abstention_reason=reason,
    )


# ── Group outcome ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GroupOutcome:
    """Group-level joint event probabilities.

    When ``abstention_reason`` is set all probability fields are ``None``.

    The ``method`` field identifies how the group probabilities were computed.
    The ``assumptions`` field explicitly documents any assumptions made.

    For the independence baseline: P(all CNF) = product of individual P(CNF).
    This is an approximation that must be explicitly labelled — passengers in
    one booking share context and their outcomes may be correlated.
    """

    p_all_cnf: Optional[float]
    p_all_cnf_or_rac: Optional[float]
    p_at_least_one_wl: Optional[float]
    method: str       # e.g. "independence_baseline", "joint_model", "insufficient_data"
    assumptions: str  # Explicit description of all assumptions made
    abstention_reason: Optional[AbstentionReason]


# ── Prediction record ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PredictionRecord:
    """Immutable prediction result for one inference request.

    Predictions are separate, immutable records. They do not overwrite or
    modify observation records.

    Every record carries:
    * Target definition and prediction timestamp.
    * Model version and feature schema version.
    * Per-passenger outcomes (may be abstentions).
    * Group outcome (may be abstention).
    * Evidence coverage assessment.
    * Limitations and warnings for the caller.
    """

    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    target: PredictionTarget = PredictionTarget.FINAL_CHART_CNF
    prediction_at: Optional[datetime] = None   # Time of prediction request
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "no_model_v0"
    feature_schema_version: str = "1.0.0"
    passenger_outcomes: list[PassengerOutcome] = field(default_factory=list)
    group_outcome: Optional[GroupOutcome] = None
    evidence_coverage: str = "insufficient"
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_fully_supported(self) -> bool:
        """Return True if all passengers have supported (non-abstaining) outcomes."""
        return all(o.is_supported() for o in self.passenger_outcomes)

    @property
    def any_abstaining(self) -> bool:
        """Return True if at least one passenger outcome is an abstention."""
        return any(not o.is_supported() for o in self.passenger_outcomes)

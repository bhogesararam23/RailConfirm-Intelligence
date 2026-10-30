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

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum

from railconfirm.domain.exceptions import ProbabilityError
from railconfirm.domain.validation import ensure_aware

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


EVENT_CLASSES_BY_TARGET: dict[str, tuple[str, ...]] = {
    PredictionTarget.FINAL_CHART_CNF.value: ("CNF",),
    PredictionTarget.FINAL_CHART_CNF_OR_RAC.value: ("CNF", "RAC"),
}
"""Which outcome classes each target's event covers, defined once.

The headline number a user reads is the probability of an *event*, not of one class:
``final_chart_cnf_or_rac`` is confirmed *or* RAC. Scoring, calibration and serving all
need that definition, and if any of them described the event differently the same
artifact would produce two numbers for one claim. It lives in the domain layer because
it is a property of the target, not of any pipeline that consumes it; the training
metrics re-export it as ``TARGET_EVENTS`` and keep the name reports already use."""


class AbstentionReason(str, Enum):
    """Stable reason codes for inference abstention.

    These codes are part of the public API contract. Do not rename or remove
    without a corresponding API version update.
    """

    NO_TRAINED_MODEL = "no_trained_model"
    """No approved, trained model artifact is available for this request."""

    NO_APPROVED_DATA = "no_approved_data"
    """No dataset approved for this use is available, so no evidence base exists.

    Distinct from ``NO_TRAINED_MODEL``: a trained model may exist in principle,
    but estimation without an approved record set is not defensible. This is the
    state of the repository until a dataset clears docs/data/DATASET_INTAKE_CHECKLIST.md.
    """

    MODEL_ARTIFACT_INVALID = "model_artifact_invalid"
    """A model artifact is configured but failed validation and is not being used.

    Reported instead of falling back silently, so a broken or mismatched artifact
    stays visible rather than looking like "no model exists yet".
    """

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

GROUP_DERIVED_TOLERANCE = 1e-5
"""How far two separately rounded group tables may disagree.

Each figure is published rounded to six decimals and the derived tables are built from
those rounded values, so a difference of a few rounding steps is arithmetic, not an
error. Anything larger means two different computations, which is what the check is
for."""


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
    p_cnf: float | None
    p_rac: float | None
    p_wl: float | None
    p_cancelled: float | None
    p_other: float | None
    abstention_reason: AbstentionReason | None
    basis: str | None = None
    """Which evidence cohort produced the estimate, or None when abstaining.

    Recorded because a broad-cohort fallback is a weaker claim than an exact
    cohort match, and a reader cannot tell them apart from the numbers alone.
    """

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
            if self.basis is not None:
                raise ValueError(
                    "Abstaining PassengerOutcome must not claim an evidence basis."
                )

    def is_supported(self) -> bool:
        """Return True if this is a supported (non-abstaining) outcome."""
        return self.abstention_reason is None

    _PROBABILITY_FIELDS = {
        "CNF": "p_cnf",
        "RAC": "p_rac",
        "WL": "p_wl",
        "CANCELLED": "p_cancelled",
        "OTHER": "p_other",
    }

    def as_distribution(self) -> dict[str, float] | None:
        """The outcome as a class→probability mapping, or None when abstaining."""
        if not self.is_supported():
            return None
        return {
            outcome: float(getattr(self, field))
            for outcome, field in self._PROBABILITY_FIELDS.items()
        }

    def with_distribution(self, distribution: Mapping[str, float]) -> PassengerOutcome:
        """The same outcome carrying a different distribution, basis kept for context.

        Used by the calibration layer, which must return the same passenger's answer
        with corrected probabilities rather than a new object that lost the evidence
        note explaining where the estimate came from.
        """
        return replace(
            self,
            p_cnf=distribution.get("CNF", self.p_cnf),
            p_rac=distribution.get("RAC", self.p_rac),
            p_wl=distribution.get("WL", self.p_wl),
            p_cancelled=distribution.get("CANCELLED", self.p_cancelled),
            p_other=distribution.get("OTHER", self.p_other),
        )


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

    What every constructed instance must satisfy, whichever method produced it:

    * all three joint figures set, finite and inside ``[0, 1]``, or all three absent;
    * ``P(all CNF) <= P(all CNF or RAC)``, because confirmed is a subset of
      confirmed-or-RAC;
    * ``P(all CNF or RAC) + P(at least one WL) <= 1``, because those two events cannot
      both happen;
    * when the count tables are published, ``P(K = k)`` sums to one and ``P(K >= k)``
      is its tail — a table nobody can reconcile is not evidence about a group.
    """

    p_all_cnf: float | None
    p_all_cnf_or_rac: float | None
    p_at_least_one_wl: float | None
    method: str       # e.g. "independence_baseline", "queue_dependent", "single_passenger", "insufficient_data"
    assumptions: str  # Explicit description of all assumptions made
    abstention_reason: AbstentionReason | None
    p_at_least_k_cnf: dict[int, float] | None = None
    p_exactly_k_cnf: dict[int, float] | None = None

    def __post_init__(self) -> None:
        self._validate_joint_probabilities()
        self._validate_count_tables()

    def _validate_joint_probabilities(self) -> None:
        figures = (self.p_all_cnf, self.p_all_cnf_or_rac, self.p_at_least_one_wl)
        if self.abstention_reason is not None:
            if any(value is not None for value in figures):
                raise ProbabilityError(
                    "An abstaining GroupOutcome must carry no joint probabilities: a "
                    "figure printed beside an abstention is a number nobody computed."
                )
            if self.p_at_least_k_cnf is not None or self.p_exactly_k_cnf is not None:
                raise ProbabilityError(
                    "An abstaining GroupOutcome must carry no count distribution: there "
                    "are no per-passenger estimates to convolve."
                )
            return
        if any(value is None for value in figures):
            raise ProbabilityError(
                "A supported GroupOutcome must set all three joint probabilities; a "
                "missing one would read as zero to every caller that multiplies it."
            )
        for name in ("p_all_cnf", "p_all_cnf_or_rac", "p_at_least_one_wl"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProbabilityError(
                    f"GroupOutcome {name} must be a number, got {value!r}."
                )
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ProbabilityError(
                    f"GroupOutcome {name} must be a finite probability in [0, 1], got "
                    f"{value!r}."
                )
        # The loop above already established that all three figures are numbers, but the
        # attribute lookups re-widen the types, so narrow once here instead of ignoring.
        all_cnf = self.p_all_cnf
        all_cnf_or_rac = self.p_all_cnf_or_rac
        at_least_one_wl = self.p_at_least_one_wl
        assert all_cnf is not None and all_cnf_or_rac is not None
        assert at_least_one_wl is not None
        if all_cnf > all_cnf_or_rac:
            raise ProbabilityError(
                f"P(all CNF) = {all_cnf} exceeds P(all CNF or RAC) = {all_cnf_or_rac}: "
                "confirmed is a subset of confirmed-or-RAC, so the first can never be "
                "the larger."
            )
        combined = all_cnf_or_rac + at_least_one_wl
        if combined > 1.0 + GROUP_DERIVED_TOLERANCE:
            raise ProbabilityError(
                f"P(all CNF or RAC) = {all_cnf_or_rac} plus P(at least one WL) = "
                f"{at_least_one_wl} exceeds 1: one passenger cannot be both settled and "
                "waitlisted, so those events must fit inside the whole."
            )

    def _validate_count_tables(self) -> None:
        exactly = self.p_exactly_k_cnf
        at_least = self.p_at_least_k_cnf
        if exactly is None and at_least is None:
            return
        # No abstention check here: _validate_joint_probabilities already refuses a
        # count distribution beside an abstention, so reaching this point means the
        # group is supported.
        if exactly is None or at_least is None:
            raise ProbabilityError(
                "P(K = k) and P(K >= k) must be published together: either alone cannot "
                "be reconciled, and an exactly-k table on its own invites the "
                "independence reading this module labels as an assumption."
            )
        highest = max(exactly)
        if highest < 1 or sorted(exactly) != list(range(highest + 1)):
            raise ProbabilityError(
                f"P(K = k) must be keyed by every count from 0 to the group size, got "
                f"{sorted(exactly)}."
            )
        if sorted(at_least) != list(range(1, highest + 1)):
            raise ProbabilityError(
                f"P(K >= k) must be keyed by every count from 1 to {highest}, got "
                f"{sorted(at_least)}."
            )
        for table, name in ((exactly, "P(K = k)"), (at_least, "P(K >= k)")):
            for key, value in table.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ProbabilityError(f"{name}[{key}] must be a number, got {value!r}.")
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    raise ProbabilityError(
                        f"{name}[{key}] must be a finite probability in [0, 1], got "
                        f"{value!r}."
                    )
        total = sum(exactly.values())
        if abs(total - 1.0) > GROUP_DERIVED_TOLERANCE:
            raise ProbabilityError(
                f"P(K = k) sums to {total}, not 1: the counts have no exact probability "
                "space behind them."
            )
        for k in range(1, highest + 1):
            tail = sum(exactly[j] for j in range(k, highest + 1))
            if abs(at_least[k] - tail) > GROUP_DERIVED_TOLERANCE:
                raise ProbabilityError(
                    f"P(K >= {k}) = {at_least[k]} is not the tail of P(K = k) = {tail}: "
                    "the two tables were derived from different arithmetic."
                )
        # Tails of a non-negative exactly-k table are non-increasing, so the check above
        # already covers "P(K >= k) cannot grow with k" — a separate test would be dead.
        all_cnf = self.p_all_cnf
        assert all_cnf is not None  # guaranteed for a supported group
        if abs(at_least[highest] - all_cnf) > GROUP_DERIVED_TOLERANCE:
            raise ProbabilityError(
                f"P(K >= {highest}) = {at_least[highest]} must equal P(all CNF) = "
                f"{all_cnf}: they are the same event under another name."
            )


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

    target: PredictionTarget
    prediction_at: datetime
    """Offset-aware as-of time of the request. Everything about this record is
    claimed relative to it, so a naive value would make the claim unverifiable."""

    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    model_version: str = "no_model_v0"
    feature_schema_version: str = "1.0.0"
    passenger_outcomes: list[PassengerOutcome] = field(default_factory=list)
    group_outcome: GroupOutcome | None = None
    evidence_coverage: str = "insufficient"
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        ensure_aware(self.prediction_at, "prediction_at")
        ensure_aware(self.created_at, "created_at")

    @property
    def is_fully_supported(self) -> bool:
        """Return True if all passengers have supported (non-abstaining) outcomes."""
        return bool(self.passenger_outcomes) and all(
            o.is_supported() for o in self.passenger_outcomes
        )

    @property
    def any_abstaining(self) -> bool:
        """Return True if at least one passenger outcome is an abstention."""
        return any(not o.is_supported() for o in self.passenger_outcomes)

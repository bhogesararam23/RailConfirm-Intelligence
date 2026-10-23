"""The calibration layer a served artifact can carry, and how it is applied.

A probability is only useful if a stated 70% means roughly seven in ten. The historical
frequency baseline is smoothed toward the base rate rather than fitted to hit observed
frequencies, so its numbers are not calibration statements even when they rank correctly.
A calibration layer is a small, explicit, reviewable correction over the **target event
probability** — the number a user actually reads — and this module owns what that means:
the shape, the arithmetic, and the refusal conditions.

Deliberately not here: how the parameters are fitted. That is a training-time decision
with its own data rules (``railconfirm.training.calibration``); serving only reads and
applies what an artifact declares. The same function is used by the evaluator, so a
measured score and a served number cannot come from different arithmetic.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.domain.prediction import PassengerOutcome

CALIBRATION_METHOD_PLATT = "platt_logistic_v1"
"""Logistic (Platt) scaling of the target event's log-odds.

One slope and one intercept, fitted on validation rows only. Chosen over isotonic
regression because it is two numbers an artifact can declare, a reviewer can read, and a
test can recompute by hand; isotonic would need a step table per band and would fit the
noise in the sample sizes this project currently has."""

CALIBRATION_METHODS = (CALIBRATION_METHOD_PLATT,)

PROBABILITY_FLOOR = 1e-9
"""Predictions are clipped to ``(floor, 1 - floor)`` before the logit.

The baseline's Laplace smoothing keeps every class away from zero, but a calibration
layer must not be defined by an infinity: logit(0) is not a number, and silently
substituting a huge negative one would let a single abstention-shaped row dominate a fit."""


@dataclass(frozen=True)
class CalibrationSpec:
    """A fitted correction, plus everything a reader needs to distrust it correctly."""

    method: str
    target: str
    event_classes: tuple[str, ...]
    slope: float
    intercept: float
    fitted_partition: str
    fitted_rows: int
    fitted_from: str | None = None
    fitted_to: str | None = None

    def __post_init__(self) -> None:
        if self.method not in CALIBRATION_METHODS:
            raise ModelArtifactError(
                f"Unknown calibration method {self.method!r}; this build knows "
                f"{list(CALIBRATION_METHODS)}."
            )
        for name in ("slope", "intercept"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ModelArtifactError(
                    f"Calibration {name} must be a number, got {value!r}."
                )
            if not math.isfinite(value):
                raise ModelArtifactError(
                    f"Calibration {name} must be finite, got {value!r}."
                )
        if self.slope < 0:
            raise ModelArtifactError(
                "Calibration slope must not be negative: as the predicted event "
                "probability rises the observed rate would have to fall, which is a "
                "correction fitted to noise rather than a calibration layer."
            )
        if self.fitted_rows < 1:
            raise ModelArtifactError(
                f"Calibration declares {self.fitted_rows} fitted rows; a correction "
                "needs at least one observation behind it."
            )
        if not self.event_classes:
            raise ModelArtifactError(
                "Calibration must name the event classes it corrects."
            )

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_classes"] = list(self.event_classes)
        return payload

    @property
    def description(self) -> str:
        window = (
            f"{self.fitted_from}..{self.fitted_to}"
            if self.fitted_from and self.fitted_to
            else "period not recorded"
        )
        return (
            f"{self.method} on {self.target} ({'/'.join(self.event_classes)}) from "
            f"{self.fitted_rows} {self.fitted_partition} rows ({window}): "
            f"slope {self.slope:.6f}, intercept {self.intercept:.6f}"
        )


def clip_probability(value: float) -> float:
    return min(1.0 - PROBABILITY_FLOOR, max(PROBABILITY_FLOOR, value))


def logit(value: float) -> float:
    p = clip_probability(value)
    return math.log(p / (1.0 - p))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def event_mass(
    distribution: Mapping[str, float], event_classes: Sequence[str]
) -> float:
    return sum(distribution.get(name, 0.0) for name in event_classes)


def calibrate_probability(spec: CalibrationSpec, predicted: float) -> float:
    """The corrected event probability for one predicted event mass."""
    return sigmoid(spec.slope * logit(predicted) + spec.intercept)


def apply_calibration(
    spec: CalibrationSpec,
    distribution: Mapping[str, float],
    event_classes: Sequence[str],
) -> dict[str, float]:
    """Move the event mass to its calibrated value, keeping each group's internal split.

    The claim being calibrated is the event ("confirmed, or RAC"), so that is what the
    correction moves. Inside the event group and outside it the classes keep their
    existing proportions: no evidence was fitted for them separately, and inventing a
    split would present an unmeasured number as a measured one.

    A mass of exactly 0 or 1 cannot be rescaled, so the distribution is returned as it
    stands rather than being clipped into a fake confidence level.
    """
    current = event_mass(distribution, event_classes)
    if current <= 0.0 or current >= 1.0:
        return dict(distribution)
    corrected = calibrate_probability(spec, current)
    within = corrected / current
    outside = (1.0 - corrected) / (1.0 - current)
    return {
        outcome: (value * within if outcome in event_classes else value * outside)
        for outcome, value in distribution.items()
    }


def spec_from_mapping(raw: Any, *, artifact_target: str) -> CalibrationSpec:
    """Validate the block an artifact declares, refusing anything it cannot describe."""
    if not isinstance(raw, dict):
        raise ModelArtifactError(
            f"Calibration must be a JSON object, got {type(raw).__name__}."
        )
    try:
        spec = CalibrationSpec(
            method=str(raw["method"]),
            target=str(raw["target"]),
            event_classes=tuple(str(name) for name in raw["event_classes"]),
            slope=raw["slope"],
            intercept=raw["intercept"],
            fitted_partition=_text(raw["fitted_partition"], "fitted_partition"),
            fitted_rows=raw["fitted_rows"],
            fitted_from=None if raw.get("fitted_from") is None else str(raw["fitted_from"]),
            fitted_to=None if raw.get("fitted_to") is None else str(raw["fitted_to"]),
        )
    except KeyError as exc:
        raise ModelArtifactError(
            f"Calibration block is missing {exc.args[0]!r}; a partial correction cannot "
            "be applied, because half a fitted layer is not a layer."
        ) from exc

    if spec.target != artifact_target:
        raise ModelArtifactError(
            f"Calibration was fitted for target {spec.target!r} but the artifact is "
            f"served for {artifact_target!r}. A correction measured against one event "
            "does not transfer to another one's probabilities."
        )
    return spec


def _text(value: Any, name: str) -> str:
    """A required string field, refusing the null that would otherwise read as "None"."""
    if not isinstance(value, str) or not value.strip():
        raise ModelArtifactError(
            f"Calibration {name} must be a non-empty string, got {value!r}."
        )
    return value


def calibrate_outcome(
    spec: CalibrationSpec, outcome: PassengerOutcome
) -> PassengerOutcome:
    """Apply the correction to one passenger's supported estimate.

    An abstention is returned untouched: there is no probability to move, and
    rewriting the reason a row refused would hide it. The evidence note gains the
    calibration identity, because "cohort SL/GN/WL n=80" alone would no longer
    describe the arithmetic that produced the number a reader sees.
    """
    distribution = outcome.as_distribution()
    if distribution is None:
        return outcome
    corrected = apply_calibration(spec, distribution, spec.event_classes)
    updated = outcome.with_distribution(corrected)
    marker = f"calibrated={spec.method}"
    basis = updated.basis
    if basis and marker not in basis:
        basis = f"{basis} {marker}"
    return replace(updated, basis=basis)

"""Fitting the calibration layer on validation rows only.

ADR-0004 sets the rule this module exists to enforce: a calibration is fitted on
development/validation data and measured on the locked test set. Fitting it on the same
rows that produce the headline score would be self-congratulation — the correction would
be tuned to the errors it is then credited with removing — so the entry point here takes
one partition's scored rows and nothing else, and refuses inputs too thin or too
degenerate to identify a slope.

The method is logistic (Platt) scaling of the target event's log-odds: two numbers,
reproducible from the rows in a fixed order, small enough for a reviewer to check, and
applied by the same function the served path uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeAlias

import pandas as pd

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.inference.calibration import (
    CALIBRATION_METHOD_PLATT,
    CalibrationSpec,
    logit,
    sigmoid,
)
from railconfirm.training.fitter import FittedBaseline
from railconfirm.training.metrics import (
    TARGET_EVENTS,
    Scorecard,
    ScoredRow,
    build_estimator,
    evaluation_provenance,
    score_partition,
    score_rows,
)

EventPair: TypeAlias = tuple[float, float]
"""(predicted event probability, observed 0/1) for one scored reservation."""

DEFAULT_MIN_CALIBRATION_ROWS = 50
"""Fewer rows than this cannot support a slope and an intercept honestly.

This is an engineering guardrail in the same spirit as the intake minimums: clearing it
means the fit is possible, not that the resulting correction is meaningful."""

MAX_ITERATIONS = 100
MAX_MAGNITUDE = 50.0
TOLERANCE = 1e-10


def event_pairs(rows: Sequence[ScoredRow]) -> list[EventPair]:
    """The pairs calibration is fitted on, from exactly the rows that were scored.

    Reusing the scored rows rather than re-walking the frame is the point: if these two
    disagreed about which rows abstained, the fitted curve would describe a different
    population than the published reliability table."""
    return [(row.event_predicted, row.event_observed) for row in rows]


def fit_platt(
    pairs: Sequence[EventPair],
    *,
    target: str,
    partition: str,
    fitted_from: str | None = None,
    fitted_to: str | None = None,
    min_rows: int = DEFAULT_MIN_CALIBRATION_ROWS,
) -> CalibrationSpec:
    """Fit the event log-odds correction on one partition's scored rows.

    Refuses rather than emitting a curve the data cannot support: too few rows, one label
    only, no spread in the predictions, a maximum-likelihood slope that runs away because
    the partition separates perfectly, or a fitted slope that points the wrong way.
    """
    if target not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Cannot calibrate target {target!r}: the event it names is not defined. "
            f"Known targets: {sorted(TARGET_EVENTS)}."
        )
    if isinstance(min_rows, bool) or not isinstance(min_rows, int) or min_rows < 2:
        raise DatasetValidationError(
            f"min_rows must be an integer of at least 2, got {min_rows!r}."
        )
    if len(pairs) < min_rows:
        raise DatasetValidationError(
            f"Cannot fit calibration on {len(pairs)} {partition} rows: at least "
            f"{min_rows} are needed before a slope and an intercept mean anything. "
            "Widen the validation period or leave the artifact uncalibrated."
        )

    positives = sum(1 for _, observed in pairs if observed > 0.5)
    if positives == 0 or positives == len(pairs):
        raise DatasetValidationError(
            f"The {partition} partition carries one label only ({positives} of "
            f"{len(pairs)} rows had the event). A calibration fitted on data with no "
            "counter-example would move every prediction toward that one class."
        )

    xs: list[float] = []
    ys: list[float] = []
    for predicted, observed in pairs:
        if not 0.0 <= predicted <= 1.0:
            raise DatasetValidationError(
                f"A scored row predicted event probability {predicted!r}, outside [0, 1]. "
                "The calibration input is wrong; fix the scoring, do not fit over it."
            )
        if predicted <= 0.0 or predicted >= 1.0:
            # Certainties carry no log-odds information and would dominate the fit.
            continue
        xs.append(logit(predicted))
        ys.append(1.0 if observed > 0.5 else 0.0)

    if len(xs) < min_rows:
        raise DatasetValidationError(
            f"Only {len(xs)} of {len(pairs)} {partition} rows have a probability in (0, 1) "
            f"to calibrate; {min_rows} are required."
        )
    if len(set(xs)) < 2:
        raise DatasetValidationError(
            f"Every {partition} row carries the same predicted event probability, so no "
            "slope is identifiable: there is nothing for a correction to relate the "
            "observed rate to."
        )

    slope = 0.0
    intercept = 0.0
    converged = False
    for _ in range(MAX_ITERATIONS):
        fitted = [sigmoid(slope * x + intercept) for x in xs]
        gradient_slope = sum(
            (p - y) * x for p, y, x in zip(fitted, ys, xs, strict=True)
        )
        gradient_intercept = sum(p - y for p, y in zip(fitted, ys, strict=True))
        weight = [p * (1.0 - p) for p in fitted]
        h11 = sum(w * x * x for w, x in zip(weight, xs, strict=True))
        h12 = sum(w * x for w, x in zip(weight, xs, strict=True))
        h22 = sum(weight)
        determinant = h11 * h22 - h12 * h12
        if determinant <= 0.0:
            raise DatasetValidationError(
                f"The {partition} rows give a singular Hessian (determinant "
                f"{determinant:.3e}): either the predicted probabilities do not vary "
                "enough to identify both a slope and an intercept, or the labels "
                "separate them perfectly and the maximum-likelihood slope runs away. "
                "Neither supports a correction."
            )
        step_slope = -(h22 * gradient_slope - h12 * gradient_intercept) / determinant
        step_intercept = -(h11 * gradient_intercept - h12 * gradient_slope) / determinant
        slope += step_slope
        intercept += step_intercept
        if not (abs(slope) < MAX_MAGNITUDE and abs(intercept) < MAX_MAGNITUDE):
            raise DatasetValidationError(
                f"Calibration did not settle on {len(xs)} {partition} rows: the fitted "
                f"slope reached {slope:.3f}. Perfectly separable validation data has no "
                "maximum-likelihood slope, so a correction here would be an artefact of "
                "the sample."
            )
        if max(abs(step_slope), abs(step_intercept)) < TOLERANCE:
            converged = True
            break

    if not converged:
        raise DatasetValidationError(
            f"Calibration did not converge within {MAX_ITERATIONS} Newton steps on "
            f"{len(xs)} {partition} rows."
        )
    if slope < 0:
        raise DatasetValidationError(
            f"The fitted slope is negative ({slope:.6f}): on the {partition} rows the "
            "event becomes less frequent as the predicted probability rises. That is "
            "noise being fitted, not a calibration layer, so no correction is written."
        )

    return CalibrationSpec(
        method=CALIBRATION_METHOD_PLATT,
        target=target,
        event_classes=TARGET_EVENTS[target],
        slope=slope,
        intercept=intercept,
        fitted_partition=partition,
        fitted_rows=len(xs),
        fitted_from=fitted_from,
        fitted_to=fitted_to,
    )


def calibration_improves(
    *, before: float | None, after: float | None
) -> bool:
    """Did the correction reduce the event Brier on the rows it was judged on?

    ``None`` on either side means there was nothing to compare, which is not an
    improvement. Called with the validation score for the fit decision, and with the
    locked-test score for what the report states.
    """
    if before is None or after is None:
        return False
    return after < before


@dataclass(frozen=True)
class CalibrationEvidence:
    """The fitted correction plus the before/after scores that justify shipping it.

    The "after" side is what the served path produces, so the ordinary validation and
    test numbers in the report describe the same arithmetic a user's screen will show.
    The "before" side is kept beside it because a correction that helps on the rows it
    was fitted on and hurts on the locked test is exactly the finding a report must not
    hide.
    """

    spec: CalibrationSpec
    validation_before: Scorecard
    validation_after: Scorecard
    test_before: Scorecard
    test_after: Scorecard

    @property
    def validation_effect(self) -> float:
        """Change in validation event Brier. Negative is an improvement."""
        assert self.validation_before.event_brier is not None
        assert self.validation_after.event_brier is not None
        return round(
            self.validation_after.event_brier - self.validation_before.event_brier, 6
        )

    @property
    def test_effect(self) -> float:
        assert self.test_before.event_brier is not None
        assert self.test_after.event_brier is not None
        return round(self.test_after.event_brier - self.test_before.event_brier, 6)

    @property
    def helps_on_locked_test(self) -> bool:
        return self.test_effect < 0

    def to_dict(self) -> dict[str, object]:
        return {
            "calibration": self.spec.to_mapping(),
            "validation_event_brier_before": self.validation_before.event_brier,
            "validation_event_brier_after": self.validation_after.event_brier,
            "validation_event_brier_change": self.validation_effect,
            "test_event_brier_before": self.test_before.event_brier,
            "test_event_brier_after": self.test_after.event_brier,
            "test_event_brier_change": self.test_effect,
            "helps_on_locked_test": self.helps_on_locked_test,
        }


def _partition_window(fitted: FittedBaseline, name: str) -> tuple[str | None, str | None]:
    for partition in fitted.split.partitions:
        if partition.name == name:
            return partition.start_date, partition.end_date
    return None, None


def fit_and_measure(
    fitted: FittedBaseline,
    *,
    dataset_id: str,
    dataset_sha256: str,
    source_reference: str,
    approval_status: str,
    is_synthetic: bool,
    mapping_version: str,
    target: str,
    min_rows: int = DEFAULT_MIN_CALIBRATION_ROWS,
) -> CalibrationEvidence:
    """Fit on validation, embed only if it helps there, and measure on the locked test.

    ADR-0004's rule in code: the correction may not be fitted on the rows that produce
    the headline score, and a calibration that does not reduce the event Brier on the
    partition it was judged on is not written into the artifact at all.
    """
    if fitted.metadata.target != target:
        raise DatasetValidationError(
            f"Cannot calibrate {target!r} on an artifact fitted for "
            f"{fitted.metadata.target!r}: the event whose probability is corrected has "
            "to be the event the model was fitted for."
        )
    estimator = build_estimator(
        fitted.cohorts,
        evaluation_provenance(
            dataset_id,
            dataset_sha256,
            source_reference,
            approval_status,
            is_synthetic=is_synthetic,
            mapping_version=mapping_version,
            fitted_from=fitted.metadata.trained_from,
            fitted_to=fitted.metadata.trained_to,
        ),
        min_sample_threshold=fitted.metadata.min_sample_threshold,
        laplace_alpha=fitted.metadata.laplace_alpha,
    )
    validation_rows = score_rows(fitted.split.val, estimator, target=target)
    fitted_from, fitted_to = _partition_window(fitted, "validation")
    spec = fit_platt(
        event_pairs(validation_rows.rows),
        target=target,
        partition="validation",
        fitted_from=fitted_from,
        fitted_to=fitted_to,
        min_rows=min_rows,
    )

    def score(frame: pd.DataFrame, partition: str, *, calibrated: bool) -> Scorecard:
        return score_partition(
            frame,
            estimator,
            prevalence=fitted.prevalence,
            partition=partition,
            target=target,
            calibration=spec if calibrated else None,
        )

    validation_before = score(fitted.split.val, "validation", calibrated=False)
    validation_after = score(fitted.split.val, "validation", calibrated=True)
    if not calibration_improves(
        before=validation_before.event_brier, after=validation_after.event_brier
    ):
        raise DatasetValidationError(
            f"Calibration was fitted on the validation partition but did not reduce its "
            f"event Brier ({validation_before.event_brier} -> {validation_after.event_brier}). "
            "No correction is written into the artifact: a layer that does not help on "
            "the rows it was chosen for is a decoration, and a decorated number is worse "
            "than an honest uncalibrated one."
        )

    return CalibrationEvidence(
        spec=spec,
        validation_before=validation_before,
        validation_after=validation_after,
        test_before=score(fitted.split.test, "test", calibrated=False),
        test_after=score(fitted.split.test, "test", calibrated=True),
    )

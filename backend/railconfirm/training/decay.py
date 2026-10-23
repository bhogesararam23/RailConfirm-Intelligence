"""Frozen-artifact decay: one already-fitted table, scored on each later period it faces.

`origins` refits at every cutoff, so it measures the fitting procedure over time. That is a
different question from the one a promoted artifact answers in service: the table is fixed,
and the world moves away from the period it was counted from. This module scores the same
artifact — its cohorts, its smoothing settings, its calibration layer, its prevalence
baseline — against successive horizons after its own declared last fitted date, and never
refits any of them.

Three rules make the numbers mean what they say:

* the cutoff comes from the artifact (`trained_to`), not from a caller's guess, so a run
  cannot quietly score the period the table already saw;
* the prevalence baseline is computed once from the frozen block, because a baseline
  recomputed per horizon drifts toward the answer it is judging;
* fewer than two usable horizons produces no scores at all, because one future window is a
  holdout, not a decay curve.

Every score comes from the same `score_partition` call the single-cutoff report uses, with
the same estimator construction the registry serves from, so a decay number and a served
number cannot describe different arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from railconfirm.data.preprocessing import (
    DEFAULT_HORIZON_DATES,
    DEFAULT_STEP_DATES,
    FrozenHorizonPlan,
    HorizonWindow,
    frozen_horizon_windows,
)
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.inference.artifacts import LoadedArtifact
from railconfirm.inference.baseline import (
    COHORT_FEATURES,
    COHORT_STATUS_SEMANTICS,
    HistoricalFrequencyBaseline,
)
from railconfirm.inference.calibration import CalibrationSpec
from railconfirm.training.dataset import ApprovedDataset
from railconfirm.training.fitter import fit_cohorts, prevalence_distribution
from railconfirm.training.metrics import (
    DEFAULT_MIN_SEGMENT_ROWS,
    TARGET_EVENTS,
    Scorecard,
    build_estimator,
    evaluation_provenance,
    score_partition,
)

FROZEN_EVALUATION_METHOD = "one frozen artifact, scored on each successive horizon"
"""The method line a reader judges these numbers by: nothing is refitted, so this measures
one artifact's decay rather than how a fitting procedure behaves over time."""


@dataclass(frozen=True)
class HorizonScore:
    """One future window and the score the frozen table earned on it."""

    window: HorizonWindow
    scorecard: Scorecard
    cohort_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizon": self.window.to_dict(),
            "cohorts": self.cohort_count,
            "score": self.scorecard.to_dict(),
        }


@dataclass(frozen=True)
class FrozenDecayResult:
    """The frozen block, every horizon scored against it, and the drift between them."""

    plan: FrozenHorizonPlan
    scores: tuple[HorizonScore, ...]
    target: str
    artifact_version: str
    fitted_from: str | None
    fitted_to: str
    cohort_count: int
    calibration: CalibrationSpec | None
    prevalence: dict[str, float]
    prevalence_rows: int
    min_sample_threshold: int
    laplace_alpha: float
    artifact_is_synthetic: bool
    dataset_is_synthetic: bool

    @property
    def cutoff(self) -> str:
        return self.plan.cutoff

    @property
    def horizon_count(self) -> int:
        return len(self.scores)

    @property
    def rows_scored(self) -> int:
        return sum(score.scorecard.scored_rows for score in self.scores)

    @property
    def rows_seen(self) -> int:
        return sum(score.scorecard.rows for score in self.scores)

    def _values(self, attribute: str) -> list[float]:
        """Non-null values for one scorecard field, kept in horizon order.

        Order is the point: drift means "first horizon to last horizon", so a collection
        that lost the ordering would make the headline number meaningless.
        """
        return [
            getattr(score.scorecard, attribute)
            for score in self.scores
            if getattr(score.scorecard, attribute) is not None
        ]

    def _spread(self, attribute: str) -> tuple[float, float] | None:
        values = self._values(attribute)
        if not values:
            return None
        return min(values), max(values)

    @property
    def horizons_with_scores(self) -> int:
        """Horizons that produced a distribution score at all.

        A horizon the table abstained on everywhere has no score, which is a different fact
        from a score that lost to the baseline and must not be counted as one."""
        return len(self._values("brier"))

    @property
    def horizons_with_event_scores(self) -> int:
        return len(self._values("event_brier"))

    def _count(self, attribute: str) -> int:
        return sum(1 for score in self.scores if getattr(score.scorecard, attribute) is True)

    @property
    def horizons_beating_baseline(self) -> int:
        return self._count("beats_baseline")

    @property
    def horizons_beating_event_baseline(self) -> int:
        return self._count("event_beats_baseline")

    @property
    def horizons_losing_event_baseline(self) -> int:
        return sum(
            1
            for score in self.scores
            if score.scorecard.event_beats_baseline is False
        )

    @property
    def first_event_brier(self) -> float | None:
        values = self._values("event_brier")
        return values[0] if values else None

    @property
    def last_event_brier(self) -> float | None:
        values = self._values("event_brier")
        return values[-1] if values else None

    @property
    def event_brier_drift(self) -> float | None:
        first, last = self.first_event_brier, self.last_event_brier
        if first is None or last is None:
            return None
        return round(last - first, 6)

    @property
    def first_coverage(self) -> float | None:
        values = self._values("coverage")
        return values[0] if values else None

    @property
    def last_coverage(self) -> float | None:
        values = self._values("coverage")
        return values[-1] if values else None

    @property
    def coverage_drift(self) -> float | None:
        first, last = self.first_coverage, self.last_coverage
        if first is None or last is None:
            return None
        return round(last - first, 6)

    @property
    def event_brier_spread(self) -> tuple[float, float] | None:
        return self._spread("event_brier")

    @property
    def brier_spread(self) -> tuple[float, float] | None:
        return self._spread("brier")

    @property
    def coverage_spread(self) -> tuple[float, float] | None:
        return self._spread("coverage")

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "horizons": self.horizon_count,
            "horizons_with_scores": self.horizons_with_scores,
            "horizons_with_event_scores": self.horizons_with_event_scores,
            "horizons_beating_baseline": self.horizons_beating_baseline,
            "horizons_beating_event_baseline": self.horizons_beating_event_baseline,
            "horizons_losing_event_baseline": self.horizons_losing_event_baseline,
            "rows_scored": self.rows_scored,
            "rows_seen": self.rows_seen,
            "first_event_brier": self.first_event_brier,
            "last_event_brier": self.last_event_brier,
            "event_brier_drift": self.event_brier_drift,
            "first_coverage": self.first_coverage,
            "last_coverage": self.last_coverage,
            "coverage_drift": self.coverage_drift,
            "event_brier_spread": list(self.event_brier_spread)
            if self.event_brier_spread
            else None,
            "brier_spread": list(self.brier_spread) if self.brier_spread else None,
            "coverage_spread": list(self.coverage_spread) if self.coverage_spread else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_method": FROZEN_EVALUATION_METHOD,
            "target": self.target,
            "target_event_classes": list(TARGET_EVENTS[self.target]),
            "artifact": {
                "version": self.artifact_version,
                "fitted_from": self.fitted_from,
                "fitted_to": self.fitted_to,
                "cohorts": self.cohort_count,
                "min_sample_threshold": self.min_sample_threshold,
                "laplace_alpha": self.laplace_alpha,
                "is_synthetic": self.artifact_is_synthetic,
            },
            "dataset": {"is_synthetic": self.dataset_is_synthetic},
            "prevalence": dict(sorted(self.prevalence.items())),
            "prevalence_rows": self.prevalence_rows,
            "calibration": self.calibration.to_mapping() if self.calibration else None,
            "plan": self.plan.to_dict(),
            "summary": self.summary,
            "horizons": [score.to_dict() for score in self.scores],
        }


def _require_frozen_contract(loaded: LoadedArtifact) -> None:
    """Refuse an artifact this build would not serve, before scoring anything.

    Decay numbers only describe the estimator the product runs, so the same two declarations
    the registry checks at load are checked here: a table keyed by a different status rule,
    or crediting features it does not read, is a different estimator under the same name.
    """
    metadata = loaded.metadata
    if metadata.cohort_semantics != COHORT_STATUS_SEMANTICS:
        raise DatasetValidationError(
            f"Artifact {metadata.version} declares cohort_semantics "
            f"{metadata.cohort_semantics!r}, but this build answers requests from "
            f"{COHORT_STATUS_SEMANTICS!r}; its decay cannot be measured with the served "
            "lookup rule because the table was not built with it."
        )
    if tuple(metadata.features_used) != COHORT_FEATURES:
        raise DatasetValidationError(
            f"Artifact {metadata.version} declares features_used "
            f"{tuple(metadata.features_used)}, but the served cohort lookup reads "
            f"{COHORT_FEATURES}; decay of an estimator that is not the one in service "
            "would be a number about nothing."
        )


def frozen_decay_estimator(loaded: LoadedArtifact) -> HistoricalFrequencyBaseline:
    """The artifact's own estimator, marked evaluation-only so synthetic fixtures can score.

    Same cohorts, same threshold, same smoothing as `LoadedArtifact.baseline()`, which is
    what the engine serves. The one difference is `evaluation_only` on the provenance, which
    is how offline scoring already exercises a synthetic table; it is unreachable from the
    serving path, so it cannot turn a fixture into a user-visible probability.
    """
    metadata = loaded.metadata
    return build_estimator(
        loaded.cohorts,
        evaluation_provenance(
            metadata.dataset_id,
            metadata.dataset_sha256,
            metadata.source_reference,
            metadata.data_approval_status,
            is_synthetic=metadata.is_synthetic,
            mapping_version=metadata.status_mapping_version,
            fitted_from=metadata.trained_from,
            fitted_to=metadata.trained_to,
        ),
        min_sample_threshold=metadata.min_sample_threshold,
        laplace_alpha=metadata.laplace_alpha,
    )


def run_frozen_decay(
    dataset: ApprovedDataset,
    loaded: LoadedArtifact,
    *,
    horizon_dates: int = DEFAULT_HORIZON_DATES,
    step_dates: int = DEFAULT_STEP_DATES,
    gap_days: int = 0,
    min_scored_rows: int = 1,
    min_segment_rows: int = DEFAULT_MIN_SEGMENT_ROWS,
) -> FrozenDecayResult:
    """Score one frozen artifact on each horizon after its own fitted period.

    Raises when the artifact cannot say where its fitted period ended, when it declares a
    contract this build would refuse to serve, or when the file cannot support two horizons
    past that cutoff. Nothing here refits: the cohort table, its settings and any
    calibration layer are exactly what the artifact carries.
    """
    metadata = loaded.metadata
    if metadata.target not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Artifact {metadata.version} targets {metadata.target!r}, which names no "
            f"scorable event. Known targets: {sorted(TARGET_EVENTS)}."
        )
    if not metadata.trained_to:
        raise DatasetValidationError(
            f"Artifact {metadata.version} does not declare the period it was fitted on "
            "(trained_from/trained_to), so decay has no cutoff: without one, the dates it "
            "was fitted on cannot be told apart from the dates that test it."
        )
    _require_frozen_contract(loaded)

    plan = frozen_horizon_windows(
        dataset.frame,
        fitted_to=metadata.trained_to,
        horizon_dates=horizon_dates,
        step_dates=step_dates,
        gap_days=gap_days,
        min_scored_rows=min_scored_rows,
    )
    if not plan.eligible:
        raise DatasetValidationError(
            f"Cannot measure decay for artifact {metadata.version} from "
            f"{dataset.dataset_id}:\n  - " + "\n  - ".join(plan.reasons)
        )

    try:
        frozen_fit = fit_cohorts(plan.train)
    except DatasetValidationError as exc:
        raise DatasetValidationError(
            f"The frozen block for artifact {metadata.version} holds nothing fittable in "
            f"this file ({plan.train_dates[0]}..{plan.train_dates[-1]}), so no reference "
            f"population exists to score horizons against: {exc}"
        ) from exc

    prevalence = prevalence_distribution(frozen_fit.label_distribution)
    estimator = frozen_decay_estimator(loaded)

    scores = tuple(
        HorizonScore(
            window=window,
            scorecard=score_partition(
                window.scored,
                estimator,
                prevalence=prevalence,
                partition=f"horizon_{window.index}",
                target=metadata.target,
                calibration=metadata.calibration,
                min_segment_rows=min_segment_rows,
            ),
            cohort_count=len(loaded.cohorts),
        )
        for window in plan.horizons
    )
    return FrozenDecayResult(
        plan=plan,
        scores=scores,
        target=metadata.target,
        artifact_version=metadata.version,
        fitted_from=metadata.trained_from,
        fitted_to=metadata.trained_to,
        cohort_count=len(loaded.cohorts),
        calibration=metadata.calibration,
        prevalence=prevalence,
        prevalence_rows=frozen_fit.rows_used,
        min_sample_threshold=metadata.min_sample_threshold,
        laplace_alpha=metadata.laplace_alpha,
        artifact_is_synthetic=metadata.is_synthetic,
        dataset_is_synthetic=dataset.is_synthetic,
    )


def describe_result(result: FrozenDecayResult) -> str:
    """The lines a terminal run prints: the frozen block, each horizon, then the drift."""
    lines: list[str] = [
        (
            f"Frozen artifact {result.artifact_version} "
            f"({result.fitted_from or 'undated'}..{result.fitted_to}, "
            f"{result.cohort_count} cohorts, cutoff {result.cutoff})"
        ),
        *(score.window.describe() for score in result.scores),
    ]
    for score in result.scores:
        card = score.scorecard
        lines.append(
            f"  horizon {score.window.index} "
            f"({score.window.scored_dates[0]}..{score.window.scored_dates[-1]}): "
            f"Brier {_fmt(card.brier)} vs {_fmt(card.baseline_brier)}, event "
            f"{_fmt(card.event_brier)} vs {_fmt(card.event_baseline_brier)}, coverage "
            f"{card.coverage:.1%} ({card.scored_rows}/{card.rows})"
        )
    lines.append(
        f"Drift across {result.horizon_count} horizons "
        f"({result.horizons_with_scores} scored): event Brier "
        f"{_fmt(result.first_event_brier)} -> {_fmt(result.last_event_brier)} "
        f"({result.event_brier_drift if result.event_brier_drift is not None else 'n/a'}), "
        f"coverage {_fmt(result.first_coverage)} -> {_fmt(result.last_coverage)}"
    )
    lines.append(
        f"  event beat the frozen base rate in "
        f"{result.horizons_beating_event_baseline}/"
        f"{result.horizons_with_event_scores} scored horizons"
    )
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"

"""Rolling-origin evaluation: refit at each cutoff, score only the period after it.

One cutoff measures one moment. A baseline that happens to look good on the last few
dates of a file is not temporally robust, so this module walks the origin forward,
refits the cohort table on the data up to each cutoff, and scores the horizon that
follows it. Two things it deliberately does not do:

* it never reuses a later origin's labels as an earlier origin's training data;
* it never reports an aggregate when the plan cannot support at least two origins —
  a single measurement under a plural name is how a trend gets invented.

Every number here comes from the same ``fit_cohorts`` and ``score_partition`` calls the
single-cutoff pipeline uses, so the two cannot drift apart. The aggregate publishes two
summary figures per score rather than one: a mean over origins and a mean pooled over
scored rows. They answer different questions and can disagree, so the report says which
way each one points against its own baseline rather than picking a flattering one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from railconfirm.data.preprocessing import (
    DATE_COLUMN,
    DEFAULT_HORIZON_DATES,
    DEFAULT_MIN_TRAIN_DATES,
    DEFAULT_STEP_DATES,
    OriginWindow,
    RollingOriginPlan,
    rolling_origin_windows,
)
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.training.fitter import fit_cohorts, prevalence_distribution
from railconfirm.training.metrics import (
    DEFAULT_MIN_SEGMENT_ROWS,
    TARGET_EVENTS,
    Scorecard,
    build_estimator,
    evaluation_provenance,
    score_partition,
)


@dataclass(frozen=True)
class OriginScore:
    """One cutoff's fit and the score of the horizon that followed it."""

    window: OriginWindow
    scorecard: Scorecard
    cohort_count: int
    rows_excluded: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.window.to_dict(),
            "cohorts": self.cohort_count,
            "fit_exclusions": dict(sorted(self.rows_excluded.items())),
            "score": self.scorecard.to_dict(),
        }


@dataclass(frozen=True)
class RollingOriginResult:
    """Every origin that was measured, plus the aggregate a reader will quote."""

    plan: RollingOriginPlan
    scores: tuple[OriginScore, ...]
    target: str

    @property
    def origin_count(self) -> int:
        return len(self.scores)

    @property
    def rows_scored(self) -> int:
        return sum(score.scorecard.scored_rows for score in self.scores)

    @property
    def rows_seen(self) -> int:
        return sum(score.scorecard.rows for score in self.scores)

    def _values(self, attribute: str) -> list[float]:
        collected: list[float] = []
        for score in self.scores:
            value = getattr(score.scorecard, attribute)
            if value is not None:
                collected.append(value)
        return collected

    def _mean(self, attribute: str) -> float | None:
        values = self._values(attribute)
        if not values:
            return None
        return round(sum(values) / len(values), 6)

    def _spread(self, attribute: str) -> tuple[float, float] | None:
        values = self._values(attribute)
        if not values:
            return None
        return min(values), max(values)

    def _pooled(self, attribute: str) -> float | None:
        """``attribute`` pooled over scored rows instead of averaged over origins.

        Each origin's score is itself a mean over the rows it scored, so the plain mean of
        those means weights a two-row horizon exactly as much as a two-thousand-row one.
        Both figures are published, because they answer different questions: the mean says
        how the fitting procedure did per cutoff, and the pooled figure says what a passenger
        actually received per prediction across the whole run. Leading with the wrong one is
        how a run of mostly-empty horizons reads as evidence.
        """
        total = 0.0
        rows = 0
        for score in self.scores:
            value = getattr(score.scorecard, attribute)
            if value is None:
                continue
            scored = score.scorecard.scored_rows
            if scored <= 0:
                continue
            total += float(value) * scored
            rows += scored
        if rows == 0:
            return None
        return round(total / rows, 6)

    def _scored_row_counts(self) -> list[int]:
        return [
            score.scorecard.scored_rows
            for score in self.scores
            if score.scorecard.brier is not None
        ]

    @property
    def pooled_brier(self) -> float | None:
        return self._pooled("brier")

    @property
    def pooled_baseline_brier(self) -> float | None:
        return self._pooled("baseline_brier")

    @property
    def pooled_event_brier(self) -> float | None:
        return self._pooled("event_brier")

    @property
    def pooled_event_baseline_brier(self) -> float | None:
        return self._pooled("event_baseline_brier")

    @property
    def scored_rows_spread(self) -> tuple[int, int] | None:
        """Smallest and largest scored-row count among origins that scored at all."""
        counts = self._scored_row_counts()
        if not counts:
            return None
        return min(counts), max(counts)

    def _verdict(self, value: float | None, baseline: float | None) -> bool | None:
        if value is None or baseline is None:
            return None
        return value < baseline

    def _agreement(
        self,
        mean: float | None,
        pooled: float | None,
        baseline_mean: float | None,
        baseline_pooled: float | None,
    ) -> str:
        """Whether the two aggregations point the same way against their baselines."""
        per_origin = self._verdict(mean, baseline_mean)
        per_row = self._verdict(pooled, baseline_pooled)
        if per_origin is None or per_row is None:
            return "undetermined"
        return "agree" if per_origin == per_row else "disagree"

    @property
    def distribution_agreement(self) -> str:
        return self._agreement(
            self.mean_brier,
            self.pooled_brier,
            self.mean_baseline_brier,
            self.pooled_baseline_brier,
        )

    @property
    def event_agreement(self) -> str:
        return self._agreement(
            self.mean_event_brier,
            self.pooled_event_brier,
            self.mean_event_baseline_brier,
            self.pooled_event_baseline_brier,
        )

    @property
    def mean_brier(self) -> float | None:
        return self._mean("brier")

    @property
    def mean_baseline_brier(self) -> float | None:
        return self._mean("baseline_brier")

    @property
    def mean_event_brier(self) -> float | None:
        return self._mean("event_brier")

    @property
    def mean_event_baseline_brier(self) -> float | None:
        return self._mean("event_baseline_brier")

    @property
    def brier_spread(self) -> tuple[float, float] | None:
        return self._spread("brier")

    @property
    def event_brier_spread(self) -> tuple[float, float] | None:
        return self._spread("event_brier")

    @property
    def coverage_spread(self) -> tuple[float, float] | None:
        return self._spread("coverage")

    def _count_beating(self, attribute: str) -> int:
        return sum(
            1 for score in self.scores if getattr(score.scorecard, attribute) is True
        )

    @property
    def origins_beating_baseline(self) -> int:
        return self._count_beating("beats_baseline")

    @property
    def origins_beating_event_baseline(self) -> int:
        return self._count_beating("event_beats_baseline")

    @property
    def origins_with_scores(self) -> int:
        """Origins that produced a distribution score at all.

        An origin whose every row abstained has no score, which is not the same fact as
        a score that lost to the baseline, so the two must not be counted together."""
        return len(self._values("brier"))

    @property
    def origins_with_event_scores(self) -> int:
        return len(self._values("event_brier"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_event_classes": list(TARGET_EVENTS[self.target]),
            "plan": self.plan.to_dict(),
            "aggregate": {
                "origins": self.origin_count,
                "origins_with_scores": self.origins_with_scores,
                "origins_with_event_scores": self.origins_with_event_scores,
                "rows_scored": self.rows_scored,
                "rows_seen": self.rows_seen,
                "mean_brier": self.mean_brier,
                "mean_baseline_brier": self.mean_baseline_brier,
                "mean_event_brier": self.mean_event_brier,
                "mean_event_baseline_brier": self.mean_event_baseline_brier,
                "pooled_brier": self.pooled_brier,
                "pooled_baseline_brier": self.pooled_baseline_brier,
                "pooled_event_brier": self.pooled_event_brier,
                "pooled_event_baseline_brier": self.pooled_event_baseline_brier,
                "scored_rows_spread": (
                    list(self.scored_rows_spread) if self.scored_rows_spread else None
                ),
                "distribution_agreement": self.distribution_agreement,
                "event_agreement": self.event_agreement,
                "brier_spread": list(self.brier_spread) if self.brier_spread else None,
                "event_brier_spread": (
                    list(self.event_brier_spread)
                    if self.event_brier_spread
                    else None
                ),
                "coverage_spread": (
                    list(self.coverage_spread) if self.coverage_spread else None
                ),
                "origins_beating_baseline": self.origins_beating_baseline,
                "origins_beating_event_baseline": self.origins_beating_event_baseline,
            },
            "origins": [score.to_dict() for score in self.scores],
        }


def run_rolling_origins(
    frame: pd.DataFrame,
    *,
    dataset_id: str,
    dataset_sha256: str,
    source_reference: str,
    approval_status: str,
    is_synthetic: bool,
    mapping_version: str,
    target: str = PredictionTarget.FINAL_CHART_CNF.value,
    min_sample_threshold: int = 30,
    laplace_alpha: float = 1.0,
    min_train_dates: int = DEFAULT_MIN_TRAIN_DATES,
    horizon_dates: int = DEFAULT_HORIZON_DATES,
    step_dates: int = DEFAULT_STEP_DATES,
    gap_days: int = 0,
    date_column: str = DATE_COLUMN,
    min_scored_rows: int = 1,
    min_segment_rows: int = DEFAULT_MIN_SEGMENT_ROWS,
) -> RollingOriginResult:
    """Refit and score one origin per cutoff, each with its own prevalence baseline.

    Raises when the plan cannot support two origins, or when a training window holds
    nothing fittable: half a temporal evaluation is worse than none, because it reads
    like evidence of stability.
    """
    if target not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Cannot score target {target!r}: the event it names is not defined. "
            f"Known targets: {sorted(TARGET_EVENTS)}."
        )
    plan = rolling_origin_windows(
        frame,
        date_column=date_column,
        min_train_dates=min_train_dates,
        horizon_dates=horizon_dates,
        step_dates=step_dates,
        gap_days=gap_days,
        min_scored_rows=min_scored_rows,
    )
    if not plan.eligible:
        raise DatasetValidationError(
            "Cannot run rolling-origin evaluation:\n  - " + "\n  - ".join(plan.reasons)
        )

    scores: list[OriginScore] = []
    for window in plan.windows:
        try:
            summary = fit_cohorts(window.train)
        except DatasetValidationError as exc:
            raise DatasetValidationError(
                f"Origin {window.index} ({window.train_dates[0]}.."
                f"{window.train_dates[-1]}) could not be fitted: {exc}"
            ) from exc
        estimator = build_estimator(
            summary.cohorts,
            evaluation_provenance(
                dataset_id,
                dataset_sha256,
                source_reference,
                approval_status,
                is_synthetic=is_synthetic,
                mapping_version=mapping_version,
                fitted_from=window.train_dates[0],
                fitted_to=window.train_dates[-1],
            ),
            min_sample_threshold=min_sample_threshold,
            laplace_alpha=laplace_alpha,
        )
        scorecard = score_partition(
            window.scored,
            estimator,
            prevalence=prevalence_distribution(summary.label_distribution),
            partition=f"origin_{window.index}",
            target=target,
            min_segment_rows=min_segment_rows,
        )
        scores.append(
            OriginScore(
                window=window,
                scorecard=scorecard,
                cohort_count=len(summary.cohorts),
                rows_excluded=dict(summary.excluded),
            )
        )
    return RollingOriginResult(plan=plan, scores=tuple(scores), target=target)


def describe_result(result: RollingOriginResult) -> str:
    """The lines a terminal run prints: one per origin, then the aggregate."""
    lines: Sequence[str] = [window.describe() for window in result.plan.windows]
    scored = result.origins_with_scores
    event_scored = result.origins_with_event_scores
    event_line = (
        f"  event {_fmt(result.mean_event_brier)} vs baseline "
        f"{_fmt(result.mean_event_baseline_brier)}, "
        f"{result.origins_beating_event_baseline}/{event_scored} beat it"
        if event_scored
        else "  event not measured: no origin produced a target-event score"
    )
    aggregate = [
        f"Aggregate over {result.origin_count} origin(s), {scored} of which produced a "
        f"score: mean Brier {_fmt(result.mean_brier)} vs baseline "
        f"{_fmt(result.mean_baseline_brier)}, {result.origins_beating_baseline}/{scored} "
        "beat it",
        event_line,
        f"  pooled over scored rows: Brier {_fmt(result.pooled_brier)} vs baseline "
        f"{_fmt(result.pooled_baseline_brier)}, event "
        f"{_fmt(result.pooled_event_brier)} vs "
        f"{_fmt(result.pooled_event_baseline_brier)}",
        f"  rows scored {result.rows_scored} of {result.rows_seen}",
    ]
    rows_spread = result.scored_rows_spread
    if rows_spread and rows_spread[0] != rows_spread[1]:
        aggregate.append(
            f"  scored rows per origin ranged {rows_spread[0]} to {rows_spread[1]}, so the "
            "mean over origins and the pooled mean weight the horizons differently"
        )
    if result.distribution_agreement == "disagree":
        aggregate.append(
            "  the two aggregations disagree about beating the baseline: the mean over "
            "origins and the pooled-per-scored-row figure point opposite ways. Quote both "
            "or neither."
        )
    if result.event_agreement == "disagree":
        aggregate.append(
            "  the two aggregations disagree about the target event for the same reason."
        )
    spread = result.brier_spread
    if spread:
        aggregate.append(f"  Brier ranged {_fmt(spread[0])} to {_fmt(spread[1])} across origins")
    return "\n".join(list(lines) + aggregate)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"

"""Probability scoring for held-out reservations.

Accuracy alone is not evidence about a probability model, so the primary measures
are proper scoring rules: the multiclass Brier score and multiclass log loss, each
compared against a training-period prevalence baseline. A number that cannot beat
"predict the base rate" is not a useful forecast however well it classifies.

Every metric is published with the count behind it, and a segment whose count will
not support the claim is labelled rather than quietly averaged in.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from railconfirm.data.preprocessing import INITIAL_STATUS_COLUMN, asof_statuses
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.prediction import PassengerOutcome, PredictionTarget
from railconfirm.domain.status import ParsedStatus, parse_status
from railconfirm.inference.baseline import (
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    HistoricalFrequencyBaseline,
)
from railconfirm.inference.group import (
    compute_group_outcomes,
    compute_queue_dependent_bounds,
)

PROBABILITY_FLOOR = 1e-12
DEFAULT_MIN_SEGMENT_ROWS = 25
RELIABILITY_BINS = 10

TARGET_EVENTS: dict[str, tuple[str, ...]] = {
    PredictionTarget.FINAL_CHART_CNF.value: ("CNF",),
    PredictionTarget.FINAL_CHART_CNF_OR_RAC.value: ("CNF", "RAC"),
}
"""Which outcome classes count as the event for each supported target.

The headline number a user reads is the probability of an event, not of one class:
``final_chart_cnf_or_rac`` is confirmed *or* RAC. Scoring the full distribution
without also scoring that event would leave the product's main claim unmeasured.
"""


@dataclass(frozen=True)
class ReliabilityBin:
    """One predicted-probability band for a single outcome class."""

    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_frequency: float


@dataclass(frozen=True)
class SegmentMetric:
    """Metrics for one slice, always with its count and a low-sample flag."""

    dimension: str
    value: str
    rows: int
    brier: float
    low_sample: bool


@dataclass(frozen=True)
class GroupScorecard:
    """Evaluation of joint group-level predictions on held-out bookings."""

    total_groups: int
    single_passenger_groups: int
    multi_passenger_groups: int
    scored_groups: int
    abstained_groups: int
    brier_all_cnf: float | None
    brier_all_cnf_or_rac: float | None
    brier_at_least_one_wl: float | None
    queue_brier_all_cnf: float | None
    queue_brier_all_cnf_or_rac: float | None
    queue_brier_at_least_one_wl: float | None
    baseline_brier_all_cnf: float | None
    brier_skill_all_cnf: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Scorecard:
    """Everything one evaluation pass produced, ready to serialise."""

    partition: str
    target: str
    rows: int
    scored_rows: int
    abstained_rows: int
    coverage: float
    brier: float | None
    log_loss: float | None
    baseline_brier: float | None
    baseline_log_loss: float | None
    brier_skill: float | None
    event_brier: float | None
    event_log_loss: float | None
    event_baseline_brier: float | None
    event_brier_skill: float | None
    event_reliability: list[ReliabilityBin]
    reliability: dict[str, list[ReliabilityBin]]
    segments: list[SegmentMetric]
    outcome_distribution: dict[str, int]
    min_segment_rows: int
    group: GroupScorecard | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reliability"] = {
            outcome: [asdict(item) for item in bins]
            for outcome, bins in self.reliability.items()
        }
        payload["event_reliability"] = [asdict(item) for item in self.event_reliability]
        payload["group"] = self.group.to_dict() if self.group is not None else None
        return payload

    @property
    def beats_baseline(self) -> bool | None:
        """None when there is nothing to compare, which is not a pass."""
        if self.brier is None or self.baseline_brier is None:
            return None
        return self.brier < self.baseline_brier

    @property
    def event_beats_baseline(self) -> bool | None:
        if self.event_brier is None or self.event_baseline_brier is None:
            return None
        return self.event_brier < self.event_baseline_brier


STRUCTURAL_FIELDS = frozenset(
    {
        "partition",
        "target",
        "rows",
        "scored_rows",
        "abstained_rows",
        "segments",
        "outcome_distribution",
        "min_segment_rows",
        "group",
    }
)
"""Scorecard fields that describe the run rather than a measured probability model."""

METRIC_KEYS = frozenset(name for name in Scorecard.__dataclass_fields__) - STRUCTURAL_FIELDS
"""Every scorecard field the report must define in words.

``railconfirm.training.report.METRIC_DEFINITIONS`` is checked against this set, so a
new metric cannot be published without being explained.
"""


def _outcome_vector(parsed: ParsedStatus) -> dict[str, float]:
    """One-hot over the declared outcome space.

    Anything outside it (censored, unknown) has no label here and the caller must
    exclude the row rather than score it as an all-zeros vector.
    """
    value = parsed.normalized.value
    if value not in OUTCOME_CLASSES:
        return {}
    return {outcome: 1.0 if outcome == value else 0.0 for outcome in OUTCOME_CLASSES}


def _brier_one(hypothesis: Mapping[str, float], truth: Mapping[str, float]) -> float:
    return sum(
        (hypothesis.get(outcome, 0.0) - truth.get(outcome, 0.0)) ** 2
        for outcome in OUTCOME_CLASSES
    )


def _log_loss_one(hypothesis: Mapping[str, float], truth: Mapping[str, float]) -> float:
    total = 0.0
    for outcome in OUTCOME_CLASSES:
        actual = truth.get(outcome, 0.0)
        if actual <= 0.0:
            continue
        predicted = min(1.0, max(PROBABILITY_FLOOR, hypothesis.get(outcome, 0.0)))
        total += actual * math.log(predicted)
    return -total


def _binary_log_loss(predicted: float, observed: float) -> float:
    p = min(1.0 - PROBABILITY_FLOOR, max(PROBABILITY_FLOOR, predicted))
    return -(observed * math.log(p) + (1.0 - observed) * math.log(1.0 - p))


def _event_probability(distribution: Mapping[str, float], event_classes: tuple[str, ...]) -> float:
    """The target's own claim: probability mass on the classes the event covers."""
    return sum(distribution.get(name, 0.0) for name in event_classes)


def _rounded(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _skill(model: float | None, baseline: float | None) -> float | None:
    """Skill against the base rate. None means there is nothing to compare with."""
    if model is None or not baseline:
        return None
    return round(1 - model / baseline, 6)


def _hypothesis_from(outcome: PassengerOutcome) -> dict[str, float]:
    return {
        "CNF": outcome.p_cnf or 0.0,
        "RAC": outcome.p_rac or 0.0,
        "WL": outcome.p_wl or 0.0,
        "CANCELLED": outcome.p_cancelled or 0.0,
        "OTHER": outcome.p_other or 0.0,
    }


def _bands(pairs: list[tuple[float, float]], *, bins: int) -> list[ReliabilityBin]:
    """Bin (predicted, observed) pairs into reliability bands, skipping empty bands.

    This is calibration *description*, not a calibration claim: it shows how observed
    frequency tracks predicted probability, with counts so thin bands are visible.
    """
    rows: list[ReliabilityBin] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        in_band = [
            (predicted, observed)
            for predicted, observed in pairs
            if lower <= predicted <= upper or (index == bins - 1 and predicted == 1.0)
        ]
        if not in_band:
            continue
        count = len(in_band)
        rows.append(
            ReliabilityBin(
                lower=round(lower, 3),
                upper=round(upper, 3),
                count=count,
                mean_predicted=round(sum(p for p, _ in in_band) / count, 4),
                observed_frequency=round(sum(o for _, o in in_band) / count, 4),
            )
        )
    return rows


def _reliability(
    predictions: list[dict[str, float]],
    truths: list[dict[str, float]],
    *,
    bins: int,
) -> dict[str, list[ReliabilityBin]]:
    return {
        outcome: _bands(
            [(prediction[outcome], truth[outcome]) for prediction, truth in zip(predictions, truths, strict=True)],
            bins=bins,
        )
        for outcome in OUTCOME_CLASSES
    }


def _slices(
    row: pd.Series, frame: pd.DataFrame, asof: ParsedStatus
) -> list[tuple[str, str]]:
    """The segments one scored row belongs to.

    Statuses are sliced by normalized category: "GNWL/10" and "RLWL/3" are different
    queues but the same population for scoring, and a per-raw-string slice would
    fragment every metric into ones. Both the booking status and the as-of status are
    reported, because the difference between them is exactly what a cohort-keyed
    mismatch would otherwise hide.
    """
    slices: list[tuple[str, str]] = []
    if INITIAL_STATUS_COLUMN in frame.columns:
        slices.append(
            ("initial_status", parse_status(str(row[INITIAL_STATUS_COLUMN])).normalized.value)
        )
    slices.append(("asof_status", asof.normalized.value))
    for column in ("class_code", "quota_code"):
        if column in frame.columns:
            slices.append((column, str(row[column]).strip().upper()))
    return slices


def score_partition(
    frame: pd.DataFrame,
    estimator: HistoricalFrequencyBaseline,
    *,
    prevalence: Mapping[str, float],
    partition: str = "test",
    target: str = PredictionTarget.FINAL_CHART_CNF.value,
    min_segment_rows: int = DEFAULT_MIN_SEGMENT_ROWS,
    reliability_bins: int = RELIABILITY_BINS,
) -> Scorecard:
    """Score one partition with the estimator that would serve it in production.

    The estimator is the same object inference uses, and the status each row is
    queried with comes from the same :func:`asof_statuses` call the fitter used, so a
    metric computed here cannot describe a code path the product does not run or a
    cohort the table was never keyed by. ``target`` selects which event the headline
    numbers describe; the full distribution is always scored as well.
    """
    if target not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Cannot score target {target!r}: the event it names is not defined. "
            f"Known targets: {sorted(TARGET_EVENTS)}."
        )
    if frame.empty:
        raise DatasetValidationError(f"Cannot score an empty {partition} partition.")
    if "final_chart_status" not in frame.columns:
        raise DatasetValidationError(
            f"The {partition} partition has no 'final_chart_status' column to score against."
        )

    event_classes = TARGET_EVENTS[target]
    statuses = asof_statuses(frame)
    has_groups = "booking_group_id" in frame.columns
    group_members: dict[str, list[tuple[PassengerOutcome | None, str | None]]] = {}
    if has_groups:
        for gid in frame["booking_group_id"]:
            if pd.notna(gid) and str(gid).strip():
                group_members.setdefault(str(gid).strip(), [])

    predictions: list[dict[str, float]] = []
    truths: list[dict[str, float]] = []
    event_pairs: list[tuple[float, float]] = []
    segment_rows: dict[tuple[str, str], list[tuple[float, float]]] = {}
    outcome_counts: dict[str, int] = {}
    abstained = 0
    brier_total = 0.0
    loss_total = 0.0
    event_brier_total = 0.0
    event_loss_total = 0.0
    event_baseline_total = 0.0

    for (_, row), asof in zip(frame.iterrows(), statuses, strict=True):
        gid = (
            str(row["booking_group_id"]).strip()
            if has_groups and pd.notna(row.get("booking_group_id"))
            else None
        )
        truth = _outcome_vector(parse_status(str(row["final_chart_status"])))
        if not truth:
            abstained += 1
            if gid and gid in group_members:
                group_members[gid].append((None, None))
            continue

        outcome = estimator.estimate(
            passenger_id=str(row.get("passenger_record_id", "row")),
            asof_status=asof,
            class_code=str(row.get("class_code", "")),
            quota_code=str(row.get("quota_code", "")),
        )
        observed = max(OUTCOME_CLASSES, key=lambda name: truth.get(name, 0.0))
        if gid and gid in group_members:
            group_members[gid].append(
                (outcome if outcome.is_supported() else None, observed)
            )

        if not outcome.is_supported():
            abstained += 1
            continue

        hypothesis = _hypothesis_from(outcome)
        predictions.append(hypothesis)
        truths.append(truth)
        brier = _brier_one(hypothesis, truth)
        brier_total += brier
        loss_total += _log_loss_one(hypothesis, truth)
        outcome_counts[observed] = outcome_counts.get(observed, 0) + 1

        event_observed = 1.0 if observed in event_classes else 0.0
        event_predicted = _event_probability(hypothesis, event_classes)
        event_pairs.append((event_predicted, event_observed))
        event_brier_total += (event_predicted - event_observed) ** 2
        event_loss_total += _binary_log_loss(event_predicted, event_observed)
        event_baseline_total += (
            _event_probability(prevalence, event_classes) - event_observed
        ) ** 2

        for dimension, value in _slices(row, frame, asof):
            bucket = segment_rows.setdefault((dimension, value), [])
            bucket.append((brier, 1.0))

    scored = len(predictions)
    baseline_brier = None
    baseline_loss = None
    if scored:
        baseline_brier = sum(
            _brier_one(prevalence, truth) for truth in truths
        ) / scored
        baseline_loss = sum(
            _log_loss_one(prevalence, truth) for truth in truths
        ) / scored

    segments = [
        SegmentMetric(
            dimension=dimension,
            value=value,
            rows=len(rows),
            brier=round(sum(item[0] for item in rows) / len(rows), 6),
            low_sample=len(rows) < min_segment_rows,
        )
        for (dimension, value), rows in sorted(segment_rows.items())
    ]

    mean_brier: float | None = brier_total / scored if scored else None
    mean_loss: float | None = loss_total / scored if scored else None
    mean_event_brier: float | None = event_brier_total / scored if scored else None
    mean_event_loss: float | None = event_loss_total / scored if scored else None
    mean_event_baseline: float | None = (
        event_baseline_total / scored if scored else None
    )

    group_card: GroupScorecard | None = None
    if has_groups and group_members:
        total_groups = len(group_members)
        single_passenger_groups = 0
        multi_passenger_groups = 0
        scored_groups = 0
        abstained_groups = 0

        indep_brier_cnf_sum = 0.0
        indep_brier_cnf_rac_sum = 0.0
        indep_brier_wl_sum = 0.0
        queue_brier_cnf_sum = 0.0
        queue_brier_cnf_rac_sum = 0.0
        queue_brier_wl_sum = 0.0
        baseline_brier_cnf_sum = 0.0

        p_prev_event = _event_probability(prevalence, event_classes)

        for _gid, members in group_members.items():
            n_passengers = len(members)
            if n_passengers <= 1:
                single_passenger_groups += 1
                continue
            multi_passenger_groups += 1

            if any(po is None or not po.is_supported() or label is None for po, label in members):
                abstained_groups += 1
                continue

            scored_groups += 1
            po_list = [po for po, _ in members if po is not None]
            labels = [label for _, label in members if label is not None]

            true_all_cnf = 1.0 if all(lbl in event_classes for lbl in labels) else 0.0
            true_all_cnf_or_rac = 1.0 if all(lbl in ("CNF", "RAC") for lbl in labels) else 0.0
            true_at_least_one_wl = 1.0 if any(lbl == "WL" for lbl in labels) else 0.0

            indep = compute_group_outcomes(po_list, method="independence_baseline")
            p_indep_cnf = indep.p_all_cnf if indep and indep.p_all_cnf is not None else 0.0
            p_indep_cnf_rac = indep.p_all_cnf_or_rac if indep and indep.p_all_cnf_or_rac is not None else 0.0
            p_indep_wl = indep.p_at_least_one_wl if indep and indep.p_at_least_one_wl is not None else 0.0

            indep_brier_cnf_sum += (p_indep_cnf - true_all_cnf) ** 2
            indep_brier_cnf_rac_sum += (p_indep_cnf_rac - true_all_cnf_or_rac) ** 2
            indep_brier_wl_sum += (p_indep_wl - true_at_least_one_wl) ** 2

            queue = compute_queue_dependent_bounds(po_list)
            p_queue_cnf = queue.p_all_cnf if queue and queue.p_all_cnf is not None else 0.0
            p_queue_cnf_rac = queue.p_all_cnf_or_rac if queue and queue.p_all_cnf_or_rac is not None else 0.0
            p_queue_wl = queue.p_at_least_one_wl if queue and queue.p_at_least_one_wl is not None else 0.0

            queue_brier_cnf_sum += (p_queue_cnf - true_all_cnf) ** 2
            queue_brier_cnf_rac_sum += (p_queue_cnf_rac - true_all_cnf_or_rac) ** 2
            queue_brier_wl_sum += (p_queue_wl - true_at_least_one_wl) ** 2

            p_base_group = p_prev_event ** n_passengers
            baseline_brier_cnf_sum += (p_base_group - true_all_cnf) ** 2

        mean_indep_cnf = indep_brier_cnf_sum / scored_groups if scored_groups else None
        mean_indep_cnf_rac = indep_brier_cnf_rac_sum / scored_groups if scored_groups else None
        mean_indep_wl = indep_brier_wl_sum / scored_groups if scored_groups else None

        mean_queue_cnf = queue_brier_cnf_sum / scored_groups if scored_groups else None
        mean_queue_cnf_rac = queue_brier_cnf_rac_sum / scored_groups if scored_groups else None
        mean_queue_wl = queue_brier_wl_sum / scored_groups if scored_groups else None

        mean_base_cnf = baseline_brier_cnf_sum / scored_groups if scored_groups else None

        group_card = GroupScorecard(
            total_groups=total_groups,
            single_passenger_groups=single_passenger_groups,
            multi_passenger_groups=multi_passenger_groups,
            scored_groups=scored_groups,
            abstained_groups=abstained_groups,
            brier_all_cnf=_rounded(mean_indep_cnf),
            brier_all_cnf_or_rac=_rounded(mean_indep_cnf_rac),
            brier_at_least_one_wl=_rounded(mean_indep_wl),
            queue_brier_all_cnf=_rounded(mean_queue_cnf),
            queue_brier_all_cnf_or_rac=_rounded(mean_queue_cnf_rac),
            queue_brier_at_least_one_wl=_rounded(mean_queue_wl),
            baseline_brier_all_cnf=_rounded(mean_base_cnf),
            brier_skill_all_cnf=_skill(mean_indep_cnf, mean_base_cnf),
        )

    return Scorecard(
        partition=partition,
        target=target,
        rows=int(len(frame)),
        scored_rows=scored,
        abstained_rows=abstained,
        coverage=round(scored / len(frame), 6) if len(frame) else 0.0,
        brier=_rounded(mean_brier),
        log_loss=_rounded(mean_loss),
        baseline_brier=_rounded(baseline_brier),
        baseline_log_loss=_rounded(baseline_loss),
        brier_skill=_skill(mean_brier, baseline_brier),
        event_brier=_rounded(mean_event_brier),
        event_log_loss=_rounded(mean_event_loss),
        event_baseline_brier=_rounded(mean_event_baseline),
        event_brier_skill=_skill(mean_event_brier, mean_event_baseline),
        event_reliability=_bands(event_pairs, bins=reliability_bins),
        reliability=_reliability(predictions, truths, bins=reliability_bins),
        segments=segments,
        outcome_distribution=dict(sorted(outcome_counts.items())),
        min_segment_rows=min_segment_rows,
        group=group_card,
    )


def build_estimator(
    cohorts: Mapping[tuple[str, str, str], Mapping[str, int]],
    provenance: FrequencyTableProvenance,
    *,
    min_sample_threshold: int,
    laplace_alpha: float,
) -> HistoricalFrequencyBaseline:
    """An estimator configured exactly as the promoted artifact configures it."""
    estimator = HistoricalFrequencyBaseline(
        min_sample_threshold=min_sample_threshold,
        laplace_alpha=laplace_alpha,
    )
    estimator.load_frequency_table(dict(cohorts), provenance)
    return estimator


def evaluation_provenance(
    dataset_id: str,
    sha256: str,
    source_reference: str,
    approval_status: str,
    *,
    is_synthetic: bool,
    mapping_version: str,
    fitted_from: str | None = None,
    fitted_to: str | None = None,
) -> FrequencyTableProvenance:
    """Provenance for an offline scoring run.

    ``evaluation_only`` is set so a synthetic fixture can exercise the metrics code.
    It does not make the numbers meaningful: the report that wraps them records
    ``is_synthetic``, and a served artifact carries no such flag, so nothing here can
    reach a user.
    """
    return FrequencyTableProvenance(
        dataset_id=dataset_id,
        sha256=sha256,
        source_reference=source_reference,
        approval_status=approval_status,
        is_synthetic=is_synthetic,
        mapping_version=mapping_version,
        fitted_from=fitted_from,
        fitted_to=fitted_to,
        evaluation_only=True,
    )

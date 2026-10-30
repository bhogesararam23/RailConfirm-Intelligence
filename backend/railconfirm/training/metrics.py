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
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from railconfirm.data.preprocessing import INITIAL_STATUS_COLUMN, asof_statuses
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.prediction import (
    EVENT_CLASSES_BY_TARGET,
    PassengerOutcome,
    PredictionTarget,
)
from railconfirm.domain.status import ParsedStatus, parse_status
from railconfirm.inference.baseline import (
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    HistoricalFrequencyBaseline,
    ProbabilityEstimator,
)
from railconfirm.inference.calibration import (
    CalibrationSpec,
    apply_calibration,
)
from railconfirm.inference.group import (
    compute_group_outcomes,
    compute_queue_dependent_bounds,
)

PROBABILITY_FLOOR = 1e-12
DEFAULT_MIN_SEGMENT_ROWS = 25
MIN_SEGMENT_CALIBRATION_ROWS = 25
"""Rows a slice needs before its observed-minus-predicted gap can carry a claim.

A cohort of three rows that all confirmed looks like a 33-point miscalibration and means
nothing, so the flag travels with the number and the report is only allowed to speak about
segments that clear it."""
RELIABILITY_BINS = 10

TARGET_EVENTS: dict[str, tuple[str, ...]] = dict(EVENT_CLASSES_BY_TARGET)
"""Which outcome classes count as the event for each supported target.

The headline number a user reads is the probability of an event, not of one class:
``final_chart_cnf_or_rac`` is confirmed *or* RAC. Scoring the full distribution
without also scoring that event would leave the product's main claim unmeasured.

The mapping itself lives in :mod:`railconfirm.domain.prediction`, because serving and
calibration need the same definition and a pipeline module is not the right owner of it.
This name stays because the reports are written against it."""


@dataclass(frozen=True)
class ReliabilityBin:
    """One predicted-probability band for a single outcome class.

    The band is half-open, ``[lower, upper)``, except the last one, which includes 1.0. A
    predicted probability that lands exactly on a boundary therefore belongs to the band it
    opens, and to that band only.
    """

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
class SegmentCalibration:
    """How well one slice's predicted event rate matches what actually happened to it.

    This is the measurement a population-wide calibration layer cannot make for itself: the
    averaged correction can be right while every cohort inside it is wrong in offsetting
    directions. Nothing here fits a per-segment correction — the slope is fitted once for the
    population — so what is published is the gap, its count, and a flag that says whether the
    count can carry the claim."""

    dimension: str
    value: str
    rows: int
    mean_predicted: float
    observed_rate: float
    gap: float
    low_sample: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    segment_calibration: list[SegmentCalibration]
    """Observed minus predicted for each slice, with counts and a low-sample flag.

    A population-wide calibration number can be exactly right while every cohort in it is
    wrong in offsetting directions, so the breakdown is published rather than implied."""
    segments: list[SegmentMetric]
    outcome_distribution: dict[str, int]
    min_segment_rows: int
    calibration_applied: bool = False
    """Whether these scores include the artifact's calibration layer.

    Structural, not a metric: it says which pipeline produced the numbers, and a reader
    comparing a calibrated run against an uncalibrated one is comparing two different
    questions."""
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
        "calibration_applied",
        "group",
    }
)
"""Scorecard fields that describe the run rather than a measured probability model."""

METRIC_KEYS = frozenset(name for name in Scorecard.__dataclass_fields__) - STRUCTURAL_FIELDS
"""Every scorecard field the report must define in words.

``railconfirm.training.report.METRIC_DEFINITIONS`` is checked against this set, so a
new metric cannot be published without being explained.
"""

GROUP_STRUCTURAL_FIELDS = frozenset(
    {
        "total_groups",
        "single_passenger_groups",
        "multi_passenger_groups",
        "scored_groups",
        "abstained_groups",
    }
)
"""Group-scorecard fields that count groups rather than measure a probability model."""

GROUP_METRIC_KEYS = frozenset(GroupScorecard.__dataclass_fields__) - GROUP_STRUCTURAL_FIELDS
"""Every published group figure the report must define in words.

The group block is nested under a structural field, so the top-level check that pairs
``METRIC_KEYS`` with ``METRIC_DEFINITIONS`` never saw it: eight numbers — including three
Brier scores of a *bound* and one baseline whose exponent is the group's own size — were
published with no definition at all."""


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

    Bands are half-open on the upper edge (the last one keeps 1.0), so every row lands in
    exactly one band and the counts sum to the rows scored. Both edges were inclusive, which
    put a predicted probability sitting on a boundary — and a smoothed cohort hits 0.1, 0.2,
    … exactly, often — into the band above and the band below, so a reliability table could
    report two rows for one prediction and an observed frequency computed from it twice.
    """
    rows: list[ReliabilityBin] = []
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        last = index == bins - 1
        in_band = [
            (predicted, observed)
            for predicted, observed in pairs
            if lower <= predicted < upper or (last and predicted == upper)
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


def segment_calibration(
    rows: Sequence[ScoredRow],
    *,
    min_rows: int = MIN_SEGMENT_CALIBRATION_ROWS,
) -> list[SegmentCalibration]:
    """Observed-minus-predicted for every slice, with the count that backs it.

    Only scored rows arrive here, so an abstention contributes no segment: a refused
    prediction has no probability to be misaligned. The values are the ones the request was
    handed, which means a calibrated run reports the gap *after* its correction — the number
    a passenger saw — rather than the table's raw output beside it.
    """
    grouped: dict[tuple[str, str], list[ScoredRow]] = {}
    for row in rows:
        for dimension, value in row.slices:
            grouped.setdefault((dimension, value), []).append(row)

    items: list[SegmentCalibration] = []
    for (dimension, value), members in sorted(grouped.items()):
        count = len(members)
        mean_predicted = round(sum(member.event_predicted for member in members) / count, 6)
        observed_rate = round(sum(member.event_observed for member in members) / count, 6)
        items.append(
            SegmentCalibration(
                dimension=dimension,
                value=value,
                rows=count,
                mean_predicted=mean_predicted,
                observed_rate=observed_rate,
                gap=round(observed_rate - mean_predicted, 6),
                low_sample=count < min_rows,
            )
        )
    return items


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


@dataclass(frozen=True)
class ScoredRow:
    """One held-out reservation, as the estimator answered it.

    Carrying the row through in this shape is what lets calibration be fitted on
    exactly the rows the metrics score: two separate loops over the same frame would
    disagree about which rows abstained, and the fitted curve would then describe a
    different population than the published numbers."""

    hypothesis: dict[str, float]
    truth: dict[str, float]
    observed: str
    event_predicted: float
    event_observed: float
    brier: float
    loss: float
    slices: list[tuple[str, str]]
    position: int = -1
    """Where this row sat in the partition, counting rows that abstained.

    Position, not passenger id: two models asked the same rows in the same order must pair
    the same reservations even when they refuse different ones, and a fixture without
    unique ids still has a stable order. AUC-style pairing on ids would silently drop or
    duplicate rows here.
    """


@dataclass(frozen=True)
class RowScores:
    """Every row one partition holds, scored or not."""

    rows: list[ScoredRow]
    group_members: dict[str, list[tuple[PassengerOutcome | None, str | None]]]
    rows_total: int
    abstained: int


def score_rows(
    frame: pd.DataFrame,
    estimator: ProbabilityEstimator,
    *,
    target: str = PredictionTarget.FINAL_CHART_CNF.value,
    calibration: CalibrationSpec | None = None,
) -> RowScores:
    """Ask the production estimator for every row, and keep what it said.

    ``calibration`` is applied to the hypothesis before any scoring, because the
    number a user is served is the calibrated one: measuring the raw table while
    serving something else would make the evaluation describe a code path the
    product does not run.

    Rows the estimator abstains on are counted, never scored as errors. A group whose
    members abstain still appears in ``group_members`` — a missing member is the fact
    the group score has to report, not a row to drop silently.
    """
    if target not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Cannot score target {target!r}: the event it names is not defined. "
            f"Known targets: {sorted(TARGET_EVENTS)}."
        )
    if frame.empty:
        raise DatasetValidationError("Cannot score an empty partition.")
    if "final_chart_status" not in frame.columns:
        raise DatasetValidationError(
            "This partition has no 'final_chart_status' column to score against."
        )
    if calibration is not None and calibration.target != target:
        # Guarded here as well as in apply_calibration so the failure names the two
        # questions rather than the two event tuples.
        raise DatasetValidationError(
            f"Cannot apply a calibration fitted for {calibration.target!r} while scoring "
            f"{target!r}: the corrected number and the scored number would describe "
            "different claims."
        )

    event_classes = TARGET_EVENTS[target]
    statuses = asof_statuses(frame)
    has_groups = "booking_group_id" in frame.columns
    group_members: dict[str, list[tuple[PassengerOutcome | None, str | None]]] = {}
    if has_groups:
        for gid in frame["booking_group_id"]:
            if pd.notna(gid) and str(gid).strip():
                group_members.setdefault(str(gid).strip(), [])

    rows: list[ScoredRow] = []
    abstained = 0

    for position, ((_, row), asof) in enumerate(
        zip(frame.iterrows(), statuses, strict=True)
    ):
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
            # The same as-of position a served request supplies, taken from the same
            # parsed status the cohort key comes from. Omitting it would score a model
            # that reads positions as if it did not (ADR-0013's rule, one estimator wider).
            asof_position=asof.position,
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
        if calibration is not None:
            hypothesis = apply_calibration(calibration, hypothesis, event_classes)
        brier = _brier_one(hypothesis, truth)
        event_observed = 1.0 if observed in event_classes else 0.0
        rows.append(
            ScoredRow(
                hypothesis=hypothesis,
                truth=truth,
                observed=observed,
                event_predicted=_event_probability(hypothesis, event_classes),
                event_observed=event_observed,
                brier=brier,
                loss=_log_loss_one(hypothesis, truth),
                slices=_slices(row, frame, asof),
                position=position,
            )
        )

    return RowScores(
        rows=rows,
        group_members=group_members,
        rows_total=int(len(frame)),
        abstained=abstained,
    )


def score_partition(
    frame: pd.DataFrame,
    estimator: ProbabilityEstimator,
    *,
    prevalence: Mapping[str, float],
    partition: str = "test",
    target: str = PredictionTarget.FINAL_CHART_CNF.value,
    min_segment_rows: int = DEFAULT_MIN_SEGMENT_ROWS,
    reliability_bins: int = RELIABILITY_BINS,
    calibration: CalibrationSpec | None = None,
    pre_scored: RowScores | None = None,
) -> Scorecard:
    """Score one partition with the estimator that would serve it in production.

    The estimator is the same object inference uses, and the status each row is
    queried with comes from the same :func:`asof_statuses` call the fitter used, so a
    metric computed here cannot describe a code path the product does not run or a
    cohort the table was never keyed by. ``target`` selects which event the headline
    numbers describe; the full distribution is always scored as well.

    ``pre_scored`` takes rows a caller already walked. The comparison harness needs the
    per-row results to pair two models, and scoring the frame twice — once for the rows,
    once for the card — is how aggregates and paired counts drift apart while both look
    right.
    """
    scored_rows = (
        pre_scored
        if pre_scored is not None
        else score_rows(frame, estimator, target=target, calibration=calibration)
    )
    event_classes = TARGET_EVENTS[target]
    rows = scored_rows.rows
    abstained = scored_rows.abstained
    predictions = [row.hypothesis for row in rows]
    truths = [row.truth for row in rows]
    event_pairs = [(row.event_predicted, row.event_observed) for row in rows]

    outcome_counts: dict[str, int] = {}
    for row in rows:
        outcome_counts[row.observed] = outcome_counts.get(row.observed, 0) + 1

    scored = len(rows)
    baseline_brier = None
    baseline_loss = None
    if scored:
        baseline_brier = sum(
            _brier_one(prevalence, truth) for truth in truths
        ) / scored
        baseline_loss = sum(
            _log_loss_one(prevalence, truth) for truth in truths
        ) / scored

    segment_rows: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for row in rows:
        for dimension, value in row.slices:
            segment_rows.setdefault((dimension, value), []).append((row.brier, 1.0))

    segments = [
        SegmentMetric(
            dimension=dimension,
            value=value,
            rows=len(items),
            brier=round(sum(item[0] for item in items) / len(items), 6),
            low_sample=len(items) < min_segment_rows,
        )
        for (dimension, value), items in sorted(segment_rows.items())
    ]

    mean_brier: float | None = (
        sum(row.brier for row in rows) / scored if scored else None
    )
    mean_loss: float | None = (
        sum(row.loss for row in rows) / scored if scored else None
    )
    mean_event_brier: float | None = (
        sum((row.event_predicted - row.event_observed) ** 2 for row in rows) / scored
        if scored
        else None
    )
    mean_event_loss: float | None = (
        sum(_binary_log_loss(row.event_predicted, row.event_observed) for row in rows) / scored
        if scored
        else None
    )
    event_baseline = _event_probability(prevalence, event_classes)
    mean_event_baseline: float | None = (
        sum((event_baseline - row.event_observed) ** 2 for row in rows) / scored
        if scored
        else None
    )

    group_card = _group_scorecard(
        group_members=scored_rows.group_members,
        event_classes=event_classes,
        prevalence=prevalence,
    )

    return Scorecard(
        partition=partition,
        target=target,
        rows=scored_rows.rows_total,
        scored_rows=scored,
        abstained_rows=abstained,
        coverage=round(scored / scored_rows.rows_total, 6) if scored_rows.rows_total else 0.0,
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
        segment_calibration=segment_calibration(
            rows, min_rows=max(min_segment_rows, 1)
        ),
        segments=segments,
        outcome_distribution=dict(sorted(outcome_counts.items())),
        min_segment_rows=min_segment_rows,
        calibration_applied=calibration is not None,
        group=group_card,
    )


def _group_scorecard(
    *,
    group_members: Mapping[str, list[tuple[PassengerOutcome | None, str | None]]],
    event_classes: tuple[str, ...],
    prevalence: Mapping[str, float],
) -> GroupScorecard | None:
    """Score the joint group claims over bookings that were fully observed."""
    if not group_members:
        return None

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

        po_list = [po for po, _ in members if po is not None]
        labels = [label for _, label in members if label is not None]

        # Both methods are asked before anything is scored, and a group that comes back
        # without the figure being scored is an abstention rather than a zero. Reading an
        # absent probability as 0.0 turns a missing number into "certainly did not happen"
        # and then publishes a Brier computed against it — the same substitution ADR-0024
        # removed one layer down, in the group methods themselves.
        indep = compute_group_outcomes(po_list, method="independence_baseline")
        queue = compute_queue_dependent_bounds(po_list)
        if (
            indep is None
            or indep.p_all_cnf is None
            or indep.p_all_cnf_or_rac is None
            or indep.p_at_least_one_wl is None
            or queue is None
            or queue.p_all_cnf is None
            or queue.p_all_cnf_or_rac is None
            or queue.p_at_least_one_wl is None
        ):
            abstained_groups += 1
            continue

        scored_groups += 1
        true_all_cnf = 1.0 if all(lbl in event_classes for lbl in labels) else 0.0
        true_all_cnf_or_rac = 1.0 if all(lbl in ("CNF", "RAC") for lbl in labels) else 0.0
        true_at_least_one_wl = 1.0 if any(lbl == "WL" for lbl in labels) else 0.0

        p_indep_cnf = indep.p_all_cnf
        p_indep_cnf_rac = indep.p_all_cnf_or_rac
        p_indep_wl = indep.p_at_least_one_wl

        indep_brier_cnf_sum += (p_indep_cnf - true_all_cnf) ** 2
        indep_brier_cnf_rac_sum += (p_indep_cnf_rac - true_all_cnf_or_rac) ** 2
        indep_brier_wl_sum += (p_indep_wl - true_at_least_one_wl) ** 2

        p_queue_cnf = queue.p_all_cnf
        p_queue_cnf_rac = queue.p_all_cnf_or_rac
        p_queue_wl = queue.p_at_least_one_wl

        queue_brier_cnf_sum += (p_queue_cnf - true_all_cnf) ** 2
        queue_brier_cnf_rac_sum += (p_queue_cnf_rac - true_all_cnf_or_rac) ** 2
        queue_brier_wl_sum += (p_queue_wl - true_at_least_one_wl) ** 2

        p_base_group = p_prev_event**n_passengers
        baseline_brier_cnf_sum += (p_base_group - true_all_cnf) ** 2

    mean_indep_cnf = indep_brier_cnf_sum / scored_groups if scored_groups else None
    mean_indep_cnf_rac = indep_brier_cnf_rac_sum / scored_groups if scored_groups else None
    mean_indep_wl = indep_brier_wl_sum / scored_groups if scored_groups else None
    mean_queue_cnf = queue_brier_cnf_sum / scored_groups if scored_groups else None
    mean_queue_cnf_rac = queue_brier_cnf_rac_sum / scored_groups if scored_groups else None
    mean_queue_wl = queue_brier_wl_sum / scored_groups if scored_groups else None
    mean_base_cnf = baseline_brier_cnf_sum / scored_groups if scored_groups else None

    return GroupScorecard(
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

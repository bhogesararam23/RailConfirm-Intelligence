"""Reproducible training and evaluation reports.

A report exists so a later reader can answer "what produced this number, and what
was it allowed to see" without re-running anything. It therefore records the dataset
hash, the split boundaries and counts, the exclusions, the feature schema, the
scoring definitions, and the limitations — including the ones that make a headline
number unusable.

Nothing reads the clock: ``generated_on`` is a caller-supplied date, so the same
inputs produce the same report bytes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from railconfirm.data.preprocessing import FEATURE_COLUMNS, SplitResult
from railconfirm.inference.artifacts import ModelArtifactMetadata
from railconfirm.training.calibration import CalibrationEvidence
from railconfirm.training.compare import ModelComparisonResult
from railconfirm.training.decay import FROZEN_EVALUATION_METHOD, FrozenDecayResult
from railconfirm.training.fitter import FitSummary
from railconfirm.training.metrics import TARGET_EVENTS, Scorecard
from railconfirm.training.origins import RollingOriginResult

REPORT_SCHEMA_VERSION = "1.1.0"
"""Raised from 1.0.0 because the calibration block gained ``locked_test_measured`` and
``helps_on_locked_test`` may now be null.

A null is not a false: a locked period on which every row abstained measured nothing about
the correction, and a 1.0.0 reader would have read that null as "did not help". The new key
is what lets a reader tell the two apart; nothing else changed meaning.
"""
ORIGIN_REPORT_SCHEMA_VERSION = "1.1.0"
"""Separate from ``REPORT_SCHEMA_VERSION``: a rolling-origin report describes many
 cutoffs, not one train/validation/test run, and a reader must be able to tell which
 shape the bytes are.

 Raised from 1.0.0 because the aggregate block now publishes a pooled figure per score
 alongside the mean over origins, plus ``scored_rows_spread`` and the two agreement
 verdicts. No existing key changed meaning; the new ones are additive, so a 1.0.0 reader
 is not being reinterpreted, it is being under-informed.
 """

DECAY_REPORT_SCHEMA_VERSION = "1.1.0"
"""Its own version because its payload is one artifact judged repeatedly, which neither
 of the other two shapes describes.

 Raised from 1.0.0 because the summary gained `first_scored_horizon` and
 `last_scored_horizon`, and because `event_brier_drift` and `coverage_drift` are now
 stated to span different sets of horizons.

 A 1.0.0 reader would have read the event drift as "last horizon minus the first" and
 been wrong whenever an earlier horizon abstained. No key was renamed or reinterpreted,
 so a minor bump carries the correction without forcing old reports to be treated as
 suspect.
 """

ORIGIN_AGGREGATE_DEFINITIONS: dict[str, str] = {
    "mean_over_origins": (
        "Unweighted mean of the per-origin scores. Each origin counts once whatever it "
        "scored, so this describes how the fitting procedure behaved across cutoffs — not "
        "per prediction. A horizon with two rows counts as much as one with two thousand."
    ),
    "pooled_over_scored_rows": (
        "Each origin's score weighted by the rows it actually scored, which is the mean "
        "squared error per scored prediction across the whole run. This is the number a "
        "statement about served predictions should rest on."
    ),
}
"""Kept out of ``METRIC_DEFINITIONS`` because only the rolling-origin report has two ways
of aggregating; a single-cutoff or decay report should not define statistics it never
publishes."""


METRIC_DEFINITIONS: dict[str, str] = {
    "brier": (
        "Multiclass Brier score: mean over rows of the summed squared difference "
        "between the predicted distribution and the one-hot observed outcome. Lower "
        "is better; a perfect forecast is 0."
    ),
    "log_loss": (
        "Multiclass cross-entropy: mean negative log probability assigned to the "
        "observed outcome class, floored at 1e-12. Lower is better."
    ),
    "baseline_brier": (
        "The same rows scored against the training-period outcome prevalence "
        "distribution, which is what any model must beat."
    ),
    "baseline_log_loss": (
        "The same rows' cross-entropy against that prevalence distribution."
    ),
    "brier_skill": (
        "1 - brier / baseline_brier. Zero means no better than predicting the base "
        "rate; negative means worse."
    ),
    "coverage": (
        "Share of partition rows the estimator produced a distribution for. Rows it "
        "abstained on are counted separately and never scored as failures."
    ),
    "reliability": (
        "Per-class bands of predicted probability against observed frequency with "
        "counts. Bands are half-open ([lower, upper), the last one including 1.0), so the "
        "counts sum to the rows scored and a prediction on a boundary is counted once. A "
        "description of calibration, not a calibration fit."
    ),
    "event_brier": (
        "Binary Brier score for the target's own event (for final_chart_cnf: the "
        " berth is confirmed; for final_chart_cnf_or_rac: confirmed or RAC), scored "
        "on the summed probability mass the estimator gives those classes."
    ),
    "event_log_loss": (
        "Binary cross-entropy for the target's event, floored at 1e-12."
    ),
    "event_baseline_brier": (
        "The same event scored against the training-period prevalence of that event."
    ),
    "event_brier_skill": (
        "1 - event_brier / event_baseline_brier for the target's event."
    ),
    "event_reliability": (
        "Reliability bands for the target's event probability, with the same half-open "
        "edges as `reliability`."
    ),
    "segment_calibration": (
        "For each slice (class, quota, booked status, as-of status): the mean predicted "
        "event probability over its scored rows, the observed event rate in the same rows, "
        "and `gap` = observed minus predicted, with the row count and a low_sample flag. "
        "Positive gap means the cohort confirmed more often than it was told to. A "
        "population can look aligned while offsetting cohorts are not, which is what these "
        "rows exist to expose; a segment below the row floor carries no claim."
    ),
}


@dataclass
class EvaluationReport:
    """One training-plus-evaluation run, described completely."""

    report_schema_version: str
    generated_on: str
    model_version: str
    target: str
    target_event_classes: list[str]
    dataset: dict[str, Any]
    split: dict[str, Any]
    fit: dict[str, Any]
    features: dict[str, Any]
    metric_definitions: dict[str, str]
    validation: Scorecard
    test: Scorecard | None
    calibration: dict[str, Any] | None = None
    """Before/after evidence for the calibration layer, when the artifact carries one.

    Kept separate from the scorecards because it answers a different question — what the
    correction changed — and the headline validation/test numbers already include it."""
    limitations: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validation"] = self.validation.to_dict()
        payload["test"] = self.test.to_dict() if self.test else None
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def summary(self) -> str:
        lines = [
            "=== Evaluation report ===",
            (
                f"Model {self.model_version} · target {self.target} "
                f"(event: {'/'.join(self.target_event_classes) or 'undefined'}) · "
                f"generated {self.generated_on}"
            ),
            (
                f"Dataset {self.dataset['dataset_id']} "
                f"(sha256 {str(self.dataset['sha256'])[:12]}…, "
                f"{self.dataset['rows']} rows)"
            ),
            "",
            "Split:",
        ]
        for line in self.split["boundaries"]:
            lines.append(f"  {line}")
        lines += [
            "",
            f"Fit: {self.fit['rows_used']} of {self.fit['rows_seen']} training rows used, "
            f"{self.fit['cohort_count']} cohorts",
            *self._feature_lines(),
        ]
        lines += _metric_lines(self.validation)
        if self.test is not None:
            lines += _metric_lines(self.test)
        if self.calibration is not None:
            if self.calibration["locked_test_measured"]:
                verdict = (
                    "helped" if self.calibration["helps_on_locked_test"] else "did not help"
                )
            else:
                verdict = "unknown — the locked period produced no score"
            lines += [
                "",
                (
                    f"Calibration: event Brier validation "
                    f"{self.calibration['validation_event_brier_before']} -> "
                    f"{self.calibration['validation_event_brier_after']}, locked test "
                    f"{self.calibration['test_event_brier_before']} -> "
                    f"{self.calibration['test_event_brier_after']} "
                    f"({verdict} on the locked period)"
                ),
            ]
        elif self.validation.calibration_applied:
            lines += [
                "",
                "Calibration: applied to the numbers above, but no before/after "
                "measurement was supplied, so its effect is unknown here.",
            ]
        lines += ["", "Conclusions:"]
        lines += [f"  - {item}" for item in self.conclusions]
        lines += ["", "Limitations:"]
        lines += [f"  - {item}" for item in self.limitations]
        return "\n".join(lines)

    def _feature_lines(self) -> list[str]:
        """State which status the cohorts are keyed by and what the estimator reads."""
        columns = " + ".join(self.fit["asof_status_columns"]) or "no status column"
        line = (
            f"Cohorts: keyed by {self.features['cohort_semantics']} from {columns}; "
            f"read by the estimator: {', '.join(self.features['used_by_estimator'])}"
        )
        unused = self.features["not_used_by_estimator"]
        if unused:
            line += f"; derived but not read: {', '.join(unused)}"
        return [line]


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def _metric_lines(scorecard: Scorecard) -> list[str]:
    """Summary lines per partition: distribution, event, and group when present."""
    label = f"{scorecard.partition.capitalize()}:"
    gap = " " * (len(label) + 1)
    lines = [
        f"{label} Brier {_fmt(scorecard.brier)} vs baseline "
        f"{_fmt(scorecard.baseline_brier)} · skill {_fmt(scorecard.brier_skill)} "
        f"· coverage {scorecard.coverage:.1%} ({scorecard.scored_rows}/"
        f"{scorecard.rows} rows)",
        f"{gap}event {_fmt(scorecard.event_brier)} vs baseline "
        f"{_fmt(scorecard.event_baseline_brier)} · skill "
        f"{_fmt(scorecard.event_brier_skill)}",
    ]
    if scorecard.group is not None:
        if scorecard.group.multi_passenger_groups > 0:
            lines.append(
                f"{gap}group all-CNF Brier {_fmt(scorecard.group.brier_all_cnf)} (queue bound: "
                f"{_fmt(scorecard.group.queue_brier_all_cnf)}) vs baseline "
                f"{_fmt(scorecard.group.baseline_brier_all_cnf)} "
                f"({scorecard.group.scored_groups}/{scorecard.group.multi_passenger_groups} multi-passenger groups)"
            )
        else:
            lines.append(
                f"{gap}group: {scorecard.group.total_groups} single-passenger bookings "
                "(no multi-passenger groups to score)"
            )
    return lines


def describe_split(split: SplitResult) -> dict[str, Any]:
    return {
        "eligible": split.eligible,
        "date_column": split.date_column,
        "boundaries": [partition.describe() for partition in split.partitions],
        "reasons": list(split.reasons),
    }


def _segment_calibration_line(label: str, scorecard: Scorecard) -> str:
    """Name the widest gap a segment actually has enough rows to support.

    The partition-level score is not evidence about a cohort: two segments wrong in opposite
    directions average to a well-calibrated headline. So the report states the worst
    *informative* segment, and says plainly when there is none.
    """
    informative = [item for item in scorecard.segment_calibration if not item.low_sample]
    if not scorecard.segment_calibration:
        return (
            f"{label}: no segment produced a calibration measurement, because nothing was "
            "scored."
        )
    if not informative:
        return (
            f"{label}: no segment holds {scorecard.min_segment_rows} rows, so subgroup "
            "calibration cannot be claimed in either direction; the gaps are published with "
            "their counts and flagged low_sample."
        )
    worst = max(informative, key=lambda item: abs(item.gap))
    return (
        f"{label}: the widest segment gap is {worst.gap:+.6f} in "
        f"{worst.dimension}={worst.value} over {worst.rows} rows (predicted "
        f"{worst.mean_predicted:.6f}, observed {worst.observed_rate:.6f}); the partition "
        "average can hide cohorts that disagree with it."
    )


def build_report(
    *,
    metadata: ModelArtifactMetadata,
    dataset_id: str,
    dataset_sha256: str,
    dataset_rows: int,
    fit: FitSummary,
    split: SplitResult,
    validation: Scorecard,
    test: Scorecard | None,
    generated_on: str,
    calibration: CalibrationEvidence | None = None,
) -> EvaluationReport:
    """Assemble the report and derive its conclusions from what was measured."""
    limitations = list(metadata.limitations)
    conclusions: list[str] = []
    event_classes = list(TARGET_EVENTS.get(metadata.target, ()))

    for scorecard in (validation, test):
        if scorecard is None:
            continue
        label = scorecard.partition
        if scorecard.target != metadata.target:
            limitations.append(
                f"{label} was scored for target {scorecard.target!r} while the "
                f"artifact declares {metadata.target!r}; the two numbers are not "
                "comparable."
            )
        if scorecard.beats_baseline is None:
            conclusions.append(
                f"{label}: no score computed — the estimator abstained on all "
                f"{scorecard.rows} rows, so nothing was measured."
            )
        elif scorecard.beats_baseline:
            conclusions.append(
                f"{label}: Brier {scorecard.brier} beats the prevalence baseline "
                f"{scorecard.baseline_brier} (skill {scorecard.brier_skill})."
            )
        else:
            conclusions.append(
                f"{label}: Brier {scorecard.brier} does not beat the prevalence "
                f"baseline {scorecard.baseline_brier}; this configuration is not an "
                "improvement on the base rate."
            )
        if scorecard.event_beats_baseline is not None:
            verdict = "beats" if scorecard.event_beats_baseline else "does not beat"
            conclusion = (
                f"{label}: target event {scorecard.target} ({'/'.join(event_classes)}) "
                f"Brier {scorecard.event_brier} {verdict} its prevalence baseline "
                f"{scorecard.event_baseline_brier} (skill "
                f"{scorecard.event_brier_skill})."
            )
            if not scorecard.event_beats_baseline:
                conclusion += " The headline probability is no better than the base rate."
            conclusions.append(conclusion)
        if scorecard.beats_baseline is not None and (
            scorecard.beats_baseline != scorecard.event_beats_baseline
        ):
            conclusions.append(
                f"{label}: the distribution and the target event disagree about beating "
                "the base rate, so neither number alone describes this model."
            )
        if scorecard.coverage < 1.0:
            conclusions.append(
                f"{label}: coverage {scorecard.coverage:.1%}; "
                f"{scorecard.abstained_rows} rows abstained and are excluded from the "
                "scores rather than counted as wrong."
            )
        conclusions.append(_segment_calibration_line(label, scorecard))

    limitations.append(
        "Subgroup calibration is reported as observed-minus-predicted per segment with the "
        "rows behind it, and no per-segment correction is fitted: one slope is applied to "
        "every cohort, so a segment can be misaligned while its partition looks aligned. "
        f"Segments under {validation.min_segment_rows} rows are flagged low_sample and "
        "carry no claim in either direction."
    )

    thin = [
        segment
        for segment in (validation.segments + (test.segments if test else []))
        if segment.low_sample
    ]
    if thin:
        limitations.append(
            f"{len(thin)} segment results rest on fewer than "
            f"{validation.min_segment_rows} rows and are marked low_sample."
        )

    if metadata.calibrated:
        limitations.append(
            "The calibration layer is one slope and intercept fitted on the population as a "
            "whole. Applying it to a segment does not calibrate that segment, so the "
            "per-segment gaps published here are the correction's residual error, not a "
            "claim that it holds cohort by cohort."
        )

    if not metadata.calibrated:
        limitations.append(
            "No calibration was fitted or applied. The reliability tables describe "
            "observed alignment only; they are not evidence that the probabilities "
            "are calibrated."
        )
        if calibration is not None:
            limitations.append(
                "A calibration was measured for this run but the artifact does not "
                "carry one, so the numbers above are the uncorrected ones."
            )
    elif calibration is None:
        limitations.append(
            "The artifact declares a calibration layer but this run carried no "
            "before/after measurement for it, so the effect of that correction is "
            "unknown here — the tables describe the corrected numbers only."
        )
    else:
        if calibration.helps_on_locked_test is None:
            verdict = (
                "unmeasured: the locked period produced no score at all, so the correction's "
                "effect there is unknown and this artifact's calibration rests on the "
                "validation window alone"
            )
        elif calibration.helps_on_locked_test:
            verdict = (
                "an improvement, which is what a locked period has to show before a "
                "correction is trusted"
            )
        else:
            verdict = (
                "no improvement: the gain belonged to the validation window and did "
                "not carry into the locked period, so promotion should weigh this"
            )
        conclusions.append(
            f"Calibration: {calibration.spec.description}. It was embedded because the "
            f"validation event Brier moved {calibration.validation_before.event_brier} -> "
            f"{calibration.validation_after.event_brier}; on the locked test the same "
            f"correction moved {calibration.test_before.event_brier} -> "
            f"{calibration.test_after.event_brier}, which is {verdict}."
        )

    return EvaluationReport(
        report_schema_version=REPORT_SCHEMA_VERSION,
        generated_on=generated_on,
        model_version=metadata.version,
        target=metadata.target,
        target_event_classes=event_classes,
        dataset={
            "dataset_id": dataset_id,
            "sha256": dataset_sha256,
            "rows": dataset_rows,
            "status_mapping_version": metadata.status_mapping_version,
            "data_approval_status": metadata.data_approval_status,
            "is_synthetic": metadata.is_synthetic,
        },
        split=describe_split(split),
        features={
            "columns": list(FEATURE_COLUMNS),
            "used_by_estimator": list(metadata.features_used),
            "not_used_by_estimator": [
                column for column in FEATURE_COLUMNS if column not in metadata.features_used
            ],
            "cohort_semantics": metadata.cohort_semantics,
            "feature_schema_version": metadata.feature_schema_version,
            "availability": (
                "Every feature is derived from the initial status, the as-of status "
                "(current_status when the source recorded one, otherwise "
                "initial_status) and its date. No outcome label, post-chart status "
                "or later observation is available to the estimator."
            ),
        },
        fit=fit.to_dict(),
        metric_definitions=dict(METRIC_DEFINITIONS),
        validation=validation,
        test=test,
        calibration=calibration.to_dict() if calibration else None,
        limitations=limitations,
        conclusions=conclusions,
    )


def write_report(report: EvaluationReport, path: Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    return target


@dataclass
class RollingOriginReport:
    """Every origin measured, the aggregate, and what the spread means."""

    report_schema_version: str
    generated_on: str
    evaluation_method: str
    target: str
    target_event_classes: list[str]
    dataset: dict[str, Any]
    plan: dict[str, Any]
    aggregate: dict[str, Any]
    origins: list[dict[str, Any]]
    metric_definitions: dict[str, str]
    limitations: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def summary(self) -> str:
        lines = [
            "=== Rolling-origin evaluation report ===",
            (
                f"{self.evaluation_method} · target {self.target} "
                f"(event: {'/'.join(self.target_event_classes) or 'undefined'}) · "
                f"generated {self.generated_on}"
            ),
            (
                f"Dataset {self.dataset['dataset_id']} "
                f"(sha256 {str(self.dataset['sha256'])[:12]}…, "
                f"{self.dataset['rows']} rows)"
            ),
            "",
            "Origins:",
        ]
        for origin in self.origins:
            score = origin["score"]
            window = origin["origin"]
            lines.append(
                f"  {window['train_start']}..{window['train_end']} "
                f"({window['train_rows']} rows, {window['train_dates']} dates) -> "
                f"{window['scored_start']}..{window['scored_end']} "
                f"({window['scored_rows']} rows)"
            )
            lines.append(
                f"    Brier {_fmt(score['brier'])} vs {_fmt(score['baseline_brier'])} "
                f"· event {_fmt(score['event_brier'])} vs "
                f"{_fmt(score['event_baseline_brier'])} · coverage "
                f"{score['coverage']:.1%} ({score['scored_rows']}/{score['rows']}), "
                f"{origin['cohorts']} cohorts"
            )
        aggregate = self.aggregate
        lines += [
            "",
            f"Aggregate over scored rows: Brier {_fmt(aggregate['pooled_brier'])} vs "
            f"{_fmt(aggregate['pooled_baseline_brier'])}, event "
            f"{_fmt(aggregate['pooled_event_brier'])} vs "
            f"{_fmt(aggregate['pooled_event_baseline_brier'])}",
            f"Mean over origins (each cutoff counts once): Brier "
            f"{_fmt(aggregate['mean_brier'])} vs "
            f"{_fmt(aggregate['mean_baseline_brier'])}, mean event "
            f"{_fmt(aggregate['mean_event_brier'])} vs "
            f"{_fmt(aggregate['mean_event_baseline_brier'])}",
            (
                f"Origins beating the base rate: "
                f"{aggregate['origins_beating_baseline']}/"
                f"{aggregate['origins_with_scores']} scoring origins (distribution), "
                f"{aggregate['origins_beating_event_baseline']}/"
                f"{aggregate['origins_with_event_scores']} (event)"
            ),
            (
                f"Aggregations vs their own baselines: distribution "
                f"{aggregate['distribution_agreement']}, event "
                f"{aggregate['event_agreement']} (agree means the mean over origins and "
                "the pooled figure reach the same verdict)"
            ),
            "",
            "Conclusions:",
        ]
        lines += [f"  - {item}" for item in self.conclusions]
        lines += ["", "Limitations:"]
        lines += [f"  - {item}" for item in self.limitations]
        return "\n".join(lines)


ORIGIN_EVALUATION_METHOD = "refit-per-origin, score-the-next-horizon"
"""The method line a reader judges the numbers by: the table is refitted each cutoff,
so this measures the fitting procedure over time rather than one frozen artifact."""


def build_origin_report(
    result: RollingOriginResult,
    *,
    dataset_id: str,
    dataset_sha256: str,
    dataset_rows: int,
    status_mapping_version: str,
    data_approval_status: str,
    is_synthetic: bool,
    generated_on: str,
) -> RollingOriginReport:
    """Assemble the origin report and derive its conclusions from what was measured."""
    payload = result.to_dict()
    limitations = [
        "Origins use expanding training windows that overlap each other, so this is not "
        f"{result.origin_count} independent evaluations; no multiplicity correction is "
        "applied and the spread is described, not tested.",
        "Each cutoff refits the cohort table from its own training window, so this "
        "measures the fitting procedure over time rather than one promoted artifact's "
        "decay.",
        "Each origin's prevalence baseline comes from its own training window; the "
        "baselines differ between origins by construction.",
        "No calibration layer is applied here: each origin refits its cohort table and "
        "no correction is fitted per cutoff, so these scores describe the uncorrected "
        "estimator.",
        "No calibration was fitted or applied. Reliability bands describe observed "
        "alignment only.",
        "RailConfirm is an independent research tool and not an official IRCTC service.",
    ]
    if is_synthetic:
        limitations.insert(
            0,
            "Fitted and scored on rows that declare is_synthetic: pipeline verification "
            "only, never evidence about railway behaviour.",
        )

    conclusions = _origin_conclusions(result)
    rows_spread = result.scored_rows_spread
    if rows_spread and rows_spread[0] != rows_spread[1]:
        limitations.append(
            f"Origins scored between {rows_spread[0]} and {rows_spread[1]} rows, so the "
            "mean over origins and the pooled figure are not interchangeable: the first "
            "describes the fitting procedure per cutoff, the second describes per-prediction "
            "performance weighted by how many rows each horizon held."
        )
    return RollingOriginReport(
        report_schema_version=ORIGIN_REPORT_SCHEMA_VERSION,
        generated_on=generated_on,
        evaluation_method=ORIGIN_EVALUATION_METHOD,
        target=result.target,
        target_event_classes=list(TARGET_EVENTS[result.target]),
        dataset={
            "dataset_id": dataset_id,
            "sha256": dataset_sha256,
            "rows": dataset_rows,
            "status_mapping_version": status_mapping_version,
            "data_approval_status": data_approval_status,
            "is_synthetic": is_synthetic,
        },
        plan=payload["plan"],
        aggregate=payload["aggregate"],
        origins=payload["origins"],
        metric_definitions={**METRIC_DEFINITIONS, **ORIGIN_AGGREGATE_DEFINITIONS},
        limitations=limitations,
        conclusions=conclusions,
    )


def _origin_conclusions(result: RollingOriginResult) -> list[str]:
    """Say whether the verdict holds across cutoffs, which is the point of the run."""
    conclusions: list[str] = []
    total = result.origin_count
    distribution_scored = result.origins_with_scores
    event_scored = result.origins_with_event_scores
    silent = total - distribution_scored
    if silent:
        conclusions.append(
            f"{silent} of {total} origins produced no score at all: every row in those "
            "horizons abstained, and an abstention is not a failed forecast."
        )
    if not distribution_scored:
        conclusions.append(
            f"No origin measured anything: all {result.rows_seen} horizon rows abstained, "
            "so this run is evidence about coverage, not about accuracy."
        )
        return conclusions

    beats = result.origins_beating_baseline
    if beats == distribution_scored:
        conclusions.append(
            f"All {distribution_scored} scoring origins beat their own training-period "
            "prevalence baseline; the distribution verdict held across cutoffs."
        )
    elif beats == 0:
        conclusions.append(
            "No scoring origin beat its training-period prevalence baseline; the "
            "distribution verdict did not hold at any cutoff."
        )
    else:
        conclusions.append(
            f"{beats} of {distribution_scored} scoring origins beat their prevalence "
            "baseline, so the distribution verdict is not stable across cutoffs and one "
            "cutoff's number should not be quoted as the result."
        )

    if result.distribution_agreement == "disagree":
        conclusions.append(
            "The two aggregations disagree about the distribution: the mean over origins "
            f"is {result.mean_brier} against a mean baseline {result.mean_baseline_brier}, "
            f"while pooled over the {result.rows_scored} scored rows it is "
            f"{result.pooled_brier} against {result.pooled_baseline_brier}. The horizons "
            "differ in size, so which figure a reader quotes decides the verdict; neither "
            "is published here as *the* result."
        )
    elif result.pooled_brier is not None:
        conclusions.append(
            f"Pooled over the {result.rows_scored} scored rows — the figure a statement "
            f"about served predictions should rest on — Brier is {result.pooled_brier} "
            f"against {result.pooled_baseline_brier}, and it points the same way against "
            "its baseline as the mean over origins."
        )

    event_beats = result.origins_beating_event_baseline
    if event_beats == event_scored:
        conclusions.append(
            f"All {event_scored} origins beat the baseline for the target event "
            f"({'/'.join(TARGET_EVENTS[result.target])})."
        )
    elif event_beats == 0:
        conclusions.append(
            f"No origin beat the baseline for the target event "
            f"({'/'.join(TARGET_EVENTS[result.target])}); the headline probability is "
            "no better than the base rate at any cutoff."
        )
    else:
        conclusions.append(
            f"{event_beats} of {event_scored} origins beat the target-event baseline: "
            "the headline claim holds at some cutoffs and not others."
        )

    if result.event_agreement == "disagree":
        conclusions.append(
            "The two aggregations disagree about the target event too: the mean over "
            f"origins is {result.mean_event_brier} against "
            f"{result.mean_event_baseline_brier}, while pooled over scored rows it is "
            f"{result.pooled_event_brier} against {result.pooled_event_baseline_brier}."
        )

    spread = result.brier_spread
    if spread and spread[1] > spread[0]:
        conclusions.append(
            f"Brier ranged from {spread[0]:.6f} to {spread[1]:.6f} across origins; the "
            "spread is a description of instability, not a tested difference."
        )
    coverage = result.coverage_spread
    if coverage and coverage[0] < 1.0:
        conclusions.append(
            f"Coverage ranged from {coverage[0]:.1%} to {coverage[1]:.1%}: at least one "
            "origin abstained on rows the others scored, and abstentions are excluded "
            "rather than counted as errors."
        )
    return conclusions


def write_origin_report(report: RollingOriginReport, path: Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    return target


DECAY_METRIC_DEFINITIONS: dict[str, str] = {
    **METRIC_DEFINITIONS,
    "prevalence": (
        "The frozen block's outcome shares — the population the artifact was fitted on, "
        "computed once from the dates at or before its declared last fitted date. Every "
        "horizon's baseline derives from this same distribution, because a baseline "
        "recomputed per horizon drifts toward the answer it is judging."
    ),
    "event_brier_drift": (
        "The last horizon that produced a score minus the first that did, in horizon "
        "order — horizons on which every row abstained carry no reading and are named by "
        "`first_scored_horizon`/`last_scored_horizon`, so the two ends of this difference "
        "are dated rather than assumed to be the nearest and furthest windows. Positive "
        "means the frozen table did worse as the calendar moved away from its fitted "
        "period; it is a difference of two measured means, not a tested trend."
    ),
    "coverage_drift": (
        "Last horizon coverage minus the first horizon's. Coverage exists for every "
        "horizon — a horizon that abstained on everything reports 0.0 — so this difference "
        "spans the whole walk, while the event Brier drift may skip horizons that scored "
        "nothing. A fall means the fixed cohort table abstains on more of the later rows — "
        "a statement about the table's reach, not about whether its numbers were right."
    ),
}


@dataclass
class FrozenDecayReport:
    """One artifact, the horizons it was judged on, and what moved between them."""

    report_schema_version: str
    generated_on: str
    evaluation_method: str
    target: str
    target_event_classes: list[str]
    dataset: dict[str, Any]
    artifact: dict[str, Any]
    prevalence: dict[str, float]
    calibration: dict[str, Any] | None
    plan: dict[str, Any]
    summary: dict[str, Any]
    horizons: list[dict[str, Any]]
    metric_definitions: dict[str, str]
    limitations: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def summary_lines(self) -> str:
        lines = [
            "=== Frozen-artifact decay report ===",
            (
                f"{self.evaluation_method} · target {self.target} "
                f"(event: {'/'.join(self.target_event_classes)}) · "
                f"generated {self.generated_on}"
            ),
            (
                f"Artifact {self.artifact['version']} fitted "
                f"{self.artifact['fitted_from']}..{self.artifact['fitted_to']} "
                f"({self.artifact['cohorts']} cohorts, threshold "
                f"{self.artifact['min_sample_threshold']}, laplace "
                f"{self.artifact['laplace_alpha']})"
            ),
            (
                f"Dataset {self.dataset['dataset_id']} (sha256 "
                f"{str(self.dataset['sha256'])[:12]}…, {self.dataset['rows']} rows)"
            ),
            f"Calibration: {self.calibration['method'] if self.calibration else 'none'}",
            "",
            "Horizons:",
        ]
        for horizon in self.horizons:
            score = horizon["score"]
            window = horizon["horizon"]
            lines.append(
                f"  {window['scored_start']}..{window['scored_end']} "
                f"({window['scored_rows']} rows): Brier {_fmt(score['brier'])} vs "
                f"{_fmt(score['baseline_brier'])} · event {_fmt(score['event_brier'])} vs "
                f"{_fmt(score['event_baseline_brier'])} · coverage "
                f"{score['coverage']:.1%} ({score['scored_rows']}/{score['rows']})"
            )
        summary = self.summary
        lines += [
            "",
            (
                f"Drift: event Brier h{summary['first_scored_horizon']} "
                f"{_fmt(summary['first_event_brier'])} -> "
                f"h{summary['last_scored_horizon']} {_fmt(summary['last_event_brier'])} "
                f"({_fmt(summary['event_brier_drift'])}), coverage "
                f"{_fmt(summary['first_coverage'])} -> "
                f"{_fmt(summary['last_coverage'])} ({_fmt(summary['coverage_drift'])})"
            ),
            (
                f"Horizons beating the frozen base rate: "
                f"{summary['horizons_beating_event_baseline']}/"
                f"{summary['horizons_with_event_scores']} (event), "
                f"{summary['horizons_beating_baseline']}/"
                f"{summary['horizons_with_scores']} (distribution)"
            ),
            "",
            "Conclusions:",
        ]
        lines += [f"  - {item}" for item in self.conclusions]
        lines += ["", "Limitations:"]
        lines += [f"  - {item}" for item in self.limitations]
        return "\n".join(lines)


def build_decay_report(
    result: FrozenDecayResult,
    *,
    dataset_id: str,
    dataset_sha256: str,
    dataset_rows: int,
    generated_on: str,
) -> FrozenDecayReport:
    """Assemble the decay report, with conclusions derived from what was measured."""
    payload = result.to_dict()
    limitations = [
        "The cohort table, its smoothing settings, its prevalence baseline and any "
        "calibration layer are the artifact's own and were never refitted, so this "
        "measures one artifact's decay rather than how the fitting procedure behaves.",
        (
            f"The prevalence baseline comes from the {result.prevalence_rows} fittable rows "
            f"this file holds up to the cutoff {result.cutoff}. It is the fitted population "
            "as this file can still show it, not a re-read of the snapshot the artifact was "
            "built from, and a different snapshot would move the reference rather than the "
            "table."
        ),
        (
            f"The {result.horizon_count} horizons are scored by the same frozen table, so "
            "they are not independent evaluations of it, and no multiplicity correction is "
            "applied."
        ),
        (
            "Drift is the difference between the first and last scored horizon means "
            "(coverage, which every horizon reports, spans the whole walk). Horizon row "
            "counts and outcome mixes differ, so a movement here describes these windows and "
            "is not a tested trend in the artifact."
        ),
        (
            "Rows the estimator abstained on are excluded from the scores and counted "
            "separately; a horizon with no score is a coverage fact, not a lost forecast."
        ),
        "RailConfirm is an independent research tool and not an official IRCTC service.",
    ]
    if result.artifact_is_synthetic or result.dataset_is_synthetic:
        limitations.insert(
            0,
            "Fitted and scored on rows that declare is_synthetic: pipeline verification "
            "only, never evidence about railway behaviour.",
        )
    if result.calibration is not None:
        limitations.append(
            f"The artifact's calibration layer ({result.calibration.method}) was fitted on "
            "the period the artifact declares and is applied unchanged to every horizon "
            "here, so drift in the corrected numbers says the correction was fitted to one "
            "window — it does not show the correction is wrong."
        )
    else:
        limitations.append(
            "No calibration layer is applied: the artifact carries none, so these scores "
            "describe the uncorrected estimator."
        )

    return FrozenDecayReport(
        report_schema_version=DECAY_REPORT_SCHEMA_VERSION,
        generated_on=generated_on,
        evaluation_method=FROZEN_EVALUATION_METHOD,
        target=result.target,
        target_event_classes=list(TARGET_EVENTS[result.target]),
        dataset={
            "dataset_id": dataset_id,
            "sha256": dataset_sha256,
            "rows": dataset_rows,
        },
        artifact=payload["artifact"],
        prevalence=payload["prevalence"],
        calibration=payload["calibration"],
        plan=payload["plan"],
        summary=payload["summary"],
        horizons=payload["horizons"],
        metric_definitions=dict(DECAY_METRIC_DEFINITIONS),
        limitations=limitations,
        conclusions=_decay_conclusions(result),
    )


def _decay_conclusions(result: FrozenDecayResult) -> list[str]:
    """What the horizons actually said, in the order they happened."""
    conclusions: list[str] = []
    total = result.horizon_count
    scored = result.horizons_with_scores
    silent = total - scored
    if silent:
        conclusions.append(
            f"{silent} of {total} horizons produced no score at all: every row there "
            "abstained, and an abstention is not a failed forecast."
        )
    if not scored:
        conclusions.append(
            f"No horizon produced a score: all {result.rows_seen} rows across "
            f"{total} horizons abstained, so this run measures the frozen table's reach and "
            "says nothing about its accuracy."
        )
        return conclusions

    first_index = result.first_scored_horizon
    last_index = result.last_scored_horizon
    if scored == 1:
        conclusions.append(
            f"Only horizon {first_index} produced a score: its target event Brier is "
            f"{result.first_event_brier:.6f}, one future window is a single measurement and "
            "not a decay curve, and no drift can be read from it."
        )
    else:
        window_phrase = (
            "in the window nearest the cutoff"
            if first_index == 0
            else f"at horizon {first_index}, not the window nearest the cutoff"
        )
        tail_phrase = (
            "in the furthest"
            if last_index == result.horizon_count - 1
            else f"at horizon {last_index}, not the furthest"
        )
        silent_horizons = [
            score.window.index
            for score in result.scores
            if score.scorecard.event_brier is None
        ]
        caveat = (
            f" Horizon{'s' if len(silent_horizons) > 1 else ''} "
            f"{', '.join(str(index) for index in silent_horizons)} produced no score, so "
            "the two ends of this difference are the two ends that were measured."
            if silent_horizons
            else ""
        )
        conclusions.append(
            f"Across {scored} scored horizons the target event Brier ran from "
            f"{result.first_event_brier:.6f} {window_phrase} to "
            f"{result.last_event_brier:.6f} {tail_phrase}, a drift of "
            f"{result.event_brier_drift:+.6f}.{caveat}"
        )
    spread = result.event_brier_spread
    if spread and spread[1] > spread[0]:
        conclusions.append(
            f"Event Brier ranged {spread[0]:.6f} to {spread[1]:.6f} across horizons; the "
            "spread describes instability against one frozen reference and is not a tested "
            "trend."
        )
    beating = result.horizons_beating_event_baseline
    if beating == result.horizons_with_event_scores:
        conclusions.append(
            f"All {beating} scored horizons beat the frozen prevalence baseline for the "
            f"target event ({'/'.join(TARGET_EVENTS[result.target])})."
        )
    elif beating == 0:
        conclusions.append(
            f"No scored horizon beat the frozen baseline for the target event "
            f"({'/'.join(TARGET_EVENTS[result.target])}): against the population it was "
            "fitted on, this table does not separate the outcomes in any window after it."
        )
    else:
        conclusions.append(
            f"{beating} of {result.horizons_with_event_scores} scored horizons beat the "
            "frozen target-event baseline, so the headline claim holds in some later "
            "windows and not others."
        )
    coverage = result.coverage_drift
    if coverage is not None and coverage < 0:
        conclusions.append(
            f"Coverage fell from {result.first_coverage:.1%} to "
            f"{result.last_coverage:.1%}: the frozen table abstains on more of the later "
            "rows, which is a reach problem before it is an accuracy one."
        )
    elif coverage is not None and coverage > 0:
        conclusions.append(
            f"Coverage rose from {result.first_coverage:.1%} to "
            f"{result.last_coverage:.1%} across horizons."
        )
    return conclusions


def write_decay_report(report: FrozenDecayReport, path: Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    return target


COMPARISON_REPORT_SCHEMA_VERSION = "1.0.0"
"""Its own shape again: this payload compares two models, which neither a single run nor a
temporal walk of one model describes."""

COMPARISON_METRIC_DEFINITIONS: dict[str, str] = {
    **METRIC_DEFINITIONS,
    "brier_delta": (
        "candidate multiclass Brier minus the baseline's on the same rows. Negative means "
        "the candidate improved the full distribution."
    ),
    "event_brier_delta": (
        "candidate event Brier minus the baseline's, on the target event the passenger is "
        "handed. Both deltas must be negative before a candidate is recommended."
    ),
    "log_loss_delta": (
        "candidate multiclass log loss minus the baseline's on the same rows."
    ),
    "coverage_delta": (
        "candidate coverage minus the baseline's. A negative value disqualifies the "
        "candidate however good its scores look, because refusing harder rows can improve "
        "an average without improving an answer."
    ),
    "rows_both_scored": (
        "Rows in the partition that both models answered. Wins, losses and ties are counted "
        "only here; a row one model refused is not a lost forecast."
    ),
    "candidate_wins": (
        "Rows both answered where the candidate's squared error on the target event was "
        "strictly smaller than the baseline's."
    ),
    "candidate_losses": (
        "Rows both answered where the candidate's event error was strictly larger."
    ),
    "ties": (
        "Rows both answered where the two errors were exactly equal. Ties count for neither "
        "model, so a candidate cannot reach a recommendation on them."
    ),
    "only_baseline_scored": (
        "Rows the baseline answered and the candidate abstained on — the reach the candidate "
        "would be giving up."
    ),
    "only_candidate_scored": (
        "Rows the candidate answered and the baseline abstained on."
    ),
    "neither_scored": "Rows in the partition that both models refused.",
    "rows_total": "Rows in the partition, scored by either model or neither.",
    "prevalence": (
        "The one reference distribution both models are scored against: the outcome shares of "
        "the shared training window. Reported because two models compared against different "
        "baselines are not being compared."
    ),
}


@dataclass
class ComparisonReport:
    """Two models, the rows they both answered, and what the locked period decided."""

    report_schema_version: str
    generated_on: str
    evaluation_method: str
    target: str
    target_event_classes: list[str]
    dataset: dict[str, Any]
    baseline: dict[str, Any]
    candidate: dict[str, Any]
    prevalence: dict[str, float]
    partitions: list[dict[str, Any]]
    verdict: dict[str, Any]
    metric_definitions: dict[str, str]
    limitations: list[str] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def summary(self) -> str:
        lines = [
            "=== Model comparison report ===",
            (
                f"{self.evaluation_method} · target {self.target} "
                f"(event: {'/'.join(self.target_event_classes)}) · generated "
                f"{self.generated_on}"
            ),
            (
                f"Baseline {self.baseline['version']} "
                f"({self.baseline['estimator']}) vs candidate "
                f"{self.candidate['version']} ({self.candidate['estimator']})"
            ),
            (
                f"Dataset {self.dataset['dataset_id']} (sha256 "
                f"{str(self.dataset['sha256'])[:12]}…, {self.dataset['rows']} rows)"
            ),
            "",
            "Partitions:",
        ]
        for partition in self.partitions:
            lines.append(f"  {partition['partition']}:")
            for role in ("baseline", "candidate"):
                card = partition[role]
                lines.append(
                    f"    {role:<9} Brier {_fmt(card['brier'])} vs "
                    f"{_fmt(card['baseline_brier'])} · event "
                    f"{_fmt(card['event_brier'])} vs "
                    f"{_fmt(card['event_baseline_brier'])} · coverage "
                    f"{card['coverage']:.1%} ({card['scored_rows']}/{card['rows']})"
                )
            compare = partition["comparison"]
            lines.append(
                f"    deltas: Brier {compare['brier_delta']}, event "
                f"{compare['event_brier_delta']}, coverage {compare['coverage_delta']}"
            )
            lines.append(
                f"    paired: {compare['candidate_wins']} wins, "
                f"{compare['candidate_losses']} losses, {compare['ties']} ties over "
                f"{compare['rows_both_scored']} rows both answered "
                f"({compare['only_baseline_scored']} baseline-only, "
                f"{compare['only_candidate_scored']} candidate-only, "
                f"{compare['neither_scored']} by neither)"
            )
        lines += ["", f"Verdict: {self.verdict['outcome']}", ""]
        lines += [f"  - {reason}" for reason in self.verdict["reasons"]]
        lines += ["", "Conclusions:"]
        lines += [f"  - {item}" for item in self.conclusions]
        lines += ["", "Limitations:"]
        lines += [f"  - {item}" for item in self.limitations]
        return "\n".join(lines)


def build_comparison_report(
    result: ModelComparisonResult,
    *,
    dataset_id: str,
    dataset_sha256: str,
    dataset_rows: int,
    is_synthetic: bool,
    generated_on: str,
) -> ComparisonReport:
    """Assemble the comparison report; every conclusion is derived from measured numbers."""
    payload = result.to_dict()
    limitations = [
        "Both models were scored on the same rows of the same split, against one prevalence "
        "baseline taken from the shared training window. Neither was fitted on the other's "
        "data, and no model saw a row from a later partition.",
        "The verdict reads the locked period only. A candidate that wins the validation "
        "window and loses the locked one is reported as losing, because the validation "
        "window is where candidates are chosen and therefore where they flatter themselves.",
        "No calibration layer is applied unless an artifact already carries one: this "
        "compares fitted tables. Calibrate the winner, then compare again if a calibrated "
        "candidate is to replace an uncalibrated baseline.",
        "One locked period is one measurement. It settles the comparison on these rows and "
        "nothing about stability over time, which is what `decay` and `origins` are for.",
        "Wins and ties are counted on the target event's squared error, because that is the "
        "number a passenger is handed; the distribution deltas are reported beside them and "
        "a candidate must improve both.",
        "RailConfirm is an independent research tool and not an official IRCTC service.",
    ]
    if is_synthetic:
        limitations.insert(
            0,
            "Fitted and scored on rows that declare is_synthetic: this compares two ways of "
            "reading the same made-up queue. Nothing here is evidence about railway "
            "behaviour, in either direction.",
        )

    conclusions = [
        f"Verdict on the locked period: {result.verdict.outcome}.",
        *result.verdict.reasons,
    ]
    for partition in result.partitions:
        if partition.baseline.brier is None or partition.candidate.brier is None:
            conclusions.append(
                f"{partition.partition}: at least one model scored nothing here, so the "
                "comparison is coverage, not accuracy."
            )

    return ComparisonReport(
        report_schema_version=COMPARISON_REPORT_SCHEMA_VERSION,
        generated_on=generated_on,
        evaluation_method=result.method,
        target=result.target,
        target_event_classes=list(TARGET_EVENTS[result.target]),
        dataset={
            "dataset_id": dataset_id,
            "sha256": dataset_sha256,
            "rows": dataset_rows,
        },
        baseline=payload["baseline"],
        candidate=payload["candidate"],
        prevalence=payload["prevalence"],
        partitions=payload["partitions"],
        verdict=payload["verdict"],
        metric_definitions=dict(COMPARISON_METRIC_DEFINITIONS),
        limitations=limitations,
        conclusions=conclusions,
    )


def write_comparison_report(report: ComparisonReport, path: Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    return target
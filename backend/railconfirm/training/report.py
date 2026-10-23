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
from railconfirm.training.fitter import FitSummary
from railconfirm.training.metrics import TARGET_EVENTS, Scorecard
from railconfirm.training.origins import RollingOriginResult

REPORT_SCHEMA_VERSION = "1.0.0"
ORIGIN_REPORT_SCHEMA_VERSION = "1.0.0"
"""Separate from ``REPORT_SCHEMA_VERSION``: a rolling-origin report describes many
cutoffs, not one train/validation/test run, and a reader must be able to tell which
shape the bytes are."""

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
        "counts. A description of calibration, not a calibration fit."
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
        "Reliability bands for the target's event probability."
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
            lines += [
                "",
                (
                    f"Calibration: event Brier validation "
                    f"{self.calibration['validation_event_brier_before']} -> "
                    f"{self.calibration['validation_event_brier_after']}, locked test "
                    f"{self.calibration['test_event_brier_before']} -> "
                    f"{self.calibration['test_event_brier_after']} "
                    f"({'helped' if self.calibration['helps_on_locked_test'] else 'did not help'} "
                    "on the locked period)"
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
        verdict = (
            "an improvement, which is what a locked period has to show before a "
            "correction is trusted"
            if calibration.helps_on_locked_test
            else "no improvement: the gain belonged to the validation window and did "
            "not carry into the locked period, so promotion should weigh this"
        )
        conclusions.append(
            f"Calibration: {calibration.spec.description}. It was embedded because the "
            f"validation event Brier moved {calibration.validation_before.event_brier} -> "
            f"{calibration.validation_after.event_brier}; on the locked test the same "
            f"correction moved {calibration.test_before.event_brier} -> "
            f"{calibration.test_after.event_brier}, which is {verdict}."
        )
        limitations.append(
            "Calibration is measured per partition overall. Subgroup calibration — by "
            "class, quota or booked status — is not evaluated here, and the protocol "
            "forbids claiming calibration inside a subgroup without counts behind it."
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
            f"Aggregate: mean Brier {_fmt(aggregate['mean_brier'])} vs "
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
        metric_definitions=dict(METRIC_DEFINITIONS),
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
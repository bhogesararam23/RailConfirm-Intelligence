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
from railconfirm.training.fitter import FitSummary
from railconfirm.training.metrics import TARGET_EVENTS, Scorecard

REPORT_SCHEMA_VERSION = "1.0.0"

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
        ]
        lines += _metric_lines(self.validation)
        if self.test is not None:
            lines += _metric_lines(self.test)
        lines += ["", "Conclusions:"]
        lines += [f"  - {item}" for item in self.conclusions]
        lines += ["", "Limitations:"]
        lines += [f"  - {item}" for item in self.limitations]
        return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def _metric_lines(scorecard: Scorecard) -> list[str]:
    """Two lines per partition: the full distribution and the target's own event."""
    label = f"{scorecard.partition.capitalize()}:"
    gap = " " * (len(label) + 1)
    return [
        f"{label} Brier {_fmt(scorecard.brier)} vs baseline "
        f"{_fmt(scorecard.baseline_brier)} · skill {_fmt(scorecard.brier_skill)} "
        f"· coverage {scorecard.coverage:.1%} ({scorecard.scored_rows}/"
        f"{scorecard.rows} rows)",
        f"{gap}event {_fmt(scorecard.event_brier)} vs baseline "
        f"{_fmt(scorecard.event_baseline_brier)} · skill "
        f"{_fmt(scorecard.event_brier_skill)}",
    ]


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
            "feature_schema_version": metadata.feature_schema_version,
            "availability": (
                "Every feature is derived from the initial status, the most recent "
                "observation and its date. No outcome label, post-chart status or "
                "later observation is available to the estimator."
            ),
        },
        fit=fit.to_dict(),
        metric_definitions=dict(METRIC_DEFINITIONS),
        validation=validation,
        test=test,
        limitations=limitations,
        conclusions=conclusions,
    )


def write_report(report: EvaluationReport, path: Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    return target

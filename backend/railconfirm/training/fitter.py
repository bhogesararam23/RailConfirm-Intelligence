"""Fitting the historical-frequency baseline from an approved dataset.

This is not a machine-learning model. It is a smoothed contingency table over
cohort cells, and the output says so. Fitting it well matters anyway, because it is
the reference every later model has to beat, and because a table fitted with leakage
in it makes every comparison downstream wrong.

Two rules are enforced here rather than documented and hoped for:

* only the training partition is read, and the split must be eligible;
* the resulting artifact is written with ``promotion = "candidate"``, so fitting
  never activates anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from railconfirm.data.preprocessing import (
    FEATURE_SCHEMA_VERSION,
    SplitResult,
    chronological_split,
)
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.status import (
    MAPPING_VERSION,
    TARGET_ELIGIBLE_STATUSES,
    parse_status,
)
from railconfirm.inference.artifacts import (
    ESTIMATOR_HISTORICAL_FREQUENCY,
    ModelArtifactMetadata,
    write_artifact,
)
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    OUTCOME_CLASSES,
    normalize_frequency_table,
)
from railconfirm.training.dataset import ApprovedDataset

CANDIDATE_PROMOTION = "candidate"
"""A fitted artifact is always a candidate. Promotion is a separate human act."""

# Statuses a row may be *booked* in and still have a final-chart outcome to learn
# from. Anything else is not a queue member and contributes no usable cell.
FITTABLE_INITIAL_STATUSES = TARGET_ELIGIBLE_STATUSES

LABEL_COLUMN = "final_chart_status"
INITIAL_COLUMN = "initial_status"


@dataclass
class FitSummary:
    """What the fit actually consumed, so a report can state it instead of guessing."""

    rows_seen: int = 0
    rows_used: int = 0
    excluded: dict[str, int] = field(default_factory=dict)
    label_distribution: dict[str, int] = field(default_factory=dict)
    cohorts: dict[tuple[str, str, str], dict[str, int]] = field(default_factory=dict)
    window: tuple[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_seen": self.rows_seen,
            "rows_used": self.rows_used,
            "excluded": dict(sorted(self.excluded.items())),
            "label_distribution": dict(sorted(self.label_distribution.items())),
            "cohort_count": len(self.cohorts),
            "training_window": list(self.window) if self.window else None,
        }


def fit_cohorts(train: pd.DataFrame) -> FitSummary:
    """Count outcome labels per (class, quota, initial status) cohort.

    A broad ``CLASS|QUOTA|ALL`` row is fitted alongside the exact cells so the
    estimator's fallback has its own counts rather than borrowing an unrelated
    cohort's.
    """
    for column in (INITIAL_COLUMN, LABEL_COLUMN, "class_code", "quota_code"):
        if column not in train.columns:
            raise DatasetValidationError(f"Fitting needs a '{column}' column.")

    summary = FitSummary(rows_seen=int(len(train)))
    table: dict[tuple[str, str, str], Counter[str]] = {}
    dates: list[str] = []

    ordered = train
    if "journey_date" in train.columns:
        ordered = train.sort_values("journey_date", kind="mergesort")

    for _, row in ordered.iterrows():
        initial = parse_status(str(row[INITIAL_COLUMN]))
        label = parse_status(str(row[LABEL_COLUMN]))

        if initial.normalized not in FITTABLE_INITIAL_STATUSES:
            key = f"initial_status_{initial.normalized.value.lower()}"
            summary.excluded[key] = summary.excluded.get(key, 0) + 1
            continue
        if label.normalized.value not in OUTCOME_CLASSES:
            summary.excluded[f"label_{label.normalized.value.lower()}"] = (
                summary.excluded.get(f"label_{label.normalized.value.lower()}", 0) + 1
            )
            continue

        class_code = str(row["class_code"]).strip().upper()
        quota_code = str(row["quota_code"]).strip().upper()
        exact = (class_code, quota_code, initial.normalized.value)
        broad = (class_code, quota_code, BROAD_COHORT_STATUS)
        table.setdefault(exact, Counter())[label.normalized.value] += 1
        table.setdefault(broad, Counter())[label.normalized.value] += 1
        summary.label_distribution[label.normalized.value] = (
            summary.label_distribution.get(label.normalized.value, 0) + 1
        )
        summary.rows_used += 1
        if "journey_date" in row.index and pd.notna(row["journey_date"]):
            dates.append(str(row["journey_date"]))

    if not table:
        raise DatasetValidationError(
            "No cohorts could be fitted: every training row was excluded. The "
            f"exclusions were {summary.excluded or 'none recorded'}."
        )

    summary.cohorts = {
        cohort: {outcome: counts[outcome] for outcome in OUTCOME_CLASSES if counts[outcome]}
        for cohort, counts in sorted(table.items())
    }
    # Validate through the same gate inference uses, so a fitted table can never be
    # something the estimator would have to reject at request time.
    normalize_frequency_table(summary.cohorts)
    if dates:
        summary.window = (min(dates), max(dates))
    return summary


def prevalence_distribution(labels: dict[str, int]) -> dict[str, float]:
    """Training-period outcome shares, as the comparison a model must beat."""
    total = sum(labels.values())
    if total <= 0:
        raise DatasetValidationError("Cannot compute prevalence from an empty label set.")
    return {outcome: labels.get(outcome, 0) / total for outcome in OUTCOME_CLASSES}


@dataclass(frozen=True)
class FittedBaseline:
    """A fitted cohort table plus the artifact description of where it came from."""

    metadata: ModelArtifactMetadata
    cohorts: dict[tuple[str, str, str], dict[str, int]]
    summary: FitSummary
    split: SplitResult
    prevalence: dict[str, float]


def build_metadata(
    dataset: ApprovedDataset,
    summary: FitSummary,
    *,
    version: str,
    target: str,
    min_sample_threshold: int,
    laplace_alpha: float,
    limitations: tuple[str, ...],
    is_synthetic: bool,
    notes: str | None,
) -> ModelArtifactMetadata:
    """Describe the artifact exactly as far as the evidence allows."""
    return ModelArtifactMetadata(
        version=version,
        target=target,
        estimator=ESTIMATOR_HISTORICAL_FREQUENCY,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        status_mapping_version=MAPPING_VERSION,
        outcome_classes=OUTCOME_CLASSES,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        source_reference=dataset.manifest.source.source_register_entry
        or dataset.manifest.source.publisher,
        data_approval_status=dataset.manifest.decision.decision,
        is_synthetic=is_synthetic,
        min_sample_threshold=min_sample_threshold,
        laplace_alpha=laplace_alpha,
        promotion=CANDIDATE_PROMOTION,
        limitations=limitations,
        trained_from=summary.window[0] if summary.window else None,
        trained_to=summary.window[1] if summary.window else None,
        calibrated=False,
        calibration_method=None,
        notes=notes,
    )


def fit_baseline(
    dataset: ApprovedDataset,
    *,
    version: str,
    target: str = "final_chart_cnf",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    gap_days: int = 0,
    min_sample_threshold: int = 30,
    laplace_alpha: float = 1.0,
    notes: str | None = None,
) -> FittedBaseline:
    """Split chronologically, fit on the training partition only, describe the result.

    Raises when the split cannot hold a future period back: fitting on data with no
    honest holdout left would produce an artifact whose numbers cannot be evaluated.
    """
    split = chronological_split(
        dataset.frame,
        train_frac=train_frac,
        val_frac=val_frac,
        gap_days=gap_days,
    )
    if not split.eligible:
        raise DatasetValidationError(
            "Cannot fit: the chronological split is not eligible.\n  - "
            + "\n  - ".join(split.reasons)
        )

    summary = fit_cohorts(split.train)
    limitations = [
        "Smoothed historical frequencies, not a trained or calibrated model.",
        "Fitted on the training partition only; no validation or test row contributed "
        "to these counts.",
        "RailConfirm is an independent research tool and not an official IRCTC service.",
    ]
    if dataset.is_synthetic:
        limitations.insert(
            0,
            "Fitted from rows that declare is_synthetic: pipeline verification only, "
            "never evidence about railway behaviour.",
        )

    metadata = build_metadata(
        dataset,
        summary,
        version=version,
        target=target,
        min_sample_threshold=min_sample_threshold,
        laplace_alpha=laplace_alpha,
        limitations=tuple(limitations),
        is_synthetic=dataset.is_synthetic,
        notes=notes,
    )
    return FittedBaseline(
        metadata=metadata,
        cohorts=summary.cohorts,
        summary=summary,
        split=split,
        prevalence=prevalence_distribution(summary.label_distribution),
    )


def write_fitted_artifact(fitted: FittedBaseline, path: Path) -> Path:
    """Persist a candidate artifact. It stays unserved until promoted explicitly."""
    return write_artifact(Path(path), fitted.metadata, fitted.cohorts)

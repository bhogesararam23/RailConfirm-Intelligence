"""Reproducible baseline fitting, temporal evaluation and reporting.

Training refuses rather than improvises: an unapproved or unverifiable dataset raises
before any artifact is written, the fitted artifact is always a candidate, and every
report names the split boundaries and the rows that were excluded.
"""

from railconfirm.training.dataset import (
    ApprovedDataset,
    TrainingDataError,
    assert_trainable,
    load_approved_dataset,
)
from railconfirm.training.fitter import (
    CANDIDATE_PROMOTION,
    FitSummary,
    FittedBaseline,
    fit_baseline,
    fit_cohorts,
    prevalence_distribution,
    write_fitted_artifact,
)
from railconfirm.training.metrics import Scorecard, build_estimator, score_partition
from railconfirm.training.origins import (
    OriginScore,
    RollingOriginResult,
    run_rolling_origins,
)
from railconfirm.training.report import (
    EvaluationReport,
    RollingOriginReport,
    build_origin_report,
    build_report,
    write_origin_report,
    write_report,
)

__all__ = [
    "CANDIDATE_PROMOTION",
    "ApprovedDataset",
    "EvaluationReport",
    "FitSummary",
    "FittedBaseline",
    "OriginScore",
    "RollingOriginReport",
    "RollingOriginResult",
    "Scorecard",
    "TrainingDataError",
    "assert_trainable",
    "build_estimator",
    "build_origin_report",
    "build_report",
    "fit_baseline",
    "fit_cohorts",
    "load_approved_dataset",
    "prevalence_distribution",
    "run_rolling_origins",
    "score_partition",
    "write_fitted_artifact",
    "write_origin_report",
    "write_report",
]

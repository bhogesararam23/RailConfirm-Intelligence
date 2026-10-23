"""Training and evaluation command line.

    python -m railconfirm.training fit      --dataset … --manifest … --out models/candidate_v1.json
    python -m railconfirm.training evaluate --dataset … --manifest … --artifact …
    python -m railconfirm.training origins  --dataset … --manifest … --min-train-dates 3
    python -m railconfirm.training decay    --dataset … --manifest … --artifact …

Exit codes: 0 success, 1 refused or failed, 2 usage error.

A successful ``fit`` writes an artifact with ``promotion = "candidate"``. It does not
serve anything: activation needs a human to set ``RAILCONFIRM_ACTIVE_MODEL_VERSION``
and to change the artifact's own promotion field, and the registry refuses either
without the other.

``origins`` evaluates the fitting procedure rather than an artifact: it refits the
cohort table at each cutoff and scores only the horizon that follows, and refuses to
run at all when the data cannot support at least two cutoffs.

``decay`` is the other question: it takes one artifact, freezes its table, its settings
and any calibration layer, and scores each successive horizon after the period it
declares it was fitted on. One horizon past that cutoff is a holdout, so the command
refuses unless the calendar supports at least two.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from railconfirm.data.preprocessing import (
    DEFAULT_HORIZON_DATES,
    DEFAULT_MIN_TRAIN_DATES,
    DEFAULT_STEP_DATES,
    chronological_split,
)
from railconfirm.domain.exceptions import (
    DatasetValidationError,
    FrequencyTableValidationError,
    ModelArtifactError,
)
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import load_artifact
from railconfirm.training.calibration import (
    DEFAULT_MIN_CALIBRATION_ROWS,
    CalibrationEvidence,
    fit_and_measure,
)
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.decay import describe_result as describe_decay
from railconfirm.training.decay import run_frozen_decay
from railconfirm.training.fitter import (
    fit_baseline,
    fit_cohorts,
    prevalence_distribution,
    with_calibration,
    write_fitted_artifact,
)
from railconfirm.training.metrics import (
    TARGET_EVENTS,
    build_estimator,
    evaluation_provenance,
    score_partition,
)
from railconfirm.training.origins import describe_result, run_rolling_origins
from railconfirm.training.report import (
    build_decay_report,
    build_origin_report,
    build_report,
    write_decay_report,
    write_origin_report,
    write_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m railconfirm.training",
        description="Reproducible baseline fitting and temporal evaluation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fit = subparsers.add_parser("fit", help="fit the baseline and write a candidate artifact")
    _add_common(fit)
    fit.add_argument("--version", required=True, help="artifact version identifier")
    fit.add_argument(
        "--target",
        default="final_chart_cnf",
        choices=sorted(TARGET_EVENTS),
        help="target the artifact is fitted for; decides which event is scored",
    )
    fit.add_argument("--out", type=Path, required=True, help="artifact .json path")
    fit.add_argument("--report", type=Path, default=None, help="write the evaluation report here")
    fit.add_argument("--min-sample-threshold", type=int, default=30)
    fit.add_argument("--laplace-alpha", type=float, default=1.0)
    fit.add_argument("--notes", default=None)
    fit.add_argument(
        "--calibrate",
        action="store_true",
        help=(
            "fit a logistic calibration layer on the validation partition and embed it in "
            "the artifact; refuses to write one that does not improve validation"
        ),
    )
    fit.add_argument(
        "--calibrate-min-rows",
        type=int,
        default=DEFAULT_MIN_CALIBRATION_ROWS,
        help="scored validation rows required before a slope and intercept are fitted",
    )
    fit.add_argument("--allow-synthetic-for-testing", action="store_true")

    evaluate = subparsers.add_parser("evaluate", help="score an artifact on held-out partitions")
    _add_common(evaluate)
    evaluate.add_argument("--artifact", type=Path, required=True)
    evaluate.add_argument(
        "--target",
        default="final_chart_cnf",
        choices=sorted(TARGET_EVENTS),
        help="target the artifact was fitted for; decides which event is scored",
    )
    evaluate.add_argument("--report", type=Path, default=None)
    evaluate.add_argument("--allow-synthetic-for-testing", action="store_true")

    origins = subparsers.add_parser(
        "origins",
        help="refit the baseline at each cutoff and score only the horizon after it",
    )
    origins.add_argument("dataset", type=Path)
    origins.add_argument("manifest", type=Path)
    origins.add_argument(
        "--target",
        default="final_chart_cnf",
        choices=sorted(TARGET_EVENTS),
        help="target each origin is scored for",
    )
    origins.add_argument(
        "--min-train-dates",
        type=int,
        default=DEFAULT_MIN_TRAIN_DATES,
        help="dates a training window must hold before it can be scored against",
    )
    origins.add_argument(
        "--horizon-dates",
        type=int,
        default=DEFAULT_HORIZON_DATES,
        help="dates scored after each cutoff",
    )
    origins.add_argument(
        "--step-dates",
        type=int,
        default=DEFAULT_STEP_DATES,
        help="dates the cutoff advances by; must be at least --horizon-dates",
    )
    origins.add_argument("--min-scored-rows", type=int, default=1)
    origins.add_argument("--gap-days", type=int, default=0)
    origins.add_argument("--min-sample-threshold", type=int, default=30)
    origins.add_argument("--laplace-alpha", type=float, default=1.0)
    origins.add_argument("--report", type=Path, default=None)
    origins.add_argument(
        "--generated-on",
        default=None,
        help="YYYY-MM-DD recorded in the report; required so output is reproducible",
    )
    origins.add_argument("--allow-synthetic-for-testing", action="store_true")

    decay = subparsers.add_parser(
        "decay",
        help="score one frozen artifact on each successive horizon, refitting nothing",
    )
    decay.add_argument("dataset", type=Path)
    decay.add_argument("manifest", type=Path)
    decay.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="the artifact whose decay is measured; its fitted period is the cutoff",
    )
    decay.add_argument(
        "--target",
        default="final_chart_cnf",
        choices=sorted(TARGET_EVENTS),
        help="must agree with the target the artifact declares",
    )
    decay.add_argument(
        "--horizon-dates",
        type=int,
        default=DEFAULT_HORIZON_DATES,
        help="dates in each scored horizon",
    )
    decay.add_argument(
        "--step-dates",
        type=int,
        default=DEFAULT_STEP_DATES,
        help="dates the horizon advances by; must be at least --horizon-dates",
    )
    decay.add_argument("--gap-days", type=int, default=0)
    decay.add_argument("--min-scored-rows", type=int, default=1)
    decay.add_argument("--report", type=Path, default=None)
    decay.add_argument(
        "--generated-on",
        default=None,
        help="YYYY-MM-DD recorded in the report; required so output is reproducible",
    )
    decay.add_argument("--allow-synthetic-for-testing", action="store_true")

    return parser


def _add_common(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("dataset", type=Path)
    subparser.add_argument("manifest", type=Path)
    subparser.add_argument("--train-frac", type=float, default=0.70)
    subparser.add_argument("--val-frac", type=float, default=0.15)
    subparser.add_argument(
        "--gap-days",
        type=int,
        default=0,
        help="minimum separation between the training period and the scored period",
    )
    subparser.add_argument(
        "--generated-on",
        default=None,
        help="YYYY-MM-DD recorded in the report; required so output is reproducible",
    )


def _dataset(args: argparse.Namespace):
    return load_approved_dataset(
        args.dataset,
        args.manifest,
        allow_synthetic_for_testing=args.allow_synthetic_for_testing,
    )


def _split(args, frame):
    return chronological_split(
        frame,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
        gap_days=args.gap_days,
    )


def _describe_intake(dataset) -> str:
    """State what validation kept, so a fit never silently rests on dropped rows."""
    report = dataset.report
    kept = f"Validation kept {report.valid_rows} of {report.total_rows} rows"
    if not report.rejected_rows:
        return kept + " (no rejections)."
    reasons = ", ".join(
        f"{reason}={count}" for reason, count in sorted(report.rejection_reasons.items())
    )
    return f"{kept} ({report.rejected_rows} rejected: {reasons})."


def _fit(args: argparse.Namespace) -> int:
    dataset = _dataset(args)
    print(_describe_intake(dataset))
    if dataset.eligibility_relaxed:
        print(
            "Eligibility thresholds were NOT met; fitted only because this is a "
            "labelled synthetic pipeline test."
        )
    fitted = fit_baseline(
        dataset,
        version=args.version,
        target=args.target,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
        gap_days=args.gap_days,
        min_sample_threshold=args.min_sample_threshold,
        laplace_alpha=args.laplace_alpha,
        notes=args.notes,
    )
    calibration: CalibrationEvidence | None = None
    if args.calibrate:
        calibration = fit_and_measure(
            fitted,
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            source_reference=fitted.metadata.source_reference,
            approval_status=fitted.metadata.data_approval_status,
            is_synthetic=dataset.is_synthetic,
            mapping_version=fitted.metadata.status_mapping_version,
            target=args.target,
            min_rows=args.calibrate_min_rows,
        )
        fitted = with_calibration(fitted, calibration.spec)

    written = write_fitted_artifact(fitted, args.out)
    print(f"Wrote candidate artifact {written}")
    print(f"Used {fitted.summary.rows_used} of {fitted.summary.rows_seen} training rows")
    print(f"Cohorts: {len(fitted.cohorts)}")
    if calibration is not None:
        print(f"Calibration: {calibration.spec.description}")
        print(
            f"  validation event Brier {calibration.validation_before.event_brier} -> "
            f"{calibration.validation_after.event_brier}; locked test "
            f"{calibration.test_before.event_brier} -> "
            f"{calibration.test_after.event_brier} "
            f"({'helped' if calibration.helps_on_locked_test else 'did not help'})"
        )
    print("Promotion is 'candidate': nothing is served until it is approved and activated.")

    if args.report is not None:
        provenance = evaluation_provenance(
            dataset.dataset_id,
            dataset.sha256,
            fitted.metadata.source_reference,
            fitted.metadata.data_approval_status,
            is_synthetic=dataset.is_synthetic,
            mapping_version=fitted.metadata.status_mapping_version,
            fitted_from=fitted.metadata.trained_from,
            fitted_to=fitted.metadata.trained_to,
        )
        estimator = build_estimator(
            fitted.cohorts,
            provenance,
            min_sample_threshold=args.min_sample_threshold,
            laplace_alpha=args.laplace_alpha,
        )
        # Scored with the calibration the artifact now carries, so the headline numbers
        # describe the arithmetic a served request would produce.
        validation = score_partition(
            fitted.split.val,
            estimator,
            prevalence=fitted.prevalence,
            partition="validation",
            target=args.target,
            calibration=fitted.metadata.calibration,
        )
        test = score_partition(
            fitted.split.test,
            estimator,
            prevalence=fitted.prevalence,
            partition="test",
            target=args.target,
            calibration=fitted.metadata.calibration,
        )
        report = build_report(
            metadata=fitted.metadata,
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            dataset_rows=dataset.report.total_rows,
            fit=fitted.summary,
            split=fitted.split,
            validation=validation,
            test=test,
            generated_on=_require_generated_on(args),
            calibration=calibration,
        )
        path = write_report(report, args.report)
        print()
        print(report.summary())
        print(f"\nReport written to {path}")
    return 0


def _require_generated_on(args: argparse.Namespace) -> str:
    if not args.generated_on:
        raise DatasetValidationError(
            "--generated-on YYYY-MM-DD is required for a report: a report stamped "
            "with the clock cannot be reproduced byte-for-byte."
        )
    return args.generated_on


def _evaluate(args: argparse.Namespace) -> int:
    dataset = _dataset(args)
    artifact = load_artifact(
        args.artifact,
        expected_version=args.artifact.stem,
        expected_target=args.target,
        max_bytes=4_194_304,
    )
    metadata = artifact.metadata
    split = _split(args, dataset.frame)
    if not split.eligible:
        print("Cannot evaluate: the split is not eligible.", file=sys.stderr)
        for reason in split.reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 1

    # Prevalence comes from the training partition, never from the scored one:
    # a baseline fitted on the answer would flatter itself.
    train_fit = fit_cohorts(split.train)
    prevalence = prevalence_distribution(train_fit.label_distribution)

    provenance = evaluation_provenance(
        dataset.dataset_id,
        dataset.sha256,
        metadata.source_reference,
        metadata.data_approval_status,
        is_synthetic=dataset.is_synthetic,
        mapping_version=metadata.status_mapping_version,
        fitted_from=metadata.trained_from,
        fitted_to=metadata.trained_to,
    )
    estimator = build_estimator(
        artifact.cohorts,
        provenance,
        min_sample_threshold=metadata.min_sample_threshold,
        laplace_alpha=metadata.laplace_alpha,
    )

    # Scored through the artifact's own calibration layer when it declares one: the
    # numbers below have to describe what a served request would emit, not a variant
    # of the model that nothing ever runs.
    validation = score_partition(
        split.val,
        estimator,
        prevalence=prevalence,
        partition="validation",
        target=args.target,
        calibration=metadata.calibration,
    )
    test = score_partition(
        split.test,
        estimator,
        prevalence=prevalence,
        partition="test",
        target=args.target,
        calibration=metadata.calibration,
    )
    applied = (
        f"calibration applied ({metadata.calibration.method})"
        if metadata.calibration is not None
        else "uncalibrated"
    )
    print(
        f"Artifact {metadata.version} · dataset {metadata.dataset_id} · "
        f"target {args.target} · {applied}\n"
        f"  validation Brier {validation.brier} (baseline {validation.baseline_brier}), "
        f"event Brier {validation.event_brier} (baseline {validation.event_baseline_brier})\n"
        f"  test       Brier {test.brier} (baseline {test.baseline_brier}), "
        f"event Brier {test.event_brier} (baseline {test.event_baseline_brier})"
    )
    if args.report is not None:
        report = build_report(
            metadata=metadata,
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            dataset_rows=dataset.report.total_rows,
            fit=train_fit,
            split=split,
            validation=validation,
            test=test,
            generated_on=_require_generated_on(args),
        )
        path = write_report(report, args.report)
        print()
        print(report.summary())
        print(f"\nReport written to {path}")
    return 0


def _origins(args: argparse.Namespace) -> int:
    dataset = _dataset(args)
    print(_describe_intake(dataset))
    if dataset.eligibility_relaxed:
        print(
            "Eligibility thresholds were NOT met; running only because this is a "
            "labelled synthetic pipeline test."
        )
    source = dataset.manifest.source
    result = run_rolling_origins(
        dataset.frame,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        source_reference=source.source_register_entry or source.publisher,
        approval_status=dataset.manifest.decision.decision,
        is_synthetic=dataset.is_synthetic,
        mapping_version=MAPPING_VERSION,
        target=args.target,
        min_sample_threshold=args.min_sample_threshold,
        laplace_alpha=args.laplace_alpha,
        min_train_dates=args.min_train_dates,
        horizon_dates=args.horizon_dates,
        step_dates=args.step_dates,
        gap_days=args.gap_days,
        min_scored_rows=args.min_scored_rows,
    )
    print(describe_result(result))
    if args.report is not None:
        report = build_origin_report(
            result,
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            dataset_rows=dataset.report.total_rows,
            status_mapping_version=MAPPING_VERSION,
            data_approval_status=dataset.manifest.decision.decision,
            is_synthetic=dataset.is_synthetic,
            generated_on=_require_generated_on(args),
        )
        path = write_origin_report(report, args.report)
        print()
        print(report.summary())
        print(f"\nReport written to {path}")
    return 0


def _decay(args: argparse.Namespace) -> int:
    """Score one frozen artifact forward through time, with nothing refitted.

    The cutoff is the artifact's own ``trained_to``, so the dates it was counted from can
    never be scored as if they were evidence about it.
    """
    dataset = _dataset(args)
    print(_describe_intake(dataset))
    if dataset.eligibility_relaxed:
        print(
            "Eligibility thresholds were NOT met; running only because this is a "
            "labelled synthetic pipeline test."
        )
    artifact = load_artifact(
        args.artifact,
        expected_version=args.artifact.stem,
        expected_target=args.target,
        max_bytes=4_194_304,
    )
    result = run_frozen_decay(
        dataset,
        artifact,
        horizon_dates=args.horizon_dates,
        step_dates=args.step_dates,
        gap_days=args.gap_days,
        min_scored_rows=args.min_scored_rows,
    )
    print(describe_decay(result))
    if args.report is not None:
        report = build_decay_report(
            result,
            dataset_id=dataset.dataset_id,
            dataset_sha256=dataset.sha256,
            dataset_rows=dataset.report.total_rows,
            generated_on=_require_generated_on(args),
        )
        path = write_decay_report(report, args.report)
        print()
        print(report.summary_lines())
        print(f"\nReport written to {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"fit": _fit, "evaluate": _evaluate, "origins": _origins, "decay": _decay}
    try:
        return handlers[args.command](args)
    except (
        DatasetValidationError,
        ModelArtifactError,
        FrequencyTableValidationError,
    ) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

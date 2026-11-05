"""Dataset intake command line.

    python -m railconfirm.data validate  <dataset.csv>
    python -m railconfirm.data manifest  <dataset.csv> --dataset-id … --title … --retrieved-on YYYY-MM-DD
    python -m railconfirm.data verify    <manifest.yaml> [<dataset.csv>]

Exit codes: 0 success, 1 a check failed or the input is unusable, 2 usage error.
A non-zero exit from ``validate`` means the file is not technically eligible; it
does not mean the file is disapproved, and it never means it is approved.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from railconfirm.config import REPO_ROOT
from railconfirm.data._io import atomic_write_csv
from railconfirm.data.inspection import (
    FormatType,
    audit_quarantine_directory,
    detect_schema,
    quarantine_dataset,
)
from railconfirm.data.loader import load_dataset_file
from railconfirm.data.longitudinal import (
    create_point_in_time_snapshot,
    load_longitudinal_dataset,
)
from railconfirm.data.longitudinal_validator import validate_longitudinal_dataset
from railconfirm.data.manifest import (
    DEFAULT_MANIFEST_DIR,
    STATUS_VALUES,
    ManifestError,
    generate_manifest,
    manifest_output_path,
    verify_manifest,
    write_manifest,
)
from railconfirm.data.prospective import (
    ProspectiveBatch,
    ReviewStatus,
    export_batch_to_longitudinal,
    generate_prospective_template,
    reconcile_and_regenerate_export,
    review_batch,
    scan_for_personal_data,
    validate_prospective_batch,
    verify_export_lineage,
    withdraw_submission,
)
from railconfirm.data.validator import validate_dataset

DEFAULT_QUARANTINE_DIR = REPO_ROOT / "data" / "quarantine"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m railconfirm.data",
        description="Dataset intake tools: validate, manifest, verify, detect, snapshot, quarantine.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="validate a candidate dataset file (non-zero if not eligible)"
    )
    validate.add_argument("dataset", type=Path)
    validate.add_argument("--json", action="store_true", help="emit the report as JSON")
    validate.add_argument(
        "--max-bytes", type=int, default=None, help="override the intake size limit"
    )

    detect = subparsers.add_parser(
        "detect", help="detect the schema and version of a candidate dataset file"
    )
    detect.add_argument("dataset", type=Path)
    detect.add_argument("--json", action="store_true", help="emit the detection result as JSON")

    snapshot = subparsers.add_parser(
        "snapshot", help="derive a point-in-time flat row training snapshot from longitudinal data"
    )
    snapshot.add_argument("dataset", type=Path, help="path to longitudinal dataset JSON file")
    snapshot.add_argument("output", type=Path, help="path to write the flat CSV interchange file")
    snapshot.add_argument(
        "--as-of-lead-days", type=int, default=None, help="horizon in whole lead days before departure"
    )
    snapshot.add_argument(
        "--as-of-datetime", type=str, default=None, help="exact timezone-aware ISO timestamp cutoff"
    )
    snapshot.add_argument(
        "--allow-censored", action="store_true", help="include censored outcomes in snapshot"
    )

    quarantine = subparsers.add_parser(
        "quarantine", help="quarantine an unapproved or contaminated file with a cryptographic sidecar"
    )
    quarantine.add_argument("dataset", type=Path)
    quarantine.add_argument("--reason", required=True, help="justification for quarantining")
    quarantine.add_argument(
        "--quarantine-dir", type=Path, default=DEFAULT_QUARANTINE_DIR, help="target directory"
    )
    quarantine.add_argument("--operator", default="cli_operator", help="operator name")

    audit_quarantine = subparsers.add_parser(
        "audit-quarantine",
        help="audit quarantine directory for pair consistency, orphaned files, and checksum integrity",
    )
    audit_quarantine.add_argument(
        "--quarantine-dir", type=Path, default=DEFAULT_QUARANTINE_DIR, help="target directory"
    )
    audit_quarantine.add_argument(
        "--purge-orphans", action="store_true", help="remove orphaned data files and sidecars"
    )
    audit_quarantine.add_argument("--json", action="store_true", help="emit result as JSON")

    manifest = subparsers.add_parser("manifest", help="generate a provenance manifest")
    manifest.add_argument("dataset", type=Path)
    manifest.add_argument("--dataset-id", required=True)
    manifest.add_argument("--title", required=True)
    manifest.add_argument(
        "--retrieved-on",
        required=True,
        help="YYYY-MM-DD the data was received, from the source record — not today's date",
    )
    manifest.add_argument("--status", default="candidate", choices=STATUS_VALUES)
    manifest.add_argument(
        "--output", type=Path, default=DEFAULT_MANIFEST_DIR, help="directory to write into"
    )
    manifest.add_argument("--name", default=None, help="manifest file name (must end .yaml)")
    manifest.add_argument("--overwrite", action="store_true")

    verify = subparsers.add_parser(
        "verify", help="verify a manifest, optionally against the dataset file it describes"
    )
    verify.add_argument("manifest", type=Path)
    verify.add_argument("dataset", type=Path, nargs="?")

    prospective = subparsers.add_parser(
        "prospective", help="local-first prospective collection tools: template, scan, audit, review, withdraw, export"
    )
    p_subs = prospective.add_subparsers(dest="prospective_action", required=True)

    p_template = p_subs.add_parser(
        "template", help="generate a safe blank prospective collection batch template"
    )
    p_template.add_argument("output", type=Path, help="path to write template JSON")
    p_template.add_argument(
        "--submissions", type=int, default=2, help="number of template submissions (1 or 2)"
    )
    p_template.add_argument(
        "--multi-passenger", action="store_true", default=True, help="include a multi-passenger booking example"
    )
    p_template.add_argument("--overwrite", action="store_true", help="overwrite existing file")

    p_scan = p_subs.add_parser(
        "scan", help="scan prospective batch for personal data or raw PNRs"
    )
    p_scan.add_argument("batch", type=Path, help="path to prospective batch JSON")
    p_scan.add_argument("--json", action="store_true", help="emit scan diagnostics as JSON")

    p_audit = p_subs.add_parser(
        "audit", help="run comprehensive audit and scientific threshold evaluation on prospective batch"
    )
    p_audit.add_argument("batch", type=Path, help="path to prospective batch JSON")
    p_audit.add_argument("--json", action="store_true", help="emit audit report as JSON")

    p_withdraw = p_subs.add_parser(
        "withdraw", help="record participant consent withdrawal and exclude submission from research"
    )
    p_withdraw.add_argument("batch", type=Path, help="path to prospective batch JSON")
    p_withdraw.add_argument("--submission-id", required=True, help="submission ID to withdraw")
    p_withdraw.add_argument("--reason", required=True, help="justification for withdrawal")
    p_withdraw.add_argument("--operator", required=True, help="operator recording the withdrawal")
    p_withdraw.add_argument(
        "--output",
        type=Path,
        default=None,
        help="destination JSON path (default: update in place)",
    )
    p_withdraw.add_argument(
        "--dry-run",
        action="store_true",
        help="simulate withdrawal without writing changes",
    )

    p_review = p_subs.add_parser("review", help="record human operator review decision")
    p_review.add_argument("batch", type=Path, help="path to prospective batch JSON")
    p_review.add_argument(
        "--action", choices=["approve", "reject", "quarantine", "withdraw"], required=True
    )
    p_review.add_argument("--reviewer", required=True, help="name or ID of human reviewer")
    p_review.add_argument("--rationale", required=True, help="explanation for review decision")
    p_review.add_argument(
        "--submission-id",
        type=str,
        default=None,
        help="optional submission ID to review an individual submission",
    )
    p_review.add_argument(
        "--output",
        type=Path,
        default=None,
        help="destination JSON path (default: update in place)",
    )
    p_review.add_argument(
        "--dry-run",
        action="store_true",
        help="simulate review action without writing changes",
    )

    p_export = p_subs.add_parser(
        "export", help="export approved prospective batch to longitudinal dataset"
    )
    p_export.add_argument("batch", type=Path, help="path to prospective batch JSON")
    p_export.add_argument("output", type=Path, help="path to write longitudinal dataset JSON")
    p_export.add_argument("--dataset-id", required=True, help="dataset ID for exported dataset")
    p_export.add_argument("--source-id", required=True, help="source identifier")
    p_export.add_argument(
        "--allow-partial",
        action="store_true",
        help="export approved submissions even if batch contains unapproved submissions",
    )
    p_export.add_argument(
        "--overwrite",
        action="store_true",
        help="allow overwriting target longitudinal dataset if it already exists",
    )
    p_export.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and simulate export without writing output dataset to disk",
    )

    p_verify_export = p_subs.add_parser(
        "verify-export",
        help="verify that a longitudinal export dataset is in sync with its source batch",
    )
    p_verify_export.add_argument("batch", type=Path, help="path to source prospective batch JSON")
    p_verify_export.add_argument("dataset", type=Path, help="path to exported longitudinal dataset JSON")
    p_verify_export.add_argument("--json", action="store_true", help="emit lineage report as JSON")

    p_reconcile = p_subs.add_parser(
        "reconcile",
        help="reconcile export with current batch, purging withdrawn or unapproved records",
    )
    p_reconcile.add_argument("batch", type=Path, help="path to source prospective batch JSON")
    p_reconcile.add_argument("dataset", type=Path, help="path to current exported longitudinal dataset JSON")
    p_reconcile.add_argument(
        "--output",
        type=Path,
        default=None,
        help="destination JSON path (default: overwrite dataset in place)",
    )
    p_reconcile.add_argument(
        "--overwrite",
        action="store_true",
        help="allow overwriting target export file",
    )
    p_reconcile.add_argument(
        "--dry-run",
        action="store_true",
        help="check reconciliation needs without writing updated export to disk",
    )

    p_rehearsal = p_subs.add_parser(
        "rehearsal",
        help="run the deterministic offline synthetic prospective-lifecycle rehearsal",
    )
    p_rehearsal.add_argument(
        "outdir",
        type=Path,
        help="isolated directory to write rehearsal artifacts and reports into",
    )
    p_rehearsal.add_argument(
        "--salt",
        default=None,
        help="override the deterministic synthetic pseudonymisation salt",
    )
    p_rehearsal.add_argument(
        "--timestamp",
        default=None,
        help="ISO-8601 timezone-aware run timestamp override (default: fixed synthetic value)",
    )
    p_rehearsal.add_argument(
        "--json",
        action="store_true",
        help="emit the rehearsal report as machine-readable JSON",
    )

    return parser


def _validate(args: argparse.Namespace) -> int:
    if not args.dataset.is_file():
        print(f"Cannot read dataset: file not found {args.dataset}", file=sys.stderr)
        return 1

    detection = detect_schema(args.dataset)
    if detection.format_type == FormatType.LONGITUDINAL:
        try:
            long_ds = load_longitudinal_dataset(args.dataset)
        except Exception as exc:
            print(f"Cannot read longitudinal dataset: {exc}", file=sys.stderr)
            return 1
        report = validate_longitudinal_dataset(long_ds)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str))
        else:
            print(f"Dataset ID: {report.dataset_id} (schema v{report.schema_version})")
            print(f"Valid: {'yes' if report.is_valid else 'no'}")
            if report.metrics:
                m = report.metrics
                print(
                    f"Journeys: {m.total_journeys}, Groups: {m.total_booking_groups}, "
                    f"Passengers: {m.total_passengers}, Observations: {m.total_observations}"
                )
                print(f"Censored: {m.censored_count} ({m.censored_percentage}%)")
            if report.errors:
                print("Errors:")
                for err in report.errors:
                    print(f"  - {err}")
            if report.warnings:
                print("Warnings:")
                for w in report.warnings:
                    print(f"  - {w}")
        return 0 if report.is_valid else 1

    if detection.format_type == FormatType.PROSPECTIVE_BATCH:
        try:
            batch = ProspectiveBatch.load(args.dataset)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        p_report = validate_prospective_batch(batch)
        if args.json:
            print(json.dumps(p_report.to_dict(), indent=2, sort_keys=True, default=str))
        else:
            print(p_report.summary())
        return 0 if p_report.is_valid else 1

    kwargs = {} if args.max_bytes is None else {"max_bytes": args.max_bytes}
    try:
        frame = load_dataset_file(args.dataset, **kwargs)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Cannot read dataset: {exc}", file=sys.stderr)
        return 1
    row_report = validate_dataset(frame, source_name=str(args.dataset))
    if args.json:
        print(json.dumps(row_report.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        print(row_report.summary())
    return 0 if row_report.technically_eligible else 1


def _detect(args: argparse.Namespace) -> int:
    res = detect_schema(args.dataset)
    if args.json:
        print(json.dumps(res.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"File: {res.file_path}")
        print(f"Format: {res.format_type.value}")
        print(f"Schema Version: {res.schema_version or 'unknown'}")
        print(f"Records/Rows: {res.record_count}")
        print(f"SHA-256: {res.sha256}")
        print(f"Valid Structure: {'yes' if res.is_valid_structure else 'no'}")
        if res.missing_columns:
            print(f"Missing Required Columns: {res.missing_columns}")
        if res.diagnostics:
            print("Diagnostics:")
            for d in res.diagnostics:
                print(f"  - {d}")
    return 0 if res.is_valid_structure else 1


def _snapshot(args: argparse.Namespace) -> int:
    try:
        long_ds = load_longitudinal_dataset(args.dataset)
    except Exception as exc:
        print(f"Cannot read longitudinal dataset: {exc}", file=sys.stderr)
        return 1

    as_of_dt = None
    if args.as_of_datetime:
        try:
            as_of_dt = datetime.fromisoformat(args.as_of_datetime)
        except Exception as exc:
            print(f"Invalid --as-of-datetime timestamp: {exc}", file=sys.stderr)
            return 1

    try:
        snap_res = create_point_in_time_snapshot(
            long_ds,
            as_of_lead_days=args.as_of_lead_days,
            as_of_datetime=as_of_dt,
            allow_censored=args.allow_censored,
        )
    except Exception as exc:
        print(f"Snapshot conversion failed: {exc}", file=sys.stderr)
        return 1

    try:
        atomic_write_csv(args.output, snap_res.frame, index=False)
    except Exception as exc:
        print(f"Snapshot write failed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated snapshot CSV with {len(snap_res.frame)} rows at {args.output}")
    print(f"Included passengers: {snap_res.rows_emitted}/{snap_res.total_passengers_considered}")
    print(f"Excluded unobserved: {snap_res.rows_skipped_no_observation}, Excluded censored: {snap_res.rows_skipped_censored}")
    return 0


def _quarantine(args: argparse.Namespace) -> int:
    try:
        q_path = quarantine_dataset(
            args.dataset,
            args.quarantine_dir,
            reason=args.reason,
            operator=args.operator,
        )
    except Exception as exc:
        print(f"Quarantine action failed: {exc}", file=sys.stderr)
        return 1

    sidecar = q_path.parent / f"{q_path.name}.quarantine.json"
    print(f"Quarantined dataset: {q_path}")
    print(f"Sidecar cryptographic report: {sidecar}")
    return 0


def _audit_quarantine(args: argparse.Namespace) -> int:
    report = audit_quarantine_directory(
        args.quarantine_dir,
        purge_orphans=args.purge_orphans,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Quarantine directory: {args.quarantine_dir}")
        print(f"Total data files:     {report['total_data_files']}")
        print(f"Total sidecars:       {report['total_sidecars']}")
        print(f"Valid pairs:          {len(report['valid_pairs'])}")
        print(f"Orphaned data files:  {len(report['orphaned_data_files'])}")
        print(f"Orphaned sidecars:    {len(report['orphaned_sidecars'])}")
        print(f"Checksum mismatches:  {len(report['checksum_mismatches'])}")
        if args.purge_orphans:
            print(f"Purged files:         {len(report['purged_files'])}")
    has_issues = (
        len(report["orphaned_data_files"]) > 0
        or len(report["orphaned_sidecars"]) > 0
        or len(report["checksum_mismatches"]) > 0
    )
    return 1 if (has_issues and not args.purge_orphans) else 0


def _manifest(args: argparse.Namespace) -> int:
    try:
        manifest = generate_manifest(
            args.dataset,
            dataset_id=args.dataset_id,
            title=args.title,
            retrieved_on=args.retrieved_on,
            status=args.status,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Cannot build manifest: {exc}", file=sys.stderr)
        return 1
    try:
        target = manifest_output_path(args.name or f"{args.dataset_id}.yaml", args.output)
        written = write_manifest(manifest, target, overwrite=args.overwrite)
    except ManifestError as exc:
        print(f"Cannot write manifest: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {written}")
    print(f"Manifest digest {manifest.digest()}")
    print(
        f"Records {manifest.coverage.row_count} rows, status {manifest.status}, "
        f"decision {manifest.decision.decision}. Approval is a human step."
    )
    return 0


def _verify(args: argparse.Namespace) -> int:
    try:
        result = verify_manifest(args.manifest, args.dataset)
    except ManifestError as exc:
        print(f"Manifest invalid: {exc}", file=sys.stderr)
        return 1
    print(result.summary())
    return 0 if result.ok else 1


def _prospective(args: argparse.Namespace) -> int:
    if args.prospective_action == "template":
        try:
            generated = generate_prospective_template(
                args.output,
                submission_count=args.submissions,
                multi_passenger=args.multi_passenger,
                overwrite=args.overwrite,
            )
        except Exception as exc:
            print(f"Cannot generate template: {exc}", file=sys.stderr)
            return 1
        print(f"Generated clean prospective batch template at {generated}")
        return 0

    if args.prospective_action == "audit":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        report = validate_prospective_batch(batch)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str))
        else:
            print(report.summary())
        return 0 if report.is_valid else 1

    if args.prospective_action == "withdraw":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        try:
            updated_sub = withdraw_submission(
                batch,
                submission_id=args.submission_id,
                reason=args.reason,
                operator=args.operator,
            )
        except Exception as exc:
            print(f"Withdrawal action failed: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            print(
                f"[DRY-RUN] Simulated consent withdrawal for submission '{updated_sub.submission_id}'. "
                "Review status would become WITHDRAWN. No files modified."
            )
            return 0

        out_path = args.output if args.output else args.batch
        batch.save(out_path)
        print(
            f"Successfully recorded consent withdrawal for submission '{updated_sub.submission_id}'. "
            f"Review status: WITHDRAWN. Saved to {out_path}"
        )
        return 0

    if args.prospective_action == "scan":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        violations = scan_for_personal_data(batch.to_dict())
        if args.json:
            print(
                json.dumps(
                    {
                        "batch_id": batch.batch_id,
                        "clean": len(violations) == 0,
                        "violations": violations,
                    },
                    indent=2,
                )
            )
        else:
            if violations:
                print(
                    f"PII Scan FAILED: {len(violations)} personal data pattern(s) detected:"
                )
                for v in violations:
                    print(f"  - {v}")
            else:
                print(
                    f"PII Scan PASSED: prospective batch '{batch.batch_id}' contains no personal data patterns."
                )
        return 0 if not violations else 1

    if args.prospective_action == "review":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1

        action_map = {
            "approve": ReviewStatus.APPROVED,
            "reject": ReviewStatus.REJECTED,
            "quarantine": ReviewStatus.QUARANTINED,
            "withdraw": ReviewStatus.WITHDRAWN,
        }
        target_action = action_map[args.action]

        try:
            review_batch(
                batch,
                action=target_action,
                reviewer=args.reviewer,
                rationale=args.rationale,
                submission_id=args.submission_id,
            )
        except Exception as exc:
            print(f"Review action failed: {exc}", file=sys.stderr)
            return 1

        target_desc = f"submission '{args.submission_id}'" if args.submission_id else f"batch '{batch.batch_id}'"
        if args.dry_run:
            print(
                f"[DRY-RUN] Simulated review status '{target_action.value}' to {target_desc}. "
                "No files modified."
            )
            return 0

        out_path = args.output if args.output else args.batch
        batch.save(out_path)
        print(
            f"Applied review status '{target_action.value}' to {target_desc}. Saved to {out_path}"
        )
        return 0

    if args.prospective_action == "verify-export":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        try:
            long_ds = load_longitudinal_dataset(args.dataset)
        except Exception as exc:
            print(f"Cannot read longitudinal dataset: {exc}", file=sys.stderr)
            return 1

        lineage_report = verify_export_lineage(batch, long_ds)
        if args.json:
            print(json.dumps(asdict(lineage_report), indent=2, sort_keys=True, default=str))
        else:
            print(lineage_report.summary())
        return 0 if lineage_report.is_synced else 1

    if args.prospective_action == "reconcile":
        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1
        try:
            long_ds = load_longitudinal_dataset(args.dataset)
        except Exception as exc:
            print(f"Cannot read longitudinal dataset: {exc}", file=sys.stderr)
            return 1

        target_out = args.output if args.output else args.dataset
        if target_out.is_file() and not args.overwrite and not args.dry_run and target_out.resolve() != args.dataset.resolve():
            print(
                f"Reconcile failed: target file already exists at {target_out}. Pass --overwrite to replace.",
                file=sys.stderr,
            )
            return 1

        pre_report = verify_export_lineage(batch, long_ds)
        if pre_report.is_synced:
            print(
                f"Export '{long_ds.dataset_id}' is already in sync with batch '{batch.batch_id}'. "
                "No reconciliation needed."
            )
            return 0

        if args.dry_run:
            print(
                f"[DRY-RUN] Reconciliation needed for '{long_ds.dataset_id}': "
                f"{len(pre_report.withdrawn_groups_present)} withdrawn group(s) and "
                f"{len(pre_report.unapproved_groups_present)} unapproved group(s) would be purged. "
                f"Target: {target_out}. No files modified."
            )
            return 0

        try:
            reconciled_ds, lineage_report = reconcile_and_regenerate_export(
                batch,
                long_ds,
                target_out,
                overwrite=True,
            )
        except Exception as exc:
            print(f"Reconciliation failed: {exc}", file=sys.stderr)
            return 1

        print(
            f"Successfully reconciled export: {len(reconciled_ds.booking_groups)} booking groups written to {target_out}. "
            f"Lineage status: {lineage_report.status.value}."
        )
        return 0 if lineage_report.is_synced else 1

    if args.prospective_action == "export":
        if args.output.is_file() and not args.overwrite and not args.dry_run:
            print(
                f"Export failed: target file already exists at {args.output}. "
                "Pass --overwrite to allow replacing it.",
                file=sys.stderr,
            )
            return 1

        try:
            batch = ProspectiveBatch.load(args.batch)
        except Exception as exc:
            print(f"Cannot read prospective batch: {exc}", file=sys.stderr)
            return 1

        try:
            long_ds = export_batch_to_longitudinal(
                batch,
                dataset_id=args.dataset_id,
                source_id=args.source_id,
                require_all_approved=not args.allow_partial,
            )
        except Exception as exc:
            print(f"Export failed: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            print(
                f"[DRY-RUN] Export simulated successfully: {len(long_ds.booking_groups)} booking groups, "
                f"{len(long_ds.journeys)} journeys would be written to {args.output}."
            )
            return 0

        args.output.parent.mkdir(parents=True, exist_ok=True)
        long_ds.save(args.output)
        print(
            f"Exported {len(long_ds.booking_groups)} booking groups to longitudinal dataset at {args.output}"
        )
        return 0

    if args.prospective_action == "rehearsal":
        from railconfirm.data.rehearsal import run_prospective_rehearsal
        from railconfirm.domain.exceptions import DatasetValidationError, SecurityError

        run_timestamp = None
        if args.timestamp:
            try:
                run_timestamp = datetime.fromisoformat(args.timestamp)
            except ValueError as exc:
                print(f"Invalid --timestamp: {exc}", file=sys.stderr)
                return 1
            if run_timestamp.tzinfo is None:
                print(
                    "--timestamp must include a timezone offset, e.g. 2026-05-01T12:00:00+00:00.",
                    file=sys.stderr,
                )
                return 1

        try:
            rehearsal_report = run_prospective_rehearsal(
                args.outdir, salt=args.salt, run_timestamp=run_timestamp
            )
        except (DatasetValidationError, SecurityError) as exc:
            print(f"Rehearsal could not start: {exc}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(rehearsal_report.to_dict(), indent=2, sort_keys=True, default=str))
        else:
            print(rehearsal_report.summary())
        return 0 if rehearsal_report.software_rehearsal_passed else 1

    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "validate": _validate,
        "manifest": _manifest,
        "verify": _verify,
        "detect": _detect,
        "snapshot": _snapshot,
        "quarantine": _quarantine,
        "audit-quarantine": _audit_quarantine,
        "prospective": _prospective,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

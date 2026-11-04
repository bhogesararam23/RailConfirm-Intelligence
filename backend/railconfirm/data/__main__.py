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
from datetime import datetime
from pathlib import Path

from railconfirm.config import REPO_ROOT
from railconfirm.data.inspection import (
    FormatType,
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
                print(f"Journeys: {m.total_journeys}, Groups: {m.total_booking_groups}, Passengers: {m.total_passengers}, Observations: {m.total_observations}")
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    snap_res.frame.to_csv(args.output, index=False)
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "validate": _validate,
        "manifest": _manifest,
        "verify": _verify,
        "detect": _detect,
        "snapshot": _snapshot,
        "quarantine": _quarantine,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

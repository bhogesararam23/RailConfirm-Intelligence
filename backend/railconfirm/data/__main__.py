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
from pathlib import Path

from railconfirm.data.loader import load_dataset_file
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m railconfirm.data",
        description="Dataset intake tools: validate, manifest, verify.",
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
    kwargs = {} if args.max_bytes is None else {"max_bytes": args.max_bytes}
    try:
        frame = load_dataset_file(args.dataset, **kwargs)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Cannot read dataset: {exc}", file=sys.stderr)
        return 1
    report = validate_dataset(frame, source_name=str(args.dataset))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str))
    else:
        print(report.summary())
    return 0 if report.technically_eligible else 1


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
    handlers = {"validate": _validate, "manifest": _manifest, "verify": _verify}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Dataset inspection, automatic schema detection, and quarantine workflow.

Inspects incoming candidate dataset files, determines their schema and version:
- Longitudinal observation contract (v2.0.0)
- Flat row training interchange (v1.0.0 / v1.1.0)
- Prospective collection batch format (v1.0.0)
- Unknown or malformed tabular / JSON files

When a dataset fails technical, integrity, or privacy checks, routes it into a
quarantine directory with a structured cryptographic sidecar report.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from railconfirm.data._io import atomic_copy_file, atomic_write_json
from railconfirm.data.longitudinal import LONGITUDINAL_SCHEMA_VERSION
from railconfirm.data.validator import REQUIRED_COLUMNS, ROW_CONTRACT_VERSION


class FormatType(str, Enum):
    """Recognized dataset format families."""

    LONGITUDINAL = "longitudinal"
    ROW_INTERCHANGE = "row_interchange"
    PROSPECTIVE_BATCH = "prospective_batch"
    UNKNOWN = "unknown"


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of a file in streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class SchemaDetectionResult:
    """Outcome of inspecting a candidate dataset file."""

    file_path: str
    format_type: FormatType
    schema_version: str | None
    file_format: str
    record_count: int
    sha256: str
    is_valid_structure: bool
    detected_columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["format_type"] = self.format_type.value
        return d


def detect_schema(path: Path | str) -> SchemaDetectionResult:
    """Inspect a candidate dataset file and detect its schema, version, and integrity.

    Args:
        path: Path to the candidate file.

    Returns:
        SchemaDetectionResult with detected format, version, columns, and diagnostics.
    """
    file_path = Path(path).resolve()
    if not file_path.is_file():
        return SchemaDetectionResult(
            file_path=str(file_path),
            format_type=FormatType.UNKNOWN,
            schema_version=None,
            file_format="missing",
            record_count=0,
            sha256="",
            is_valid_structure=False,
            diagnostics=[f"File not found: {file_path}"],
        )

    file_ext = file_path.suffix.lower().lstrip(".")
    checksum = compute_sha256(file_path)

    # 1. Try JSON inspection
    if file_ext == "json":
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            return SchemaDetectionResult(
                file_path=str(file_path),
                format_type=FormatType.UNKNOWN,
                schema_version=None,
                file_format="json",
                record_count=0,
                sha256=checksum,
                is_valid_structure=False,
                diagnostics=[f"Malformed JSON: {exc}"],
            )

        if isinstance(data, dict):
            # Check for Longitudinal v2.0
            if "journeys" in data and "booking_groups" in data:
                ver = str(data.get("schema_version", LONGITUDINAL_SCHEMA_VERSION))
                journeys_count = len(data.get("journeys", {}))
                groups = data.get("booking_groups", [])
                total_passengers = sum(len(g.get("passengers", [])) for g in groups)
                return SchemaDetectionResult(
                    file_path=str(file_path),
                    format_type=FormatType.LONGITUDINAL,
                    schema_version=ver,
                    file_format="json",
                    record_count=total_passengers,
                    sha256=checksum,
                    is_valid_structure=True,
                    metadata={
                        "journeys_count": journeys_count,
                        "booking_groups_count": len(groups),
                        "dataset_id": data.get("dataset_id"),
                        "source_id": data.get("source_id"),
                    },
                )

            # Check for prospective batch
            if "prospective_submissions" in data or "submissions" in data:
                ver = str(data.get("schema_version", "1.0.0"))
                subs = data.get("prospective_submissions", data.get("submissions", [])) or []
                return SchemaDetectionResult(
                    file_path=str(file_path),
                    format_type=FormatType.PROSPECTIVE_BATCH,
                    schema_version=ver,
                    file_format="json",
                    record_count=len(subs),
                    sha256=checksum,
                    is_valid_structure=True,
                    metadata={"batch_id": data.get("batch_id")},
                )

        # JSON array of row objects
        if isinstance(data, list):
            if not data:
                return SchemaDetectionResult(
                    file_path=str(file_path),
                    format_type=FormatType.UNKNOWN,
                    schema_version=None,
                    file_format="json",
                    record_count=0,
                    sha256=checksum,
                    is_valid_structure=False,
                    diagnostics=["Empty JSON array"],
                )
            if isinstance(data[0], dict):
                columns = list(data[0].keys())
                missing = [c for c in REQUIRED_COLUMNS if c not in columns]
                if not missing:
                    return SchemaDetectionResult(
                        file_path=str(file_path),
                        format_type=FormatType.ROW_INTERCHANGE,
                        schema_version=ROW_CONTRACT_VERSION,
                        file_format="json",
                        record_count=len(data),
                        sha256=checksum,
                        is_valid_structure=True,
                        detected_columns=columns,
                    )
                return SchemaDetectionResult(
                    file_path=str(file_path),
                    format_type=FormatType.UNKNOWN,
                    schema_version=None,
                    file_format="json",
                    record_count=len(data),
                    sha256=checksum,
                    is_valid_structure=False,
                    detected_columns=columns,
                    missing_columns=missing,
                    diagnostics=[f"JSON array missing required row interchange columns: {missing}"],
                )

    # 2. Try Tabular inspection (CSV, TSV, Parquet)
    try:
        if file_ext == "parquet":
            df_sample = pd.read_parquet(file_path)
            row_count = len(df_sample)
        elif file_ext in ("csv", "tsv", "txt"):
            sep = "\t" if file_ext == "tsv" else ","
            df_sample = pd.read_csv(file_path, sep=sep, nrows=100, comment="#")
            # Count total rows safely, skipping comments and blanks
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                non_comment_lines = [
                    line for line in f if line.strip() and not line.strip().startswith("#")
                ]
                row_count = max(len(non_comment_lines) - 1, 0)
        else:
            return SchemaDetectionResult(
                file_path=str(file_path),
                format_type=FormatType.UNKNOWN,
                schema_version=None,
                file_format=file_ext or "unknown",
                record_count=0,
                sha256=checksum,
                is_valid_structure=False,
                diagnostics=[f"Unsupported file extension: .{file_ext}"],
            )
    except Exception as exc:
        return SchemaDetectionResult(
            file_path=str(file_path),
            format_type=FormatType.UNKNOWN,
            schema_version=None,
            file_format=file_ext,
            record_count=0,
            sha256=checksum,
            is_valid_structure=False,
            diagnostics=[f"Failed reading tabular file: {exc}"],
        )

    columns = [str(c) for c in df_sample.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]

    if not missing:
        return SchemaDetectionResult(
            file_path=str(file_path),
            format_type=FormatType.ROW_INTERCHANGE,
            schema_version=ROW_CONTRACT_VERSION,
            file_format=file_ext,
            record_count=row_count,
            sha256=checksum,
            is_valid_structure=True,
            detected_columns=columns,
            missing_columns=[],
        )

    return SchemaDetectionResult(
        file_path=str(file_path),
        format_type=FormatType.UNKNOWN,
        schema_version=None,
        file_format=file_ext,
        record_count=row_count,
        sha256=checksum,
        is_valid_structure=False,
        detected_columns=columns,
        missing_columns=missing,
        diagnostics=[f"Missing required row interchange columns: {missing}"],
    )


def quarantine_dataset(
    file_path: Path | str,
    quarantine_dir: Path | str,
    reason: str,
    *,
    operator: str = "system",
    diagnostics: dict[str, Any] | None = None,
) -> Path:
    """Safely isolate a candidate dataset into the quarantine area with cryptographic report.

    Stages the copy directly into the quarantine directory, computes checksum and
    size directly on the quarantined copy, commits the file, and produces a
    corresponding `.quarantine.json` sidecar. In-process failures rollback the
    committed file.

    Args:
        file_path: Path to the rejected file.
        quarantine_dir: Directory where quarantined files are stored.
        reason: Plain-text justification for the quarantine action.
        operator: Human or system actor initiating the action.
        diagnostics: Additional diagnostic records or error lists.

    Returns:
        The Path to the quarantined file.
    """
    source_path = Path(file_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Cannot quarantine non-existent file: {source_path}")

    target_dir = Path(quarantine_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp_prefix = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    staged_file = target_dir / f".staged_{timestamp_prefix}_{source_path.name}"
    atomic_copy_file(source_path, staged_file)

    try:
        checksum = compute_sha256(staged_file)
        file_size = staged_file.stat().st_size
        target_filename = f"{timestamp_prefix}_{checksum[:12]}_{source_path.name}"
        target_file = target_dir / target_filename
        os.replace(staged_file, target_file)
    except Exception:
        if staged_file.exists():
            try:
                staged_file.unlink()
            except OSError:
                pass
        raise

    # Generate cryptographic sidecar report
    sidecar_path = target_dir / f"{target_filename}.quarantine.json"
    report = {
        "quarantined_at": datetime.now(tz=UTC).isoformat(),
        "original_path": str(source_path),
        "quarantined_path": str(target_file),
        "quarantine_reason": reason,
        "operator": operator,
        "sha256": checksum,
        "file_size_bytes": file_size,
        "diagnostics": diagnostics or {},
        "recommended_action": (
            "Review data provenance, inspect schema diagnostics, and run redaction "
            "or obtain legal clarification before re-attempting intake."
        ),
    }

    try:
        atomic_write_json(sidecar_path, report, indent=2)
    except Exception:
        if target_file.exists():
            try:
                target_file.unlink()
            except OSError:
                pass
        raise

    return target_file


def audit_quarantine_directory(
    quarantine_dir: Path | str,
    *,
    purge_orphans: bool = False,
) -> dict[str, Any]:
    """Audit the quarantine directory for pair consistency, orphaned files, and checksum integrity.

    Verifies that every quarantined data file has a corresponding `.quarantine.json`
    sidecar report, every sidecar has a corresponding data file, and all data
    files match their recorded SHA-256 hashes.

    Args:
        quarantine_dir: Directory containing quarantined datasets and sidecars.
        purge_orphans: If True, unlinks orphaned data files and orphaned sidecars.

    Returns:
        Dictionary with audit summary and findings:
        - ``total_data_files``: Count of data files found.
        - ``total_sidecars``: Count of sidecar files found.
        - ``valid_pairs``: List of string paths for valid (file, sidecar) pairs.
        - ``orphaned_data_files``: List of string paths for data files missing sidecars.
        - ``orphaned_sidecars``: List of string paths for sidecars missing data files.
        - ``checksum_mismatches``: List of dicts describing integrity discrepancies.
        - ``purged_files``: List of string paths unlinked during purge (if enabled).
    """
    qdir = Path(quarantine_dir).resolve()
    if not qdir.is_dir():
        return {
            "total_data_files": 0,
            "total_sidecars": 0,
            "valid_pairs": [],
            "orphaned_data_files": [],
            "orphaned_sidecars": [],
            "checksum_mismatches": [],
            "purged_files": [],
        }

    # Sidecars end in .quarantine.json; temporary/staged files start with .
    all_files = [f for f in qdir.iterdir() if f.is_file() and not f.name.startswith(".")]
    sidecars = {f.name: f for f in all_files if f.name.endswith(".quarantine.json")}
    data_files = {f.name: f for f in all_files if not f.name.endswith(".quarantine.json")}

    valid_pairs: list[str] = []
    orphaned_data_files: list[str] = []
    orphaned_sidecars: list[str] = []
    checksum_mismatches: list[dict[str, Any]] = []
    purged_files: list[str] = []

    # Check data files
    for name, path in data_files.items():
        expected_sidecar_name = f"{name}.quarantine.json"
        if expected_sidecar_name in sidecars:
            sidecar_path = sidecars[expected_sidecar_name]
            try:
                sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
                recorded_hash = sidecar_data.get("sha256")
                actual_hash = compute_sha256(path)
                if recorded_hash and actual_hash != recorded_hash:
                    checksum_mismatches.append(
                        {
                            "data_file": str(path),
                            "sidecar": str(sidecar_path),
                            "expected_sha256": recorded_hash,
                            "actual_sha256": actual_hash,
                        }
                    )
                else:
                    valid_pairs.append(str(path))
            except Exception as exc:
                checksum_mismatches.append(
                    {
                        "data_file": str(path),
                        "sidecar": str(sidecar_path),
                        "error": f"Failed to parse sidecar: {exc}",
                    }
                )
        else:
            orphaned_data_files.append(str(path))

    # Check sidecars
    for sc_name, sc_path in sidecars.items():
        expected_data_name = sc_name[: -len(".quarantine.json")]
        if expected_data_name not in data_files:
            orphaned_sidecars.append(str(sc_path))

    if purge_orphans:
        for path_str in orphaned_data_files:
            p = Path(path_str)
            try:
                p.unlink()
                purged_files.append(path_str)
            except OSError:
                pass
        for sc_str in orphaned_sidecars:
            p = Path(sc_str)
            try:
                p.unlink()
                purged_files.append(sc_str)
            except OSError:
                pass

    return {
        "total_data_files": len(data_files),
        "total_sidecars": len(sidecars),
        "valid_pairs": valid_pairs,
        "orphaned_data_files": orphaned_data_files,
        "orphaned_sidecars": orphaned_sidecars,
        "checksum_mismatches": checksum_mismatches,
        "purged_files": purged_files,
    }

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
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

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
                subs = data.get("prospective_submissions", data.get("submissions", []))
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
            df_sample = pd.read_csv(file_path, sep=sep, nrows=100)
            # Count total rows safely
            with file_path.open("r", encoding="utf-8", errors="replace") as f:
                row_count = max(sum(1 for _ in f) - 1, 0)
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

    checksum = compute_sha256(source_path)
    file_size = source_path.stat().st_size
    timestamp_prefix = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    target_filename = f"{timestamp_prefix}_{checksum[:12]}_{source_path.name}"
    target_file = target_dir / target_filename

    # Copy source into quarantine (retaining original if needed by caller)
    shutil.copy2(source_path, target_file)

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

    with sidecar_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return target_file

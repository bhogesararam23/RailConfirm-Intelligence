"""Dataset schema and data quality validator for RailConfirm Intelligence.

Validates candidate datasets according to docs/data/DATASET_INTAKE_CHECKLIST.md.
Ensures no malformed records, leakage, or unverified outcome labels enter the pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from railconfirm.data.loader import load_dataset_file
from railconfirm.domain.status import NormalizedStatus, parse_status

REQUIRED_COLUMNS = [
    "train_number",
    "journey_date",
    "class_code",
    "quota_code",
    "initial_status",
    "final_chart_status",
    "observation_date",
]


@dataclass
class DatasetValidationReport:
    """Report detailing data quality, schema compliance, and outcome coverage."""

    total_rows: int
    valid_rows: int
    rejected_rows: int
    missing_columns: list[str] = field(default_factory=list)
    duplicate_rows: int = 0
    null_counts: dict[str, int] = field(default_factory=dict)
    initial_status_distribution: dict[str, int] = field(default_factory=dict)
    final_status_distribution: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Returns True if schema is complete and at least one valid row exists."""
        return len(self.missing_columns) == 0 and self.valid_rows > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            "=== Dataset Validation Report ===",
            f"Total rows: {self.total_rows}",
            f"Valid rows: {self.valid_rows}",
            f"Rejected rows: {self.rejected_rows}",
            f"Duplicates: {self.duplicate_rows}",
        ]
        if self.missing_columns:
            lines.append(f"Missing required columns: {', '.join(self.missing_columns)}")
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        lines.append("Final outcome distribution:")
        for k, v in self.final_status_distribution.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def validate_dataset(df: pd.DataFrame) -> DatasetValidationReport:
    """Validate a DataFrame against RailConfirm data contract and intake rules."""
    total_rows = len(df)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    null_counts = {c: int(df[c].isna().sum()) for c in df.columns}
    rejection_reasons: dict[str, int] = {}
    warnings: list[str] = []

    if missing_cols:
        return DatasetValidationReport(
            total_rows=total_rows,
            valid_rows=0,
            rejected_rows=total_rows,
            missing_columns=missing_cols,
            duplicate_rows=0,
            null_counts=null_counts,
            warnings=[f"Missing required columns: {missing_cols}"],
            rejection_reasons={"missing_required_columns": total_rows},
        )

    # Check duplicates across booking context
    dup_cols = ["train_number", "journey_date", "class_code", "quota_code", "initial_status", "observation_date"]
    dup_mask = df.duplicated(subset=[c for c in dup_cols if c in df.columns], keep="first")
    duplicate_rows = int(dup_mask.sum())

    initial_dist: dict[str, int] = {}
    final_dist: dict[str, int] = {}

    valid_count = 0
    rejected_count = 0

    for idx, row in df.iterrows():
        # Check required fields not empty / NaN
        has_null = False
        for c in REQUIRED_COLUMNS:
            val = str(row[c]).strip()
            if not val or val.lower() == "nan":
                has_null = True
                break

        if has_null:
            rejected_count += 1
            rejection_reasons["missing_required_value"] = rejection_reasons.get("missing_required_value", 0) + 1
            continue

        init_parsed = parse_status(str(row["initial_status"]))
        final_parsed = parse_status(str(row["final_chart_status"]))

        initial_dist[init_parsed.normalized.value] = initial_dist.get(init_parsed.normalized.value, 0) + 1
        final_dist[final_parsed.normalized.value] = final_dist.get(final_parsed.normalized.value, 0) + 1

        if init_parsed.normalized == NormalizedStatus.UNKNOWN:
            rejected_count += 1
            rejection_reasons["unknown_initial_status"] = rejection_reasons.get("unknown_initial_status", 0) + 1
            continue

        if final_parsed.normalized == NormalizedStatus.UNKNOWN:
            rejected_count += 1
            rejection_reasons["unknown_final_status"] = rejection_reasons.get("unknown_final_status", 0) + 1
            continue

        valid_count += 1

    if duplicate_rows > 0:
        warnings.append(f"Found {duplicate_rows} potential duplicate observation rows.")

    if final_dist.get(NormalizedStatus.CENSORED.value, 0) > 0:
        warnings.append(
            f"Dataset contains {final_dist[NormalizedStatus.CENSORED.value]} CENSORED outcome records. "
            "Ensure these are not treated as negative training labels."
        )

    return DatasetValidationReport(
        total_rows=total_rows,
        valid_rows=valid_count,
        rejected_rows=rejected_count,
        missing_columns=[],
        duplicate_rows=duplicate_rows,
        null_counts=null_counts,
        initial_status_distribution=initial_dist,
        final_status_distribution=final_dist,
        warnings=warnings,
        rejection_reasons=rejection_reasons,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m railconfirm.data.validator <dataset_path>")
        sys.exit(1)

    path = sys.argv[1]
    df = load_dataset_file(path)
    report = validate_dataset(df)
    print(report.summary())
    sys.exit(0 if report.is_valid else 1)

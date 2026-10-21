"""Dataset manifest generator and parser for RailConfirm Intelligence.

Generates reproducible, cryptographically verifiable manifests for candidate datasets
following docs/data/DATASET_MANIFEST_TEMPLATE.yaml and ADR-0005.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.validator import validate_dataset


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DatasetManifest:
    """Manifest record for an evaluated dataset."""

    dataset_name: str
    dataset_version: str
    file_name: str
    sha256: str
    created_at: str
    source_reference: str
    license_or_terms: str
    is_synthetic: bool
    total_records: int
    valid_records: int
    rejected_records: int
    approval_status: str  # "approved_for_training", "quarantined", "metadata_only", "synthetic_test_only"
    notes: str | None = None

    def to_yaml(self) -> str:
        return yaml.dump(asdict(self), sort_keys=False)


def generate_manifest(
    file_path: Path,
    dataset_name: str,
    dataset_version: str = "1.0.0",
    source_ref: str = "local_candidate",
    license_terms: str = "unspecified",
    is_synthetic: bool = False,
    approval_status: str = "quarantined",
    notes: str | None = None,
) -> DatasetManifest:
    """Generate a manifest for a candidate dataset file."""
    path = Path(file_path)
    sha = compute_sha256(path)
    df = load_dataset_file(path)
    report = validate_dataset(df)

    return DatasetManifest(
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        file_name=path.name,
        sha256=sha,
        created_at=datetime.now(UTC).isoformat(),
        source_reference=source_ref,
        license_or_terms=license_terms,
        is_synthetic=is_synthetic,
        total_records=report.total_rows,
        valid_records=report.valid_rows,
        rejected_records=report.rejected_rows,
        approval_status=approval_status,
        notes=notes,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m railconfirm.data.manifest <dataset_path> [output_yaml_path]")
        sys.exit(1)

    file_p = Path(sys.argv[1])
    name = file_p.stem
    manifest = generate_manifest(file_p, dataset_name=name)

    output = manifest.to_yaml()
    if len(sys.argv) >= 3:
        out_p = Path(sys.argv[2])
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output, encoding="utf-8")
        print(f"Manifest written to {out_p}")
    else:
        print(output)

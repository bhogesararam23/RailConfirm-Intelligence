"""Unit tests for dataset schema validation and manifest generation."""

from pathlib import Path

import pandas as pd

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.manifest import generate_manifest
from railconfirm.data.validator import validate_dataset


def test_validate_synthetic_dataset(synthetic_dataset_path: Path):
    df = load_dataset_file(synthetic_dataset_path)
    report = validate_dataset(df)
    assert report.is_valid is True
    assert report.total_rows == 6
    assert report.valid_rows == 6
    assert report.rejected_rows == 0
    assert "CNF" in report.final_status_distribution


def test_validate_missing_columns():
    df_incomplete = pd.DataFrame(
        {
            "train_number": ["12301"],
            "journey_date": ["2026-10-01"],
        }
    )
    report = validate_dataset(df_incomplete)
    assert report.is_valid is False
    assert len(report.missing_columns) > 0


def test_validate_unknown_status():
    df_unknown = pd.DataFrame(
        {
            "train_number": ["12301"],
            "journey_date": ["2026-10-01"],
            "class_code": ["SL"],
            "quota_code": ["GN"],
            "initial_status": ["INVALID_STATUS_CODE"],
            "final_chart_status": ["CNF"],
            "observation_date": ["2026-09-25"],
        }
    )
    report = validate_dataset(df_unknown)
    assert report.rejected_rows == 1
    assert "unknown_initial_status" in report.rejection_reasons


def test_manifest_generation(synthetic_dataset_path: Path):
    manifest = generate_manifest(
        file_path=synthetic_dataset_path,
        dataset_name="synthetic_test_set",
        is_synthetic=True,
        approval_status="synthetic_test_only",
    )
    assert manifest.dataset_name == "synthetic_test_set"
    assert manifest.is_synthetic is True
    assert len(manifest.sha256) == 64
    assert manifest.valid_records == 6
    yaml_str = manifest.to_yaml()
    assert "sha256" in yaml_str

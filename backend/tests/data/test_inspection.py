"""Tests for dataset schema inspection, auto-detection, and quarantine workflow."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.data.inspection import (
    FormatType,
    compute_sha256,
    detect_schema,
    quarantine_dataset,
)
from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    FinalOutcome,
    LabelConfidence,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    StatusObservation,
    VerificationMethod,
    save_longitudinal_dataset,
)
from railconfirm.data.validator import REQUIRED_COLUMNS, ROW_CONTRACT_VERSION
from railconfirm.domain.status import NormalizedStatus


@pytest.fixture
def longitudinal_file(tmp_path: Path) -> Path:
    journey = LongitudinalJourney(
        journey_id="J1",
        train_number="12301",
        journey_date=date(2026, 12, 1),
        boarding_station="NDLS",
        destination_station="HWH",
        class_code="3A",
        quota_code="GN",
    )
    p = PassengerReservation(
        passenger_record_id="P1",
        booking_group_id="B1",
        passenger_sequence=1,
        original_status_raw="GNWL 10",
        original_status_category=NormalizedStatus.WL,
        original_observed_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        observations=[
            StatusObservation(
                observation_id="O1",
                passenger_record_id="P1",
                observed_at=datetime(2026, 11, 15, 10, 0, tzinfo=UTC),
                status_raw="RAC 2",
                status_category=NormalizedStatus.RAC,
            )
        ],
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CNF",
            outcome_category=NormalizedStatus.CNF,
            outcome_observed_at=datetime(2026, 12, 1, 12, 0, tzinfo=UTC),
            verification_method=VerificationMethod.CHART_SNAPSHOT,
            label_confidence=LabelConfidence.VERIFIED,
        ),
    )
    group = BookingGroup(
        booking_group_id="B1",
        journey_id="J1",
        passengers=[p],
    )
    dataset = LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id="test_longitudinal_inspection",
        source_id="test_source",
        created_at=datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        journeys={"J1": journey},
        booking_groups=[group],
    )
    target = tmp_path / "sample_longitudinal.json"
    save_longitudinal_dataset(dataset, target)
    return target


@pytest.fixture
def valid_csv_file(tmp_path: Path) -> Path:
    csv_path = tmp_path / "valid_rows.csv"
    headers = list(REQUIRED_COLUMNS)
    row_data = ["12301", "2026-12-01", "3A", "GN", "GNWL 10", "CNF", "2026-11-20"]
    csv_path.write_text(f"{','.join(headers)}\n{','.join(row_data)}\n", encoding="utf-8")
    return csv_path


def test_detect_longitudinal_schema(longitudinal_file: Path):
    result = detect_schema(longitudinal_file)
    assert result.format_type == FormatType.LONGITUDINAL
    assert result.schema_version == LONGITUDINAL_SCHEMA_VERSION
    assert result.file_format == "json"
    assert result.record_count == 1
    assert result.is_valid_structure is True
    assert len(result.sha256) == 64
    assert result.metadata.get("dataset_id") == "test_longitudinal_inspection"


def test_detect_row_interchange_csv(valid_csv_file: Path):
    result = detect_schema(valid_csv_file)
    assert result.format_type == FormatType.ROW_INTERCHANGE
    assert result.schema_version == ROW_CONTRACT_VERSION
    assert result.file_format == "csv"
    assert result.record_count == 1
    assert result.is_valid_structure is True
    assert set(REQUIRED_COLUMNS).issubset(set(result.detected_columns))
    assert len(result.missing_columns) == 0


def test_detect_row_interchange_json_array(tmp_path: Path):
    json_path = tmp_path / "rows.json"
    data = [
        {
            "train_number": "12301",
            "journey_date": "2026-12-01",
            "class_code": "3A",
            "quota_code": "GN",
            "initial_status": "GNWL 10",
            "final_chart_status": "CNF",
            "observation_date": "2026-11-20",
        }
    ]
    json_path.write_text(json.dumps(data), encoding="utf-8")
    result = detect_schema(json_path)
    assert result.format_type == FormatType.ROW_INTERCHANGE
    assert result.record_count == 1
    assert result.is_valid_structure is True


def test_detect_missing_required_columns_csv(tmp_path: Path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("train_number,journey_date\n12301,2026-12-01\n", encoding="utf-8")
    result = detect_schema(csv_path)
    assert result.format_type == FormatType.UNKNOWN
    assert result.is_valid_structure is False
    assert "class_code" in result.missing_columns
    assert "final_chart_status" in result.missing_columns
    assert any("Missing required row interchange columns" in d for d in result.diagnostics)


def test_detect_non_existent_file(tmp_path: Path):
    missing_path = tmp_path / "non_existent.csv"
    result = detect_schema(missing_path)
    assert result.format_type == FormatType.UNKNOWN
    assert result.is_valid_structure is False
    assert any("File not found" in d for d in result.diagnostics)


def test_detect_malformed_json(tmp_path: Path):
    bad_json = tmp_path / "broken.json"
    bad_json.write_text("{ unquoted_key: 123 ", encoding="utf-8")
    result = detect_schema(bad_json)
    assert result.format_type == FormatType.UNKNOWN
    assert result.is_valid_structure is False
    assert any("Malformed JSON" in d for d in result.diagnostics)


def test_quarantine_dataset_creates_sidecar_and_isolates(tmp_path: Path):
    source_file = tmp_path / "unapproved_dataset.csv"
    source_file.write_text("data,with,leakage\n1,2,3\n", encoding="utf-8")
    original_checksum = compute_sha256(source_file)

    quarantine_dir = tmp_path / "quarantine"
    quarantined_path = quarantine_dataset(
        source_file,
        quarantine_dir,
        reason="Dataset contains potential personal identifiers and unverified consent",
        operator="lead_auditor",
        diagnostics={"unverified_columns": ["passenger_name_raw"]},
    )

    assert quarantined_path.is_file()
    assert quarantined_path.parent == quarantine_dir
    assert original_checksum[:12] in quarantined_path.name

    # Check sidecar report
    sidecar_path = quarantine_dir / f"{quarantined_path.name}.quarantine.json"
    assert sidecar_path.is_file()

    with sidecar_path.open("r", encoding="utf-8") as f:
        report = json.load(f)

    assert report["quarantine_reason"] == "Dataset contains potential personal identifiers and unverified consent"
    assert report["operator"] == "lead_auditor"
    assert report["sha256"] == original_checksum
    assert report["diagnostics"] == {"unverified_columns": ["passenger_name_raw"]}
    assert "Review data provenance" in report["recommended_action"]


def test_quarantine_non_existent_file_raises(tmp_path: Path):
    missing_file = tmp_path / "missing.csv"
    quarantine_dir = tmp_path / "quarantine"
    with pytest.raises(FileNotFoundError, match="Cannot quarantine non-existent file"):
        quarantine_dataset(missing_file, quarantine_dir, reason="test")

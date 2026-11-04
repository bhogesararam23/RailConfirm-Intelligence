"""Tests for dataset schema inspection, auto-detection, and quarantine workflow."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.data.inspection import (
    FormatType,
    audit_quarantine_directory,
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


def test_quarantine_checksum_computed_on_quarantined_file(tmp_path: Path):
    source_file = tmp_path / "original.csv"
    source_file.write_text("v1_content", encoding="utf-8")
    quarantine_dir = tmp_path / "quarantine"

    quarantined = quarantine_dataset(
        source_file,
        quarantine_dir,
        reason="Test quarantine hash verification",
    )
    sidecar_path = quarantine_dir / f"{quarantined.name}.quarantine.json"
    sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))

    # The sidecar sha256 must match the quarantined file's actual hash
    assert sidecar_data["sha256"] == compute_sha256(quarantined)


def test_audit_quarantine_directory_valid_and_missing(tmp_path: Path):
    # Test on non-existent directory returns zero report safely
    missing_dir = tmp_path / "does_not_exist"
    report = audit_quarantine_directory(missing_dir)
    assert report["total_data_files"] == 0
    assert report["valid_pairs"] == []

    # Create a valid quarantined file + sidecar
    source_file = tmp_path / "sample.csv"
    source_file.write_text("sample_row_1\n", encoding="utf-8")
    quarantine_dir = tmp_path / "quarantine"

    quarantined = quarantine_dataset(
        source_file,
        quarantine_dir,
        reason="Privacy audit failure",
    )

    audit = audit_quarantine_directory(quarantine_dir)
    assert audit["total_data_files"] == 1
    assert audit["total_sidecars"] == 1
    assert str(quarantined) in audit["valid_pairs"]
    assert len(audit["orphaned_data_files"]) == 0
    assert len(audit["orphaned_sidecars"]) == 0
    assert len(audit["checksum_mismatches"]) == 0


def test_audit_quarantine_directory_orphans_and_purge(tmp_path: Path):
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True)

    # 1. Create a valid pair
    valid_file = quarantine_dir / "valid_data.csv"
    valid_file.write_text("content", encoding="utf-8")
    valid_sidecar = quarantine_dir / "valid_data.csv.quarantine.json"
    valid_sidecar.write_text(json.dumps({"sha256": compute_sha256(valid_file)}), encoding="utf-8")

    # 2. Create an orphaned data file (missing sidecar)
    orphan_data = quarantine_dir / "orphan_data.csv"
    orphan_data.write_text("orphan content", encoding="utf-8")

    # 3. Create an orphaned sidecar (missing data file)
    orphan_sidecar = quarantine_dir / "orphan_alone.csv.quarantine.json"
    orphan_sidecar.write_text(json.dumps({"sha256": "abcdef"}), encoding="utf-8")

    # Audit without purge
    audit = audit_quarantine_directory(quarantine_dir, purge_orphans=False)
    assert audit["total_data_files"] == 2
    assert audit["total_sidecars"] == 2
    assert str(valid_file) in audit["valid_pairs"]
    assert str(orphan_data) in audit["orphaned_data_files"]
    assert str(orphan_sidecar) in audit["orphaned_sidecars"]
    assert len(audit["purged_files"]) == 0
    assert orphan_data.exists()
    assert orphan_sidecar.exists()

    # Audit with purge
    purge_audit = audit_quarantine_directory(quarantine_dir, purge_orphans=True)
    assert len(purge_audit["purged_files"]) == 2
    assert not orphan_data.exists()
    assert not orphan_sidecar.exists()
    assert valid_file.exists()
    assert valid_sidecar.exists()


def test_audit_quarantine_directory_detects_checksum_mismatch(tmp_path: Path):
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir(parents=True)

    data_file = quarantine_dir / "tampered.csv"
    data_file.write_text("tampered_content", encoding="utf-8")
    sidecar = quarantine_dir / "tampered.csv.quarantine.json"
    sidecar.write_text(json.dumps({"sha256": "recorded_wrong_hash_123"}), encoding="utf-8")

    audit = audit_quarantine_directory(quarantine_dir)
    assert len(audit["checksum_mismatches"]) == 1
    mismatch = audit["checksum_mismatches"][0]
    assert mismatch["data_file"] == str(data_file)
    assert mismatch["expected_sha256"] == "recorded_wrong_hash_123"
    assert mismatch["actual_sha256"] == compute_sha256(data_file)


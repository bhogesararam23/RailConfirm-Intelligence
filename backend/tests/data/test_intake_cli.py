"""Tests for the dataset intake command line."""

from pathlib import Path

import pytest

from railconfirm.data.__main__ import main
from railconfirm.data.manifest import parse_manifest


@pytest.fixture
def candidate_csv(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.csv"
    path.write_text(
        "# SYNTHETIC DATA - TESTING ONLY\n"
        "train_number,journey_date,class_code,quota_code,initial_status,"
        "final_chart_status,observation_date\n"
        "12301,2026-10-01,SL,GN,GNWL/10,CNF,2026-09-20\n"
        "12301,2026-10-02,SL,GN,GNWL/11,RAC 3,2026-09-21\n",
        encoding="utf-8",
    )
    return path


def test_validate_exits_one_when_not_eligible(candidate_csv: Path, capsys):
    assert main(["validate", str(candidate_csv)]) == 1
    out = capsys.readouterr().out
    assert "structurally valid  : yes" in out
    assert "technically eligible: no" in out


def test_validate_json_output_is_parseable(candidate_csv: Path, capsys):
    import json

    assert main(["validate", "--json", str(candidate_csv)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_rows"] == 2
    assert payload["structurally_valid"] is True


def test_validate_exits_zero_when_eligible(tmp_path: Path, capsys):
    rows = []
    for day in range(1, 9):
        for index in range(30):
            rows.append(
                f"1230{index % 3},2026-02-{day:02d},SL,GN,GNWL/{index:02d},"
                f"{'CNF' if index % 2 else 'WL/5'},2026-01-{20 + index % 5:02d}"
            )
    path = tmp_path / "big.csv"
    path.write_text(
        "train_number,journey_date,class_code,quota_code,initial_status,"
        "final_chart_status,observation_date\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    assert main(["validate", str(path)]) == 0, capsys.readouterr().out
    assert "technically eligible: yes" in capsys.readouterr().out


def test_validate_reports_an_unreadable_file(tmp_path: Path, capsys):
    assert main(["validate", str(tmp_path / "absent.csv")]) == 1
    assert "Cannot read dataset" in capsys.readouterr().err


def test_manifest_writes_a_reviewable_file(candidate_csv: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "manifests"
    code = main(
        [
            "manifest",
            str(candidate_csv),
            "--dataset-id",
            "cli-fixture",
            "--title",
            "CLI fixture set",
            "--retrieved-on",
            "2026-10-18",
            "--output",
            str(out_dir),
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out
    assert "Approval is a human step" in printed
    written = out_dir / "cli-fixture.yaml"
    assert written.is_file()
    parsed = parse_manifest(written.read_text(encoding="utf-8"))
    assert parsed.status == "candidate"
    assert parsed.decision.decision == "under_review"
    assert parsed.coverage.row_count == 2


def test_manifest_refuses_to_invent_todays_date(candidate_csv: Path, tmp_path: Path, capsys):
    code = main(
        [
            "manifest",
            str(candidate_csv),
            "--dataset-id",
            "x",
            "--title",
            "x",
            "--retrieved-on",
            "",
            "--output",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "retrieved_on" in capsys.readouterr().err


def test_manifest_status_choices_are_closed(candidate_csv: Path, tmp_path: Path):
    with pytest.raises(SystemExit):
        main(
            [
                "manifest",
                str(candidate_csv),
                "--dataset-id",
                "x",
                "--title",
                "x",
                "--retrieved-on",
                "2026-10-18",
                "--status",
                "approved_for_training",
                "--output",
                str(tmp_path),
            ]
        )


def test_verify_round_trips_a_generated_manifest(candidate_csv: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "manifests"
    assert main(
        [
            "manifest",
            str(candidate_csv),
            "--dataset-id",
            "cli-fixture",
            "--title",
            "CLI fixture set",
            "--retrieved-on",
            "2026-10-18",
            "--output",
            str(out_dir),
        ]
    ) == 0
    capsys.readouterr()
    assert main(["verify", str(out_dir / "cli-fixture.yaml"), str(candidate_csv)]) == 0
    assert "FAIL" not in capsys.readouterr().out


def test_verify_fails_after_the_dataset_changes(candidate_csv: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "manifests"
    main(
        [
            "manifest",
            str(candidate_csv),
            "--dataset-id",
            "cli-fixture",
            "--title",
            "CLI fixture set",
            "--retrieved-on",
            "2026-10-18",
            "--output",
            str(out_dir),
        ]
    )
    capsys.readouterr()
    candidate_csv.write_text(
        candidate_csv.read_text(encoding="utf-8") + "12301,2026-10-03,SL,GN,GNWL/9,CNF,2026-09-22\n",
        encoding="utf-8",
    )
    assert main(["verify", str(out_dir / "cli-fixture.yaml"), str(candidate_csv)]) == 1
    assert "content changed" in capsys.readouterr().out


def test_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit):
        main(["frobnicate"])


def test_cli_detect_subcommand(candidate_csv: Path, capsys):
    import json

    assert main(["detect", str(candidate_csv)]) == 0
    out = capsys.readouterr().out
    assert "Format: row_interchange" in out
    assert "Valid Structure: yes" in out

    assert main(["detect", "--json", str(candidate_csv)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["format_type"] == "row_interchange"
    assert d["is_valid_structure"] is True


def test_cli_validate_and_snapshot_longitudinal(tmp_path: Path, capsys):
    import json
    from datetime import UTC, date, datetime

    import pandas as pd

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
    from railconfirm.domain.status import NormalizedStatus

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
        original_status_raw="GNWL 20",
        original_status_category=NormalizedStatus.WL,
        original_observed_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        observations=[
            StatusObservation(
                observation_id="O1",
                passenger_record_id="P1",
                observed_at=datetime(2026, 11, 15, 10, 0, tzinfo=UTC),
                status_raw="RAC 5",
                status_category=NormalizedStatus.RAC,
                status_position=5,
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
    ds = LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id="cli_long_test",
        source_id="test_source",
        created_at=datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        journeys={"J1": journey},
        booking_groups=[group],
    )
    ds_path = tmp_path / "long.json"
    save_longitudinal_dataset(ds, ds_path)

    # 1. Validate
    assert main(["validate", str(ds_path)]) == 0
    assert "Valid: yes" in capsys.readouterr().out

    assert main(["validate", "--json", str(ds_path)]) == 0
    v_report = json.loads(capsys.readouterr().out)
    assert v_report["is_valid"] is True
    assert v_report["metrics"]["total_passengers"] == 1

    # 2. Snapshot
    out_csv = tmp_path / "snapshot.csv"
    assert (
        main(
            [
                "snapshot",
                str(ds_path),
                str(out_csv),
                "--as-of-lead-days",
                "10",
            ]
        )
        == 0
    )
    assert "Generated snapshot CSV" in capsys.readouterr().out
    assert out_csv.is_file()

    df = pd.read_csv(out_csv)
    assert len(df) == 1
    assert df.iloc[0]["train_number"] == 12301
    assert df.iloc[0]["final_chart_status"] == "CNF"


def test_cli_quarantine_subcommand(candidate_csv: Path, tmp_path: Path, capsys):
    q_dir = tmp_path / "quarantine_target"
    assert (
        main(
            [
                "quarantine",
                str(candidate_csv),
                "--reason",
                "Potential unverified PII in review",
                "--quarantine-dir",
                str(q_dir),
                "--operator",
                "security_lead",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Quarantined dataset:" in out
    assert "Sidecar cryptographic report:" in out
    assert q_dir.is_dir()
    files = list(q_dir.glob("*.quarantine.json"))
    assert len(files) == 1

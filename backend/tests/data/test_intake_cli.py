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

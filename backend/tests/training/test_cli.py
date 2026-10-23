"""Tests for the training command line and the reports it writes."""

import json
from pathlib import Path

import pytest

from railconfirm.training.__main__ import main
from tests.support.datasets import (
    approved_decision,
    write_approved_manifest,
    write_dataset,
)


@pytest.fixture
def paths(tmp_path: Path):
    csv = write_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    return tmp_path, csv, manifest


def test_fit_writes_a_candidate_artifact_and_report(paths, capsys):
    tmp_path, csv, manifest = paths
    artifact = tmp_path / "out" / "pipeline_v1.json"
    report = tmp_path / "out" / "report.json"
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "pipeline_v1",
            "--out",
            str(artifact),
            "--report",
            str(report),
            "--generated-on",
            "2026-04-05",
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 0, capsys.readouterr().err
    assert artifact.is_file()
    payload = json.loads(report.read_text(encoding="utf-8"))

    assert payload["model_version"] == "pipeline_v1"
    assert payload["target"] == "final_chart_cnf"
    assert len(payload["dataset"]["sha256"]) == 64
    assert payload["dataset"]["is_synthetic"] is True
    assert payload["split"]["eligible"] is True
    assert len(payload["split"]["boundaries"]) == 3
    assert payload["fit"]["rows_used"] > 0
    assert "brier" in payload["metric_definitions"]
    assert payload["validation"]["rows"] > 0
    assert payload["test"]["rows"] > 0
    printed = capsys.readouterr().out
    assert "Promotion is 'candidate'" in printed


def test_fit_refuses_unapproved_data_and_exits_one(tmp_path: Path, capsys):
    csv = write_dataset(tmp_path)
    manifest = write_approved_manifest(
        csv,
        tmp_path,
        dataset_id="unapproved",
        decision=approved_decision(decision="under_review", reviewed_by=None, reviewed_on=None),
    )
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "v",
            "--out",
            str(tmp_path / "v.json"),
        ]
    )
    assert code == 1
    assert "Refused:" in capsys.readouterr().err


def test_fit_without_the_synthetic_opt_in_exits_one(paths, capsys):
    tmp_path, csv, manifest = paths
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "v",
            "--out",
            str(tmp_path / "v.json"),
        ]
    )
    assert code == 1
    assert "is_synthetic" in capsys.readouterr().err


def test_report_requires_an_explicit_generation_date(paths, capsys):
    """A clock-stamped report cannot be reproduced, so the caller must name the date."""
    tmp_path, csv, manifest = paths
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "v",
            "--out",
            str(tmp_path / "v.json"),
            "--report",
            str(tmp_path / "r.json"),
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "--generated-on" in capsys.readouterr().err


def test_two_runs_produce_identical_reports(paths):
    """Reproducibility: same inputs, same date, same bytes."""
    tmp_path, csv, manifest = paths
    digests = []
    for index in (1, 2):
        artifact = tmp_path / f"run{index}.json"
        report = tmp_path / f"report{index}.json"
        main(
            [
                "fit",
                str(csv),
                str(manifest),
                "--version",
                f"run{index}",
                "--out",
                str(artifact),
                "--report",
                str(report),
                "--generated-on",
                "2026-04-05",
                "--min-sample-threshold",
                "5",
                "--allow-synthetic-for-testing",
            ]
        )
        payload = json.loads(report.read_text(encoding="utf-8"))
        # Only the version identifier differs between the runs.
        payload.pop("model_version")
        digests.append(json.dumps(payload, sort_keys=True))
    assert digests[0] == digests[1]


def test_evaluate_scores_an_existing_artifact(paths, capsys):
    tmp_path, csv, manifest = paths
    artifact = tmp_path / "eval_v1.json"
    main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "eval_v1",
            "--out",
            str(artifact),
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
    )
    capsys.readouterr()
    code = main(
        [
            "evaluate",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact),
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    assert "target final_chart_cnf" in out
    assert "validation Brier" in out
    assert "event Brier" in out
    assert out.count("event Brier") == 2


def test_evaluate_refuses_an_artifact_fitted_for_the_other_target(paths, capsys):
    tmp_path, csv, manifest = paths
    artifact = tmp_path / "eval_merged.json"
    main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "eval_merged",
            "--target",
            "final_chart_cnf_or_rac",
            "--out",
            str(artifact),
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
    )
    capsys.readouterr()
    code = main(
        [
            "evaluate",
            str(csv),
            str(manifest),
            "--artifact",
            str(artifact),
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "not 'final_chart_cnf'" in capsys.readouterr().err

    assert (
        main(
            [
                "evaluate",
                str(csv),
                str(manifest),
                "--artifact",
                str(artifact),
                "--target",
                "final_chart_cnf_or_rac",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "target final_chart_cnf_or_rac" in out


def test_an_unscorable_target_is_a_usage_error_not_a_silent_default(paths, capsys):
    tmp_path, csv, manifest = paths
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "fit",
                str(csv),
                str(manifest),
                "--version",
                "weird_v1",
                "--target",
                "departure_status",
                "--out",
                str(tmp_path / "weird.json"),
                "--allow-synthetic-for-testing",
            ]
        )
    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not (tmp_path / "weird.json").exists()


def test_evaluate_can_write_a_full_report(paths):
    tmp_path, csv, manifest = paths
    artifact = tmp_path / "eval_v1.json"
    main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "eval_v1",
            "--out",
            str(artifact),
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
    )
    report = tmp_path / "eval-report.json"
    assert (
        main(
            [
                "evaluate",
                str(csv),
                str(manifest),
                "--artifact",
                str(artifact),
                "--report",
                str(report),
                "--generated-on",
                "2026-04-06",
                "--allow-synthetic-for-testing",
            ]
        )
        == 0
    )
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["conclusions"]
    assert any("Brier" in line for line in payload["conclusions"])
    assert any("calibration" in line.lower() for line in payload["limitations"])


def test_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit):
        main(["frobnicate"])

"""Tests for the training command line and the reports it writes."""

import json
from pathlib import Path

import pytest

from railconfirm.training.__main__ import main
from tests.support.datasets import (
    GATE_ROW_COUNT,
    approved_decision,
    gate_defects,
    write_approved_manifest,
    write_dataset,
    write_gate_dataset,
    write_moving_dataset,
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


def test_fit_states_which_rows_validation_kept(tmp_path: Path, capsys):
    """A fit must not rest silently on rows the report says were rejected."""
    csv = write_gate_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="cli-defects")
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "gated_v1",
            "--out",
            str(tmp_path / "gated_v1.json"),
            "--min-sample-threshold",
            "1",
            "--allow-synthetic-for-testing",
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    # Counted from the fixture, not hardcoded: every defect shape in gate_defects()
    # is rejected, and P0001 goes with the contradiction it is part of.
    total = GATE_ROW_COUNT + len(gate_defects())
    kept = GATE_ROW_COUNT - 1
    assert f"Validation kept {kept} of {total} rows ({total - kept} rejected" in printed
    assert "exact_duplicate_row=1" in printed
    assert "contradictory_labels=2" in printed
    assert "observation_on_journey_date=1" in printed
    assert "Eligibility thresholds were NOT met" in printed


@pytest.mark.parametrize("command", ["fit", "evaluate"])
def test_the_cli_refuses_a_technically_ineligible_real_dataset(tmp_path: Path, capsys, command):
    csv = write_gate_dataset(tmp_path, synthetic="false")
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="cli-too-small")
    argv = [
        command,
        str(csv),
        str(manifest),
        "--train-frac",
        "0.5",
        "--val-frac",
        "0.25",
    ]
    argv += (
        ["--version", "v", "--out", str(tmp_path / "v.json")]
        if command == "fit"
        else ["--artifact", str(tmp_path / "missing.json")]
    )
    assert main(argv) == 1
    assert "not technically eligible" in capsys.readouterr().err


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


def test_origins_scores_several_cutoffs_and_writes_a_report(tmp_path: Path, capsys):
    csv = write_moving_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="origins-cli")
    report = tmp_path / "origins.json"
    code = main(
        [
            "origins",
            str(csv),
            str(manifest),
            "--min-sample-threshold",
            "1",
            "--min-train-dates",
            "4",
            "--horizon-dates",
            "2",
            "--step-dates",
            "2",
            "--report",
            str(report),
            "--generated-on",
            "2026-10-23",
            "--allow-synthetic-for-testing",
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "Validation kept 240 of 240 rows" in printed
    assert "Aggregate over" in printed
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["evaluation_method"] == "refit-per-origin, score-the-next-horizon"
    assert payload["plan"]["origin_count"] == len(payload["origins"])
    assert payload["plan"]["origin_count"] >= 2
    assert payload["dataset"]["is_synthetic"] is True
    assert payload["conclusions"]
    assert any("independent evaluations" in line for line in payload["limitations"])


def test_origins_refuses_data_that_supports_only_one_cutoff(tmp_path: Path, capsys):
    """Six dates with a five-date training block leaves a single horizon."""
    csv = write_gate_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="origins-one")
    code = main(
        [
            "origins",
            str(csv),
            str(manifest),
            "--min-train-dates",
            "5",
            "--min-sample-threshold",
            "1",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "rolling-origin evaluation" in err
    assert "Only 1 origin usable" in err


def test_origins_report_still_requires_an_explicit_generation_date(tmp_path: Path, capsys):
    csv = write_moving_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="origins-undated")
    assert (
        main(
            [
                "origins",
                str(csv),
                str(manifest),
                "--min-train-dates",
                "4",
                "--report",
                str(tmp_path / "o.json"),
                "--allow-synthetic-for-testing",
            ]
        )
        == 1
    )
    assert "--generated-on" in capsys.readouterr().err


def test_origins_refuses_a_technically_ineligible_real_dataset(tmp_path: Path, capsys):
    csv = write_gate_dataset(tmp_path, synthetic="false")
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="origins-real")
    assert main(["origins", str(csv), str(manifest), "--min-train-dates", "2"]) == 1
    assert "not technically eligible" in capsys.readouterr().err


def test_unknown_command_is_a_usage_error():
    with pytest.raises(SystemExit):
        main(["frobnicate"])

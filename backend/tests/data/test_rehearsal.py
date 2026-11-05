"""Tests for the deterministic offline synthetic prospective-lifecycle rehearsal.

These tests cover the rehearsal orchestration only. They assert that the software
behaves as documented on synthetic fixtures; passing them establishes nothing
about real railway behaviour and does not authorize a real pilot.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from railconfirm.data.__main__ import main
from railconfirm.data.longitudinal import load_longitudinal_dataset
from railconfirm.data.prospective import (
    MIN_SALT_LENGTH,
    derive_pseudonym,
)
from railconfirm.data.rehearsal import (
    DEFAULT_REHEARSAL_SALT,
    REHEARSAL_GATE_ORDER,
    SYNTHETIC_MARK,
    GateStatus,
    RehearsalGate,
    RehearsalReport,
    run_prospective_rehearsal,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError


def _run(tmp_path: Path) -> RehearsalReport:
    return run_prospective_rehearsal(tmp_path / "workspace")


def test_rehearsal_passes_every_gate(tmp_path: Path) -> None:
    report = _run(tmp_path)

    assert report.software_rehearsal_passed is True
    assert report.overall_status is GateStatus.PASS
    assert report.gate_ids == list(REHEARSAL_GATE_ORDER)
    assert report.missing_gate_ids == []
    assert report.failed_gates == []
    assert report.is_synthetic is True


def test_rehearsal_is_deterministic_for_the_same_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = run_prospective_rehearsal(workspace)
    second = run_prospective_rehearsal(workspace)

    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )


def test_rehearsal_writes_labelled_machine_and_human_reports(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _run(tmp_path)

    text = (workspace / "reports" / "rehearsal_report.txt").read_text(encoding="utf-8")
    assert text.startswith(SYNTHETIC_MARK)
    assert "REAL-WORLD PILOT AUTHORIZED: NO" in text

    payload = json.loads(
        (workspace / "reports" / "rehearsal_report.json").read_text(encoding="utf-8")
    )
    assert payload["is_synthetic"] is True
    assert payload["real_world_pilot_authorized"] is False
    assert payload["software_rehearsal_passed"] is True
    assert payload["gate_count"] == len(REHEARSAL_GATE_ORDER)


def test_withdrawal_cannot_survive_into_verified_current_export(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    report = _run(tmp_path)

    dataset = load_longitudinal_dataset(workspace / "export" / "approved_export.json")
    exported_groups = {bg.booking_group_id for bg in dataset.booking_groups}
    withdrawn_groups = {
        derive_pseudonym(f"synthetic_pnr_{seq:04d}", salt=DEFAULT_REHEARSAL_SALT)
        for seq in (2, 6)
    }
    assert withdrawn_groups.isdisjoint(exported_groups)

    stale = report.gate("stale_export_detection")
    assert stale is not None
    assert any("STALE_WITHDRAWN_RECORDS_PRESENT" in item for item in stale.evidence)


def test_rehearsal_rejects_a_salt_below_the_minimum(tmp_path: Path) -> None:
    with pytest.raises(SecurityError):
        run_prospective_rehearsal(tmp_path / "workspace", salt="x" * (MIN_SALT_LENGTH - 1))


def test_rehearsal_rejects_a_naive_timestamp(tmp_path: Path) -> None:
    with pytest.raises(DatasetValidationError):
        run_prospective_rehearsal(
            tmp_path / "workspace",
            run_timestamp=datetime(2026, 5, 1, 12, 0),  # noqa: DTZ001 - deliberately naive
        )


def test_rehearsal_accepts_an_aware_timestamp_override(tmp_path: Path) -> None:
    report = run_prospective_rehearsal(
        tmp_path / "workspace",
        run_timestamp=datetime(2026, 6, 1, 8, 30, tzinfo=UTC),
    )
    assert report.run_timestamp == "2026-06-01T08:30:00+00:00"
    assert report.software_rehearsal_passed is True


# ── Gate and report contract (fail-closed) ─────────────────────────────────────


def test_gate_without_evidence_fails_closed() -> None:
    gate = RehearsalGate("example", "Example gate")

    assert gate.status is GateStatus.FAIL
    assert gate.is_complete is False
    assert "gate recorded no evidence (incomplete)" in gate.effective_failures()


def test_gate_with_a_failure_is_failed() -> None:
    gate = RehearsalGate("example", "Example gate").record("evidence").fail("boom")

    assert gate.status is GateStatus.FAIL
    assert "boom" in gate.to_dict()["failures"]


def test_gate_with_a_warning_is_warned() -> None:
    gate = RehearsalGate("example", "Example gate").record("evidence").warn("careful")

    assert gate.status is GateStatus.WARN
    assert gate.to_dict()["warnings"] == ["careful"]


def test_report_fails_when_gates_are_missing() -> None:
    report = RehearsalReport(
        run_id="REH_TEST",
        run_timestamp="2026-05-01T12:00:00+00:00",
        workspace="ws",
        gates=[],
    )

    assert report.overall_status is GateStatus.FAIL
    assert report.software_rehearsal_passed is False
    assert report.missing_gate_ids == list(REHEARSAL_GATE_ORDER)


def test_report_warns_when_a_gate_warns_but_none_fail() -> None:
    gates = [RehearsalGate(gid, gid).record("evidence") for gid in REHEARSAL_GATE_ORDER]
    gates[0].warn("soft warning")
    report = RehearsalReport(
        run_id="REH_TEST",
        run_timestamp="2026-05-01T12:00:00+00:00",
        workspace="ws",
        gates=gates,
    )

    assert report.overall_status is GateStatus.WARN
    assert report.software_rehearsal_passed is True
    assert "REAL-WORLD PILOT AUTHORIZED: NO" in report.readiness_statement


# ── CLI surface ────────────────────────────────────────────────────────────────


def test_cli_rehearsal_exits_zero_and_labels_synthetic(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "cli_ws"
    assert main(["prospective", "rehearsal", str(outdir)]) == 0

    out = capsys.readouterr().out
    assert "SYNTHETIC" in out
    assert "REAL-WORLD PILOT AUTHORIZED: NO" in out


def test_cli_rehearsal_json_is_parseable(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "cli_ws"
    assert main(["prospective", "rehearsal", str(outdir), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["software_rehearsal_passed"] is True
    assert payload["gate_count"] == len(REHEARSAL_GATE_ORDER)
    assert payload["real_world_pilot_authorized"] is False


def test_cli_rehearsal_rejects_a_naive_timestamp(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "cli_ws"
    exit_code = main(
        ["prospective", "rehearsal", str(outdir), "--timestamp", "2026-05-01T12:00:00"]
    )

    assert exit_code == 1
    assert "timezone offset" in capsys.readouterr().err


def test_cli_rehearsal_rejects_a_short_salt(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "cli_ws"
    exit_code = main(
        ["prospective", "rehearsal", str(outdir), "--salt", "too-short"]
    )

    assert exit_code == 1
    assert "Rehearsal could not start" in capsys.readouterr().err

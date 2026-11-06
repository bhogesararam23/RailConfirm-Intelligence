"""Unit and integration tests for the local operator service layer (ADR-0050)."""

from __future__ import annotations

from pathlib import Path

import pytest

from railconfirm.data.operator import (
    OperatorService,
    OperatorWorkspace,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError


def test_operator_workspace_initialization_and_listing(tmp_path: Path) -> None:
    ws_dir = tmp_path / "operator_workspace"
    ws = OperatorWorkspace(ws_dir)
    ws.initialize()

    assert ws.batches_dir.is_dir()
    assert ws.exports_dir.is_dir()
    assert ws.quarantine_dir.is_dir()
    assert ws.rehearsals_dir.is_dir()
    assert ws.list_batch_files() == []


def test_operator_service_lifecycle_seed_inspect_review_withdraw_export_reconcile(
    tmp_path: Path,
) -> None:
    service = OperatorService.from_directory(tmp_path / "op_ws")

    # 1. Status initially empty
    status = service.get_status()
    assert status["operator_enabled"] is True
    assert status["batches_count"] == 0
    assert status["is_synthetic_environment"] is True

    # 2. Seed synthetic fixture
    summary = service.seed_synthetic_fixture("BATCH_OP_001")
    assert summary.batch_id == "BATCH_OP_001"
    assert summary.total_submissions == 8
    assert summary.pending_count > 0

    # 3. List batches
    batches = service.list_batches()
    assert len(batches) == 1
    assert batches[0].batch_id == "BATCH_OP_001"

    # 4. Inspect batch
    inspection = service.inspect_batch("BATCH_OP_001")
    assert inspection.summary.batch_id == "BATCH_OP_001"
    assert inspection.pii_scan["passed"] is True
    assert inspection.pii_scan["findings_count"] == 0
    assert inspection.audit_report["total_submissions"] == 8
    assert len(inspection.submissions) == 8

    # 5. Review submission
    sub_id = inspection.submissions[0]["submission_id"]
    rev_result = service.review_submission(
        "BATCH_OP_001",
        submission_id=sub_id,
        action="approved",
        reviewer="lead_operator",
        rationale="Synthetic submission verified and approved for pilot simulation.",
    )
    assert rev_result.action == "approved"
    assert rev_result.reviewer == "lead_operator"
    assert rev_result.batch_summary.approved_count == 1

    # Also approve second submission
    sub_id_2 = inspection.submissions[1]["submission_id"]
    service.review_submission(
        "BATCH_OP_001",
        submission_id=sub_id_2,
        action="approved",
        reviewer="lead_operator",
        rationale="Synthetic submission approved.",
    )

    # 6. Preview export
    preview = service.preview_export("BATCH_OP_001")
    assert preview.batch_id == "BATCH_OP_001"
    assert preview.approved_count == 2
    assert preview.excluded_count == 6
    assert preview.booking_groups_count == 2

    # 7. Execute export
    export_res = service.execute_export("BATCH_OP_001")
    assert export_res.booking_groups_count == 2
    assert export_res.lineage_status == "verified_in_sync"
    assert Path(export_res.export_path).is_file()

    # 8. Inspect lineage (should be in sync)
    lineage = service.inspect_lineage("BATCH_OP_001")
    assert lineage.is_synced is True
    assert lineage.status == "verified_in_sync"
    assert lineage.source_sha256_matches is True
    assert lineage.withdrawn_groups_present == []

    # 9. Withdraw an approved submission (simulating post-export participant withdrawal)
    withdrawn = service.withdraw_submission(
        "BATCH_OP_001",
        submission_id=sub_id,
        reason="Participant requested deletion of ticket observations.",
        operator="lead_operator",
    )
    assert withdrawn.submission_id == sub_id
    assert withdrawn.audit_record["reason"] == "Participant requested deletion of ticket observations."

    # 10. Inspect lineage again (must now be STALE due to withdrawn records present)
    stale_lineage = service.inspect_lineage("BATCH_OP_001")
    assert stale_lineage.is_synced is False
    assert stale_lineage.status == "stale_withdrawn_records_present"
    assert len(stale_lineage.withdrawn_groups_present) == 1

    # 11. Reconcile export
    reconcile_res = service.reconcile_export("BATCH_OP_001")
    assert reconcile_res.reconciled_booking_groups == 1
    assert reconcile_res.lineage.is_synced is True
    assert reconcile_res.lineage.status == "verified_in_sync"
    assert reconcile_res.lineage.withdrawn_groups_present == []


def test_operator_service_review_validations(tmp_path: Path) -> None:
    service = OperatorService.from_directory(tmp_path / "op_ws")
    service.seed_synthetic_fixture("BATCH_VAL_001")

    # Reject non-existent batch
    with pytest.raises(DatasetValidationError) as exc_info:
        service.review_submission(
            "NON_EXISTENT",
            submission_id="SUB_001",
            action="approved",
            reviewer="op",
            rationale="rationale",
        )
    assert "not found" in str(exc_info.value)

    # Reject non-existent submission
    with pytest.raises(DatasetValidationError) as exc_info:
        service.review_submission(
            "BATCH_VAL_001",
            submission_id="SUB_DOES_NOT_EXIST",
            action="approved",
            reviewer="op",
            rationale="rationale",
        )
    assert "not found" in str(exc_info.value)

    # Reject empty reviewer
    with pytest.raises(DatasetValidationError) as exc_info:
        service.review_submission(
            "BATCH_VAL_001",
            submission_id="SUB_REH_001",
            action="approved",
            reviewer="   ",
            rationale="rationale",
        )
    assert "Reviewer identifier is required" in str(exc_info.value)

    # Reject empty rationale
    with pytest.raises(DatasetValidationError) as exc_info:
        service.review_submission(
            "BATCH_VAL_001",
            submission_id="SUB_REH_001",
            action="approved",
            reviewer="op",
            rationale="   ",
        )
    assert "Review rationale is required" in str(exc_info.value)

    # Reject invalid action
    with pytest.raises(DatasetValidationError) as exc_info:
        service.review_submission(
            "BATCH_VAL_001",
            submission_id="SUB_REH_001",
            action="invalid_action_name",
            reviewer="op",
            rationale="rationale",
        )
    assert "Invalid review action" in str(exc_info.value)


def test_operator_service_refuses_approval_of_personal_data(tmp_path: Path) -> None:
    service = OperatorService.from_directory(tmp_path / "op_ws")
    service.seed_synthetic_fixture("BATCH_PII_001")

    # Attempting to approve with personal data in rationale must raise SecurityError
    with pytest.raises(SecurityError) as exc_info:
        service.review_submission(
            "BATCH_PII_001",
            submission_id="SUB_REH_001",
            action="approved",
            reviewer="op",
            rationale="Passenger email is test.passenger@example.com for follow up.",
        )
    assert "personal data detected" in str(exc_info.value)


def test_operator_service_withdrawal_validations(tmp_path: Path) -> None:
    service = OperatorService.from_directory(tmp_path / "op_ws")
    service.seed_synthetic_fixture("BATCH_WITHDRAW_VAL")

    # Empty operator
    with pytest.raises(DatasetValidationError) as exc_info:
        service.withdraw_submission(
            "BATCH_WITHDRAW_VAL",
            submission_id="SUB_REH_001",
            reason="valid reason",
            operator="",
        )
    assert "Operator identifier is required" in str(exc_info.value)

    # Empty reason
    with pytest.raises(DatasetValidationError) as exc_info:
        service.withdraw_submission(
            "BATCH_WITHDRAW_VAL",
            submission_id="SUB_REH_001",
            reason="   ",
            operator="op",
        )
    assert "Withdrawal reason is required" in str(exc_info.value)


def test_operator_service_rehearsal_run_and_retrieve(tmp_path: Path) -> None:
    service = OperatorService.from_directory(tmp_path / "op_ws")

    assert service.get_latest_rehearsal() is None

    report = service.run_rehearsal()
    assert report.software_rehearsal_passed is True

    latest = service.get_latest_rehearsal()
    assert latest is not None
    assert latest["software_rehearsal_passed"] is True
    assert latest["gate_count"] == 15

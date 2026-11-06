"""Tests for operator API endpoints and security boundaries (ADR-0050)."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from railconfirm.api.app import create_app
from railconfirm.data.operator import OperatorService


@pytest.fixture
def test_operator_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "operator_test_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def test_operator_api_disabled_by_default() -> None:
    # Default app with no operator_enabled flag
    app = create_app()
    client = TestClient(app)

    response = client.get("/v1/operator/status")
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"] == "Operator mode is disabled. To enable locally, set RAILCONFIRM_OPERATOR_ENABLED=true."
    assert payload["details"][0]["code"] == "OPERATOR_DISABLED"


def test_operator_api_refuses_non_local_client(test_operator_ws: Path) -> None:
    service = OperatorService.from_directory(test_operator_ws)
    app = create_app(operator_enabled=True, operator_service=service)
    # Simulate an external client IP
    client = TestClient(app, client=("192.168.1.100", 54321))

    response = client.get("/v1/operator/status")
    assert response.status_code == 403
    payload = response.json()
    assert payload["details"][0]["code"] == "NON_LOCAL_ACCESS_FORBIDDEN"
    assert "192.168.1.100" in payload["error"]


def test_operator_api_lifecycle_and_security_controls(test_operator_ws: Path) -> None:
    service = OperatorService.from_directory(test_operator_ws)
    app = create_app(operator_enabled=True, operator_service=service)
    client = TestClient(app)

    # 1. Status endpoint
    status_resp = client.get("/v1/operator/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["operator_enabled"] is True
    assert status_data["batches_count"] == 0
    assert status_data["is_synthetic_environment"] is True

    # 2. Seed synthetic batch
    seed_resp = client.post("/v1/operator/batches/seed")
    assert seed_resp.status_code == 201
    batch_summary = seed_resp.json()
    batch_id = batch_summary["batch_id"]
    assert batch_summary["total_submissions"] == 8

    # 3. List batches
    list_resp = client.get("/v1/operator/batches")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["count"] == 1
    assert list_data["batches"][0]["batch_id"] == batch_id

    # 4. Inspect batch
    inspect_resp = client.get(f"/v1/operator/batches/{batch_id}")
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert inspect_data["summary"]["batch_id"] == batch_id
    assert inspect_data["pii_scan"]["passed"] is True
    assert len(inspect_data["submissions"]) == 8

    # 4b. Inspect non-existent batch gives 404
    missing_resp = client.get("/v1/operator/batches/NON_EXISTENT_BATCH")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["details"][0]["code"] == "BATCH_NOT_FOUND"

    # 5. Review submission - valid approval
    sub_id_1 = inspect_data["submissions"][0]["submission_id"]
    sub_id_2 = inspect_data["submissions"][1]["submission_id"]
    rev_resp = client.post(
        f"/v1/operator/batches/{batch_id}/review",
        json={
            "submission_id": sub_id_1,
            "action": "approved",
            "reviewer": "test_operator",
            "rationale": "Verified synthetic test record.",
        },
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["action"] == "approved"
    assert rev_data["batch_summary"]["approved_count"] == 1

    # Approve second submission
    client.post(
        f"/v1/operator/batches/{batch_id}/review",
        json={
            "submission_id": sub_id_2,
            "action": "approved",
            "reviewer": "test_operator",
            "rationale": "Second approved record.",
        },
    )

    # 5b. Review submission - PII in rationale rejected with 400
    pii_rev_resp = client.post(
        f"/v1/operator/batches/{batch_id}/review",
        json={
            "submission_id": inspect_data["submissions"][2]["submission_id"],
            "action": "approved",
            "reviewer": "test_operator",
            "rationale": "Passenger email is test.passenger@example.com for communication.",
        },
    )
    assert pii_rev_resp.status_code == 400
    assert pii_rev_resp.json()["details"][0]["code"] == "PERSONAL_DATA_DETECTED"

    # 6. Export preview
    preview_resp = client.get(f"/v1/operator/batches/{batch_id}/export-preview")
    assert preview_resp.status_code == 200
    prev_data = preview_resp.json()
    assert prev_data["approved_count"] == 2
    assert prev_data["booking_groups_count"] == 2

    # 7. Execute export
    export_resp = client.post(
        f"/v1/operator/batches/{batch_id}/export",
        json={"dataset_id": "TEST_DATASET_001"},
    )
    assert export_resp.status_code == 200
    exp_data = export_resp.json()
    assert exp_data["booking_groups_count"] == 2
    assert exp_data["lineage_status"] == "verified_in_sync"

    # 8. Check lineage
    lineage_resp = client.get(f"/v1/operator/batches/{batch_id}/lineage")
    assert lineage_resp.status_code == 200
    lin_data = lineage_resp.json()
    assert lin_data["is_synced"] is True
    assert lin_data["status"] == "verified_in_sync"

    # 9. Participant withdrawal
    withdraw_resp = client.post(
        f"/v1/operator/batches/{batch_id}/withdraw",
        json={
            "submission_id": sub_id_1,
            "reason": "Participant opted out via withdrawal request.",
            "operator": "test_operator",
        },
    )
    assert withdraw_resp.status_code == 200
    w_data = withdraw_resp.json()
    assert w_data["submission_id"] == sub_id_1
    assert w_data["batch_summary"]["withdrawn_count"] == 1

    # 10. Check lineage is now stale
    stale_lin_resp = client.get(f"/v1/operator/batches/{batch_id}/lineage")
    assert stale_lin_resp.status_code == 200
    stale_lin_data = stale_lin_resp.json()
    assert stale_lin_data["is_synced"] is False
    assert stale_lin_data["status"] == "stale_withdrawn_records_present"

    # 11. Reconcile export
    reconcile_resp = client.post(f"/v1/operator/batches/{batch_id}/reconcile")
    assert reconcile_resp.status_code == 200
    rec_data = reconcile_resp.json()
    assert rec_data["reconciled_booking_groups"] == 1
    assert rec_data["lineage"]["is_synced"] is True

    # 12. Run synthetic rehearsal via API
    rehearsal_resp = client.post(
        "/v1/operator/rehearsal/run",
        json={},
    )
    assert rehearsal_resp.status_code == 200
    reh_data = rehearsal_resp.json()
    assert reh_data["report"]["software_rehearsal_passed"] is True
    assert reh_data["report"]["gate_count"] == 15
    assert "REAL-WORLD PILOT AUTHORIZED: NO" in reh_data["summary_text"]

    # 13. Get latest rehearsal report
    latest_reh_resp = client.get("/v1/operator/rehearsal/latest")
    assert latest_reh_resp.status_code == 200
    assert latest_reh_resp.json()["software_rehearsal_passed"] is True


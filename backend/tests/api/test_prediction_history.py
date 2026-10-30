"""Prediction history over HTTP: opt-in, reopenable by internal id, bounded by retention.

The important behaviours are the ones a privacy claim depends on. Nothing is stored by
default; asking to store against a server that keeps no history says so instead of
pretending; a stored report reads back identical; and an id that looks like a PNR is not
an addressable report.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from railconfirm.api.app import create_app
from railconfirm.config import settings
from railconfirm.storage.predictions import PredictionStorageError, PredictionStore
from tests.conftest import valid_payload

MANUAL_URL = "/v1/predictions/manual"


def reopen_url(prediction_id: str) -> str:
    return f"/v1/predictions/{prediction_id}"


@pytest.fixture
def history(tmp_path):
    store = PredictionStore(tmp_path / "history" / "predictions.sqlite3", retention_days=7)
    yield store
    store.close()


@pytest.fixture
def client_with_history(history):
    with TestClient(create_app(prediction_store=history)) as client:
        yield client


@pytest.fixture
def client_without_history():
    with TestClient(create_app()) as client:
        yield client


def test_nothing_is_stored_unless_the_caller_asks(client_with_history, history):
    response = client_with_history.post(MANUAL_URL, json=valid_payload())
    assert response.status_code == 200, response.text
    assert response.json()["stored"] is False
    assert response.json()["report_url"] is None
    assert history.size == 0


def test_a_request_to_store_is_honoured_when_history_is_enabled(client_with_history, history):
    body = valid_payload(persist=True)
    response = client_with_history.post(MANUAL_URL, json=body)
    assert response.status_code == 200, response.text
    served = response.json()
    assert served["stored"] is True
    assert served["report_url"] == reopen_url(served["prediction_id"])
    assert served["retention_expires_at"] is not None
    assert history.size == 1


def test_a_stored_report_reads_back_with_the_numbers_it_was_served_with(
    client_with_history,
):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    reopened = client_with_history.get(served["report_url"])
    assert reopened.status_code == 200, reopened.text
    stored = reopened.json()
    # The stored report is what the user saw, not a re-computed one: the model version
    # and registry state are part of the claim.
    for field in (
        "prediction_id",
        "target",
        "prediction_at",
        "created_at",
        "model_version",
        "registry_status",
        "evidence_coverage",
        "is_supported",
        "passenger_count",
        "passenger_outcomes",
        "limitations",
        "outcome_classes",
    ):
        assert stored[field] == served[field], field
    assert stored["stored"] is True
    assert stored["retention_expires_at"] == served["retention_expires_at"]


def test_an_unknown_id_is_a_documented_not_found(client_with_history):
    response = client_with_history.get(reopen_url("11111111-2222-4333-8444-555555555555"))
    assert response.status_code == 404
    body = response.json()
    assert set(body) >= {"error", "details", "request_id"}
    assert body["request_id"]
    assert body["details"][0]["code"] == "not_found"


def test_a_pnr_shaped_id_is_not_an_addressable_report(client_with_history):
    response = client_with_history.get(reopen_url("2748391056"))
    assert response.status_code == 404
    assert "PNR" in response.json()["error"]
    # Asking by PNR must not become a ticket tracker, so nothing is looked up at all.
    assert response.json()["details"][0]["code"] == "not_found"


def test_a_server_without_history_says_so_instead_of_lying(client_without_history):
    served = client_without_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    assert served["stored"] is False
    assert any("keeps no prediction history" in item for item in served["limitations"])
    response = client_without_history.get(reopen_url(served["prediction_id"]))
    assert response.status_code == 404
    assert response.json()["details"][0]["code"] == "history_disabled"


def test_reopening_a_purged_report_is_not_found(client_with_history, history):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    assert history.purge_expired(now=datetime.now(UTC) + timedelta(days=8)) == 1
    response = client_with_history.get(served["report_url"])
    assert response.status_code == 404
    assert response.json()["details"][0]["code"] == "not_found"


def test_health_reports_whether_history_is_enabled(client_with_history, client_without_history):
    enabled = client_with_history.get("/v1/health").json()["prediction_history"]
    assert enabled == {"enabled": True, "retention_days": 7, "stored_reports": 0}
    assert client_without_history.get("/v1/health").json()["prediction_history"] == {}


def test_history_is_opened_only_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "persist_predictions", True)
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "prediction_retention_days", 14)
    app = create_app()
    store = app.state.prediction_store
    assert store is not None
    assert store.retention_days == 14
    assert (tmp_path / "storage" / "predictions.sqlite3").exists()
    app.state.prediction_store.close()


def test_the_default_configuration_keeps_no_history(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "persist_predictions", False)
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    app = create_app()
    assert app.state.prediction_store is None
    assert not (tmp_path / "storage").exists()


def test_a_storage_refusal_still_delivers_the_prediction(client_with_history, history, monkeypatch):
    """A save failure is a limitation on the report, never a lost or invented estimate."""

    def refuse(*args, **kwargs):
        raise PredictionStorageError("denied key(s) ['passenger_name']")

    monkeypatch.setattr(history, "save", refuse)
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    assert served["stored"] is False
    assert served["report_url"] is None
    assert any("was not stored" in item for item in served["limitations"])
    assert any("denied key" in item for item in served["limitations"])
    assert served["passenger_outcomes"][0]["abstention_reason"] == "no_trained_model"
    assert history.size == 0


def test_a_stored_report_survives_a_second_client_on_the_same_database(tmp_path):
    """One store instance is not the only reader: the file is the record."""
    path = tmp_path / "shared" / "predictions.sqlite3"
    first = PredictionStore(path, retention_days=7)
    try:
        with TestClient(create_app(prediction_store=first)) as client:
            served = client.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    finally:
        first.close()

    second = PredictionStore(path, retention_days=7)
    try:
        with TestClient(create_app(prediction_store=second)) as client:
            reopened = client.get(served["report_url"])
            assert reopened.status_code == 200, reopened.text
            assert reopened.json()["prediction_id"] == served["prediction_id"]
    finally:
        second.close()


# ── Listing what history holds ─────────────────────────────────────────────────


def test_the_list_is_empty_when_nothing_has_been_kept(client_with_history):
    response = client_with_history.get("/v1/predictions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"reports": [], "count": 0, "retention_days": 7}


def test_listing_requires_history_and_says_which_gate_is_closed(client_without_history):
    response = client_without_history.get("/v1/predictions")
    assert response.status_code == 404
    body = response.json()
    # An empty list would read as "nothing kept"; the answer must be "this server does
    # not keep reports at all", which is a different fact for a client to act on.
    assert body["error"] == "This server keeps no prediction history."
    assert body["details"][0]["code"] == "history_disabled"


def test_the_list_names_kept_reports_without_describing_them(client_with_history):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    listed = client_with_history.get("/v1/predictions")
    assert listed.status_code == 200, listed.text
    reports = listed.json()["reports"]
    assert len(reports) == 1 and listed.json()["count"] == 1
    report = reports[0]
    assert set(report) == {
        "prediction_id",
        "target",
        "model_version",
        "recorded_at",
        "retention_expires_at",
    }
    assert report["prediction_id"] == served["prediction_id"]
    assert report["target"] == served["target"]
    assert report["model_version"] == served["model_version"]
    assert report["retention_expires_at"] == served["retention_expires_at"]
    # The point of the narrow shape: a list must not carry ticket detail.
    text = listed.text
    for leak in ("p_cnf", "current_status", "train_number", "passenger", "limitations"):
        assert leak not in text, leak


def test_a_report_past_retention_is_listed_no_more_than_it_is_readable(
    client_with_history, history
):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    aged = datetime.now(UTC) - timedelta(days=8)
    history._connection.execute(
        "UPDATE predictions SET recorded_at = ?, expires_at = ? WHERE prediction_id = ?",
        (
            aged.isoformat(timespec="seconds"),
            (aged + timedelta(days=7)).isoformat(timespec="seconds"),
            served["prediction_id"],
        ),
    )
    history._connection.commit()
    assert client_with_history.get(served["report_url"]).status_code == 404
    assert client_with_history.get("/v1/predictions").json()["reports"] == []


def test_the_list_is_newest_first(client_with_history, history):
    """Retention is second-precise, so two saves in one second must still order cleanly."""
    now = datetime.now(UTC).replace(microsecond=0)
    for offset, identifier in ((120, "older-0000-0000-0000-000000000001"), (60, "older-0000-0000-0000-000000000002")):
        history.save(
            prediction_id=identifier,
            payload={
                "prediction_id": identifier,
                "target": "final_chart_cnf",
                "prediction_at": (now - timedelta(seconds=offset)).isoformat(),
                "model_version": "no_model_v0",
                "registry_status": "no_active_version",
                "evidence_coverage": "insufficient",
                "is_supported": False,
                "passenger_count": 0,
                "passenger_outcomes": [],
                "limitations": ["No trained model is available."],
            },
            target="final_chart_cnf",
            model_version="no_model_v0",
            prediction_at=now - timedelta(seconds=offset),
            recorded_at=now - timedelta(seconds=offset),
        )
    same_second = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    listed = client_with_history.get("/v1/predictions").json()["reports"]
    ids = [report["prediction_id"] for report in listed]
    assert ids[0] == same_second["prediction_id"]
    assert ids[1:] == ["older-0000-0000-0000-000000000002", "older-0000-0000-0000-000000000001"]
    # Repeated calls agree: a tied second must not make the list shuffle between views.
    assert ids == [
        report["prediction_id"]
        for report in client_with_history.get("/v1/predictions").json()["reports"]
    ]


# ── Deleting a kept report ─────────────────────────────────────────────────────


def test_delete_removes_the_report_and_leaves_nothing_to_reopen(client_with_history, history):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    deleted = client_with_history.delete(served["report_url"])
    assert deleted.status_code == 204, deleted.text
    # 204 carries no body: a deleted report must not be confirmable by reading it back.
    assert deleted.content == b""
    assert history.size == 0
    assert client_with_history.get(served["report_url"]).status_code == 404
    assert client_with_history.get("/v1/predictions").json()["reports"] == []


def test_deleting_requires_history(client_without_history):
    response = client_without_history.delete("/v1/predictions/whatever-1")
    assert response.status_code == 404
    assert response.json()["details"][0]["code"] == "history_disabled"


def test_an_unknown_id_and_a_second_delete_answer_identically(client_with_history):
    """No route may confirm which ids history once held."""
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    url = served["report_url"]
    assert client_with_history.delete(url).status_code == 204
    second = client_with_history.delete(url)
    never = client_with_history.delete("/v1/predictions/never-stored-0000-0000-0000-000000")
    assert second.status_code == never.status_code == 404
    assert second.json()["details"] == never.json()["details"]


def test_deleting_an_expired_report_answers_like_an_unknown_id(client_with_history, history):
    """Past retention is not a kept report, so DELETE must not confirm it existed (ADR-0015).

    The row is still cleared, but the answer is the same 404 an id that never existed
    receives: otherwise the route tells a caller which ids this machine once held.
    """
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    aged = datetime.now(UTC) - timedelta(days=8)
    history._connection.execute(
        "UPDATE predictions SET recorded_at = ?, expires_at = ? WHERE prediction_id = ?",
        (
            aged.isoformat(timespec="seconds"),
            (aged + timedelta(days=7)).isoformat(timespec="seconds"),
            served["prediction_id"],
        ),
    )
    history._connection.commit()
    assert client_with_history.get(served["report_url"]).status_code == 404

    expired = client_with_history.delete(served["report_url"])
    never = client_with_history.delete("/v1/predictions/never-stored-0000-0000-0000-000000")
    assert expired.status_code == 404
    assert expired.json()["details"] == never.json()["details"]
    # The expired row is cleared without being confirmed; retention and deletion agree.
    assert history.size == 0


@pytest.mark.parametrize("method", ["get", "delete"])
def test_a_pnr_shaped_id_is_not_an_address_on_any_history_route(client_with_history, method):
    response = getattr(client_with_history, method)("/v1/predictions/1234567890")
    assert response.status_code == 404
    detail = response.json()["details"][0]
    assert detail["code"] == "not_found"
    assert "internal id" in detail["message"]


def test_deleting_one_report_leaves_the_other_reports_readable(client_with_history):
    first = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    second = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    assert client_with_history.delete(first["report_url"]).status_code == 204
    reopened = client_with_history.get(second["report_url"])
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["prediction_id"] == second["prediction_id"]
    assert client_with_history.get("/v1/predictions").json()["count"] == 1


def test_a_row_the_store_cannot_explain_answers_with_the_storage_envelope(
    client_with_history, history
):
    served = client_with_history.post(MANUAL_URL, json=valid_payload(persist=True)).json()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat(timespec="seconds")
    # A row that is still inside retention but whose clocks contradict each other: the
    # store must refuse it loudly instead of listing a report it cannot explain.
    assert history.get(served["prediction_id"], now=datetime.now(UTC)) is not None
    history._connection.execute(
        "UPDATE predictions SET recorded_at = ?, expires_at = ?", (future, future)
    )
    history._connection.commit()
    response = client_with_history.get("/v1/predictions")
    assert response.status_code == 500
    detail = response.json()["details"][0]
    assert detail["code"] == "storage_unavailable"
    assert "before it was recorded" in detail["message"]

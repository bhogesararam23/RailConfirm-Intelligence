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

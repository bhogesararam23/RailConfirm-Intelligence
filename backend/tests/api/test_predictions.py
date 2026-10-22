"""API tests for POST /v1/predictions/manual endpoint."""

from fastapi.testclient import TestClient


def test_predict_manual_synthetic_booking(client: TestClient, synthetic_booking_data: dict):
    # Remove metadata keys before posting to the API
    payload = {
        "journey": synthetic_booking_data["journey"],
        "prediction_at": synthetic_booking_data["prediction_at"],
        "passengers": synthetic_booking_data["passengers"],
    }
    response = client.post("/v1/predictions/manual", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "prediction_id" in data
    assert "target_definition" in data
    assert data["model_version"] == "no_model_v0"
    assert data["evidence_coverage"] == "insufficient"
    assert len(data["passenger_outcomes"]) == 2

    # Nothing is promoted in the registry, so the blocking gate is reported as a
    # missing trained model and the registry status is spelled out in limitations.
    for outcome in data["passenger_outcomes"]:
        assert outcome["is_supported"] is False
        assert outcome["abstention_reason"] == "no_trained_model"
        assert outcome["p_cnf"] is None
        assert outcome["basis"] is None

    # Group outcome must also abstain
    assert data["group_outcome"]["is_supported"] is False
    assert data["group_outcome"]["abstention_reason"] == "no_trained_model"

    # Limitations must clearly state no model is available and why
    assert len(data["limitations"]) > 0
    assert any("no model version is configured" in text.lower() for text in data["limitations"])
    assert any("no_active_version" in text for text in data["limitations"])


def test_predict_manual_invalid_stations(client: TestClient):
    payload = {
        "journey": {
            "train_number": "12301",
            "journey_date": "2026-11-15",
            "boarding_station": "NDLS",
            "destination_station": "NDLS",  # Same station
            "class_code": "SL",
            "quota_code": "GN",
        },
        "passengers": [
            {
                "original_status": "GNWL/1",
                "current_status": "GNWL/1",
            }
        ],
    }
    response = client.post("/v1/predictions/manual", json=payload)
    # Validation error from domain journey or pydantic
    assert response.status_code in (400, 422)


def test_predict_manual_empty_passengers(client: TestClient):
    payload = {
        "journey": {
            "train_number": "12301",
            "journey_date": "2026-11-15",
            "boarding_station": "NDLS",
            "destination_station": "HWH",
            "class_code": "SL",
            "quota_code": "GN",
        },
        "passengers": [],
    }
    response = client.post("/v1/predictions/manual", json=payload)
    assert response.status_code == 422

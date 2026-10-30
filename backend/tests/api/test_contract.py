"""API contract tests: error envelope, temporal rules, limits and injection.

These assert the shape the frontend and any later client depend on.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from railconfirm.config import settings
from railconfirm.inference.engine import InferenceEngine
from railconfirm.inference.registry import ModelRegistry
from tests.conftest import OBSERVED_AT, valid_payload
from tests.support.artifacts import write_fixture_artifact as write

PREDICTION_URL = "/v1/predictions/manual"


def field_errors(response) -> dict[str, str]:
    """Map dotted field path -> message from the documented error envelope."""
    body = response.json()
    assert set(body) >= {"error", "details"}, body
    return {d["field"]: d["message"] for d in body["details"]}


# ── Happy path and contract fields ─────────────────────────────────────────────


def test_manual_prediction_contract_fields(client: TestClient):
    response = client.post(PREDICTION_URL, json=valid_payload())
    assert response.status_code == 200, response.text
    body = response.json()

    for key in (
        "prediction_id",
        "target",
        "target_definition",
        "prediction_at",
        "created_at",
        "model_version",
        "registry_status",
        "feature_schema_version",
        "evidence_coverage",
        "is_supported",
        "passenger_count",
        "passenger_outcomes",
        "group_outcome",
        "limitations",
        "warnings",
        "outcome_classes",
    ):
        assert key in body, f"missing {key}"

    assert body["target"] == "final_chart_cnf"
    assert body["registry_status"] == "no_active_version"
    assert body["evidence_coverage"] == "insufficient"
    assert body["passenger_count"] == 1
    assert body["prediction_at"].startswith("2026-10-21T08:00:00")
    assert body["passenger_outcomes"][0]["basis"] is None


def test_response_echoes_the_requested_target(client: TestClient):
    payload = valid_payload(target="final_chart_cnf_or_rac")
    response = client.post(PREDICTION_URL, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["target"] == "final_chart_cnf_or_rac"
    # Nothing is fitted for this target, so no number may appear.
    assert all(o["p_cnf"] is None for o in body["passenger_outcomes"])


def test_the_definition_describes_the_event_the_target_names(client: TestClient):
    """A report that names one question and describes another is not a contract.

    The served definition used to describe the full five-class distribution whatever the
    target was, so a `final_chart_cnf_or_rac` request was captioned with the confirmed
    question. Each answer now names the event its own classes cover.
    """
    definitions = {
        target: client.post(PREDICTION_URL, json=valid_payload(target=target))
        .json()["target_definition"]
        for target in ("final_chart_cnf", "final_chart_cnf_or_rac")
    }
    confirmed = definitions["final_chart_cnf"]
    merged = definitions["final_chart_cnf_or_rac"]
    assert "confirmed (CNF)" in confirmed
    assert "RAC" not in confirmed
    assert "CNF" in merged and "RAC" in merged
    assert merged != confirmed


def test_an_abstaining_outcome_publishes_no_target_event_probability(client: TestClient):
    body = client.post(PREDICTION_URL, json=valid_payload()).json()
    for outcome in body["passenger_outcomes"]:
        assert "p_target_event" in outcome
        assert outcome["p_target_event"] is None


def test_rejected_target_value_is_a_validation_error(client: TestClient):
    response = client.post(PREDICTION_URL, json=valid_payload(target="departure_cnf"))
    assert response.status_code == 422
    assert "target" in field_errors(response)


def test_original_and_current_status_are_kept_separate(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0] = {
        "original_status": "GNWL/45",
        "current_status": "CNF",
        "current_status_observed_at": OBSERVED_AT.isoformat(),
    }
    outcome = client.post(PREDICTION_URL, json=payload).json()["passenger_outcomes"][0]
    assert outcome["original_status"] == "GNWL/45"
    assert outcome["original_status_normalized"] == "WL"
    assert outcome["current_status"] == "CNF"
    assert outcome["current_status_normalized"] == "CNF"


def test_parse_note_surfaces_as_a_parse_warning(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0]["current_status"] = "WL/0"
    outcome = client.post(PREDICTION_URL, json=payload).json()["passenger_outcomes"][0]
    assert any("position" in note.lower() for note in outcome["parse_warnings"])


def test_unknown_status_is_reported_not_mapped(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0]["current_status"] = "CK"
    body = client.post(PREDICTION_URL, json=payload).json()
    outcome = body["passenger_outcomes"][0]
    assert outcome["current_status_normalized"] == "UNKNOWN"
    assert outcome["abstention_reason"] == "unknown_status"
    assert outcome["p_cnf"] is None
    assert any("CK" in warning for warning in body["warnings"])


def test_injected_ready_artifact_serves_estimates_through_the_api(
    make_client, tmp_path
):
    write(tmp_path)
    engine = InferenceEngine(
        registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")
    )
    response = make_client(engine).post(PREDICTION_URL, json=valid_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["registry_status"] == "ready"
    assert body["model_version"] == "fixture_v1"
    assert body["evidence_coverage"] == "sufficient"
    outcome = body["passenger_outcomes"][0]
    assert outcome["is_supported"] is True
    assert outcome["basis"] == "cohort=SL/GN/WL n=105 exact_status_match=true"
    assert body["group_outcome"]["method"] == "single_passenger"
    # The target's event is published beside the distribution, so a client shows the
    # figure the evaluation scores instead of adding classes itself.
    assert outcome["p_target_event"] == pytest.approx(outcome["p_cnf"])


def test_a_merged_target_serves_confirmed_or_rac_as_its_event(make_client, tmp_path):
    """`final_chart_cnf_or_rac` must answer with CNF plus RAC, not with confirmed alone."""
    write(tmp_path, target="final_chart_cnf_or_rac")
    engine = InferenceEngine(
        registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")
    )
    body = make_client(engine).post(
        PREDICTION_URL, json=valid_payload(target="final_chart_cnf_or_rac")
    ).json()
    outcome = body["passenger_outcomes"][0]
    assert body["registry_status"] == "ready"
    assert outcome["is_supported"] is True
    assert outcome["p_target_event"] == pytest.approx(outcome["p_cnf"] + outcome["p_rac"])
    assert outcome["p_target_event"] > outcome["p_cnf"]


# ── Temporal rules at the boundary ─────────────────────────────────────────────


def test_naive_prediction_at_is_rejected(client: TestClient):
    response = client.post(
        PREDICTION_URL, json=valid_payload(prediction_at="2026-10-21T08:00:00")
    )
    assert response.status_code == 422
    assert "no timezone offset" in field_errors(response)["prediction_at"]


def test_validation_messages_do_not_carry_python_prefixes(client: TestClient):
    """"Value error, ..." is a Python artefact, not something a client can act on."""
    response = client.post(
        PREDICTION_URL, json=valid_payload(prediction_at="2026-10-21T08:00:00")
    )
    for message in field_errors(response).values():
        assert not message.startswith(("Value error, ", "Assertion failed, "))


def test_naive_observation_timestamp_is_rejected(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0]["current_status_observed_at"] = "2026-10-21T07:30:00"
    response = client.post(PREDICTION_URL, json=payload)
    assert response.status_code == 422
    assert any(
        path.endswith("current_status_observed_at") for path in field_errors(response)
    )


def test_prediction_on_or_after_journey_date_is_rejected(client: TestClient):
    response = client.post(
        PREDICTION_URL, json=valid_payload(prediction_at="2026-11-15T06:00:00+00:00")
    )
    assert response.status_code == 422
    body = response.json()
    assert body["details"][0]["code"] == "INVALID_PREDICTION_AT"
    assert "on or after journey date" in body["details"][0]["message"]


def test_evidence_newer_than_prediction_at_is_rejected(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0]["current_status_observed_at"] = "2026-10-21T09:00:00+00:00"
    response = client.post(PREDICTION_URL, json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["details"][0]["code"] == "INVALID_PREDICTION_AT"
    assert "leak the outcome" in body["details"][0]["message"]


def test_observed_at_may_be_omitted(client: TestClient):
    payload = valid_payload()
    del payload["passengers"][0]["current_status_observed_at"]
    assert client.post(PREDICTION_URL, json=payload).status_code == 200


# ── Input limits and validation shape ──────────────────────────────────────────


def test_more_passengers_than_the_documented_limit_is_rejected(client: TestClient):
    passenger = {
        "original_status": "GNWL/10",
        "current_status": "GNWL/5",
        "current_status_observed_at": OBSERVED_AT.isoformat(),
    }
    response = client.post(
        PREDICTION_URL,
        json=valid_payload(passengers=[passenger] * 7),
    )
    assert response.status_code == 422
    assert "passengers" in field_errors(response)


@pytest.mark.parametrize("status", ["", "   "])
def test_blank_status_is_rejected_at_the_boundary(client: TestClient, status):
    payload = valid_payload()
    payload["passengers"][0]["current_status"] = status
    response = client.post(PREDICTION_URL, json=payload)
    assert response.status_code == 422
    assert any(path.endswith("current_status") for path in field_errors(response))


def test_oversized_status_string_is_rejected(client: TestClient):
    payload = valid_payload()
    payload["passengers"][0]["current_status"] = "GNWL/" + "9" * 400
    assert client.post(PREDICTION_URL, json=payload).status_code == 422


@pytest.mark.parametrize(
    "journey_patch,expected_field",
    [
        ({"train_number": "123"}, "journey.train_number"),
        ({"train_number": "12A01"}, "journey.train_number"),
        ({"boarding_station": "N"}, "journey.boarding_station"),
        ({"boarding_station": "NDLS!"}, "journey.boarding_station"),
        ({"boarding_station": "NDLS", "destination_station": "NDLS"}, "journey"),
        ({"journey_date": "15/11/2026"}, "journey.journey_date"),
    ],
)
def test_invalid_journey_fields_report_their_path(
    client: TestClient, journey_patch, expected_field
):
    payload = valid_payload()
    payload["journey"].update(journey_patch)
    response = client.post(PREDICTION_URL, json=payload)
    assert response.status_code == 422
    assert expected_field in field_errors(response)


def test_body_above_the_declared_limit_gets_413(make_client):
    client = make_client()
    response = client.post(
        PREDICTION_URL,
        content=b"{" + b'"a":1,' * 20000 + b'"x":1}',
        headers={"Content-Type": "application/json", "Content-Length": "120000"},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["details"][0]["code"] == "REQUEST_TOO_LARGE"


def test_malformed_content_length_is_a_bad_request(make_client):
    client = make_client()
    response = client.post(
        PREDICTION_URL,
        json=valid_payload(),
        headers={"Content-Length": "abc"},
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["code"] == "invalid_input"


# ── Operational surface ────────────────────────────────────────────────────────


def test_request_id_is_returned_and_echoed(client: TestClient):
    first = client.get("/v1/health")
    assert first.headers["X-Request-ID"]
    second = client.get("/v1/health", headers={"X-Request-ID": "trace-abc"})
    assert second.headers["X-Request-ID"] == "trace-abc"


def test_error_envelope_carries_the_request_id(client: TestClient):
    response = client.get("/v1/health", headers={"X-Request-ID": "trace-42"})
    bad = client.post(PREDICTION_URL, json={}, headers={"X-Request-ID": "trace-42"})
    assert bad.status_code == 422
    assert bad.json()["request_id"] == "trace-42"
    assert response.headers["X-Request-ID"] == "trace-42"


def test_an_unrouted_path_answers_with_the_envelope_not_starlette(client: TestClient):
    """The contract says every error is an envelope; a 404 is the commonest error.

    `/v1/predictions/{id}` is a real route, so an unrouted path has to sit outside
    it — otherwise this asserts the history endpoint rather than the router.
    """
    response = client.get("/v1/reportings")
    assert response.status_code == 404
    body = response.json()
    assert set(body) >= {"error", "details", "request_id"}
    assert body["details"][0]["code"] == "not_found"
    assert "detail" not in body


def test_a_wrong_method_answers_with_the_envelope_too(client: TestClient):
    response = client.delete("/v1/health")
    assert response.status_code == 405
    body = response.json()
    assert set(body) >= {"error", "details", "request_id"}
    assert body["details"][0]["code"] == "invalid_input"


def test_health_reports_no_history_by_default(client: TestClient):
    assert client.get("/v1/health").json()["prediction_history"] == {}


def test_health_reports_registry_state_and_limits(client: TestClient):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert body["model_available"] is False
    assert body["registry_status"] == "no_active_version"
    assert body["limits"]["max_passengers_per_request"] == 6
    assert body["limits"]["min_sample_threshold"] == settings.min_sample_threshold


def test_health_reports_available_when_artifact_is_ready(make_client, tmp_path):
    write(tmp_path, min_sample_threshold=17)
    engine = InferenceEngine(
        registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")
    )
    body = make_client(engine).get("/v1/health").json()
    assert body["model_available"] is True
    assert body["registry_status"] == "ready"
    assert body["model_version"] == "fixture_v1"
    # The threshold that governs the next prediction is the artifact's own, not
    # the fallback baseline's.
    assert body["limits"]["min_sample_threshold"] == 17


def test_unhandled_error_does_not_leak_exception_text(make_client):
    class ExplodingEngine(InferenceEngine):
        def predict(self, *args, **kwargs):  # type: ignore[override]
            raise RuntimeError("passenger secret status GNWL/12")

    client = make_client(ExplodingEngine(), raise_server_exceptions=False)
    response = client.post(PREDICTION_URL, json=valid_payload())
    assert response.status_code == 500
    body = response.json()
    assert "secret" not in json.dumps(body)
    assert body["details"][0]["code"] == "INTERNAL_ERROR"
    assert body["request_id"]


# ── CORS ───────────────────────────────────────────────────────────────────────


def test_preflight_from_configured_origin_is_allowed(client: TestClient):
    response = client.options(
        PREDICTION_URL,
        headers={
            "Origin": settings.cors_allowed_origins[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.cors_allowed_origins[0]


def test_preflight_from_an_unconfigured_origin_gets_no_allow_header(client: TestClient):
    response = client.options(
        PREDICTION_URL,
        headers={
            "Origin": "https://not-allowed.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_openapi_documents_the_verified_fields(client: TestClient):
    schema = client.get("/openapi.json").json()
    request_body = schema["paths"]["/v1/predictions/manual"]["post"]["requestBody"]
    ref = request_body["content"]["application/json"]["schema"]["$ref"]
    name = ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][name]["properties"]
    assert set(props) == {"journey", "prediction_at", "target", "passengers", "persist"}
    assert "basis" in schema["components"]["schemas"]["PassengerOutcomeResponse"]["properties"]
    assert (
        "p_target_event"
        in schema["components"]["schemas"]["PassengerOutcomeResponse"]["properties"]
    )
    response_props = schema["components"]["schemas"]["PredictionResponse"]["properties"]
    assert "registry_status" in response_props
    for field in ("stored", "report_url", "retention_expires_at"):
        assert field in response_props, field
    assert "/v1/predictions/{prediction_id}" in schema["paths"]
    assert "prediction_history" in schema["components"]["schemas"]["HealthResponse"]["properties"]

    # History listing and deletion are part of the contract, so their shape is pinned
    # here: the frontend types are written against exactly these fields.
    assert "get" in schema["paths"]["/v1/predictions"], "GET /v1/predictions is undocumented"
    assert "delete" in schema["paths"]["/v1/predictions/{prediction_id}"]
    list_props = schema["components"]["schemas"]["StoredReportsResponse"]["properties"]
    assert set(list_props) == {"reports", "count", "retention_days"}
    summary_props = schema["components"]["schemas"]["StoredReportSummary"]["properties"]
    assert set(summary_props) == {
        "prediction_id",
        "target",
        "model_version",
        "recorded_at",
        "retention_expires_at",
    }
    delete_responses = schema["paths"]["/v1/predictions/{prediction_id}"]["delete"]["responses"]
    # A deleted report answers with nothing at all, so nothing can be read back.
    assert "204" in delete_responses
    assert not delete_responses["204"].get("content")

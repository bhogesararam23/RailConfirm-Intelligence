"""Engine behaviour across registry states.

Regression cover for the contradiction where the registry reported an active model
version while every passenger abstained with ``no_trained_model``.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import make_observation
from railconfirm.domain.prediction import AbstentionReason, PredictionTarget
from railconfirm.inference.engine import InferenceEngine
from railconfirm.inference.registry import ModelRegistry
from tests.support.artifacts import write_fixture_artifact as write

JOURNEY = make_journey(
    train_number="12301",
    journey_date=date(2026, 11, 15),
    boarding_station="NDLS",
    destination_station="HWH",
    class_code="SL",
    quota_code="GN",
)

# Fixed in the past so observation time stays behind ingestion time as tests run.
AS_OF = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 10, 21, 7, 30, tzinfo=UTC)


def inputs(raw="GNWL/12", observed_at=OBSERVED_AT, passenger_id="p-1"):
    obs = make_observation(
        raw,
        source="fixture",
        observed_at=observed_at,
        ingested_at=AS_OF,
    )
    return [{"passenger_id": passenger_id, "original_obs": obs, "current_obs": obs}]


def predict(engine: InferenceEngine, passenger_inputs=None, **kwargs):
    return engine.predict(
        JOURNEY,
        inputs() if passenger_inputs is None else passenger_inputs,
        prediction_at=AS_OF,
        **kwargs,
    )


def test_ready_artifact_yields_supported_estimates(tmp_path: Path):
    write(tmp_path)
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))

    outcome = record.passenger_outcomes[0]
    assert outcome.is_supported()
    assert outcome.p_cnf == pytest.approx(71 / 110)
    assert record.model_version == "fixture_v1"
    assert record.feature_schema_version == "1.0.0"
    assert record.evidence_coverage == "sufficient"
    assert record.prediction_at == AS_OF
    assert "Synthetic fixture artifact" in record.limitations[0]


def test_ready_artifact_reports_its_own_feature_schema(tmp_path: Path):
    write(tmp_path, feature_schema_version="2.3.0")
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))
    assert record.feature_schema_version == "2.3.0"


def test_broken_artifact_is_reported_as_invalid_not_absent(tmp_path: Path):
    (tmp_path / "fixture_v1.json").write_text("{{{ not json", encoding="utf-8")
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))

    assert record.passenger_outcomes[0].abstention_reason is AbstentionReason.MODEL_ARTIFACT_INVALID
    assert record.model_version == "no_model_v0"
    assert any("artifact_invalid" in text for text in record.limitations)


def test_unapproved_training_data_is_reported_as_missing_data(tmp_path: Path):
    write(tmp_path, data_approval_status="quarantined")
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))

    assert record.passenger_outcomes[0].abstention_reason is AbstentionReason.NO_APPROVED_DATA
    assert record.model_version == "no_model_v0"
    assert any("data_not_approved" in text for text in record.limitations)


def test_target_mismatch_does_not_serve_a_different_question(tmp_path: Path):
    """An artifact for CNF must not answer a CNF-or-RAC request."""
    write(tmp_path)
    registry = ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")
    resolution = registry.resolve(PredictionTarget.FINAL_CHART_CNF_OR_RAC)
    assert resolution.abstention_reason is AbstentionReason.MODEL_ARTIFACT_INVALID

    record = predict(
        InferenceEngine(registry=registry),
        target=PredictionTarget.FINAL_CHART_CNF_OR_RAC,
    )
    assert not record.passenger_outcomes[0].is_supported()


def test_unknown_status_still_wins_over_a_ready_artifact(tmp_path: Path):
    write(tmp_path)
    record = predict(
        InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")),
        passenger_inputs=inputs(raw="NOT_A_STATUS"),
    )
    assert record.passenger_outcomes[0].abstention_reason is AbstentionReason.UNKNOWN_STATUS
    assert record.warnings


def test_mixed_support_reports_partial_coverage(tmp_path: Path):
    """Regression: partial support was reported as a flat 'insufficient'."""
    write(tmp_path)
    engine = InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1"))
    record = predict(
        engine,
        passenger_inputs=[
            inputs(raw="GNWL/12", passenger_id="p-ok")[0],
            inputs(raw="NOT_A_STATUS", passenger_id="p-bad")[0],
        ],
    )
    assert record.evidence_coverage == "partial"
    assert record.is_fully_supported is False
    assert any("1 of 2" in text for text in record.warnings)
    # A group estimate cannot be built while one member abstains.
    assert record.group_outcome.abstention_reason is AbstentionReason.UNKNOWN_STATUS

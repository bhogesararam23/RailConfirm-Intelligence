"""Engine behaviour across registry states.

Regression cover for the contradiction where the registry reported an active model
version while every passenger abstained with ``no_trained_model``.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import make_observation
from railconfirm.domain.prediction import (
    FEATURE_SCHEMA_VERSION,
    AbstentionReason,
    PredictionTarget,
)
from railconfirm.domain.status import MAPPING_VERSION
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
    assert record.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert record.evidence_coverage == "sufficient"
    assert record.prediction_at == AS_OF
    assert "Synthetic fixture artifact" in record.limitations[0]


def test_an_artifact_fitted_under_another_feature_schema_is_refused(tmp_path: Path):
    """A schema version the build does not derive is a refusal, not a label to echo.

    The declaration used to be checked only for being a non-empty string, so an artifact
    fitted under schema ``2.3.0`` — a version this build has never had — loaded and served,
    and the record repeated the claim back. Its cohorts were keyed from whatever as-of
    derivation that build applied, which is the population a lookup here does not reach.
    """
    write(tmp_path, feature_schema_version="2.3.0")
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))

    assert record.model_version == "no_model_v0"
    assert record.passenger_outcomes[0].abstention_reason is AbstentionReason.MODEL_ARTIFACT_INVALID
    assert any("artifact_invalid" in text for text in record.limitations)
    assert any("2.3.0" in text and FEATURE_SCHEMA_VERSION in text for text in record.limitations)


def test_an_artifact_fitted_under_another_status_mapping_is_refused(tmp_path: Path):
    """The cohort key's third part is the normalized status, so its mapping is a contract."""
    write(tmp_path, status_mapping_version="0.9.0")
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))

    assert record.passenger_outcomes[0].abstention_reason is AbstentionReason.MODEL_ARTIFACT_INVALID
    assert any("0.9.0" in text and MAPPING_VERSION in text for text in record.limitations)


def test_an_abstention_reports_the_feature_schema_the_build_applies(tmp_path: Path):
    """With no artifact, the record still names the contract its inputs were derived under.

    The value was a literal ``"1.0.0"`` in two places — the record default and the engine's
    no-model branch — while the build had moved to 3.0.0, so every abstained prediction
    claimed a feature schema that no longer existed.
    """
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path)))

    assert record.model_version == "no_model_v0"
    assert record.feature_schema_version == FEATURE_SCHEMA_VERSION


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


# ── The calibration layer at serving time ──────────────────────────────────────

CALIBRATION = {
    "method": "platt_logistic_v1",
    "target": "final_chart_cnf",
    "event_classes": ["CNF"],
    "slope": 1.0,
    "intercept": 0.0,
    "fitted_partition": "validation",
    "fitted_rows": 120,
    "fitted_from": "2026-01-01",
    "fitted_to": "2026-06-30",
}
# Raw fixture cell: CNF 70, RAC 20, WL 10, CANCELLED 5, OTHER 0 → denominator 110.
RAW_P_CNF = 71 / 110


def test_an_identity_calibration_leaves_the_numbers_and_marks_the_basis(tmp_path: Path):
    write(tmp_path, calibrated=True, calibration=CALIBRATION)
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))
    outcome = record.passenger_outcomes[0]
    assert outcome.p_cnf == pytest.approx(RAW_P_CNF)
    assert "calibrated=platt_logistic_v1" in outcome.basis
    assert any("Probabilities are calibrated" in text for text in record.limitations)
    assert not any("are not calibrated" in text for text in record.limitations)


def test_a_flat_calibration_moves_the_event_mass_and_everything_sums_to_one(tmp_path: Path):
    """Slope 0, intercept 0: every prediction becomes 0.5, and the rest rescales."""
    write(tmp_path, calibrated=True, calibration={**CALIBRATION, "slope": 0.0})
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))
    outcome = record.passenger_outcomes[0]
    assert outcome.p_cnf == pytest.approx(0.5)
    assert sum(
        [outcome.p_cnf, outcome.p_rac, outcome.p_wl, outcome.p_cancelled, outcome.p_other]
    ) == pytest.approx(1.0)
    # The non-event classes keep their ratios: 20/10/5/0 scaled by (1-0.5)/(1-p_cnf_raw).
    outside = (1.0 - 0.5) / (1.0 - RAW_P_CNF)
    assert outcome.p_rac == pytest.approx((21 / 110) * outside)
    assert outcome.p_wl == pytest.approx((11 / 110) * outside)


def test_the_group_estimate_is_built_from_the_calibrated_probabilities(tmp_path: Path):
    write(tmp_path, calibrated=True, calibration={**CALIBRATION, "slope": 0.0})
    engine = InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1"))
    record = engine.predict(
        JOURNEY,
        [
            inputs(raw="GNWL/12", passenger_id="p-1")[0],
            inputs(raw="GNWL/13", passenger_id="p-2")[0],
        ],
        prediction_at=AS_OF,
    )
    assert record.passenger_outcomes[0].p_cnf == pytest.approx(0.5)
    assert record.group_outcome.p_all_cnf == pytest.approx(0.25)
    assert record.group_outcome.method == "independence_baseline"


def test_an_uncalibrated_artifact_still_says_the_numbers_are_uncalibrated(tmp_path: Path):
    write(tmp_path)
    record = predict(InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")))
    assert any(
        "Probabilities are not calibrated" in text for text in record.limitations
    )
    assert "calibrated=" not in (record.passenger_outcomes[0].basis or "")


def test_an_abstention_is_not_rescaled_into_a_number(tmp_path: Path):
    """Calibration corrects probabilities; it does not manufacture one."""
    write(tmp_path, calibrated=True, calibration={**CALIBRATION, "slope": 0.0})
    record = predict(
        InferenceEngine(registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")),
        passenger_inputs=inputs(raw="NOT_A_STATUS"),
    )
    outcome = record.passenger_outcomes[0]
    assert outcome.p_cnf is None
    assert outcome.basis is None

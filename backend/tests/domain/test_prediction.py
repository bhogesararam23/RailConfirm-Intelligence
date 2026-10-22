"""Unit tests for prediction records, probabilities, and abstention types."""

from datetime import UTC, datetime

import pytest

from railconfirm.domain.exceptions import TemporalIntegrityError
from railconfirm.domain.prediction import (
    AbstentionReason,
    PassengerOutcome,
    PredictionRecord,
    PredictionTarget,
    make_abstention_outcome,
)

PREDICTION_AT = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)


def test_supported_passenger_outcome_valid():
    outcome = PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.6,
        p_rac=0.2,
        p_wl=0.1,
        p_cancelled=0.05,
        p_other=0.05,
        abstention_reason=None,
    )
    assert outcome.is_supported() is True
    assert outcome.p_cnf == 0.6


def test_supported_passenger_outcome_sum_violation():
    with pytest.raises(ValueError, match="must sum to 1.0"):
        PassengerOutcome(
            passenger_id="p-1",
            p_cnf=0.8,
            p_rac=0.5,  # Sum exceeds 1.0
            p_wl=0.0,
            p_cancelled=0.0,
            p_other=0.0,
            abstention_reason=None,
        )


def test_abstention_passenger_outcome():
    outcome = make_abstention_outcome(
        passenger_id="p-2",
        reason=AbstentionReason.NO_TRAINED_MODEL,
    )
    assert outcome.is_supported() is False
    assert outcome.abstention_reason == AbstentionReason.NO_TRAINED_MODEL
    assert outcome.p_cnf is None
    assert outcome.p_rac is None


def test_prediction_record():
    p1 = make_abstention_outcome("p-1", AbstentionReason.NO_TRAINED_MODEL)
    record = PredictionRecord(
        target=PredictionTarget.FINAL_CHART_CNF,
        prediction_at=PREDICTION_AT,
        passenger_outcomes=[p1],
        evidence_coverage="insufficient",
    )
    assert record.is_fully_supported is False
    assert record.any_abstaining is True
    assert record.target == PredictionTarget.FINAL_CHART_CNF


def test_prediction_record_requires_an_as_of_time():
    """No default: an estimate without a prediction timestamp cannot say what it knew."""
    with pytest.raises(TypeError):
        PredictionRecord(target=PredictionTarget.FINAL_CHART_CNF)


def test_prediction_record_rejects_naive_timestamps():
    with pytest.raises(TemporalIntegrityError, match="no timezone offset"):
        PredictionRecord(
            target=PredictionTarget.FINAL_CHART_CNF,
            prediction_at=datetime(2026, 11, 10, 8, 0),  # noqa: DTZ001 - deliberately naive
        )


def test_record_with_no_passengers_is_not_fully_supported():
    """Regression: ``all()`` over an empty list made an empty request look sufficient."""
    record = PredictionRecord(
        target=PredictionTarget.FINAL_CHART_CNF,
        prediction_at=PREDICTION_AT,
        passenger_outcomes=[],
    )
    assert record.is_fully_supported is False


def test_abstaining_outcome_cannot_claim_an_evidence_basis():
    with pytest.raises(ValueError, match="must not claim an evidence basis"):
        PassengerOutcome(
            passenger_id="p-1",
            p_cnf=None,
            p_rac=None,
            p_wl=None,
            p_cancelled=None,
            p_other=None,
            abstention_reason=AbstentionReason.NO_APPROVED_DATA,
            basis="cohort=SL/GN/WL n=105",
        )

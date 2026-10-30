"""Unit tests for prediction records, probabilities, and abstention types."""

from datetime import UTC, datetime

import pytest

from railconfirm.domain.exceptions import TemporalIntegrityError
from railconfirm.domain.prediction import (
    EVENT_CLASSES_BY_TARGET,
    TARGET_DEFINITIONS,
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


def supported_outcome() -> PassengerOutcome:
    return PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.6,
        p_rac=0.25,
        p_wl=0.1,
        p_cancelled=0.03,
        p_other=0.02,
        abstention_reason=None,
    )


def test_the_target_event_is_the_sum_of_the_classes_it_covers():
    """One booking, two questions: exactly the classes each target names."""
    outcome = supported_outcome()
    assert outcome.probability_of(EVENT_CLASSES_BY_TARGET["final_chart_cnf"]) == pytest.approx(
        0.6
    )
    assert outcome.probability_of(
        EVENT_CLASSES_BY_TARGET["final_chart_cnf_or_rac"]
    ) == pytest.approx(0.85)


def test_the_merged_event_is_never_narrower_than_confirmed():
    outcome = supported_outcome()
    confirmed = outcome.probability_of(EVENT_CLASSES_BY_TARGET["final_chart_cnf"])
    merged = outcome.probability_of(EVENT_CLASSES_BY_TARGET["final_chart_cnf_or_rac"])
    assert confirmed is not None and merged is not None
    assert merged >= confirmed


def test_an_abstention_has_no_event_probability():
    """None, not 0: an absent estimate must not read as a certain non-outcome."""
    outcome = make_abstention_outcome("p-1", AbstentionReason.NO_TRAINED_MODEL)
    assert outcome.probability_of(EVENT_CLASSES_BY_TARGET["final_chart_cnf"]) is None


def test_an_unknown_event_class_is_refused_rather_than_skipped():
    """Skipping a typo would silently shrink the event to a different question."""
    with pytest.raises(ValueError, match="not outcome classes"):
        supported_outcome().probability_of(("CNF", "CONFIRMED"))


def test_an_event_that_covers_no_class_is_refused():
    """An empty event is not zero chance; it is a question with no classes."""
    with pytest.raises(ValueError, match="at least one outcome class"):
        supported_outcome().probability_of(())


def test_every_target_publishes_a_definition_naming_its_event():
    assert set(TARGET_DEFINITIONS) == {target.value for target in PredictionTarget}
    assert "confirmed (CNF)" in TARGET_DEFINITIONS[PredictionTarget.FINAL_CHART_CNF.value]
    merged = TARGET_DEFINITIONS[PredictionTarget.FINAL_CHART_CNF_OR_RAC.value]
    assert "CNF" in merged and "RAC" in merged

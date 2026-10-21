"""Unit tests for HistoricalFrequencyBaseline estimator."""

import pytest

from railconfirm.domain.prediction import AbstentionReason
from railconfirm.domain.status import parse_status
from railconfirm.inference.baseline import HistoricalFrequencyBaseline


def test_baseline_abstains_when_not_loaded():
    baseline = HistoricalFrequencyBaseline()
    parsed = parse_status("GNWL/10")
    outcome = baseline.estimate(
        passenger_id="p-1",
        parsed_status=parsed,
        class_code="SL",
        quota_code="GN",
    )
    assert outcome.is_supported() is False
    assert outcome.abstention_reason == AbstentionReason.NO_TRAINED_MODEL


def test_baseline_abstains_on_unknown_status():
    baseline = HistoricalFrequencyBaseline()
    parsed = parse_status("INVALID_CODE")
    outcome = baseline.estimate(
        passenger_id="p-1",
        parsed_status=parsed,
        class_code="SL",
        quota_code="GN",
    )
    assert outcome.is_supported() is False
    assert outcome.abstention_reason == AbstentionReason.UNKNOWN_STATUS


def test_baseline_estimates_with_loaded_frequencies():
    baseline = HistoricalFrequencyBaseline(min_sample_threshold=10)
    # Load synthetic frequency table
    freq_table = {
        ("SL", "GN", "WL"): {"CNF": 70, "RAC": 20, "WL": 10, "CANCELLED": 5, "OTHER": 0}
    }
    baseline.load_frequencies(freq_table)

    parsed = parse_status("GNWL/15")
    outcome = baseline.estimate(
        passenger_id="p-1",
        parsed_status=parsed,
        class_code="SL",
        quota_code="GN",
    )
    assert outcome.is_supported() is True
    assert outcome.p_cnf is not None
    assert 0.0 <= outcome.p_cnf <= 1.0

    # Total probabilities must sum to 1.0
    total = (
        outcome.p_cnf
        + outcome.p_rac
        + outcome.p_wl
        + outcome.p_cancelled
        + outcome.p_other
    )
    assert total == pytest.approx(1.0)


def test_baseline_abstains_below_sample_threshold():
    baseline = HistoricalFrequencyBaseline(min_sample_threshold=50)
    freq_table = {
        ("3A", "TQ", "WL"): {"CNF": 5, "RAC": 0, "WL": 2, "CANCELLED": 0, "OTHER": 0}
    }
    baseline.load_frequencies(freq_table)

    parsed = parse_status("TQWL/1")
    outcome = baseline.estimate(
        passenger_id="p-1",
        parsed_status=parsed,
        class_code="3A",
        quota_code="TQ",
    )
    assert outcome.is_supported() is False
    assert outcome.abstention_reason == AbstentionReason.INSUFFICIENT_SAMPLE

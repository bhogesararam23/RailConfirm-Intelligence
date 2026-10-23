"""Unit and adversarial tests for the HistoricalFrequencyBaseline estimator.

The counts used here are arithmetic fixtures: they exercise the estimator's
mathematics and abstention rules. They are not railway evidence and must never
be cited as an accuracy claim.
"""

import math

import pytest

from railconfirm.domain.exceptions import FrequencyTableValidationError
from railconfirm.domain.prediction import AbstentionReason
from railconfirm.domain.status import parse_status
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    HistoricalFrequencyBaseline,
    normalize_frequency_table,
)

SL_WL_COUNTS = {"CNF": 70, "RAC": 20, "WL": 10, "CANCELLED": 5, "OTHER": 0}


def approved_provenance(**overrides) -> FrequencyTableProvenance:
    base = {
        "dataset_id": "fixture-sl-gn-2026-10",
        "sha256": "0" * 64,
        "source_reference": "SOURCE_REGISTER#fixture",
        "approval_status": "approved",
        "is_synthetic": False,
    }
    base.update(overrides)
    return FrequencyTableProvenance(**base)


def loaded_baseline(table, min_sample_threshold=10, provenance=None) -> HistoricalFrequencyBaseline:
    baseline = HistoricalFrequencyBaseline(min_sample_threshold=min_sample_threshold)
    baseline.load_frequency_table(
        table,
        provenance if provenance is not None else approved_provenance(),
    )
    return baseline


def estimate(baseline, raw="GNWL/15", class_code="SL", quota_code="GN", pid="p-1"):
    return baseline.estimate(
        passenger_id=pid,
        parsed_status=parse_status(raw),
        class_code=class_code,
        quota_code=quota_code,
    )


# ── Abstention paths ───────────────────────────────────────────────────────────


def test_abstains_without_data_and_says_no_approved_data():
    """A missing evidence base is not the same as a missing trained model."""
    outcome = estimate(HistoricalFrequencyBaseline())
    assert not outcome.is_supported()
    assert outcome.abstention_reason == AbstentionReason.NO_APPROVED_DATA
    assert outcome.basis is None


def test_abstains_on_unknown_status_before_considering_data():
    baseline = loaded_baseline({("SL", "GN", "WL"): SL_WL_COUNTS})
    outcome = estimate(baseline, raw="NOT_A_CODE")
    assert outcome.abstention_reason == AbstentionReason.UNKNOWN_STATUS


@pytest.mark.parametrize(
    "raw,cohort",
    [("CAN", "CANCELLED"), ("CANCELLED", "CANCELLED"), ("CENSORED", "CENSORED")],
)
def test_abstains_on_statuses_outside_the_reservation_queue(raw, cohort):
    """Cancelled and censored records must not be folded into queue estimates.

    Regression: the estimator previously smoothed any non-UNKNOWN status, so a
    censored row produced a confident probability for a booking whose outcome was
    never observed.
    """
    baseline = loaded_baseline({("SL", "GN", cohort): SL_WL_COUNTS})
    outcome = estimate(baseline, raw=raw)
    assert not outcome.is_supported()
    assert outcome.abstention_reason == AbstentionReason.UNSUPPORTED_STATUS


def test_abstains_when_cohort_is_absent_entirely():
    baseline = loaded_baseline({("3A", "TQ", "WL"): SL_WL_COUNTS})
    outcome = estimate(baseline, class_code="SL", quota_code="GN")
    assert outcome.abstention_reason == AbstentionReason.INSUFFICIENT_SAMPLE


def test_abstains_below_minimum_sample_threshold():
    baseline = loaded_baseline(
        {("SL", "GN", "WL"): {"CNF": 2, "RAC": 1, "WL": 1, "CANCELLED": 0, "OTHER": 0}},
        min_sample_threshold=50,
    )
    outcome = estimate(baseline)
    assert outcome.abstention_reason == AbstentionReason.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize(
    "provenance_kwargs",
    [
        {"approval_status": "quarantined"},
        {"approval_status": "candidate"},
        {"approval_status": "restricted"},
        {"approval_status": "rejected"},
        {"approval_status": "approved", "is_synthetic": True},
    ],
)
def test_unapproved_or_synthetic_provenance_never_produces_estimates(provenance_kwargs):
    """A mechanical check cannot approve a dataset, and synthetic rows are not evidence."""
    baseline = loaded_baseline(
        {("SL", "GN", "WL"): SL_WL_COUNTS},
        provenance=approved_provenance(**provenance_kwargs),
    )
    outcome = estimate(baseline)
    assert outcome.abstention_reason == AbstentionReason.NO_APPROVED_DATA


def test_evaluation_only_flag_is_not_a_license_override():
    """The offline-scoring escape hatch applies to synthetic data only.

    An unapproved real dataset must stay blocked even with evaluation_only set, so
    the flag cannot be used to talk past the approval gate.
    """
    baseline = loaded_baseline(
        {("SL", "GN", "WL"): SL_WL_COUNTS},
        provenance=approved_provenance(
            approval_status="quarantined", is_synthetic=False, evaluation_only=True
        ),
    )
    assert estimate(baseline).abstention_reason == AbstentionReason.NO_APPROVED_DATA


def test_evaluation_only_permits_scoring_a_synthetic_table():
    baseline = loaded_baseline(
        {("SL", "GN", "WL"): SL_WL_COUNTS},
        provenance=approved_provenance(
            approval_status="approved", is_synthetic=True, evaluation_only=True
        ),
    )
    assert estimate(baseline).is_supported()


def test_model_artifact_metadata_cannot_carry_the_evaluation_flag():
    """The serving path builds provenance from artifact metadata, which has no
    evaluation_only field — so a stored artifact can never opt into it."""
    from dataclasses import fields

    from railconfirm.inference.artifacts import ModelArtifactMetadata

    metadata_names = {field.name for field in fields(ModelArtifactMetadata)}
    assert "evaluation_only" not in metadata_names

    from railconfirm.inference.baseline import FrequencyTableProvenance

    provenance_names = {field.name for field in fields(FrequencyTableProvenance)}
    assert "evaluation_only" in provenance_names


# ── Estimate paths ─────────────────────────────────────────────────────────────


def test_smoothed_distribution_matches_hand_computed_laplace():
    baseline = loaded_baseline({("SL", "GN", "WL"): SL_WL_COUNTS})
    outcome = estimate(baseline)
    assert outcome.is_supported()

    total = sum(SL_WL_COUNTS.values())
    denom = total + len(OUTCOME_CLASSES)
    assert outcome.p_cnf == pytest.approx((70 + 1) / denom)
    assert outcome.p_other == pytest.approx((0 + 1) / denom)
    assert math.isclose(
        outcome.p_cnf + outcome.p_rac + outcome.p_wl + outcome.p_cancelled + outcome.p_other,
        1.0,
        abs_tol=1e-12,
    )


def test_estimate_records_the_cohort_and_sample_size():
    baseline = loaded_baseline({("SL", "GN", "WL"): SL_WL_COUNTS})
    basis = estimate(baseline).basis
    assert basis is not None
    assert "SL/GN/WL" in basis
    assert "n=105" in basis


def test_broad_cohort_fallback_is_labelled_as_a_fallback():
    baseline = loaded_baseline(
        {
            ("SL", "GN", "CNF"): SL_WL_COUNTS,
            ("SL", "GN", BROAD_COHORT_STATUS): SL_WL_COUNTS,
        }
    )
    outcome = estimate(baseline, raw="RAC 4")
    assert outcome.is_supported()
    assert "exact_status_match=false" in outcome.basis
    assert BROAD_COHORT_STATUS in outcome.basis


def test_exact_cohort_is_preferred_over_broad_fallback():
    baseline = loaded_baseline(
        {
            ("SL", "GN", "WL"): {"CNF": 90, "RAC": 5, "WL": 5, "CANCELLED": 0, "OTHER": 0},
            ("SL", "GN", BROAD_COHORT_STATUS): {"CNF": 10, "RAC": 5, "WL": 85, "CANCELLED": 0, "OTHER": 0},
        }
    )
    outcome = estimate(baseline)
    assert outcome.p_cnf == pytest.approx(91 / (100 + 5))
    assert "exact_status_match=true" in outcome.basis


def test_lowercase_fitted_keys_still_match_at_inference():
    """Regression: fitted keys were never normalised, so a lowercase table could
    only ever abstain while appearing to be loaded."""
    baseline = loaded_baseline({("sl", " gn ", "wl"): SL_WL_COUNTS})
    outcome = estimate(baseline)
    assert outcome.is_supported()
    assert "SL/GN/WL" in outcome.basis


def test_rac_and_confirmed_statuses_are_estimated():
    baseline = loaded_baseline(
        {
            ("SL", "GN", "WL"): SL_WL_COUNTS,
            ("SL", "GN", "RAC"): {"CNF": 50, "RAC": 40, "WL": 10, "CANCELLED": 0, "OTHER": 0},
            ("SL", "GN", "CNF"): {"CNF": 100, "RAC": 0, "WL": 0, "CANCELLED": 0, "OTHER": 0},
        }
    )
    assert estimate(baseline, raw="RAC 2").is_supported()
    assert estimate(baseline, raw="CNF").is_supported()


# ── Table validation ───────────────────────────────────────────────────────────


def test_unknown_outcome_key_is_rejected_not_smoothed_away():
    """Regression: {"CONFIRMED": 100} yielded a flat 0.2 distribution."""
    with pytest.raises(FrequencyTableValidationError, match="outside the defined outcome space"):
        normalize_frequency_table({("SL", "GN", "WL"): {"CONFIRMED": 100}})


@pytest.mark.parametrize(
    "counts,expected_fragment",
    [
        ({"CNF": -5, "RAC": 10, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "negative count"),
        ({"CNF": 12.5, "RAC": 7.5, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "integers"),
        ({"CNF": float("nan"), "RAC": 7, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "integers"),
        ({"CNF": float("inf"), "RAC": 7, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "integers"),
        ({"CNF": "30", "RAC": 20, "WL": 10, "CANCELLED": 0, "OTHER": 0}, "integers"),
        ({"CNF": True, "RAC": 0, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "integers"),
        ({"CNF": 0, "RAC": 0, "WL": 0, "CANCELLED": 0, "OTHER": 0}, "no positive counts"),
        ({}, "no outcome counts"),
        ([("CNF", 10)], "mapping"),
    ],
)
def test_malformed_counts_are_rejected(counts, expected_fragment):
    with pytest.raises(FrequencyTableValidationError, match=expected_fragment):
        normalize_frequency_table({("SL", "GN", "WL"): counts})


@pytest.mark.parametrize(
    "table,expected_fragment",
    [
        ({}, "empty"),
        ([], "mapping"),
        ({("SL", "GN"): SL_WL_COUNTS}, "3-tuples"),
        ({("SL", "GN", "WL", "extra"): SL_WL_COUNTS}, "3-tuples"),
        ({("SL", "GN", "WAITLISTED"): SL_WL_COUNTS}, "not a normalized status"),
        ({("SL", "", "WL"): SL_WL_COUNTS}, "empty quota_code"),
        ({("SL", "GN", "WL"): SL_WL_COUNTS, ("sl", "gn", "wl"): SL_WL_COUNTS}, "collide"),
    ],
)
def test_malformed_tables_are_rejected(table, expected_fragment):
    with pytest.raises(FrequencyTableValidationError, match=expected_fragment):
        normalize_frequency_table(table)


def test_load_requires_provenance():
    baseline = HistoricalFrequencyBaseline(min_sample_threshold=5)
    with pytest.raises(FrequencyTableValidationError, match="provenance"):
        baseline.load_frequency_table({("SL", "GN", "WL"): SL_WL_COUNTS}, None)


def test_failed_load_leaves_previous_state_untouched():
    baseline = loaded_baseline({("SL", "GN", "WL"): SL_WL_COUNTS})
    with pytest.raises(FrequencyTableValidationError):
        baseline.load_frequency_table(
            {("SL", "GN", "WL"): {"NOPE": 5}},
            approved_provenance(),
        )
    assert baseline.is_loaded
    assert estimate(baseline).is_supported()


def test_clear_removes_table_and_provenance():
    baseline = loaded_baseline({("SL", "GN", "WL"): SL_WL_COUNTS})
    baseline.clear()
    assert not baseline.is_loaded
    assert baseline.provenance is None
    assert estimate(baseline).abstention_reason == AbstentionReason.NO_APPROVED_DATA


@pytest.mark.parametrize("bad_value", [0, -1, True])
def test_rejects_nonsensical_sample_threshold(bad_value):
    with pytest.raises(ValueError, match="min_sample_threshold"):
        HistoricalFrequencyBaseline(min_sample_threshold=bad_value)


@pytest.mark.parametrize("bad_alpha", [0.0, -1.0, float("nan"), math.inf])
def test_rejects_nonsensical_smoothing(bad_alpha):
    with pytest.raises(ValueError, match="laplace_alpha"):
        HistoricalFrequencyBaseline(laplace_alpha=bad_alpha)


def test_normalization_is_pure_and_does_not_mutate_the_input():
    table = {("sl", "gn", "wl"): SL_WL_COUNTS}
    normalized = normalize_frequency_table(table)
    assert list(table.keys()) == [("sl", "gn", "wl")]
    assert normalized[("SL", "GN", "WL")]["CNF"] == 70

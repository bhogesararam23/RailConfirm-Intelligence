"""A cohort model that reads the as-of queue position, and refuses to read anything else.

Synthetic counts only. The frequency baseline answers every passenger in a cohort with the
same number, so a queue position of 1 and one of 200 get the same probability — and the
feature schema has derived that position for later models since 3.0.0 while nothing used it.
These tests pin the second estimator: it must use the position, must say which cell answered,
must fall back instead of inventing a rate from three rows, and must keep every trust gate the
frequency baseline already enforces.
"""

import pytest

from railconfirm.domain.exceptions import FrequencyTableValidationError
from railconfirm.domain.prediction import AbstentionReason
from railconfirm.domain.status import MAPPING_VERSION, parse_status
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    FrequencyTableProvenance,
    HistoricalFrequencyBaseline,
)
from railconfirm.inference.queue import (
    DEFAULT_MIN_BAND_ROWS,
    QUEUE_ESTIMATOR_ID,
    QUEUE_FEATURES,
    CohortPositionBaseline,
    band_labels,
    normalize_band_table,
    position_band,
)

COHORTS = {("SL", "GN", "WL"): {"CNF": 40, "WL": 60}}
BANDS = {
    ("SL", "GN", "WL", "1"): {"CNF": 30, "WL": 5},
    ("SL", "GN", "WL", "2-3"): {"CNF": 8, "WL": 12},
    ("SL", "GN", "WL", "4-7"): {"CNF": 20, "WL": 30},
    # Deliberately thin: one row cannot carry a rate, so the cohort must answer.
    ("SL", "GN", "WL", "8-15"): {"CNF": 1},
}


def provenance(**overrides) -> FrequencyTableProvenance:
    base = {
        "dataset_id": "queue-fixture",
        "sha256": "a" * 64,
        "source_reference": "tests/inference/test_queue_model.py",
        "approval_status": "approved",
        "is_synthetic": False,
        "mapping_version": MAPPING_VERSION,
    }
    base.update(overrides)
    return FrequencyTableProvenance(**base)


def model(cohorts=COHORTS, bands=BANDS, **kwargs) -> CohortPositionBaseline:
    kwargs.setdefault("min_sample_threshold", 5)
    kwargs.setdefault("laplace_alpha", 1.0)
    estimator = CohortPositionBaseline(**kwargs)
    estimator.load_tables(cohorts, bands, provenance())
    return estimator


def asof(raw: str):
    return parse_status(raw)


def smoothed(counts: dict[str, int]) -> float:
    """The hand-checkable add-alpha rate this estimator is required to produce."""
    return (counts["CNF"] + 1.0) / (sum(counts.values()) + 5.0)


# ── The band rule ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("position", "band"),
    [
        (1, "1"),
        (2, "2-3"),
        (3, "2-3"),
        (4, "4-7"),
        (7, "4-7"),
        (8, "8-15"),
        (16, "16-31"),
        (32, "32-63"),
        (64, "64-127"),
        (127, "64-127"),
        (128, "128+"),
        (5000, "128+"),
    ],
)
def test_bands_are_doubling_widths_so_the_rule_never_depends_on_the_data(position, band):
    """Cut points from the training file would move when the file moves; these do not."""
    assert position_band(position) == band


def test_an_absent_position_is_absent_rather_than_zero():
    assert position_band(None) is None


@pytest.mark.parametrize("position", [0, -1, -40])
def test_a_non_positive_position_is_rejected_rather_than_banded(position):
    with pytest.raises(ValueError, match="positive"):
        position_band(position)


def test_the_estimator_identifies_itself_and_the_features_it_reads():
    assert QUEUE_ESTIMATOR_ID == "cohort_position_baseline"
    assert QUEUE_FEATURES == (
        "class_code",
        "quota_code",
        "asof_normalized",
        "asof_position",
    )


# ── What a position does to the answer ─────────────────────────────────────────


def test_a_first_in_queue_passenger_is_answered_from_the_first_in_queue_cell():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    assert outcome.abstention_reason is None
    assert outcome.p_cnf == pytest.approx(smoothed({"CNF": 30, "WL": 5}))
    assert "band=1" in outcome.basis
    assert "n=35" in outcome.basis


def test_the_same_cohort_at_different_positions_produces_different_probabilities():
    """The whole reason this model exists: a cohort is not one number."""
    estimator = model()
    shallow = estimator.estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    deep = estimator.estimate(
        passenger_id="p-2",
        asof_status=asof("GNWL/5"),
        class_code="SL",
        quota_code="GN",
        asof_position=5,
    )
    assert shallow.p_cnf > deep.p_cnf
    assert "band=4-7" in deep.basis


def test_a_thin_band_answers_from_the_cohort_and_says_that_is_what_happened():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/10"),
        class_code="SL",
        quota_code="GN",
        asof_position=10,
    )
    assert outcome.p_cnf == pytest.approx(smoothed({"CNF": 40, "WL": 60}))
    assert "band=8-15" in outcome.basis
    assert "below the 2-row band floor" in outcome.basis
    assert "cohort rate used" in outcome.basis
    assert "n=100" in outcome.basis


def test_the_band_floor_is_configurable_and_respected():
    outcome = model(min_band_rows=1).estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/10"),
        class_code="SL",
        quota_code="GN",
        asof_position=10,
    )
    assert outcome.p_cnf == pytest.approx(smoothed({"CNF": 1}))
    assert "band=8-15" in outcome.basis
    assert "cohort rate used" not in outcome.basis


def test_no_position_means_no_band_and_the_cohort_answers_without_invention():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL"),
        class_code="SL",
        quota_code="GN",
        asof_position=None,
    )
    assert outcome.p_cnf == pytest.approx(smoothed({"CNF": 40, "WL": 60}))
    assert "position unavailable" in outcome.basis


def test_the_default_band_floor_is_a_stated_number_not_a_magic_value():
    assert DEFAULT_MIN_BAND_ROWS == 2
    assert CohortPositionBaseline(min_sample_threshold=5).min_band_rows == (
        DEFAULT_MIN_BAND_ROWS
    )


def test_the_distribution_still_sums_to_one_over_the_five_outcome_classes():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/2"),
        class_code="SL",
        quota_code="GN",
        asof_position=2,
    )
    total = (
        outcome.p_cnf + outcome.p_rac + outcome.p_wl + outcome.p_cancelled + outcome.p_other
    )
    assert total == pytest.approx(1.0)
    assert outcome.p_rac > 0.0  # unseen classes keep smoothed mass, never a hard zero


# ── Fallbacks and abstentions, as the frequency baseline already behaves ────────


def test_a_missing_status_cohort_falls_back_to_the_broad_cohort_by_class_and_quota():
    cohorts = {("SL", "GN", BROAD_COHORT_STATUS): {"CNF": 10, "WL": 30}}
    bands = {("SL", "GN", BROAD_COHORT_STATUS, "1"): {"CNF": 9, "WL": 1}}
    outcome = model(cohorts=cohorts, bands=bands).estimate(
        passenger_id="p-1",
        asof_status=asof("RLWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    # A broad-cohort fallback is still position-aware: the band belongs to that cohort key.
    assert outcome.p_cnf == pytest.approx(smoothed({"CNF": 9, "WL": 1}))
    assert "band=1" in outcome.basis
    assert "exact_status_match=false" in outcome.basis


def test_a_class_quota_pair_with_no_evidence_abstains():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/4"),
        class_code="3A",
        quota_code="GN",
        asof_position=4,
    )
    assert outcome.p_cnf is None
    assert outcome.abstention_reason is AbstentionReason.INSUFFICIENT_SAMPLE


def test_a_cohort_below_the_sample_floor_abstains_even_when_a_band_is_rich():
    cohorts = {("3A", "GN", "WL"): {"CNF": 2, "WL": 3}}
    bands = {("3A", "GN", "WL", "1"): {"CNF": 2, "WL": 1}}
    outcome = model(cohorts=cohorts, bands=bands, min_sample_threshold=20).estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/1"),
        class_code="3A",
        quota_code="GN",
        asof_position=1,
    )
    assert outcome.abstention_reason is AbstentionReason.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize("raw", ["CANCELLED", "CENSORED"])
def test_a_record_outside_the_reservation_queue_abstains_as_unsupported(raw):
    """A cancelled or censored booking has no queue to be deep in, position or not."""
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof(raw),
        class_code="SL",
        quota_code="GN",
        asof_position=3,
    )
    assert outcome.abstention_reason is AbstentionReason.UNSUPPORTED_STATUS


def test_an_unmappable_status_abstains_before_any_lookup():
    outcome = model().estimate(
        passenger_id="p-1",
        asof_status=asof("CK"),
        class_code="SL",
        quota_code="GN",
        asof_position=3,
    )
    assert outcome.abstention_reason is AbstentionReason.UNKNOWN_STATUS


@pytest.mark.parametrize(
    "overrides",
    [
        {"approval_status": "pending"},
        {"approval_status": "under_review"},
        {"is_synthetic": True},
    ],
)
def test_provenance_that_may_not_estimate_yields_abstention_whatever_the_position_is(overrides):
    """The position model inherits the trust gates; a second estimator adds no way around."""
    kwargs = {"min_sample_threshold": 5}
    estimator = CohortPositionBaseline(**kwargs)
    estimator.load_tables(COHORTS, BANDS, provenance(**overrides))
    for position in (1, 5, None):
        outcome = estimator.estimate(
            passenger_id="p-1",
            asof_status=asof("GNWL/5"),
            class_code="SL",
            quota_code="GN",
            asof_position=position,
        )
        assert outcome.abstention_reason is AbstentionReason.NO_APPROVED_DATA


def test_a_table_that_is_not_loaded_abstains_and_reports_itself_unloaded():
    estimator = CohortPositionBaseline(min_sample_threshold=5)
    assert estimator.is_loaded is False
    outcome = estimator.estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/5"),
        class_code="SL",
        quota_code="GN",
        asof_position=5,
    )
    assert outcome.abstention_reason is AbstentionReason.NO_APPROVED_DATA


# ── Table validation at load, not smoothing at estimate ────────────────────────


def test_loading_stores_both_tables_and_reports_the_cohorts_it_can_answer_from():
    estimator = model()
    assert estimator.is_loaded is True
    assert estimator.cohort_count == 1
    assert estimator.band_count == 4


def test_an_empty_cohort_table_is_refused_rather_than_answered_with_a_default():
    with pytest.raises(FrequencyTableValidationError, match="empty"):
        model(cohorts={})


def test_an_empty_band_table_is_refused_because_a_model_that_ignores_position_is_the_other_one():
    with pytest.raises(FrequencyTableValidationError, match="empty"):
        normalize_band_table({})


@pytest.mark.parametrize(
    "band_counts",
    [
        {"CONFIRMED": 10},
        {"CNF": -3, "WL": 10},
        {"CNF": 2.5, "WL": 10},
        {"CNF": True, "WL": 4},
        {"CNF": 0, "WL": 0},
        "not-a-mapping",
    ],
)
def test_a_malformed_band_cell_raises_at_load_with_the_band_named(band_counts):
    with pytest.raises(FrequencyTableValidationError):
        normalize_band_table({("SL", "GN", "WL", "4-7"): band_counts})


def test_band_keys_that_collide_after_normalisation_are_refused_not_overwritten():
    """('sl','gn','wl','1') and ('SL','GN','WL','1') would silently lose one cell."""
    with pytest.raises(FrequencyTableValidationError, match="collide"):
        normalize_band_table(
            {
                ("sl", "gn", "wl", "1"): {"CNF": 5, "WL": 1},
                ("SL", "GN", "WL", "1"): {"CNF": 9, "WL": 1},
            }
        )


def test_band_cells_are_normalised_the_way_cohort_keys_already_are():
    normalized = normalize_band_table({(" sl ", "gn", "wl", "2-3"): {"CNF": 3, "WL": 1}})
    assert list(normalized) == [("SL", "GN", "WL", "2-3")]


def test_a_band_key_of_the_wrong_shape_is_refused():
    with pytest.raises(FrequencyTableValidationError, match="four"):
        normalize_band_table({("SL", "GN", "WL"): {"CNF": 3, "WL": 1}})


@pytest.mark.parametrize(
    "label",
    ["0", "1-3", "128", "200+", "64-128", "8 - 15", "first", "1 to 3"],
)
def test_a_band_label_the_model_never_produces_is_refused(label):
    """A cell keyed by an unreachable label can never answer a request.

    `1-3` and `128` are the plausible mistakes: one neighbouring width and the top cut
    written as a ceiling. Both would load, be counted as position evidence, and never be
    read by `position_band`.
    """
    with pytest.raises(FrequencyTableValidationError, match="never produces"):
        normalize_band_table({("SL", "GN", "WL", label): {"CNF": 3, "WL": 1}})


@pytest.mark.parametrize("label", band_labels())
def test_every_reachable_band_label_is_accepted(label):
    normalized = normalize_band_table({("SL", "GN", "WL", label): {"CNF": 3, "WL": 1}})
    assert list(normalized) == [("SL", "GN", "WL", label)]


def test_the_accepted_labels_are_exactly_what_the_banding_rule_returns():
    """The loader's list is checked against the function that produces labels, not a copy."""
    produced = {position_band(position) for position in range(1, 5000)}
    assert produced == set(band_labels())


def test_a_band_keyed_by_a_status_the_estimator_cannot_look_up_is_refused():
    """The first three parts name a cohort, so they are validated as one."""
    with pytest.raises(FrequencyTableValidationError, match="not a normalized status"):
        normalize_band_table({("SL", "GN", "WAITING", "1"): {"CNF": 3, "WL": 1}})


def test_a_band_key_with_no_band_is_refused():
    with pytest.raises(FrequencyTableValidationError, match="names no band"):
        normalize_band_table({("SL", "GN", "WL", "   "): {"CNF": 3, "WL": 1}})


def test_a_band_key_with_an_empty_class_is_refused():
    with pytest.raises(FrequencyTableValidationError, match="empty class_code"):
        normalize_band_table({("  ", "GN", "WL", "1"): {"CNF": 3, "WL": 1}})


def test_a_band_cell_whose_cohort_has_no_row_is_refused_and_nothing_is_loaded():
    """The estimator resolves the cohort first, so an orphan cell could never be reached.

    A table made only of orphans is the frequency model under the position model's name,
    which is the confusion ADR-0020 exists to prevent.
    """
    estimator = CohortPositionBaseline(min_sample_threshold=5)
    with pytest.raises(FrequencyTableValidationError, match="no row in the cohort table"):
        estimator.load_tables(
            COHORTS,
            {("SL", "GN", "RAC", "1"): {"CNF": 1, "WL": 1}},
            provenance(),
        )
    assert not estimator.is_loaded
    assert estimator.provenance is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_sample_threshold": 0},
        {"min_sample_threshold": True},
        {"laplace_alpha": 0.0},
        {"laplace_alpha": float("nan")},
        {"min_band_rows": 0},
    ],
)
def test_the_settings_that_make_a_distribution_meaningless_are_refused(kwargs):
    with pytest.raises(ValueError):
        CohortPositionBaseline(**kwargs)


# ── Parity: the frequency baseline must not change behaviour because a new input exists ──


def test_the_frequency_baseline_reads_the_position_and_ignores_it():
    """Same result with or without the position, or the two models are not comparable."""
    estimator = HistoricalFrequencyBaseline(min_sample_threshold=5, laplace_alpha=1.0)
    estimator.load_frequency_table(COHORTS, provenance())
    plain = estimator.estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/1"),
        class_code="SL",
        quota_code="GN",
    )
    with_position = estimator.estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    deep_position = estimator.estimate(
        passenger_id="p-1",
        asof_status=asof("GNWL/60"),
        class_code="SL",
        quota_code="GN",
        asof_position=60,
    )
    assert plain.p_cnf == with_position.p_cnf == deep_position.p_cnf

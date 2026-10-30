"""The calibration layer's arithmetic and its refusal conditions.

Every number here is constructed so the expected result can be written down by hand:
the point of the tests is that a correction moves the target event's mass and nothing
else, and that a spec which cannot be applied cannot be loaded.
"""

import math

import pytest

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.domain.prediction import AbstentionReason, PassengerOutcome
from railconfirm.inference.calibration import (
    CalibrationSpec,
    apply_calibration,
    calibrate_outcome,
    calibrate_probability,
    clip_probability,
    event_mass,
    logit,
    sigmoid,
    spec_from_mapping,
)

DISTRIBUTION = {
    "CNF": 0.2,
    "RAC": 0.1,
    "WL": 0.6,
    "CANCELLED": 0.05,
    "OTHER": 0.05,
}
EVENT = ("CNF",)


def spec(slope: float = 1.0, intercept: float = 0.0, **overrides) -> CalibrationSpec:
    fields = {
        "method": "platt_logistic_v1",
        "target": "final_chart_cnf",
        "event_classes": EVENT,
        "slope": slope,
        "intercept": intercept,
        "fitted_partition": "validation",
        "fitted_rows": 120,
    }
    fields.update(overrides)
    return CalibrationSpec(**fields)  # type: ignore[arg-type]


# ── The primitives ─────────────────────────────────────────────────────────────


def test_logit_and_sigmoid_invert_each_other_inside_the_range():
    for value in (0.01, 0.2, 0.5, 0.9, 0.99):
        assert sigmoid(logit(value)) == pytest.approx(value, abs=1e-12)


def test_logit_is_finite_at_the_edges():
    """Clipped, not infinite: a certainty must not become an arbitrarily large log-odds."""
    assert math.isfinite(logit(0.0))
    assert math.isfinite(logit(1.0))
    assert logit(0.0) == pytest.approx(logit(clip_probability(0.0)))
    assert sigmoid(logit(0.0)) > 0.0


def test_sigmoid_stays_inside_zero_one():
    assert 0.0 <= sigmoid(-50.0) < 1e-20
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert 0.9999 < sigmoid(50.0) <= 1.0


def test_event_mass_sums_only_the_classes_in_the_event():
    assert event_mass(DISTRIBUTION, ("CNF",)) == pytest.approx(0.2)
    assert event_mass(DISTRIBUTION, ("CNF", "RAC")) == pytest.approx(0.3)


# ── Applying a spec ────────────────────────────────────────────────────────────


def test_a_unit_slope_and_zero_intercept_is_the_identity():
    assert apply_calibration(spec(1.0, 0.0), DISTRIBUTION, EVENT) == pytest.approx(
        DISTRIBUTION
    )


def test_the_correction_moves_the_event_mass_and_keeps_each_group_proportional():
    """Hand check: logit(0.2) = -1.386294, doubled = -2.772589 → sigmoid = 0.058755."""
    calibrated = apply_calibration(spec(2.0, 0.0), DISTRIBUTION, EVENT)
    expected = sigmoid(2 * logit(0.2))
    assert event_mass(calibrated, EVENT) == pytest.approx(expected, abs=1e-12)
    assert sum(calibrated.values()) == pytest.approx(1.0)
    # Inside the event there is only CNF; outside, the RAC/WL/CANCELLED/OTHER split
    # keeps its ratios because nothing was fitted for those separately.
    outside = sum(v for k, v in calibrated.items() if k not in EVENT)
    assert calibrated["WL"] / calibrated["RAC"] == pytest.approx(6.0)
    assert outside == pytest.approx(1.0 - expected)


def test_a_merged_event_moves_as_one_mass():
    merged = spec(
        2.0, 0.0, target="final_chart_cnf_or_rac", event_classes=("CNF", "RAC")
    )
    calibrated = apply_calibration(merged, DISTRIBUTION, ("CNF", "RAC"))
    assert event_mass(calibrated, ("CNF", "RAC")) == pytest.approx(
        sigmoid(2 * logit(0.3))
    )
    assert calibrated["CNF"] / calibrated["RAC"] == pytest.approx(2.0)
    assert sum(calibrated.values()) == pytest.approx(1.0)


def test_a_certainty_is_left_alone_because_it_cannot_be_rescaled():
    """Returning the input beats clipping into a fabricated confidence level."""
    certain = {"CNF": 1.0, "RAC": 0.0, "WL": 0.0, "CANCELLED": 0.0, "OTHER": 0.0}
    assert apply_calibration(spec(3.0, 1.0), certain, EVENT) == certain
    empty = {"CNF": 0.0, "RAC": 0.0, "WL": 1.0, "CANCELLED": 0.0, "OTHER": 0.0}
    assert apply_calibration(spec(3.0, 1.0), empty, EVENT) == empty


def test_calibrate_probability_matches_the_distribution_level_correction():
    assert calibrate_probability(spec(2.0, 0.5), 0.2) == pytest.approx(
        event_mass(apply_calibration(spec(2.0, 0.5), DISTRIBUTION, EVENT), EVENT)
    )


# ── Passengers ─────────────────────────────────────────────────────────────────


def supported(passenger_id: str = "p-1", **overrides) -> PassengerOutcome:
    fields = {
        "passenger_id": passenger_id,
        "p_cnf": 0.2,
        "p_rac": 0.1,
        "p_wl": 0.6,
        "p_cancelled": 0.05,
        "p_other": 0.05,
        "abstention_reason": None,
        "basis": "cohort=SL/GN/WL n=80 exact_status_match=true",
    }
    fields.update(overrides)
    return PassengerOutcome(**fields)  # type: ignore[arg-type]


def test_a_supported_outcome_is_corrected_and_its_basis_says_so():
    outcome = calibrate_outcome(spec(2.0, 0.0), supported())
    assert outcome.p_cnf == pytest.approx(sigmoid(2 * logit(0.2)))
    assert sum(
        [outcome.p_cnf, outcome.p_rac, outcome.p_wl, outcome.p_cancelled, outcome.p_other]
    ) == pytest.approx(1.0)
    assert "calibrated=platt_logistic_v1" in (outcome.basis or "")
    assert "cohort=SL/GN/WL" in (outcome.basis or "")


def test_an_abstention_is_returned_untouched():
    abstained = PassengerOutcome(
        passenger_id="p-2",
        p_cnf=None,
        p_rac=None,
        p_wl=None,
        p_cancelled=None,
        p_other=None,
        abstention_reason=AbstentionReason.INSUFFICIENT_SAMPLE,
    )
    assert calibrate_outcome(spec(2.0, 0.0), abstained) is abstained


def test_the_marker_is_not_stacked_by_repeated_application():
    once = calibrate_outcome(spec(1.0, 0.0), supported())
    twice = calibrate_outcome(spec(1.0, 0.0), once)
    assert twice.basis is not None
    assert twice.basis.count("calibrated=platt_logistic_v1") == 1


# ── The spec's own rules ───────────────────────────────────────────────────────


def test_the_description_names_the_rows_and_period_behind_the_correction():
    text = spec(1.5, -0.25, fitted_from="2026-04-01", fitted_to="2026-04-12").description
    assert "platt_logistic_v1 on final_chart_cnf (CNF)" in text
    assert "120 validation rows (2026-04-01..2026-04-12)" in text
    assert "slope 1.500000, intercept -0.250000" in text


@pytest.mark.parametrize(
    "overrides,fragment",
    [
        ({"method": "isotonic"}, "Unknown calibration method"),
        ({"slope": True}, "must be a number"),
        ({"slope": "1.0"}, "must be a number"),
        ({"slope": float("nan")}, "must be finite"),
        ({"intercept": float("inf")}, "must be finite"),
        ({"slope": -0.01}, "must not be negative"),
        ({"fitted_rows": 0}, "at least one observation"),
        # A row count that is not an integer is not a smaller count: "120" and null used
        # to raise TypeError out of the loader, and 120.5 and True used to be accepted.
        ({"fitted_rows": "120"}, "row count is an integer"),
        ({"fitted_rows": 120.5}, "row count is an integer"),
        ({"fitted_rows": True}, "row count is an integer"),
        ({"event_classes": ()}, "name the event classes"),
        ({"target": "departure_status"}, "whose event this build does not define"),
        # The event is a property of the target. A block naming one target while carrying
        # another target's event classes was accepted before and moved the wrong mass.
        ({"event_classes": ("CNF", "RAC")}, "whose event is"),
        ({"event_classes": ("CNF", "CNF")}, "whose event is"),
        # Fitting on the rows the correction is then scored against measures its own fit.
        ({"fitted_partition": "test"}, "may carry a fit"),
        ({"fitted_partition": "train"}, "may carry a fit"),
        ({"fitted_from": "2026-04-12", "fitted_to": "2026-04-01"}, "reversed"),
    ],
)
def test_a_spec_that_cannot_be_applied_is_not_constructed(overrides, fragment):
    with pytest.raises(ModelArtifactError, match=fragment):
        spec(**overrides)


def test_the_cnf_or_rac_target_accepts_its_own_two_class_event():
    merged = spec(1.0, 0.0, target="final_chart_cnf_or_rac", event_classes=("CNF", "RAC"))
    assert merged.event_classes == ("CNF", "RAC")


def test_a_correction_is_refused_when_it_is_applied_to_a_different_event():
    """Serving and scoring must correct the same mass, so a caller cannot name another."""
    with pytest.raises(ModelArtifactError, match="being applied to CNF/RAC"):
        apply_calibration(spec(2.0, 0.0), DISTRIBUTION, ("CNF", "RAC"))


def test_a_two_class_correction_is_refused_on_the_single_class_event():
    merged = spec(2.0, 0.0, target="final_chart_cnf_or_rac", event_classes=("CNF", "RAC"))
    with pytest.raises(ModelArtifactError, match="being applied to CNF"):
        apply_calibration(merged, DISTRIBUTION, ("CNF",))


def test_a_round_trip_through_a_mapping_preserves_the_spec():
    original = spec(1.234, -0.432, fitted_from="2026-04-01", fitted_to="2026-04-12")
    restored = spec_from_mapping(original.to_mapping(), artifact_target="final_chart_cnf")
    assert restored == original


def test_a_block_for_another_target_is_refused():
    """A correction fitted to the CNF event does not describe a CNF-or-RAC probability."""
    with pytest.raises(ModelArtifactError, match="was fitted for target"):
        spec_from_mapping(spec(1.0, 0.0).to_mapping(), artifact_target="final_chart_cnf_or_rac")


@pytest.mark.parametrize("bad", [None, [], "platt", 7])
def test_a_calibration_that_is_not_an_object_is_refused(bad):
    with pytest.raises(ModelArtifactError, match="must be a JSON object"):
        spec_from_mapping(bad, artifact_target="final_chart_cnf")


def test_a_missing_field_is_named_rather_than_defaulted():
    block = spec(1.0, 0.0).to_mapping()
    del block["intercept"]
    with pytest.raises(ModelArtifactError, match="missing 'intercept'"):
        spec_from_mapping(block, artifact_target="final_chart_cnf")


@pytest.mark.parametrize("bad", ["CNF", 3, {"CNF": 1}, ["CNF", ""]])
def test_event_classes_must_be_a_list_of_named_classes(bad):
    """A bare string would iterate into characters and name an event nobody wrote."""
    block = spec(1.0, 0.0).to_mapping()
    block["event_classes"] = bad
    with pytest.raises(ModelArtifactError, match="event_classes must be a list"):
        spec_from_mapping(block, artifact_target="final_chart_cnf")


def test_a_block_declaring_another_event_for_the_same_target_is_refused_at_load():
    """The reported defect: `final_chart_cnf` accepting a CNF+RAC correction."""
    block = spec(1.0, 0.0).to_mapping()
    block["event_classes"] = ["CNF", "RAC"]
    with pytest.raises(ModelArtifactError, match="whose event is"):
        spec_from_mapping(block, artifact_target="final_chart_cnf")


@pytest.mark.parametrize("bad", ["120", None, 120.5, True])
def test_a_malformed_row_count_is_refused_by_the_loader_and_not_raised_through_it(bad):
    """A hand-edited artifact must be rejected, not crash the component reading it.

    The registry catches `ModelArtifactError` and reports `artifact_invalid`; a `TypeError`
    escapes it, so a malformed calibration block became an unhandled exception on the
    resolution path rather than a refusal with a reason. A fraction and a boolean were
    worse still: they were accepted as row counts that cannot exist.
    """
    block = spec(1.0, 0.0).to_mapping()
    block["fitted_rows"] = bad
    with pytest.raises(ModelArtifactError, match="row count is an integer"):
        spec_from_mapping(block, artifact_target="final_chart_cnf")

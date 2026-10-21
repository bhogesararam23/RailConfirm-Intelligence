"""Unit tests for group outcome calculation in RailConfirm Intelligence."""

import pytest

from railconfirm.domain.prediction import (
    AbstentionReason,
    PassengerOutcome,
    make_abstention_outcome,
)
from railconfirm.inference.group import compute_group_outcomes


def test_empty_passenger_outcomes():
    assert compute_group_outcomes([]) is None


def test_single_passenger_group():
    po = PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.7,
        p_rac=0.2,
        p_wl=0.05,
        p_cancelled=0.03,
        p_other=0.02,
        abstention_reason=None,
    )
    group = compute_group_outcomes([po])
    assert group is not None
    assert group.p_all_cnf == pytest.approx(0.7)
    assert group.p_all_cnf_or_rac == pytest.approx(0.9)
    assert group.p_at_least_one_wl == pytest.approx(0.05)
    assert group.method == "single_passenger"
    assert group.abstention_reason is None


def test_multi_passenger_independence_baseline():
    p1 = PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.8,
        p_rac=0.1,
        p_wl=0.1,
        p_cancelled=0.0,
        p_other=0.0,
        abstention_reason=None,
    )
    p2 = PassengerOutcome(
        passenger_id="p-2",
        p_cnf=0.5,
        p_rac=0.3,
        p_wl=0.2,
        p_cancelled=0.0,
        p_other=0.0,
        abstention_reason=None,
    )
    group = compute_group_outcomes([p1, p2])
    assert group is not None
    # P(all CNF) = 0.8 * 0.5 = 0.4
    assert group.p_all_cnf == pytest.approx(0.4)
    # P(all CNF or RAC) = (0.8+0.1) * (0.5+0.3) = 0.9 * 0.8 = 0.72
    assert group.p_all_cnf_or_rac == pytest.approx(0.72)
    # P(at least one WL) = 1 - (1-0.1)*(1-0.2) = 1 - 0.9*0.8 = 1 - 0.72 = 0.28
    assert group.p_at_least_one_wl == pytest.approx(0.28)
    assert group.method == "independence_baseline"
    assert "Assumes passenger confirmation outcomes are statistically independent" in group.assumptions


def test_group_abstains_if_any_passenger_abstains():
    p1 = PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.8,
        p_rac=0.1,
        p_wl=0.1,
        p_cancelled=0.0,
        p_other=0.0,
        abstention_reason=None,
    )
    p2 = make_abstention_outcome("p-2", AbstentionReason.NO_TRAINED_MODEL)

    group = compute_group_outcomes([p1, p2])
    assert group is not None
    assert group.p_all_cnf is None
    assert group.abstention_reason == AbstentionReason.NO_TRAINED_MODEL
    assert group.method == "insufficient_data"

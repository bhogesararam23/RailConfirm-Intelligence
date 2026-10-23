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


def test_poisson_binomial_pmf():
    from railconfirm.inference.group import compute_poisson_binomial_pmf

    # Empty list
    assert compute_poisson_binomial_pmf([]) == [1.0]

    # Single probability
    pmf1 = compute_poisson_binomial_pmf([0.7])
    assert pmf1[0] == pytest.approx(0.3)
    assert pmf1[1] == pytest.approx(0.7)

    # Two probabilities [0.8, 0.5]
    pmf2 = compute_poisson_binomial_pmf([0.8, 0.5])
    assert pmf2[0] == pytest.approx(0.2 * 0.5)  # 0.10
    assert pmf2[1] == pytest.approx(0.8 * 0.5 + 0.2 * 0.5)  # 0.50
    assert pmf2[2] == pytest.approx(0.8 * 0.5)  # 0.40
    assert sum(pmf2) == pytest.approx(1.0)


def test_multi_passenger_at_least_k_cnf_independence():
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
    assert group.p_at_least_k_cnf is not None
    assert group.p_exactly_k_cnf is not None
    # P(K >= 1) = 0.5 + 0.4 = 0.9
    assert group.p_at_least_k_cnf[1] == pytest.approx(0.9)
    # P(K >= 2) = 0.4 = P(all CNF)
    assert group.p_at_least_k_cnf[2] == pytest.approx(0.4)
    # Exactly k probabilities sum to 1.0
    assert sum(group.p_exactly_k_cnf.values()) == pytest.approx(1.0)
    assert group.p_exactly_k_cnf[0] == pytest.approx(0.1)
    assert group.p_exactly_k_cnf[1] == pytest.approx(0.5)
    assert group.p_exactly_k_cnf[2] == pytest.approx(0.4)


def test_queue_dependent_comonotonic_bounds():
    from railconfirm.inference.group import compute_queue_dependent_bounds

    assert compute_queue_dependent_bounds([]) is None

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

    group = compute_queue_dependent_bounds([p1, p2])
    assert group is not None
    # Under sequential queue clearance: min(0.8, 0.5) = 0.5
    assert group.p_all_cnf == pytest.approx(0.5)
    # P(all CNF or RAC) = min(0.8+0.1, 0.5+0.3) = min(0.9, 0.8) = 0.8
    assert group.p_all_cnf_or_rac == pytest.approx(0.8)
    # P(at least one WL) = max(0.1, 0.2) = 0.2
    assert group.p_at_least_one_wl == pytest.approx(0.2)
    assert group.method == "queue_dependent_comonotonic"
    assert "comonotonic upper bound" in group.assumptions

    # P(K >= 1) = highest probability = 0.8
    # P(K >= 2) = 2nd highest probability = 0.5
    assert group.p_at_least_k_cnf == {1: 0.8, 2: 0.5}
    # P(K = 0) = 1 - 0.8 = 0.2
    # P(K = 1) = 0.8 - 0.5 = 0.3
    # P(K = 2) = 0.5
    assert group.p_exactly_k_cnf == {0: 0.2, 1: 0.3, 2: 0.5}
    assert sum(group.p_exactly_k_cnf.values()) == pytest.approx(1.0)

    # Comonotonic joint confirmation is >= independent joint confirmation (0.5 >= 0.4)
    indep = compute_group_outcomes([p1, p2])
    assert group.p_all_cnf >= indep.p_all_cnf


def test_queue_dependent_abstains_on_abstained_passenger():
    from railconfirm.inference.group import compute_queue_dependent_bounds

    p1 = PassengerOutcome(
        passenger_id="p-1",
        p_cnf=0.8,
        p_rac=0.1,
        p_wl=0.1,
        p_cancelled=0.0,
        p_other=0.0,
        abstention_reason=None,
    )
    p2 = make_abstention_outcome("p-2", AbstentionReason.UNSUPPORTED_STATUS)
    group = compute_queue_dependent_bounds([p1, p2])
    assert group is not None
    assert group.p_all_cnf is None
    assert group.abstention_reason == AbstentionReason.UNSUPPORTED_STATUS

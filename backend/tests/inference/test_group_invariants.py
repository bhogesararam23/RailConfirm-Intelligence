"""What the group arithmetic refuses, and the invariants every published figure holds.

The distribution-level tests in ``tests/domain`` cover the shape of a ``GroupOutcome``;
this file covers the arithmetic that produces one. Every case here exists because the code
previously returned a plausible number for input it could not have meant: a probability of
``1.5`` became certainty, a NaN became certainty, an unknown method became the independence
approximation, and a group figure could exceed the event that contains it.
"""

import math

import pytest

from railconfirm.domain.exceptions import ProbabilityError
from railconfirm.domain.prediction import (
    AbstentionReason,
    GroupOutcome,
    PassengerOutcome,
    make_abstention_outcome,
)
from railconfirm.inference.group import (
    GROUP_METHODS,
    compute_group_outcomes,
    compute_poisson_binomial_pmf,
    compute_queue_dependent_bounds,
)


def passenger(passenger_id: str, cnf: float, rac: float, wl: float) -> PassengerOutcome:
    """A supported outcome whose five classes sum to one."""
    other = round(1.0 - cnf - rac - wl, 12)
    return PassengerOutcome(
        passenger_id=passenger_id,
        p_cnf=cnf,
        p_rac=rac,
        p_wl=wl,
        p_cancelled=0.0,
        p_other=other,
        abstention_reason=None,
    )


# ── Input validation: refuse, do not clamp ─────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        1.5,
        -0.2,
        float("nan"),
        float("inf"),
        float("-inf"),
        "0.5",
        None,
        True,
    ],
)
def test_a_probability_that_is_not_one_is_refused_by_the_pmf(value):
    """`1.5` used to become certainty and a NaN used to become certainty too."""
    with pytest.raises(ProbabilityError, match="must be"):
        compute_poisson_binomial_pmf([0.5, value])


def test_the_pmf_names_the_passenger_whose_input_is_wrong():
    with pytest.raises(ProbabilityError, match="Passenger 1 contributes"):
        compute_poisson_binomial_pmf([0.5, 1.5])


def test_the_edges_are_still_exact_probabilities():
    """Zero and one are valid; refusing out-of-range input must not refuse the edges."""
    assert compute_poisson_binomial_pmf([1.0, 1.0]) == [0.0, 0.0, 1.0]
    assert compute_poisson_binomial_pmf([0.0, 0.0]) == [1.0, 0.0, 0.0]


def test_an_unknown_group_method_is_refused_instead_of_silently_approximated():
    """`queue_dependent` (no suffix) used to return the independence product."""
    outcomes = [passenger("p-1", 0.8, 0.1, 0.1), passenger("p-2", 0.5, 0.3, 0.2)]
    with pytest.raises(ProbabilityError, match="Unknown group method"):
        compute_group_outcomes(outcomes, method="queue_dependent")
    assert GROUP_METHODS == ("independence_baseline", "queue_dependent_comonotonic")


def test_every_known_method_is_accepted_by_name():
    outcomes = [passenger("p-1", 0.8, 0.1, 0.1), passenger("p-2", 0.5, 0.3, 0.2)]
    for method in GROUP_METHODS:
        assert compute_group_outcomes(outcomes, method=method) is not None


# ── The joint figures ──────────────────────────────────────────────────────────


def test_an_abstaining_group_cannot_carry_a_figure():
    with pytest.raises(ProbabilityError, match="no joint probabilities"):
        GroupOutcome(
            p_all_cnf=0.4,
            p_all_cnf_or_rac=None,
            p_at_least_one_wl=None,
            method="insufficient_data",
            assumptions="stub",
            abstention_reason=AbstentionReason.NO_TRAINED_MODEL,
        )


def test_an_abstaining_group_cannot_carry_a_count_distribution():
    with pytest.raises(ProbabilityError, match="no count distribution"):
        GroupOutcome(
            p_all_cnf=None,
            p_all_cnf_or_rac=None,
            p_at_least_one_wl=None,
            method="insufficient_data",
            assumptions="stub",
            abstention_reason=AbstentionReason.NO_TRAINED_MODEL,
            p_exactly_k_cnf={0: 1.0},
            p_at_least_k_cnf={1: 0.0},
        )


def test_a_supported_group_must_set_every_figure():
    with pytest.raises(ProbabilityError, match="must set all three"):
        GroupOutcome(
            p_all_cnf=0.4,
            p_all_cnf_or_rac=None,
            p_at_least_one_wl=0.2,
            method="independence_baseline",
            assumptions="stub",
            abstention_reason=None,
        )


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), "0.4", True])
def test_a_joint_figure_outside_the_unit_interval_is_refused(value):
    with pytest.raises(ProbabilityError, match="finite probability|must be a number"):
        GroupOutcome(
            p_all_cnf=value,
            p_all_cnf_or_rac=0.8,
            p_at_least_one_wl=0.1,
            method="independence_baseline",
            assumptions="stub",
            abstention_reason=None,
        )


def test_confirmed_all_cannot_exceed_confirmed_or_rac():
    with pytest.raises(ProbabilityError, match="exceeds"):
        GroupOutcome(
            p_all_cnf=0.7,
            p_all_cnf_or_rac=0.6,
            p_at_least_one_wl=0.1,
            method="independence_baseline",
            assumptions="stub",
            abstention_reason=None,
        )


def test_settled_and_waitlisted_cannot_together_exceed_the_whole():
    """One passenger cannot be both confirmed-or-RAC and on the waitlist."""
    with pytest.raises(ProbabilityError, match="exceeds 1"):
        GroupOutcome(
            p_all_cnf=0.5,
            p_all_cnf_or_rac=0.7,
            p_at_least_one_wl=0.4,
            method="independence_baseline",
            assumptions="stub",
            abstention_reason=None,
        )


# ── The count tables ──────────────────────────────────────────────────────────


def group(**overrides) -> GroupOutcome:
    fields = {
        "p_all_cnf": 0.4,
        "p_all_cnf_or_rac": 0.72,
        "p_at_least_one_wl": 0.28,
        "method": "independence_baseline",
        "assumptions": "stub",
        "abstention_reason": None,
        "p_exactly_k_cnf": {0: 0.1, 1: 0.5, 2: 0.4},
        "p_at_least_k_cnf": {1: 0.9, 2: 0.4},
    }
    fields.update(overrides)
    return GroupOutcome(**fields)  # type: ignore[arg-type]


def test_a_consistent_pair_of_tables_is_accepted():
    assert group().p_at_least_k_cnf == {1: 0.9, 2: 0.4}


def test_the_two_tables_must_be_published_together():
    with pytest.raises(ProbabilityError, match="published together"):
        group(p_at_least_k_cnf=None)


def test_exactly_k_must_sum_to_one():
    with pytest.raises(ProbabilityError, match="sums to"):
        group(p_exactly_k_cnf={0: 0.1, 1: 0.5, 2: 0.3}, p_at_least_k_cnf={1: 0.8, 2: 0.3})


def test_at_least_k_must_be_the_tail_of_the_exactly_k_table():
    with pytest.raises(ProbabilityError, match="is not the tail"):
        group(p_at_least_k_cnf={1: 0.9, 2: 0.3})


def test_the_top_of_the_table_must_be_the_all_confirmed_figure():
    with pytest.raises(ProbabilityError, match="same event under another name"):
        group(p_all_cnf=0.5)


def test_the_tables_must_be_keyed_by_every_count():
    with pytest.raises(ProbabilityError, match="keyed by every count"):
        group(p_exactly_k_cnf={0: 0.6, 2: 0.4}, p_at_least_k_cnf={1: 0.4, 2: 0.4})


# ── What the real arithmetic produces ─────────────────────────────────────────


@pytest.mark.parametrize(
    "probabilities",
    [
        [0.9, 0.1],
        [0.5, 0.5, 0.5],
        [0.99, 0.01, 0.5, 0.75],
        [0.0, 1.0, 0.3],
        [1.0, 1.0, 1.0, 1.0],
    ],
)
def test_both_methods_publish_reconcilable_tables(probabilities):
    """The constructor checks it; this asserts it for inputs that stress the edges."""
    outcomes = [
        passenger(f"p-{index}", p, 0.0, round((1.0 - p) / 2, 12))
        for index, p in enumerate(probabilities)
    ]
    for method in GROUP_METHODS:
        result = compute_group_outcomes(outcomes, method=method)
        assert result is not None
        exactly = result.p_exactly_k_cnf or {}
        at_least = result.p_at_least_k_cnf or {}
        n = len(probabilities)
        assert sum(exactly.values()) == pytest.approx(1.0, abs=1e-5)
        assert at_least[n] == pytest.approx(result.p_all_cnf or 0.0, abs=1e-5)
        for k in range(1, n + 1):
            assert all(value >= 0.0 for value in exactly.values())
            assert at_least[k] == pytest.approx(
                sum(exactly[j] for j in range(k, n + 1)), abs=1e-5
            )


def test_the_comonotonic_bound_is_never_below_the_independence_product():
    """P(all CNF) is smallest under independence; a bound below it would be a bug."""
    outcomes = [passenger("p-1", 0.8, 0.1, 0.1), passenger("p-2", 0.5, 0.3, 0.2)]
    independence = compute_group_outcomes(outcomes, method="independence_baseline")
    comonotonic = compute_queue_dependent_bounds(outcomes)
    assert independence is not None and comonotonic is not None
    assert (comonotonic.p_all_cnf or 0.0) >= (independence.p_all_cnf or 0.0)
    assert (comonotonic.p_all_cnf_or_rac or 0.0) >= (
        independence.p_all_cnf_or_rac or 0.0
    )


def test_a_certain_group_produces_a_degenerate_table():
    """Two passengers who are both certain give one non-zero row: P(K = 2) = 1."""
    outcomes = [passenger("p-1", 1.0, 0.0, 0.0), passenger("p-2", 1.0, 0.0, 0.0)]
    for method in GROUP_METHODS:
        result = compute_group_outcomes(outcomes, method=method)
        assert result is not None
        assert result.p_all_cnf == 1.0
        assert result.p_at_least_one_wl == 0.0
        assert result.p_exactly_k_cnf == {0: 0.0, 1: 0.0, 2: 1.0}
        assert math.isclose(sum((result.p_exactly_k_cnf or {}).values()), 1.0)


def test_an_impossible_group_produces_a_degenerate_table():
    """No passenger can be confirmed, so the count table collapses to one certain row."""
    outcomes = [passenger("p-1", 0.0, 0.5, 0.5), passenger("p-2", 0.0, 0.5, 0.5)]
    for method in GROUP_METHODS:
        result = compute_group_outcomes(outcomes, method=method)
        assert result is not None
        assert result.p_all_cnf == 0.0
        assert result.p_exactly_k_cnf == {0: 1.0, 1: 0.0, 2: 0.0}
        assert result.p_at_least_k_cnf == {1: 0.0, 2: 0.0}
    # The waitlist figure is where the methods disagree, and the assumption is why:
    # independence allows both passengers to be waitlisted at once (0.75), while a shared
    # queue order makes every passenger's last-resort waitlisting one event (0.5).
    independence = compute_group_outcomes(outcomes, method="independence_baseline")
    comonotonic = compute_queue_dependent_bounds(outcomes)
    assert independence is not None and comonotonic is not None
    assert independence.p_at_least_one_wl == 0.75
    assert comonotonic.p_at_least_one_wl == 0.5


# ── The module boundary ───────────────────────────────────────────────────────


def test_a_supported_outcome_without_a_marginal_is_refused_not_read_as_zero():
    """Defence in depth: the group ran ``po.p_cnf or 0.0``, which invents a zero.

    ``PassengerOutcome`` refuses to be constructed in this state, so the object is built
    without validation to prove the arithmetic refuses it too, rather than publishing a
    group figure that quietly treated a missing number as a confirmed passenger's
    opposite.
    """
    outcome = object.__new__(PassengerOutcome)
    for name, value in (
        ("passenger_id", "p-1"),
        ("p_cnf", None),
        ("p_rac", 0.1),
        ("p_wl", 0.1),
        ("p_cancelled", 0.0),
        ("p_other", 0.8),
        ("abstention_reason", None),
        ("basis", None),
    ):
        object.__setattr__(outcome, name, value)
    for method in GROUP_METHODS:
        with pytest.raises(ProbabilityError, match="carries no p_cnf"):
            compute_group_outcomes([outcome, passenger("p-2", 0.5, 0.3, 0.2)], method=method)


def test_both_methods_abstain_for_the_same_reason():
    """Which passengers abstained decides the reason, not which method was asked for."""
    outcomes = [
        passenger("p-1", 0.8, 0.1, 0.1),
        make_abstention_outcome("p-2", AbstentionReason.UNSUPPORTED_STATUS),
    ]
    for method in GROUP_METHODS:
        result = compute_group_outcomes(outcomes, method=method)
        assert result is not None
        assert result.abstention_reason == AbstentionReason.UNSUPPORTED_STATUS
        assert result.method == "insufficient_data"
        assert result.p_exactly_k_cnf is None and result.p_at_least_k_cnf is None

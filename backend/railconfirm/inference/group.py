"""Group outcome computation for RailConfirm Intelligence.

Implements joint group outcome calculation across passengers in a booking group.

Key rules (ADR-0003, docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md):
- Passenger outcomes are not independent by default.
- The independence baseline is an approximation baseline that must be clearly
  labelled with its assumptions.
- If any passenger outcome abstains, the group outcome must also abstain.
- Single-passenger bookings trivially have group outcome equal to passenger outcome.
"""

from __future__ import annotations

import math

from railconfirm.domain.exceptions import ProbabilityError
from railconfirm.domain.prediction import (
    AbstentionReason,
    GroupOutcome,
    PassengerOutcome,
)

GROUP_METHODS: tuple[str, ...] = (
    "independence_baseline",
    "queue_dependent_comonotonic",
)
"""The two methods this module implements, and the only names a caller may ask for.

A misspelt or unimplemented method used to fall through to the independence branch, so
``method="queue_dependent"`` returned a product of marginals labelled as whatever the
caller believed it had asked for. A bound and an independence approximation are different
claims about the same booking, and nothing downstream could tell them apart."""


def _require_probability(value: object, index: int) -> float:
    """One marginal probability, refused rather than clamped."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbabilityError(
            f"Passenger {index} contributes {value!r} to the group distribution; a "
            "probability must be a number."
        )
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ProbabilityError(
            f"Passenger {index} contributes {value!r} to the group distribution; a "
            "probability must be finite and inside [0, 1]. Clamping it here would "
            "publish a group figure computed from a value nobody meant to pass."
        )
    return number


def _first_abstention(passenger_outcomes: list[PassengerOutcome]) -> AbstentionReason | None:
    """The reason the group must abstain, or None when every passenger is supported."""
    for outcome in passenger_outcomes:
        if not outcome.is_supported():
            # is_supported() is defined as "abstention_reason is None", so this branch
            # always has a reason; NO_TRAINED_MODEL is the conservative default only for
            # an outcome that somehow lost it.
            return outcome.abstention_reason or AbstentionReason.NO_TRAINED_MODEL
    return None


def _abstaining_group(reason: AbstentionReason) -> GroupOutcome:
    """The group answer when at least one passenger has no estimate."""
    return GroupOutcome(
        p_all_cnf=None,
        p_all_cnf_or_rac=None,
        p_at_least_one_wl=None,
        method="insufficient_data",
        assumptions=(
            "Group outcome is unavailable because at least one passenger outcome is an "
            "abstention."
        ),
        abstention_reason=reason,
    )


def _marginal(outcome: PassengerOutcome, field_name: str) -> float:
    """One marginal from a supported outcome, read rather than substituted.

    ``PassengerOutcome`` refuses a supported outcome that is missing a probability, so the
    None branch is unreachable from a validated object. It is still refused here instead
    of being read as zero: a group figure built on a substituted zero would look exactly
    like an estimate.
    """
    value = getattr(outcome, field_name)
    if value is None:
        raise ProbabilityError(
            f"Passenger {outcome.passenger_id} is supported but carries no {field_name}; "
            "there is no marginal to combine."
        )
    return float(value)


def _single_passenger_outcome(outcome: PassengerOutcome) -> GroupOutcome:
    """A one-passenger booking: the group event is the passenger's own outcome."""
    p_cnf = round(_marginal(outcome, "p_cnf"), 6)
    p_rac = round(_marginal(outcome, "p_rac"), 6)
    p_wl = round(_marginal(outcome, "p_wl"), 6)
    return GroupOutcome(
        p_all_cnf=p_cnf,
        p_all_cnf_or_rac=round(min(1.0, p_cnf + p_rac), 6),
        p_at_least_one_wl=p_wl,
        method="single_passenger",
        assumptions=(
            "Single passenger booking: group outcome is identical to passenger marginal "
            "outcome."
        ),
        abstention_reason=None,
        p_at_least_k_cnf={1: p_cnf},
        p_exactly_k_cnf={0: round(1.0 - p_cnf, 6), 1: p_cnf},
    )


def compute_poisson_binomial_pmf(probabilities: list[float]) -> list[float]:
    """Compute exact PMF of sum of independent Bernoulli variables (Poisson-binomial distribution).

    Parameters
    ----------
    probabilities:
        List of success probabilities p_i in [0, 1]. Anything else raises.

    Returns
    -------
    list[float]
        PMF of length len(probabilities) + 1, where index k is P(K = k).
    """
    pmf = [1.0]
    for index, p in enumerate(probabilities):
        checked = _require_probability(p, index)
        new_pmf = [0.0] * (len(pmf) + 1)
        new_pmf[0] = pmf[0] * (1.0 - checked)
        for k in range(1, len(pmf)):
            new_pmf[k] = pmf[k] * (1.0 - checked) + pmf[k - 1] * checked
        new_pmf[-1] = pmf[-1] * checked
        pmf = new_pmf
    return pmf


def compute_queue_dependent_bounds(
    passenger_outcomes: list[PassengerOutcome],
) -> GroupOutcome | None:
    """Compute comonotonic queue-clearing group bounds for passengers in a booking.

    In Indian Railways, waitlisted passengers on the same booking share a queue
    context and clear sequentially (FIFO order). Under sequential queue clearing:
    - a lower-priority passenger is confirmed only if all higher-priority passengers
      in the booking are confirmed;
    - P(all CNF) = min_i P(CNF_i);
    - P(all CNF or RAC) = min_i P(CNF_i or RAC_i);
    - P(at least one WL) = max_i P(WL_i);
    - P(at least k CNF) = k-th highest marginal confirmation probability.

    This represents the comonotonic upper bound (Fréchet-Hoeffding upper bound)
    on joint confirmation.
    """
    if not passenger_outcomes:
        return None

    reason = _first_abstention(passenger_outcomes)
    if reason is not None:
        return _abstaining_group(reason)

    n = len(passenger_outcomes)
    if n == 1:
        return _single_passenger_outcome(passenger_outcomes[0])

    # Multi-passenger comonotonic queue clearing
    cnf_probs = sorted(
        (_marginal(po, "p_cnf") for po in passenger_outcomes), reverse=True
    )
    cnf_or_rac_probs = [
        min(1.0, _marginal(po, "p_cnf") + _marginal(po, "p_rac"))
        for po in passenger_outcomes
    ]
    wl_probs = [_marginal(po, "p_wl") for po in passenger_outcomes]

    p_all_cnf = round(min(cnf_probs), 6)
    p_all_cnf_or_rac = round(min(cnf_or_rac_probs), 6)
    p_at_least_one_wl = round(max(wl_probs), 6)

    # P(K >= k) under sequential order: k-th highest probability (1-indexed)
    p_at_least_k: dict[int, float] = {}
    for k in range(1, n + 1):
        p_at_least_k[k] = round(cnf_probs[k - 1], 6)

    # P(K == k) = P(K >= k) - P(K >= k+1). The differences are already non-negative
    # because the probabilities are sorted, so no clamp is needed to make them so.
    p_exactly_k: dict[int, float] = {}
    p_exactly_k[0] = round(1.0 - cnf_probs[0], 6)
    for k in range(1, n):
        p_exactly_k[k] = round(cnf_probs[k - 1] - cnf_probs[k], 6)
    p_exactly_k[n] = round(cnf_probs[-1], 6)

    return GroupOutcome(
        p_all_cnf=p_all_cnf,
        p_all_cnf_or_rac=p_all_cnf_or_rac,
        p_at_least_one_wl=p_at_least_one_wl,
        method="queue_dependent_comonotonic",
        assumptions=(
            "Assumes sequential FIFO queue clearance without intra-booking cancellations. "
            "Lower-priority passengers confirm only if higher-priority passengers in the "
            "booking confirm, establishing the comonotonic upper bound on joint confirmation."
        ),
        abstention_reason=None,
        p_at_least_k_cnf=p_at_least_k,
        p_exactly_k_cnf=p_exactly_k,
    )


def compute_group_outcomes(
    passenger_outcomes: list[PassengerOutcome],
    *,
    method: str = "independence_baseline",
) -> GroupOutcome | None:
    """Compute group-level outcome probabilities from passenger outcomes.

    Parameters
    ----------
    passenger_outcomes:
        List of PassengerOutcome instances for all passengers in the group.
    method:
        Computation method: 'independence_baseline' (default) or
        'queue_dependent_comonotonic'. Any other name raises.

    Returns
    -------
    Optional[GroupOutcome]
        GroupOutcome or None if passenger_outcomes is empty.
    """
    if not passenger_outcomes:
        return None

    if method == "queue_dependent_comonotonic":
        return compute_queue_dependent_bounds(passenger_outcomes)
    if method not in GROUP_METHODS:
        raise ProbabilityError(
            f"Unknown group method {method!r}; this build computes "
            f"{list(GROUP_METHODS)}. Falling back to the independence baseline would "
            "return an approximation under the name of the method the caller asked for."
        )

    # Check if any passenger outcome is an abstention
    reason = _first_abstention(passenger_outcomes)
    if reason is not None:
        return _abstaining_group(reason)

    # All passenger outcomes are supported
    n = len(passenger_outcomes)

    if n == 1:
        return _single_passenger_outcome(passenger_outcomes[0])

    # Multi-passenger: compute independence baseline approximation.
    # P(all CNF or RAC) = prod(P_i(CNF) + P_i(RAC)); the min() only absorbs the tolerance
    # in each passenger's own distribution, which is validated to sum to 1.
    p_all_cnf_or_rac = 1.0
    # P(at least one WL) = 1 - prod(1 - P_i(WL))
    p_none_wl = 1.0
    cnf_probs: list[float] = []

    for po in passenger_outcomes:
        p_c = _marginal(po, "p_cnf")
        p_r = _marginal(po, "p_rac")
        p_w = _marginal(po, "p_wl")
        cnf_probs.append(p_c)

        p_all_cnf_or_rac *= min(1.0, p_c + p_r)
        p_none_wl *= 1.0 - p_w

    p_at_least_one_wl = max(0.0, min(1.0, 1.0 - p_none_wl))

    # Exact Poisson-binomial distribution for number of confirmed passengers
    pmf = compute_poisson_binomial_pmf(cnf_probs)
    p_exactly_k = {k: round(value, 6) for k, value in enumerate(pmf)}
    # The tail sums use the rounded exactly-k values, so the two published tables agree
    # by construction rather than to within a rounding step.
    p_at_least_k: dict[int, float] = {
        k: round(sum(p_exactly_k[j] for j in range(k, n + 1)), 6) for k in range(1, n + 1)
    }

    return GroupOutcome(
        p_all_cnf=p_exactly_k[n],
        p_all_cnf_or_rac=round(p_all_cnf_or_rac, 6),
        p_at_least_one_wl=round(p_at_least_one_wl, 6),
        method="independence_baseline",
        assumptions=(
            "Assumes passenger confirmation outcomes are statistically independent. "
            "This is an uncalibrated baseline approximation — real group outcomes exhibit "
            "positive correlation due to shared booking queue position and quota allocation."
        ),
        abstention_reason=None,
        p_at_least_k_cnf=p_at_least_k,
        p_exactly_k_cnf=p_exactly_k,
    )

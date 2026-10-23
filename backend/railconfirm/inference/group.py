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

from railconfirm.domain.prediction import (
    AbstentionReason,
    GroupOutcome,
    PassengerOutcome,
)


def compute_poisson_binomial_pmf(probabilities: list[float]) -> list[float]:
    """Compute exact PMF of sum of independent Bernoulli variables (Poisson-binomial distribution).

    Parameters
    ----------
    probabilities:
        List of success probabilities p_i in [0, 1].

    Returns
    -------
    list[float]
        PMF of length len(probabilities) + 1, where index k is P(K = k).
    """
    pmf = [1.0]
    for p in probabilities:
        clamped_p = max(0.0, min(1.0, float(p)))
        new_pmf = [0.0] * (len(pmf) + 1)
        new_pmf[0] = pmf[0] * (1.0 - clamped_p)
        for k in range(1, len(pmf)):
            new_pmf[k] = pmf[k] * (1.0 - clamped_p) + pmf[k - 1] * clamped_p
        new_pmf[-1] = pmf[-1] * clamped_p
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

    for po in passenger_outcomes:
        if not po.is_supported():
            reason = po.abstention_reason or AbstentionReason.NO_TRAINED_MODEL
            return GroupOutcome(
                p_all_cnf=None,
                p_all_cnf_or_rac=None,
                p_at_least_one_wl=None,
                method="insufficient_data",
                assumptions=(
                    "Group outcome is unavailable because at least one passenger "
                    "outcome is an abstention."
                ),
                abstention_reason=reason,
            )

    n = len(passenger_outcomes)
    if n == 1:
        po = passenger_outcomes[0]
        p_cnf = round(po.p_cnf or 0.0, 6)
        p_rac = round(po.p_rac or 0.0, 6)
        p_wl = round(po.p_wl or 0.0, 6)
        return GroupOutcome(
            p_all_cnf=p_cnf,
            p_all_cnf_or_rac=round(min(1.0, p_cnf + p_rac), 6),
            p_at_least_one_wl=p_wl,
            method="single_passenger",
            assumptions="Single passenger booking: group outcome is identical to passenger marginal outcome.",
            abstention_reason=None,
            p_at_least_k_cnf={1: p_cnf},
            p_exactly_k_cnf={0: round(max(0.0, 1.0 - p_cnf), 6), 1: p_cnf},
        )

    # Multi-passenger comonotonic queue clearing
    cnf_probs = sorted([po.p_cnf or 0.0 for po in passenger_outcomes], reverse=True)
    cnf_or_rac_probs = [min(1.0, (po.p_cnf or 0.0) + (po.p_rac or 0.0)) for po in passenger_outcomes]
    wl_probs = [po.p_wl or 0.0 for po in passenger_outcomes]

    p_all_cnf = round(min(cnf_probs), 6)
    p_all_cnf_or_rac = round(min(cnf_or_rac_probs), 6)
    p_at_least_one_wl = round(max(wl_probs), 6)

    # P(K >= k) under sequential order: k-th highest probability (1-indexed)
    p_at_least_k: dict[int, float] = {}
    for k in range(1, n + 1):
        p_at_least_k[k] = round(cnf_probs[k - 1], 6)

    # P(K == k) = P(K >= k) - P(K >= k+1)
    p_exactly_k: dict[int, float] = {}
    p_exactly_k[0] = round(max(0.0, 1.0 - cnf_probs[0]), 6)
    for k in range(1, n):
        p_exactly_k[k] = round(max(0.0, cnf_probs[k - 1] - cnf_probs[k]), 6)
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
        Computation method: 'independence_baseline' (default) or 'queue_dependent_comonotonic'.

    Returns
    -------
    Optional[GroupOutcome]
        GroupOutcome or None if passenger_outcomes is empty.
    """
    if not passenger_outcomes:
        return None

    if method == "queue_dependent_comonotonic":
        return compute_queue_dependent_bounds(passenger_outcomes)

    # Check if any passenger outcome is an abstention
    for po in passenger_outcomes:
        if not po.is_supported():
            reason = po.abstention_reason or AbstentionReason.NO_TRAINED_MODEL
            return GroupOutcome(
                p_all_cnf=None,
                p_all_cnf_or_rac=None,
                p_at_least_one_wl=None,
                method="insufficient_data",
                assumptions=(
                    "Group outcome is unavailable because at least one passenger "
                    "outcome is an abstention."
                ),
                abstention_reason=reason,
            )

    # All passenger outcomes are supported
    n = len(passenger_outcomes)

    if n == 1:
        po = passenger_outcomes[0]
        p_cnf = round(po.p_cnf or 0.0, 6)
        p_rac = round(po.p_rac or 0.0, 6)
        p_wl = round(po.p_wl or 0.0, 6)
        return GroupOutcome(
            p_all_cnf=p_cnf,
            p_all_cnf_or_rac=round(min(1.0, p_cnf + p_rac), 6),
            p_at_least_one_wl=p_wl,
            method="single_passenger",
            assumptions="Single passenger booking: group outcome is identical to passenger marginal outcome.",
            abstention_reason=None,
            p_at_least_k_cnf={1: p_cnf},
            p_exactly_k_cnf={0: round(max(0.0, 1.0 - p_cnf), 6), 1: p_cnf},
        )

    # Multi-passenger: compute independence baseline approximation
    # P(all CNF) = prod(P_i(CNF))
    p_all_cnf = 1.0
    # P(all CNF or RAC) = prod(P_i(CNF) + P_i(RAC))
    p_all_cnf_or_rac = 1.0
    # P(at least one WL) = 1 - prod(1 - P_i(WL))
    p_none_wl = 1.0
    cnf_probs: list[float] = []

    for po in passenger_outcomes:
        p_c = po.p_cnf or 0.0
        p_r = po.p_rac or 0.0
        p_w = po.p_wl or 0.0
        cnf_probs.append(p_c)

        p_all_cnf *= p_c
        p_all_cnf_or_rac *= min(1.0, p_c + p_r)
        p_none_wl *= max(0.0, 1.0 - p_w)

    p_at_least_one_wl = max(0.0, min(1.0, 1.0 - p_none_wl))

    # Exact Poisson-binomial distribution for number of confirmed passengers
    pmf = compute_poisson_binomial_pmf(cnf_probs)
    p_exactly_k = {k: round(val, 6) for k, val in enumerate(pmf)}

    # P(K >= k) = sum_{j=k}^n P(K = j)
    p_at_least_k: dict[int, float] = {}
    for k in range(1, n + 1):
        p_at_least_k[k] = round(sum(pmf[k:]), 6)

    return GroupOutcome(
        p_all_cnf=round(p_all_cnf, 6),
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

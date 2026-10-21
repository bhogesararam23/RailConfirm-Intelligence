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
from typing import Optional

from railconfirm.domain.prediction import (
    AbstentionReason,
    GroupOutcome,
    PassengerOutcome,
)


def compute_group_outcomes(
    passenger_outcomes: list[PassengerOutcome],
) -> Optional[GroupOutcome]:
    """Compute group-level outcome probabilities from passenger outcomes.

    Parameters
    ----------
    passenger_outcomes:
        List of PassengerOutcome instances for all passengers in the group.

    Returns
    -------
    Optional[GroupOutcome]
        GroupOutcome or None if passenger_outcomes is empty.
    """
    if not passenger_outcomes:
        return None

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
        p_cnf = po.p_cnf or 0.0
        p_rac = po.p_rac or 0.0
        p_wl = po.p_wl or 0.0
        return GroupOutcome(
            p_all_cnf=p_cnf,
            p_all_cnf_or_rac=min(1.0, p_cnf + p_rac),
            p_at_least_one_wl=p_wl,
            method="single_passenger",
            assumptions="Single passenger booking: group outcome is identical to passenger marginal outcome.",
            abstention_reason=None,
        )

    # Multi-passenger: compute independence baseline approximation
    # P(all CNF) = prod(P_i(CNF))
    p_all_cnf = 1.0
    # P(all CNF or RAC) = prod(P_i(CNF) + P_i(RAC))
    p_all_cnf_or_rac = 1.0
    # P(at least one WL) = 1 - prod(1 - P_i(WL))
    p_none_wl = 1.0

    for po in passenger_outcomes:
        p_c = po.p_cnf or 0.0
        p_r = po.p_rac or 0.0
        p_w = po.p_wl or 0.0

        p_all_cnf *= p_c
        p_all_cnf_or_rac *= min(1.0, p_c + p_r)
        p_none_wl *= max(0.0, 1.0 - p_w)

    p_at_least_one_wl = max(0.0, min(1.0, 1.0 - p_none_wl))

    return GroupOutcome(
        p_all_cnf=p_all_cnf,
        p_all_cnf_or_rac=p_all_cnf_or_rac,
        p_at_least_one_wl=p_at_least_one_wl,
        method="independence_baseline",
        assumptions=(
            "Assumes passenger confirmation outcomes are statistically independent. "
            "This is an uncalibrated baseline approximation — real group outcomes exhibit "
            "positive correlation due to shared booking queue position and quota allocation."
        ),
        abstention_reason=None,
    )

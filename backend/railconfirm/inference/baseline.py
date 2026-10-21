"""Historical frequency baseline estimator for RailConfirm Intelligence.

This baseline estimates probabilities from smoothed historical frequencies
loaded from an approved local dataset. It is an assumption-driven fallback
and must be clearly labelled as such in all outputs.

Key rules
---------
* Falls back to abstention if no approved dataset is available.
* Uses Laplace smoothing for sparse categories.
* Returns AbstentionReason.INSUFFICIENT_SAMPLE when count < threshold.
* Never fabricates numbers — all estimates must be traceable to real data.
"""

from __future__ import annotations

import logging

from railconfirm.config import settings
from railconfirm.domain.prediction import (
    AbstentionReason,
    PassengerOutcome,
    make_abstention_outcome,
)
from railconfirm.domain.status import NormalizedStatus, ParsedStatus

logger = logging.getLogger(__name__)

# ── Laplace smoothing constant ─────────────────────────────────────────────────
# Applied to each outcome class bin to avoid zero probabilities for unseen categories.
_LAPLACE_ALPHA = 1.0
_N_CLASSES = 5  # CNF, RAC, WL, CANCELLED, OTHER


class HistoricalFrequencyBaseline:
    """Estimate outcome probabilities from smoothed historical frequencies.

    This is an approximation baseline — not a trained model. It is only used
    when no trained model artifact is available.

    Parameters
    ----------
    min_sample_threshold:
        Minimum number of historical samples required to produce an estimate.
        Below this threshold the estimator abstains with INSUFFICIENT_SAMPLE.
    """

    def __init__(
        self,
        min_sample_threshold: int | None = None,
    ) -> None:
        self.min_sample_threshold = (
            min_sample_threshold
            if min_sample_threshold is not None
            else settings.min_sample_threshold
        )
        # Frequency table: loaded from approved dataset if one exists.
        # Key: (class_code, quota_code, normalized_status)
        # Value: dict mapping outcome → count
        self._freq_table: dict[tuple, dict[str, int]] = {}
        self._is_loaded = False

    def load_frequencies(
        self, freq_table: dict[tuple, dict[str, int]]
    ) -> None:
        """Load pre-computed frequency counts from an approved dataset.

        Parameters
        ----------
        freq_table:
            Mapping of (class_code, quota_code, normalized_initial_status)
            to a dict of {outcome_class: count}.
        """
        self._freq_table = freq_table
        self._is_loaded = True
        logger.info(
            "HistoricalFrequencyBaseline loaded with %d category entries.",
            len(freq_table),
        )

    def estimate(
        self,
        passenger_id: str,
        parsed_status: ParsedStatus,
        class_code: str,
        quota_code: str,
    ) -> PassengerOutcome:
        """Return a smoothed frequency estimate or an abstention.

        Parameters
        ----------
        passenger_id:
            Unique passenger ID for the outcome record.
        parsed_status:
            The parsed current status for this passenger.
        class_code:
            Journey class code.
        quota_code:
            Journey quota code.

        Returns
        -------
        PassengerOutcome
            Either a supported estimate or an abstention with a reason code.
        """
        # ── Unknown status → abstain ───────────────────────────────────────────
        if parsed_status.normalized == NormalizedStatus.UNKNOWN:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.UNKNOWN_STATUS,
            )

        # ── No dataset loaded → abstain ────────────────────────────────────────
        if not self._is_loaded or not self._freq_table:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.NO_TRAINED_MODEL,
            )

        # ── Look up frequency counts ───────────────────────────────────────────
        key = (
            class_code.upper(),
            quota_code.upper(),
            parsed_status.normalized.value,
        )
        counts = self._freq_table.get(key)

        if counts is None:
            # No data for this combination — check a broader fallback.
            key_broad = (class_code.upper(), quota_code.upper(), "ALL")
            counts = self._freq_table.get(key_broad)

        if counts is None:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )

        # ── Check minimum sample threshold ─────────────────────────────────────
        total_count = sum(counts.values())
        if total_count < self.min_sample_threshold:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )

        # ── Laplace-smoothed frequencies ───────────────────────────────────────
        outcomes = ["CNF", "RAC", "WL", "CANCELLED", "OTHER"]
        denom = total_count + _LAPLACE_ALPHA * _N_CLASSES
        raw_probs = [(counts.get(o, 0) + _LAPLACE_ALPHA) / denom for o in outcomes]
        prob_sum = sum(raw_probs)
        probs = [p / prob_sum for p in raw_probs]

        return PassengerOutcome(
            passenger_id=passenger_id,
            p_cnf=probs[0],
            p_rac=probs[1],
            p_wl=probs[2],
            p_cancelled=probs[3],
            p_other=probs[4],
            abstention_reason=None,
        )

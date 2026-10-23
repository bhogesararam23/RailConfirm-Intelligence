"""Historical frequency baseline estimator for RailConfirm Intelligence.

This baseline estimates probabilities from smoothed historical frequencies
loaded from an approved local dataset. It is an assumption-driven fallback and
must be clearly labelled as such in all outputs. It is *not* a trained,
calibrated machine-learning model and must never be presented as one.

Key rules
---------
* A frequency table cannot be installed without provenance, and provenance that
  is not approved for estimation yields abstention rather than numbers.
* Structural problems in a table (unknown outcome keys, negative or fractional
  counts, colliding cohort keys) are raised at load time. They are never
  smoothed into a plausible-looking distribution.
* Statuses outside the reservation queue have no final-chart outcome to
  estimate and abstain as unsupported.
* Below the minimum sample threshold the estimator abstains.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass

from railconfirm.config import settings
from railconfirm.domain.exceptions import FrequencyTableValidationError
from railconfirm.domain.prediction import (
    AbstentionReason,
    PassengerOutcome,
    make_abstention_outcome,
)
from railconfirm.domain.status import (
    MAPPING_VERSION,
    TARGET_ELIGIBLE_STATUSES,
    NormalizedStatus,
    ParsedStatus,
)

logger = logging.getLogger(__name__)

# The explicitly defined outcome space. Every supported distribution is over
# exactly these classes, mutually exclusive and exhaustive.
OUTCOME_CLASSES: tuple[str, ...] = ("CNF", "RAC", "WL", "CANCELLED", "OTHER")

# Pseudo-status used by a broad-cohort row that aggregates across statuses for a
# class/quota pair. Kept separate so a fallback is never mistaken for an exact
# cohort match.
BROAD_COHORT_STATUS = "ALL"

# Laplace smoothing applied per outcome class to keep unseen classes at a small
# non-zero probability instead of a hard zero.
DEFAULT_LAPLACE_ALPHA = 1.0

_APPROVED_STATUS = "approved"


@dataclass(frozen=True)
class FrequencyTableProvenance:
    """Where a frequency table came from and what it may be used for.

    A mechanical validator cannot prove that a dataset is licensed for training,
    so the approval decision is carried here as an explicit, reviewable field
    rather than being inferred from a passing quality report.
    """

    dataset_id: str
    sha256: str
    source_reference: str
    approval_status: str
    is_synthetic: bool
    mapping_version: str = MAPPING_VERSION
    fitted_from: str | None = None
    fitted_to: str | None = None
    notes: str | None = None
    evaluation_only: bool = False
    """True when this table exists to exercise the pipeline, never to answer a user.

    A synthetic cohort table can legitimately be scored against synthetic rows:
    that is how the metrics code is checked. It can never produce a served
    prediction, because a model artifact carries no such flag and the registry
    rejects synthetic provenance outright.
    """

    def approved_for_estimation(self) -> bool:
        """Return True when this table may produce estimates.

        A real dataset explicitly approved for use qualifies. Synthetic rows
        qualify only for an evaluation-only table, which exists solely to verify
        the pipeline and is never reachable from the serving path.
        """
        if self.approval_status != _APPROVED_STATUS:
            return False
        return not self.is_synthetic or self.evaluation_only


FrequencyTable = Mapping[tuple[str, str, str], Mapping[str, int]]


def _validate_cohort_key(key: object) -> tuple[str, str, str]:
    if not isinstance(key, tuple) or len(key) != 3:
        raise FrequencyTableValidationError(
            f"Cohort keys must be (class_code, quota_code, status) 3-tuples, got {key!r}."
        )
    parts = tuple(str(part).strip().upper() for part in key)
    class_code, quota_code, status = parts
    for name, value in (("class_code", class_code), ("quota_code", quota_code)):
        if not value:
            raise FrequencyTableValidationError(
                f"Cohort {key!r} has an empty {name}."
            )
    known_statuses = {member.value for member in NormalizedStatus} | {BROAD_COHORT_STATUS}
    if status not in known_statuses:
        raise FrequencyTableValidationError(
            f"Cohort {key!r} uses status {status!r}, which is not a normalized "
            f"status category {sorted(known_statuses - {BROAD_COHORT_STATUS})} or "
            f"the {BROAD_COHORT_STATUS!r} broad cohort."
        )
    return class_code, quota_code, status


def _validate_counts(counts: object, cohort: tuple[str, str, str]) -> dict[str, int]:
    if not isinstance(counts, Mapping):
        raise FrequencyTableValidationError(
            f"Cohort {cohort} counts must be a mapping of outcome class to count, "
            f"got {type(counts).__name__}."
        )
    if not counts:
        raise FrequencyTableValidationError(f"Cohort {cohort} has no outcome counts.")

    validated: dict[str, int] = {}
    for outcome, count in counts.items():
        if outcome not in OUTCOME_CLASSES:
            raise FrequencyTableValidationError(
                f"Cohort {cohort} reports outcome {outcome!r}, which is outside the "
                f"defined outcome space {list(OUTCOME_CLASSES)}. An unrecognised label "
                "must be fixed in the fitting step, not smoothed away."
            )
        # bool is a subclass of int but is never a count.
        if isinstance(count, bool) or not isinstance(count, int):
            raise FrequencyTableValidationError(
                f"Cohort {cohort} outcome {outcome!r} has count {count!r} of type "
                f"{type(count).__name__}; counts must be integers, so a fractional "
                "value means the aggregation step is wrong."
            )
        if count < 0:
            raise FrequencyTableValidationError(
                f"Cohort {cohort} outcome {outcome!r} has negative count {count}."
            )
        validated[outcome] = count

    if sum(validated.values()) <= 0:
        raise FrequencyTableValidationError(
            f"Cohort {cohort} has no positive counts, so it carries no evidence."
        )
    return validated


def normalize_frequency_table(table: FrequencyTable) -> dict[tuple[str, str, str], dict[str, int]]:
    """Validate and canonicalise a frequency table for inference-time lookup.

    Keys are uppercased and stripped so that a table fitted with lowercase codes
    still matches at inference time, and collisions are rejected instead of
    silently overwriting one another.

    Raises
    ------
    FrequencyTableValidationError
        If the table is empty or any cohort is structurally unusable.
    """
    if not isinstance(table, Mapping):
        raise FrequencyTableValidationError(
            f"Frequency table must be a mapping of cohort to counts, got "
            f"{type(table).__name__}."
        )
    if not table:
        raise FrequencyTableValidationError("Frequency table is empty.")

    normalized: dict[tuple[str, str, str], dict[str, int]] = {}
    for raw_key, raw_counts in table.items():
        cohort = _validate_cohort_key(raw_key)
        if cohort in normalized:
            raise FrequencyTableValidationError(
                f"Cohort keys {raw_key!r} collide with an earlier entry after "
                "normalisation; the table would silently discard one of them."
            )
        normalized[cohort] = _validate_counts(raw_counts, cohort)
    return normalized


class HistoricalFrequencyBaseline:
    """Estimate outcome probabilities from smoothed historical frequencies.

    This is an approximation baseline used when no trained model artifact is
    active. Estimates are only produced from a table whose provenance is
    explicitly approved; otherwise every request abstains.

    Parameters
    ----------
    min_sample_threshold:
        Minimum number of historical records in a cohort required to produce an
        estimate. Below this the estimator abstains with INSUFFICIENT_SAMPLE.
    laplace_alpha:
        Additive smoothing weight per outcome class. Must be positive and finite.
    """

    def __init__(
        self,
        min_sample_threshold: int | None = None,
        laplace_alpha: float = DEFAULT_LAPLACE_ALPHA,
    ) -> None:
        if isinstance(min_sample_threshold, bool) or (
            min_sample_threshold is not None and min_sample_threshold < 1
        ):
            raise ValueError(
                f"min_sample_threshold must be a positive integer, got {min_sample_threshold!r}."
            )
        if not math.isfinite(laplace_alpha) or laplace_alpha <= 0:
            raise ValueError(
                f"laplace_alpha must be positive and finite, got {laplace_alpha!r}."
            )

        self.min_sample_threshold = (
            min_sample_threshold
            if min_sample_threshold is not None
            else settings.min_sample_threshold
        )
        self.laplace_alpha = laplace_alpha
        self._table: dict[tuple[str, str, str], dict[str, int]] = {}
        self._provenance: FrequencyTableProvenance | None = None

    @property
    def is_loaded(self) -> bool:
        """True when a validated frequency table is installed."""
        return bool(self._table)

    @property
    def provenance(self) -> FrequencyTableProvenance | None:
        return self._provenance

    def load_frequency_table(
        self,
        table: FrequencyTable,
        provenance: FrequencyTableProvenance,
    ) -> None:
        """Install a validated frequency table together with its provenance.

        The table is validated before anything is stored, so a failed load
        leaves the previous state untouched.
        """
        if not isinstance(provenance, FrequencyTableProvenance):
            raise FrequencyTableValidationError(
                "A frequency table must be loaded with FrequencyTableProvenance; "
                "estimates without recorded provenance cannot be defended."
            )
        normalized = normalize_frequency_table(table)
        self._table = normalized
        self._provenance = provenance
        logger.info(
            "HistoricalFrequencyBaseline loaded %d cohorts from dataset %s "
            "(approval=%s, synthetic=%s, approved_for_estimation=%s).",
            len(normalized),
            provenance.dataset_id,
            provenance.approval_status,
            provenance.is_synthetic,
            provenance.approved_for_estimation(),
        )

    def clear(self) -> None:
        """Remove any installed table and provenance."""
        self._table = {}
        self._provenance = None

    def _lookup(self, class_code: str, quota_code: str, status: str) -> tuple[
        tuple[str, str, str], dict[str, int], bool
    ] | None:
        """Return the matching cohort, its counts, and whether it was a fallback."""
        cls = class_code.strip().upper()
        quota = quota_code.strip().upper()

        exact = (cls, quota, status)
        counts = self._table.get(exact)
        if counts is not None:
            return exact, counts, False

        broad = (cls, quota, BROAD_COHORT_STATUS)
        counts = self._table.get(broad)
        if counts is not None:
            return broad, counts, True
        return None

    def estimate(
        self,
        passenger_id: str,
        parsed_status: ParsedStatus,
        class_code: str,
        quota_code: str,
    ) -> PassengerOutcome:
        """Return a smoothed frequency estimate or an abstention.

        Abstention reasons are ordered from the most actionable to the least:
        an unmappable status, then a status outside the target population, then
        a missing evidence base, then a cohort too small to report.
        """
        if parsed_status.normalized == NormalizedStatus.UNKNOWN:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.UNKNOWN_STATUS,
            )

        if parsed_status.normalized not in TARGET_ELIGIBLE_STATUSES:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.UNSUPPORTED_STATUS,
            )

        if not self._table:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.NO_APPROVED_DATA,
            )

        provenance = self._provenance
        if provenance is None or not provenance.approved_for_estimation():
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.NO_APPROVED_DATA,
            )

        matched = self._lookup(class_code, quota_code, parsed_status.normalized.value)
        if matched is None:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )

        cohort, counts, is_fallback = matched
        total_count = sum(counts.values())
        if total_count < self.min_sample_threshold:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )

        probs = self._smoothed_distribution(counts)
        basis = (
            f"cohort={'/'.join(cohort)} n={total_count} "
            f"exact_status_match=false (broad {BROAD_COHORT_STATUS} cohort fallback)"
            if is_fallback
            else f"cohort={'/'.join(cohort)} n={total_count} exact_status_match=true"
        )

        return PassengerOutcome(
            passenger_id=passenger_id,
            p_cnf=probs["CNF"],
            p_rac=probs["RAC"],
            p_wl=probs["WL"],
            p_cancelled=probs["CANCELLED"],
            p_other=probs["OTHER"],
            abstention_reason=None,
            basis=basis,
        )

    def _smoothed_distribution(self, counts: Mapping[str, int]) -> dict[str, float]:
        """Add-alpha smoothing over the fixed outcome space, normalised to 1.

        Unknown keys and malformed counts cannot reach this method: the table is
        validated when it is loaded.
        """
        n_classes = len(OUTCOME_CLASSES)
        denom = sum(counts.values()) + self.laplace_alpha * n_classes
        return {
            outcome: (counts.get(outcome, 0) + self.laplace_alpha) / denom
            for outcome in OUTCOME_CLASSES
        }

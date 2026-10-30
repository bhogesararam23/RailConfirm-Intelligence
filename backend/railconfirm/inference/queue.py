"""Cohort-position baseline: the queue position the as-of status already carries.

The frequency baseline answers every passenger in a cohort with one number, so a berth first
in the waitlist and one two hundred deep get the same probability. This estimator keeps the
same cohort key — class, quota and the as-of status, exactly what the request supplies
(ADR-0013) — and splits each cohort by the as-of queue position, because that is the one
piece of information a waiting reservation actually conveys.

Key rules
---------
* Band cut points are fixed doubling widths (1, 2-3, 4-7, 8-15, …), never quantiles of the
  training file. Cuts derived from data move when the data moves, which would make a served
  probability depend on which rows happened to be in the fitting period.
* A band that is too thin to carry a rate does not get one: the cohort answers, and the basis
  says that is what happened. A rate from three rows is noise wearing a decimal point.
* An absent position is absent, never zero. Fabricating "first in queue" would hand the
  shallowest, most confident answer to a passenger whose depth is unknown.
* Every trust gate the frequency baseline enforces applies here unchanged: provenance that may
  not estimate abstains, malformed cells raise at load, and statuses outside the target
  population abstain.
"""

from __future__ import annotations

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
    TARGET_ELIGIBLE_STATUSES,
    NormalizedStatus,
    ParsedStatus,
)
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    DEFAULT_LAPLACE_ALPHA,
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    cohort_key,
    normalize_frequency_table,
    validate_cohort_key,
    validate_outcome_counts,
)

QUEUE_ESTIMATOR_ID = "cohort_position_baseline"
"""The artifact's own statement of which arithmetic produced it.

The registry builds the estimator named here, so a table of cohort totals can never be
answered by band cells, or the reverse, on the strength of a file name."""

QUEUE_FEATURES: tuple[str, ...] = (
    "class_code",
    "quota_code",
    "asof_normalized",
    "asof_position",
)
"""What this estimator reads, including the position the frequency baseline ignores.

Declared on the artifact and checked at load: the report credits a model with features only
when its own arithmetic consumes them."""

QUEUE_ARTIFACT_FORMAT = "railconfirm.cohort-position-baseline/1"
"""Its own format rather than a new revision of the frequency table's.

The payload adds a second, differently keyed table, so a reader must be able to tell which
model a file describes from the format string alone. Existing `/2` artifacts keep meaning
exactly what they meant."""

DEFAULT_MIN_BAND_ROWS = 2
"""Rows a band cell needs before it may answer.

Two is the smallest count that can express a rate rather than a single outcome, and below it
the cohort's own number is the honest answer. A band floor is deliberately far below the
cohort floor: bands split a cohort, so requiring the cohort threshold of every band would
make the position almost never get used."""

BAND_CEILINGS: tuple[tuple[int, str], ...] = (
    (1, "1"),
    (3, "2-3"),
    (7, "4-7"),
    (15, "8-15"),
    (31, "16-31"),
    (63, "32-63"),
    (127, "64-127"),
)
"""Doubling widths, closed at the top so depth beyond 127 is one cell rather than forty."""

LAST_BAND_LABEL = "128+"

BandKey = tuple[str, str, str, str]
BandTable = Mapping[BandKey, Mapping[str, int]]


def position_band(position: int | None) -> str | None:
    """The band label an as-of queue position falls in, or None when there is no position.

    Raises on a non-positive position rather than clamping it: `WL/0` is an unusable position
    that the status parser already records as a parse note, and quietly banding it as 1 would
    invent the shallowest queue.
    """
    if position is None:
        return None
    if isinstance(position, bool) or not isinstance(position, int) or position < 1:
        raise ValueError(
            f"An as-of queue position must be a positive integer or None, got {position!r}."
        )
    for ceiling, label in BAND_CEILINGS:
        if position <= ceiling:
            return label
    return LAST_BAND_LABEL


def band_labels() -> tuple[str, ...]:
    """Every band label the model can produce, in queue order."""
    return tuple(label for _, label in BAND_CEILINGS) + (LAST_BAND_LABEL,)


def _validate_band_key(raw_key: object) -> BandKey:
    """Read one band key, refusing anything the estimator could never look up.

    Both halves are checked against the code that produces them rather than against a copy
    of it: the first three parts are a cohort key, validated by the same rule the cohort
    table uses, and the fourth must be a label ``position_band`` can return. A cell outside
    either set is unreachable at every request, and its presence would make an artifact
    look position-aware while every answer came from the cohort.
    """
    if not isinstance(raw_key, tuple):
        raise FrequencyTableValidationError(
            f"Band key {raw_key!r} must be a four-part tuple (class_code, quota_code, "
            "status, band)."
        )
    if len(raw_key) != 4:
        raise FrequencyTableValidationError(
            f"Band key {raw_key!r} must be a four-part tuple (class_code, quota_code, "
            "status, band); a three-part key names a cohort, not a band."
        )
    cohort = validate_cohort_key(raw_key[:3])
    band = str(raw_key[3]).strip()
    if not band:
        raise FrequencyTableValidationError(
            f"Band key {raw_key!r} names no band, so no request could ever match it."
        )
    reachable = band_labels()
    if band not in reachable:
        raise FrequencyTableValidationError(
            f"Band key {raw_key!r} names band {band!r}, which this build never produces. "
            f"The reachable bands are {list(reachable)}: the cuts are fixed doubling widths "
            "(ADR-0020), so a neighbouring or rounded label is a different model's table."
        )
    return (*cohort, band)


def validate_band_cohorts(
    cohorts: Mapping[tuple[str, str, str], object],
    bands: Mapping[BandKey, object],
) -> None:
    """Refuse a band cell whose cohort has no row of its own.

    ``CohortPositionBaseline.estimate`` resolves the cohort first and answers from the band
    only afterwards, so a band cell without a parent cohort row can never be reached — and
    a table made only of such cells is the frequency model wearing the position model's
    name. Best read as the cross-check it is: the band table is a refinement of the cohort
    table, and a refinement of rows that do not exist is an orphan.
    """
    orphans = sorted({key[:3] for key in bands} - set(cohorts))
    if orphans:
        raise FrequencyTableValidationError(
            f"Band cells {orphans} name cohorts with no row in the cohort table. The "
            "estimator resolves the cohort before it reads a band, so these cells could "
            "never answer a request; fit them against the cohorts they refine."
        )



def normalize_band_table(table: BandTable) -> dict[BandKey, dict[str, int]]:
    """Validate and canonicalise the position-band table the way cohort tables already are.

    Keys are stripped and uppercased so a table fitted with lowercase codes still matches at
    inference, collisions after normalisation are refused rather than resolved by whichever
    row came last, and a malformed cell raises here instead of being smoothed later.
    """
    if not isinstance(table, Mapping):
        raise FrequencyTableValidationError(
            f"Band table must be a mapping of (class, quota, status, band) to counts, got "
            f"{type(table).__name__}."
        )
    if not table:
        raise FrequencyTableValidationError(
            "Band table is empty: a position-aware model with no position cells answers every "
            "request from the cohort, which is the other estimator."
        )

    normalized: dict[BandKey, dict[str, int]] = {}
    for raw_key, raw_counts in table.items():
        band_key = _validate_band_key(raw_key)
        if band_key in normalized:
            raise FrequencyTableValidationError(
                f"Band keys {raw_key!r} collide with an earlier entry after normalisation; "
                "the table would silently discard one of them."
            )
        normalized[band_key] = validate_outcome_counts(raw_counts, band_key)
    return normalized


@dataclass(frozen=True)
class _Answered:
    """Which cell answered, so the basis can say so in the same words every time."""

    cohort: tuple[str, str, str]
    cohort_counts: dict[str, int]
    is_fallback: bool
    band: str | None
    band_counts: dict[str, int] | None


class CohortPositionBaseline:
    """Estimate outcome probabilities from cohort rates split by as-of queue position.

    Parameters
    ----------
    min_sample_threshold:
        Rows a cohort needs before it may answer at all — the same floor the frequency
        baseline applies, so a thin cohort abstains in both models rather than answering
        confidently in one.
    laplace_alpha:
        Additive smoothing per outcome class, applied to band cells and cohorts alike.
    min_band_rows:
        Rows a band cell needs before it may answer; below it the cohort answers and the
        basis records the substitution.
    """

    def __init__(
        self,
        min_sample_threshold: int | None = None,
        laplace_alpha: float = DEFAULT_LAPLACE_ALPHA,
        min_band_rows: int = DEFAULT_MIN_BAND_ROWS,
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
        if isinstance(min_band_rows, bool) or not isinstance(min_band_rows, int) or (
            min_band_rows < 1
        ):
            raise ValueError(
                f"min_band_rows must be a positive integer, got {min_band_rows!r}."
            )

        self.min_sample_threshold = (
            min_sample_threshold
            if min_sample_threshold is not None
            else settings.min_sample_threshold
        )
        self.laplace_alpha = laplace_alpha
        self.min_band_rows = min_band_rows
        self._cohorts: dict[tuple[str, str, str], dict[str, int]] = {}
        self._bands: dict[BandKey, dict[str, int]] = {}
        self._provenance: FrequencyTableProvenance | None = None

    @property
    def is_loaded(self) -> bool:
        return bool(self._cohorts)

    @property
    def cohort_count(self) -> int:
        return len(self._cohorts)

    @property
    def band_count(self) -> int:
        return len(self._bands)

    @property
    def provenance(self) -> FrequencyTableProvenance | None:
        return self._provenance

    def load_tables(
        self,
        cohorts: Mapping[tuple[str, str, str], Mapping[str, int]],
        bands: BandTable,
        provenance: FrequencyTableProvenance,
    ) -> None:
        """Install both tables only if both validate; a half-loaded model is not a model."""
        normalized_cohorts = normalize_frequency_table(cohorts)
        normalized_bands = normalize_band_table(bands)
        validate_band_cohorts(normalized_cohorts, normalized_bands)
        self._cohorts = normalized_cohorts
        self._bands = normalized_bands
        self._provenance = provenance

    def _lookup_cohort(
        self, class_code: str, quota_code: str, status: str
    ) -> tuple[tuple[str, str, str], dict[str, int], bool] | None:
        exact = cohort_key(class_code, quota_code, status)
        counts = self._cohorts.get(exact)
        if counts is not None:
            return exact, counts, False
        broad = cohort_key(class_code, quota_code, BROAD_COHORT_STATUS)
        counts = self._cohorts.get(broad)
        if counts is not None:
            return broad, counts, True
        return None

    def _band_counts(self, cohort: tuple[str, str, str], band: str) -> dict[str, int] | None:
        return self._bands.get((*cohort, band))

    def estimate(
        self,
        passenger_id: str,
        asof_status: ParsedStatus,
        class_code: str,
        quota_code: str,
        asof_position: int | None = None,
    ) -> PassengerOutcome:
        """Return a position-aware estimate, a cohort-rate estimate, or an abstention.

        Abstentions are ordered from the most actionable to the least, exactly as the
        frequency baseline orders them, so a passenger sees the same reason from either model
        when the reason is about the request rather than about the table.
        """
        if asof_status.normalized == NormalizedStatus.UNKNOWN:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.UNKNOWN_STATUS,
            )
        if asof_status.normalized not in TARGET_ELIGIBLE_STATUSES:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.UNSUPPORTED_STATUS,
            )
        provenance = self._provenance
        if not self.is_loaded or provenance is None or not provenance.approved_for_estimation():
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.NO_APPROVED_DATA,
            )

        matched = self._lookup_cohort(
            class_code, quota_code, asof_status.normalized.value
        )
        if matched is None:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )
        cohort, cohort_counts, is_fallback = matched
        if sum(cohort_counts.values()) < self.min_sample_threshold:
            return make_abstention_outcome(
                passenger_id=passenger_id,
                reason=AbstentionReason.INSUFFICIENT_SAMPLE,
            )

        try:
            band = position_band(asof_position)
        except ValueError:
            # An unusable position is treated as a missing one: the cohort still answers, and
            # the basis records that this request could not be placed in the queue.
            band = None
        if band is None:
            return self._outcome(
                passenger_id=passenger_id,
                counts=cohort_counts,
                basis=self._basis(cohort, cohort_counts, is_fallback, band=None),
            )

        band_counts = self._band_counts(cohort, band)
        if band_counts is not None and sum(band_counts.values()) >= self.min_band_rows:
            return self._outcome(
                passenger_id=passenger_id,
                counts=band_counts,
                basis=self._basis(
                    cohort, cohort_counts, is_fallback, band=band, band_counts=band_counts
                ),
            )
        return self._outcome(
            passenger_id=passenger_id,
            counts=cohort_counts,
            basis=self._basis(
                cohort,
                cohort_counts,
                is_fallback,
                band=band,
                band_counts=band_counts,
                band_below_floor=True,
            ),
        )

    def _basis(
        self,
        cohort: tuple[str, str, str],
        cohort_counts: dict[str, int],
        is_fallback: bool,
        *,
        band: str | None,
        band_counts: dict[str, int] | None = None,
        band_below_floor: bool = False,
    ) -> str:
        """Name the cell that answered, including when the band was declined."""
        cohort_part = f"cohort={'/'.join(cohort)} n={sum(cohort_counts.values())}"
        if band is None:
            detail = "as-of queue position unavailable; cohort rate used"
        elif band_below_floor:
            seen = sum(band_counts.values()) if band_counts else 0
            detail = (
                f"band={band} n={seen} below the {self.min_band_rows}-row band floor, "
                "cohort rate used"
            )
        elif band_counts is not None:
            detail = f"band={band} n={sum(band_counts.values())} position-aware cell used"
        else:
            detail = f"band={band} has no historical cell for this cohort, cohort rate used"
        fallback_part = (
            " exact_status_match=false (broad "
            f"{BROAD_COHORT_STATUS} cohort fallback)"
            if is_fallback
            else " exact_status_match=true"
        )
        return f"{cohort_part} {detail}{fallback_part}"

    def _outcome(
        self, *, passenger_id: str, counts: Mapping[str, int], basis: str
    ) -> PassengerOutcome:
        probs = self._smoothed_distribution(counts)
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

        Identical to the frequency baseline's rule on purpose: two models that smooth
        differently cannot be compared, and the comparison is the point of having both.
        """
        n_classes = len(OUTCOME_CLASSES)
        denom = sum(counts.values()) + self.laplace_alpha * n_classes
        return {
            outcome: (counts.get(outcome, 0) + self.laplace_alpha) / denom
            for outcome in OUTCOME_CLASSES
        }


__all__ = [
    "BAND_CEILINGS",
    "DEFAULT_MIN_BAND_ROWS",
    "QUEUE_ARTIFACT_FORMAT",
    "QUEUE_ESTIMATOR_ID",
    "QUEUE_FEATURES",
    "CohortPositionBaseline",
    "band_labels",
    "normalize_band_table",
    "position_band",
    "validate_band_cohorts",
]

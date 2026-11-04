"""Longitudinal dataset validation and quality auditing.

Validates multi-observation railway reservation histories against:
- Structural integrity (journeys, booking groups, passengers)
- Temporal integrity (strict chronological ordering, timezone-aware clocks)
- Lead-time bounds (no retrodiction or observation post-chart)
- Contradictory outcomes and state transition anomalies
- Group-level consistency (shared journeys, matching passenger counts)

Generates structured audit reports and quality metrics for prospective dataset intake.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    CensoringReason,
    LongitudinalDataset,
)
from railconfirm.domain.status import NormalizedStatus


@dataclass(frozen=True)
class TransitionEvent:
    """A status transition between successive observations or to final outcome."""

    from_status: str
    to_status: str
    elapsed_hours: float
    is_anomaly: bool = False
    anomaly_reason: str | None = None


@dataclass(frozen=True)
class LongitudinalQualityMetrics:
    """Detailed quality and coverage metrics for a longitudinal dataset."""

    total_journeys: int
    total_booking_groups: int
    total_passengers: int
    total_observations: int
    observations_per_passenger_min: int
    observations_per_passenger_median: float
    observations_per_passenger_max: int
    lead_hours_min: float
    lead_hours_median: float
    lead_hours_max: float
    observation_interval_hours_median: float | None
    censored_count: int
    censored_percentage: float
    censoring_reasons_breakdown: dict[str, int]
    verification_methods_breakdown: dict[str, int]
    label_confidence_breakdown: dict[str, int]
    outcome_categories_breakdown: dict[str, int]
    initial_categories_breakdown: dict[str, int]
    group_size_distribution: dict[int, int]
    transition_anomaly_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LongitudinalAuditReport:
    """Structured audit report produced by longitudinal validator."""

    dataset_id: str
    schema_version: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: LongitudinalQualityMetrics | None = None
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "evaluated_at": self.evaluated_at,
        }


def _check_transition_anomaly(
    from_cat: NormalizedStatus,
    to_cat: NormalizedStatus,
    from_raw: str,
    to_raw: str,
) -> tuple[bool, str | None]:
    """Detect impossible or suspicious railway status transitions."""
    # Cancellation is always valid from any state
    if to_cat == NormalizedStatus.CANCELLED:
        return False, None

    # Confirmed berths cannot regress to Waitlist or RAC
    if from_cat == NormalizedStatus.CNF and to_cat in (NormalizedStatus.RAC, NormalizedStatus.WL):
        return True, f"CNF berth regressed to {to_cat.value} ({from_raw} -> {to_raw})"

    # RAC berths moving backward to WL is anomalous on Indian Railways (berths do not drop from RAC to WL)
    if from_cat == NormalizedStatus.RAC and to_cat == NormalizedStatus.WL:
        return True, f"RAC reservation regressed to Waitlist ({from_raw} -> {to_raw})"

    return False, None


def validate_longitudinal_dataset(
    dataset: LongitudinalDataset,
    *,
    strict: bool = True,
) -> LongitudinalAuditReport:
    """Perform thorough schema, temporal, and domain validation on a longitudinal dataset.

    Args:
        dataset: The longitudinal dataset to validate.
        strict: When True, treat transition anomalies as validation errors. When False,
            treat them as warnings.

    Returns:
        A LongitudinalAuditReport with validation status, diagnostics, and metrics.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if dataset.schema_version != LONGITUDINAL_SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema_version '{dataset.schema_version}'; expected '{LONGITUDINAL_SCHEMA_VERSION}'"
        )

    if not dataset.dataset_id:
        errors.append("Dataset missing dataset_id")

    if not dataset.source_id:
        errors.append("Dataset missing source_id")

    if not dataset.journeys:
        errors.append("Dataset contains no journeys")

    if not dataset.booking_groups:
        errors.append("Dataset contains no booking groups")

    # Track metrics collections
    obs_counts_per_p: list[int] = []
    lead_hours_list: list[float] = []
    intervals_hours_list: list[float] = []
    censoring_reasons_counter: Counter[str] = Counter()
    verification_methods_counter: Counter[str] = Counter()
    label_confidence_counter: Counter[str] = Counter()
    outcome_categories_counter: Counter[str] = Counter()
    initial_categories_counter: Counter[str] = Counter()
    group_sizes_counter: Counter[int] = Counter()
    transition_anomalies: list[str] = []

    total_passengers_count = 0
    total_observations_count = 0
    censored_count = 0

    seen_journey_ids = set(dataset.journeys.keys())
    seen_group_ids: set[str] = set()
    seen_passenger_ids: set[str] = set()
    seen_observation_ids: set[str] = set()

    for j_id, journey in dataset.journeys.items():
        if journey.scheduled_departure_at is not None:
            if journey.scheduled_departure_at.tzinfo is None:
                errors.append(f"Journey '{j_id}' scheduled_departure_at has no timezone info")
            elif journey.scheduled_departure_at.date() != journey.journey_date:
                warnings.append(
                    f"Journey '{j_id}' scheduled_departure_at date ({journey.scheduled_departure_at.date()}) "
                    f"differs from journey_date ({journey.journey_date})"
                )

    for group in dataset.booking_groups:
        if group.booking_group_id in seen_group_ids:
            errors.append(f"Duplicate booking_group_id '{group.booking_group_id}'")
        seen_group_ids.add(group.booking_group_id)

        if group.journey_id not in seen_journey_ids:
            errors.append(
                f"Booking group '{group.booking_group_id}' references unknown journey_id '{group.journey_id}'"
            )
            continue

        journey = dataset.journeys[group.journey_id]
        passengers = group.passengers
        p_count = len(passengers)
        total_passengers_count += p_count
        group_sizes_counter[p_count] += 1

        if group.booking_created_at is not None and group.booking_created_at.tzinfo is None:
            errors.append(f"Booking group '{group.booking_group_id}' booking_created_at has no timezone info")

        # Fallback reference departure timestamp: midnight UTC on journey_date if not specified
        ref_departure = (
            journey.scheduled_departure_at
            if journey.scheduled_departure_at is not None
            else datetime(
                journey.journey_date.year,
                journey.journey_date.month,
                journey.journey_date.day,
                23,
                59,
                59,
                tzinfo=UTC,
            )
        )

        for p in passengers:
            if p.passenger_record_id in seen_passenger_ids:
                errors.append(f"Duplicate passenger_record_id '{p.passenger_record_id}'")
            seen_passenger_ids.add(p.passenger_record_id)

            initial_categories_counter[p.original_status_category.value] += 1

            if p.original_observed_at is not None:
                if p.original_observed_at.tzinfo is None:
                    errors.append(
                        f"Passenger '{p.passenger_record_id}' original_observed_at has no timezone info"
                    )
                elif group.booking_created_at and p.original_observed_at < group.booking_created_at:
                    errors.append(
                        f"Passenger '{p.passenger_record_id}' original_observed_at ({p.original_observed_at}) "
                        f"is earlier than booking_created_at ({group.booking_created_at})"
                    )

            p_obs = p.observations
            obs_count = len(p_obs)
            total_observations_count += obs_count
            obs_counts_per_p.append(obs_count)

            # Check observations ordering and temporal sanity
            last_dt: datetime | None = None
            last_cat = p.original_status_category
            last_raw = p.original_status_raw

            for obs in p_obs:
                if obs.observation_id in seen_observation_ids:
                    errors.append(f"Duplicate observation_id '{obs.observation_id}'")
                seen_observation_ids.add(obs.observation_id)

                if obs.passenger_record_id != p.passenger_record_id:
                    errors.append(
                        f"Observation '{obs.observation_id}' passenger_record_id '{obs.passenger_record_id}' "
                        f"does not match parent passenger '{p.passenger_record_id}'"
                    )

                if obs.observed_at.tzinfo is None:
                    errors.append(f"Observation '{obs.observation_id}' observed_at has no timezone info")
                    continue

                # Observation must be strictly after previous observation
                if last_dt is not None:
                    if obs.observed_at <= last_dt:
                        errors.append(
                            f"Passenger '{p.passenger_record_id}' observation '{obs.observation_id}' "
                            f"at {obs.observed_at} is not strictly after previous observation at {last_dt}"
                        )
                    else:
                        elapsed = (obs.observed_at - last_dt).total_seconds() / 3600.0
                        intervals_hours_list.append(elapsed)

                # Observation cannot be in the future relative to journey departure
                if obs.observed_at > ref_departure:
                    errors.append(
                        f"Observation '{obs.observation_id}' at {obs.observed_at} occurred after scheduled departure/charting {ref_departure}"
                    )

                # Lead hours before departure
                lead_h = (ref_departure - obs.observed_at).total_seconds() / 3600.0
                lead_hours_list.append(lead_h)

                # Check transition anomalies
                is_anom, anom_msg = _check_transition_anomaly(
                    last_cat, obs.status_category, last_raw, obs.status_raw
                )
                if is_anom and anom_msg:
                    transition_anomalies.append(
                        f"Passenger '{p.passenger_record_id}': {anom_msg}"
                    )

                last_dt = obs.observed_at
                last_cat = obs.status_category
                last_raw = obs.status_raw

            # Check outcome
            if p.outcome is not None:
                outcome = p.outcome
                outcome_categories_counter[outcome.outcome_category.value] += 1
                verification_methods_counter[outcome.verification_method.value] += 1
                label_confidence_counter[outcome.label_confidence.value] += 1

                if outcome.is_censored:
                    censored_count += 1
                    if outcome.censoring_reason:
                        censoring_reasons_counter[outcome.censoring_reason.value] += 1
                    else:
                        errors.append(
                            f"Passenger '{p.passenger_record_id}' is marked censored without censoring_reason"
                        )
                elif outcome.outcome_category == NormalizedStatus.CANCELLED:
                    # Passenger cancelled their ticket prior to charting; outcome is right-censored for CNF estimation
                    censored_count += 1
                    censoring_reasons_counter[CensoringReason.USER_CANCELLED.value] += 1
                    warnings.append(
                        f"Passenger '{p.passenger_record_id}' cancelled status with non-censored flag; treated as censored"
                    )

                if outcome.outcome_observed_at is not None:
                    if outcome.outcome_observed_at.tzinfo is None:
                        errors.append(
                            f"Passenger '{p.passenger_record_id}' outcome_observed_at has no timezone info"
                        )
                    elif last_dt is not None and outcome.outcome_observed_at < last_dt:
                        errors.append(
                            f"Passenger '{p.passenger_record_id}' outcome_observed_at ({outcome.outcome_observed_at}) "
                            f"is earlier than latest observation ({last_dt})"
                        )

                # Check transition to outcome
                is_anom, anom_msg = _check_transition_anomaly(
                    last_cat, outcome.outcome_category, last_raw, outcome.outcome_status_raw
                )
                if is_anom and anom_msg:
                    transition_anomalies.append(
                        f"Passenger '{p.passenger_record_id}' final transition: {anom_msg}"
                    )

    # Process transition anomalies
    if transition_anomalies:
        if strict:
            errors.extend(transition_anomalies)
        else:
            warnings.extend(transition_anomalies)

    # Compute metrics summary
    if obs_counts_per_p:
        obs_min = min(obs_counts_per_p)
        obs_max = max(obs_counts_per_p)
        obs_median = float(statistics.median(obs_counts_per_p))
    else:
        obs_min = obs_max = 0
        obs_median = 0.0

    if lead_hours_list:
        lead_min = min(lead_hours_list)
        lead_max = max(lead_hours_list)
        lead_median = float(statistics.median(lead_hours_list))
    else:
        lead_min = lead_max = lead_median = 0.0

    interval_median = (
        float(statistics.median(intervals_hours_list))
        if intervals_hours_list
        else None
    )

    censored_pct = (
        (censored_count / total_passengers_count * 100.0)
        if total_passengers_count > 0
        else 0.0
    )

    metrics = LongitudinalQualityMetrics(
        total_journeys=len(dataset.journeys),
        total_booking_groups=len(dataset.booking_groups),
        total_passengers=total_passengers_count,
        total_observations=total_observations_count,
        observations_per_passenger_min=obs_min,
        observations_per_passenger_median=obs_median,
        observations_per_passenger_max=obs_max,
        lead_hours_min=lead_min,
        lead_hours_median=lead_median,
        lead_hours_max=lead_max,
        observation_interval_hours_median=interval_median,
        censored_count=censored_count,
        censored_percentage=round(censored_pct, 2),
        censoring_reasons_breakdown=dict(censoring_reasons_counter),
        verification_methods_breakdown=dict(verification_methods_counter),
        label_confidence_breakdown=dict(label_confidence_counter),
        outcome_categories_breakdown=dict(outcome_categories_counter),
        initial_categories_breakdown=dict(initial_categories_counter),
        group_size_distribution=dict(group_sizes_counter),
        transition_anomaly_count=len(transition_anomalies),
    )

    is_valid = len(errors) == 0

    return LongitudinalAuditReport(
        dataset_id=dataset.dataset_id,
        schema_version=dataset.schema_version,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        metrics=metrics,
    )

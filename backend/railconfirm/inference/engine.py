"""Inference engine for RailConfirm Intelligence.

Coordinates model resolution, feature snapshot building, passenger-level
inference, group outcome calculation, and abstention reporting.

In the current build (Phase 0–7, local-first), no artifact is promoted and no
dataset is approved, so the engine abstains with the specific gate that is closed:
``no_trained_model``, ``model_artifact_invalid`` or ``no_approved_data``.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from railconfirm.domain.journey import Journey
from railconfirm.domain.passenger import StatusObservation
from railconfirm.domain.prediction import (
    AbstentionReason,
    PassengerOutcome,
    PredictionRecord,
    PredictionTarget,
    make_abstention_outcome,
)
from railconfirm.domain.status import NormalizedStatus
from railconfirm.domain.validation import validate_prediction_timing
from railconfirm.inference.baseline import HistoricalFrequencyBaseline
from railconfirm.inference.group import compute_group_outcomes
from railconfirm.inference.registry import ModelRegistry


class InferenceEngine:
    """Core inference coordinator for manual and future batch predictions."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        baseline: HistoricalFrequencyBaseline | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.baseline = baseline or HistoricalFrequencyBaseline()

    def predict(
        self,
        journey: Journey,
        passenger_inputs: Sequence[Mapping[str, Any]],
        prediction_at: datetime,
        target: PredictionTarget = PredictionTarget.FINAL_CHART_CNF,
    ) -> PredictionRecord:
        """Run prediction pipeline for a journey and set of passenger inputs.

        Parameters
        ----------
        journey:
            Journey context.
        passenger_inputs:
            List of dicts containing 'passenger_id', 'original_obs', 'current_obs'.
        prediction_at:
            Offset-aware effective timestamp of the prediction request. Required:
            an estimate with no as-of time cannot say which evidence it used.
        target:
            PredictionTarget, default FINAL_CHART_CNF.

        Raises
        ------
        TemporalIntegrityError
            If the prediction timestamp is naive, is on or after the journey date,
            or precedes evidence supplied with the request.

        Returns
        -------
        PredictionRecord
            Immutable result containing per-passenger outcomes and group outcome.
        """
        now = datetime.now(UTC)
        effective_prediction_at = prediction_at

        validate_prediction_timing(
            journey_date=journey.journey_date,
            prediction_at=effective_prediction_at,
            observation_times=[
                (str(p_inp["passenger_id"]), p_inp["current_obs"].observed_at)
                for p_inp in passenger_inputs
            ],
        )

        # Resolve what may legitimately serve this request. A configured-but-broken
        # artifact is reported as such instead of masquerading as "no model yet".
        estimator, resolution = self.registry.estimator(target, self.baseline)
        artifact = resolution.artifact
        is_model_served = resolution.is_ready

        if is_model_served and artifact is not None:
            model_version = artifact.metadata.version
            feature_schema_version = artifact.metadata.feature_schema_version
            limitations = list(artifact.metadata.limitations)
            if not artifact.metadata.calibrated:
                limitations.append(
                    "Probabilities are not calibrated; no validation of predicted "
                    "against observed outcome frequency has been recorded."
                )
        else:
            model_version = "no_model_v0"
            feature_schema_version = "1.0.0"
            limitations = [
                "RailConfirm is an independent research tool and not an official IRCTC service.",
                "Predictions represent probabilities of reservation outcomes, not guaranteed confirmations.",
                (
                    "No promoted model artifact is active for this target. "
                    f"Registry state: {resolution.status.value} — {resolution.detail}"
                ),
            ]

        passenger_outcomes: list[PassengerOutcome] = []
        warnings: list[str] = []

        for p_inp in passenger_inputs:
            p_id = p_inp["passenger_id"]
            curr_obs: StatusObservation = p_inp["current_obs"]
            parsed = curr_obs.parsed

            # Unknown status takes precedence in abstention
            if parsed.normalized == NormalizedStatus.UNKNOWN:
                outcome = make_abstention_outcome(
                    passenger_id=p_id,
                    reason=AbstentionReason.UNKNOWN_STATUS,
                )
                warnings.append(
                    f"Passenger {p_id[:8]}: Status '{curr_obs.raw_status}' could not be normalized."
                )
            elif estimator.is_loaded:
                outcome = estimator.estimate(
                    passenger_id=p_id,
                    parsed_status=parsed,
                    class_code=journey.class_code,
                    quota_code=journey.quota_code,
                )
                if outcome.abstention_reason is AbstentionReason.UNSUPPORTED_STATUS:
                    warnings.append(
                        f"Passenger {p_id[:8]}: status '{curr_obs.raw_status}' "
                        f"({parsed.normalized.value}) is outside the population this "
                        "target estimates."
                    )
            else:
                # No evidence base is available at all. Report the specific gate
                # that is closed rather than a generic "no model" message.
                outcome = make_abstention_outcome(
                    passenger_id=p_id,
                    reason=resolution.abstention_reason or AbstentionReason.NO_APPROVED_DATA,
                )

            passenger_outcomes.append(outcome)

        # Compute group outcome
        group_outcome = compute_group_outcomes(passenger_outcomes)

        supported_count = sum(1 for po in passenger_outcomes if po.is_supported())
        if not passenger_outcomes or supported_count == 0:
            evidence_coverage = "insufficient"
        elif supported_count == len(passenger_outcomes):
            evidence_coverage = "sufficient"
        else:
            evidence_coverage = "partial"

        if not passenger_outcomes:
            warnings.append(
                "No passengers were supplied, so there is nothing to estimate."
            )
        elif evidence_coverage == "partial":
            warnings.append(
                f"{supported_count} of {len(passenger_outcomes)} passengers have an "
                "estimate; the remainder abstained and the group outcome is "
                "unavailable."
            )

        return PredictionRecord(
            prediction_id=str(uuid.uuid4()),
            target=target,
            prediction_at=effective_prediction_at,
            created_at=now,
            model_version=model_version,
            feature_schema_version=feature_schema_version,
            passenger_outcomes=passenger_outcomes,
            group_outcome=group_outcome,
            evidence_coverage=evidence_coverage,
            limitations=limitations,
            warnings=warnings,
        )

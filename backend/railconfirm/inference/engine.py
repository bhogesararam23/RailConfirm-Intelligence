"""Inference engine for RailConfirm Intelligence.

Coordinates model resolution, feature snapshot building, passenger-level
inference, group outcome calculation, and abstention reporting.

In the current build (Phase 0–7, local-first), if no model artifact exists
and the baseline frequency table is not loaded, the engine safely abstains
with NO_TRAINED_MODEL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from railconfirm.config import settings
from railconfirm.domain.journey import Journey
from railconfirm.domain.passenger import StatusObservation
from railconfirm.domain.prediction import (
    AbstentionReason,
    GroupOutcome,
    PassengerOutcome,
    PredictionRecord,
    PredictionTarget,
    make_abstention_outcome,
)
from railconfirm.domain.status import NormalizedStatus
from railconfirm.inference.baseline import HistoricalFrequencyBaseline
from railconfirm.inference.group import compute_group_outcomes
from railconfirm.inference.registry import ModelRegistry


class InferenceEngine:
    """Core inference coordinator for manual and future batch predictions."""

    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        baseline: Optional[HistoricalFrequencyBaseline] = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.baseline = baseline or HistoricalFrequencyBaseline()

    def predict(
        self,
        journey: Journey,
        passenger_inputs: list[dict[str, Any]],
        prediction_at: Optional[datetime] = None,
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
            Effective timestamp of the prediction request.
        target:
            PredictionTarget, default FINAL_CHART_CNF.

        Returns
        -------
        PredictionRecord
            Immutable result containing per-passenger outcomes and group outcome.
        """
        now = datetime.now(timezone.utc)
        effective_prediction_at = prediction_at or now

        # Check model availability in registry
        has_trained_model = self.registry.has_model()
        model_version = (
            self.registry.active_version() if has_trained_model else "no_model_v0"
        )

        passenger_outcomes: list[PassengerOutcome] = []
        warnings: list[str] = []
        limitations: list[str] = [
            "RailConfirm is an independent research tool and not an official IRCTC service.",
            "Predictions represent probabilities of reservation outcomes, not guaranteed confirmations.",
        ]

        if not has_trained_model:
            limitations.append(
                "No trained machine learning model is currently active. "
                "The system abstains from generating speculative percentages until an approved "
                "historical dataset passes the intake checklist."
            )

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
            elif not has_trained_model:
                # Fallback to baseline estimator
                outcome = self.baseline.estimate(
                    passenger_id=p_id,
                    parsed_status=parsed,
                    class_code=journey.class_code,
                    quota_code=journey.quota_code,
                )
            else:
                # Future: dispatch to trained model artifact
                outcome = make_abstention_outcome(
                    passenger_id=p_id,
                    reason=AbstentionReason.NO_TRAINED_MODEL,
                )

            passenger_outcomes.append(outcome)

        # Compute group outcome
        group_outcome = compute_group_outcomes(passenger_outcomes)

        evidence_coverage = (
            "sufficient"
            if all(po.is_supported() for po in passenger_outcomes)
            else "insufficient"
        )

        return PredictionRecord(
            prediction_id=str(uuid.uuid4()),
            target=target,
            prediction_at=effective_prediction_at,
            created_at=now,
            model_version=model_version,
            feature_schema_version="1.0.0",
            passenger_outcomes=passenger_outcomes,
            group_outcome=group_outcome,
            evidence_coverage=evidence_coverage,
            limitations=limitations,
            warnings=warnings,
        )

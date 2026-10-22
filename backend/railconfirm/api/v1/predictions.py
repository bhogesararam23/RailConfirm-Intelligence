"""POST /v1/predictions/manual endpoint.

Validates the incoming request, normalizes statuses, dispatches to the
inference engine, and returns a structured response.

If no model is available the engine returns a structured abstention —
never a fabricated probability. The endpoint always returns HTTP 200 with
a PredictionResponse, even for abstentions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TypedDict

from fastapi import APIRouter

from railconfirm.api.v1.schemas import (
    GroupOutcomeResponse,
    PassengerOutcomeResponse,
    PredictionRequest,
    PredictionResponse,
)
from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import StatusObservation, make_observation
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.inference.engine import InferenceEngine


class PassengerInferenceInput(TypedDict):
    passenger_id: str
    original_obs: StatusObservation
    current_obs: StatusObservation
    original_status_raw: str
    current_status_raw: str


router = APIRouter()
_engine = InferenceEngine()


@router.post(
    "/predictions/manual",
    response_model=PredictionResponse,
    summary="Manual prediction",
    description=(
        "Submit journey context and per-passenger statuses for a final-chart "
        "confirmation probability estimate. Returns a structured abstention "
        "when no trained model is available."
    ),
    tags=["predictions"],
)
async def predict_manual(request: PredictionRequest) -> PredictionResponse:
    """Handle a manual prediction request end-to-end."""
    # ── Build domain journey ───────────────────────────────────────────────────
    journey = make_journey(
        train_number=request.journey.train_number,
        journey_date=request.journey.journey_date,
        boarding_station=request.journey.boarding_station,
        destination_station=request.journey.destination_station,
        class_code=request.journey.class_code,
        quota_code=request.journey.quota_code,
    )

    # ── Build passenger observations ───────────────────────────────────────────
    now = datetime.now(UTC)
    passenger_inputs: list[PassengerInferenceInput] = []
    for p_req in request.passengers:
        p_id = str(uuid.uuid4())
        original_obs = make_observation(
            raw_status=p_req.original_status,
            source="manual_entry",
            observed_at=None,       # original booking time not provided
            ingested_at=now,
        )
        current_obs = make_observation(
            raw_status=p_req.current_status,
            source="manual_entry",
            observed_at=p_req.current_status_observed_at,
            ingested_at=now,
        )
        passenger_inputs.append(
            {
                "passenger_id": p_id,
                "original_obs": original_obs,
                "current_obs": current_obs,
                "original_status_raw": p_req.original_status,
                "current_status_raw": p_req.current_status,
            }
        )

    # ── Dispatch to inference engine ───────────────────────────────────────────
    prediction = _engine.predict(
        journey=journey,
        passenger_inputs=passenger_inputs,
        prediction_at=request.prediction_at,
        target=PredictionTarget.FINAL_CHART_CNF,
    )

    # ── Build per-passenger response objects ───────────────────────────────────
    passenger_responses: list[PassengerOutcomeResponse] = []
    for inp, outcome in zip(passenger_inputs, prediction.passenger_outcomes):
        orig_parsed = inp["original_obs"].parsed
        curr_parsed = inp["current_obs"].parsed

        warnings_list: list[str] = []
        if orig_parsed.parse_note:
            warnings_list.append(f"original_status: {orig_parsed.parse_note}")
        if curr_parsed.parse_note:
            warnings_list.append(f"current_status: {curr_parsed.parse_note}")

        passenger_responses.append(
            PassengerOutcomeResponse(
                passenger_id=outcome.passenger_id,
                original_status=inp["original_status_raw"],
                original_status_normalized=orig_parsed.normalized.value,
                current_status=inp["current_status_raw"],
                current_status_normalized=curr_parsed.normalized.value,
                p_cnf=outcome.p_cnf,
                p_rac=outcome.p_rac,
                p_wl=outcome.p_wl,
                p_cancelled=outcome.p_cancelled,
                p_other=outcome.p_other,
                is_supported=outcome.is_supported(),
                abstention_reason=(
                    outcome.abstention_reason.value
                    if outcome.abstention_reason
                    else None
                ),
                basis=outcome.basis,
                parse_warnings=warnings_list,
            )
        )

    # ── Build group outcome response ───────────────────────────────────────────
    group_resp: GroupOutcomeResponse | None = None
    if prediction.group_outcome is not None:
        go = prediction.group_outcome
        group_resp = GroupOutcomeResponse(
            p_all_cnf=go.p_all_cnf,
            p_all_cnf_or_rac=go.p_all_cnf_or_rac,
            p_at_least_one_wl=go.p_at_least_one_wl,
            method=go.method,
            assumptions=go.assumptions,
            is_supported=go.abstention_reason is None,
            abstention_reason=(
                go.abstention_reason.value if go.abstention_reason else None
            ),
        )

    return PredictionResponse(
        prediction_id=prediction.prediction_id,
        target_definition=(
            "Probability of each final-chart outcome for each passenger "
            "(CNF = confirmed berth, RAC = Reservation Against Cancellation, "
            "WL = waitlisted, CANCELLED = cancelled, OTHER = other outcome). "
            "These are mutually exclusive and exhaustive over the supported population."
        ),
        prediction_at=prediction.prediction_at or request.prediction_at,
        created_at=prediction.created_at,
        model_version=prediction.model_version,
        feature_schema_version=prediction.feature_schema_version,
        evidence_coverage=prediction.evidence_coverage,
        is_supported=any(p.is_supported for p in passenger_responses),
        passenger_count=len(passenger_responses),
        passenger_outcomes=passenger_responses,
        group_outcome=group_resp,
        limitations=list(prediction.limitations),
        warnings=list(prediction.warnings),
        outcome_classes=(
            "CNF, RAC, WL, CANCELLED, OTHER — mutually exclusive and exhaustive "
            "over the eligible population. Probabilities sum to 1.0 per passenger."
        ),
    )

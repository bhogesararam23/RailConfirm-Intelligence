"""POST /v1/predictions/manual endpoint.

Validates the incoming request, normalizes statuses, dispatches to the inference
engine, and returns a structured response.

If no validated model or approved data is available the engine returns a
structured abstention — never a fabricated probability. A valid request that the
available evidence cannot support is reported through the abstention contract,
not as a 200 with an invented number and not as an HTTP error.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, TypedDict

from fastapi import APIRouter, Depends

from railconfirm.api.dependencies import get_engine, get_prediction_store
from railconfirm.api.problems import ApiProblem
from railconfirm.api.v1.schemas import (
    GroupOutcomeResponse,
    PassengerOutcomeResponse,
    PredictionRequest,
    PredictionResponse,
)
from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import StatusObservation, make_observation
from railconfirm.domain.validation import ReasonCode
from railconfirm.inference.engine import InferenceEngine
from railconfirm.storage.predictions import PredictionStorageError, PredictionStore

logger = logging.getLogger(__name__)

HISTORY_DISABLED_MESSAGE = (
    "This server keeps no prediction history (RAILCONFIRM_PERSIST_PREDICTIONS is not "
    "enabled), so the report was not stored and cannot be reopened later."
)
_PNR_SHAPE_HINT = "^[1-9][0-9]{9}$"

# The route prefix is part of the stored report_url: a client that follows it must land
# on this same router.
REPORT_PATH = "/v1/predictions/"


class PassengerInferenceInput(TypedDict):
    passenger_id: str
    original_obs: StatusObservation
    current_obs: StatusObservation
    original_status_raw: str
    current_status_raw: str


router = APIRouter()


@router.post(
    "/predictions/manual",
    response_model=PredictionResponse,
    summary="Manual prediction",
    description=(
        "Submit journey context and per-passenger statuses for a final-chart "
        "confirmation probability estimate. Returns a structured abstention with "
        "the specific blocking reason when no validated model or approved data is "
        "available."
    ),
    tags=["predictions"],
)
async def predict_manual(
    request: PredictionRequest,
    engine: Annotated[InferenceEngine, Depends(get_engine)],
    store: Annotated[PredictionStore | None, Depends(get_prediction_store)],
) -> PredictionResponse:
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
    prediction = engine.predict(
        journey=journey,
        passenger_inputs=passenger_inputs,
        prediction_at=request.prediction_at,
        target=request.target,
    )
    resolution = engine.registry.resolve(request.target)
    logger.info(
        "prediction served: id=%s target=%s coverage=%s registry=%s passengers=%d",
        prediction.prediction_id,
        request.target.value,
        prediction.evidence_coverage,
        resolution.status.value,
        len(passenger_inputs),
    )

    # ── Build per-passenger response objects ───────────────────────────────────
    passenger_responses: list[PassengerOutcomeResponse] = []
    for inp, outcome in zip(
        passenger_inputs, prediction.passenger_outcomes, strict=True
    ):
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

    response = PredictionResponse(
        prediction_id=prediction.prediction_id,
        target=prediction.target.value,
        target_definition=(
            "Probability of each final-chart outcome for each passenger "
            "(CNF = confirmed berth, RAC = Reservation Against Cancellation, "
            "WL = waitlisted, CANCELLED = cancelled, OTHER = other outcome). "
            "These are mutually exclusive and exhaustive over the supported population."
        ),
        prediction_at=prediction.prediction_at,
        created_at=prediction.created_at,
        model_version=prediction.model_version,
        registry_status=resolution.status.value,
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
    if not request.persist:
        return response
    return _store_report(
        response,
        store=store,
        prediction_at=prediction.prediction_at,
        target=prediction.target.value,
    )


def _store_report(
    response: PredictionResponse,
    *,
    store: PredictionStore | None,
    prediction_at: datetime,
    target: str,
) -> PredictionResponse:
    """Write the report the caller asked to keep, and say plainly whether it was kept.

    A storage failure never turns into a failed prediction: the estimate is still
    delivered, and the limitation records that no reopenable copy exists.
    """
    if store is None:
        return response.model_copy(
            update={"limitations": [*response.limitations, HISTORY_DISABLED_MESSAGE]}
        )
    try:
        stored = store.save(
            prediction_id=response.prediction_id,
            payload=response.model_dump(mode="json"),
            target=target,
            model_version=response.model_version,
            prediction_at=prediction_at,
        )
    except PredictionStorageError as exc:
        logger.warning("prediction not stored: id=%s reason=%s", response.prediction_id, exc)
        return response.model_copy(
            update={
                "limitations": [
                    *response.limitations,
                    f"History is enabled but this report was not stored: {exc}",
                ]
            }
        )
    logger.info(
        "prediction stored: id=%s expires=%s retention_days=%d",
        stored.prediction_id,
        stored.expires_at.isoformat(),
        store.retention_days,
    )
    return response.model_copy(
        update={
            "stored": True,
            "report_url": f"{REPORT_PATH}{stored.prediction_id}",
            "retention_expires_at": stored.expires_at,
        }
    )


@router.get(
    "/predictions/{prediction_id}",
    response_model=PredictionResponse,
    summary="Reopen a stored prediction report",
    description=(
        "Returns the report that was served for this internal id, including the model "
        "version, registry state and limitations that came with it. Requires prediction "
        "history to be enabled on this server. PNR numbers are not accepted here."
    ),
    tags=["predictions"],
)
async def read_prediction(
    prediction_id: str,
    store: Annotated[PredictionStore | None, Depends(get_prediction_store)],
) -> PredictionResponse:
    """Serve a stored report by internal id."""
    if store is None:
        raise ApiProblem(
            status_code=404,
            code=ReasonCode.HISTORY_DISABLED,
            message="This server keeps no prediction history.",
        )
    if len(prediction_id) == 10 and prediction_id.isdigit() and prediction_id[0] != "0":
        # The id in a URL is the one place a user might paste a PNR. Answering that
        # question here would make this endpoint a ticket tracker.
        raise ApiProblem(
            status_code=404,
            code=ReasonCode.NOT_FOUND,
            message=(
                "Reports are reopened by the internal id the server returned, not by a "
                "PNR number."
            ),
        )
    stored = store.get(prediction_id, now=datetime.now(UTC))
    if stored is None:
        raise ApiProblem(
            status_code=404,
            code=ReasonCode.NOT_FOUND,
            message=(
                "No stored report has this id. Either it was never stored, its retention "
                "window has closed, or the id is wrong."
            ),
        )
    try:
        report = PredictionResponse.model_validate(stored.payload)
    except ValueError as exc:
        raise ApiProblem(
            status_code=500,
            code=ReasonCode.STORAGE_UNAVAILABLE,
            message=f"The stored report for this id does not match the API contract: {exc}",
        ) from exc
    if report.prediction_id != prediction_id:
        raise ApiProblem(
            status_code=500,
            code=ReasonCode.STORAGE_UNAVAILABLE,
            message="The stored report disagrees with the id it is filed under.",
        )
    return report.model_copy(
        update={
            "stored": True,
            "report_url": f"{REPORT_PATH}{prediction_id}",
            "retention_expires_at": stored.expires_at,
        }
    )

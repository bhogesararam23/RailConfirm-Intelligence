"""GET /v1/health endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from railconfirm.api.dependencies import get_engine
from railconfirm.api.v1.schemas import MAX_PASSENGERS_PER_REQUEST, HealthResponse
from railconfirm.config import settings
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.inference.engine import InferenceEngine

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health and model availability check",
    description=(
        "Reports the configured version identifiers and whether a validated, "
        "promoted model artifact could serve a prediction right now. "
        "`model_version: no_model_v0` with `model_available: false` is the "
        "expected state of the local-first build."
    ),
    tags=["health"],
)
async def health_check(
    engine: Annotated[InferenceEngine, Depends(get_engine)],
) -> HealthResponse:
    """Return API health plus the registry state an operator needs to triage."""
    resolution = engine.registry.resolve(PredictionTarget.FINAL_CHART_CNF)
    served = resolution.is_ready and resolution.artifact is not None
    # Report the threshold that actually governs the next prediction: a promoted
    # artifact carries its own, and the fallback baseline's would be misleading.
    active_threshold = (
        resolution.artifact.metadata.min_sample_threshold
        if served and resolution.artifact is not None
        else engine.baseline.min_sample_threshold
    )
    return HealthResponse(
        status="ok",
        model_version=resolution.version if served else "no_model_v0",
        data_version=settings.data_version,
        app_version=settings.app_version,
        model_available=served,
        registry_status=resolution.status.value,
        limits={
            "max_passengers_per_request": MAX_PASSENGERS_PER_REQUEST,
            "min_sample_threshold": active_threshold,
            "max_artifact_bytes": settings.max_artifact_bytes,
            "max_request_bytes": settings.max_request_bytes,
        },
    )

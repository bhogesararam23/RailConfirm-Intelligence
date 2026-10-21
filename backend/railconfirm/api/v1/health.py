"""GET /v1/health endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from railconfirm.api.v1.schemas import HealthResponse
from railconfirm.config import settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns the current operational status of the API, the active model "
        "version, and the data version in use."
    ),
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """Return API health and version metadata."""
    return HealthResponse(
        status="ok",
        model_version=settings.active_model_version,
        data_version=settings.data_version,
        app_version=settings.app_version,
    )

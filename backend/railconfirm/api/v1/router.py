"""API v1 router: registers all v1 endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from railconfirm.api.v1 import health, predictions

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(predictions.router)

"""Dependency providers for the API layer.

The inference engine is supplied through the application state rather than a
module-level singleton, so a test or a later phase can install a different
registry or baseline without importing and patching private globals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from fastapi import Request

from railconfirm.api.problems import ApiProblem
from railconfirm.config import settings
from railconfirm.inference.engine import InferenceEngine
from railconfirm.storage.predictions import PredictionStore

if TYPE_CHECKING:
    from railconfirm.data.operator import OperatorService

LOCAL_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def get_engine(request: Request) -> InferenceEngine:
    """Return the engine bound to this application instance."""
    return request.app.state.engine


def get_prediction_store(request: Request) -> PredictionStore | None:
    """Return the history store, or None when this server keeps no history.

    None is the default state, not an error: prediction history is opt-in because a
    local tool that accumulated ticket data silently would contradict its own privacy
    claim.
    """
    return getattr(request.app.state, "prediction_store", None)


def require_local_operator(request: Request) -> None:
    """Enforce that operator endpoints are enabled and called from loopback."""
    is_enabled = getattr(request.app.state, "operator_enabled", settings.operator_enabled)
    if not is_enabled:
        raise ApiProblem(
            status_code=403,
            code="OPERATOR_DISABLED",
            message="Operator mode is disabled. To enable locally, set RAILCONFIRM_OPERATOR_ENABLED=true.",
        )

    client_host = request.client.host if request.client else ""
    if client_host not in LOCAL_HOSTS:
        raise ApiProblem(
            status_code=403,
            code="NON_LOCAL_ACCESS_FORBIDDEN",
            message=f"Operator access forbidden from non-local host: '{client_host}'. The operator workbench is strictly local-only.",
        )


def get_operator_service(request: Request) -> OperatorService:
    """Return the OperatorService bound to the application, or initialize default."""
    service = getattr(request.app.state, "operator_service", None)
    if service is None:
        from railconfirm.data.operator import OperatorService

        service = OperatorService.from_directory(settings.operator_dir)
        request.app.state.operator_service = service
    return service

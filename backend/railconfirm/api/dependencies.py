"""Dependency providers for the API layer.

The inference engine is supplied through the application state rather than a
module-level singleton, so a test or a later phase can install a different
registry or baseline without importing and patching private globals.
"""

from __future__ import annotations

from fastapi import Request

from railconfirm.inference.engine import InferenceEngine
from railconfirm.storage.predictions import PredictionStore


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

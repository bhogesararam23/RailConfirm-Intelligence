"""Dependency providers for the API layer.

The inference engine is supplied through the application state rather than a
module-level singleton, so a test or a later phase can install a different
registry or baseline without importing and patching private globals.
"""

from __future__ import annotations

from fastapi import Request

from railconfirm.inference.engine import InferenceEngine


def get_engine(request: Request) -> InferenceEngine:
    """Return the engine bound to this application instance."""
    return request.app.state.engine

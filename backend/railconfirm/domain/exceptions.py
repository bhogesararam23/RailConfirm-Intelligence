"""Domain exceptions for RailConfirm Intelligence."""

from __future__ import annotations


class RailConfirmError(Exception):
    """Base exception for all RailConfirm domain errors."""


class StatusParseError(RailConfirmError):
    """Raised when a status string cannot be parsed at all (not UNKNOWN — that
    is a valid normalized state; this is for structural failures)."""


class JourneyValidationError(RailConfirmError, ValueError):
    """Raised when a Journey fails hard constraint validation."""


class DatasetValidationError(RailConfirmError):
    """Raised when a dataset fails schema or integrity validation."""


class InferenceError(RailConfirmError):
    """Raised for internal inference failures (not abstentions)."""


class ModelRegistryError(RailConfirmError):
    """Raised when a requested model version cannot be resolved."""

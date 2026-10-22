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


class FrequencyTableValidationError(DatasetValidationError, ValueError):
    """Raised when a historical frequency table is structurally unusable.

    This is a programming/ingestion failure, not an abstention: a malformed
    count table must never be smoothed into a probability distribution. Both
    bases are inherited so callers may catch it as ``ValueError`` at a boundary.
    """


class ModelArtifactError(RailConfirmError):
    """Raised when a model artifact is present but cannot be trusted.

    Distinct from ``ModelRegistryError``: the file exists, so the problem is its
    metadata, schema or approval state rather than an unresolvable version.
    """


class InferenceError(RailConfirmError):
    """Raised for internal inference failures (not abstentions)."""


class ModelRegistryError(RailConfirmError):
    """Raised when a requested model version cannot be resolved."""

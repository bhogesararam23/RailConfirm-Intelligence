"""Domain exceptions for RailConfirm Intelligence."""

from __future__ import annotations


class RailConfirmError(Exception):
    """Base exception for all RailConfirm domain errors."""


class StatusParseError(RailConfirmError):
    """Raised when a status string cannot be parsed at all (not UNKNOWN — that
    is a valid normalized state; this is for structural failures)."""


class JourneyValidationError(RailConfirmError, ValueError):
    """Raised when a Journey fails hard constraint validation."""


class TemporalIntegrityError(RailConfirmError, ValueError):
    """Raised when timestamps cannot support the claim being made.

    Covers a naive timestamp (nothing to compare against), a prediction made at
    or after the event it predicts, and evidence dated after the prediction
    timestamp. Both bases are inherited so an API boundary can treat it as a
    422 input problem while callers can still catch the domain type.
    """


class DatasetValidationError(RailConfirmError, ValueError):
    """Raised when a dataset fails schema or integrity validation.

    Also a ``ValueError`` so an API or CLI boundary can treat it as bad input
    without importing the domain hierarchy.
    """


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

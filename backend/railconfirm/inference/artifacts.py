"""Model artifact format for RailConfirm Intelligence.

An artifact is a JSON document, never a pickled object. Loading a model must not
be able to execute code, so deserialisation is restricted to data the project
defines: ``ARTIFACT_FORMAT`` names the expected shape and anything else is
rejected before it reaches an estimator.

A file existing is not evidence that it may be used. Every artifact carries its
target, feature/mapping schema versions, the dataset it was fitted from and an
explicit promotion state, and the registry only serves artifacts whose
declaration matches the request.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.inference.baseline import (
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    FrequencyTableValidationError,
    HistoricalFrequencyBaseline,
    normalize_frequency_table,
)

ARTIFACT_FORMAT = "railconfirm.frequency-baseline/1"
"""Artifact format identifier. Bump when the JSON layout changes."""

ESTIMATOR_HISTORICAL_FREQUENCY = "historical_frequency_baseline"
"""The only estimator this build knows how to serve."""

PROMOTION_APPROVED = "approved_for_local_use"
"""Metadata value required before an artifact may be promoted by configuration."""

_COHORT_SEPARATOR = "|"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ModelArtifactMetadata:
    """What a model artifact claims to be, and what it was fitted from."""

    version: str
    target: str
    estimator: str
    feature_schema_version: str
    status_mapping_version: str
    outcome_classes: tuple[str, ...]
    dataset_id: str
    dataset_sha256: str
    source_reference: str
    data_approval_status: str
    is_synthetic: bool
    min_sample_threshold: int
    laplace_alpha: float
    promotion: str
    limitations: tuple[str, ...]
    trained_from: str | None = None
    trained_to: str | None = None
    calibration_method: str | None = None
    calibrated: bool = False
    notes: str | None = None

    def provenance(self) -> FrequencyTableProvenance:
        return FrequencyTableProvenance(
            dataset_id=self.dataset_id,
            sha256=self.dataset_sha256,
            source_reference=self.source_reference,
            approval_status=self.data_approval_status,
            is_synthetic=self.is_synthetic,
            mapping_version=self.status_mapping_version,
            fitted_from=self.trained_from,
            fitted_to=self.trained_to,
            notes=self.notes,
        )


@dataclass(frozen=True)
class LoadedArtifact:
    """A parsed, validated artifact: metadata plus its canonical cohort table."""

    metadata: ModelArtifactMetadata
    cohorts: dict[tuple[str, str, str], dict[str, int]]
    path: Path

    def baseline(self) -> HistoricalFrequencyBaseline:
        """Build the estimator this artifact declares, with matching settings."""
        estimator = HistoricalFrequencyBaseline(
            min_sample_threshold=self.metadata.min_sample_threshold,
            laplace_alpha=self.metadata.laplace_alpha,
        )
        estimator.load_frequency_table(self.cohorts, self.metadata.provenance())
        return estimator


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelArtifactError(message)


def _iso_date(value: Any, field_name: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise ModelArtifactError(
            f"{field_name} must be an ISO-8601 date, got {value!r}."
        ) from exc


def metadata_from_mapping(raw: Any, *, expected_version: str, expected_target: str) -> ModelArtifactMetadata:
    """Validate an artifact's metadata block against the request it received.

    Rejects rather than repairs: a version or target that does not match what was
    asked for means the caller would be served an estimate for a different
    question than the one it posed.
    """
    _require(isinstance(raw, dict), "Artifact metadata must be a JSON object.")
    text_fields = (
        "version",
        "target",
        "estimator",
        "feature_schema_version",
        "status_mapping_version",
        "dataset_id",
        "dataset_sha256",
        "source_reference",
        "data_approval_status",
        "promotion",
    )
    for name in text_fields:
        value = raw.get(name)
        _require(
            isinstance(value, str) and bool(value.strip()),
            f"Artifact metadata field {name!r} must be a non-empty string.",
        )

    _require(
        raw["version"] == expected_version,
        f"Artifact declares version {raw['version']!r} but {expected_version!r} "
        "was requested; the file name and its contents must agree.",
    )
    _require(
        raw["target"] == expected_target,
        f"Artifact is fitted for target {raw['target']!r}, not {expected_target!r}. "
        "A final-chart estimate and a departure estimate are different questions.",
    )
    _require(
        raw["estimator"] == ESTIMATOR_HISTORICAL_FREQUENCY,
        f"Unknown estimator {raw['estimator']!r}; this build serves "
        f"{ESTIMATOR_HISTORICAL_FREQUENCY!r} only.",
    )
    _require(
        _SHA256_RE.match(raw["dataset_sha256"]) is not None,
        "Artifact dataset_sha256 must be 64 lowercase hexadecimal characters so "
        "the training data can be identified.",
    )

    outcome_classes = raw.get("outcome_classes")
    _require(
        isinstance(outcome_classes, list)
        and tuple(outcome_classes) == OUTCOME_CLASSES,
        f"Artifact outcome_classes must be exactly {list(OUTCOME_CLASSES)}, got "
        f"{outcome_classes!r}. A different class order or set would silently "
        "misassign every probability.",
    )

    is_synthetic = raw.get("is_synthetic")
    _require(
        isinstance(is_synthetic, bool),
        f"Artifact is_synthetic must be a boolean, got {is_synthetic!r}.",
    )

    threshold = raw.get("min_sample_threshold")
    _require(
        isinstance(threshold, int)
        and not isinstance(threshold, bool)
        and threshold >= 1,
        f"Artifact min_sample_threshold must be a positive integer, got {threshold!r}.",
    )

    alpha = raw.get("laplace_alpha")
    _require(
        isinstance(alpha, int | float)
        and not isinstance(alpha, bool)
        and math.isfinite(alpha)
        and alpha > 0,
        f"Artifact laplace_alpha must be a positive finite number, got {alpha!r}.",
    )

    limitations = raw.get("limitations")
    _require(
        isinstance(limitations, list)
        and bool(limitations)
        and all(isinstance(item, str) and item.strip() for item in limitations),
        "Artifact limitations must be a non-empty list of strings: an uncalibrated "
        "estimate must ship with the limitation stated.",
    )

    calibrated = raw.get("calibrated", False)
    _require(
        isinstance(calibrated, bool),
        f"Artifact calibrated must be a boolean, got {calibrated!r}.",
    )
    calibration_method = raw.get("calibration_method")
    if calibrated:
        _require(
            isinstance(calibration_method, str) and bool(calibration_method.strip()),
            "An artifact claiming calibrated=true must name the calibration method "
            "and the period it was fitted on.",
        )

    trained_from = raw.get("trained_from")
    trained_to = raw.get("trained_to")
    if trained_from is not None:
        trained_from = _iso_date(trained_from, "trained_from")
    if trained_to is not None:
        trained_to = _iso_date(trained_to, "trained_to")
    if trained_from is not None and trained_to is not None:
        _require(
            trained_from <= trained_to,
            f"Artifact training window is reversed: {trained_from} > {trained_to}.",
        )

    notes = raw.get("notes")
    _require(
        notes is None or (isinstance(notes, str) and bool(notes.strip())),
        "Artifact notes must be null or a non-empty string.",
    )

    return ModelArtifactMetadata(
        version=raw["version"],
        target=raw["target"],
        estimator=raw["estimator"],
        feature_schema_version=raw["feature_schema_version"],
        status_mapping_version=raw["status_mapping_version"],
        outcome_classes=tuple(outcome_classes),
        dataset_id=raw["dataset_id"],
        dataset_sha256=raw["dataset_sha256"],
        source_reference=raw["source_reference"],
        data_approval_status=raw["data_approval_status"],
        is_synthetic=is_synthetic,
        min_sample_threshold=threshold,
        laplace_alpha=float(alpha),
        promotion=raw["promotion"],
        limitations=tuple(limitations),
        trained_from=trained_from,
        trained_to=trained_to,
        calibration_method=calibration_method,
        calibrated=calibrated,
        notes=notes,
    )


def _decode_cohorts(raw_cohorts: Any) -> dict[tuple[str, str, str], dict[str, int]]:
    _require(
        isinstance(raw_cohorts, dict) and bool(raw_cohorts),
        "Artifact cohorts must be a non-empty object keyed by 'CLASS|QUOTA|STATUS'.",
    )
    table: dict[tuple[str, str, str], dict[str, int]] = {}
    for key, counts in raw_cohorts.items():
        parts = str(key).split(_COHORT_SEPARATOR)
        _require(
            len(parts) == 3 and all(part.strip() for part in parts),
            f"Cohort key {key!r} must have three non-empty parts separated by "
            f"{_COHORT_SEPARATOR!r}.",
        )
        _require(
            isinstance(counts, dict),
            f"Cohort {key!r} counts must be a JSON object.",
        )
        class_code, quota_code, status = parts
        table[(class_code, quota_code, status)] = dict(counts)
    return table


def load_artifact(
    path: Path,
    *,
    expected_version: str,
    expected_target: str,
    max_bytes: int,
) -> LoadedArtifact:
    """Read and validate a JSON model artifact.

    The size limit is checked before the file is read, and the declared format is
    checked before the metadata, so an unrelated or hostile file is rejected
    rather than partially trusted.
    """
    size = path.stat().st_size
    _require(
        size <= max_bytes,
        f"Artifact {path.name} is {size} bytes, above the configured limit of "
        f"{max_bytes}; refusing to read it.",
    )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelArtifactError(
            f"Artifact {path.name} is not valid UTF-8 JSON, so it cannot be loaded "
            f"as a RailConfirm model: {exc}."
        ) from exc

    _require(
        isinstance(document, dict),
        f"Artifact {path.name} must contain a single JSON object.",
    )
    declared_format = document.get("artifact_format")
    _require(
        declared_format == ARTIFACT_FORMAT,
        f"Artifact {path.name} declares format {declared_format!r}, expected "
        f"{ARTIFACT_FORMAT!r}.",
    )

    metadata = metadata_from_mapping(
        document.get("metadata"),
        expected_version=expected_version,
        expected_target=expected_target,
    )
    cohorts = _decode_cohorts(document.get("cohorts"))
    try:
        normalized = normalize_frequency_table(cohorts)
    except FrequencyTableValidationError as exc:
        raise ModelArtifactError(
            f"Artifact {path.name} carries an unusable cohort table: {exc}"
        ) from exc
    return LoadedArtifact(metadata=metadata, cohorts=normalized, path=path)


def encode_cohorts(table: dict[tuple[str, str, str], dict[str, int]]) -> dict[str, dict[str, int]]:
    """Encode a cohort table for JSON with deterministic key order."""
    return {
        _COHORT_SEPARATOR.join(cohort): {c: counts[c] for c in OUTCOME_CLASSES if c in counts}
        for cohort, counts in sorted(table.items())
    }


def build_artifact_document(
    metadata: ModelArtifactMetadata,
    cohorts: dict[tuple[str, str, str], dict[str, int]],
) -> str:
    """Serialise an artifact deterministically so two runs can be compared."""
    document = {
        "artifact_format": ARTIFACT_FORMAT,
        "metadata": {
            **asdict(metadata),
            "outcome_classes": list(metadata.outcome_classes),
            "limitations": list(metadata.limitations),
        },
        "cohorts": encode_cohorts(cohorts),
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_artifact(
    path: Path,
    metadata: ModelArtifactMetadata,
    cohorts: dict[tuple[str, str, str], dict[str, int]],
) -> Path:
    """Write a validated artifact to ``path`` (a ``.json`` file under the models dir)."""
    normalize_frequency_table(cohorts)
    if path.suffix != ".json":
        raise ModelArtifactError(f"Artifact path {path} must use the .json extension.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_artifact_document(metadata, cohorts), encoding="utf-8")
    return path

"""Model artifact format for RailConfirm Intelligence.

An artifact is a JSON document, never a pickled object. Loading a model must not
be able to execute code, so deserialisation is restricted to data the project
defines: ``ARTIFACT_FORMAT`` names the expected shape and anything else is
rejected before it reaches an estimator.

A file existing is not evidence that it may be used. Every artifact carries its
target, feature/mapping schema versions, the features it actually reads, the status
its cohorts are keyed by, the dataset it was fitted from and an explicit promotion
state, and the registry only serves artifacts whose declarations match the request
and whose cohort rule matches the lookup the estimator performs.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.inference.baseline import (
    COHORT_FEATURES,
    COHORT_STATUS_SEMANTICS,
    OUTCOME_CLASSES,
    FrequencyTableProvenance,
    FrequencyTableValidationError,
    HistoricalFrequencyBaseline,
    normalize_frequency_table,
)
from railconfirm.inference.calibration import (
    CalibrationSpec,
    spec_from_mapping,
)
from railconfirm.inference.queue import (
    DEFAULT_MIN_BAND_ROWS,
    QUEUE_ARTIFACT_FORMAT,
    QUEUE_ESTIMATOR_ID,
    QUEUE_FEATURES,
    BandKey,
    CohortPositionBaseline,
    normalize_band_table,
)

ARTIFACT_FORMAT = "railconfirm.frequency-baseline/2"
"""Artifact format identifier. Bump when the JSON layout changes.

2 adds ``features_used`` and ``cohort_semantics``, which are required at load: a
table that does not say which status its cohorts were built from cannot be shown to
be queried with the same rule the product uses."""

ESTIMATOR_HISTORICAL_FREQUENCY = "historical_frequency_baseline"
"""The cohort frequency table, the first estimator this build serves."""

KNOWN_FORMATS = (ARTIFACT_FORMAT, QUEUE_ARTIFACT_FORMAT)
"""Every artifact layout this build can read.

Checked before the metadata so an unrelated file is refused rather than partially
trusted; which of the two is allowed then follows from the estimator the metadata names."""


def format_for_estimator(estimator: str) -> str | None:
    """The only artifact layout that can carry this estimator's arithmetic."""
    if estimator == ESTIMATOR_HISTORICAL_FREQUENCY:
        return ARTIFACT_FORMAT
    if estimator == QUEUE_ESTIMATOR_ID:
        return QUEUE_ARTIFACT_FORMAT
    return None

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
    features_used: tuple[str, ...] = COHORT_FEATURES
    """The features the estimator actually reads, not the schema it could read.

    A frequency baseline consumes class, quota and the as-of status. Declaring that
    here stops a report or a reviewer from crediting the estimator with queue
    positions and lead days it never looks at."""
    cohort_semantics: str = COHORT_STATUS_SEMANTICS
    min_band_rows: int = DEFAULT_MIN_BAND_ROWS
    """Rows a position cell needs before it may answer; meaningless to the frequency table.

    Written into the artifact rather than read from configuration, because it changes the
    served number: the same table with a different floor is a different model."""
    """Which status the cohort keys were built from; must match the lookup rule."""
    trained_from: str | None = None
    trained_to: str | None = None
    calibration_method: str | None = None
    calibrated: bool = False
    calibration: CalibrationSpec | None = None
    """The fitted correction over the target event, when there is one.

    ``calibrated`` is derived from this block rather than claimed beside it: an artifact
    that says it is calibrated must carry the method, the slope, the intercept and the
    rows behind them, and one that does not must say ``calibrated: false``."""
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
    """A parsed, validated artifact: metadata plus the tables its estimator reads."""

    metadata: ModelArtifactMetadata
    cohorts: dict[tuple[str, str, str], dict[str, int]]
    path: Path
    bands: dict[BandKey, dict[str, int]] = field(default_factory=dict)

    def estimator(self) -> HistoricalFrequencyBaseline | CohortPositionBaseline:
        """Build exactly the estimator this artifact declares, with its own settings.

        Dispatch is here rather than at the call site so a cohort table can never be
        answered by the position arithmetic, or the reverse, because some caller imported
        the wrong class.
        """
        return self.estimator_for(self.metadata.provenance())

    def estimator_for(
        self, provenance: FrequencyTableProvenance
    ) -> HistoricalFrequencyBaseline | CohortPositionBaseline:
        """The same construction against a caller-supplied provenance.

        Offline evaluation passes ``evaluation_only`` provenance so a synthetic fixture can
        be scored without ever becoming servable. Every other setting — cohorts, band
        cells, threshold, smoothing, band floor — is what a request gets, so a score and a
        served number stay one arithmetic.
        """
        if self.metadata.estimator == QUEUE_ESTIMATOR_ID:
            position_model = CohortPositionBaseline(
                min_sample_threshold=self.metadata.min_sample_threshold,
                laplace_alpha=self.metadata.laplace_alpha,
                min_band_rows=self.metadata.min_band_rows,
            )
            position_model.load_tables(self.cohorts, self.bands, provenance)
            return position_model
        baseline = HistoricalFrequencyBaseline(
            min_sample_threshold=self.metadata.min_sample_threshold,
            laplace_alpha=self.metadata.laplace_alpha,
        )
        baseline.load_frequency_table(self.cohorts, provenance)
        return baseline


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
        raw["estimator"] in (ESTIMATOR_HISTORICAL_FREQUENCY, QUEUE_ESTIMATOR_ID),
        f"Unknown estimator {raw['estimator']!r}; this build serves "
        f"{ESTIMATOR_HISTORICAL_FREQUENCY!r} and {QUEUE_ESTIMATOR_ID!r} only.",
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
    calibration_raw = raw.get("calibration")
    calibration: CalibrationSpec | None = None
    if calibration_raw is not None:
        calibration = spec_from_mapping(calibration_raw, artifact_target=raw["target"])
        _require(
            calibrated is True,
            "Artifact carries a calibration block but declares calibrated=false: a "
            "correction that is not applied must not be shipped beside one that is, or a "
            "reader cannot tell which number the artifact produced.",
        )
        _require(
            calibration_method in (None, calibration.method),
            f"Artifact calibration_method {calibration_method!r} disagrees with the "
            f"block's {calibration.method!r}.",
        )
        calibration_method = calibration.method
    else:
        _require(
            calibrated is False,
            "An artifact claiming calibrated=true must carry the calibration block — "
            "method, fitted partition, row count, period and both parameters. A claim "
            "without them cannot be reviewed, reproduced or applied.",
        )

    expected_features = (
        QUEUE_FEATURES
        if raw["estimator"] == QUEUE_ESTIMATOR_ID
        else COHORT_FEATURES
    )
    features_used = raw.get("features_used")
    _require(
        isinstance(features_used, list) and tuple(features_used) == expected_features,
        f"Artifact features_used must be exactly {list(expected_features)} for estimator "
        f"{raw['estimator']!r}, got {features_used!r}. That declaration is what a report "
        "credits the model with: three names means the frequency table never looked at a "
        "queue position, and four means it did, so the numbers would not mean what the "
        "artifact claims.",
    )

    cohort_semantics = raw.get("cohort_semantics")
    _require(
        cohort_semantics == COHORT_STATUS_SEMANTICS,
        f"Artifact cohort_semantics is {cohort_semantics!r}, but requests are answered "
        f"from {COHORT_STATUS_SEMANTICS!r} (the status held as of the prediction "
        "time). Fitting on one status column and looking up another would answer with "
        "counts from a different population, so the artifact is refused instead of "
        "reinterpreted.",
    )

    min_band_rows = raw.get("min_band_rows", DEFAULT_MIN_BAND_ROWS)
    _require(
        isinstance(min_band_rows, int)
        and not isinstance(min_band_rows, bool)
        and min_band_rows >= 1,
        f"Artifact min_band_rows must be a positive integer, got {min_band_rows!r}.",
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
        features_used=tuple(features_used),
        cohort_semantics=cohort_semantics,
        min_band_rows=int(min_band_rows),
        trained_from=trained_from,
        trained_to=trained_to,
        calibration_method=calibration_method,
        calibrated=calibrated,
        calibration=calibration,
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
        declared_format in KNOWN_FORMATS,
        f"Artifact {path.name} declares format {declared_format!r}, expected one of "
        f"{list(KNOWN_FORMATS)}.",
    )

    metadata = metadata_from_mapping(
        document.get("metadata"),
        expected_version=expected_version,
        expected_target=expected_target,
    )
    expected_format = format_for_estimator(metadata.estimator)
    assert expected_format is not None  # metadata_from_mapping has already refused others
    _require(
        declared_format == expected_format,
        f"Artifact {path.name} declares format {declared_format!r} but estimator "
        f"{metadata.estimator!r}, whose tables are laid out as {expected_format!r}. "
        "Reading one estimator's payload with the other's arithmetic would produce "
        "plausible numbers for the wrong model.",
    )

    cohorts = _decode_cohorts(document.get("cohorts"))
    try:
        normalized = normalize_frequency_table(cohorts)
    except FrequencyTableValidationError as exc:
        raise ModelArtifactError(
            f"Artifact {path.name} carries an unusable cohort table: {exc}"
        ) from exc

    bands: dict[BandKey, dict[str, int]] = {}
    if metadata.estimator == QUEUE_ESTIMATOR_ID:
        try:
            bands = normalize_band_table(_decode_bands(document, path.name))
        except FrequencyTableValidationError as exc:
            raise ModelArtifactError(
                f"Artifact {path.name} carries an unusable band table: {exc}"
            ) from exc
    else:
        _require(
            "bands" not in document,
            f"Artifact {path.name} carries band cells but declares the frequency "
            "estimator, which never reads a queue position. Either this file is the "
            "other model or the band table would be silently ignored.",
        )

    return LoadedArtifact(
        metadata=metadata, cohorts=normalized, path=path, bands=bands
    )


def _decode_bands(document: dict[str, Any], name: str) -> dict[BandKey, dict[str, int]]:
    """Read the position cells, refusing a missing block instead of answering flat."""
    raw_bands = document.get("bands")
    if not isinstance(raw_bands, dict) or not raw_bands:
        raise ModelArtifactError(
            f"Artifact {name} declares the position estimator but carries no band cells, "
            "so every request would be answered from the cohort — the model it does not "
            "claim to be. Fit the position bands or declare the frequency estimator."
        )
    table: dict[BandKey, dict[str, int]] = {}
    for key, counts in raw_bands.items():
        parts = str(key).split(_COHORT_SEPARATOR)
        _require(
            len(parts) == 4 and all(part.strip() for part in parts),
            f"Band key {key!r} must be a four-part key "
            f"CLASS{_COHORT_SEPARATOR}QUOTA{_COHORT_SEPARATOR}STATUS"
            f"{_COHORT_SEPARATOR}BAND; a three-part key names a cohort, not a band.",
        )
        _require(
            isinstance(counts, dict),
            f"Band {key!r} counts must be a JSON object.",
        )
        class_code, quota_code, status, band = parts
        table[(class_code, quota_code, status, band)] = dict(counts)
    return table


def encode_bands(table: dict[BandKey, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Encode band cells for JSON with deterministic key order."""
    return {
        _COHORT_SEPARATOR.join(band_key): {
            c: counts[c] for c in OUTCOME_CLASSES if c in counts
        }
        for band_key, counts in sorted(table.items())
    }


def encode_cohorts(table: dict[tuple[str, str, str], dict[str, int]]) -> dict[str, dict[str, int]]:
    """Encode a cohort table for JSON with deterministic key order."""
    return {
        _COHORT_SEPARATOR.join(cohort): {c: counts[c] for c in OUTCOME_CLASSES if c in counts}
        for cohort, counts in sorted(table.items())
    }


def build_artifact_document(
    metadata: ModelArtifactMetadata,
    cohorts: dict[tuple[str, str, str], dict[str, int]],
    bands: dict[BandKey, dict[str, int]] | None = None,
) -> str:
    """Serialise an artifact deterministically so two runs can be compared.

    The format follows the estimator rather than the caller, and the band block exists only
    for the model that reads it: a file carrying counts its arithmetic never consults is the
    confusion this refuses to write.
    """
    declared_format = format_for_estimator(metadata.estimator)
    if declared_format is None:
        raise ModelArtifactError(
            f"Artifact declares unknown estimator {metadata.estimator!r}, so no payload "
            "layout could carry it."
        )
    metadata_block = asdict(metadata)
    if metadata.estimator == QUEUE_ESTIMATOR_ID:
        if not bands:
            raise ModelArtifactError(
                "A cohort-position artifact with no band cells answers every request from "
                "the cohort, which makes it the frequency-baseline artifact: write it as "
                "that estimator, or fit the position cells."
            )
        payload_bands: dict[str, dict[str, int]] | None = encode_bands(
            normalize_band_table(bands)
        )
    else:
        if bands:
            raise ModelArtifactError(
                "The frequency-baseline declares no band table, so band cells in this "
                "artifact would never be read. Declare the position estimator instead."
            )
        payload_bands = None
        metadata_block.pop("min_band_rows", None)

    document = {
        "artifact_format": declared_format,
        "metadata": {
            **metadata_block,
            "outcome_classes": list(metadata.outcome_classes),
            "limitations": list(metadata.limitations),
        },
        "cohorts": encode_cohorts(normalize_frequency_table(cohorts)),
    }
    if payload_bands is not None:
        document["bands"] = payload_bands
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_artifact(
    path: Path,
    metadata: ModelArtifactMetadata,
    cohorts: dict[tuple[str, str, str], dict[str, int]],
    bands: dict[BandKey, dict[str, int]] | None = None,
) -> Path:
    """Write a validated artifact to ``path`` (a ``.json`` file under the models dir)."""
    if path.suffix != ".json":
        raise ModelArtifactError(f"Artifact path {path} must use the .json extension.")
    document = build_artifact_document(metadata, cohorts, bands=bands)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path

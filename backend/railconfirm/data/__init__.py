"""Data loading, validation, manifest handling, and preprocessing for RailConfirm Intelligence."""

from railconfirm.data.loader import DEFAULT_MAX_BYTES, SUPPORTED_SUFFIXES, load_dataset_file
from railconfirm.data.manifest import (
    DatasetManifest,
    ManifestError,
    generate_manifest,
    parse_manifest,
    verify_manifest,
    write_manifest,
)
from railconfirm.data.preprocessing import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    SplitResult,
    assert_no_label_columns,
    chronological_split,
    extract_features,
    feature_frame,
    strip_labels,
)
from railconfirm.data.validator import (
    DatasetValidationReport,
    EligibilityThresholds,
    validate_dataset,
)

__all__ = [
    "DEFAULT_MAX_BYTES",
    "FEATURE_COLUMNS",
    "FEATURE_SCHEMA_VERSION",
    "DatasetManifest",
    "DatasetValidationReport",
    "EligibilityThresholds",
    "ManifestError",
    "SUPPORTED_SUFFIXES",
    "SplitResult",
    "assert_no_label_columns",
    "chronological_split",
    "extract_features",
    "feature_frame",
    "generate_manifest",
    "load_dataset_file",
    "parse_manifest",
    "strip_labels",
    "validate_dataset",
    "verify_manifest",
    "write_manifest",
]

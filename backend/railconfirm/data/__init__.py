"""Data loading, validation, manifest handling, and preprocessing for RailConfirm Intelligence."""

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.manifest import DatasetManifest, generate_manifest
from railconfirm.data.preprocessing import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    SplitResult,
    assert_no_label_columns,
    chronological_split,
    extract_features,
    feature_frame,
)
from railconfirm.data.validator import (
    DatasetValidationReport,
    EligibilityThresholds,
    validate_dataset,
)

__all__ = [
    "FEATURE_COLUMNS",
    "FEATURE_SCHEMA_VERSION",
    "DatasetManifest",
    "DatasetValidationReport",
    "EligibilityThresholds",
    "SplitResult",
    "assert_no_label_columns",
    "chronological_split",
    "extract_features",
    "feature_frame",
    "generate_manifest",
    "load_dataset_file",
    "validate_dataset",
]

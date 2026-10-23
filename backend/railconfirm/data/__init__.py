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
    ASOF_STATUS_FEATURE,
    FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    OriginWindow,
    RollingOriginPlan,
    SplitResult,
    asof_statuses,
    assert_no_label_columns,
    chronological_split,
    extract_features,
    feature_frame,
    require_status_columns,
    rolling_origin_windows,
    strip_labels,
)
from railconfirm.data.validator import (
    DatasetValidationReport,
    EligibilityThresholds,
    assess_dataset,
    validate_dataset,
)

__all__ = [
    "ASOF_STATUS_FEATURE",
    "DEFAULT_MAX_BYTES",
    "FEATURE_COLUMNS",
    "FEATURE_SCHEMA_VERSION",
    "DatasetManifest",
    "DatasetValidationReport",
    "EligibilityThresholds",
    "ManifestError",
    "OriginWindow",
    "RollingOriginPlan",
    "SUPPORTED_SUFFIXES",
    "SplitResult",
    "asof_statuses",
    "assert_no_label_columns",
    "assess_dataset",
    "chronological_split",
    "extract_features",
    "feature_frame",
    "generate_manifest",
    "load_dataset_file",
    "parse_manifest",
    "require_status_columns",
    "rolling_origin_windows",
    "strip_labels",
    "validate_dataset",
    "verify_manifest",
    "write_manifest",
]

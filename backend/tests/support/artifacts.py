"""Shared synthetic model-artifact fixtures.

These build self-declared synthetic artifacts so tests can exercise the registry
and engine trust boundaries. Nothing here is railway evidence.
"""

from __future__ import annotations

from pathlib import Path

from railconfirm.domain.prediction import PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import (
    ESTIMATOR_HISTORICAL_FREQUENCY,
    PROMOTION_APPROVED,
    ModelArtifactMetadata,
    write_artifact,
)
from railconfirm.inference.baseline import OUTCOME_CLASSES
from railconfirm.inference.queue import QUEUE_ESTIMATOR_ID, QUEUE_FEATURES
from railconfirm.inference.registry import ModelRegistry

COHORTS: dict[tuple[str, str, str], dict[str, int]] = {
    ("SL", "GN", "WL"): {"CNF": 70, "RAC": 20, "WL": 10, "CANCELLED": 5, "OTHER": 0},
}

LIMITATIONS = ("Synthetic fixture artifact; not railway evidence.",)


def artifact_metadata(**overrides) -> ModelArtifactMetadata:
    base: dict[str, object] = {
        "version": "fixture_v1",
        "target": PredictionTarget.FINAL_CHART_CNF.value,
        "estimator": ESTIMATOR_HISTORICAL_FREQUENCY,
        "feature_schema_version": "1.0.0",
        "status_mapping_version": MAPPING_VERSION,
        "outcome_classes": OUTCOME_CLASSES,
        "dataset_id": "fixture-sl-gn-2026-10",
        "dataset_sha256": "a" * 64,
        "source_reference": "SOURCE_REGISTER#fixture",
        "data_approval_status": "approved",
        "is_synthetic": False,
        "min_sample_threshold": 10,
        "laplace_alpha": 1.0,
        "promotion": PROMOTION_APPROVED,
        "limitations": LIMITATIONS,
        "trained_from": "2026-01-01",
        "trained_to": "2026-06-30",
    }
    base.update(overrides)
    return ModelArtifactMetadata(**base)  # type: ignore[arg-type]


POSITION_BANDS: dict[tuple[str, str, str, str], dict[str, int]] = {
    ("SL", "GN", "WL", "1"): {"CNF": 60, "RAC": 15, "WL": 15, "CANCELLED": 5, "OTHER": 5},
    ("SL", "GN", "WL", "32-63"): {
        "CNF": 5,
        "RAC": 5,
        "WL": 80,
        "CANCELLED": 5,
        "OTHER": 5,
    },
    ("SL", "GN", "ALL", "1"): {"CNF": 60, "RAC": 15, "WL": 15, "CANCELLED": 5, "OTHER": 5},
    ("SL", "GN", "ALL", "32-63"): {
        "CNF": 5,
        "RAC": 5,
        "WL": 80,
        "CANCELLED": 5,
        "OTHER": 5,
    },
}
"""First-in-queue and deep-in-queue cells for the fixture cohort. Synthetic by construction."""


def write_fixture_artifact(
    tmp_path: Path,
    name: str = "fixture_v1",
    cohorts: dict[tuple[str, str, str], dict[str, int]] | None = None,
    bands: dict[tuple[str, str, str, str], dict[str, int]] | None = None,
    **meta_overrides,
) -> Path:
    """Write an artifact file called ``<name>.json`` with the given metadata.

    Passing `bands` writes a position artifact and switches the estimator for the caller:
    band cells with no estimator that reads them are the mismatch the loader refuses."""
    if bands is not None:
        meta_overrides.setdefault("estimator", QUEUE_ESTIMATOR_ID)
        meta_overrides.setdefault("features_used", QUEUE_FEATURES)
    return write_artifact(
        tmp_path / f"{name}.json",
        artifact_metadata(**meta_overrides),
        COHORTS if cohorts is None else cohorts,
        bands=bands,
    )


def registry_for(tmp_path: Path, version: str = "fixture_v1") -> ModelRegistry:
    return ModelRegistry(models_dir=tmp_path, active_version=version)

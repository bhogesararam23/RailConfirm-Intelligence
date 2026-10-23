"""Synthetic dataset fixtures for the training pipeline tests.

Every row is labelled ``is_synthetic=true``. That label is load-bearing: it lets the
full fit → evaluate → registry path be exercised while guaranteeing the resulting
artifact can never be served as a real model. Nothing produced here is railway
evidence, and no test here asserts anything about railway behaviour.
"""

from __future__ import annotations

from pathlib import Path

from railconfirm.data.manifest import (
    AllowedUses,
    DecisionRecord,
    SourceRecord,
    generate_manifest,
    write_manifest,
)
from railconfirm.data.validator import REQUIRED_COLUMNS
from railconfirm.domain.prediction import PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.artifacts import (
    ESTIMATOR_HISTORICAL_FREQUENCY,
    PROMOTION_APPROVED,
    ModelArtifactMetadata,
    write_artifact,
)
from railconfirm.inference.baseline import OUTCOME_CLASSES

HEADER = ",".join(
    [*REQUIRED_COLUMNS, "booking_group_id", "passenger_record_id", "is_synthetic"]
)

APPROVED_REVIEWER = "synthetic-test-harness"

FITTABLE_COHORTS = {
    ("SL", "GN", "WL"): {"CNF": 70, "RAC": 20, "WL": 10, "CANCELLED": 5, "OTHER": 0},
    ("3A", "GN", "WL"): {"CNF": 30, "RAC": 10, "WL": 60, "CANCELLED": 0, "OTHER": 0},
    ("SL", "GN", "RAC"): {"CNF": 40, "RAC": 40, "WL": 20, "CANCELLED": 0, "OTHER": 0},
}


def build_rows(count: int = 240) -> list[str]:
    """Deterministic rows spanning 12 journey dates and both outcome labels."""
    rows: list[str] = []
    for index in range(count):
        day = index % 12 + 1
        month = 4 + index % 3
        initial = 10 + (index % 40)
        final = "CNF" if index % 3 == 0 else "WL/5"
        rows.append(
            f"1230{index % 3},2026-{month:02d}-{day:02d},"
            f"{'SL' if index % 2 else '3A'},GN,GNWL/{initial},{final},"
            f"2026-03-{(index % 28) + 1:02d},B{index:04d},P{index:04d},true"
        )
    return rows


def write_dataset(directory: Path, *, count: int = 240) -> Path:
    path = Path(directory) / "synthetic-training.csv"
    path.write_text(
        "# SYNTHETIC DATA - PIPELINE TEST ONLY - NOT REAL RAILWAY OBSERVATIONS\n"
        + HEADER
        + "\n"
        + "\n".join(build_rows(count))
        + "\n",
        encoding="utf-8",
    )
    return path


def approved_source(**overrides) -> SourceRecord:
    base = {
        "publisher": "synthetic test harness",
        "retrieved_on": "2026-04-01",
        "source_register_entry": "tests/support/datasets.py",
        "terms_url": "https://example.invalid/synthetic-terms",
        "licence_name": "synthetic fixture",
        "licence_review_status": "approved",
        "allowed_uses": AllowedUses(
            local_inspection="permitted",
            transformation="permitted",
            model_training="permitted",
            aggregate_metric_publication="permitted",
            commercial_deployment="prohibited",
            redistribution="prohibited",
        ),
        "attribution_requirements": "none",
    }
    base.update(overrides)
    return SourceRecord(**base)


def approved_decision(**overrides) -> DecisionRecord:
    base = {
        "reviewed_by": APPROVED_REVIEWER,
        "reviewed_on": "2026-04-02",
        "decision": "approved",
        "rationale": "Synthetic fixture approved for pipeline testing only.",
    }
    base.update(overrides)
    return DecisionRecord(**base)


def write_approved_manifest(
    dataset_path: Path,
    directory: Path,
    *,
    dataset_id: str = "synthetic-pipeline-fixture",
    source: SourceRecord | None = None,
    decision: DecisionRecord | None = None,
) -> Path:
    """Generate and write a manifest whose decision section satisfies the gate."""
    manifest = generate_manifest(
        dataset_path,
        dataset_id=dataset_id,
        title="Synthetic pipeline fixture",
        retrieved_on="2026-04-01",
        source=source or approved_source(),
        decision=decision if decision is not None else approved_decision(),
    )
    return write_manifest(manifest, Path(directory) / f"{dataset_id}.yaml", overwrite=True)


def artifact_metadata(**overrides) -> ModelArtifactMetadata:
    base = {
        "version": "fixture_v1",
        "target": PredictionTarget.FINAL_CHART_CNF.value,
        "estimator": ESTIMATOR_HISTORICAL_FREQUENCY,
        "feature_schema_version": "2.0.0",
        "status_mapping_version": MAPPING_VERSION,
        "outcome_classes": OUTCOME_CLASSES,
        "dataset_id": "synthetic-pipeline-fixture",
        "dataset_sha256": "b" * 64,
        "source_reference": "tests/support/datasets.py",
        "data_approval_status": "approved",
        "is_synthetic": False,
        "min_sample_threshold": 5,
        "laplace_alpha": 1.0,
        "promotion": PROMOTION_APPROVED,
        "limitations": ("Synthetic fixture artifact; not railway evidence.",),
        "trained_from": "2026-04-01",
        "trained_to": "2026-04-12",
    }
    base.update(overrides)
    return ModelArtifactMetadata(**base)


def write_serving_artifact(
    directory: Path,
    *,
    name: str = "fixture_v1",
    cohorts: dict | None = None,
    **meta_overrides,
) -> Path:
    """Write an artifact that the registry will serve, for engine and CLI tests."""
    return write_artifact(
        Path(directory) / f"{name}.json",
        artifact_metadata(**meta_overrides),
        cohorts or FITTABLE_COHORTS,
    )

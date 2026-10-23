"""Tests for the training data gate: what may and may not be fitted on."""

from pathlib import Path

import pytest

from railconfirm.training.dataset import TrainingDataError, load_approved_dataset
from tests.support.datasets import (
    approved_decision,
    approved_source,
    write_approved_manifest,
    write_dataset,
)


@pytest.fixture
def dataset(tmp_path: Path):
    csv = write_dataset(tmp_path)
    manifest = write_approved_manifest(csv, tmp_path)
    return csv, manifest


def test_approved_dataset_loads(dataset):
    csv, manifest = dataset
    loaded = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    assert loaded.report.valid_rows > 0
    assert loaded.is_synthetic is True
    assert len(loaded.sha256) == 64


def test_synthetic_rows_are_blocked_without_an_explicit_opt_in(dataset):
    """The gate's whole purpose: pipeline testing must not become a real claim."""
    csv, manifest = dataset
    with pytest.raises(TrainingDataError, match="is_synthetic"):
        load_approved_dataset(csv, manifest)


def test_unverified_manifest_is_refused(dataset, tmp_path):
    csv, manifest = dataset
    tampered = tmp_path / "tampered.yaml"
    text = manifest.read_text(encoding="utf-8").replace("row_count: 240", "row_count: 999")
    tampered.write_text(text, encoding="utf-8")
    with pytest.raises(TrainingDataError, match="row_count"):
        load_approved_dataset(
            csv, tampered, allow_synthetic_for_testing=True
        )


def test_changed_file_content_is_refused(dataset, tmp_path):
    csv, manifest = dataset
    edited = tmp_path / "edited.csv"
    edited.write_bytes(csv.read_bytes() + b"12301,2026-07-01,SL,GN,GNWL/9,CNF,2026-06-01,B9,P9,true\n")
    with pytest.raises(TrainingDataError, match="content changed"):
        load_approved_dataset(edited, manifest, allow_synthetic_for_testing=True)


@pytest.mark.parametrize(
    "decision_kwargs,fragment",
    [
        ({"decision": "under_review", "reviewed_by": None, "reviewed_on": None}, "requires an explicit"),
        ({"decision": "quarantined", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "quarantined"),
        ({"decision": "rejected", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "rejected"),
        ({"decision": "restricted", "reviewed_by": "R.", "reviewed_on": "2026-04-02"}, "restricted"),
    ],
)
def test_non_approved_decision_is_refused(dataset, tmp_path, decision_kwargs, fragment):
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="scenario", decision=approved_decision(**decision_kwargs)
    )
    with pytest.raises(TrainingDataError, match=fragment):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_approval_without_a_named_reviewer_is_refused(dataset, tmp_path):
    """The manifest model rejects this on construction, before training is reached."""
    csv, _ = dataset
    from railconfirm.data.manifest import ManifestError

    with pytest.raises(ManifestError, match="reviewed_by"):
        write_approved_manifest(
            csv,
            tmp_path,
            dataset_id="no-reviewer",
            decision=approved_decision(reviewed_by=None),
        )


@pytest.mark.parametrize(
    "source_overrides,fragment",
    [
        ({"licence_review_status": "pending"}, "licence_review_status"),
        ({"licence_review_status": "restricted"}, "licence_review_status"),
    ],
)
def test_unreviewed_licence_is_refused(dataset, tmp_path, source_overrides, fragment):
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="licence-case", source=approved_source(**source_overrides)
    )
    with pytest.raises(TrainingDataError, match=fragment):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_licence_approved_without_training_permission_is_refused(dataset, tmp_path):
    """The manifest cannot even express this contradiction, so the gate is two-layered."""
    csv, _ = dataset
    from railconfirm.data.manifest import AllowedUses, ManifestError

    with pytest.raises(ManifestError, match="model_training"):
        approved_source(
            allowed_uses=AllowedUses(model_training="unknown"),
            licence_review_status="approved",
        )


def test_restricted_training_use_is_refused_even_with_an_approved_licence(dataset, tmp_path):
    """A licence reviewed as "approved" but permitting only restricted training is not
    a training permission; the two fields are checked separately on purpose."""
    csv, _ = dataset
    from railconfirm.data.manifest import AllowedUses

    manifest = write_approved_manifest(
        csv,
        tmp_path,
        dataset_id="use-restricted",
        source=approved_source(allowed_uses=AllowedUses(model_training="restricted")),
        decision=approved_decision(),
    )
    with pytest.raises(TrainingDataError, match="model_training"):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


@pytest.mark.parametrize("status", ["pending", "restricted", "rejected"])
def test_licence_review_order_is_checked_before_training_use(dataset, tmp_path, status):
    """Both are blockers; the message names the first one so a reviewer fixes in order."""
    csv, _ = dataset
    manifest = write_approved_manifest(
        csv,
        tmp_path,
        dataset_id=f"licence-{status}",
        source=approved_source(
            licence_review_status=status,
            allowed_uses=approved_source().allowed_uses,
        ),
    )
    with pytest.raises(TrainingDataError, match="licence_review_status"):
        load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)


def test_missing_files_are_reported(tmp_path):
    with pytest.raises(TrainingDataError, match="Dataset file not found"):
        load_approved_dataset(tmp_path / "nope.csv", tmp_path / "nope.yaml")
    csv = write_dataset(tmp_path)
    with pytest.raises(TrainingDataError, match="Manifest file not found"):
        load_approved_dataset(csv, tmp_path / "nope.yaml")


def test_structurally_invalid_dataset_is_refused(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_text(
        "train_number,journey_date\n12301,2026-04-01\n", encoding="utf-8"
    )
    manifest = write_approved_manifest(path, tmp_path, dataset_id="broken")
    with pytest.raises(TrainingDataError, match="structurally valid|Schema incomplete"):
        load_approved_dataset(path, manifest, allow_synthetic_for_testing=True)

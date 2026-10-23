"""Dataset access gate for training.

Training must refuse before it produces anything misleading. This module decides
whether a file may be fitted on, and it is deliberately conservative:

* the manifest must verify against the file it describes (hash, size, row count);
* a named human must have recorded an approval decision with a rationale;
* the licence review must permit model training explicitly;
* synthetic rows can never satisfy the gate. A pipeline test may opt in explicitly
  with ``allow_synthetic_for_testing``, and the artifact it produces records that
  fact, which makes the artifact unservable by the registry.

The last rule is what lets the whole training-to-registry path be exercised without
any chance of a synthetic result being presented as a real one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.manifest import DatasetManifest, parse_manifest, verify_manifest
from railconfirm.data.validator import DatasetValidationReport, validate_dataset
from railconfirm.domain.exceptions import DatasetValidationError

TRAINING_USE_FIELD = "model_training"
PERMITTED = "permitted"


class TrainingDataError(DatasetValidationError):
    """The dataset cannot be used for training, with the reason."""


@dataclass(frozen=True)
class ApprovedDataset:
    """A dataset file plus the manifest and validation report that describe it."""

    dataset_path: Path
    manifest: DatasetManifest
    frame: pd.DataFrame
    report: DatasetValidationReport
    is_synthetic: bool

    @property
    def dataset_id(self) -> str:
        return self.manifest.dataset_id

    @property
    def sha256(self) -> str:
        return self.manifest.file.sha256 or ""


def _detect_synthetic(frame: pd.DataFrame) -> bool:
    if "is_synthetic" not in frame.columns:
        return False
    values = {str(value).strip().lower() for value in frame["is_synthetic"].tolist()}
    return bool(values & {"true", "1", "yes"})


def assert_trainable(
    manifest: DatasetManifest,
    *,
    is_synthetic: bool,
    allow_synthetic_for_testing: bool = False,
) -> None:
    """Raise TrainingDataError unless this dataset may legitimately be fitted on."""
    if is_synthetic and not allow_synthetic_for_testing:
        raise TrainingDataError(
            "Dataset rows declare is_synthetic. Synthetic records can exercise the "
            "pipeline; they cannot support any claim about railway behaviour. Pass "
            "allow_synthetic_for_testing to fit anyway — the artifact will be marked "
            "synthetic and the registry will refuse to serve it."
        )

    decision = manifest.decision
    if decision.decision != "approved":
        raise TrainingDataError(
            f"Dataset {manifest.dataset_id!r} has decision "
            f"{decision.decision!r}; training requires an explicit 'approved' "
            "decision recorded by a named reviewer."
        )
    if not (decision.reviewed_by or "").strip() or not (decision.reviewed_on or "").strip():
        raise TrainingDataError(
            "Training needs an approval carrying reviewed_by and reviewed_on."
        )
    if manifest.source.licence_review_status != "approved":
        raise TrainingDataError(
            f"source.licence_review_status is "
            f"{manifest.source.licence_review_status!r}; the licence must be reviewed "
            "and approved before training."
        )
    use = getattr(manifest.source.allowed_uses, TRAINING_USE_FIELD)
    if use != PERMITTED:
        raise TrainingDataError(
            f"source.allowed_uses.{TRAINING_USE_FIELD} is {use!r}; training is only "
            "permitted when the recorded licence says so."
        )


def load_approved_dataset(
    dataset_path: Path,
    manifest_path: Path,
    *,
    allow_synthetic_for_testing: bool = False,
) -> ApprovedDataset:
    """Load a dataset only after its provenance and permissions check out."""
    data_path = Path(dataset_path)
    manifest_file = Path(manifest_path)
    if not data_path.is_file():
        raise TrainingDataError(f"Dataset file not found: {data_path}")
    if not manifest_file.is_file():
        raise TrainingDataError(f"Manifest file not found: {manifest_file}")

    manifest = parse_manifest(manifest_file.read_text(encoding="utf-8"))

    verification = verify_manifest(manifest_file, data_path)
    if not verification.ok:
        raise TrainingDataError(
            "Manifest does not verify against the dataset file:\n  - "
            + "\n  - ".join(verification.findings)
        )

    frame = load_dataset_file(data_path)
    report = validate_dataset(frame, source_name=data_path.name)
    if not report.structurally_valid:
        raise TrainingDataError(
            "Dataset is not structurally valid:\n  - "
            + "\n  - ".join(report.eligibility_findings or report.missing_columns)
        )

    synthetic = _detect_synthetic(frame)
    assert_trainable(
        manifest,
        is_synthetic=synthetic,
        allow_synthetic_for_testing=allow_synthetic_for_testing,
    )

    return ApprovedDataset(
        dataset_path=data_path,
        manifest=manifest,
        frame=frame,
        report=report,
        is_synthetic=synthetic,
    )

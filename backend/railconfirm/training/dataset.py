"""Dataset access gate for training.

Training must refuse before it produces anything misleading. This module decides
whether a file may be fitted on, and it is deliberately conservative:

* the manifest must verify against the file it describes (hash, size, row count);
* a named human must have recorded an approval decision with a rationale;
* the licence review must permit model training explicitly;
* the file must pass the validator's *technical eligibility* rules, not merely be
  structurally parseable — enough clean rows, more than one outcome class, and a
  date span a chronological split can hold back;
* rows the validator rejected (duplicates, contradictory or censored labels,
  unparseable dates, observations after the journey) are removed here, so they
  cannot reach fitting or scoring;
* synthetic rows can never satisfy the gate. A pipeline test may opt in explicitly
  with ``allow_synthetic_for_testing``, and the artifact it produces records that
  fact, which makes the artifact unservable by the registry.

The last two rules are what let the whole training-to-registry path be exercised
without any chance of a synthetic result being presented as a real one. The
eligibility relaxation available to that opt-in applies to synthetic rows only: a
real dataset that fails intake is refused with no way around it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.manifest import DatasetManifest, parse_manifest, verify_manifest
from railconfirm.data.validator import (
    DatasetValidationReport,
    assess_dataset,
)
from railconfirm.domain.exceptions import DatasetValidationError

TRAINING_USE_FIELD = "model_training"
PERMITTED = "permitted"


class TrainingDataError(DatasetValidationError):
    """The dataset cannot be used for training, with the reason."""


@dataclass(frozen=True)
class ApprovedDataset:
    """A dataset file plus the manifest and validation report that describe it.

    ``frame`` holds only the rows the validator kept, so every count in ``report``
    describes the same file the frame came from while fitting sees only the part of
    it that passed. ``eligibility_relaxed`` records that a pipeline-test run fitted
    on rows below the intake thresholds, which the artifact then has to state.
    """

    dataset_path: Path
    manifest: DatasetManifest
    frame: pd.DataFrame
    report: DatasetValidationReport
    is_synthetic: bool
    eligibility_relaxed: bool = False

    @property
    def dataset_id(self) -> str:
        return self.manifest.dataset_id

    @property
    def sha256(self) -> str:
        return self.manifest.file.sha256 or ""

    @property
    def rejected_rows(self) -> int:
        return self.report.rejected_rows


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
    """Load a dataset only after its permissions and quality both check out."""
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
    report, usable = assess_dataset(frame, source_name=data_path.name)
    synthetic = _detect_synthetic(frame)

    if not report.structurally_valid:
        raise TrainingDataError(
            "Dataset is not structurally valid:\n  - "
            + "\n  - ".join(report.eligibility_findings or report.missing_columns)
        )

    assert_trainable(
        manifest,
        is_synthetic=synthetic,
        allow_synthetic_for_testing=allow_synthetic_for_testing,
    )

    # A pipeline-test run may fit below the intake thresholds because its purpose is
    # to exercise the code, and its artifact is marked synthetic so it can never be
    # served. Nothing else may: a real dataset that cannot support an evaluation is
    # refused rather than fitted on anyway.
    relaxed = synthetic and allow_synthetic_for_testing and not report.technically_eligible
    if not report.technically_eligible and not relaxed:
        raise TrainingDataError(
            "Dataset is structurally valid but not technically eligible for "
            "training:\n  - " + "\n  - ".join(report.eligibility_findings)
        )

    return ApprovedDataset(
        dataset_path=data_path,
        manifest=manifest,
        frame=usable,
        report=report,
        is_synthetic=synthetic,
        eligibility_relaxed=relaxed,
    )

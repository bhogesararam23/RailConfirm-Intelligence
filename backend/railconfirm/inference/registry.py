"""Model artifact registry for RailConfirm Intelligence.

The registry answers one question: *is there an artifact that may legitimately
serve this request?* A file sitting in the models directory is not an answer.
Activation requires both an explicit configuration value and a metadata block
that declares itself approved for local use, so a dropped-in file cannot silently
become the active model.

Every resolution attempt returns a status, a safe human-readable detail and, when
it abstains, the abstention reason the caller should report. Failures are visible
rather than folded into "no model exists yet".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from railconfirm.config import settings
from railconfirm.domain.exceptions import ModelArtifactError
from railconfirm.domain.prediction import AbstentionReason, PredictionTarget
from railconfirm.inference.artifacts import (
    PROMOTION_APPROVED,
    LoadedArtifact,
    load_artifact,
)
from railconfirm.inference.baseline import (
    HistoricalFrequencyBaseline,
    ProbabilityEstimator,
)

logger = logging.getLogger(__name__)

NO_MODEL_VERSION = "no_model_v0"
"""Sentinel active-model value meaning "nothing is promoted"."""

_APPROVED_DATA_STATUS = "approved"

# A version becomes a file name, so it is restricted to characters that cannot
# traverse a path. An env-provided value is external input at the boundary.
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ArtifactStatus(str, Enum):
    """Registry resolution outcome. Part of the operational contract."""

    NO_ACTIVE_VERSION = "no_active_version"
    ARTIFACT_MISSING = "artifact_missing"
    ARTIFACT_INVALID = "artifact_invalid"
    NOT_PROMOTED = "not_promoted"
    DATA_NOT_APPROVED = "data_not_approved"
    READY = "ready"


@dataclass(frozen=True)
class ArtifactResolution:
    """Outcome of an artifact resolution attempt."""

    status: ArtifactStatus
    version: str
    detail: str
    abstention_reason: AbstentionReason | None
    artifact: LoadedArtifact | None = None

    @property
    def is_ready(self) -> bool:
        return self.status is ArtifactStatus.READY and self.artifact is not None


def _validate_version(version: str) -> str:
    if version == NO_MODEL_VERSION:
        return version
    candidate = str(version).strip()
    if not _VERSION_PATTERN.match(candidate) or ".." in candidate:
        raise ModelArtifactError(
            f"Active model version {version!r} is not a safe artifact identifier; "
            "expected a short alphanumeric name."
        )
    return candidate


class ModelRegistry:
    """Resolves the active model artifact against explicit promotion state."""

    def __init__(
        self,
        models_dir: Path | None = None,
        active_version: str | None = None,
        max_artifact_bytes: int | None = None,
    ) -> None:
        self._models_dir = models_dir
        self._active_version = active_version
        self._max_artifact_bytes = max_artifact_bytes

    @property
    def models_dir(self) -> Path:
        return self._models_dir if self._models_dir is not None else settings.models_dir

    @property
    def active_version(self) -> str:
        configured = (
            self._active_version
            if self._active_version is not None
            else settings.active_model_version
        )
        return _validate_version(configured)

    @property
    def max_artifact_bytes(self) -> int:
        return (
            self._max_artifact_bytes
            if self._max_artifact_bytes is not None
            else settings.max_artifact_bytes
        )

    def artifact_path(self, version: str) -> Path:
        return self.models_dir / f"{version}.json"

    def resolve(self, target: PredictionTarget) -> ArtifactResolution:
        """Resolve the active artifact for ``target`` without raising.

        A configuration that names an unsafe version is a deployment error, not a
        prediction outcome, so that case still raises.
        """
        version = self.active_version

        if version == NO_MODEL_VERSION:
            return ArtifactResolution(
                status=ArtifactStatus.NO_ACTIVE_VERSION,
                version=NO_MODEL_VERSION,
                detail=(
                    "No model version is configured as active; the registry serves no "
                    "artifact."
                ),
                abstention_reason=AbstentionReason.NO_TRAINED_MODEL,
            )

        path = self.artifact_path(version)
        if not path.is_file():
            return ArtifactResolution(
                status=ArtifactStatus.ARTIFACT_MISSING,
                version=version,
                detail=f"Active model version {version!r} has no artifact at {path}.",
                abstention_reason=AbstentionReason.NO_TRAINED_MODEL,
            )

        try:
            artifact = load_artifact(
                path,
                expected_version=version,
                expected_target=target.value,
                max_bytes=self.max_artifact_bytes,
            )
        except ModelArtifactError as exc:
            logger.warning("Model artifact %s rejected: %s", path.name, exc)
            return ArtifactResolution(
                status=ArtifactStatus.ARTIFACT_INVALID,
                version=version,
                detail=f"Artifact {path.name} was rejected: {exc}",
                abstention_reason=AbstentionReason.MODEL_ARTIFACT_INVALID,
            )

        metadata = artifact.metadata

        if metadata.promotion != PROMOTION_APPROVED:
            return ArtifactResolution(
                status=ArtifactStatus.NOT_PROMOTED,
                version=version,
                detail=(
                    f"Artifact {version} declares promotion {metadata.promotion!r}; "
                    f"only {PROMOTION_APPROVED!r} may serve predictions."
                ),
                abstention_reason=AbstentionReason.NO_TRAINED_MODEL,
            )

        if metadata.data_approval_status != _APPROVED_DATA_STATUS or metadata.is_synthetic:
            return ArtifactResolution(
                status=ArtifactStatus.DATA_NOT_APPROVED,
                version=version,
                detail=(
                    f"Artifact {version} was fitted from dataset {metadata.dataset_id!r} "
                    f"(approval={metadata.data_approval_status!r}, "
                    f"synthetic={metadata.is_synthetic}); it may not serve estimates."
                ),
                abstention_reason=AbstentionReason.NO_APPROVED_DATA,
            )

        return ArtifactResolution(
            status=ArtifactStatus.READY,
            version=version,
            detail=(
                f"Artifact {version} serves target {metadata.target} from dataset "
                f"{metadata.dataset_id} ({len(artifact.cohorts)} cohorts)."
            ),
            abstention_reason=None,
            artifact=artifact,
        )

    def estimator(
        self,
        target: PredictionTarget,
        fallback: HistoricalFrequencyBaseline,
    ) -> tuple[ProbabilityEstimator, ArtifactResolution]:
        """Return the estimator to use plus the resolution that justifies it.

        When no artifact is ready the caller-supplied fallback is used, so the
        engine keeps a single code path and the fallback's own provenance gate
        decides whether it can produce numbers.
        """
        resolution = self.resolve(target)
        if not resolution.is_ready or resolution.artifact is None:
            return fallback, resolution
        return resolution.artifact.estimator(), resolution

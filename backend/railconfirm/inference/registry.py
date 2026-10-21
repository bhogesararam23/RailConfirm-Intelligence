"""Model artifact registry for RailConfirm Intelligence.

Checks for the presence of approved, trained model artifacts.
Currently: no artifacts exist (Phase 0–7, local-first build).
"""

from __future__ import annotations

from railconfirm.config import settings


class ModelRegistry:
    """Resolves available model artifacts.

    In the current build (Phases 0–7), no trained artifacts exist. The registry
    always reports no available model, causing the inference engine to abstain.

    When an approved artifact is added in a later phase, update this class and
    record the decision in a new ADR before making the artifact active.
    """

    def has_model(self, model_version: str = "latest") -> bool:
        """Return True if a trained artifact for ``model_version`` is available."""
        # No artifacts exist in the current build.
        if settings.active_model_version == "no_model_v0":
            return False

        artifact_path = (
            settings.models_dir / f"{settings.active_model_version}.pkl"
        )
        return artifact_path.exists()

    def active_version(self) -> str:
        """Return the configured active model version string."""
        return settings.active_model_version

"""Application configuration for RailConfirm Intelligence.

All configuration is sourced from environment variables or defaults.
No secrets are hardcoded. No external network calls are made at startup.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to the repository layout so that artifact and dataset paths resolve
# identically whether the process starts from the repository root or from
# backend/. A relative path that depends on the current working directory makes
# "which artifact was loaded" unreproducible.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


def anchor_path(path: Path) -> Path:
    """Resolve a configured directory relative to the repository root."""
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings have safe defaults so the application can start without
    any environment configuration (local-first development mode).
    """

    model_config = SettingsConfigDict(
        env_prefix="RAILCONFIRM_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "RailConfirm Intelligence API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Server ─────────────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Paths ──────────────────────────────────────────────────────────────────
    # Approved local research datasets. This is a Git-ignored path: passing a
    # technical validation is not permission to publish the file.
    data_dir: Path = Path("data/processed")

    # Directory where model artifacts are stored (also Git-ignored by default).
    models_dir: Path = Path("models")

    # ── Inference ──────────────────────────────────────────────────────────────
    # Minimum sample threshold below which the baseline abstains.
    min_sample_threshold: int = 30

    # Upper bound on a model artifact read, so a corrupt or oversized file cannot
    # exhaust memory before it is validated.
    max_artifact_bytes: int = 4_194_304

    # ── Model registry ─────────────────────────────────────────────────────────
    # Active model version identifier. "no_model_v0" means no artifact is promoted.
    active_model_version: str = "no_model_v0"

    # ── Data ───────────────────────────────────────────────────────────────────
    # Version tag for the currently loaded dataset.
    data_version: str = "none"

    @field_validator("data_dir", "models_dir", mode="after")
    @classmethod
    def _anchor_directories(cls, value: Path) -> Path:
        return anchor_path(value)

    @field_validator("max_artifact_bytes", mode="after")
    @classmethod
    def _require_positive_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_artifact_bytes must be at least 1.")
        return value


# Singleton instance — import this throughout the application.
settings = Settings()

"""Application configuration for RailConfirm Intelligence.

All configuration is sourced from environment variables or defaults.
No secrets are hardcoded. No external network calls are made at startup.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings have safe defaults so the application can start without
    any environment configuration (local-first development mode).
    """

    model_config = SettingsConfigDict(
        env_prefix="RAILCONFIRM_",
        env_file=".env",
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
    # Base directory for locally approved datasets.
    data_dir: Path = Path("data/approved")

    # Directory where trained model artifacts are stored.
    models_dir: Path = Path("models")

    # ── Inference ──────────────────────────────────────────────────────────────
    # Minimum sample threshold below which the baseline abstains.
    min_sample_threshold: int = 30

    # ── Model registry ─────────────────────────────────────────────────────────
    # Active model version identifier. "no_model_v0" means no artifact exists.
    active_model_version: str = "no_model_v0"

    # ── Data ───────────────────────────────────────────────────────────────────
    # Version tag for the currently loaded dataset.
    data_version: str = "none"


# Singleton instance — import this throughout the application.
settings = Settings()

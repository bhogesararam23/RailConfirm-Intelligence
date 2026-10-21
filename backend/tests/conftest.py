"""Pytest configuration and shared fixtures for RailConfirm Intelligence tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from railconfirm.api.app import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def synthetic_booking_data() -> dict:
    """Load the synthetic booking request fixture."""
    path = FIXTURES_DIR / "synthetic_booking.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def synthetic_dataset_path() -> Path:
    """Return path to synthetic dataset CSV."""
    return FIXTURES_DIR / "synthetic_dataset.csv"


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    app = create_app()
    return TestClient(app)

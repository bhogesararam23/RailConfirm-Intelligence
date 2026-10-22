"""Pytest configuration and shared fixtures for RailConfirm Intelligence tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from railconfirm.api.app import create_app
from railconfirm.inference.engine import InferenceEngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Fixed in the past so observation times stay behind ingestion time as tests run.
AS_OF = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 10, 21, 7, 30, tzinfo=UTC)


def valid_payload(**overrides) -> dict:
    """A schema-valid manual prediction request, overridable per test."""
    payload: dict = {
        "journey": {
            "train_number": "12301",
            "journey_date": "2026-11-15",
            "boarding_station": "NDLS",
            "destination_station": "HWH",
            "class_code": "SL",
            "quota_code": "GN",
        },
        "prediction_at": AS_OF.isoformat(),
        "passengers": [
            {
                "original_status": "GNWL/45",
                "current_status": "GNWL/12",
                "current_status_observed_at": OBSERVED_AT.isoformat(),
            }
        ],
    }
    payload.update(overrides)
    return payload


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
def make_client():
    """Build a TestClient around an optionally injected engine."""

    def _make(
        engine: InferenceEngine | None = None,
        *,
        raise_server_exceptions: bool = True,
    ) -> TestClient:
        return TestClient(
            create_app(engine=engine),
            raise_server_exceptions=raise_server_exceptions,
        )

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    """Create a FastAPI test client with default wiring."""
    return make_client()

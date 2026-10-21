# RailConfirm Intelligence — Backend

Python backend implementing the domain model, prediction API, and local data pipeline.

**Status:** Phase 1–2 implementation. No trained model is currently available; the inference engine returns structured abstention responses for all requests. This is expected behavior until an approved dataset passes the intake checklist.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Setup

```bash
cd backend

# Using uv (recommended)
uv venv .venv
source .venv/bin/activate        # Linux/macOS
# Or on Windows:
.\.venv\Scripts\Activate.ps1

uv pip install -e ".[dev]"

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the API server

```bash
uvicorn railconfirm.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000`. Interactive docs at `http://127.0.0.1:8000/docs`.

**Note:** The server currently returns `NO_TRAINED_MODEL` abstentions for all prediction requests. This is correct behavior — no fabricated probabilities are returned.

## Running tests

```bash
# From the backend/ directory:
pytest tests/ -v
```

All tests must pass without external network access or private data files.

```bash
# With coverage:
pytest tests/ -v --cov=railconfirm --cov-report=term-missing
```

## API endpoints

### `POST /v1/predictions/manual`

Submit a journey and passenger status list for prediction.

**Request:**
```json
{
  "journey": {
    "train_number": "12301",
    "journey_date": "2026-11-15",
    "boarding_station": "NDLS",
    "destination_station": "HWH",
    "class_code": "SL",
    "quota_code": "GN"
  },
  "prediction_at": "2026-11-10T08:00:00Z",
  "passengers": [
    {
      "original_status": "GNWL/45",
      "current_status": "GNWL/12",
      "current_status_observed_at": "2026-11-10T07:30:00Z"
    }
  ]
}
```

**Response (no model available):**
```json
{
  "prediction_id": "...",
  "target_definition": "final_chart_cnf",
  "prediction_at": "2026-11-10T08:00:00Z",
  "model_version": "no_model_v0",
  "evidence_coverage": "insufficient",
  "is_supported": false,
  "passenger_outcomes": [
    {
      "passenger_id": "...",
      "is_supported": false,
      "abstention_reason": "no_trained_model",
      "p_cnf": null,
      "p_rac": null,
      "p_wl": null,
      "p_cancelled": null,
      "p_other": null
    }
  ],
  "limitations": [
    "No trained model is available. An approved historical dataset must pass the intake checklist before a model can be trained and validated."
  ]
}
```

### `GET /v1/health`

Returns API health and model availability.

```json
{
  "status": "ok",
  "model_version": "no_model_v0",
  "data_version": "none",
  "model_available": false
}
```

## Project structure

```
backend/
  pyproject.toml          — Package config and dependencies
  railconfirm/
    config.py             — Environment-variable configuration
    domain/
      status.py           — Status normalization (versioned mapping v1.0.0)
      journey.py          — Journey, class, and quota domain types
      passenger.py        — Passenger reservation and observation types
      prediction.py       — Prediction output, abstention, group semantics
      validation.py       — Shared validators and reason codes
      exceptions.py       — Domain exception hierarchy
    api/
      app.py              — FastAPI application factory
      v1/
        predictions.py    — POST /v1/predictions/manual
        health.py         — GET /v1/health
        schemas.py        — Request/response Pydantic models
    inference/
      engine.py           — Abstention-first dispatch
      baseline.py         — Historical frequency baseline (requires approved data)
      group.py            — Group outcome computation
      registry.py         — Model artifact registry
    data/
      loader.py           — CSV/JSON local dataset loader
      validator.py        — Dataset schema validation
      manifest.py         — Dataset manifest handling
      preprocessing.py    — As-of-time feature construction
  tests/
    domain/               — Status, journey, passenger, prediction, group tests
    api/                  — Prediction and health endpoint tests
    data/                 — Loader and validator tests
    fixtures/             — Clearly labelled SYNTHETIC test fixtures only
```

## Configuration

All configuration uses environment variables. Copy `.env.example` to `.env` for local development (`.env` is gitignored).

| Variable | Default | Description |
|----------|---------|-------------|
| `RAILCONFIRM_MODEL_DIR` | `./models` | Directory for model artifact files |
| `RAILCONFIRM_DATA_DIR` | `./data` | Directory for approved local datasets |
| `RAILCONFIRM_LOG_LEVEL` | `INFO` | Logging level |
| `RAILCONFIRM_CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |

**Never commit secrets, API keys, or PNR data.** The application works without any credentials.

## Status mapping

Status codes are parsed by `railconfirm.domain.status.parse_status()` using mapping version `1.0.0`.

Known codes: `CNF`, `RAC`, `RAC/N`, `GNWL/N`, `RLWL/N`, `PQWL/N`, `TQWL/N`, `RQWL/N`, `DPWL/N`, `WL/N`, `CAN`, `CANCELLED`, `CENSORED`.

Unknown codes are returned as `UNKNOWN` — never silently mapped to WL. Add new codes only after authoritative verification.

## Data pipeline

See `docs/data/DATASET_INTAKE_CHECKLIST.md` for the full intake process. Raw data files must not be committed to the repository.

```bash
# Validate a local dataset file (once one is approved)
python -m railconfirm.data.validator path/to/dataset.csv

# Generate dataset manifest
python -m railconfirm.data.manifest path/to/dataset.csv --output data/manifests/
```

## Limitations

- No trained prediction model is currently available. All inference requests return structured abstention.
- No approved historical dataset has yet passed the intake checklist.
- Group outcome estimates use an independence baseline (clearly labelled) as a placeholder until joint-model training is possible.
- This local-first implementation has no third-party runtime API dependencies (ADR-0007).

See `docs/PROJECT_STATUS.md` for the current implementation status.

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

Returns API health and the configured version identifiers. `model_available` is
not reported: the registry resolves promotion state per request, and
`model_version` equal to `no_model_v0` is the unavailable state.

```json
{
  "status": "ok",
  "model_version": "no_model_v0",
  "data_version": "none",
  "app_version": "0.1.0"
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
      artifacts.py        — JSON model artifact format and validation
      baseline.py         — Historical frequency baseline (requires approved provenance)
      group.py            — Group outcome computation
      registry.py         — Model artifact resolution and promotion gate
    data/
      loader.py           — CSV/JSON local dataset loader
      validator.py        — Dataset schema validation
      manifest.py         — Dataset manifest handling
      preprocessing.py    — As-of-time feature construction and chronological splits
  tests/
    domain/               — Status, journey, passenger, prediction tests
    inference/            — Baseline, group, registry and engine tests
    api/                  — Prediction and health endpoint tests
    data/                 — Loader, validator and preprocessing tests
    support/              — Shared synthetic artifact fixtures
    fixtures/             — Clearly labelled SYNTHETIC test fixtures only
```

## Configuration

All configuration uses environment variables with the `RAILCONFIRM_` prefix. Copy `.env.example` (repository root) to `.env` for local development; `.env` is gitignored. Every variable is optional — the defaults keep the application local-first and abstaining.

| Variable | Default | Description |
|----------|---------|-------------|
| `RAILCONFIRM_HOST` | `127.0.0.1` | Uvicorn bind address for the development server |
| `RAILCONFIRM_PORT` | `8000` | Uvicorn bind port |
| `RAILCONFIRM_DEBUG` | `false` | Debug flag |
| `RAILCONFIRM_DATA_DIR` | `data/processed` | Git-ignored directory for approved local datasets |
| `RAILCONFIRM_MODELS_DIR` | `models` | Directory holding `models/<version>.json` artifacts |
| `RAILCONFIRM_ACTIVE_MODEL_VERSION` | `no_model_v0` | The one promoted artifact version; `no_model_v0` serves nothing |
| `RAILCONFIRM_MIN_SAMPLE_THRESHOLD` | `30` | Smallest cohort the baseline will report an estimate for |
| `RAILCONFIRM_MAX_ARTIFACT_BYTES` | `4194304` | Largest artifact the registry will read |
| `RAILCONFIRM_DATA_VERSION` | `none` | Dataset version reported by `/v1/health` |

Relative paths are resolved against the repository root, not the current working directory, so the same artifact is loaded whichever way the server is started.

**Never commit secrets, API keys, or PNR data.** The application works without any credentials.

## Model artifacts

The registry serves exactly one artifact: `models/<RAILCONFIRM_ACTIVE_MODEL_VERSION>.json`. Loading is restricted to JSON — no pickle, no object reconstruction — and the artifact must declare a format identifier, its target, its feature-schema and status-mapping versions, the outcome class order, the dataset id and SHA-256, an explicit approval status and a promotion value of `approved_for_local_use`.

A file appearing in `models/` does not activate it. Resolution reports which gate is closed:

| Status | Meaning | Abstention reason |
|---|---|---|
| `no_active_version` | Nothing is promoted | `no_trained_model` |
| `artifact_missing` | Configured version has no file | `no_trained_model` |
| `artifact_invalid` | File exists but failed validation | `model_artifact_invalid` |
| `not_promoted` | Metadata does not declare approval for use | `no_trained_model` |
| `data_not_approved` | Fitted from unapproved or synthetic data | `no_approved_data` |
| `ready` | Serves estimates for the requested target | — |

## Status mapping

Status codes are parsed by `railconfirm.domain.status.parse_status()` using mapping version `1.1.0`, and the version is stamped on every parsed record.

Known codes: `CNF`, `RAC`, `RAC/N`, `GNWL/N`, `RLWL/N`, `PQWL/N`, `TQWL/N`, `RQWL/N`, `DPWL/N`, `WL/N`, `CAN`, `CANCELLED`, `CENSORED`.

`CK` and `CKWL` resolve to `UNKNOWN`. Mapping 1.0.0 mapped them to the waitlist category on an unverified guess; see `docs/model/STATUS_GLOSSARY.md`.

Unknown codes are never silently mapped to WL. Add a code only after authoritative verification, with a recorded source, examples, tests, and a mapping version bump.

## Data pipeline

See `docs/data/DATASET_INTAKE_CHECKLIST.md` for the full intake process. Raw data files must not be committed to the repository.

```bash
# from backend/, validate a local candidate dataset file
python -m railconfirm.data.validator path/to/dataset.csv   # exits non-zero when unusable

# generate a provenance manifest (path is positional, omit to print to stdout)
python -m railconfirm.data.manifest path/to/dataset.csv path/to/manifest.yaml
```

## Limitations

- No trained prediction model is currently available. All inference requests return structured abstention.
- No approved historical dataset has yet passed the intake checklist.
- Group outcome estimates use an independence baseline (clearly labelled) as a placeholder until joint-model training is possible.
- This local-first implementation has no third-party runtime API dependencies (ADR-0007).

See `docs/PROJECT_STATUS.md` for the current implementation status.

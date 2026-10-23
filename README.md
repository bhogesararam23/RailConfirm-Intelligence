# RailConfirm Intelligence

An evidence-driven Indian Railways ticket confirmation probability predictor for waitlisted (WL) and Reservation Against Cancellation (RAC) tickets, with passenger-wise forecasts, group-level outcome analysis, historical trend modelling, and a planned path to authorized live ticket/status data and verified current/upcoming operational context.

RailConfirm is developed as both an open research project and a web application. The goal is not to produce a percentage that looks arbitrarily precise; the goal is to estimate meaningful probabilities, evaluate them against real outcomes, and be transparent about where the model does and does not have sufficient evidence.

> **Current status:** A local-first application core exists and is tested — FastAPI backend, Next.js frontend, domain contracts, dataset intake pipeline and a validated model registry (384 backend tests, 96% branch coverage, CI green). **No prediction is produced yet and nothing has been validated against real railway data,** because no candidate dataset has cleared the intake checklist and no artifact is promoted. The system therefore returns a structured abstention (`no_trained_model`, `registry_status: no_active_version`) to every request, which is the intended behaviour rather than a placeholder. The frontend's types were written against an imagined response shape and are the main known gap; see `docs/PROJECT_STATUS.md`. External live data integrations remain planned core capabilities in roadmap Phases 8–10 (ADR-0008).

## Quickstart (Local Development)

### Prerequisites

- **Python 3.11+**
- **Node.js 20+** and **npm**

### 1. Run the Python Backend

```bash
cd backend

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate       # On Linux/macOS
# or: .\.venv\Scripts\Activate.ps1   # On Windows

pip install -e ".[dev]"

# Test suite (384 tests, no live API dependencies) with coverage floor
pytest tests/ --cov=railconfirm --cov-fail-under=90

# Lint and type-check, both configured in pyproject.toml
ruff check railconfirm/ tests/
mypy

# Start the API server
uvicorn railconfirm.api.app:app --host 127.0.0.1 --port 8000
```

The API runs at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is at
`http://127.0.0.1:8000/docs`.

### 2. Run the Next.js Frontend

```bash
cd frontend

npm ci
npm run type-check
npm run lint
npm run dev
```

The frontend is served on `http://localhost:3000` by default, which the backend's CORS
allowlist permits. Port 3000 is a local Grafana on the maintainer's machine, so if you
move the dev server, list the new origin in `RAILCONFIRM_CORS_ALLOWED_ORIGINS` —
requests from an unlisted origin are blocked at preflight and the UI reports it as an
unreachable backend.

### 3. Dataset intake tooling

```bash
cd backend
python -m railconfirm.data validate path/to/dataset.csv     # exit 1 when not eligible
python -m railconfirm.data manifest path/to/dataset.csv \
  --dataset-id my-set --title "My set" --retrieved-on 2026-10-18
python -m railconfirm.data verify ../data/manifests/my-set.yaml path/to/dataset.csv
cd ..
python scripts/check_repository_hygiene.py                  # docs links, secrets, PNR-shaped data
```

## Core Features Implemented

- **Domain Model & Normalization (`backend/railconfirm/domain/`):**
  - Indian Railways status mapping (`v1.1.0`) distinguishing CNF, RAC, and specific waitlist categories (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL).
  - Unrecognized codes are normalized to `UNKNOWN` and never silently coerced into WL. `CK` and `CKWL` are deliberately unmapped pending verification.
  - Offset-aware timestamps required: a naive `prediction_at`, a prediction at or after the journey date, or evidence newer than the prediction timestamp is refused.
  - Privacy by design: no passenger names or raw PNRs stored or required.
- **Prediction Engine & Group Baselines (`backend/railconfirm/inference/`):**
  - Abstention-first engine with reason codes that name the closed gate (`no_trained_model`, `model_artifact_invalid`, `no_approved_data`, `unknown_status`, `unsupported_status`, `insufficient_sample`).
  - Historical frequency baseline with Laplace smoothing, validated cohort tables and required provenance. It is not wired to any real dataset.
  - Multi-passenger group outcomes computed under an explicitly labelled independence assumption — a baseline, not a validated dependence model.
- **Model Registry (`backend/railconfirm/inference/registry.py`):** JSON artifacts with metadata validation and two-gate promotion; a file appearing in `models/` activates nothing (ADR-0009).
- **Local Dataset Intake Pipeline (`backend/railconfirm/data/`):**
  - Loader with explicit CSV/JSON structure checks and a size bound.
  - Validator separating structural validity, technical eligibility and approval, with per-reason row accounting.
  - Deterministic SHA-256 manifests that follow `DATASET_MANIFEST_TEMPLATE.yaml`, plus verification that re-hashes and recounts the dataset.
  - Chronological splitting that reports an inability to evaluate rather than returning an empty test set.
- **Web Interface (`frontend/`):** journey details, dynamic passenger rows (1–6), textual status indicators, evidence disclaimers. **Not yet matched to the API contract** — see the status note above.

## Principles

1. **Evidence before percentages.** Every displayed probability must be traceable to a model version, prediction timestamp, and documented input data.
2. **No invented data.** Synthetic examples may be used for tests and UI development, but must never be presented as real railway history or model performance.
3. **No leakage.** A historical prediction may use only information that would have been available at that prediction time.
4. **Evaluate probabilities, not just labels.** Calibration and proper scoring rules matter.
5. **Broad goals, honest coverage.** The long-term goal includes multiple WL/RAC categories, but support is enabled only when data quality and evaluation justify it.
6. **Authorized access.** Do not bypass access controls or assume that a publicly reachable endpoint permits bulk collection, storage, or model training.
7. **Privacy by design.** Avoid collecting passenger names and other unnecessary personal data. Protect PNRs and define retention before enabling tracking.
8. **Explain limits.** RailConfirm is an estimate, not an official railway decision or a guarantee of a final reservation outcome.

## Current Roadmap

The current build is local-first: no third-party runtime APIs, live PNR lookup, automated polling, or live news/event feeds are implemented now. These are planned core capabilities of the target product in roadmap Phases 8–10, after the local data/model foundations. Research agents may help identify and prepare datasets, but each dataset must pass provenance, licence, privacy, label-quality and leakage checks before training.

See the [detailed roadmap](docs/ROADMAP.md), [dataset intake checklist](docs/data/DATASET_INTAKE_CHECKLIST.md), [dataset manifest template](docs/data/DATASET_MANIFEST_TEMPLATE.yaml), and [local-first development rules](docs/technical/LOCAL_FIRST_DEVELOPMENT.md).

## Documentation

Start with the [documentation map](docs/README.md) for the recommended reading order. The [roadmap](docs/ROADMAP.md) is the canonical execution plan.

**Product:** [Product brief](docs/product/PRODUCT_BRIEF.md) · [Requirements](docs/product/PRODUCT_REQUIREMENTS.md) · [User journeys](docs/product/USER_JOURNEYS.md) · [MVP acceptance criteria](docs/product/MVP_ACCEPTANCE.md)

**Technical:** [System design](docs/technical/SYSTEM_DESIGN.md) · [Domain model](docs/technical/DOMAIN_MODEL.md) · [Storage model](docs/technical/STORAGE_MODEL.md) · [Inference and group probabilities](docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md) · [Ingestion and tracking](docs/technical/INGESTION_AND_TRACKING.md)

**Build and operations:** [Roadmap](docs/ROADMAP.md) · [Agent handoff](docs/AGENT_HANDOFF.md) · [Implementation plan](docs/technical/IMPLEMENTATION_PLAN.md) · [Local-first development](docs/technical/LOCAL_FIRST_DEVELOPMENT.md) · [Testing strategy](docs/technical/TESTING_STRATEGY.md) · [Frontend guide](docs/technical/FRONTEND_GUIDE.md) · [Observability](docs/technical/OBSERVABILITY.md) · [Deployment runbook](docs/technical/DEPLOYMENT_RUNBOOK.md)

**Research and governance:** [Project status](docs/PROJECT_STATUS.md) · [Research plan](docs/research/RESEARCH_PLAN.md) · [Data acquisition](docs/data/DATA_ACQUISITION.md) · [Data contract](docs/data/DATA_CONTRACT.md) · [Prediction targets](docs/model/PREDICTION_TARGETS.md) · [Evaluation protocol](docs/research/EVALUATION_PROTOCOL.md) · [Security and privacy](docs/SECURITY_AND_PRIVACY.md) · [Architecture Decision Records](docs/adr/README.md)

The current no-third-party-runtime-API boundary is recorded in [ADR-0007](docs/adr/ADR-0007-local-first-no-external-runtime-apis.md). [ADR-0008](docs/adr/ADR-0008-live-data-integrations-as-long-term-core-capability.md) records that authorized live status and verified context integrations remain part of the long-term product goal.

Also see [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), [development log](docs/DEVELOPMENT_LOG.md), and [third-party data policy](THIRD_PARTY_DATA.md).

## License

Software and documentation in this repository are licensed under the Apache License 2.0 unless a file or directory says otherwise. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Disclaimer

RailConfirm Intelligence is an independent research and software project. It is not an official Indian Railways or IRCTC service and should not be represented as affiliated with, endorsed by, or operated by either. Final reservation status is determined by the relevant railway systems and applicable rules. Do not make travel or financial decisions solely on an unvalidated prediction.

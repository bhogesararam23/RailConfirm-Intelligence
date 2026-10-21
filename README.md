# RailConfirm Intelligence

An evidence-driven Indian Railways ticket confirmation probability predictor for waitlisted (WL) and Reservation Against Cancellation (RAC) tickets, with passenger-wise forecasts, group-level outcome analysis, historical trend modelling, and a planned path to authorized live ticket/status data and verified current/upcoming operational context.

RailConfirm is developed as both an open research project and a web application. The goal is not to produce a percentage that looks arbitrarily precise; the goal is to estimate meaningful probabilities, evaluate them against real outcomes, and be transparent about where the model does and does not have sufficient evidence.

> **Current status (Phases 1–5 local-first release):** Core application stack, API contracts, domain validation, dataset intake pipeline, and Next.js user interface are implemented and verified. The system intentionally operates in abstention mode (`no_trained_model`) until a candidate historical dataset passes the intake checklist. External live data integrations remain planned core capabilities of the long-term product in roadmap Phases 8–10 (ADR-0008).

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

# Run test suite (40 tests, all passing without live API dependencies)
pytest tests/ -v

# Start the API server
uvicorn railconfirm.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Run the Next.js Frontend

```bash
cd frontend

# Install dependencies
npm install

# Type-check and production build
npm run type-check
npm run build

# Start development server
npm run dev
```

Open `http://localhost:3000` to interact with the local application.

## Core Features Implemented

- **Domain Model & Normalization (`backend/railconfirm/domain/`):**
  - Indian Railways status mapping (`v1.0.0`) distinguishing CNF, RAC, and specific waitlist categories (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL).
  - Unrecognized codes are normalized to `UNKNOWN` and never silently coerced into WL.
  - Strict journey validation (4–6 digit train numbers, distinct origin/destination).
  - Privacy by design: no passenger names or raw PNRs stored or required.
- **Prediction Engine & Group Baselines (`backend/railconfirm/inference/`):**
  - Abstention-first engine returning explicit reason codes (`no_trained_model`, `unknown_status`, `insufficient_sample`).
  - Historical frequency baseline with Laplace smoothing.
  - Multi-passenger group joint outcome estimation with explicit assumption warnings.
- **Local Dataset Intake Pipeline (`backend/railconfirm/data/`):**
  - Loader and schema validator enforcing `docs/data/DATASET_INTAKE_CHECKLIST.md`.
  - Cryptographic SHA-256 dataset manifest generator.
  - Chronological dataset partitioner preventing temporal data leakage.
- **Modern Local-First Web Interface (`frontend/`):**
  - Journey details and dynamic passenger rows (1–6 passengers).
  - Clear separation between original booking status and latest observed status.
  - Accessible, textual status indicators and evidence disclaimers.

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

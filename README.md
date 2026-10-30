# RailConfirm Intelligence

An evidence-driven Indian Railways ticket confirmation probability predictor for waitlisted (WL) and Reservation Against Cancellation (RAC) tickets, with passenger-wise forecasts, group-level outcome analysis, historical trend modelling, and a planned path to authorized live ticket/status data and verified current/upcoming operational context.

RailConfirm is developed as both an open research project and a web application. The goal is not to produce a percentage that looks arbitrarily precise; the goal is to estimate meaningful probabilities, evaluate them against real outcomes, and be transparent about where the model does and does not have sufficient evidence.

> **Current status:** A local-first application core exists and is tested — FastAPI backend, Next.js frontend, domain contracts, a dataset intake pipeline whose training gate enforces **technical eligibility** and passes on only validated rows, reproducible baseline fitting with target-event scoring, **rolling-origin evaluation** and **frozen-artifact decay** across successive horizons, dependent group outcome distributions with queue-clearing bounds, an opt-in logistic **calibration** layer measured on a locked test, **two estimators** — the cohort frequency table and a cohort model that also reads the as-of queue position — a **paired model comparison** that decides between them only on the locked period, a validated model registry, and opt-in prediction history (1043 backend tests, 96.2% branch coverage, CI green). **No prediction is produced yet and nothing has been validated against real railway data,** because no candidate dataset has cleared the intake checklist and no artifact is promoted. The system therefore returns a structured abstention (`no_trained_model`, `registry_status: no_active_version`) to every request, which is the intended behaviour rather than a placeholder. The frontend is written against the shipped contract, with 115 tests, and CI starts both processes for real — a production frontend build against a running backend, over sockets — as a fourth job that also drives the client's own request-building module against the live server (ADR-0027); see `docs/PROJECT_STATUS.md`. External live data integrations remain planned core capabilities in roadmap Phases 8–10 (ADR-0008).

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

# Test suite (1043 tests, no live API dependencies) with coverage floor
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
npm test                        # 115 tests, no backend needed; the live cross-stack suite has its own command (section 4)
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

### 4. Full-stack check

CI runs this on every push, and it is the only check that starts both halves of the
product (ADR-0027). Build the frontend against the backend origin it will start, then
run the script from the repository root:

```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010 npm run build
cd ..
python scripts/smoke_full_stack.py                # backend + frontend + client suite
python scripts/smoke_full_stack.py --skip-frontend # backend + client suite only
```

It starts the API on `127.0.0.1:8010` with prediction history enabled, checks health,
an abstention, a field-level refusal, the same-day horizon refusal, the store / reopen /
list / delete round trip, a PNR-shaped id, an unrouted path and the CORS preflight, then
starts the production build on `127.0.0.1:3010` and fetches its pages. It also asserts
that the built bundle names the backend it just started, and runs
`npm run test:live` — the client's own `src/lib/api.ts` against that server.

What it does not do: no browser runs, so the pages are checked for content only and a
JavaScript-only failure would still pass; and with no promoted artifact every prediction
must abstain, so this says nothing about railway accuracy.

### 5. Fitting and evaluation

```bash
cd backend
python -m railconfirm.training fit data/processed/dataset.csv data/manifests/set.yaml \
  --version baseline_v1 --out ../models/baseline_v1.json \
  --report ../reports/baseline_v1.json --generated-on 2026-10-23
python -m railconfirm.training fit data/processed/dataset.csv data/manifests/set.yaml \
  --version baseline_v2 --out ../models/baseline_v2.json \
  --report ../reports/baseline_v2.json --generated-on 2026-10-23 --calibrate
python -m railconfirm.training evaluate data/processed/dataset.csv data/manifests/set.yaml \
  --artifact ../models/baseline_v1.json --target final_chart_cnf
python -m railconfirm.training origins data/processed/dataset.csv data/manifests/set.yaml \
  --report ../reports/origins.json --generated-on 2026-10-23  # refit per cutoff, score the horizon after it
python -m railconfirm.training decay data/processed/dataset.csv data/manifests/set.yaml \
  --artifact ../models/baseline_v1.json --horizon-dates 2 --step-dates 2 \
  --report ../reports/decay.json --generated-on 2026-10-23  # one frozen table, judged further out
python -m railconfirm.training compare data/processed/dataset.csv data/manifests/set.yaml \
  --version v3 --candidate-estimator cohort_position_baseline \
  --report ../reports/compare.json --generated-on 2026-10-23  # which model may replace which
cd ..
```

Fitting reads only datasets whose manifest verifies against the file and whose approval
record permits model training, and it always writes a `candidate` artifact — serving still
needs an explicit promotion (ADR-0009, ADR-0011). Reports are byte-reproducible and score
the target's own event as well as the full outcome distribution. `--calibrate` fits a
logistic correction on the validation partition only, embeds it only when it strictly
improves validation event Brier, and reports the locked-test effect whichever way it goes
(ADR-0017). `decay` takes one artifact and scores it on each successive horizon after its own
declared cutoff — refitting nothing, moving the baseline nowhere — which is the question a
promoted model faces in service, as opposed to `origins`, which refits per cutoff and measures
the fitting procedure (ADR-0018). No dataset in this repository is approved, so no fit has
ever run on real data.

## Core Features Implemented

- **Domain Model & Normalization (`backend/railconfirm/domain/`):**
  - Indian Railways status mapping (`v1.1.0`) distinguishing CNF, RAC, and specific waitlist categories (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL).
  - Unrecognized codes are normalized to `UNKNOWN` and never silently coerced into WL. `CK` and `CKWL` are deliberately unmapped pending verification.
  - Offset-aware timestamps required: a naive `prediction_at`, a prediction at or after the journey date, or evidence newer than the prediction timestamp is refused.
  - Privacy by design: no passenger names or raw PNRs stored or required.
- **Prediction Engine & Group Baselines (`backend/railconfirm/inference/`):**
  - Abstention-first engine with reason codes that name the closed gate (`no_trained_model`, `model_artifact_invalid`, `no_approved_data`, `unknown_status`, `unsupported_status`, `insufficient_sample`).
  - Historical frequency baseline with Laplace smoothing, validated cohort tables keyed by `(class, quota, as-of status)` and required provenance. It is not wired to any real dataset.
  - A second estimator that splits each cohort by the as-of queue position in fixed doubling bands (1, 2-3, 4-7, …, 128+), answers from the band only when it has enough rows, and says in `basis` which cell answered or why the cohort did instead (ADR-0020). An unknown position stays unknown rather than being banded as first in the queue.
  - Multi-passenger group outcomes reported as two honest extremes rather than one implied number: a Poisson-binomial distribution over how many confirm (independent members) and comonotonic queue-clearing bounds (perfectly dependent members). Group-event Brier scores are in the evaluation report. Neither is validated on real multi-passenger data, and independence is never silently multiplied into a claim (ADR-0016).
  - Optional logistic calibration layer applied to the target event's log-odds before a probability is served, using the same function the evaluator scores with, so the measured number and the served number come from one arithmetic path (ADR-0017).
- **Model comparison (`python -m railconfirm.training compare`, ADR-0021):** the baseline and a candidate are fitted on **one split**, scored against **one** prevalence baseline, and paired row by row; the verdict reads the **locked period only** and requires the distribution score, the target-event score, the paired win count and coverage all to favour the candidate. A candidate that wins the window it was chosen in and loses the locked one is reported as losing. Promoting stays a human act — this prints the numbers a promotion would rest on.
- **Model Registry (`backend/railconfirm/inference/registry.py`):** JSON artifacts (`/2`) with metadata validation and two-gate promotion; a file appearing in `models/` activates nothing, and an artifact whose declared cohort-status rule or consumed-feature list differs from what this build serves — or whose `calibrated` flag and calibration block disagree — is refused at load (ADR-0009, ADR-0013, ADR-0017). Two artifact formats exist now, one per estimator, and the loader refuses a file whose format, estimator, `features_used` and band block do not all agree (ADR-0020).
- **Training and Evaluation (`backend/railconfirm/training/`, ADR-0011, ADR-0013, ADR-0014, ADR-0017, ADR-0018):** a dataset gate that enforces technical eligibility and passes on only the rows validation kept, cohort fitting on the training partition keyed by the single as-of status rule that scoring and serving also use, multiclass Brier/log loss plus the target event's own score against a prevalence baseline drawn from each run's own training period, abstention and low-sample accounting, **rolling-origin evaluation that refits at every cutoff**, **frozen-artifact decay that keeps one table fixed and judges each later horizon against it**, both refusing when the calendar cannot support two windows, an opt-in logistic calibration layer that is fitted on validation, embedded only when it strictly improves validation event Brier, and reported on the locked test either way, **subgroup calibration published per class, quota and status as observed-minus-predicted with its row count and a floor on what may be claimed from it (ADR-0019)** — no per-segment correction is fitted — and deterministic JSON reports that define every number they publish and state which features the estimator actually reads. Tested on synthetic fixtures; never run on approved real data, because none exists.
- **Local Dataset Intake Pipeline (`backend/railconfirm/data/`):**
  - Loader with explicit CSV/JSON structure checks and a size bound.
  - Validator separating structural validity, technical eligibility and approval, with per-reason row accounting.
  - Deterministic SHA-256 manifests that follow `DATASET_MANIFEST_TEMPLATE.yaml`, plus verification that re-hashes and recounts the dataset.
  - Chronological splitting that reports an inability to evaluate rather than returning an empty test set.
- **Web Interface (`frontend/`):** journey and target entry, dynamic passenger rows (1–6), observed and estimated status shown separately, null-safe probability rendering with all five outcome classes, evidence cohort and sample size, per-reason abstention text, provenance block, skip link and labelled controls. `/prediction/[id]` reopens a report the user chose to keep, as it was served.
- **Prediction history (`backend/railconfirm/storage/`, ADR-0012):** off by default and opt-in per request. When both switches are on, the served report is kept in one local SQLite file with a retention window, and reopening it returns the numbers and model version it was produced with. The write refuses a payload carrying a passenger-name key or a PNR-shaped value.

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

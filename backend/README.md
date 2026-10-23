# RailConfirm Intelligence — Backend

Python backend implementing the domain model, prediction API, and local data pipeline.

**Status:** Roadmap Phases 0–7 local-first core: domain contracts, dataset intake with an eligibility-enforced training gate, reproducible baseline fitting and temporal evaluation (single-split and rolling-origin), dependent group outcome distributions, optional logistic calibration, opt-in prediction history and a gated model registry. **No trained model is currently available to serve,** because no candidate dataset has cleared the intake checklist and nothing has been fitted on real railway data; the inference engine therefore returns structured abstention responses for all requests. This is expected behavior, not a placeholder.

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

Timestamps must carry a UTC offset, and an observation cannot be dated in the
future: the example below predicts a November journey as of a past October
timestamp so it can be pasted and still work.

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
  "prediction_at": "2026-10-21T08:00:00Z",
  "passengers": [
    {
      "original_status": "GNWL/45",
      "current_status": "GNWL/12",
      "current_status_observed_at": "2026-10-21T07:30:00Z"
    }
  ]
}
```

**Response (nothing promoted — the current state):**
```json
{
  "prediction_id": "…",
  "target": "final_chart_cnf",
  "target_definition": "Probability of each final-chart outcome for each passenger …",
  "prediction_at": "2026-10-21T08:00:00Z",
  "created_at": "2026-10-23T04:10:22.119289Z",
  "model_version": "no_model_v0",
  "registry_status": "no_active_version",
  "feature_schema_version": "1.0.0",
  "evidence_coverage": "insufficient",
  "is_supported": false,
  "passenger_count": 1,
  "passenger_outcomes": [
    {
      "passenger_id": "…",
      "original_status": "GNWL/45",
      "original_status_normalized": "WL",
      "current_status": "GNWL/12",
      "current_status_normalized": "WL",
      "p_cnf": null,
      "p_rac": null,
      "p_wl": null,
      "p_cancelled": null,
      "p_other": null,
      "is_supported": false,
      "abstention_reason": "no_trained_model",
      "basis": null,
      "parse_warnings": []
    }
  ],
  "group_outcome": {
    "p_all_cnf": null,
    "p_all_cnf_or_rac": null,
    "p_at_least_one_wl": null,
    "method": "insufficient_data",
    "assumptions": "Group outcome is unavailable because at least one passenger outcome is an abstention.",
    "is_supported": false,
    "abstention_reason": "no_trained_model"
  },
  "limitations": [
    "RailConfirm is an independent research tool and not an official IRCTC service.",
    "No promoted model artifact is active for this target. Registry state: no_active_version — No model version is configured as active; the registry serves no artifact."
  ],
  "warnings": [],
  "outcome_classes": "CNF, RAC, WL, CANCELLED, OTHER — mutually exclusive and exhaustive over the eligible population. Probabilities sum to 1.0 per passenger."
}
```

The full field list, request constraints and error envelope are in `docs/architecture/API_CONTRACT.md`.

### `GET /v1/predictions/{prediction_id}`

Reopens a report the server kept (ADR-0012). Storage needs both
`RAILCONFIRM_PERSIST_PREDICTIONS=true` and `"persist": true` on the original request; the
response's `stored` field says what actually happened. Nothing is recomputed on reopen, so
the numbers arrive with the `model_version`, `registry_status` and limitations they were
served with.

| Result | When |
|---|---|
| `200` | A stored report exists for the id and is inside its retention window |
| `404 not_found` | No such id, or it aged out |
| `404 history_disabled` | This server keeps no history |

An id shaped like a PNR is answered with `not_found` and a message saying reports are
reopened by the id the server returned. This endpoint does not look tickets up.

### `GET /v1/health`

Returns API health, the configured version identifiers, whether a validated and
promoted artifact could serve a prediction, the limits in force, and whether this server
keeps prediction history.

```json
{
  "status": "ok",
  "model_version": "no_model_v0",
  "data_version": "none",
  "app_version": "0.1.0",
  "model_available": false,
  "registry_status": "no_active_version",
  "limits": {
    "max_passengers_per_request": 6,
    "min_sample_threshold": 30,
    "max_artifact_bytes": 4194304,
    "max_request_bytes": 65536
  }
}
```

## Project structure

```
backend/
  pyproject.toml          — Package config and dependencies
  railconfirm/
    config.py             — Environment-variable configuration
    domain/
      status.py           — Status normalization (versioned mapping v1.1.0)
      journey.py          — Journey, class, and quota domain types
      passenger.py        — Passenger reservation and observation types
      prediction.py       — Prediction output, abstention, group semantics
      validation.py       — Shared validators and reason codes
      exceptions.py       — Domain exception hierarchy
    api/
      app.py              — FastAPI application factory
      problems.py         — Endpoint-level problems carried into the error envelope
      v1/
        predictions.py    — POST /v1/predictions/manual, GET /v1/predictions/{id}
        health.py         — GET /v1/health
        schemas.py        — Request/response Pydantic models
    storage/
      predictions.py      — Opt-in SQLite history: retention, denied-key refusal, list, delete
    inference/
      engine.py           — Abstention-first dispatch
      artifacts.py        — JSON model artifact format and validation
      baseline.py         — Historical frequency baseline (requires approved provenance)
      calibration.py      — Logistic correction applied identically in scoring and serving
      group.py            — Poisson-binomial group distribution and queue-clearing bounds
      registry.py         — Model artifact resolution and promotion gate
    data/
      loader.py           — CSV/JSON local dataset loader
      validator.py        — Structural validity, eligibility and row filtering
      manifest.py         — Dataset manifest handling
      preprocessing.py    — As-of-time feature construction, chronological splits, origin windows
    training/
      dataset.py          — The gate: manifest-verified, approved, eligible, kept rows only
      fitter.py           — Cohort fitting keyed by the as-of status
      metrics.py          — Distribution and target-event scoring, group-event card
      calibration.py      — Platt slope/intercept fitting with refusal conditions
      origins.py          — Rolling-origin refit and per-cutoff scoring
      decay.py            — One frozen artifact scored on each successive horizon
      report.py           — Byte-reproducible JSON evaluation reports
      __main__.py         — `fit`, `evaluate`, `origins` and `decay` commands
  tests/
    domain/               — Status, journey, passenger, prediction tests
    inference/            — Baseline, group, calibration, registry and engine tests
    api/                  — Prediction, health and history endpoint tests
    data/                 — Loader, validator, preprocessing, rolling-origin and decay-window tests
    storage/              — Opt-in history tests
    training/             — Gate, fitter, metrics, calibration, cohort-parity, decay and report tests
    support/              — Shared synthetic artifact and dataset fixtures
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
| `RAILCONFIRM_STORAGE_DIR` | `data/storage` | Git-ignored directory for the opt-in history file |
| `RAILCONFIRM_PERSIST_PREDICTIONS` | `false` | Whether this server keeps reports at all; a request still has to ask |
| `RAILCONFIRM_PREDICTION_RETENTION_DAYS` | `30` | How long a kept report stays retrievable; minimum 1 |

Relative paths are resolved against the repository root, not the current working directory, so the same artifact is loaded whichever way the server is started.

**Never commit secrets, API keys, or PNR data.** The application works without any credentials.

## Model artifacts

The registry serves exactly one artifact: `models/<RAILCONFIRM_ACTIVE_MODEL_VERSION>.json`. Loading is restricted to JSON — no pickle, no object reconstruction — and the artifact must declare a format identifier, its target, its feature-schema and status-mapping versions, the outcome class order, the dataset id and SHA-256, an explicit approval status and a promotion value of `approved_for_local_use`. It must also declare which status rule its cohorts are keyed by (`cohort_semantics`, `asof_status_v1`) and which features the estimator actually reads (`features_used`); an artifact that declares either differently is refused at load rather than served under a mistaken assumption. A `calibrated: true` artifact must carry the calibration block that justifies the claim, and a block without the claim is refused too — half a fitted layer is not a layer (ADR-0017).

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

See `docs/data/DATASET_INTAKE_CHECKLIST.md` for the full intake process and
`docs/data/DATA_CONTRACT.md` for the row contract. Raw data files must not be
committed to the repository; manifests under `data/manifests/` may be.

```bash
# from backend/ — validate a candidate dataset file
python -m railconfirm.data validate path/to/dataset.csv
python -m railconfirm.data validate --json path/to/dataset.csv   # machine-readable report

# generate a provenance manifest (retrieved_on is required: a manifest must not be
# dated by the clock, or two runs cannot be compared)
python -m railconfirm.data manifest path/to/dataset.csv \
  --dataset-id my-set --title "My candidate set" --retrieved-on 2026-10-18

# verify a manifest, optionally re-checking the dataset file it describes
python -m railconfirm.data verify data/manifests/my-set.yaml path/to/dataset.csv
```

Exit codes: `0` success, `1` a check failed or the input is unusable, `2` usage error.
`validate` exits `1` when a file is **not technically eligible** — that is not the
same as being disapproved, and no exit code can approve a dataset.

The three verdicts a report gives are distinct: `structurally valid` (schema
complete, at least one interpretable row), `technically eligible` (clears the
documented intake minimums), and approval, which this tool never determines.
`assess_dataset()` returns the report **and** the frame restricted to rows that passed
every row-level check; `validate_dataset()` is the report-only wrapper. Training reads
the file through that filter, so a duplicate, contradiction, censored label or
impossible date cannot reach a cohort count (ADR-0013).

Manifest YAML follows `docs/data/DATASET_MANIFEST_TEMPLATE.yaml`, and a test
asserts every template section and key is present in generated output. Writing a
manifest that claims `status: approved` without a named reviewer, a date and a
rationale is rejected by the model, as is `licence_review_status: approved` while
`allowed_uses.model_training` is still `unknown`.

## Training and evaluation

`python -m railconfirm.training` fits the historical-frequency baseline and scores it on
a later period (ADR-0011, ADR-0013). It reads a dataset only through the gate: the
manifest must verify against the file, a named reviewer must have recorded an `approved`
decision, the licence review must permit `model_training`, rows that declare
`is_synthetic` are refused, and the file must be **technically eligible** — structural
validity alone is not enough. Only the rows validation kept are passed on.

```bash
# from backend/ — fit a candidate artifact and write a reproducible report
python -m railconfirm.training fit data/processed/dataset.csv data/manifests/set.yaml \
  --version baseline_v1 --out models/baseline_v1.json \
  --report reports/baseline_v1.json --generated-on 2026-10-23 \
  --min-sample-threshold 30 --laplace-alpha 1.0

# score an existing artifact on held-out partitions
python -m railconfirm.training evaluate data/processed/dataset.csv data/manifests/set.yaml \
  --artifact models/baseline_v1.json --target final_chart_cnf

# refit at each cutoff and score only the horizon after it (rolling-origin, ADR-0014)
python -m railconfirm.training origins data/processed/dataset.csv data/manifests/set.yaml \
  --min-train-dates 4 --horizon-dates 2 --step-dates 2 \
  --report reports/origins.json --generated-on 2026-10-23

# score one frozen artifact on each horizon after its own fitted period (decay, ADR-0018)
python -m railconfirm.training decay data/processed/dataset.csv data/manifests/set.yaml \
  --artifact models/baseline_v1.json --horizon-dates 2 --step-dates 2 \
  --report reports/decay.json --generated-on 2026-10-23

# fit the baseline and add a logistic calibration layer measured on the locked test
python -m railconfirm.training fit data/processed/dataset.csv data/manifests/set.yaml \
  --version baseline_v2 --out models/baseline_v2.json \
  --report reports/baseline_v2.json --generated-on 2026-10-23 \
  --calibrate --calibrate-min-rows 50
```

A successful `fit` writes `promotion: "candidate"`, so nothing starts serving; activation
still needs `RAILCONFIRM_ACTIVE_MODEL_VERSION` and the artifact's own approval field
(ADR-0009). Exit codes match the data commands: `0` success, `1` refused or unusable
input, `2` usage error. A run states its intake accounting rather than resting on it
silently:

```text
Validation kept 23 of 32 rows (9 rejected: censored_label=1, contradictory_labels=2,
exact_duplicate_row=1, invalid_train_number=1, missing_required_value=1,
observation_after_journey=1, unknown_initial_status=1, unparseable_date=1).
Eligibility thresholds were NOT met; fitted only because this is a labelled synthetic pipeline test.
```

- Every partition is scored twice — as a five-class distribution and as the target's own
  event (`final_chart_cnf` is CNF; `final_chart_cnf_or_rac` is CNF or RAC) — against a
  prevalence baseline computed from the **training** period only. When the two verdicts
  disagree, the report says so instead of quoting the better one.
- Cohorts are keyed `(class_code, quota_code, asof_normalized)`, where the as-of status is
  `current_status` when the source recorded one and `initial_status` otherwise. Fitting,
  scoring and the served request use that one rule, so a table is never queried under a
  different contract than it was built with. Segments are reported for the booked status
  and the as-of status separately, because the gap between them is where a keying mistake
  would show.
- The artifact declares `features_used` (`class_code`, `quota_code`, `asof_normalized`) and
  `cohort_semantics` (`asof_status_v1`), and `load_artifact()` refuses anything that
  declares otherwise. The wider feature schema is derived for later estimators; this
  baseline does not read it, and the report says so.
- Rows the estimator abstains on are excluded from the scores and counted separately.
- `--generated-on` is required for a report: output stamped by the clock cannot be
  reproduced byte-for-byte.
- `--allow-synthetic-for-testing` exists so the pipeline can be exercised. It marks the
  artifact synthetic, which the registry refuses to serve, so a fixture can never become
  a user-visible probability. It is the only route below the intake thresholds and it
  works only when rows declare `is_synthetic` — passing the flag for a real file changes
  nothing — and the artifact carries a limitation recording the relaxation.
- Rolling-origin evaluation (`origins`) plans whole-date cutoffs, refits the cohort table
  and its prevalence baseline from each origin's own past, and refuses to run at all when
  the calendar supports fewer than two cutoffs. Conclusions are written against the
  origins that produced a score — an abstaining horizon is counted separately, not as a
  lost forecast — and the Brier and coverage ranges across origins are printed instead of
  being averaged into a single flattering number. The method is
  `refit-per-origin, score-the-next-horizon`: it measures the fitting procedure over time,
  not one frozen artifact's decay.
- Calibration (`--calibrate`, ADR-0017) is a logistic rescaling of the target event's
  log-odds — slope and intercept fitted by Newton–Raphson on the **validation** partition
  only, never on the locked test and never on the training rows the cohort counts come from.
  It needs at least `--calibrate-min-rows` (default 50) scored validation rows whose predicted
  event probability lies strictly inside `(0, 1)` and whose labels are not one class. It
  refuses rather than degrades: too few rows, a single label, one repeated predicted
  probability, a prediction outside `[0, 1]` (a scoring bug), a singular Hessian from
  perfectly separable evidence, non-convergence, or a negative slope.
- The layer is embedded in the artifact only when it **strictly reduces validation event
  Brier**. The locked test is scored both with and without it either way, and `fit` prints
  `validation event Brier X -> Y; locked test A -> B (helped / did not help)`, so a
  correction that helps in-sample and hurts out-of-sample is visible instead of buried.
- `apply_calibration` rescales the target event's mass and redistributes the remainder
  proportionally, so every distribution still sums to 1. Abstentions are returned untouched —
  there is no probability to move, and rewriting the reason a row refused would hide it. The
  evidence note gains the calibration identity, because a cohort label alone would no longer
  describe the arithmetic that produced the number.
- Reliability bands and every scorecard field are computed on the corrected probabilities, and
  each scorecard records `calibration_applied`, so a reader cannot mistake a calibrated score
  for the raw table's. Both report and artifact state that calibration was measured across the
  population, not within a cohort subgroup.
- Frozen-artifact decay (`decay`, ADR-0018) answers a different question from `origins`. The
  cutoff is the artifact's own `trained_to` — never a caller's flag, because a chosen cutoff
  lets the fitted period be scored as evidence about itself — and the cohorts, smoothing
  settings and calibration block are the artifact's, applied unchanged to every horizon.
  One prevalence baseline is computed from the fittable rows up to the cutoff and reused for
  all of them, because a baseline recomputed per horizon drifts toward the answer it is
  judging. The run refuses below two usable horizons, refuses when a booking spans the
  cutoff, counts horizons that abstained everywhere separately from horizons that lost, and
  reports first-to-last drift plus the spread rather than a mean that hides the ordering.
- Subgroup calibration (`--calibrate` or not, ADR-0019) is published on every scorecard: per
  `class_code`, `quota_code`, booked status and as-of status it reports the mean predicted event
  probability, the observed event rate, `gap = observed - predicted` and the row count. A
  population can look aligned while offsetting cohorts are not, which reliability bands cannot
  show because they pool classes. The gaps are measured on the corrected probability — the number
  a passenger was handed — and no per-segment correction is fitted, so the report calls these
  numbers the correction's residual error. Segments below the scorecard's row floor (default 25)
  are flagged `low_sample` and carry no claim in either direction; when none clears the floor the
  conclusion says subgroup calibration cannot be claimed rather than quoting a thin cohort.
- Not implemented: a per-segment calibration correction, and any number computed from approved
  real data. The reports state both limits in their own words.

## Limitations

- No trained prediction model is currently available. All inference requests return structured abstention.
- No approved historical dataset has yet passed the intake checklist.
- Group outcomes combine a Poisson-binomial distribution, which assumes passengers confirm independently of each other, with comonotonic queue-clearing bounds, which assume the opposite. Both are reported instead of one implied number, and neither has been evaluated against real multi-passenger bookings (ADR-0016).
- Calibration exists as a mechanism fitted on labelled synthetic rows; no railway probability has ever been corrected with it, and the improvement it shows on those fixtures is a check that the arithmetic runs, not a result.
- This local-first implementation has no third-party runtime API dependencies (ADR-0007).

See `docs/PROJECT_STATUS.md` for the current implementation status.

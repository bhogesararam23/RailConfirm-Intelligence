# Changelog

Notable changes to RailConfirm Intelligence are recorded here.

The format is inspired by Keep a Changelog; dates use ISO 8601.

## [Unreleased]

### Changed
- **CI checks are declared, not inherited (ADR-0010):** commit `a87afc1` passed locally and failed the CI lint job because `pyproject.toml` set no Ruff rule set — local ruff 0.16.9 enabled `DTZ001`, CI's ruff 0.17.2 did not, turning the timezone-suppression `# noqa` markers into unused-noqa failures. `[tool.ruff.lint] select` now names the rules (`E4/E7/E9/F/I/B/DTZ/C4/RUF100`), Mypy is configured in `pyproject.toml` and CI runs plain `mypy`, and dev tool ranges are constrained so a lint result is reproducible across machines. Runtime libraries stay version-bounded rather than frozen: CI demonstrating the suite passes on both pandas 2.3 and 3.1 is evidence worth keeping.
- **The repository hygiene step was structurally incapable of failing:** `grep -r "pnr" … | grep -v … | head -5` inside `if …; then` tests `head`'s status, which is 0 even on empty input, so the "secret and private data" check warned on every commit and prevented nothing. Checks moved to `scripts/check_repository_hygiene.py` (identical locally and in CI): required docs, relative Markdown links, private-key/token patterns, committed `.env` files, tracked files over 2 MB, and PNR-shaped values in files that do not declare their data synthetic. Verified to exit 1 on a deliberately broken link and 0 after restoring it.
- `.github/workflows/ci.yml` requests `permissions: contents: read`, cancels superseded runs on the same ref, and enforces `--cov-fail-under=90` with branch coverage (currently 92%).
- `ci/README.md` rewritten: it linked `ci/github-actions-ci.yml`, deleted when the workflow landed, described "strict type-checking" that was not configured, and claimed a privacy scan that could not fail. It now lists each job as it runs, including the frontend gap.

### Fixed
- **Status mapping integrity (`backend/railconfirm/domain/status.py`, mapping v1.1.0):** `CK` and `CKWL` were mapped to the waitlist category on an unverified guess. They now resolve to `UNKNOWN` with a review note, so an unverified family cannot be trained on as ordinary waitlist data. A position token that is present but invalid (`WL/0`, `RAC 0`) is now reported in `parse_note` instead of being dropped silently. See `docs/model/STATUS_GLOSSARY.md`.
- **Dataset validator (`backend/railconfirm/data/validator.py`):** a dataset was called valid when at least one row parsed. `is_valid` returned true for one good row in a 500-row file (now 100% rejected), `str(pd.NA)` renders `"<NA>"` so genuinely empty cells passed the required-value check, duplicate rows only produced a warning while still counting as valid, contradictory outcome labels on one reservation were undetected, dates were never parsed at all (so an observation dated after its own journey was accepted as a forecast input, and `01/02/2026` would be silently coerced by locale), and `unknown_final_status` rows were tallied in the distribution but reconciled as neither valid nor rejected. Rows are now counted under a stable reason and valid + rejected always equals total.
- **Structural validity, technical eligibility and approval are three separate verdicts.** `technically_eligible` requires clearing documented intake minimums (row counts, valid fraction, distinct journey dates, distinct labelled reservations, label diversity, duplicate share, plausible confirmed-outcome share); `approval` is reported as `NOT DETERMINED HERE`, because no mechanical check can establish that a dataset is licensed for training. `python -m railconfirm.data.validator <file>` now exits non-zero unless the file is technically eligible.
- **Baseline estimator evidence gate (`backend/railconfirm/inference/baseline.py`):** a frequency table could produce a confident distribution from nonsense. An unrecognised outcome key (`{"CONFIRMED": 100}`) silently returned a flat 0.2/0.2/0.2 estimate; negative counts and NaN raised an unhandled error mid-request; string and fractional counts were accepted or crashed; and a table fitted with lowercase cohort keys never matched, so it abstained while appearing loaded. Tables are now validated and canonicalised at load, malformed input raises `FrequencyTableValidationError` before any state changes, and a cohort that cannot support an estimate abstains instead of inventing one.
- **Error envelope, exception leakage and input bounds (`backend/railconfirm/api/`):** FastAPI raises `RequestValidationError` for request bodies and only a `pydantic.ValidationError` handler existed, so every `422` came back as Starlette's `{"detail": [...]}` and clients could not read field paths; both now emit the documented `{error, details[], request_id}` envelope. The `500` handler returned `str(exc)`, which can contain submitted status strings — the text now stays in the server log. Whitespace-only status strings produced an `unknown_status` abstention that read as "this status is unsupported" instead of "you left this empty", and status strings had no length bound. Health reported the fallback baseline's threshold even while a promoted artifact governed predictions.

### Added
- **API surface hardening (`backend/railconfirm/api/`):** CORS with an explicit origin allowlist (the browser could not reach the backend at all before), a `413` body-size limit (`RAILCONFIRM_MAX_REQUEST_BYTES`), `X-Request-ID` on every response, privacy-aware access logging (method/path/status/duration only — no bodies or status strings), engine dependency injection replacing the module-level singleton, `target` selection on the manual route, and `registry_status`/`model_available` on the prediction and health responses. `docs/architecture/API_CONTRACT.md` now describes the surface that ships rather than a proposal.
- **JSON model artifacts with two-gate promotion (`backend/railconfirm/inference/artifacts.py`, `registry.py`, ADR-0009):** an artifact is a JSON document declaring its format, version, target, feature-schema and status-mapping versions, outcome class order, dataset id and SHA-256, approval status, fitting window and promotion state. Serving requires both `RAILCONFIRM_ACTIVE_MODEL_VERSION` naming it and metadata declaring `approved_for_local_use`, so a file appearing in `models/` activates nothing. Reads are size-bounded, version names are path-safe, and pickle is not an accepted format — loading a model can no longer execute code. Registry resolution reports `no_active_version`, `artifact_missing`, `artifact_invalid`, `not_promoted`, `data_not_approved` or `ready`.
- **`model_artifact_invalid` abstention reason** for a configured artifact that failed validation, so a broken model is not reported as an absent one.
- **Estimator provenance:** a frequency table can only be installed with `FrequencyTableProvenance` (dataset id, SHA-256, source reference, approval status, synthetic flag, fitting window). Estimates require an explicitly approved, non-synthetic dataset; a passing quality check is not treated as a licensing decision. New `no_approved_data` abstention reason separates "no evidence base exists" from "no trained model is active" (`docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`).
- **Evidence basis on every estimate:** `PassengerOutcome.basis` records the matched cohort and its sample size, and states whether it was an exact status match or a broad-cohort fallback. Exposed as `basis` on the per-passenger API response.

### Changed
- **Temporal integrity is enforced (`backend/railconfirm/domain/validation.py`, `exceptions.py`, `passenger.py`, `prediction.py`, `inference/engine.py`):** offset-aware timestamps are required for `prediction_at`, `observed_at` and `created_at` — a naive timestamp is refused rather than assumed to be local or UTC, because an assumed zone shifts a lead time by up to twelve hours and that is the resolution at which "was this known before the chart?" is decided. A prediction timestamp on or after the journey date is rejected (the outcome is already settled, so it is not a forecast), evidence dated after `prediction_at` is rejected (it would leak the outcome into an as-of estimate), and an observation newer than its own ingestion time is rejected. `PredictionRecord.prediction_at` is now a required field.
- **Evidence coverage reports `partial`:** a request where some passengers have estimates and others abstain previously looked identical to a request where nothing was supported. An empty passenger list no longer reports `sufficient` (`all()` over an empty list is true); it reports `insufficient` with a warning.
- **Cancelled and censored statuses are surfaced as warnings** in addition to the `unsupported_status` abstention, so a caller can see the status was understood but is outside the target population.
- `domain/validation.py` is now the single home for train-number, station-code and date rules, replacing the duplicated regex in `journey.py`. `domain/exceptions.py` gained `TemporalIntegrityError`, and journey constraint failures now raise the declared domain exception instead of a bare `ValueError`.
- **Configuration paths are anchored to the repository root** (`backend/railconfirm/config.py`): `RAILCONFIRM_DATA_DIR` now defaults to `data/processed` (Git-ignored, matching `data/README.md`) and `RAILCONFIRM_MODELS_DIR` to `models`, resolved regardless of the working directory the server starts from. `.env.example` documents the variables the settings object actually reads.
- `backend/README.md` corrected: `RAILCONFIRM_MODEL_DIR`/`LOG_LEVEL` were never implemented under those names, the manifest command takes an output path positionally rather than `--output`, the documented prediction example used a future observation timestamp that the temporal rules now reject, and status mapping is v1.1.0.

## [0.1.0] - 2026-10-21

### Added
- **Domain model & status mapping (`backend/railconfirm/domain/`):**
  - Versioned reservation status mapping (`v1.0.0`) from Indian Railways terminology.
  - Distinguishes CNF, RAC, and WL categories (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL).
  - Explicit `UNKNOWN` status normalization — unrecognized codes are never silently mapped to WL.
  - Journey domain model with 4–6 digit train numbers, station differentiation, and class/quota validation.
  - Immutable `StatusObservation` and `PassengerReservation` domain types without passenger names (ADR-0005).
  - Multi-class prediction records and group-level outcome definitions.
- **FastAPI backend (`backend/railconfirm/api/`):**
  - `POST /v1/predictions/manual`: handles manual prediction requests with structured abstention responses.
  - `GET /v1/health`: returns API health, model version (`no_model_v0`), and data version.
  - Full Pydantic v2 schemas preserving original vs. latest observed statuses.
- **Inference engine & group baseline (`backend/railconfirm/inference/`):**
  - Abstention-first `InferenceEngine` returning `NO_TRAINED_MODEL` when no verified artifact is present.
  - `HistoricalFrequencyBaseline` with Laplace smoothing and minimum sample size thresholds.
  - Group outcome computation with independence baseline and explicit dependency disclaimers.
  - `ModelRegistry` checking local artifact presence.
- **Local dataset intake pipeline (`backend/railconfirm/data/`):**
  - Local dataset loader supporting CSV and JSON formats without network access.
  - Schema and data quality validator checking required columns, nulls, duplicates, and outcome distributions.
  - SHA-256 cryptographic manifest generator matching `docs/data/DATASET_MANIFEST_TEMPLATE.yaml`.
  - Chronological dataset partitioner (`chronological_split`) preventing temporal target leakage.
- **Next.js 14 frontend (`frontend/`):**
  - TypeScript + React + Tailwind CSS web interface.
  - `JourneyForm` and `PassengerList` with dynamic rows (up to 6 passengers) and client validation.
  - `StatusBadge` (textual & accessible, not color-only), `ProbabilityBar`, and `AbstentionCard`.
  - `PassengerOutcomeCard` and `GroupOutcomeCard` with explicit assumption notes.
  - Dedicated pages for methodology and data governance.
- **Test suite & CI (`backend/tests/`, `.github/workflows/ci.yml`):**
  - 43 passing unit, domain, inference, API, and data pipeline tests with 84% statement coverage.
  - Added feature extraction and chronological partitioning unit tests (`test_preprocessing.py`).
  - Added `ruff`, `mypy`, `pytest-cov`, and `types-PyYAML` to backend dev dependencies.
  - Standardized `pyproject.toml` build backend to `setuptools.build_meta`.
  - Consolidated single active GitHub Actions CI workflow at `.github/workflows/ci.yml` covering backend lint/type/tests, frontend build/type-check, and repository security scans.
  - Aligned `PredictionResponse.is_supported` across backend FastAPI schema and frontend Next.js types.

### Changed
- Updated `docs/PROJECT_STATUS.md` and `docs/DEVELOPMENT_LOG.md` to document the verified Phases 1–5 implementation.
- Updated root `README.md` with local setup and execution instructions.

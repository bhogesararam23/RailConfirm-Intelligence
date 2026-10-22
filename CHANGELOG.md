# Changelog

Notable changes to RailConfirm Intelligence are recorded here.

The format is inspired by Keep a Changelog; dates use ISO 8601.

## [Unreleased]

### Fixed
- **Status mapping integrity (`backend/railconfirm/domain/status.py`, mapping v1.1.0):** `CK` and `CKWL` were mapped to the waitlist category on an unverified guess. They now resolve to `UNKNOWN` with a review note, so an unverified family cannot be trained on as ordinary waitlist data. A position token that is present but invalid (`WL/0`, `RAC 0`) is now reported in `parse_note` instead of being dropped silently. See `docs/model/STATUS_GLOSSARY.md`.
- **Baseline estimator evidence gate (`backend/railconfirm/inference/baseline.py`):** a frequency table could produce a confident distribution from nonsense. An unrecognised outcome key (`{"CONFIRMED": 100}`) silently returned a flat 0.2/0.2/0.2 estimate; negative counts and NaN raised an unhandled error mid-request; string and fractional counts were accepted or crashed; and a table fitted with lowercase cohort keys never matched, so it abstained while appearing loaded. Tables are now validated and canonicalised at load, malformed input raises `FrequencyTableValidationError` before any state changes, and a cohort that cannot support an estimate abstains instead of inventing one.

### Added
- **Estimator provenance:** a frequency table can only be installed with `FrequencyTableProvenance` (dataset id, SHA-256, source reference, approval status, synthetic flag, fitting window). Estimates require an explicitly approved, non-synthetic dataset; a passing quality check is not treated as a licensing decision. New `no_approved_data` abstention reason separates "no evidence base exists" from "no trained model is active" (`docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`).
- **Evidence basis on every estimate:** `PassengerOutcome.basis` records the matched cohort and its sample size, and states whether it was an exact status match or a broad-cohort fallback. Exposed as `basis` on the per-passenger API response.

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

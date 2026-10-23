# Changelog

Notable changes to RailConfirm Intelligence are recorded here.

The format is inspired by Keep a Changelog; dates use ISO 8601.

## [Unreleased]

Milestone A (audit and harden the implemented foundation) and the frontend rebuild. Every behaviour described as broken below was reproduced against the running code before it was changed.

### Fixed

- **An unrouted path did not use the documented error envelope.** `GET` on a path nothing routes to answered Starlette's `{"detail": "Not Found"}` while every other failure answers `{error, details[], request_id}` — so the contract sentence "all handled errors use one envelope" was false for the most common mistake a client can make, and a client had to special-case it. Found by watching the real browser traffic while testing the reopen route, not by a test that assumed it. A `StarletteHTTPException` handler now maps 404 to `not_found`, 405 to `invalid_input` and 5xx to `INTERNAL_ERROR` through the same envelope, and the frontend's fallback branch stays as defence against a non-conforming reply.

- **A storage rule the rest of the product does not hold rejected every real save.** The first version of the history store refused any report whose `recorded_at` preceded its `prediction_at`, reasoning that a record cannot predate the estimate it describes. The entry form defaults "estimating as of" to 24 hours ahead — a legitimate question, "will this clear by the chart?" asked about a future moment — so the browser flow produced `stored: false` with a refusal message on every attempt. The check was invented, not required: the domain already validates `prediction_at` against the journey date and against the observation times, which is where the leakage rule actually lives. Retention now runs from the save, and a test pins the future-as-of case down so the rule cannot come back.

- **A naive timestamp was silently converted before it was checked.** Normalising the stored clock to UTC happened on the same path as validating it, and `astimezone()` assumes a naive value was local time — the exact guess the store exists to refuse. The awareness check now runs before any conversion, with a test that passes a naive `recorded_at` and expects a refusal.

- **The SQLite connection was bound to the thread that opened it.** The application factory opens the store at startup, but FastAPI serves routes on other threads, so the first real request raised `SQLite objects created in a thread can only be used in that same thread`. The store now holds one explicitly shared connection behind a lock, and a test writes from six threads to prove nothing is lost — a unit test on its own thread could never have caught this.

- **Two report reads disagreed about the same number.** The write path returned the in-memory expiry with microseconds while the read path reconstructed it from second-precision text, so `retention_expires_at` differed between the response that stored a report and the response that reopened it. Stored values are now normalised through the format they will be read back in.

- **Test fixtures that reused one passenger id** produced two React children with the same key, which printed a warning in every frontend run and would have masked a real key bug. The group fixtures now use distinct ids.

- **The frontend was written against a response shape the backend never sends (`frontend/src/`).** `types.ts` declared an `observed_status` object that does not exist in `PassengerOutcomeResponse`, so the branch that rendered observed status was dead code and **no ticket status was ever displayed**; the error type expected `{error, code, detail}` instead of the documented `{error, details[], request_id}`, so every validation failure surfaced as an undifferentiated banner with no field marked; `unsupported_quota` had no entry in the abstention message map and silently fell back to the "no trained model" text, telling the user the wrong reason; `p_cancelled` was never rendered, so the probability bar summed to less than 100% while its legend claimed a complete breakdown; `(x || 0) * 100).toFixed(1)` rendered a missing estimate as a confident `0.0%`; no request had a timeout, so a hung backend left the form spinning with the submit button disabled; and `datetime-local` inputs sent naive, offset-less timestamps that the backend now rejects. Types now mirror `api/v1/schemas.py` field for field, and 81 Vitest tests — including contract fixtures copied from the backend schemas — fail if the two drift again.

- **Privacy copy claimed more than the code enforced.** "No ticket data leaves your environment" was shown regardless of where `NEXT_PUBLIC_API_URL` pointed. The page now states the actual origin and only claims "on this machine" when it is a loopback address; the data-governance page says what is true today (no third-party calls, nothing stored) instead of promising a property of the deployment.

- **Accessibility defects:** `role="status"` on static status badges announced unchanging labels as live updates; the spinner rendered its label three times; field errors had no `aria-describedby` or `aria-invalid`; passenger rows were keyed by array index, so removing a middle row reused another row's input state; the add-passenger button vanished at the limit instead of showing a disabled reason; there was no skip link and the nav had no label.

- **Grammar in count sentences** ("1 of 1 passengers have an estimate", "Group outcomes (1 passengers)"), caught by exercising the real UI rather than by rendering tests alone.

- **Status mapping integrity (`backend/railconfirm/domain/status.py`, mapping v1.1.0):** `CK` and `CKWL` were mapped to the waitlist category on an unverified guess with no reference anywhere in the repository, so a guessed family joined the waitlist population in datasets and predictions. Both now resolve to `UNKNOWN` with a note naming what must be verified before re-admission. A position token that is present but invalid (`WL/0`, `RAC 0`) was dropped without a trace; it now records a `parse_note`, so "source omitted the position" and "source gave an unusable position" are distinguishable. See `docs/model/STATUS_GLOSSARY.md`.

- **Baseline estimator evidence gate (`backend/railconfirm/inference/baseline.py`):** a frequency table could produce a confident distribution from nonsense. An unrecognised outcome key (`{"CONFIRMED": 100}`) matched no class and, because those foreign counts were summed into the denominator and the result renormalised, returned a flat 0.2 per class — a supported estimate from zero evidence. Negative and NaN counts surfaced as unhandled `ValueError`s mid-request (a 500 for a valid request), string counts raised `TypeError`, fractional counts were smoothed, and a table fitted with lowercase cohort keys silently never matched at inference, so it abstained while appearing loaded. Tables are canonicalised and validated at load before any state changes; malformed input raises `FrequencyTableValidationError`.

- **Model artifact trust boundary (`backend/railconfirm/inference/registry.py`):** `has_model()` returned True for any existing `<version>.pkl`, so a foreign or corrupt file became the active model and the engine reported that version on the response while every passenger abstained with `no_trained_model` — a broken artifact was indistinguishable from one never trained. Pickle was also the container, which executes arbitrary code on load. See ADR-0009.

- **Temporal integrity (`backend/railconfirm/domain/`):** nothing enforced a timezone anywhere. A naive `prediction_at` was accepted and echoed back; a prediction dated on or after the journey was accepted, asking for a forecast of an outcome already settled; evidence observed after `prediction_at` was used as evidence for that same timestamp, which is the leakage rule AGENTS.md and ADR-0004 state; and an observation newer than its own ingestion time was accepted. Offset-aware timestamps are now required and those cases are refused. `PredictionRecord.prediction_at` is a required field.

- **Evidence coverage and status scope (`backend/railconfirm/inference/engine.py`):** an empty passenger list reported `evidence_coverage: sufficient` because `all()` over an empty list is true; a partly supported request reported `insufficient` as though nothing worked, although the contract documents `partial`; and cancelled or censored statuses produced supported probabilities (a censored row yielded `p_cnf` 0.73) instead of an out-of-population abstention.

- **API reachability, error envelope and leakage (`backend/railconfirm/api/`):** no CORS middleware existed, so a browser on `:3000` posting to `:8000` was blocked at preflight and the frontend reported that as "could not reach the backend". FastAPI raises `RequestValidationError` for request bodies while only a `pydantic.ValidationError` handler was registered, so every `422` returned Starlette's detail array and clients could not read field paths. The `500` handler returned `str(exc)`, which can contain submitted status strings. Whitespace-only statuses became `unknown_status` abstentions that read as "unsupported" rather than "you left this empty", status strings were unbounded, and passenger lists had no server-side cap. Health reported the fallback baseline's threshold even while a promoted artifact governed predictions.

- **Dataset validation (`backend/railconfirm/data/validator.py`):** a dataset was called valid when at least one row parsed, so one good row in a 500-row file reported valid. `str(pd.NA)` renders `"<NA>"`, letting genuinely empty cells pass the required-value check; duplicates only warned and stayed in `valid_rows`; contradictory outcome labels on one reservation were undetected; dates were never parsed at all, so an observation after its own journey was accepted and `01/02/2026` would be coerced by locale; and `unknown_final_status` rows reconciled as neither valid nor rejected. Valid plus rejected now always equals total, under stable reasons.

- **Chronological splitting (`backend/railconfirm/data/preprocessing.py`):** with one or two distinct journey dates every row came back as `train` with empty validation and test frames and nothing said so; at exactly three dates `train` held six rows while `test` held none, so any metric would have scored against nothing. Splits now allocate whole dates, are independent of input row order, parse dates strictly as ISO, and return `eligible=False` with **no partitions at all** when a genuine future period cannot be held back. A `booking_group_id` spanning partitions blocks the split.

- **As-of features:** queue positions were fabricated as `0`, which reads to a model as "first in queue"; `lead_days` used `errors="coerce"` then `fillna(0)`, so a missing date asserted a same-day lead; and `.clip(lower=0)` turned a post-departure observation, which is pure leakage, into a zero-day lead. Positions are nullable, an unknown lead is null, and `extract_features` refuses a frame still carrying an outcome column.

- **CSV loading (`backend/railconfirm/data/loader.py`):** pandas accepts a short row padded with NaN, drops the surplus fields of a long row, renames a repeated column to `a.1` and a blank one to `Unnamed: 1`, all silently (confirmed against pandas 2.3.3). Header and row widths are now checked explicitly, which also keeps parsing identical across the pandas versions development and CI run.

- **CI checks were inherited from tool defaults (ADR-0010):** commit `a87afc1` passed locally and failed CI lint because `pyproject.toml` declared no Ruff rule set — local 0.16.9 enabled `DTZ001`, CI's 0.17.2 did not, so the `# noqa` markers became `RUF100` failures. `[tool.ruff.lint] select` now names the rules, Mypy is configured in `pyproject.toml`, and dev tool ranges are constrained.

- **The CI hygiene step could not fail:** `grep -r "pnr" ... | grep -v ... | head -5` inside `if ...; then` tests `head`, which exits 0 on empty input, so the "secret and private data" check warned on every commit and prevented nothing. Checks moved to `scripts/check_repository_hygiene.py`. Verified able to fail: a reintroduced broken link produced exit 1, restoring it produced exit 0.

- **Manifests asserted a clock date (`backend/railconfirm/data/manifest.py`):** `datetime.now()` meant two runs over the same file never produced the same bytes, and nothing verified a manifest against its dataset. Generation is now deterministic (`--retrieved-on` required), output follows `DATASET_MANIFEST_TEMPLATE.yaml` section-for-section — previously only `sha256` matched by name — and `verify_manifest` re-hashes and **recounts** rows and duplicates instead of trusting what the file claims.

### Added

- **Frontend test suite:** Vitest + Testing Library + jsdom (`npm test`), covering null-safe probability formatting, evidence-basis wording, every abstention reason's distinct text, the error envelope, timeout and network classification, client validation rules against the server's, and rendering of supported, abstaining and partially supported responses. CI runs it in the frontend job.

- **Prediction context selection in the form:** the estimating-as-of moment and the target (`final_chart_cnf` / `final_chart_cnf_or_rac`) are now inputs the user can see and change, with the browser's UTC offset attached, instead of the page silently stamping `new Date()`.

- **Report provenance block:** target, as-of time, model version, registry state, feature-schema version, request id and evidence coverage are shown even when every passenger abstains.

- **JSON model artifacts with two-gate promotion (`inference/artifacts.py`, ADR-0009):** an artifact declares its format, version, target, feature-schema and status-mapping versions, outcome class order, dataset id and SHA-256, approval status, fitting window and promotion state. Serving requires both `RAILCONFIRM_ACTIVE_MODEL_VERSION` naming the file and metadata declaring `approved_for_local_use`, so a file appearing in `models/` activates nothing. Reads are size-bounded, version names are path-safe, and pickle is not an accepted format.

- **Abstention reasons that name the closed gate:** `no_approved_data` ("no evidence base exists") and `model_artifact_invalid` ("configured artifact rejected") join `no_trained_model`, because those three call for different unfinished work. Documented in `docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`.

- **Estimator provenance:** a frequency table can only be installed with `FrequencyTableProvenance` (dataset id, SHA-256, source reference, approval status, synthetic flag, fitting window). Only a real, explicitly approved dataset yields estimates — a passing quality check is not a licensing decision, and synthetic fixtures prove arithmetic, not railway behaviour.

- **Evidence basis on every estimate:** `PassengerOutcome.basis` records the matched cohort and its sample size and states whether a broad-cohort fallback was used; exposed as `basis` in the API response. A fallback is a weaker claim than a cohort match and the numbers alone do not show which ran.

- **API surface:** CORS with an explicit origin allowlist, a `413` body-size limit, `X-Request-ID` on every response, privacy-aware access logging (method/path/status/duration only), engine dependency injection replacing the module-level singleton, `target` selection on the manual route, and `registry_status`/`model_available` on prediction and health responses.

- **Dataset intake command line:** `python -m railconfirm.data validate|manifest|verify` with documented exit codes and a `--json` report form.

- **Approval cannot be manufactured by a script:** `status: approved` requires `decision.decision: approved` with `reviewed_by`, `reviewed_on` and a rationale, plus an approved licence review permitting model training; `licence_review_status: approved` is refused while training use is `unknown`; `privacy.contains_raw_pnr: permitted` is refused outright. The status vocabulary is closed, so `approved_for_training`, `metadata_only` and `synthetic_test_only` no longer parse.

- `EligibilityThresholds` makes the intake minimums explicit and configurable; `SplitResult` publishes per-partition row counts, distinct dates, distinct bookings and boundaries; `FEATURE_SCHEMA_VERSION`/`FEATURE_COLUMNS` are now the shared feature definition training and inference must agree on.

- **Baseline training pipeline (`backend/railconfirm/training/`, ADR-0011):** `dataset.py` is the only way training obtains data — the manifest must verify against the file it describes (hash, size, recounted rows), a named reviewer must have recorded an `approved` decision with a rationale, `licence_review_status` must be approved **and** `allowed_uses.model_training` must be `permitted`, and rows declaring `is_synthetic` are refused unless the caller opts in for pipeline testing, which marks the resulting artifact unservable. `fitter.py` counts cohorts from the training partition only, refuses an ineligible split, validates the fitted table through the same `normalize_frequency_table` gate inference uses, records the training window and exclusion counts, and always writes `promotion: "candidate"` — fitting activates nothing.

- **Probability evaluation (`training/metrics.py`):** multiclass Brier and log loss for held-out rows, each compared with a prevalence baseline computed from the **training** period, plus `brier_skill`, coverage, abstention counts, per-class reliability bands with counts, and per-segment scores that carry their row counts and a `low_sample` flag. Abstained rows are excluded from the scores instead of being counted as wrong. Scoring uses the same `HistoricalFrequencyBaseline` object inference serves from, so a metric cannot describe a code path the product does not run.

- **The target's own event is scored, not just the distribution (`TARGET_EVENTS`):** `final_chart_cnf` scores the confirmed mass against a 0/1 label and `final_chart_cnf_or_rac` scores confirmed-plus-RAC, each with its own binary Brier, log loss, prevalence baseline, skill and reliability bands. The report prints a verdict for both and adds an explicit line when they disagree about beating the base rate — which they do on the synthetic fixture (distribution 0.501038 against a 0.500000 baseline, CNF event 0.232664 against 0.250000), so quoting one number would have hidden the other result.

- **Reproducible evaluation reports (`training/report.py`):** deterministic JSON — `--generated-on` is required and nothing reads the clock — publishing split boundaries, rows used and excluded per reason, the feature list with its availability statement, the dataset hash and approval state, metric definitions, segment counts and a limitations block that states when no calibration was fitted. Conclusions are derived from the measured verdicts rather than hand-written, `METRIC_KEYS` is derived from the scorecard's own fields, and a test fails if a published number lacks a definition or a definition describes nothing published.

- **Training command line:** `python -m railconfirm.training fit|evaluate` with `--target` restricted to targets that have a defined event, target agreement checked against the artifact's declared target, and `Refused: …` on exit 1 for blocked data, ineligible splits and rejected artifacts instead of a traceback.

- **`FrequencyTableProvenance.evaluation_only`:** a memory-only flag that lets synthetic cohorts be scored so the metrics code is actually exercised. It is not a field of `ModelArtifactMetadata`, so no stored artifact can carry it, and it does not override the approval requirement — tests assert both.

- **Opt-in local prediction history (`backend/railconfirm/storage/`, ADR-0012).** A report can now be kept and reopened, which is what `/prediction/[id]` — documented in the frontend guide since the start and previously decoration — needed. Storage requires two independent switches: `RAILCONFIRM_PERSIST_PREDICTIONS` on the server (default **false**) and `"persist": true` on the request. The response carries `stored`, `report_url` and `retention_expires_at`, so "did my report get kept?" is answered by the server rather than assumed from the request; a save the store refused still delivers the estimate and puts the reason in `limitations`. `GET /v1/predictions/{prediction_id}` returns the stored response unchanged — nothing is recomputed, because a reopened report is evidence about what was said then, with the model version it came with. Retention is enforced twice over: an expired id stops resolving before a purge ever runs, and `prediction_retention_days` refuses a value below 1. `DENIED_KEYS` and a PNR-shaped-value scan run at the write, so a future field cannot start storing a passenger name or a PNR by oversight, and a 10-digit id on the reopen route is refused with a message saying reports are reopened by the id the server returned. SQLite in one Git-ignored file, no new dependency, no server; `data/storage/` and `*.sqlite3*` are ignored so a history file cannot be committed.

- **`/prediction/[id]` in the frontend** renders the kept report with a banner saying it is "the report as it was served" and when that copy stops being retrievable, and separates the three reasons a report can be unavailable — never stored, aged out, this server keeps no history — because they call for different actions. The entry form's new "keep this report" control states that the response says whether it was actually kept.

- **`GET /v1/health` reports `prediction_history`** (`enabled`, `retention_days`, `stored_reports`, empty when disabled), so an interface can stop offering to save where saving is impossible, and an operator can see the state without opening the file.

- **Candidate dataset review (`docs/data/CANDIDATE_DATASET_REVIEW.md`):** the search for a trainable dataset is now recorded with evidence instead of being described as a gap. Four candidates were inspected on 2026-10-23 — a Kaggle "Indian Railway Ticket Confirmation" set whose own page says it is *"synthetically generated and does not represent real data"* (MIT, rejected), an IRCTC-scraped schedule/fare/availability set with no per-reservation chart label (Apache 2.0, rejected for training), a stations/trains/schedules metadata set credited to DataMeet (Kaggle lists `CC0: Public Domain`, under review for reference use only), and its origin repository `datameet/railways`, which cites CC0 in prose but **has no licence file**, so the grant is unconfirmed. `data.gov.in` returned HTTP 403 to an unauthenticated automated fetch, so its holdings were not read. No file was downloaded or ingested. The finding is specific: none of these carries both a reservation's booked status and its verified final-chart outcome under training permission, which is what the abstention behaviour is waiting on. `docs/data/SOURCE_REGISTER.md` records each verdict and `docs/PROJECT_STATUS.md` states the blocker in those terms.

### Changed

- Backend tests grew from 43 to 502 and branch coverage from 84% statements to 95.91% (statements and branches); CI now fails below 90%. 74 cover the training, evaluation and reporting pipeline and 38 the prediction history. Frontend tests grew to 93.

- `.github/workflows/ci.yml` requests `permissions: contents: read`, cancels superseded runs on the same ref, and enforces `--cov-fail-under=90`.

- **Configuration paths are anchored to the repository root** (`backend/railconfirm/config.py`): `RAILCONFIRM_DATA_DIR` defaults to `data/processed` (Git-ignored, the path `data/README.md` documents) and `RAILCONFIRM_MODELS_DIR` to `models`, resolved whichever directory the server starts from. `.env.example` now lists the variables the settings object actually reads.

- `domain/validation.py` is the single home for train-number, station-code and date rules, replacing the duplicated regex in `journey.py`; `domain/exceptions.py` gained `TemporalIntegrityError`, `FrequencyTableValidationError` and `ModelArtifactError`, and is now actually used.

- Documentation rewritten to describe the system that exists: `docs/architecture/API_CONTRACT.md` (it still read "no API implementation is implied" after the route had shipped), `docs/data/DATA_CONTRACT.md` (now states the row contract the validator enforces), `docs/data/DATASET_INTAKE_CHECKLIST.md` (which items are machine-checked and which are human decisions), `docs/research/EVALUATION_PROTOCOL.md` (implemented split behaviour; rolling-origin explicitly not implemented), `docs/adr/ADR-0009`, `docs/adr/ADR-0010`, `docs/model/STATUS_GLOSSARY.md`, `docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`, `backend/README.md`, `ci/README.md`, `data/README.md`.

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

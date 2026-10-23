# Development and session log

This is a durable record of meaningful development sessions, including decisions, checks and open questions. It is not intended to replace Git history.

## 2026-10-21 — Repository foundation

### Scope
Initialized the empty public repository with project, research, data governance, agent workflow, security and licensing documentation.

### Added
- Project README and status page.
- Research plan and prediction/evaluation specifications.
- Data acquisition plan, data contract and source register.
- Architecture overview and privacy/security baseline.
- Contributor and agent instructions.
- Changelog, third-party data note and notice.
- ADR process and ADR-0001 through ADR-0006.

### Decisions
- Documentation and data-readiness gates precede model performance claims.
- Initial web/API/ML stack is a candidate direction, not a deployed implementation.
- Passenger outcomes distinguish CNF, RAC and WL where data supports those targets.
- Group outcomes should account for dependence between passengers.
- Backtesting must be chronological and leakage-resistant.
- Data access and PNR retention require source-specific authorization and privacy controls.
- Apache-2.0 applies to original repository materials; third-party data remains separately governed.

### Checks
- Repository was confirmed public, writable and empty before initialization.
- Documentation changes were committed through the GitHub repository API.
- No code, model training, dataset ingestion, automated tests or deployment was run during this documentation session.

### Open items
- Verify candidate datasets, licences, label semantics, historical outcome coverage and costs.
- Decide which sources are usable for model training and which are reference-only.
- Implement schemas and their validation tests.
- Implement a baseline and chronological evaluation.
- Validate the proposed technology stack in the first vertical slice.
- Keep live PNR tracking disabled until provider permissions and controls are verified.

## 2026-10-21 — Product and technical specification

### Scope
Expanded the documentation from project/research principles into implementation-oriented product and engineering contracts.

### Added
- Product brief, requirements, user journeys and MVP acceptance criteria.
- Central documentation index and agent handoff.
- System design, domain model and logical storage model.
- Inference and group-probability specification.
- Source ingestion/tracking lifecycle.
- Frontend interaction/accessibility guide.
- Testing strategy, observability and deployment runbook.
- Ordered implementation plan.
- Updated README, changelog and documentation index.

### Decisions and boundaries
- Manual entry remains the first product path.
- Live tracking stays disabled until an authorized source and retention policy are verified.
- No unsupported probability is returned as if it were a trained prediction.
- The first code task should be the status/domain contract and tests, subject to authoritative verification of status mappings.
- No new material architecture decision was made beyond elaborating the existing ADRs.

### Checks
- Verified the new and updated files on the repository's main branch.
- Confirmed the docs contain proposed behavior and implementation gates rather than claims of completed software.
- No application tests, model runs, dataset ingestion or deployment were performed; there is no implementation to validate yet.

### Remaining work
- Implement the domain contract and status normalization with tests.
- Complete source/terms feasibility review.
- Build the manual-entry API/UI shell with an explicit no-model response.
- Establish a reproducible baseline once permitted labelled data is available.


## 2026-10-21 — Local-first roadmap

### Scope
Converted the staged implementation plan into a single phased roadmap and made the current runtime boundary explicit.

### Added
- Local-first roadmap with phase deliverables and exit gates.
- ADR-0007 for no third-party runtime APIs in the current build.
- Dataset intake checklist and manifest template for agent-prepared candidate data.
- Local data workspace instructions and ignored local dataset paths.
- Updated product, implementation, agent and project status documentation.

### Decisions
- The current application has no third-party runtime API dependency; an internal frontend/backend API remains allowed.
- Agents may research and prepare candidate data, but files are not approved for training until source rights, provenance, privacy, labels and quality pass review.
- Live PNR lookup/polling, news/context feeds and hosted inference are deferred beyond the current roadmap and require a new ADR to reopen.

### Checks
- Confirmed the new files were committed to the repository's default branch.
- No dataset was downloaded or approved in this session.
- No application code, training, automated tests or deployment was run in this documentation session.

### Next step
Implement Phase 1 of docs/ROADMAP.md: domain/status schema and parsing tests. Continue agent-assisted dataset discovery as a separately tracked task, completing a manifest and intake report for each candidate.


## 2026-10-21 — Product scope consistency audit

### Scope
Audited product, roadmap, agent, architecture, data and ADR documents for language that could cause the first local-first build boundary to be mistaken for a permanent exclusion of live data integrations.

### Findings and corrections
- Kept ADR-0007's local-first restriction for implementation Phases 0–7.
- Added ADR-0008 to state that authorized live ticket/status sources, verified current/upcoming operational/news/event context, and continuous forecast updates are planned core capabilities of the long-term product.
- Expanded docs/ROADMAP.md with planned Phases 8–10 and explicit permission, reliability, privacy, data-freshness and incremental-value exit gates.
- Aligned the product brief, product requirements, canvas, project status, source register, implementation plan, local-first guide, API contract, ingestion/tracking guide, user journeys, README and agent instructions with the same distinction.
- Added dataset-source controls so agent-prepared files remain candidates until rights, label meaning, privacy and quality pass review.

### Validation
- Scanned key goal/scope documents for contradictory phrasing and verified that current-build restrictions refer to Phases 0–7 while the long-term integrations appear in Phases 8–10.
- Checked the updated roadmap, ADR index, source register and agent handoff.
- No application tests, model training, live API integration or dataset ingestion was run; this session was documentation review and correction only.

### Remaining work
- Implement Phase 1 domain/status contracts and tests.
- Continue candidate dataset discovery and produce an intake report for each dataset.
- Keep concrete provider selection and source-specific ADRs pending until the underlying rights/terms and usefulness are verified.


## 2026-10-21 — First implementation session (Phases 1–5 foundation)

### Scope
First substantive implementation session. Built the Python backend (domain, API, inference, data pipeline) and the Next.js frontend (React/TypeScript/Tailwind), establishing the foundational codebase for the local-first application.

### Stack validated
- Python 3.11 + FastAPI + Pydantic v2 (backend, per ADR-0002).
- TypeScript + Next.js 14 + Tailwind CSS (frontend, per ADR-0002).
- pytest with httpx for async API tests (no external network required).
- GitHub Actions CI with backend tests, frontend build check, and documentation presence check.
- No PostgreSQL in the initial setup; the first local demo uses in-memory state to remain dependency-light.

### Implemented (backend — `backend/`)
- `railconfirm/domain/status.py`: versioned status parsing and normalization; raw status always preserved; unknown codes mapped to UNKNOWN (never silently to WL); WL categories (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL) parsed separately from position; mapping version 1.0.0 with source reference.
- `railconfirm/domain/journey.py`: typed journey, class/quota validation, supported code registries.
- `railconfirm/domain/passenger.py`: immutable StatusObservation, PassengerReservation (no name field), BookingGroup.
- `railconfirm/domain/prediction.py`: PredictionTarget, AbstentionReason, PassengerOutcome, GroupOutcome, PredictionRecord; probabilities enforced in [0, 1]; mutually exclusive outcomes summing to 1.
- `railconfirm/domain/validation.py`: shared validators and reason codes.
- `railconfirm/domain/exceptions.py`: domain exception hierarchy.
- `railconfirm/api/app.py`: FastAPI application factory.
- `railconfirm/api/v1/predictions.py`: POST /v1/predictions/manual; returns structured abstention (not fabricated probability) when no model available.
- `railconfirm/api/v1/health.py`: GET /v1/health with model_version and data_version.
- `railconfirm/api/v1/schemas.py`: request/response Pydantic models; original_status and current_status kept distinct.
- `railconfirm/inference/engine.py`: abstention-first dispatch; returns NO_TRAINED_MODEL when no artifact available.
- `railconfirm/inference/baseline.py`: HistoricalFrequencyBaseline with Laplace smoothing; abstains if approved dataset not available.
- `railconfirm/inference/group.py`: independence baseline clearly labelled as such; warns about dependency assumption; abstains if any passenger abstains.
- `railconfirm/inference/registry.py`: model version/artifact registry.
- `railconfirm/data/loader.py`, `validator.py`, `manifest.py`, `preprocessing.py`: local dataset intake pipeline.
- `railconfirm/config.py`: environment-variable configuration; no hard-coded secrets.
- Comprehensive test suite under `backend/tests/`.
- Clearly labelled synthetic fixtures in `backend/tests/fixtures/`.

### Implemented (frontend — `frontend/`)
- Next.js 14 app with TypeScript and Tailwind CSS.
- Type-safe API client matching the API contract.
- JourneyForm, PassengerList, PassengerRow — no name field, original vs current status kept distinct.
- StatusBadge, ProbabilityBar, AbstentionCard — accessible, text labels not color-only.
- PredictionResult, PassengerOutcomeCard, GroupOutcomeCard — honest abstention shown when no model.
- Methodology and data pages explaining product status accurately.
- Client-side validation with matching server-side enforcement.

### CI
- `.github/workflows/ci.yml`: backend tests, frontend type-check and build, documentation presence check — all run without external credentials or network access.

### Data and model status
- No approved historical dataset available; intake pipeline is implemented and tested with synthetic fixtures.
- Inference engine always abstains with NO_TRAINED_MODEL; no fabricated probabilities returned.
- Baseline estimator implemented but not yet runnable without an approved dataset.

### Checks run
- See commit-level notes for exact pytest and build output.
- All domain tests pass on synthetic fixtures.
- API returns structured abstention responses, not fake probabilities.
- Frontend builds and type-checks without errors.

### Remaining work
- Identify and intake an approved historical dataset (source rights, privacy, label semantics to be verified).
- Train and evaluate the baseline estimator once an approved dataset passes the intake checklist.
- Build out the group outcome layer beyond the independence baseline (requires labelled booking groups).
- Add PostgreSQL persistence layer for Phases 6–7.
- Complete the model card and dataset manifest once real data is approved.
- Enable GitHub Actions CI to run automatically on push (pending remote push access verification).

## 2026-10-21 — CI consolidation, code quality tooling, and verification

### Scope
Consolidated continuous integration workflow, configured backend developer tooling (`ruff`, `mypy`, `pytest-cov`), fixed packaging build backend, and executed full verification across the repository.

### Changes
- **CI Workflow consolidation:**
  - Migrated active workflow to `.github/workflows/ci.yml` with push and PR triggers on `main`.
  - Removed redundant `ci/github-actions-ci.yml` to maintain a single source of truth; updated `ci/README.md`.
  - Configured jobs for backend checks (`ruff`, `mypy`, `pytest --cov`), frontend checks (`npm ci`, `type-check`, `lint`, `build`), and docs/security scans.
- **Backend developer tooling & packaging:**
  - Added `ruff>=0.4.0`, `mypy>=1.10.0`, `pytest-cov>=5.0.0`, and `types-PyYAML>=6.0.12` to `[project.optional-dependencies].dev` in `backend/pyproject.toml`.
  - Fixed `[build-system]` to use standard PEP 517 `setuptools.build_meta`.
  - Cleaned up unused local variables in `railconfirm/inference/baseline.py` (`total_smoothed`, `smoothed_counts`) and added strict probability normalization.
  - Resolved `ruff` and `mypy` issues: converted `ValueError` to `TypeError` on invalid journey date type, fixed timezone awareness with `timezone.utc`, added typed dict for passenger inputs, and broadened engine sequence signature to `Sequence[Mapping[str, Any]]`.
  - Aligned `PredictionResponse.is_supported` field between backend schema and frontend Next.js types.
- **Tests:**
  - Added `backend/tests/data/test_preprocessing.py` covering feature extraction and chronological partitioning without temporal leakage.
  - Test suite expanded to 43 passing tests.

### Checks run & results
- **Backend Linting:** `ruff check railconfirm/ tests/` &rarr; 0 errors (all checks passed).
- **Backend Type-checking:** `mypy railconfirm/ --ignore-missing-imports` &rarr; 0 errors (success: no issues found in 26 source files).
- **Backend Tests & Coverage:** `pytest tests/ -v --cov=railconfirm --cov-report=term-missing` &rarr; 43 passed in 1.13s with 84% statement coverage.
- **FastAPI Endpoints:** Verified `GET /v1/health` (200 OK) and `POST /v1/predictions/manual` (200 OK with `is_supported=False` and structured `no_trained_model` abstention).
- **Frontend Type-check:** `npm run type-check` (`tsc --noEmit`) &rarr; 0 errors.
- **Frontend Lint:** `npm run lint` (`next lint`) &rarr; 0 errors or warnings.
- **Frontend Production Build:** `npm run build` &rarr; compiled successfully, generated all 6 static routes.
- **Markdown Links:** Verified all relative documentation links resolving correctly.
- **Security & Privacy:** Scanned repository for `.env` files and unredacted 10-digit PNR strings; confirmed zero private data or secrets committed.

### Remaining work
- Observe GitHub Actions CI execution upon remote push to `origin/main`.
- Intake and evaluate candidate historical dataset under `docs/data/DATASET_INTAKE_CHECKLIST.md`.

## 2026-10-23 — Milestone A: audit and harden the implemented foundation

### Scope

Reviewed the implemented domain, inference, API and data layers against observed
behaviour rather than the previous session's reports, fixed every concrete defect
found, and made CI checks mean the same thing locally and remotely. Eleven commits
pushed to `origin/main`, ending at `7126d4e`.

### Defects confirmed and fixed

Each was reproduced against the code before it was changed. Probe scripts ran
outside the repository and were deleted.

1. `HistoricalFrequencyBaseline` smoothed any dictionary it was given. A cohort
   keyed `{"CONFIRMED": 100}` returned `p_cnf 0.2, p_rac 0.2, p_wl 0.2` as a
   *supported* estimate; negative counts raised an unhandled `ValueError` mid-request;
   `{"CNF": "30"}` raised `TypeError`; lowercase fitted cohort keys never matched,
   so a loaded table abstained while appearing usable.
2. `ModelRegistry.has_model()` returned True for any existing `<version>.pkl`. The
   engine then reported that version while every passenger abstained with
   `no_trained_model`, so a broken artifact looked like an untrained one. Pickle was
   the container, which executes code on load.
3. `parse_status` mapped `CK` to `WL/CKWL` on an inline comment admitting the
   semantics "need verification". No reference existed anywhere in the repository.
4. No timezone was enforced anywhere: a naive `prediction_at` was accepted and
   echoed; `prediction_at` after the journey date was accepted; a status observed
   after `prediction_at` was used as evidence for that timestamp.
5. An empty passenger list reported `evidence_coverage: sufficient` because `all()`
   over an empty list is true. A partly supported request reported `insufficient`.
   `CENSORED` and `CANCELLED` statuses produced supported probabilities (`p_cnf 0.73`).
6. `validate_dataset` reported valid on one parsed row of 500. `str(pd.NA)` renders
   `"<NA>"` so empty cells passed the required-value test; duplicates only warned;
   contradictory labels were undetected; dates were never parsed; `unknown_final_status`
   rows reconciled as neither valid nor rejected.
7. `chronological_split` returned every row as `train` with empty val/test for one or
   two distinct dates, and at exactly three dates gave `train` 6 rows and `test` none.
   Non-ISO dates sorted lexicographically, putting `01/02/2026` in `train` next to
   `2025-12-31` while `2026-01-01` went to test.
8. `extract_features` fabricated position `0`, turned unparseable dates into
   `lead_days = 0` via `fillna`, and clamped post-departure observations to `0`.
9. The loader trusted pandas: a row wider than the header **loses its surplus
   fields**, a short row is NaN-padded, a duplicate column becomes `a.1`, a blank one
   becomes `Unnamed: 1`. Confirmed against pandas 2.3.3.
10. `generate_manifest` stamped `datetime.now()`, so two runs over one file produced
    different bytes; nothing could verify a manifest against its dataset; only
    `sha256` of ~60 template keys matched.
11. The API had no CORS middleware at all, so the frontend could not reach the
    backend; only a `pydantic.ValidationError` handler was registered while FastAPI
    raises `RequestValidationError` for bodies, so every 422 returned an undocumented
    shape; the 500 handler returned `str(exc)`, which can contain submitted statuses.

### Correction to the 2026-10-21 entry

That entry records "Verified all relative documentation links resolving correctly"
and "Scanned repository for `.env` files and unredacted 10-digit PNR strings;
confirmed zero private data". Both were wrong as executed. The link check missed
`ci/README.md` pointing at `ci/github-actions-ci.yml`, deleted when the workflow
landed; the hygiene scan is broken by its shell pipeline (`grep … | head -5` inside
`if …; then` tests `head`, which exits 0 on empty input, so the step could never
fail). Neither claim was re-verified at the time. Both are now actual checks in
`scripts/check_repository_hygiene.py`, and the failure mode was demonstrated: a
reintroduced broken link produced exit 1, restoring it produced exit 0.

### Checks run and results

- `pytest tests/` → **384 passed**. Grew from 43 at session start.
- `pytest --cov=railconfirm` → **96%** (statements and branches; branch coverage now
  enabled in `pyproject.toml`). Previously reported 84% was statements only.
- `ruff check railconfirm/ tests/` → all checks passed, against an explicitly
  declared rule set.
- `mypy` → no issues in 29 source files, against `pyproject.toml` configuration.
- `python scripts/check_repository_hygiene.py` → exit 0; 168 tracked files scanned.
- **Real HTTP verification, not only TestClient:** `uvicorn railconfirm.api.app:app`
  on `127.0.0.1:8123` — `/v1/health` 200 with `model_available: false` and
  `registry_status: no_active_version`; `POST /v1/predictions/manual` 200 with
  structured abstention; naive `prediction_at` → 422 with dotted field path;
  identical stations → 422; oversize body → 413 `REQUEST_TOO_LARGE`; CORS preflight
  allowed for `http://localhost:3000` and refused for an unlisted origin; `/docs` 200;
  OpenAPI listing exactly the four request fields.
- **Promotion gate verified end to end** with a temporary artifact created *outside*
  the repository: file present without `RAILCONFIRM_ACTIVE_MODEL_VERSION` served
  nothing (`no_active_version`); with it activated the same request returned
  `p_cnf 0.6454` for the SL/GN/WL cohort, `basis cohort=SL/GN/WL n=105
  exact_status_match=true`, and a passenger whose cohort was absent abstained so
  coverage came back `partial`. The temporary file was deleted; no synthetic artifact
  claiming approved real data was left in the tree.
- **GitHub Actions observed:** runs 39862139214, 39864368103, 39871983243 and 39876116132
  succeeded on pushed commits. Runs 39865661797, 39868053637, 39874595819, 39875188482
  and 39875632374 failed, each on a real defect in my own change (an undeclared Ruff
  rule set, then two platform-dependent test assumptions, then a mypy-version
  disagreement). All were fixed forward; no history was rewritten and no check was
  weakened to get green. `main` is green at `7126d4e`.

### Decisions

- ADR-0009: JSON artifacts, two-gate promotion, split abstention reasons, validated
  frequency tables, unverified status families kept unknown.
- ADR-0010: declared lint/type rule sets, dev tools pinned to verified versions
  (`ruff~=0.16.9`, `mypy~=1.19.1`), and a hygiene gate that can actually fail.
  The ADR's original claim that version *ranges* were sufficient was corrected in a
  later commit after CI proved otherwise, and the correction is recorded in the ADR
  rather than quietly rewritten.

### Data and model evidence

No approved dataset exists. No training, evaluation or calibration has been run,
because there is nothing eligible to run them on. No accuracy or calibration figure
appears anywhere in the repository.

### Remaining work

1. Frontend contract mismatch: `frontend/src/lib/types.ts` describes an
   `observed_status` object the backend never returns, so observed statuses are not
   displayed, `(x || 0) * 100` renders a fabricated `0.0%` for a null probability,
   `p_cancelled` is never rendered so the probability bar cannot sum to 100%, and the
   error shape does not match. No frontend test framework exists.
2. Group outcomes remain an independence baseline; dependence-aware estimation needs booking labels.
3. Dataset intake: find and review a real candidate; nothing has been approved.
4. Training, evaluation and calibration pipelines: not implemented.
5. Persistence and prediction history: not implemented; nothing is stored today.

## 2026-10-23 — Frontend rebuilt against the real API contract

### Scope

The Milestone A audit found the frontend could not work end-to-end and reported
defects that rendering tests alone had never caught. This session rebuilt it against
the shipped backend contract and added the test layer that was missing.

### What was wrong, and how it was confirmed

The audit read `frontend/src/lib/types.ts` against
`backend/railconfirm/api/v1/schemas.py` and found a declared `observed_status`
object the backend never sends. The consequence was not cosmetic: the branch that
would have displayed the passenger's ticket status was unreachable, so the page
showed an estimate or an abstention without ever showing what was observed. The
error type expected `{error, code, detail}` where the server sends
`{error, details[], request_id}`, so a 422 produced one banner and no field was
marked. `unsupported_quota` had no message entry and silently borrowed the "no
trained model" text. `p_cancelled` was never rendered, so the stacked bar could not
sum to 100% while its legend presented itself as the complete distribution.
`((x || 0) * 100).toFixed(1)` rendered a deliberately absent probability as `0.0%`.
No request had a timeout. `datetime-local` produced naive timestamps the backend now
rejects.

### Changes

- `lib/types.ts` mirrors the backend schemas field for field, including `target`,
  `registry_status`, `basis`, `passenger_count`, `outcome_classes` and the full
  abstention reason union.
- `lib/api.ts` attaches an `AbortController` timeout, classifies failures into
  `validation` / `http` / `network` / `timeout`, parses the documented error envelope
  into per-field messages, and reports the request id. A transport failure no longer
  claims the backend is down: a blocked CORS preflight is indistinguishable from the
  page, so the message names both possibilities.
- `lib/validation.ts` mirrors the server rules, adds `hasUtcOffset` and
  `toOffsetIso` so browser-local input is sent with a real offset, drops the invented
  "limited to 2 years" rule the server does not implement, and maps server dotted
  field paths back onto form keys.
- Rendering: null-safe `formatProbability` (an em dash, never a fabricated zero), all
  five outcome classes in the bar and legend, evidence cohort with sample size and
  fallback labelling, group assumption always visible, provenance block shown even
  when everything abstains.
- Accessibility: `role="status"` removed from static badges, one announcement per
  spinner, `aria-invalid`/`aria-describedby` on inputs, rows keyed by stable ids, the
  add-passenger control kept visible and disabled at the limit with its reason, a skip
  link and a labelled nav.
- Privacy copy conditioned on the configured origin: the page names the address it
  posts to and only claims "on this machine" for a loopback URL.
- Vitest + Testing Library + jsdom configured; `npm test` added to the CI frontend job.

### Checks run and results

- `npm test` → **81 passed** across 4 files (validation, statusUtils, api, contract rendering).
- `npm run type-check` → 0 errors. `npm run lint` → no warnings or errors.
- `npm run build` → compiled, 6/6 static pages generated.
- **Browser verification against both running servers** (`uvicorn` on `127.0.0.1:8000`,
  `next dev` on `:3123`, backend CORS configured for that origin):
  - abstaining state: `OPTIONS` preflight 200, `POST /v1/predictions/manual` 200, page
    rendered "No estimate for this booking", reason code `no_trained_model`, both
    observed statuses visible with their raw strings, provenance block showing
    `no_model_v0` / `no_active_version` / `1.0.0`, and the registry limitation text.
  - supported state: with a temporary synthetic artifact promoted via
    `RAILCONFIRM_ACTIVE_MODEL_VERSION`, the same flow rendered 64.5% CNF, 19.1% RAC,
    10.0% WL, 5.5% CANCELLED, 0.9% OTHER, the legend summing to 100%, the basis line
    "Cohort SL / GN / WL — 105 historical records — exact status match", model version
    `smoke_v0`, registry `ready`, and the artifact's own limitations including the
    synthetic warning. The temporary artifact lived outside the repository and was
    deleted; nothing claiming approved real data was left behind.
- Two grammar defects were found only by looking at the rendered page
  ("1 of 1 passengers have", "Group outcomes (1 passengers)") and are now fixed and
  covered by tests.

### Remaining work

- No end-to-end browser test runs in CI; the flow above was verified by hand.
- The contract tests compare against fixtures copied from the backend schemas rather
  than against a running server, so a coordinated change to both sides can still pass.
- `/prediction/[id]` stays unimplemented until persistence exists.

## 2026-10-23 — Baseline training and target-event evaluation implemented

### Scope

Milestones D and E of the engineering directive: turn the documented evaluation protocol
into code that fits the historical-frequency baseline and scores held-out periods, without
letting a synthetic result become a user-visible probability. Decided in ADR-0011.

New: `backend/railconfirm/training/{__init__,__main__,dataset,fitter,metrics,report}.py`,
`backend/tests/training/` (74 tests), `backend/tests/support/datasets.py`,
`docs/adr/ADR-0011-…-target-event-evaluation.md`.
Changed: `inference/baseline.py` (`evaluation_only` provenance flag), and the status page,
evaluation protocol, backend README, changelog and ADR index.

### What was built

- **Fitting gate (`training/dataset.py`).** `load_approved_dataset` verifies the manifest
  against the file (re-hash and recount), requires an `approved` decision with a named
  reviewer, date and rationale, requires `licence_review_status: approved` **and**
  `allowed_uses.model_training: permitted`, and refuses rows that declare `is_synthetic`
  unless `allow_synthetic_for_testing` is passed. That opt-in copies the synthetic flag into
  the artifact, which the registry then refuses to serve, so the whole fit → evaluate →
  registry path is exercisable today with no route to a fabricated estimate.
- **Fit (`training/fitter.py`).** Cohorts counted from the training partition only, split
  must be eligible, the table validated through the same `normalize_frequency_table` gate
  inference uses, exclusions counted per reason, and `promotion: "candidate"` always.
- **Score (`training/metrics.py`).** Multiclass Brier and log loss against a
  training-period prevalence baseline, with skill, coverage, abstentions, per-class
  reliability bands, and segment scores carrying counts and `low_sample` flags. The
  estimator is the inference object, so the metric describes the code path that serves.
- **Target events (`TARGET_EVENTS`).** The product's headline number is the probability of
  an event, so each partition is also scored as that event: CNF for `final_chart_cnf`,
  CNF+RAC for `final_chart_cnf_or_rac`, with binary Brier, log loss, prevalence baseline,
  skill and reliability bands. `evaluate --target` replaced a hardcoded
  `final_chart_cnf`, and `--target` accepts only targets that have an event definition.
- **Report (`training/report.py`).** Deterministic JSON, `--generated-on` mandatory,
  conclusions derived from the measured verdicts, and `METRIC_KEYS` derived from the
  scorecard's own fields so a published number cannot lack a definition.

### The interesting result

On the synthetic fixture the distribution verdict and the event verdict disagree:

```
Validation: Brier 0.501038 vs baseline 0.500000 · skill -0.002076 · coverage 100.0% (40/40 rows)
            event 0.232664 vs baseline 0.250000 · skill 0.069343
```

The five-class score loses to the base rate while the CNF event narrowly beats it, because
smoothing spreads mass onto classes that never occur. Reporting only one of those numbers
would have flattered the configuration, so the report now prints both and adds: *"the
distribution and the target event disagree about beating the base rate, so neither number
alone describes this model."* Nothing here is evidence about railways — the fixture is
synthetic — but it is evidence that the reporting catches this class of mistake.

### Checks run and results

- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **461 passed**, total
  branch-inclusive coverage **95.78%** (training package: `metrics.py` 99%, `report.py` 97%,
  `__main__.py` 92%, `dataset.py` 95%, `fitter.py` 92%).
- `python -m ruff check railconfirm/ tests/` → all checks passed. `python -m mypy` → no
  issues in 35 source files.
- `python scripts/check_repository_hygiene.py` → passed.
- Real CLI runs in a temporary directory outside the repository
  (`python -m railconfirm.training fit … --report …`, then `evaluate …`): fit used 160 of
  160 training rows into 4 cohorts, wrote the candidate artifact, and printed the report
  above. `evaluate --target final_chart_cnf_or_rac` on a `final_chart_cnf` artifact exits 1
  with `Refused: Artifact is fitted for target 'final_chart_cnf_or_rac', not
  'final_chart_cnf'. …`.
- The fit → serve boundary was verified against the real registry using the fitted file:
  as written it resolves `not_promoted` / `no_trained_model`; after an operator edits
  `promotion` it resolves `data_not_approved` / `no_approved_data` because `is_synthetic` is
  still true; only falsifying `is_synthetic` to false makes it `ready`. That last step is
  forgery rather than a mistake, and it is why the artifact carries the dataset id and
  SHA-256 — recorded as a consequence in ADR-0011.
- Two defects my own code had before this session's tests: `_evaluate` hardcoded the target
  so a merged-target artifact could never be scored, and `main()` did not catch
  `ModelArtifactError`, so a rejected artifact would have raised a traceback instead of
  exiting 1. Both fixed and covered.
- Frontend checks were not re-run: no frontend file changed in this session.

### Remaining work

1. Intake a real candidate dataset (the only scientific blocker; everything below needs it).
2. Rolling-origin evaluation across multiple cutoffs — the protocol describes it, the code
   does a single cutoff.
3. Calibration fitting and its measurement (`calibrated` is always false; the report says so).
4. Dependence-aware group outcomes (ADR-0003) — the engine still uses the labelled
   independence baseline.
5. Persistence and prediction history (Milestone G), then `/prediction/[id]` in the frontend.

## 2026-10-23 — Dataset search conducted and recorded with evidence

### Scope

Milestone B. The project's one scientific blocker is the absence of a trainable dataset,
and until today that was stated as a gap without a record of what was actually looked for.
This session searched, inspected, and wrote the findings into
`docs/data/CANDIDATE_DATASET_REVIEW.md` and `docs/data/SOURCE_REGISTER.md`. **No dataset
was downloaded, ingested, manifested or approved.**

### What was verified

- Kaggle `aaryananil/indian-railway-ticket-confirmation` — metadata panel says `MIT`,
  903,874 bytes, updated 2024-08-14. Its own description states: *"This dataset is
  synthetically generated and does not represent real data."* Rejected: a licence to use it
  is not evidence about railways, and this repository already maintains its own labelled
  synthetic fixtures.
- Kaggle `bhavyarajdev/indian-railways-schedule-prices-availability-data` — `Apache 2.0`,
  7,026,565 bytes, updated 2023-12-13; the page says the content was collected by *"web
  scraping techniques"* from the IRCTC website in October 2023. Rejected for training: it
  holds schedules, fares and availability snapshots, not per-reservation final-chart labels,
  and the rights question depends on a third party's scraping that cannot be verified here.
- Kaggle `sripaadsrinivasan/indian-railways-dataset` — `CC0: Public Domain`, 17,170,333
  bytes; three JSON files (Stations, Trains, Schedules) credited to DataMeet. Reference
  metadata only — no outcome labels — so at best it would sharpen station and train
  validation, not unlock training.
- Its origin, `github.com/datameet/railways` — `gh api` reports `license: null`, contents are
  `README.md`, `stations.json`, `trains.json`, `schedules.json`, last pushed **2016-08-08**.
  The README does carry a `#### License` heading linking to a CC0 page, so the contributors
  asserted CC0, but GitHub sees no licence file and the assertion is by individuals
  describing data gathered from Indian Railways, not a rights holder. The collection-method
  note the README links (`sajjad.in/2016/08/…`) failed to fetch on 2026-10-23, so the
  gathering method could not be checked at all. Under review, not ingested.
- `https://www.data.gov.in/resource?…q=railway+reservation` returned **HTTP 403** to an
  unauthenticated automated fetch. This environment has no portal API key, so the national
  catalogue was not read. Recorded as a next step requiring a browser session or a key,
  not as a finding about its contents.

### What this changes about the plan

A trainable row needs the booked status **and** the verified final-chart outcome for the same
reservation, with journey and observation timestamps. Nothing found carries both. The two
realistic sources are a licensed data agreement with a railway/CRIS holder, or prospective
user-contributed observations with explicit consent — the latter is a product decision with
consent, retention and sampling-bias work attached, not a scraper. Training therefore stays
blocked, and `python -m railconfirm.training fit` will keep refusing until a named approval
exists. The honest consequence for scheduling: model-quality milestones cannot be sequenced by
writing more code; they are gated on a rights-and-data decision only the maintainer can make.

### Checks run

Documentation only. `python scripts/check_repository_hygiene.py` → passed (required docs
present, relative links resolve). No code changed, so the backend and frontend suites were
not re-run; the last recorded green CI for `main` is run `39890962780` at 461 tests.

## 2026-10-23 — Opt-in prediction history, and the defects only a running app shows

### Scope

Milestone G: persistence and prediction history, so `/prediction/[id]` — documented in the
frontend guide from the beginning and previously decoration — has something behind it.
Decided in ADR-0012. The design constraint that shaped everything: this is the one feature
that can store submitted ticket data, so it must be impossible to enable by accident.

New: `backend/railconfirm/storage/`, `backend/tests/storage/`,
`backend/tests/api/test_prediction_history.py`,
`frontend/src/app/prediction/[id]/page.tsx`,
`frontend/src/components/prediction/StoredPredictionReport.tsx`,
`docs/adr/ADR-0012-…`.
Changed: `api/app.py`, `api/problems.py` (new), `api/dependencies.py`, `api/v1/predictions.py`,
`api/v1/health.py`, `api/v1/schemas.py`, `config.py`, `domain/validation.py`, the frontend
types/client/form/result, `.gitignore`, `.env.example`, and the status, contract, storage,
security, frontend-guide and README documents.

### How it works

Two independent switches. `RAILCONFIRM_PERSIST_PREDICTIONS` (default false) decides whether
a server keeps history at all; `"persist": true` on the request decides whether one report
goes in. The response answers with `stored`, `report_url` and `retention_expires_at`, so the
client never has to infer a save from its own request. `GET /v1/predictions/{id}` returns the
stored response verbatim — nothing is recomputed, because a reopened report is evidence about
what was said then. Retention hides before it deletes: an expired id stops resolving
immediately, and `purge_expired()` removes the rows. `DENIED_KEYS` plus a PNR-shaped-value
scan run at the write, so a future field cannot begin storing a name or a PNR quietly. A
10-digit id on the reopen route is refused outright: that endpoint must not become a ticket
tracker by convenience.

### Five defects, all found by running it

`pytest` was green for every one of these. They surfaced when the real browser talked to the
real server, which is the reason this repository asks for both.

1. **Every real save was refused.** The store required `recorded_at >= prediction_at`. The
   form defaults the as-of moment to 24 hours ahead — a legitimate question — so the browser
   got `stored: false` and a refusal on every attempt. That ordering was my invention, not a
   product rule: the domain already validates `prediction_at` against the journey date and
   the observation times, which is where the leakage rule actually lives. Removed; retention
   runs from the save; a test now pins the future-as-of case.
2. **An unrouted path answered `{"detail":"Not Found"}`** instead of the documented
   `{error, details[], request_id}` envelope, making a contract sentence false for the
   commonest client mistake. A `StarletteHTTPException` handler now routes 404/405/5xx
   through the same envelope.
3. **`SQLite objects created in a thread can only be used in that same thread.`** The factory
   opens the store at startup; FastAPI serves on other threads. One shared connection behind
   a lock with `check_same_thread=False`, plus a six-thread write test.
4. **A naive timestamp was converted before it was checked** — `astimezone()` assumes local
   time for a naive value, which is the guess the store exists to refuse. Awareness is now
   checked first.
5. **`retention_expires_at` differed between the save and the reopen** (microseconds in
   memory, seconds on disk). Values are normalised through the format they are read back in.

### Checks run and results

- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **502 passed**,
  coverage **95.91%**; `ruff check` and `mypy` clean (38 source files).
- `npm test` → **93 passed** (5 files); `npm run type-check`, `npm run lint` clean;
  `npm run build` compiles and lists `/prediction/[id]` as a dynamic route.
- `python scripts/check_repository_hygiene.py` → passed.
- **Real HTTP** (`uvicorn` on `127.0.0.1:8033`, history enabled, retention 7 days): a request
  without `persist` → `stored: false`, nothing written; with `persist` → `stored: true`,
  `report_url`, expiry; reopen → every reported field identical to what was served; unsaved
  id → `404 not_found`; PNR-shaped id → `404 not_found` with the "not by a PNR" message;
  health → `{'enabled': True, 'retention_days': 7, 'stored_reports': 1}`. A second server
  process on the same file reopened the first one's report, which is the check that the
  database, not the process, is the record.
- **Real browser** (`next dev` on `localhost:3123`): ticked "Keep this report", submitted,
  and the result page rendered "Kept on this machine. Reopen it later at this report —
  retrievable until 30 Oct 2026, 09:20 IST". Following the link showed the stored report with
  the "as it was served" banner, `no_model_v0`, `no_active_version` and the abstention reason.
  An invented id rendered "Report not available" with the never-stored-or-aged-out wording and
  the request id, plus Try again / Start a new estimate.
- The first browser attempt is how defect 1 was found: the page showed no saved banner because
  the backend had refused the save, and the reason was in the response's `limitations`.

### Remaining work

1. Intake a real candidate dataset — unchanged, still the scientific blocker
   (`docs/data/CANDIDATE_DATASET_REVIEW.md` records the 2026-10-23 search).
2. A label-feedback route: history makes "what did the chart actually say?" possible, but
   collecting that needs its own consent, retention and sampling-bias design (ADR-0012 lists
   it as a consequence, not as a next step to code up now).
3. Per-row deletion and any authenticated access boundary, both deferred until history could
   be enabled by default or exposed beyond one machine.
4. Rolling-origin evaluation, calibration fitting, dependence-aware group outcomes.

### Follow-up: CI caught what local mypy could not

The first push of this work (`0bfcd54`) failed CI run `39899559995` at the type-check step:

```
railconfirm/api/app.py:199: error: "FastAPI" has no attribute "add_event_handler"  [attr-defined]
```

The same tree passed `mypy` locally. The difference is the resolved library, not the
checker: local `fastapi 0.135.1` / `starlette 0.52.1` still expose the deprecated
shutdown-event API in their type surface, while the newer starlette CI installs no longer
does. ADR-0010 keeps runtime libraries on ranges deliberately, so this is that decision's
cost arriving on schedule rather than a new problem.

Fixed forward in `4c867bf` by using the supported mechanism — an async `lifespan` attached
to the application closes the store — which exists in both versions. Behaviour is
unchanged; the deprecated call is gone rather than suppressed with an ignore comment,
because an ignore would go stale the moment the local environment catches up.

CI run `39899994841` on `4c867bf`: **success** — backend 502 passed at 95.86% branch
coverage, ruff and mypy clean; frontend 93 passed, type-check, lint and build clean;
documentation and hygiene job clean. The one remaining pytest warning is upstream
(`StarletteDeprecationWarning` from `fastapi.testclient`'s own import), not from this code.

## 2026-10-23 — The training gate enforces eligibility, and one as-of status spans fit, score and serve

### Scope
Two audit findings on the same theme: the pipeline reported more discipline than it
enforced. First, `training/dataset.py` tested `report.structurally_valid` and handed on
the **original frame**, so technically ineligible files and validator-rejected rows both
reached fitting and scoring. Second, the baseline was keyed by `initial_status` while
evaluation and the engine queried `current_status`, so metrics described a lookup the
product never performs. Nothing was claimed fixed without reproducing it first.

### What was reproduced before changing anything
- `load_approved_dataset()` accepted a 32-row file carrying `contradictory_labels`,
  `censored_label`, `unparseable_date`, `observation_after_journey`,
  `invalid_train_number`, `missing_required_value`, `unknown_initial_status` and
  `exact_duplicate_row` rejections, and returned all 32 rows: `len(frame)` was 32 while
  the same report said `valid_rows = 23`.
- `fit_cohorts()` counted a booked-`GNWL/40`-observed-`RAC 2` row into the `WL` cell while
  `score_partition()` and `InferenceEngine` asked for the `RAC` cell. Nothing in the
  artifact recorded which column its keys came from, so the mismatch survived a reload.
- The evaluation report published all eight `FEATURE_COLUMNS` under one availability
  sentence although the estimator reads three.

### Decisions (ADR-0013)
- **Decide the verdict and the rows in one pass.** `assess_dataset()` returns
  `(report, usable_frame)`; `validate_dataset()` stays the report-only wrapper.
  Re-filtering inside each consumer would let the counts and the data drift apart. The
  frame's index is reset internally — a caller-supplied index with duplicate labels made
  the per-row duplicate lookup ambiguous, which is a latent crash, not a theoretical one.
- **Training requires technical eligibility.** Any eligibility finding is now a refusal
  that quotes the findings. Blocker order is manifest verification → structural validity →
  human permission rules → eligibility, so a rejected licence is still reported as a
  rejected licence rather than as a quality problem.
- **One relaxation, tied to the data and written down.** Fitting below the thresholds needs
  rows declaring `is_synthetic` *and* `allow_synthetic_for_testing`; the flag alone cannot
  rescue real data. The relaxation is recorded on `ApprovedDataset` and lands in the
  artifact's limitations. Synthetic detection still reads the whole file before filtering,
  so a marker living only on a rejected row cannot make the rest of a file look like
  evidence.
- **One as-of status.** `preprocessing.asof_statuses()` — `current_status` when the source
  recorded one, `initial_status` otherwise, an unmappable value left `UNKNOWN` — is called
  by the fitter, the scorer, and (through `StatusObservation`) the served request. A blank
  later look means no later look existed, not that the status became unknown.
- **Artifacts declare their contract.** `cohort_semantics` (`asof_status_v1`) and
  `features_used` (`class_code, quota_code, asof_normalized`) are required at load, so a
  table built on another rule is refused with an explanation instead of serving
  wrong-population numbers. `artifact_format` becomes `railconfirm.frequency-baseline/2`;
  ADR-0009's status line points at ADR-0013 for that one identifier and its decision
  otherwise stands.
- **Feature schema 3.0.0.** `obs_normalized`/`obs_position` became `asof_normalized`/
  `asof_position` and the fallback changed meaning, so the version was bumped rather than
  letting an old artifact be read under new semantics.
- **Reports say what is unused.** The report publishes `used_by_estimator`,
  `not_used_by_estimator`, `cohort_semantics` and which status columns the fit had, and
  segments are reported for the booked status *and* the as-of status — the gap between
  those two is where a keying mistake would hide.

### Files
`backend/railconfirm/data/{__init__,preprocessing,validator}.py`,
`backend/railconfirm/inference/{artifacts,baseline,engine}.py`,
`backend/railconfirm/training/{__main__,dataset,fitter,metrics,report}.py`;
tests `data/test_preprocessing.py`, `data/test_validator.py`, `inference/test_baseline.py`,
`inference/test_registry.py`, `support/datasets.py`, `training/test_cohort_parity.py` (new),
`training/test_dataset_gate.py`, `training/test_fitter.py`, `training/test_report.py`,
`training/test_cli.py`;
docs `adr/ADR-0013-*.md` (new), `adr/ADR-0009-*.md` (status note), `adr/README.md`,
`data/DATA_CONTRACT.md`, `data/DATASET_INTAKE_CHECKLIST.md`,
`research/EVALUATION_PROTOCOL.md`, `technical/INFERENCE_AND_GROUP_PROBABILITIES.md`,
`architecture/API_CONTRACT.md`, `PROJECT_STATUS.md`, `AGENT_HANDOFF.md`, plus `README.md`,
`backend/README.md` and `CHANGELOG.md`.

### Checks run
- `python -m pytest tests --cov=railconfirm --cov-fail-under=90` → **563 passed**, coverage
  **96.03%**, gate satisfied.
- `python -m ruff check railconfirm tests` → **All checks passed!**
- `python -m mypy` → **Success: no issues found in 38 source files** (local libraries; CI
  resolves newer ones, so the pushed run is checked separately).
- `npm run type-check && npm run lint && npm test && npm run build` in `frontend/` → lint
  clean, **93 passed (5 files)**, build exit 0. The frontend was not touched by this change;
  run to confirm no contract drift.
- `python scripts/check_repository_hygiene.py` → exit 0, "22 required files, 201 tracked
  files scanned".
- `python -m railconfirm.data validate tests/fixtures/synthetic_dataset.csv` → exit **1**
  (not technically eligible), unchanged.

### Pipeline exercised on labelled synthetic fixtures
- `railconfirm.data validate` on the moving fixture → structurally valid, technically
  eligible, 240 rows, 12 distinct journey dates, 240 distinct labelled bookings.
- `railconfirm.training fit … --allow-synthetic-for-testing` → exit 0. Printed
  `Validation kept 240 of 240 rows (no rejections).`, wrote a `promotion: "candidate"`
  artifact with 6 cohorts, and the report stated
  `Cohorts: keyed by asof_status_v1 from initial_status + current_status; read by the
  estimator: class_code, quota_code, asof_normalized; derived but not read: init_normalized,
  init_position, asof_position, queue_ratio, lead_days`. Validation Brier 0.503704 vs
  baseline 0.500000; event 0.251111 vs 0.250000, and the conclusions say both do not beat
  the base rate. **No railway claim: these are synthetic rows.**
- The original pipeline fixture re-fit to the numbers already documented (Brier 0.501038 vs
  0.500000; event 0.232664 vs 0.250000), which is the expected result: it records no
  `current_status`, so its as-of status is its booked status.
- `fit` on a 32-row file with one of every rejected shape printed the per-reason accounting
  (`9 rejected: censored_label=1, contradictory_labels=2, exact_duplicate_row=1, …`) plus
  the relaxation notice, and the artifact it wrote carries a limitation saying intake was
  not met.
- `fit` on the same shape **without** `is_synthetic` → exit 1: `Refused: Dataset is
  structurally valid but not technically eligible for training:` followed by the three
  findings. Re-run **with** `--allow-synthetic-for-testing` → the identical refusal.
- `evaluate` on the labelled synthetic artifact → exit 0 with both partitions scored; the
  registry still refused the same artifact for serving (`not_promoted`, and
  `data_not_approved` after promotion and version were hand-flipped in a temp copy).

### Application runtime
`uvicorn railconfirm.api.app:app --port 8041` with `RAILCONFIRM_MODELS_DIR` set to a
**temporary, never-committed** probe artifact fitted from the labelled synthetic fixture
(its flags set so the registry would serve it, its limitation text stating plainly that it
is a runtime probe and not railway evidence). `GET /v1/health` reported
`model_available: true, registry_status: ready`. `POST /v1/predictions/manual` with three
passengers all booked `GNWL/40`:

| current_status | served cohort | `p_cnf` | expected from the fitted cell |
|---|---|---|---|
| `RAC 2` | `cohort=SL/GN/RAC n=40 exact_status_match=true` | 0.4666667 | 21/45 |
| `GNWL/40` | `cohort=SL/GN/WL n=80 exact_status_match=true` | 0.4823529 | 41/85 |
| `MYSTERY/4` | — | `null`, `abstention_reason: unknown_status` | abstain |

`feature_schema_version` reported `3.0.0` and `evidence_coverage: partial`. Before this
change, the first row would have been answered from the `WL` cell. The server was stopped
and the temp directories deleted afterwards.

### Open
- The dataset blocker is unchanged and is not a code problem: no candidate carries both a
  reservation's booked status and its verified final-chart outcome under training permission
  (`docs/data/CANDIDATE_DATASET_REVIEW.md`).
- `asof_statuses()` inherits whatever `observation_date` means in a real file. A source
  that publishes `current_status` after the chart would leak through a rule this repository
  cannot see, so intake review must pin the publication time per source; the validator only
  enforces `observation_date <= journey_date` today.
- `features_used` is a per-estimator declaration. A future estimator needs its own
  vocabulary and `ESTIMATOR_*` value, not a widened constant here.
- Existing `/1` artifacts would now be refused. None exist in the repository or in any
  documented deployment, so nothing was orphaned.

## 2026-10-23 — Rolling-origin evaluation: the pipeline now refuses a single cutoff

### Scope
The next gap the project's own protocol named: `docs/research/EVALUATION_PROTOCOL.md` said
rolling-origin evaluation "must be added before any result is called temporally robust",
and `docs/AGENT_HANDOFF.md` listed it as a task. ADR-0011 had postponed it because it
"needs a dataset long enough for several cutoffs" — which is true of the *result* and
false of the *tool*: if the multi-cutoff path only gets written after the data lands, the
first run on approved data is the one most likely to be quoted, and it would be one cutoff.
This revises that reasoning (ADR-0014), on labelled synthetic fixtures only.

### Decisions (ADR-0014)
- **Whole-date expanding cutoffs, planned before any fitting.** `rolling_origin_windows()`
  takes `min_train_dates` dates to start, scores the next `horizon_dates`, advances by
  `step_dates`, optionally separated by `gap_days`. Dates, never rows, so a record cannot
  straddle a cutoff; ambiguous dates raise exactly as in `chronological_split`.
- **Fewer than two usable origins is refused, not averaged in.** `MIN_ORIGINS = 2`; a plan
  that yields one returns **no windows** with a reason naming the date count, and
  `run_rolling_origins()` raises instead of scoring a partial plan. One measurement under a
  plural name is the misleading case the command exists to prevent.
- **`step_dates >= horizon_dates` is required, and it makes double-counting impossible with
  one rule.** Every earlier horizon sits inside every later training block, so a booking
  appearing in two scored windows necessarily straddles the later cutoff — the crossing
  check already refuses it. An added "scored twice" check was written, found unreachable,
  and removed rather than left as decoration.
- **Each origin refits, and each origin gets its own baseline.** `fit_cohorts` → cohorts +
  prevalence → `build_estimator` → `score_partition`, all the same functions the
  single-cutoff path uses. Consequences stated in the report: the method line is
  `refit-per-origin, score-the-next-horizon` (this measures the fitting procedure across
  time, not one frozen artifact's decay), baselines differ by construction, overlapping
  windows are not independent evaluations, and no multiplicity correction is applied.
- **Origins that scored nothing are counted apart from origins that lost.**
  `origins_with_scores` sits beside `origins_beating_baseline`; conclusions are written
  against the scoring origins, and an all-abstention run says "No origin measured anything
  … this run is evidence about coverage, not about accuracy" instead of implying a loss.
- **The spread is the finding.** Conclusions report all/none/some beating, the Brier range
  and the coverage range. `--report` requires `--generated-on` and is byte-reproducible.

### Files
New: `backend/railconfirm/training/origins.py`,
`backend/tests/data/test_rolling_origins.py`, `backend/tests/training/test_origins.py`,
`docs/adr/ADR-0014-rolling-origin-evaluation-with-per-cutoff-refitting.md`.
Changed: `backend/railconfirm/data/preprocessing.py` (window planner),
`backend/railconfirm/training/{report,__main__,__init__}.py`,
`backend/railconfirm/data/__init__.py`, `backend/tests/training/test_cli.py`,
`docs/research/EVALUATION_PROTOCOL.md`, `docs/adr/README.md`, `docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`, `README.md`, `backend/README.md`, `CHANGELOG.md`.

### Checks run
- `python -m pytest tests --cov=railconfirm --cov-fail-under=90` → **611 passed**, coverage
  **96.30%**; `railconfirm/training/origins.py` at 100%, `report.py` 97% (remaining gaps are
  pre-existing single-cutoff branches).
- `python -m ruff check railconfirm tests` → **All checks passed!**
- `python -m mypy` → **Success: no issues found in 39 source files**.
- `python scripts/check_repository_hygiene.py` → exit 0, "22 required files, 205 tracked
  files scanned".
- 44 new tests: the planner (boundaries grow by the step, no origin scores a date it
  trained on, horizons disjoint, row order cannot move a boundary, scarce horizon /
  unhonourable gap / single origin / straddling booking each refuse with reasons, ambiguous
  dates raise, argument rules raise, no frames in `to_dict`); the run (hand-checked cells —
  origin 0's four-CNF block gives baseline 2.0 against model 92/81, origin 1's 4-CNF/2-WL
  block gives 2/9 against 48/121, mean and spread match; a threshold only one horizon
  clears yields "1 of 2 origins produced no score at all" plus a coverage range; a
  both-waitlisted fixture yields "All 2 scoring origins beat…"; one cutoff refuses; an
  unfittable window names "Origin 0 (2026-02-01..2026-02-02)"; the merged target scores
  6/9 mass; reports are byte-stable); the CLI (nine-origin run writes a report, single
  cutoff exits 1, missing `--generated-on` exits 1, an ineligible real file exits 1).

### Pipeline exercised on labelled synthetic fixtures
- `python -m railconfirm.training origins synthetic-moving.csv … --min-sample-threshold 1
  --allow-synthetic-for-testing --report … --generated-on 2026-10-23` → exit 0, **9 origins
  over 12 journey dates, all 9 producing a score**. Printed:
  `Aggregate over 9 origin(s), 9 of which produced a score: mean Brier 0.958270 vs baseline
  0.607018, 1/9 beat it`, `event 0.473334 vs baseline 0.303509, 2/9 beat it`,
  `rows scored 180 of 180`, `Brier ranged 0.503704 to 1.632000 across origins`, and the
  conclusion that the distribution verdict "is not stable across cutoffs and one cutoff's
  number should not be quoted as the result".
- This is the concrete argument for the feature: the single-cutoff run on the same file
  reports Brier 0.503704 against 0.500000 — one number that reads as "barely loses" — while
  across nine cutoffs the same method ranges up to 1.632000 and beats the base rate at one
  of nine. **Synthetic rows: neither figure says anything about railways.**
- Repeating the run produced a byte-identical report (`cmp` clean), which is what
  `--generated-on` exists to guarantee.
- A six-date file asked for a five-date training block → exit 1:
  `Refused: Cannot run rolling-origin evaluation: - Only 1 origin usable from 6 distinct
  journey_date values…`, after the same run printed its intake accounting and the synthetic
  relaxation notice.

### Open
- Rolling-origin evaluation has never run on approved real data, and the current intake
  floor of four distinct journey dates only supports two origins with the defaults — a
  real temporal claim needs a longer file, which is now an explicit intake requirement in
  `docs/AGENT_HANDOFF.md`.
- Not implemented: calibration fitting (ADR-0004), and scoring one *frozen* artifact against
  successive horizons, which is a different question from the refit-per-origin run and would
  need its own method declaration.
- Per-origin results are unweighted. Weighting by horizon rows is a decision for when real
  row counts exist, not a default to add now.

## 2026-10-23 — History listing and per-report deletion

### Scope
Extended prediction history (ADR-0012) with a list route, a delete route, and a frontend
history page, completing ADR-0015. The previous session's uncommitted work was verified
clean before committing.

### Added
- `GET /v1/predictions` — lists stored report summaries (id, target, model version, clocks)
  without payload; answers 404 with `history_disabled` when the store is off so a client
  cannot mistake "nothing kept" for "storage disabled".
- `DELETE /v1/predictions/{id}` — hard-deletes one report; absent, expired, and already-
  deleted answer identically (same 404 body) so the route cannot be used to probe what this
  machine holds. PNR-shaped ids are refused the same way the GET route refuses them.
- `PredictionStore.delete()` — removes the named row and returns whether anything was
  removed; a blank id returns False rather than raising.
- `PredictionStore.summaries()` — newest first with a stable id tie-break; excludes rows
  past retention; carries no payload (asserted by scanning the serialised list for
  probability and status keys).
- `PRAGMA secure_delete = ON` on the SQLite connection — freed pages are zeroed on delete;
  the limitation (WAL side-file, filesystem snapshot) is documented rather than overstated.
- `StoredReportSummary` / `StoredReportsResponse` schemas in `api/v1/schemas.py`.
- `frontend/src/app/history/` — history page listing kept reports with two-step deletion
  confirmation (first click shows Confirm, second issues DELETE, Keep it escapes).
- `frontend/src/components/prediction/HistoryList.tsx` — loading, listed, empty, disabled
  and failed states; a refused or network-failed delete leaves the report listed.
- `frontend/src/components/layout/Header.tsx` — History nav link.
- Three new `StoredPredictionReport` tests covering the two-step deletion flow.
- `docs/adr/ADR-0015-history-listing-and-per-report-deletion.md`.
- API contract updated with the two new routes.

### Checks run
- `python -m pytest tests/ -x --tb=short -q` → **633 passed in 35.16 s** (exit 0).
- `python -m ruff check .` → **All checks passed!** (exit 0).
- `python -m mypy railconfirm/` → **Success: no issues found** (exit 0).
- `npm test -- --run` (frontend) → **6 test files, 113 tests, 0 failed** (exit 0).
- `npx tsc --noEmit` (frontend) → clean (exit 0).
- `npm run lint` (frontend) → **No ESLint warnings or errors** (exit 0).
- `npm run build` (frontend) → **Compiled successfully**, 7 static pages generated (exit 0).

### Files
New: `docs/adr/ADR-0015-history-listing-and-per-report-deletion.md`,
`frontend/src/app/history/` (page.tsx, loading.tsx),
`frontend/src/components/prediction/HistoryList.tsx`,
`frontend/src/components/__tests__/historyList.test.tsx`.
Changed: `backend/railconfirm/api/app.py`,
`backend/railconfirm/api/v1/predictions.py` (list + delete routes),
`backend/railconfirm/api/v1/schemas.py` (summary/response types),
`backend/railconfirm/storage/__init__.py` (StoredSummary export),
`backend/railconfirm/storage/predictions.py` (delete, summaries, secure_delete),
`backend/tests/api/test_contract.py` (history routes contract),
`backend/tests/api/test_prediction_history.py` (list, delete, metadata-only assertions),
`backend/tests/storage/test_predictions.py` (delete, summaries, secure_delete),
`frontend/src/components/__tests__/storedReport.test.tsx` (deletion confirmation),
`frontend/src/components/layout/Header.tsx`,
`frontend/src/components/prediction/StoredPredictionReport.tsx` (delete trigger),
`frontend/src/lib/__tests__/api.test.ts`,
`frontend/src/lib/api.ts` (listPredictions, deletePrediction),
`frontend/src/lib/types.ts`,
`docs/adr/README.md`, `docs/architecture/API_CONTRACT.md`.

### Open
- `purge_expired()` has no scheduler in the local-first build; rows past retention are
  hidden and unreadable but occupy disk until an operator purges them or a per-report delete
  clears one. This is ADR-0012's recorded position, unchanged.
- No new access boundary: the list and delete routes are unauthenticated like every other
  route in the local-first build (CORS allowlist limits which origins). Multi-user history
  would require authentication; that is ADR-0012's stated consequence.

## 2026-10-23 — Dependent group outcomes, Poisson-binomial distribution, queue bounds, and group evaluation

### Scope
Addressed the group outcome and evaluation gaps identified in roadmap Phase 6 and ADR-0003:
computing exact multi-passenger outcome distributions ($P(K = k)$ and $P(K \ge k)$),
modeling sequential queue-clearing comonotonic bounds under Indian Railways FIFO queue rules,
and evaluating multi-passenger group events in `score_partition()`. Decided in ADR-0016.

### Implemented
- **Exact Poisson-binomial PMF and tail probabilities (`backend/railconfirm/inference/group.py`):**
  Added `compute_poisson_binomial_pmf()` implementing exact $O(n^2)$ dynamic programming
  convolution of passenger marginal probabilities. Extends `compute_group_outcomes()` to populate
  `p_at_least_k_cnf` and `p_exactly_k_cnf` on `GroupOutcome`.
- **Sequential queue-clearing comonotonic bounds (`backend/railconfirm/inference/group.py`):**
  Added `compute_queue_dependent_bounds()` modeling Indian Railways FIFO waitlist queue clearance,
  yielding the Fréchet-Hoeffding comonotonic upper bound ($P_{\text{all CNF}} = \min_i p_i$,
  $P(K \ge k) = p_{(k)}$) where lower-priority passengers confirm only if higher-priority
  passengers confirm. Both methods enforce probability axioms ($\sum P(K=k) = 1.0$,
  $P(\text{all CNF}) = P(K=n) = P(K \ge n)$) and declare their assumptions.
- **Group event scoring in offline evaluation (`backend/railconfirm/training/metrics.py`):**
  Added `GroupScorecard` and group-level scoring in `score_partition()`. When `booking_group_id`
  is present in the evaluated partition, tracks total, single-passenger, and multi-passenger
  groups, scores both the independence baseline and queue comonotonic bounds against observed
  joint outcomes (`all_cnf`, `all_cnf_or_rac`, `at_least_one_wl`) using Brier scores, and
  evaluates group skill against group prevalence baselines.
- **Evaluation report formatting (`backend/railconfirm/training/report.py`):**
  Extended partition summary lines to include group Brier scores and skill when groups are present.
- **API and Frontend schemas & UI (`backend/railconfirm/api/v1/`, `frontend/src/`):**
  Exposed `p_at_least_k_cnf` and `p_exactly_k_cnf` on `GroupOutcomeResponse`. Updated
  `frontend/src/components/prediction/GroupOutcomeCard.tsx` to display confirmed berths distribution
  grid ($P(\ge k \text{ passengers confirmed})$) for multi-passenger groups and support queue
  comonotonic method labels.

### Checks run and results
- `pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **640 passed** in 94.09s, **96.21%**
  branch coverage (coverage gate satisfied).
- `ruff check .` → **All checks passed!**
- `mypy railconfirm/` → **Success: no issues found in 39 source files**.
- `npm test -- --run` → **115 passed** across 6 test files.
- `npx tsc --noEmit` & `npm run lint` → clean (0 errors, 0 warnings).
- `npm run build` → compiled successfully, 7 static pages generated.
- `python scripts/check_repository_hygiene.py` → **passed** (22 required files, 210 tracked files scanned).

### Files
New: `docs/adr/ADR-0016-dependent-group-outcomes-and-group-event-evaluation.md`.
Changed: `backend/railconfirm/api/v1/predictions.py`,
`backend/railconfirm/api/v1/schemas.py`,
`backend/railconfirm/domain/prediction.py`,
`backend/railconfirm/inference/group.py`,
`backend/railconfirm/training/metrics.py`,
`backend/railconfirm/training/report.py`,
`backend/tests/inference/test_group.py`,
`backend/tests/training/test_metrics.py`,
`frontend/src/components/__tests__/contract.test.tsx`,
`frontend/src/components/prediction/GroupOutcomeCard.tsx`,
`frontend/src/lib/types.ts`,
`docs/adr/README.md`,
`CHANGELOG.md`,
`docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`.

## 2026-10-24 — Logistic calibration that has to earn its place, and the sentence it contradicted

### Scope
Closed the calibration gap the handoff listed under "does not exist": a probability could be
counted and smoothed but never corrected, and an artifact could claim `calibrated: true` with
nothing behind the claim. Decided in ADR-0017. Synthetic fixtures only — no approved dataset
exists, so nothing here is a railway result.

### Reproduced before changing anything
- A successful calibrated `fit` printed `Smoothed historical frequencies, not a trained or
  calibrated model.` **and** `Probabilities are calibrated — platt_logistic_v1 ...` in the same
  limitations block. Found by reading the live output, not by a test.
- The calibration summary line used `→`. On this machine's Windows console a finished `fit` raised
  `UnicodeEncodeError` **after** writing the artifact, and pytest never saw it because it captures
  its own stream instead of the console the CLI writes to.

### Implemented
- `backend/railconfirm/inference/calibration.py` — `CalibrationSpec`, `logit`/`sigmoid` and
  `apply_calibration`, which rescales the target event's mass and redistributes the remainder
  proportionally so every distribution still sums to 1. Certainties and abstentions pass through
  unchanged.
- `backend/railconfirm/training/calibration.py` — `fit_platt` (Newton–Raphson on the validation
  rows, 100 iterations, tolerance 1e-10) refusing too few rows, one label, no spread in the
  predictions, certainties dropping the usable count below the floor, a prediction outside
  `[0, 1]`, a singular Hessian from separable evidence, non-convergence and a negative slope; plus
  `fit_and_measure`, which embeds only on a strict validation improvement and always reports the
  locked-test movement.
- `training/metrics.py` — `score_rows`/`score_partition` take `calibration=` and record
  `calibration_applied`, so evaluation scores the arithmetic serving uses.
- `training/fitter.py` — `with_calibration` attaches the spec and **replaces** the uncalibrated
  limitation sentence with `CALIBRATED_LIMITATION`, which still says the numbers are cohort counts.
- `inference/artifacts.py` — `metadata_from_mapping` refuses a bare `calibrated: true`, a block on
  an uncalibrated artifact, a method or target disagreement, a negative or non-finite slope and a
  partial block. `artifact_format` stays `/2`, because the block is optional and its absence has
  exactly one meaning.
- `inference/engine.py` — serves through the same `apply_calibration`; `basis` gains
  `calibrated=platt_logistic_v1`, and the limitations branch follows the block that actually loaded.
- `training/__main__.py` — `fit --calibrate [--calibrate-min-rows N]` prints
  `validation event Brier X -> Y; locked test A -> B (helped / did not help)`; `evaluate` prints
  `calibration applied (platt_logistic_v1)` or `uncalibrated`. ASCII arrows throughout.

### Live runs (labelled synthetic fixtures written to the OS temp directory; nothing committed)

```
$ python -m railconfirm.training fit synthetic-balanced.csv synthetic-balanced-fixture.yaml \
    --version cal_v1 --out cal_v1.json --report cal_v1-report.json \
    --generated-on 2026-10-24 --calibrate --calibrate-min-rows 10 --allow-synthetic-for-testing
Validation kept 240 of 240 rows (no rejections).
Calibration: platt_logistic_v1 on final_chart_cnf (CNF) from 40 validation rows
  (2026-04-09..2026-04-10): slope 3.124728, intercept 1.016226
  validation event Brier 0.240085 -> 0.239898; locked test 0.23996 -> 0.239487 (helped)
exit 0

$ python -m railconfirm.training evaluate synthetic-balanced.csv \
    synthetic-balanced-fixture.yaml --artifact cal_v1.json --target final_chart_cnf \
    --allow-synthetic-for-testing
Artifact cal_v1 · dataset synthetic-balanced-fixture · target final_chart_cnf ·
  calibration applied (platt_logistic_v1)
  validation Brier 0.481401 (baseline 0.48), event Brier 0.239898 (baseline 0.24)
  test       Brier 0.480359 (baseline 0.48), event Brier 0.239487 (baseline 0.24)
exit 0

$ python -m railconfirm.training fit ... --calibrate --allow-synthetic-for-testing   # default floor
Refused: Cannot fit calibration on 40 validation rows: at least 50 are needed before a
slope and an intercept mean anything. Widen the validation period or leave the artifact
uncalibrated.
exit 1, and no artifact written

$ python -m railconfirm.training fit <900-row fixture> ... --calibrate
Refused: The fitted slope is negative (-13.829494): on the validation rows the event becomes
less frequent as the predicted probability rises. That is noise being fitted, not a
calibration layer, so no correction is written.
exit 1
```

The two refusals carry the weight: the same code that embeds a correction on one window refuses a
larger window whose validation labels happen to run against the slope. The improvement it did
accept is 0.000187 on validation and 0.000473 on the locked test — a mechanism check on synthetic
rows, not evidence about railways.

Registry gates on the fitted file, called directly:

```
ModelRegistry(models_dir=…, active_version='cal_v1').resolve(FINAL_CHART_CNF)
  -> not_promoted / no_trained_model      (promotion 'candidate')
after editing promotion to 'approved_for_local_use':
  -> data_not_approved / no_approved_data
     "Artifact cal_v1 was fitted from dataset 'synthetic-balanced-fixture'
      (approval='approved', synthetic=True); it may not serve estimates."
```

A synthetic calibrated artifact therefore stays unservable, and it is the synthetic-provenance
check — not only the candidate flag — that stops it.

Intake gate re-checked on the repository fixture:

```
$ python -m railconfirm.data validate tests/fixtures/synthetic_dataset.csv     # exit 1
  - Only 6 rows, below the provisional minimum of 200.
  - Only 6 usable rows, below the provisional minimum of 100.
  - 6 distinct labelled reservations; at least 40 are needed to evaluate a
    probability rather than count a table.
```

### Checks run and results
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **728 passed** in 173.58s,
  total coverage **96.32%** (exit 0).
- `ruff check railconfirm/ tests/` → **All checks passed!**
- `mypy` → **Success: no issues found in 41 source files**
- `npm test -- --run` → **115 passed** across 6 test files (exit 0).
- `npm run type-check` → clean; `npm run lint` → **No ESLint warnings or errors**.
- `npm run build` → compiled successfully; `/`, `/about/data`, `/about/methodology`, `/history`
  and `/prediction/[id]` all generated.
- `python scripts/check_repository_hygiene.py` → **passed** (22 required files, 214 tracked files).
- A serving probe earlier in this work ran `uvicorn` on port 8043 against a temporarily promoted
  copy of the calibrated artifact and returned `p_cnf 0.391304348` where the raw table gives
  `0.385416667`, with the basis naming `calibrated=platt_logistic_v1`. Scratch fixtures, the probe
  artifact and its models directory were deleted; nothing was added under `data/` or `models/`.

### Files
New: `backend/railconfirm/inference/calibration.py`, `backend/railconfirm/training/calibration.py`,
`backend/tests/inference/test_calibration.py` (28 tests),
`backend/tests/training/test_calibration.py` (40 tests),
`docs/adr/ADR-0017-logistic-calibration-fitted-on-validation-and-measured-on-the-locked-test.md`.
Changed: `backend/railconfirm/domain/prediction.py`, `inference/artifacts.py`, `inference/engine.py`,
`training/fitter.py`, `training/metrics.py`, `training/report.py`, `training/__main__.py`,
`backend/tests/inference/test_engine_artifact.py`, `backend/tests/inference/test_registry.py`,
`backend/tests/support/datasets.py`, `README.md`, `backend/README.md`, `CHANGELOG.md`,
`docs/PROJECT_STATUS.md`, `docs/AGENT_HANDOFF.md`, `docs/adr/README.md`,
`docs/architecture/API_CONTRACT.md`, `docs/research/EVALUATION_PROTOCOL.md`,
`docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`.

### Unresolved
- The dataset blocker is unchanged and was never a code problem: no candidate carries both a
  reservation's booked status and its verified final-chart outcome under training permission, so
  every number this pipeline produces still comes from synthetic rows.
- Calibration is fitted on one window and is not carried across rolling origins; subgroup
  calibration is not measured; and no frozen artifact has been scored against successive horizons.


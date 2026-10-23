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

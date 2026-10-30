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

## 2026-10-24 — Frozen-artifact decay: one table, judged further out (ADR-0018)

### Scope
ADR-0014 and ADR-0017 both ended with the same sentence: nothing here scores one *frozen*
artifact against successive horizons. `origins` refits the cohort table and its prevalence
baseline at every cutoff, which measures the fitting procedure. A promoted model in service is
the opposite situation — the table does not move, the calendar does. Built that measurement and
recorded the decision in ADR-0018.

### What the single-cutoff number was hiding
Before writing anything, the same estimator was scored two ways on the balanced synthetic
fixture. One cutoff reports `test event Brier 0.239487` against a `0.24` base rate: a win by
0.0005, and the kind of number a report would carry as "beats the baseline". Scored as three
successive two-date horizons against the same frozen table and the same frozen baseline, the
identical estimator produces `0.243482, 0.240300, 0.239411` and beats the base rate in **one of
the three**. Nothing about the arithmetic changed; the single number simply kept the ordering
secret. That is the reason this command exists before any real data does.

### Implemented
- `backend/railconfirm/data/preprocessing.py` — `frozen_horizon_windows()`,
  `FrozenHorizonPlan`, `HorizonWindow`, `MIN_HORIZONS = 2`. Whole-date horizons after the
  cutoff, `step_dates >= horizon_dates` so no outcome is scored twice, and **no windows at
  all** when fewer than two usable horizons exist. A `booking_group_id` spanning the cutoff
  refuses the entire plan rather than dropping rows from the side under test. Exported from
  `railconfirm.data`.
- `backend/railconfirm/training/decay.py` — `run_frozen_decay()`, `FrozenDecayResult`,
  `HorizonScore`, `frozen_decay_estimator()`, `describe_result()`. The cutoff comes from
  `metadata.trained_to`; the cohorts, threshold, smoothing and calibration block are the
  artifact's and are passed to `score_partition()` unchanged; the prevalence baseline is
  computed once from the fittable rows at or before the cutoff. Refusals: an artifact with no
  declared period, a plan the file cannot support, a frozen block with nothing fittable, a
  target with no defined event, and an artifact whose `cohort_semantics` or `features_used`
  differ from what this build serves.
- `backend/railconfirm/training/report.py` — `FrozenDecayReport`, `build_decay_report()`,
  `_decay_conclusions()`, `write_decay_report()`, `DECAY_REPORT_SCHEMA_VERSION`, and
  `DECAY_METRIC_DEFINITIONS` adding `prevalence`, `event_brier_drift` and `coverage_drift` to
  the scorecard definitions. Limitations state that the table and baseline were never refitted,
  where the baseline came from, that the horizons are not independent evaluations, and that a
  calibration block was fitted to one window. Conclusions are derived from the measured values,
  and a run where nothing was scored says so without using a word that could read as positive.
- `backend/railconfirm/training/__main__.py` — the `decay` subcommand
  (`--artifact`, `--horizon-dates`, `--step-dates`, `--gap-days`, `--min-scored-rows`,
  `--report`, `--generated-on`, `--target` checked against the artifact's declared target), and
  the module docstring now names three evaluation questions rather than two.

### Live runs (labelled synthetic fixtures in the OS temp directory, nothing committed)
```
$ python -m railconfirm.training fit synthetic-balanced.csv … --version decay_v1 \
    --train-frac 0.5 --val-frac 0.25 --min-sample-threshold 5 --allow-synthetic-for-testing
Wrote candidate artifact …decay_v1.json · Used 120 of 120 training rows · Cohorts: 4 · exit 0

$ python -m railconfirm.training decay synthetic-balanced.csv … --artifact decay_v1.json \
    --horizon-dates 2 --step-dates 2 --report decay-report.json --generated-on 2026-10-24 …
Frozen artifact decay_v1 (2026-04-01..2026-04-06, 4 cohorts, cutoff 2026-04-06)
  horizon 0 (2026-04-07..2026-04-08): Brier 0.489622 vs 0.480000, event 0.243482 vs 0.240000, coverage 100.0%
  horizon 1 (2026-04-09..2026-04-10): Brier 0.482206 vs 0.480000, event 0.240300 vs 0.240000, coverage 100.0%
  horizon 2 (2026-04-11..2026-04-12): Brier 0.480027 vs 0.480000, event 0.239411 vs 0.240000, coverage 100.0%
Drift across 3 horizons (3 scored): event Brier 0.243482 -> 0.239411 (-0.004071), coverage 1.000000 -> 1.000000
  event beat the frozen base rate in 1/3 scored horizons
exit 0

$ python -m railconfirm.training decay … --artifact cal_v1.json --horizon-dates 2 --step-dates 2 …
Frozen artifact cal_v1 (2026-04-01..2026-04-08, 4 cohorts, cutoff 2026-04-08)
  horizon 0 (2026-04-09..2026-04-10): event 0.239898 vs 0.240000, coverage 100.0%
  horizon 1 (2026-04-11..2026-04-12): event 0.239487 vs 0.240000, coverage 100.0%
  event beat the frozen base rate in 2/2 scored horizons
exit 0

$ python -m railconfirm.training decay … --horizon-dates 4 --step-dates 4 …   # 6 dates left
Refused: Cannot measure decay for artifact decay_v1 from synthetic-balanced-fixture:
  - Only 1 horizon usable after 2026-04-06 from 12 distinct journey_date values. A single
    future block is what ``chronological_split`` already provides; measuring decay needs at
    least 2, so no horizon was scored rather than reporting one point as a trend.
exit 1, and no report written
```
The calibrated run is the cross-check worth recording: its two horizons are the same rows the
earlier `fit --calibrate` measured as validation and locked test, and the numbers come out
identically (`0.239898`, `0.239487`). That is the correction being applied by one code path,
not a second implementation agreeing by luck.

### Checks run and results
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **802 passed** in 257.62s,
  total coverage **96.17%** (exit 0). New this session: 39 planner tests
  (`tests/data/test_frozen_horizons.py`) and 35 decay tests (`tests/training/test_decay.py`).
- `ruff check railconfirm/ tests/` → **All checks passed!** (after `--fix` reorganised the new
  test module's imports; three import-order findings, zero remaining).
- `mypy` → **Success: no issues found in 42 source files** (the first pass flagged
  `Sequence[str]` with `.append` in `describe_result`; the accumulator is now a `list[str]`).
- `python scripts/check_repository_hygiene.py` → **passed** (22 required files, 218 tracked
  files scanned for links, secrets and unlabelled ticket data), run after the documentation
  edits including this entry.
- Frontend gates re-run after the change: `npm test -- --run` → **115 passed** across 6 test
  files; `npm run type-check` clean; `npm run lint` → **No ESLint warnings or errors**;
  `npm run build` → compiled successfully, 7 static pages. No frontend file was touched by
  this work, so these are confirmation runs rather than regression tests of new UI.

### Files
New: `backend/railconfirm/training/decay.py`, `backend/tests/data/test_frozen_horizons.py`,
`backend/tests/training/test_decay.py`,
`docs/adr/ADR-0018-frozen-artifact-decay-across-successive-horizons.md`.
Changed: `backend/railconfirm/data/preprocessing.py`, `backend/railconfirm/data/__init__.py`,
`backend/railconfirm/training/report.py`, `backend/railconfirm/training/__main__.py`,
`README.md`, `backend/README.md`, `CHANGELOG.md`, `docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`, `docs/adr/README.md`, `docs/research/EVALUATION_PROTOCOL.md`,
`docs/DEVELOPMENT_LOG.md`.

### Unresolved
- Subgroup calibration is still unmeasured, and `decay` does not change that: it shows whether
  one population-wide correction holds later, not whether it holds inside a class or quota.
- Both temporal commands now need a dataset long enough to give two windows, which the current
  intake minimum of four distinct journey dates only barely supports. That is an intake
  requirement to raise with the reviewer, not a reason to relax a refusal.

## 2026-10-24 — Paired model comparison: the locked period decides, in both directions (ADR-0021)

### Scope
Roadmap Phase 4's exit gate reads "candidate evaluated on locked later journeys and compared
with baseline". ADR-0020 produced a candidate, and the repository still had no way to compare
two models: each could be fitted and scored on its own split, which answers nothing. Built the
comparison, so the promotion conversation has a number with a provenance instead of an opinion.

### Why the window that chose the candidate cannot judge it
Two purpose-built synthetic fixtures settled the design before any code was trusted:

- position-informative labels: the candidate **lost validation** (Brier `0.295680 → 0.366304`,
  delta `+0.070624`) and **won the locked period** (`0.375680 → 0.337007`, `-0.038673`; event
  `0.184984 → 0.156482`; 62 paired wins against 18 losses). A rule that read validation, or the
  better of the two, rejects a model that generalises.
- position-blind labels: the candidate's event score improved on validation while the locked
  period went backwards (`+0.172314` distribution, `+0.077057` event, 32 wins against 48
  losses). A rule that read the flattering window would promote noise.

Same code, opposite verdicts, each traceable to printed numbers. That is the mechanism being
demonstrated, not a result about railways.

### Implemented (tests first, 29 new tests)
- `backend/railconfirm/training/compare.py` — `pair_scores`, `PairedCount`,
  `PartitionComparison`, `decide_verdict`, `Verdict`, `run_model_comparison`,
  `MODEL_SELECTION_METHOD`, `describe_result`. Refusals before any arithmetic: different split
  partitions (name, boundaries, row counts), the same estimator on both sides, different
  targets, and two unequal prevalence baselines.
- Rows are paired by **partition position**, not by passenger identity. `ScoredRow` carries it,
  and both models walk the same frame in the same order, so the pairing survives the models
  abstaining on different rows. `only_baseline_scored`, `only_candidate_scored` and
  `neither_scored` are published; none of them counts as a win.
- The verdict is four conditions at once on the locked period — distribution Brier improved,
  event Brier improved, coverage not worse, paired wins strictly greater than losses — with each
  failure emitted as its own reason at its own numbers. No comparable rows, or a model that
  scored nothing there, yields `undetermined`.
- `training/metrics.py` — `score_partition(..., pre_scored=…)` so the aggregate card and the
  paired counts come from one pass over the rows. The first draft named that parameter
  `scored`, which already means "count of scored rows" inside the function; mypy caught the
  collision before any test could.

### One design point worth the argument
Coverage is a **condition**, not a footnote. A candidate that abstains more can improve every
average by dropping the rows it answers badly, so `coverage_delta < 0` disqualifies it however
good its scores look, and the reason says so. Pairing itself uses the target event's squared
error — the number a passenger is handed — while the distribution Brier must improve too, so a
win cannot be manufactured by moving mass inside the event's complement.

### Checks run and results
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **947 passed**, total
  coverage **96.17%** (exit 0). 29 of them new, in `tests/training/test_compare.py`.
- `ruff check railconfirm/ tests/` → **All checks passed!**
- `mypy` → **Success: no issues found in 44 source files**
- Live `compare` runs on both fixtures: exit 0, `Verdict: candidate` and `Verdict: baseline`
  respectively, each printing the locked-period line and its blocks. Fixtures and reports were
  written to the OS temp directory and deleted; nothing was added under `data/` or `models/`.
- Hygiene and the frontend gates are recorded in the next section, run after this entry.

### Files
New: `backend/railconfirm/training/compare.py`, `backend/tests/training/test_compare.py`,
`docs/adr/ADR-0021-paired-model-comparison-on-the-locked-period.md`.
Changed: `backend/railconfirm/training/metrics.py` (`ScoredRow.position`, `pre_scored`),
`backend/railconfirm/training/report.py`, `backend/railconfirm/training/__main__.py`,
`README.md`, `backend/README.md`, `CHANGELOG.md`, `docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`, `docs/adr/README.md`, `docs/research/EVALUATION_PROTOCOL.md`,
`docs/DEVELOPMENT_LOG.md`.

### Unresolved
- The comparison has never judged two models on real data, and cannot until a dataset clears
  intake. `min_band_rows` still has no CLI flag, and a McNemar-style significance test on the
  paired counts is deliberately deferred rather than invented after seeing results.

## 2026-10-24 — Subgroup calibration measured, and a floor on what may be claimed from it

### Scope
ADR-0017 closed by recording that subgroup calibration was not measured. That sentence was
honest and it was also the last remaining way this repository could say "calibrated" about a
population while knowing nothing about the cohorts it serves — and a served probability is
keyed by class, quota and as-of status, so the claim has always been about cohorts. Measured it,
and recorded the wording discipline in ADR-0019.

### Why the average is not the finding
One logistic correction moves every row's log-odds by the same rule, so two cohorts sitting on
opposite sides of the population mean can average out to an aligned headline while each stays
wrong. Reliability bands do not reveal this, because they pool classes: they answer "rows
predicted in the 0.3–0.4 band confirmed how often", across every cohort at once. The test that
pins the whole change is exactly that case — ten rows predicted 0.3 that all confirm, ten
predicted 0.7 that none do: population predicted 0.5 against observed 0.5, and segments sitting
at +0.7 and −0.7.

### Implemented
- `training/metrics.py` — `SegmentCalibration`, `segment_calibration()`,
  `MIN_SEGMENT_CALIBRATION_ROWS = 25`, and a `segment_calibration` field on every `Scorecard`.
  Sliced by the dimensions `score_partition` already segments by (`class_code`, `quota_code`,
  `asof_status`, `initial_status`), publishing `rows`, `mean_predicted`, `observed_rate`,
  `gap = observed − predicted` and `low_sample`.
- `training/report.py` — the metric definition, `_segment_calibration_line()` as a per-partition
  conclusion, the unconditional "no per-segment correction is fitted" limitation, and — when a
  layer is present — the statement that the gaps are that correction's residual error.
- Nothing in `inference/` changed: no new artifact field, no new abstention reason, and no
  probability moves. This is measurement on the evaluation side.

### Two things the design refuses
- **No per-cohort slope.** Cohorts are counted in the tens, and a correction whose provenance
  depends on a passenger's class is a lookup table with a claim attached. The gap is a
  measurement, not a proposal.
- **No claim below the floor.** `gap` is published for every segment, but a three-row cohort
  where all three confirmed is not a 33-point miscalibration — it is three rows. Segments under
  the scorecard's existing `min_segment_rows` are flagged and unusable, and when no segment
  clears the floor the conclusion says subgroup calibration cannot be claimed in either
  direction rather than quoting a thin cohort to fill the line.

### Caught by the repository's own rule
Adding a scorecard field failed `test_every_published_metric_is_defined_and_nothing_extra_is`
immediately — the check that no number may be published without a written definition. Two suites
red on the first run, and the fix was to define the field rather than to exempt it, which is the
outcome that test exists to produce.

### Live run (labelled synthetic fixture, in the OS temp directory, nothing committed)
```
$ python -m railconfirm.training fit synthetic-balanced.csv synthetic-balanced-fixture.yaml \
    --version segcal_v1 --out segcal_v1.json --report segcal-report.json \
    --generated-on 2026-10-24 --min-sample-threshold 5 --allow-synthetic-for-testing
exit 0 · validation population event Brier 0.240085 against a 0.240000 baseline

validation segment_calibration:
  asof_status=WL      rows=40  pred=0.388169 obs=0.400000 gap=+0.011831  low_sample=False
  initial_status=WL   rows=40  pred=0.388169 obs=0.400000 gap=+0.011831  low_sample=False
  quota_code=GN       rows=40  pred=0.388169 obs=0.400000 gap=+0.011831  low_sample=False
  class_code=3A       rows=17  pred=0.391892 obs=0.411765 gap=+0.019873  low_sample=True
  class_code=SL       rows=23  pred=0.385417 obs=0.391304 gap=+0.005887  low_sample=True

conclusion: validation: the widest segment gap is +0.011831 in asof_status=WL over 40 rows
  (predicted 0.388169, observed 0.400000); the partition average can hide cohorts that
  disagree with it.
limitation: 4 segment results rest on fewer than 25 rows and are marked low_sample.
```
The largest gap in the run belongs to `class_code=3A` (+0.019873) and the report declines to
build a claim on it because 17 rows cannot carry one — which is the whole point of the floor.
The synthetic cohorts are near-identical, so the informative gaps are around +0.012: this is
evidence the measurement reads correctly, not evidence about railway cohorts.

### Checks run and results
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **824 passed** in 265.95s,
  total coverage **96.23%** (exit 0). 22 of them new, in `tests/training/test_segment_calibration.py`.
- `ruff check railconfirm/ tests/` → **All checks passed!**
- `mypy` → **Success: no issues found in 42 source files**
- Frontend, untouched by this change and re-run as confirmation: `npm test -- --run` →
  **115 passed**; `npm run type-check` clean; `npm run lint` → **No ESLint warnings or errors**;
  `npm run build` → compiled successfully, 7 static pages.
- `python scripts/check_repository_hygiene.py` → recorded below, run after this entry.

### Files
New: `backend/tests/training/test_segment_calibration.py`,
`docs/adr/ADR-0019-subgroup-calibration-measured-with-a-row-floor-on-the-claim.md`.
Changed: `backend/railconfirm/training/metrics.py`, `backend/railconfirm/training/report.py`,
`README.md`, `backend/README.md`, `CHANGELOG.md`, `docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`, `docs/adr/README.md`, `docs/research/EVALUATION_PROTOCOL.md`,
`docs/DEVELOPMENT_LOG.md`.

### Unresolved
- The gaps have never been read on approved data, and on a sparse real file the most likely
  honest output is "no segment holds 25 rows". That is a statement about dataset size, and it
  argues for raising the distinct-journey-date intake minimum before any promotion decision.
- No interval on the gaps, deliberately: a defensible one needs a stated resampling scheme and
  counts, and a fake precision would be worse than a point estimate with a flag. Deferred, not
  rejected.

## 2026-10-24 — A second estimator that reads the queue position (ADR-0020)

### Scope
`FEATURE_COLUMNS` has derived `asof_position` since schema 3.0.0, and after ADR-0013 the report
says plainly which of those columns the served estimator reads: three of eight. A flat cohort
rate answers a passenger first in the waitlist and one two hundred deep with the same number —
an average over a queue, not a model of one. The evaluation protocol has listed "status-and-time
baseline using current normalized status, queue position and time remaining" as baseline 2 since
Phase 3, and roadmap Phase 4 is named after calibrating candidates that do not exist. Built the
candidate, before data could make its verdict convenient, for the same reason ADR-0014 and
ADR-0018 built the temporal paths: the first run after intake is the run that gets quoted.

### Implemented (tests first, 94 new tests)
- `backend/railconfirm/inference/queue.py` (new) — `CohortPositionBaseline`, `position_band`,
  `normalize_band_table`, `QUEUE_ESTIMATOR_ID`, `QUEUE_FEATURES`, `QUEUE_ARTIFACT_FORMAT`,
  `DEFAULT_MIN_BAND_ROWS = 2`. Each cohort key is kept and split by **fixed doubling bands**
  (`1, 2-3, 4-7, 8-15, 16-31, 32-63, 64-127, 128+`).
- `inference/baseline.py` — `ProbabilityEstimator` protocol (what engine/registry/evaluator
  need from either model), the `validate_outcome_counts` rename so band cells are checked by
  the same rule as cohort cells, and `estimate(..., asof_position=None)` on the frequency
  baseline — accepted and ignored, pinned by a test that byte-compares its output with and
  without the position.
- `inference/artifacts.py` — second format, `bands` on `LoadedArtifact`, dispatch via
  `estimator()` / `estimator_for(provenance)`, estimator-aware `features_used` requirement,
  `min_band_rows` recorded only for the model that uses it, and refusals in both directions at
  load and at write.
- `inference/engine.py`, `inference/registry.py` — serve through the declaration: the engine
  passes `asof_position=parsed.position`, the registry builds whatever the artifact names.
- `training/fitter.py` — `fit_cohorts(..., with_bands=)` fills band cells in the same single
  pass that fills cohorts (one loop, so the two cannot drift), `FitSummary` reports
  `estimator`/`band_count`/`rows_without_position`, `fit_baseline(estimator=…)` refuses an
  unknown name instead of defaulting, and the limitation text differs per model: the frequency
  artifact still says positions are derived-but-unread.
- `training/metrics.py` — `score_rows` passes `asof_position=asof.position`, the same parsed
  status that supplies the cohort key.
- `training/decay.py`, `training/__main__.py` — decay and `evaluate` build the estimator from
  the artifact rather than from the cohort table; `fit --estimator cohort_position_baseline`
  prints `Estimator:` and `Bands: N position cells (M training rows carried no position)`.

### A latent defect the new model exposed
`frozen_decay_estimator()` constructed every artifact with `build_estimator(loaded.cohorts, …)`.
With only one estimator that was correct; the moment a position artifact existed it silently
scored the flat model and reported **identical numbers** for the two. Caught by a live run, then
by a test written before the fix:

```
$ python -m railconfirm.training decay … --artifact pos_v1.json --horizon-dates 2 --step-dates 2
  (before the fix) event 0.240085 / 0.239960 — identical to flat_v1, i.e. bands never read
  (after  the fix) event 0.246575 / 0.275914, drift +0.029339, 0/2 horizons beat the baseline
```
The defect could not have affected any artifact that could exist before this change, so it is
recorded here and in ADR-0020 rather than as a user-visible fix. `evaluate` had the same shape
and went the same way.

### Live runs (labelled synthetic fixtures, OS temp directory, nothing committed)
```
$ python -m railconfirm.training fit … --version pos_v1 --estimator cohort_position_baseline \
    --min-sample-threshold 5 --allow-synthetic-for-testing
Used 160 of 160 training rows
Estimator: cohort_position_baseline
Cohorts: 4
Bands: 12 position cells (0 training rows carried no position)
exit 0

$ python -m railconfirm.training evaluate … --artifact flat_v1.json    # exit 0
  validation Brier 0.480955 (baseline 0.48), event Brier 0.240085 (baseline 0.24)
  test       Brier 0.480489 (baseline 0.48), event Brier 0.239960 (baseline 0.24)

$ python -m railconfirm.training evaluate … --artifact pos_v1.json     # exit 0
  validation Brier 0.495196 (baseline 0.48), event Brier 0.246575 (baseline 0.24)
  test       Brier 0.566032 (baseline 0.48), event Brier 0.275914 (baseline 0.24)

$ python -m railconfirm.training decay … --artifact pos_v1.json --horizon-dates 2 --step-dates 2
Drift across 2 horizons (2 scored): event Brier 0.246575 -> 0.275914 (0.029339), coverage 1.0 -> 1.0
  event beat the frozen base rate in 0/2 scored horizons
exit 0
```
The position model is **worse** here, and that is the honest reading: the balanced fixture's
labels are generated independently of queue position, so banding a cohort adds variance without
adding signal. It is not evidence about railways in either direction — no approved dataset
exists — and it is exactly why ADR-0021's paired comparison has to be the thing that decides
promotion rather than whichever number looks better on one split.

### Checks run and results
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **918 passed** in 273.37s,
  total coverage **96.24%** (exit 0).
- `ruff check railconfirm/ tests/` → **All checks passed!** (after `--fix` on import ordering and
  removal of a now-unused `build_estimator` import in two modules).
- `mypy` → **Success: no issues found in 43 source files** (a `Protocol` with a settable
  `is_loaded` attribute was rejected against the classes' read-only properties; declared it as a
  property in the protocol).
- `python scripts/check_repository_hygiene.py` → passed (recorded below after this entry).
- Frontend: no frontend file changed; its gates were green in this session at 115 tests with
  clean type-check, lint and build, and are re-run before the push recorded below.

### Files
New: `backend/railconfirm/inference/queue.py`,
`backend/tests/inference/test_queue_model.py`,
`backend/tests/inference/test_queue_artifact.py`,
`backend/tests/training/test_queue_pipeline.py`,
`docs/adr/ADR-0020-cohort-position-estimator-and-a-second-artifact-format.md`.
Changed: `inference/baseline.py`, `inference/artifacts.py`, `inference/engine.py`,
`inference/registry.py`, `training/fitter.py`, `training/metrics.py`, `training/decay.py`,
`training/__main__.py`, `tests/support/artifacts.py`, `tests/inference/test_registry.py`,
`README.md`, `backend/README.md`, `CHANGELOG.md`, `docs/PROJECT_STATUS.md`,
`docs/AGENT_HANDOFF.md`, `docs/adr/README.md`, `docs/architecture/API_CONTRACT.md`,
`docs/research/EVALUATION_PROTOCOL.md`,
`docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`, `docs/DEVELOPMENT_LOG.md`.

### Unresolved
- Whether the position estimator beats the flat one is unanswered, and unanswerable here: it
  needs real queue behaviour. The comparison harness (ADR-0021) is the next piece.
- Time remaining (`lead_days`) is still derived and unread. Adding it to a model means
  re-examining the leakage rule at the same time, not just widening `features_used`.
- `min_band_rows` has no CLI flag; it is settable through the fitting API and recorded on the
  artifact. Documented as such rather than implied.

## 2026-10-30 — Hardening sweep: refusals instead of coercions, and a cross-stack gate (ADR-0022 to ADR-0027)

### Scope
End-to-end audit of the implemented foundation with the directive "harden what already
exists before adding more": calibration identity, model comparison, group arithmetic, queue
bands, the prediction horizon, and then a check that actually starts both halves of the
product. Every defect below was reproduced against the running code before it was changed.

### Changed
- **Calibration identity (ADR-0022).** A calibration block could declare `target:
  final_chart_cnf` with `event_classes: [CNF, RAC]`, and the same artifact then produced
  `0.103448` on the served path and `0.058824` on the scored path — one artifact, two numbers
  for one claim. The target → event table now lives in the domain module and is read by
  fitting, scoring and serving; a contradictory or unknown target, an empty event and any
  partition other than `validation` are refused at construction.
- **Comparison identity (ADR-0023).** `run_model_comparison` stamped the dataset's id and hash
  into its report without checking either model against it, and compared partitions by
  `(name, start_date, end_date, row_count)` only — while the scoring loop walked the
  *baseline's* frames for both models. Matching dates and counts are not the same rows. Both
  models must now name the `(dataset_id, sha256)` pair, each partition's rows are
  fingerprinted in stored order, and `pair_scores` refuses a repeated position. The verdict
  rule is unchanged: refusals only.
- **Group arithmetic (ADR-0024).** Marginals were clamped into range before being tested, so
  `1.5` and `NaN` contributed certainty; an unknown method name fell through to the
  independence branch and returned a product of marginals under a name the module does not
  implement; and `GroupOutcome` validated nothing, so `P(all CNF) = 0.7` beside
  `P(all CNF or RAC) = 0.6` was constructible and the two count tables could disagree about
  the same event. Invalid input now raises `ProbabilityError` naming the passenger, the
  method list is closed, and every joint figure and count-table entry is checked on
  construction.
- **Queue bands (ADR-0025).** A band cell labelled `1-3` or `128` loaded, counted towards
  `band_count` and was written back, though `position_band` can never return it; the key's
  status part was never validated; and a band cell whose cohort has no row loaded too, which
  `estimate` can never reach. Labels are now derived from `band_labels()`, the cohort part
  uses the cohort table's own rule, and `validate_band_cohorts` refuses orphans in
  `load_tables`, `build_artifact_document` and `load_artifact`. The shared position fixture
  was itself built on orphan `ALL` cells and was corrected.
- **Prediction horizon (ADR-0026).** Serving has always refused a `prediction_at` on or after
  the journey date; the row contract refused only `observation_date > journey_date`, so a
  record observed *on* its journey date was fitted with `lead_days = 0` — the one horizon the
  service will not answer, and the one a date-only record cannot order against the final
  chart. `MIN_LEAD_DAYS = 1` is now imported by both paths, same-day observations are refused
  under their own reason (`observation_on_journey_date`) and counted separately from
  `date_order_violations`, and the row contract is versioned (`1.1.0`) with every report
  naming the version it applied.
- **Cross-stack gate (ADR-0027).** `scripts/smoke_full_stack.py` starts the API under uvicorn
  and the production frontend build under `next start` on loopback ports and checks health, an
  abstention, a field-level refusal, the same-day horizon refusal, store / reopen / list /
  delete / delete-again, a PNR-shaped id, an unrouted path, the CORS preflight and the rendered
  pages; it fails when no built chunk names the backend it started, and runs the client's own
  `api.ts` against that server via `npm run test:live`. CI runs it as a fourth job and uploads
  the server logs on failure. `scripts/` is now linted under the declared Ruff config.

### Found by running it, not by reading it
- **jsdom made every live client call look like an outage.** `api.ts` wraps each request in an
  `AbortController`; under jsdom that controller is jsdom's while `fetch` is Node's, and Node's
  fetch rejects a foreign `AbortSignal` with `TypeError: RequestInit: Expected signal
  ("AbortSignal {}") to be an instance of AbortSignal`. The client reported that as a network
  failure, so all five live checks failed with "the backend may not be running" while the
  backend was running and answering. The live suite runs in the `node` environment now.
- **A suite that skips is a suite that passes.** The first draft of the live file skipped
  itself when `RAILCONFIRM_LIVE_API_URL` was unset, and `npm test` would have collected it in
  every offline run. The config now throws without the variable, the file repeats the refusal,
  and `npm test` excludes it.

### Checks run
- `python -m pytest tests/ -q --cov=railconfirm --cov-fail-under=90` → **1043 passed**, total
  coverage **96.18%** (exit 0). One earlier run reported five failures in
  `tests/api/test_prediction_history.py` and `tests/api/test_contract.py`; they were caused by
  `RAILCONFIRM_PERSIST_PREDICTIONS` and `RAILCONFIRM_STORAGE_DIR` left set in the developer
  shell by the smoke script's manual run, not by the code — both files pass (60 tests) once
  those variables are cleared, and CI never sets them.
- `ruff check railconfirm/ tests/` → clean. `mypy` → clean, 44 source files.
  `ruff check --config backend/pyproject.toml scripts/` → clean.
- `python scripts/check_repository_hygiene.py` → 22 required files, 238 tracked files scanned.
- `npm test` → 115 passed, 6 files. `npx vitest run --config vitest.live.config.ts` → 5 passed
  against a running backend.
- `python scripts/smoke_full_stack.py` → **11 checks passed** (eight backend, the client suite,
  two frontend pages) against a production build made with
  `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010`.
- CI verified independently with `gh run list`: success through `127a254`. The run for the
  smoke-gate commit is the evidence for the new job and is recorded in the commit that
  follows this entry.

### Decisions
- ADR-0022, ADR-0023, ADR-0024, ADR-0025, ADR-0026, ADR-0027.
- Where a value could be coerced into range or a label into a near neighbour, the choice was to
  refuse: a coerced number is a claim nobody made.

### Unresolved
- No browser runs in CI. Interactions, focus order, screen-reader output and visual regression
  are unverified end to end; `npm run test:live` proves the client's request/response handling,
  not how a page behaves.
- Dataset research is the standing blocker and is unchanged by this sweep: no candidate has
  cleared the intake checklist, so every requirement above is still verified only against
  synthetic fixtures.

## 2026-10-30 — Second-pass dataset review: the Railofy competition matrix

### Scope
Review the candidate named in the current directive — `github.com/Yogalakshmi4784/PNR-Prediction`,
whose README points at the Railofy Kaggle competition — using primary evidence, and decide
whether its data may be stored, transformed, trained on, distributed or used commercially.

### What was read
- Repository metadata, the full blob listing with byte sizes, the `LICENSE` text and the
  README, all through the GitHub API. Created and last pushed the same day (2024-08-09),
  one star, GPL-3.0 at the root, 10 blobs, 18.8 MB.
- The two CSVs the README names, opened **once, read-only, outside the product runtime**,
  to establish the header, dtypes and summary statistics. The repository's own intake gate
  was then run against a temporary copy under `%TEMP%`. Both copies deleted afterwards.
- Not opened: `PNR_Confirmation.pkl` (a fitted model of unknown provenance in a format that
  executes code on load, refused by `data/loader.py` by design) and `sweetviz_report.html`.

### Findings
- **The data licence question the README invites does not resolve in the uploader's favour.**
  The `LICENSE` is verbatim GPLv3; the string "dataset" appears in it zero times. A code
  licence establishes nothing about the CSVs, and the copyleft terms mean none of that code
  may be copied into this Apache-2.0 project. That the competition CSVs sit in a public
  third-party repository is a redistribution by someone who is not the rights holder — not
  a grant.
- **The file cannot satisfy the row contract at any price.** 36,775 labelled rows of 17
  scaled floats (13 outside `[0, 1]`), one `QT` code (`GN`/`PQ`/`RL`), five integer flags, an
  11-digit `pk` that is not a PNR and not unique (three values repeat, each with a different
  quota), and a **binary** `target` with base rate 0.3148. `JD`, which the README's glossary
  calls Journey Date, is a float. `python -m railconfirm.data validate` → **0 valid rows,
  exit 1**, seven required columns missing. No dates means no chronological split (ADR-0014),
  no decay horizon (ADR-0018) and no one-clear-day horizon (ADR-0026); no status string means
  `asof_statuses()` has nothing to read, so neither estimator can be fitted or scored; a
  binary label cannot carry the CNF/RAC/WL distinction (ADR-0003).
- **The README's metrics are not evidence.** F1 0.872 and MCC 0.815 for KNN, with no split
  description, no baseline against the 0.3148 base rate, and no time ordering. Measured
  univariate association with the label tops out at `GROP` 0.293 (`CURP` 0.250, `RPW` 0.220,
  `NDTD` −0.206, `CANP` 0.187, `CUCA` 0.164, `GRCA` −0.128), which does not explain such an
  MCC. The glossary also lists `CCA` as availability *after chart preparation* and `RPW` as a
  pre-computed confirmation weight; the correlations do not show `CCA` dominating, so this is
  recorded as a question about an undocumented transformation, not asserted as proven leakage.
- **Rights remain unreadable, and that is the blocker.** The competition's rules, data and
  About-Dataset pages are client-rendered and return only a page title to an automated fetch;
  `https://www.kaggle.com/api/v1/competitions/list?search=railofy` answers **HTTP 401** without
  an account, and this environment has no Kaggle credentials. Search metadata establishes only
  that the competition is titled "Indian Railways Challenge", hosted by Railofy, and marked
  "Late Submission" (closed). Behind that sits a second question: what Railofy itself was
  permitted to publish from a private PNR-tracking service.

### Decisions recorded
- `SOURCE_REGISTER.md`: Kaggle `railofy-challenge` → **Quarantined, terms unreadable from this
  environment**; `Yogalakshmi4784/PNR-Prediction` → **Rejected for training on content**, code
  not reusable. No manifest was generated, because a manifest would imply a candidate worth
  deciding on. No ADR: nothing was approved, and the gate refused the file.
- `CANDIDATE_DATASET_REVIEW.md` now documents a third disqualifying shape — reservation data
  whose semantics were destroyed by an undocumented scaling before publication — and the
  method of the pass, including that the earlier "raw files deliberately were not fetched"
  sentence is superseded and why.

### Checks run
- `python -m railconfirm.data validate <temporary copy>` → 0 valid of 36,775, exit 1 (output
  quoted in the review).
- Summary statistics computed with pandas in this environment; the figures above are the
  measured ones.
- No test suite, lint or type check was needed: this pass changed documentation only. The
  repository hygiene check and the Markdown link check were run before committing.

### Unresolved
- The Railofy competition terms, and Railofy's own rights to the records it supplied. Closing
  either requires an authenticated Kaggle session or contact with the host — maintainer
  actions, not agent actions.
- Training remains blocked exactly as before. This pass removed one plausible-looking
  candidate from the search space with evidence instead of assumption.

## 2026-10-30 — Evaluation reliability: the aggregate that beat the base rate on rows that lost to it (ADR-0028)

### Scope
Audit of the rolling-origin aggregate, continuing the evaluation-reliability workstream: what
the published number actually averages, and whether a reader can tell when it flatters the
table. The one-defect-at-a-time rule applied — the defect below was found by reading the
aggregation against the scoring loop, then reproduced as a constructed plan in a test.

### Changed
- **One aggregate was published, and it was the mean of means (ADR-0028).** Each origin's
  scorecard is a mean over the rows that origin scored, so `mean_brier` gives a horizon with
  two rows the same weight as a horizon with two thousand. A plan whose last horizon is a
  partial date block — the normal case — therefore had a published figure that answered "how
  did the fitting procedure do per cutoff" while reading as "what did a passenger get per
  prediction". The two can land on opposite sides of the same baseline: nine small horizons
  that scored well and one large one that scored badly produce a mean that beats the base rate
  beside a pooled error that loses to it.
- **Both figures are now computed and published**, with `scored_rows_spread` and two verdicts
  (`distribution_agreement`, `event_agreement`) that compare each aggregation against its own
  baseline and return `agree`, `disagree` or `undetermined`. An abstaining origin contributes
  to neither figure, which keeps the existing rule that a coverage failure is not a bad score.
- **Disagreement is a conclusion, not a footnote.** The report prints both pairs of numbers
  and states that which figure a reader quotes decides the verdict, so neither is presented as
  *the* result; an agreement names the pooled figure as the one a statement about served
  predictions should rest on. Uneven horizons add a limitation; the terminal output prints the
  range and does not warn when every origin scored the same number of rows, because a warning
  that fires on every balanced run is a warning nobody reads.
- `ORIGIN_REPORT_SCHEMA_VERSION` → `1.1.0` (additive keys, no change of meaning).
  `ORIGIN_AGGREGATE_DEFINITIONS` now travels in the origin report's `metric_definitions` and is
  deliberately absent from the single-cutoff and decay reports, which publish no aggregate over
  origins.

### Found while writing the tests
- **The spread line fired on balanced runs.** `describe_result` printed "scored rows per origin
  ranged 2 to 2, so the mean over origins and the pooled mean weight the horizons differently"
  — a false statement on every plan whose horizons are equal in size. Both the terminal line
  and the report limitation now require the two counts to differ.
- **An existing test counted a substring rather than lines.**
  `test_describe_result_prints_one_line_per_origin_then_the_aggregate` asserted
  `text.count("origin ") == 2`, which passed only because no other line contained that
  substring; the new spread sentence made it fail for the right reason. It now counts lines
  beginning with `origin `.

### Checks run
- `python -m pytest tests/training/test_origins.py -q` → 26 passed.
- `python -m pytest -q` → **1050 passed** (60.9 s).
- `python -m ruff check .` → clean. `python -m mypy railconfirm` → clean, 44 source files.
- Figures in the ADR and the tests are hand-computed from the constructed scorecards, not taken
  from a run's output.

### Unresolved
- The pooled figure is a weighted mean of per-origin means that were already rounded to six
  decimal places. The difference is far below the precision at which these numbers mean
  anything, but it is recorded in ADR-0028 rather than left to be rediscovered.
- Rolling origins still overlap by construction, so neither aggregation is an independent
  sample: no interval, multiplicity correction or test statistic is attached to either. The
  remaining evaluation work is the same as before — the pipeline has never run on approved real
  data, and every figure above comes from synthetic fixtures.

## 2026-10-30 — A locked period that scored nothing reported itself as a crash (ADR-0029)

### Scope
Continuing the evaluation-reliability workstream into `backend/railconfirm/training/calibration.py`,
`decay.py` and their report paths: what a calibration's published evidence claims, and what
happens when one of its two readings does not exist. The defect below was found by reading the
public properties of `CalibrationEvidence` against the scoring loop that populates them, then
reproduced in a script before any code was changed.

### Changed
- **A missing locked reading raised from a public property.** `test_effect` and
  `helps_on_locked_test` opened with bare `assert` statements. A locked partition on which
  every row abstained — `scored_rows == 0`, `event_brier is None`, which happens whenever the
  estimator cannot reach a cohort — produced `AssertionError` from `to_dict()` and from the
  `fit` command's own summary line. The CLI reaches both **after** `write_fitted_artifact`, so a
  fit that had completed and written its model reported itself as a crash, exited non-zero and
  never wrote `--report`. Under `python -O` the same path returned `None - None` and raised
  `TypeError`, so the assertion was not even a reliable error.
- `test_effect` now returns `float | None`, `helps_on_locked_test` returns `bool | None`, and a
  new `locked_test_measured` states whether the period produced an event score at all. `None`
  is not `False`: a correction that measured nothing has not been shown to fail.
- The conclusion, the summary line and the terminal output say *unmeasured* / *unknown* for that
  case, and keep the existing failing wording for a measurement that was made and pointed the
  wrong way. One wording rule, three rendering paths.
- `validation_effect` now raises `DatasetValidationError` naming the contradiction. The refusal
  is right — `fit_platt` cannot fit without rows carrying a probability strictly inside
  `(0, 1)` — but a bare `assert` was the wrong way to say it.
- `REPORT_SCHEMA_VERSION` → `1.1.0`: the calibration block gained `locked_test_measured` and
  `helps_on_locked_test` may now be null. No key changed meaning, but a `1.0.0` reader would
  have read that null as `false`, which is exactly the ambiguity the new key removes.

### Found while writing the tests
- **A changed status would not have made the locked period unreachable.** The first version of
  the CLI test rewrote the locked rows to `RAC 2`, and the fit still scored them: `_lookup`
  falls back from `(class, quota, status)` to a broad `(class, quota, ALL)` cohort, so every
  status inside a known class/quota pair is answerable. The fixture now moves the locked rows to
  an unseen quota (`TQ`), which no fallback can reach. That fallback is a real property of the
  lookup and is recorded in the test and in ADR-0029 rather than left as a puzzle.
- **A malformed row count escaped the artifact boundary as `TypeError`.** `CalibrationSpec`
  compared `fitted_rows < 1` without checking the type, so an artifact declaring `"120"` or
  `null` raised `TypeError` out of `spec_from_mapping` — past the registry's
  `except ModelArtifactError` handler and past the CLI's, which turns a rejectable artifact into
  an unhandled exception. A fraction (`120.5`) and a boolean (`true`) were *accepted* as row
  counts. Reproduced against the loader for six values (`120` accepted; `"120"` and `null`
  `TypeError`; `120.5` and `True` accepted; `0` and `-3` correctly refused), then fixed by
  checking the type before the comparison, the same rule the artifact metadata already applies
  to `min_sample_threshold` and `laplace_alpha`. Seven regression cases were added to
  `tests/inference/test_calibration.py`.

### Checks run
- Before the first commit (the tri-state change): `pytest tests/training/test_calibration.py` →
  44 passed; `pytest` over the whole backend → **1054 passed** (77.2 s); `ruff check .` clean;
  `mypy railconfirm` clean, 44 source files; the hygiene script passed (22 required files, 240
  tracked files).
- After the second fix (the row count): `pytest tests/inference/test_calibration.py` → 49
  passed; `pytest` over the whole backend → **1061 passed** (79.4 s); Ruff clean; mypy clean, 44
  source files; the hygiene script passed.
- Both defects were reproduced before they were fixed: the crash path with a standalone script
  against a fitted fixture, and the loader with a six-value probe whose output is quoted above.

### Unresolved
- A calibrated artifact whose locked period could not be scored is still written, and still
  carries its calibration: the fit decision is a validation decision (ADR-0017). The report now
  states the missing measurement instead, and promotion stays `candidate`. Whether a promotion
  reviewer should require a measured locked effect is a product decision that has not been made,
  and it is recorded here rather than silently enforced by the code.
- Nothing above is evidence about railway behaviour. Every number involved comes from synthetic
  fixtures, and the report keeps stating that in its limitations.

## 2026-10-30 — The decay readout dated its drift from a window nobody measured (ADR-0030)

### Scope
Continuing the evaluation-reliability workstream into `backend/railconfirm/training/decay.py`
and `backend/railconfirm/training/report.py`: what the frozen-artifact drift actually
subtracts, and what it says about the horizons it subtracted. The defect was found by reading
`_decay_conclusions` against the `_values(...)` helper it calls, not from a failing test — the
suite asserted the skip-silent behaviour as if it were intended.

### Changed
- **The conclusion named windows it had not measured.** `first_event_brier` and
  `last_event_brier` come from `_values("event_brier")`, which skips `None`, so the two ends of
  the drift are the first and last *scored* horizons. A horizon on which every row abstained has
  no event Brier — legitimate since ADR-0029 — and the sentence still said "in the window nearest
  the cutoff" / "in the furthest". The metric definition repeated the claim ("last horizon
  event Brier minus the first horizon's"), so the number and its definition agreed with each
  other and both disagreed with the run.
- `FrozenDecayResult` publishes `scored_horizon_indices`, `first_scored_horizon` and
  `last_scored_horizon`; both indices enter `summary`, so a reader holding only the JSON can tell
  the drift starts at horizon 1. `describe_result` prints `h{first} … -> h{last} …`.
- The conclusion dates its own endpoints, names the skipped horizons, and keeps the near/far
  wording only when those are the windows it used.
- **One scored horizon was reported as a decay curve.** With two horizons and one silent, the
  old wording printed `ran from 0.240000 … to 0.240000 …, a drift of +0.000000` — a zero
  difference between a number and itself, in a report whose `MIN_HORIZONS = 2` exists because a
  trend through one point is not a trend. That case now reports the single score, says one
  future window is a single measurement, and prints no drift.
- **The two drift figures spanned different horizon sets and nothing said so.** `coverage` is
  defined on every horizon (a fully abstaining horizon reports `0.0`), so `coverage_drift`
  always spans horizon 0 to the last, while `event_brier_drift` may skip horizons at either end.
  Both metric definitions and the limitations list now state their own span.
- `DECAY_REPORT_SCHEMA_VERSION` → `1.1.0`: the summary gained two keys and two definitions
  changed wording. Additive, the same rule ADR-0028 and ADR-0029 applied.
- The arithmetic, the plan, the frozen baseline and every score are untouched. On a run where
  every horizon scored — every run the fixtures produce — the published numbers are identical.

### Found while writing the tests
- The existing test named
  `test_drift_compares_the_first_horizon_with_the_last_rather_than_averaging` encoded the skip
  in its own body: it ran a six-horizon fixture on which everything scored, so "first scored"
  and "first horizon" coincided and the distinction was invisible. Making a horizon silent had
  to be constructed, which is why `without_a_score(card)` and `mute(result, indices)` now exist:
  the first replaces a scorecard's measurements with a fully abstaining one, the second applies
  it to named horizons. Mutating the fixture's data was the alternative and would have changed
  what every other test in the file measures.
- Dataclasses make this cheap and safe — `replace()` on the result and on each `HorizonScore`
  keeps `window`, `cohort_count` and the horizon indices intact, so the muted run is still a
  valid run and only the reading is gone.

### Checks run
- `pytest tests/training/test_decay.py` → **37 passed** (40.8 s) after the change. The defect was
  not found by a failing test — it was found by reading `_values(...)` against the sentence
  built from it — so the two new tests were written from the constructed silent-horizon case
  rather than from a red run.
- `pytest` over the whole backend → **1063 passed** (156.0 s).
- `ruff check .` clean; `mypy railconfirm` clean, 44 source files; the hygiene script passed.

### Unresolved
- `event_brier_spread` still describes only the horizons that scored, which is correct for a
  spread of readings but means it is not comparable to the coverage figures beside it. The
  metric definition for the spread does not yet say which horizons it spans; the same
  clarifying sentence should be added to `METRIC_DEFINITIONS` in the shared block, where it
  would apply to the single-cutoff and rolling-origin reports too, and that is a wider edit than
  this fix.
- Nothing above is evidence about railway behaviour. Every number involved comes from synthetic
  fixtures.

## 2026-10-30 — A reliability band counted one prediction twice (ADR-0031)

### Scope
Continuing the evaluation-reliability workstream into `backend/railconfirm/training/metrics.py`:
the reliability bands every scorecard publishes, and whether their counts describe the rows they
claim to. Found by reading the band-membership condition against what the band is used for, then
reproduced with a cohort chosen to make a probability land exactly on an edge.

### Changed
- **Both band edges were inclusive.** `_bands` used
  `lower <= predicted <= upper or (index == bins - 1 and predicted == 1.0)`, so a prediction on
  a boundary was a member of the band below and the band above. With ten bins and a smoothed
  table producing `(count + 1) / (n + 5)`, boundaries are ordinary: one confirmation in a
  fifteen-row cohort is exactly `2/20 = 0.1`.
- Reproduced before the fix, on one scored row predicted at `p_cnf = 0.1`:
  `CNF 0.0–0.1 count 1 mean 0.1` and `CNF 0.1–0.2 count 1 mean 0.1` — `sum(count) == 2` for
  `scored_rows == 1`, and the event bands overlapped the same way.
- Bands are now half-open, `[lower, upper)`, with the last one including `1.0`, so they
  partition the scored rows. `ReliabilityBin`'s docstring states the rule and `_bands` records
  what the overlapping version did.
- `METRIC_DEFINITIONS["reliability"]` and `["event_reliability"]` now state the half-open rule
  and the invariant, because a reader summing the counts needs to know what the total should be.
  No schema version changes: no key was added, renamed or reinterpreted, and the payload shape
  is identical.
- No score, Brier value, calibration fit or artifact is affected.

### Found while writing the tests
- **The existing assertion was already there and could not fail.**
  `test_reliability_bands_carry_counts` already asserted
  `sum(band.count for band in cnf_bands) == card.scored_rows`; its fixture predicts `91/105`,
  which is not on an edge, so the invariant held by accident. The regression test therefore had
  to construct a cohort whose probability is exactly `0.1` — hence the new optional `cohorts`
  argument on the file's `estimator` helper.
- The other direction had to be pinned too: a half-open rule that drops `1.0` would silently
  lose a certain prediction, so `test_bands_cover_both_endpoints_and_each_row_once` passes
  `0.0`, `0.5` and `1.0` through two bins and checks both endpoints are held.

### Checks run
- `pytest tests/training/test_metrics.py` → **27 passed** (1.9 s) after the change.
- `pytest` over the whole backend → **1065 passed** (161.0 s).
- `ruff check .` clean; `mypy railconfirm` clean, 44 source files; the hygiene script passed.
- The probe that reproduced the overlap was a throwaway script outside the suite; it was deleted
  after its output was recorded here and in ADR-0031.

### Unresolved
- A band's `mean_predicted` and `observed_frequency` are rounded to four decimals while the
  counts are exact, so a reader recomputing a band mean from published rows would not reproduce
  it to the last digit. The report says the bands are a description, not a fit, but it does not
  say the means are rounded; that belongs in the shared metric block and was left for the same
  wider edit as the spread definition above.
- Nothing above is evidence about railway behaviour. The fixture is synthetic.


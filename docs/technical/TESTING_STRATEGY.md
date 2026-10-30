# Testing strategy

Status: this describes what the repository runs, not what it intends to run. Where a
layer below is still a plan, it says so.

Current totals on a developer machine: **1043 backend tests** at 96.2% branch coverage
(`--cov-fail-under=90`), **115 frontend tests**, **5 live cross-stack tests** that need a
running backend, and one **full-stack smoke script** that starts both processes. Every
suite below that exercises the model pipeline uses clearly-labelled synthetic fixtures;
none of them measures railway accuracy, because there is no approved real dataset.

## Commands

```bash
# Backend, from backend/
pytest tests/ --cov=railconfirm --cov-fail-under=90
ruff check railconfirm/ tests/
mypy

# Frontend, from frontend/
npm run type-check
npm run lint
npm test                     # excludes the live suite

# Cross-stack, from the repository root (needs a frontend build first)
python scripts/smoke_full_stack.py
python scripts/check_repository_hygiene.py
```

`npm test` deliberately excludes `src/lib/__tests__/liveApi.test.ts`: that file needs a
server, and a suite that skips itself when the server is absent reports success without
evidence. `vitest.live.config.ts` refuses to start without `RAILCONFIRM_LIVE_API_URL`
(ADR-0027).

## Testing layers

### Full-stack smoke

The only layer that starts both halves of the product (ADR-0027).
`scripts/smoke_full_stack.py` runs the API under uvicorn and the production frontend build
under `next start` on loopback ports, then checks over real sockets:

- `/` and `/v1/health` report the empty registry, history enabled, and the governing
  sample threshold;
- a schema-valid request **abstains** with `no_trained_model`, carries no probability, and
  its group outcome abstains for the same reason with a limitation naming
  `no_active_version`;
- a field error answers 422 with `details[0].field`, `X-Request-ID` on both the envelope and
  the header, and the documented codes;
- a `prediction_at` on the journey date is refused with `INVALID_PREDICTION_AT`;
- store, reopen, list, delete and delete-again behave as documented, the listing summary
  carries only the five non-ticket fields, and a delete returns no body;
- a PNR-shaped id is a 404 `not_found`, not a lookup;
- an unrouted path uses the same error envelope;
- the CORS preflight allows the frontend origin;
- the built client bundle names the backend that is running (a build pointed elsewhere
  fails here rather than passing two separate checks);
- `npm run test:live` — the client's own `api.ts` — runs against that server.

What it does not cover: no browser, so a JavaScript-only failure still passes and no
interaction, focus order or accessibility check happens end to end. A browser driver is
the obvious next layer and is not configured.

### Unit tests
Cover pure logic and edge cases:
- status parsing, normalization and unknown codes;
- position parsing and invalid numbers;
- request schema validation;
- time-zone and prediction-horizon calculations;
- output probability validation and sum-to-one tolerance;
- group-event derivation from a supplied joint distribution;
- data freshness and abstention rules;
- redaction helpers and identifier handling.

Unit tests should be deterministic and use clearly labelled fixtures.

### Contract tests
Check frontend/backend schemas and source adapter contracts:
- required/optional fields;
- enum/schema version compatibility;
- response classes and structured errors;
- provider payload mapping without real credentials;
- idempotency behavior;
- stale response semantics.

Fixture files must not contain real PNRs or private provider payloads.

### Integration tests
Use disposable/local database instances and fake provider adapters to test:
- persistence of observations and provenance;
- immutable predictions;
- retention and deletion flows;
- request validation through inference orchestration;
- permission/adapter disabled states;
- transaction consistency for multiple passengers.

Tests that call a live provider must be separately marked opt-in, disabled in ordinary CI and run only where authorization and safe test data exist.

### Frontend tests
Check:
- accessible form labels and keyboard operation;
- add/remove passenger rows;
- validation and useful correction messages;
- distinct display for original and current status;
- explicit unsupported/stale states;
- correct distinction between CNF and RAC;
- no color-only meaning;
- no probability display when API returns abstention.

### Research tests
Check:
- split grouping keeps all snapshots of a booking in one partition;
- feature timestamps do not exceed prediction_at;
- labels and post-chart/final-outcome fields never enter features;
- chronological train/validation/test ordering;
- proper probability bounds and class order;
- group event probabilities agree with their defined joint distribution;
- synthetic records are excluded from empirical evaluation;
- results are reproducible for a fixed code/data/configuration version.

## Golden edge cases

Include test cases for:
- one passenger with known status;
- mixed RAC and WL among several passengers;
- unknown raw status code;
- malformed/negative position;
- missing original status;
- current status timestamp unknown;
- stale latest observation;
- unsupported quota/class;
- partial or censored final outcomes;
- duplicate and out-of-order snapshots;
- one cancelled passenger within a group;
- provider outage and rate-limit response;
- model not loaded or feature schema mismatch;
- probability vector containing NaN, infinity, negative or out-of-range values.

These fixtures test behavior, not actual model performance.

## Model evaluation tests

Separate correctness tests from performance evaluation. A model can pass unit tests and still be poorly calibrated. Performance reporting requires real eligible observations with documented rights and outcome labels.

At minimum, evaluation automation should assert:
- defined dataset/version and split;
- no group leakage;
- no future-observation leakage;
- metric definitions and sample counts exist;
- calibration and proper scoring rules are computed;
- subgroup results are not reported as conclusive below a stated sample threshold;
- baseline comparison is included.

## CI expectations

`.github/workflows/ci.yml` runs four jobs, all without credentials or third-party network
access:

1. **backend-checks** — Ruff (declared rule set), mypy (declared config), and pytest with
   `--cov-fail-under=90`.
2. **frontend-checks** — `tsc --noEmit`, ESLint, `npm test`, and a production build.
3. **full-stack-smoke** — installs the backend's runtime dependencies, builds the frontend
   against `http://127.0.0.1:8010`, and runs `scripts/smoke_full_stack.py`, uploading the
   server logs when it fails (ADR-0027).
4. **repository-hygiene** — required documentation present, relative Markdown links resolve,
   no secret material, no PNR-shaped value outside synthetic-labelled files, `scripts/`
   linted under the same declared Ruff configuration, and the workflow YAML parses.

Research tests that need a protected dataset validate the pipeline with synthetic fixtures;
empirical score generation stays a separate controlled workflow. A CI run proves the
software behaves as specified on fixtures. It does not establish that the product predicts
railway outcomes, and no green run should be described that way.

## Reporting

For every change, report commands actually run and their outcomes. If something was not run because dependencies/data are unavailable, state that. Do not write "all tests pass" unless all applicable tests ran and passed.

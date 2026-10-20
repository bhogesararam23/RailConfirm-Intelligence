# Testing strategy

Status: test plan for implementation; no test suite is claimed to exist yet.

## Testing layers

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

Once code exists, CI should run formatting, linting, type checks, unit/contract tests and safe integration tests. Research tests that need a protected dataset should validate the pipeline with synthetic fixtures while keeping empirical score generation as a separate controlled workflow.

## Reporting

For every change, report commands actually run and their outcomes. If something was not run because dependencies/data are unavailable, state that. Do not write "all tests pass" unless all applicable tests ran and passed.

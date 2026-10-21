# Product requirements

Status: initial requirements baseline. Requirements are subject to revisions through normal review.

## Priority definitions

- **P0 — Required for a trustworthy first vertical slice**
- **P1 — Required before calling the ML predictor research-validated**
- **P2 — Later capability, dependent on evidence, rights or product feedback**

## Functional requirements

### Inputs and journey context

- **PR-001 (P0):** The user can enter train number, journey date, boarding station, destination station, class and quota when known.
- **PR-002 (P0):** The user can add, remove and reorder passengers without entering passenger names.
- **PR-003 (P0):** Each passenger has separately represented original status and latest known status.
- **PR-004 (P0):** Each manually supplied latest status records an observation timestamp or is explicitly marked as timestamp unknown.
- **PR-005 (P0):** Raw status text is preserved; normalization does not silently convert unknown values.
- **PR-006 (P0):** Invalid or incomplete inputs produce useful validation errors before a prediction is requested.
- **PR-007 (P2 / deferred):** A future ADR may propose an authorized lookup adapter. It is not part of the current build, and the manual workflow must not depend on an external provider.

### Predictions

- **PR-010 (P0):** The API identifies whether a request is eligible for a validated model, a documented baseline, or neither.
- **PR-011 (P0):** Unsupported requests return a structured unavailable/abstain response rather than invented numeric probabilities.
- **PR-012 (P1):** For supported categories, each passenger receives mutually exclusive final-outcome probabilities under a documented target definition.
- **PR-013 (P1):** CNF and RAC remain separate concepts in both results and explanatory text.
- **PR-014 (P1):** The system derives supported group events such as all CNF, all CNF/RAC, exactly k CNF and at least k CNF.
- **PR-015 (P1):** Group events are derived from a joint or explicitly validated structured distribution, not silently from an independence assumption.
- **PR-016 (P0):** Every result identifies prediction time, model/version, target, evidence status and limitations.
- **PR-017 (P1):** Where available and validated, results show data freshness, coverage and uncertainty.
- **PR-018 (P2):** The product shows how predictions change across observed snapshots without confusing prediction movement with ticket-status movement.

### External integrations (deferred; not in current roadmap)

- **PR-020 (current scope):** The application starts and supports its manual workflow without third-party API credentials or provider connectivity.
- **PR-021 (current scope):** Tests and core UI behavior do not call live railway, news, calendar, weather or hosted-inference services.
- **PR-022 (deferred):** Live PNR lookup and scheduled status refresh require a separate ADR, documented source permissions, privacy/retention controls and failure behavior.
- **PR-023 (deferred):** Future tracking data must have access control, a defined retention policy and tested deletion behavior before enablement.
- **PR-024 (deferred):** Notifications or other provider-backed services are outside the current build.

### Research and governance

- **PR-030 (P0):** Every training/evaluation source is registered with provenance and permitted use.
- **PR-031 (P0):** Synthetic data is clearly separated from real observations and excluded from empirical model-performance claims.
- **PR-032 (P1):** The evaluation uses chronological splits and prevents snapshots from one booking leaking across partitions.
- **PR-033 (P1):** The evaluation reports proper scoring rules, calibration, sample counts and coverage.
- **PR-034 (P1):** Performance is reported across supported status categories, quotas, classes and prediction horizons where sample size permits.
- **PR-035 (P1):** Model and data versions are recorded to reproduce results.
- **PR-036 (P2):** Verified external event features are added only after a feature ablation demonstrates incremental value.

## Non-functional requirements

- **NFR-001 — Honesty:** UI must not imply that an untrained or unsupported estimate is a validated probability.
- **NFR-002 — Privacy:** Passenger names are not needed. Avoid raw PNRs in URLs, logs, analytics and error traces.
- **NFR-003 — Security:** The current core path has no third-party runtime API dependency; validate all user-supplied/local data. Any future provider credentials must stay server-side and use bounded timeouts/retries.
- **NFR-004 — Reproducibility:** Model evaluation can be reconstructed from a code revision, data version, split definition and configuration.
- **NFR-005 — Traceability:** Each estimate includes target semantics, timestamp and model version.
- **NFR-006 — Resilience:** Missing local data/model artifacts return explicit setup/unsupported behavior; the core workflow must not depend on provider availability.
- **NFR-007 — Maintainability:** Product UI, domain logic, data ingestion, training and inference are separable.
- **NFR-008 — Accessibility:** Forms have labels, keyboard operation, focus visibility, useful error messages and non-color-only status cues.
- **NFR-009 — Performance:** Latency targets are set after implementation and measured with a representative workload; do not publish invented targets.
- **NFR-010 — Data rights:** No source enters persistent ingestion or training until its usage rights are recorded.

## Release gates

A feature cannot be described as prediction-ready unless target definitions, model versioning, evaluation evidence, error handling and coverage disclosures are present. Any future live tracking or external context integration is deferred and would need a new provider-authority, privacy and security gate.

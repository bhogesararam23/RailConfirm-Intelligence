# Implementation plan

Status: planned order of work. This document is intended to give a new coding agent a concrete starting sequence without requiring it to invent missing requirements.

## Working rules

- Read AGENTS.md, the product requirements, the architecture decision index and current project status first.
- Inspect current code before creating or renaming files.
- Use the smallest useful vertical slice and keep tests with the code.
- Do not build live tracking or claim a model exists while data rights and evidence are missing.
- Add material decisions as sequential ADRs. Update CHANGELOG and DEVELOPMENT_LOG at appropriate milestones.
- Do not inflate commit count. Make related, reviewable changes.

## Phase 0 — Feasibility, specifications and repo hygiene

Tasks:
1. Review candidate data sources and the source register.
2. Confirm which sources may be used for reference, storage, derived features, training and publication.
3. Choose the first supported reservation status taxonomy from authoritative references.
4. Refine the target/label/censoring rules with available dataset semantics.
5. Decide on a concrete initial runtime stack only after reviewing environment/cost constraints.
6. Set up the minimal package layout and CI after the first code task is selected.

Exit criteria:
- An approved or explicitly unavailable data path is documented.
- Target semantics and unknown status handling are clear.
- No accidental claim of historical-model readiness appears in docs or UI.

## Phase 1 — Domain package and contracts

Tasks:
1. Define typed journey, passenger status, status observation and prediction contracts.
2. Implement status parsing without discarding raw strings.
3. Implement validation and stable reason codes.
4. Add tests for mixed RAC/WL groups and malformed/unknown inputs.
5. Publish schema/version rules and keep API docs in sync.

Exit criteria:
- Deterministic domain tests cover normal and edge behavior.
- Unknown status is never silently mapped to a supported target.

## Phase 2 — API shell and manual form

Tasks:
1. Build the manual-entry form and passenger row management.
2. Add request validation in the API.
3. Return a stable no-model-available response when no evaluated model is registered.
4. Build the result page's supported/abstained states.
5. Add frontend/API contract tests.
6. Make the UI accessible and avoid color-only meaning.

Exit criteria:
- User can submit a valid scenario and get a truthful state.
- No fake numeric probabilities are rendered.
- The experience works without provider credentials.

## Phase 3 — Data quality pipeline and baseline

Tasks:
1. Implement an ingestion path for an approved dataset or an explicitly documented local fixture.
2. Store source/version and validation metadata.
3. Add data-quality summaries and exclusion reasons.
4. Reconstruct as-of-time snapshots.
5. Implement the historical-frequency baseline.
6. Add chronological and booking-group partition logic.
7. Write leakage and reproducibility tests.

Exit criteria:
- A reproducible baseline run exists only for eligible real labelled data.
- Synthetic fixtures are excluded from empirical metric outputs.
- Split and feature-timestamp checks pass.

## Phase 4 — Candidate models and calibration

Tasks:
1. Compare the baseline with one or more tabular candidates.
2. Train and select using development/validation periods only.
3. Calibrate on validation data.
4. Evaluate on a locked future period using Brier score, log loss and calibration.
5. Report subgroup sample counts and uncertainty.
6. Create a versioned model card and evaluation report.
7. Add artifact compatibility checks to inference.

Exit criteria:
- Candidate utility over baseline is measured on holdout.
- Supported categories and limitations are explicitly documented.
- If the model fails to beat baseline, report the failure and do not promote it.

## Phase 5 — Group outcome estimation

Tasks:
1. Establish the available group-level labelled sample.
2. Build a transparent baseline for group events.
3. Implement a joint/structured candidate with explicit assumptions.
4. Evaluate all-CNF, all-CNF/RAC and count-based events on held-out groups.
5. Compare calibration and proper scoring rules.
6. Expose only events with enough evidence.

Exit criteria:
- Passenger and group outputs remain coherent.
- Dependence assumptions are documented and tested.
- Unsupported group estimates abstain.

## Phase 6 — Authorized live data and tracking

Tasks:
1. Assess a real provider and update the source register.
2. Verify access, storage, rate-limit, model-training and publication terms.
3. Implement an adapter behind a feature/configuration switch.
4. Add secure identifier mapping, consent, retention and deletion.
5. Add freshness states, idempotency, bounded retries and provider health.
6. Test disabled/outage/rate-limit/unknown-status behavior.

Exit criteria:
- Written source terms cover the actual operations performed.
- The adapter can be disabled without breaking manual entry.
- Old data is clearly labelled stale.

## Phase 7 — External context and ongoing monitoring

Tasks:
1. Select structured calendar/operational event sources and verify terms.
2. Normalize events with source and publication timestamps.
3. Test feature ablation on temporal holdout.
4. Add drift, freshness, calibration and abstention monitoring.
5. Define a documented retraining and rollback workflow.

Exit criteria:
- External context is retained only if it adds measurable value.
- Retraining cannot silently reuse the locked test set.
- Monitoring alerts and operational ownership are documented.

## First coding task recommended

Start with the domain schema and reservation-status normalization tests—not a trained model and not live PNR automation. These concepts underpin form validation, storage, historical data and inference, and they can be implemented/tested without pretending data access is solved.

The precise first status mapping must be checked against an authoritative reference before production use.

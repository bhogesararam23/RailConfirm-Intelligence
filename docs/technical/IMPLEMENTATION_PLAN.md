# Implementation plan

Status: planned work order. The canonical phase gates are in [ROADMAP.md](../ROADMAP.md).

## Current scope

The initial build is local-first and has no third-party runtime APIs. The project can use its own internal API between frontend and backend. Research agents may discover and prepare candidate dataset files, but those files must pass the [dataset intake checklist](../data/DATASET_INTAKE_CHECKLIST.md) before they can be used for model training.

Do not implement live PNR lookup, polling, news feeds, external calendar/weather/event APIs or hosted inference in Phases 0–7. These are planned core long-term capabilities in roadmap Phases 8–10, not permanently out of scope. Preserve clean adapter boundaries while keeping the current app fully local.

## Phase 0 — Data feasibility and source rights

1. Inventory candidate historical data and primary-source documentation.
2. Record each candidate in the source register.
3. Review permitted local storage, transformations, model training, aggregate publication and commercial use separately.
4. Determine whether reliable status trajectories and final outcome labels are available.
5. Quarantine files containing unexpected PNRs or identifiable passenger data until reviewed.
6. Mark synthetic fixtures separately from real observations.

**Exit:** An approved data path exists, or the data blocker is documented honestly. A source is not approved just because a file is downloadable.

## Phase 1 — Domain package and contracts

1. Define typed journey, passenger status, observation, prediction and abstention structures.
2. Verify supported status mappings from authoritative references.
3. Preserve raw statuses and parsed positions separately.
4. Implement validation and stable reason codes.
5. Test mixed RAC/WL groups, malformed positions, timestamps and unknown statuses.

**Exit:** Unknown categories cannot silently enter a supported model path; deterministic tests cover documented invariants.

## Phase 2 — Local dataset intake and quality

1. Implement a loader for the approved local file format.
2. Validate schema, dates, train/class/quota coverage, status distribution, duplicates and contradictions.
3. Store source/dataset version and transformation provenance.
4. Build as-of-time snapshots without using future observations.
5. Produce inclusion/exclusion and missing-label reports.
6. Keep raw/private datasets outside Git unless an explicit rights and privacy review permits publication.

**Exit:** Dataset provenance, labels, quality and permitted use are documented well enough to define an experiment.

## Phase 3 — Historical/statistical baseline

1. Define the target and eligible outcomes.
2. Choose chronological train/validation/test cutoffs based on available data.
3. Keep snapshots of the same booking/journey in a single partition.
4. Implement a smoothed historical-frequency baseline and a status/time baseline where fields allow.
5. Compute Brier score, log loss, calibration, coverage and subgroup sample counts.
6. Record all configuration and results in an experiment report.

**Exit:** An approved, reproducible baseline evaluation exists, with leakage checks. Synthetic data is not used to report predictive performance.

## Phase 4 — Candidate ML and calibration

1. Select candidate models only after assessing dataset size and coverage.
2. Tune candidates on development/validation data only.
3. Fit calibration only on the designated calibration/validation split.
4. Evaluate once on the locked later test period.
5. Compare with the baseline and include uncertainty and subgroup limitations.
6. Version the model, feature schema, target definition and dataset.
7. Document the result in a model card.

**Exit:** The model is promoted only if the evidence supports its use. If candidates do not beat the baseline, report that and retain the stronger simpler approach or abstain.

## Phase 5 — Manual local web/API vertical slice

1. Build the journey form and multi-passenger input.
2. Preserve original and current status separately.
3. Implement the internal API contract and server-side validation.
4. Run inference from a compatible local model artifact only when one is available.
5. Return an explicit no-model/unsupported result where coverage is absent.
6. Show passenger probabilities, model version, prediction time and limits only when the model is validated.
7. Test end-to-end without external API credentials or network access.

**Exit:** Manual input works end-to-end locally, and no unsupported numeric estimate is fabricated.

## Phase 6 — Group outcome estimates

1. Define the available held-out booking-group population.
2. Implement a transparent group baseline.
3. Evaluate a joint/structured outcome method against that baseline.
4. Measure all-CNF, all-CNF/RAC, exactly-k-CNF and at-least-k-CNF events.
5. Check probability coherence and subgroup coverage.
6. Abstain for groups/categories without supporting evidence.

**Exit:** Group performance is evaluated on labelled groups and does not depend on an unvalidated independence assumption.

## Phase 7 — Hardening and reproducibility

1. Add unit, contract and local integration tests.
2. Add safe CI checks that do not require private datasets or external credentials.
3. Document local setup, configuration, migrations and model loading.
4. Verify log redaction, data boundary and secret hygiene.
5. Test missing model, missing dataset, unsupported input and corrupt artifact behavior.
6. Prepare local release instructions, model card, dataset manifest and runbook.

**Exit:** A clean environment can run core checks and a supported local demo without third-party services.

## Later roadmap phases — Planned core integrations

These are not part of the current implementation sequence through Phase 7, but they are planned capabilities of the target product. Follow [ROADMAP.md](../ROADMAP.md): Phase 8 covers authorized live ticket/status data; Phase 9 covers verified operational/news/event/calendar context with temporal ablation; Phase 10 covers continuous tracking and forecast updates. For each actual provider, obtain source-specific ADR approval, verify access/storage/training/publication terms, assess cost and failure behavior, add privacy/retention controls and a kill switch, and preserve the local/manual fallback. The need for a source-specific ADR is an implementation gate, not a reason to remove these capabilities from the product goal.

## First coding task

Start with the domain schema and status parsing/normalization tests. This is independent of live data and provides the foundation for ingestion, API validation, training and the UI. Verify the exact status mappings from authoritative references before coding them as production behavior.

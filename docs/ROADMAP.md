# Roadmap

Last reviewed: 2026-10-21

This roadmap defines the order of work for RailConfirm Intelligence. It is intentionally phase-based rather than calendar-based: data availability and verified outcomes determine when research phases can exit.

## Scope decision for the current build

The initial version is **local-first and has no third-party runtime integrations**.

- No live IRCTC/PNR API, third-party railway API, hosted news feed, external event API, or provider-backed tracking in the current roadmap.
- The application may have its own internal backend API. "No API" here means no external service/API dependency for the product's core runtime.
- Data may be researched, manually collected, reviewed or prepared by a coding/research agent, and may also be supplied as user-owned files. Every source still needs provenance, applicable licence/terms, permitted-use notes, schema validation and a quality report.
- An agent must not invent data, claim a data source exists without evidence, or bypass a website's restrictions to obtain data.
- The app should work from a controlled local dataset and a versioned model artifact. Missing datasets or unsupported categories must produce an explicit no-data/unsupported state, not a fabricated probability.
- External runtime integration is a later, separately approved direction. It is not part of the MVP or the phases below.

## Product outcome

Deliver a research-backed web application that accepts a train/journey and multiple passenger statuses, estimates passenger-level final-chart outcomes when the dataset supports it, and provides coherent group-level outcome estimates only when the joint approach is validated.

The first milestone is not "show a percentage." It is to produce a defensible end-to-end path from dataset provenance to an evaluated baseline and a clearly qualified result.

## Roadmap at a glance

| Phase | Focus | Main output | Exit gate |
|---|---|---|---|
| 0 | Scope and data feasibility | Locked product/data boundaries and dataset inventory | No unresolved ambiguity about initial runtime integrations; sources and rights are documented |
| 1 | Domain contracts | Tested status parsing and typed request/response contracts | Unknown/malformed statuses are handled explicitly |
| 2 | Dataset intake and quality | Reviewed, versioned local dataset with provenance | Data passes quality, label, permission and leakage checks |
| 3 | Research baseline | Reproducible historical/statistical baseline | Time-safe split and evaluation report can be reproduced |
| 4 | Model candidates and calibration | Compared candidate model and calibrated probabilities | Candidate evaluated on locked later journeys and compared with baseline |
| 5 | Manual web/API vertical slice | Working local manual-entry flow | User can enter a mixed-status booking and receive supported result or honest abstention |
| 6 | Passenger/group outcome quality | Joint/group estimate and evaluation | Group metrics and dependency assumptions are validated |
| 7 | Hardening and reproducible release | Test coverage, model card, setup and release docs | Fresh environment can reproduce the approved demo without third-party APIs |
| Later / out of current scope | Live tracking and external context | Optional integration proposal | Requires new ADR, verified permissions, security/privacy review and measured product need |

Phases can overlap only when their dependencies are satisfied. Do not advance to a later gate by replacing missing evidence with synthetic data.

## Phase 0 — Lock scope and investigate data

### Work
- Confirm that the initial product has no external runtime APIs or provider integrations.
- Inventory candidate historical datasets that agents can discover and prepare lawfully.
- Separate datasets that are merely downloadable from those whose licence/terms permit our actual use: local inspection, transformation, research, model training, aggregate publication and commercial deployment.
- Identify whether records include observation timestamps and verified final outcomes.
- Decide what can safely be committed, what must stay local, and what can be represented only by a schema/manifest in Git.
- Record each candidate in the source register and use the dataset intake checklist.

### Deliverables
- Source register with statuses and rationale.
- Dataset inventory report containing schemas, time range, sample counts, label coverage and open questions.
- Explicit statement of whether a suitable training dataset is available.
- No secrets, raw PNRs, passenger names or unlicensed records committed.

### Exit criteria
- Product/runtime scope is recorded in ADR-0007.
- Every candidate has a documented provenance/usage review.
- At least one legitimate dataset path is identified, or the blocker is documented and the implementation continues only with domain/UI work and clearly labelled synthetic tests.

## Phase 1 — Domain contract and validation

### Work
- Implement domain types for journey context, passenger reservation status, status observations, target definition, prediction output and abstention.
- Preserve raw status text and separately store normalized state/position.
- Establish the accepted status mapping from authoritative references, citing the source and date checked.
- Validate missing, malformed, unknown and unsupported values.
- Cover mixed RAC/WL passenger lists and group identity.
- Define stable reason codes for invalid input, unsupported status and no model.

### Deliverables
- Typed schemas and parsing/normalization functions.
- Unit tests for supported and unsupported status strings, positions, timestamps and mixed bookings.
- API request/response schemas, independent of any third-party provider.
- Developer command to run the tests.

### Exit criteria
- Unknown statuses are never silently mapped to WL/CNF/RAC.
- Raw input is preserved when the schema permits storage.
- All documented invariants have deterministic tests.

## Phase 2 — Agent-assisted dataset intake

### Work
- Have a research/coding agent find candidate data files and primary-source documentation.
- Download or prepare files only where the source and applicable terms permit the intended use.
- Prefer authoritative/open or expressly licensed datasets; a search result or working download link is not sufficient evidence of reuse rights.
- Keep large/raw data outside Git unless its licence, size and privacy properties permit repository storage.
- Create a manifest for each dataset: source, retrieval date, licence/terms, intended permitted use, file hash, schema version, row counts and transformations.
- Validate train/date/class/quota fields, raw statuses, timestamp order, duplicates, contradictory records, missing labels and cohort coverage.
- Clearly isolate synthetic fixtures from any candidate real dataset.
- Do not use raw PNR data or names in the public repo; if a received file contains identifiable information, stop and quarantine it until permitted processing and minimization are established.

### Deliverables
- Dataset intake report.
- Reviewed schema and mapping table.
- Reproducible cleaning/validation scripts.
- Versioned local data manifest and checksums where safe.
- Explicit included/excluded row counts and reasons.

### Exit criteria
- Data origin and intended use are clear.
- Final-outcome labels have a defined meaning and verification basis.
- Data can be regenerated or independently audited to the extent allowed by the source.
- No leakage, privacy or licence blocker remains for the proposed experiment.

## Phase 3 — Baseline before advanced ML

### Work
- Define the primary target moment (initially proposed as final chart) and prediction horizons based on the data actually available.
- Build a historical-frequency baseline with smoothing/fallback behavior.
- Add a simple status-and-time baseline if trajectory data exists.
- Create chronological train/validation/locked-test partitions grouped by booking/journey.
- Reconstruct only features available at each prediction timestamp.
- Evaluate Brier score, log loss, calibration, coverage and subgroup sample counts.
- Report uncertainty and the baseline's known limitations.

### Deliverables
- Reproducible baseline training/evaluation command.
- Versioned experiment record.
- Data quality report and baseline evaluation report.
- Initial model card, even if it documents a baseline rather than ML.

### Exit criteria
- A fresh environment can reproduce the result from approved data and code.
- Split and as-of-time leakage tests pass.
- No performance claim is made beyond the data and evaluation actually support.

## Phase 4 — Candidate ML and calibration

### Work
- Inspect dataset size, class imbalance, missingness and coverage before selecting algorithms.
- Compare one or more suitable tabular models against the baseline.
- Keep preprocessing, feature construction, model fitting and calibration within the development/validation split.
- Evaluate once on the locked later period.
- Run ablation tests before adopting any additional feature group.
- Build a coverage/abstention rule for unsupported combinations.
- Preserve artifacts with dataset version, code revision, feature schema and target definition.

### Deliverables
- Candidate comparison report.
- Calibrated artifact and inference interface, if supported by evidence.
- Locked-test metrics with uncertainty and subgroup counts.
- Updated model card and limitations.

### Exit criteria
- Candidate performance is compared to the baseline using predeclared metrics.
- Calibration and class/segment limitations are reported.
- If no candidate improves the baseline, retain the baseline or abstain; do not force a model release.

## Phase 5 — Manual-entry web/API vertical slice

### Work
- Implement the journey form and dynamic passenger rows.
- Keep original booking status separate from latest observed status.
- Include a status observation timestamp when known and permit an explicit unknown-time state.
- Use the internal API to validate inputs and invoke the local inference service.
- Show either a versioned supported prediction or a clear unsupported/no-model state.
- Present the prediction timestamp, target definition, model version and data limitations.
- Keep all external integrations disabled and unnecessary network calls out of the core user flow.

### Deliverables
- Working local web application.
- Internal API and request/response validation.
- Passenger result table.
- Accessible loading, error, unsupported and no-model states.
- UI/API contract tests.

### Exit criteria
- A manual ticket scenario runs end-to-end without an external provider credential.
- No fake probabilities appear when data/model coverage is missing.
- Mixed statuses do not get collapsed into one ticket-level result.

## Phase 6 — Group outcome estimation

### Work
- Keep passenger probabilities separate from group-level events.
- Establish a group-level baseline.
- Compare a joint/structured outcome method with an explicit assumption-driven baseline.
- Evaluate all-CNF, all-CNF/RAC, exactly-k-CNF and at-least-k-CNF events on held-out bookings.
- Test internal coherence: group outcomes must be compatible with the estimated outcome distribution.
- Document when group estimates are unavailable due to sample size or unsupported categories.

### Deliverables
- Group probability method and tests.
- Group-level evaluation report.
- User-facing terminology for "confirmed berth" versus "at least RAC accommodation."

### Exit criteria
- Group outcomes are not generated by unvalidated independence assumptions.
- The evaluation is based on actual labelled groups, not only synthetic examples.
- Unsupported group outcomes abstain transparently.

## Phase 7 — Hardening and reproducible local release

### Work
- Add unit, contract, integration and frontend tests.
- Add local setup instructions, dependency locking, migration workflow and environment validation.
- Verify privacy-safe logging, local data boundaries and secret scanning.
- Document how to load a reviewed dataset and a model artifact.
- Add model/data version display, basic diagnostic logging and stable error handling.
- Add a CI workflow for safe checks that do not require private datasets or external credentials.
- Verify the application still works with network access to third-party APIs unavailable.

### Deliverables
- Reproducible local installation and test instructions.
- CI checks and safe fixtures.
- Release checklist and runbook.
- Model card and dataset manifest for any included model/data.

### Exit criteria
- Clean setup can run required checks without external runtime APIs.
- Sensitive data is not required for ordinary development tests.
- The scope/status page accurately describes what works and what remains research-only.

## Later — Explicitly out of the current build

Live PNR lookup, automated status refresh, live news/event feeds, external calendar APIs, push notifications and third-party hosted prediction services are not MVP work. Reconsider them only when there is a clear need and a separate ADR establishes:
- source/provider and current terms;
- permitted access, persistence, model use and publication;
- cost/rate-limit and failure behavior;
- privacy, security and retention requirements;
- test strategy and a way to disable the integration;
- evidence that the integration materially improves the product.

## How agents should handle data

An agent may research sources, download permitted data, transform a file, produce a schema summary, or submit a dataset intake report. It must not:
- invent rows, historical values or final outcomes;
- call a restricted service or bypass access restrictions;
- claim a source is licensed based only on availability;
- silently change raw statuses or remove inconvenient rows;
- combine synthetic and real records without persistent labels;
- put personal ticket details into Git or logs;
- train or report metrics before data rights and labels are reviewed.

Data brought by an agent is a candidate input, not automatically an approved training dataset.

## Roadmap change control

Update this document when priorities or gates change. A material change to external integrations, target semantics, model evaluation, data retention or system architecture requires a new sequential ADR. Update the root README, documentation index, changelog and development log in the same roadmap session.

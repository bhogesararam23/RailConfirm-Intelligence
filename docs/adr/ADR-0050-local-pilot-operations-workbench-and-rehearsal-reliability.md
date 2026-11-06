# ADR-0050: Local Pilot Operations Workbench and Rehearsal Reliability

- **Status:** Accepted
- **Date:** 2026-11-06
- **Decision owner:** Project maintainers
- **Related:** ADR-0007, ADR-0043, ADR-0044, ADR-0045, ADR-0046, ADR-0047, ADR-0048, ADR-0049, docs/architecture/API_CONTRACT.md, docs/data/PROSPECTIVE_COLLECTION_PROTOCOL.md, docs/SECURITY_AND_PRIVACY.md

## Context

ADR-0049 introduced `railconfirm.data.rehearsal`, an offline orchestration module verifying the 15-gate prospective data lifecycle. However, two operational limitations remained:
1. **Rehearsal Reliability & Isolation:** Repeated rehearsal executions in persistent parent directories risk path conflicts, partial writes, non-deterministic dict ordering across environments, and unisolated quarantine/run directories.
2. **Operator Usability & Governance Gap:** The prospective data lifecycle (intake audit, submission review, consent withdrawal, export preview/execution, lineage verification, safe reconciliation, and rehearsal execution) was previously operable only via CLI commands and test harnesses. There was no inspectable, UI-driven operator workflow.

Constraints shaping this milestone:
- **Local-first MVP (ADR-0007):** Strictly local-first. No live IRCTC calls, scraping, external APIs, third-party database engines, or hosted services.
- **Strict loopback isolation:** Administrative and operator mutations must not be exposed to network-accessible deployments. The workbench must be disabled by default (`RAILCONFIRM_OPERATOR_ENABLED=false`) and strictly forbidden on non-loopback host interfaces.
- **Data protection & privacy:** No personal data, passenger names, phone numbers, credentials, or raw PNRs may be stored, processed, or displayed. Existing PII scanners must guard persistence.
- **Synthetic integrity:** All operator data is synthetic. The workbench and rehearsal outputs must explicitly state that synthetic outcomes do not represent real railway evidence and do not authorize a real-world pilot.

## Decision

1. **Harden Rehearsal Reliability (`railconfirm.data.rehearsal`):**
   - **Run and Quarantine Isolation:** Every rehearsal run is isolated under dedicated directories: `runs/{run_id}` and `quarantine/{run_id}`.
   - **Explicit Output-Directory Policy:** Refuse to execute into dirty directories containing existing non-empty report files.
   - **Deterministic Output Across Workspaces:** Normalize cross-workspace report dictionaries and SHA-256 fingerprints using canonical sorted keys.
   - **Fail-Closed Diagnostics Recovery:** On unhandled exceptions or report write errors, write an explicit failure diagnostic report rather than leaving corrupt uninspected state.

2. **Add Local Operator Service Layer (`railconfirm.data.operator`):**
   - Provide `OperatorWorkspace` managing isolated batch, review, export, and rehearsal directories under `data/operator/`.
   - Provide `OperatorService` reusing existing domain primitives (`inspect_prospective_batch`, `build_export_candidate`, `reconcile_export_against_source`, `verify_export_lineage`, `execute_rehearsal`).
   - Implement typed, auditable transitions: review decision recording with required operator identity and technical rationale; consent withdrawal audit logging; export preview; longitudinal export execution; and atomic lineage reconciliation.

3. **Establish Local-Only Server-Side Security Boundary (`/v1/operator/*`):**
   - Guard all operator endpoints behind `require_local_operator` FastAPI dependency.
   - If `RAILCONFIRM_OPERATOR_ENABLED` is false, return HTTP 403 `OPERATOR_DISABLED`.
   - If the requesting client IP is not a loopback address (`127.0.0.1`, `::1`), return HTTP 403 `LOCAL_OPERATOR_REQUIRED`.
   - Expose typed endpoints: `GET /v1/operator/status`, `GET /v1/operator/batches`, `POST /v1/operator/batches/seed`, `GET /v1/operator/batches/{batch_id}`, `POST /v1/operator/batches/{batch_id}/review`, `POST /v1/operator/batches/{batch_id}/withdraw`, `GET /v1/operator/batches/{batch_id}/export-preview`, `POST /v1/operator/batches/{batch_id}/export`, `GET /v1/operator/batches/{batch_id}/lineage`, `POST /v1/operator/batches/{batch_id}/reconcile`, `POST /v1/operator/rehearsal/run`, and `GET /v1/operator/rehearsal/latest`.

4. **Build the Operator Workbench UI (`frontend/src/app/operator`):**
   - Extended the Next.js frontend with an Operator interface accessible via the primary header.
   - Components:
     - `OperatorBanner`: Prominent amber notice clarifying offline synthetic governance simulation and pilot non-authorization.
     - `OperatorOverview`: Metric cards (batches, submissions, pending reviews, approved, withdrawn, rehearsal status) and batch switching controls.
     - `BatchAuditView`: Batch metadata, provenance verification, automated PII scan results, and technical eligibility checklist.
     - `SubmissionReviewView`: Pseudonymized submissions table, observation drill-down, and decision recording drawer (with mandatory rationale).
     - `WithdrawalLineageView`: Participant consent withdrawal form, immutable audit trail, export preview, longitudinal export trigger, lineage status badges (`Verified In Sync`, `STALE: Withdrawn Records Present`), and atomic reconciliation.
     - `RehearsalView`: 15-gate rehearsal trigger, gate-by-gate pass/fail breakdown with evidence and human actions, and non-authorization callout.

## Alternatives Considered

- **Embedding operator actions in the public predictor UI:** Rejected. Operator actions are administrative and must have a clear physical and architectural boundary separate from the public-facing prediction interface.
- **Client-side mock storage:** Rejected. The operator workflow must exercise the real backend data service layer and file operations, ensuring atomic integrity and schema adherence.
- **Adding an external SQL database:** Rejected. The local file-based JSON/JSONL format satisfies all current pilot governance requirements without adding heavy external infrastructure or operational overhead.

## Consequences

- Operators have a complete, inspectable visual workbench to audit synthetic data batches, review submissions, exercise participant withdrawal, preview exports, and run the 15-gate lifecycle rehearsal.
- Security and privacy boundaries are strictly enforced server-side via loopback gating and configuration toggles.
- No network dependencies, live IRCTC scraping, or unauthorized pilot credentials were introduced.
- Rehearsal reliability is hardened against path conflicts, race conditions, and non-deterministic serialization.

## Validation

- **Backend Unit & API Tests:** 21 rehearsal tests (`test_rehearsal.py`), 6 operator service tests (`test_operator.py`), and 3 API integration tests (`test_operator_api.py`), contributing to 1,303 total backend tests passing at 94.43% code coverage (above the 90% floor).
- **Frontend Unit Tests:** 9 operator API client tests and 6 operator view component tests in Vitest (144 total frontend unit tests passing).
- **End-to-End Browser Tests:** Playwright E2E suite (`operator.spec.ts`) verifying full operator lifecycle: seeding fixture, PII audit, submission review, export generation, consent withdrawal, lineage staleness, safe reconciliation, and 15-gate rehearsal execution (8 total Playwright E2E tests passing).
- **Socket Smoke & Hygiene:** `scripts/smoke_full_stack.py` (11 checks) and `scripts/check_repository_hygiene.py` passed with 0 link, secret, or ticket data violations.

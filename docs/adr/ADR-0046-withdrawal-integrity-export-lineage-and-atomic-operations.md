# ADR-0046: Withdrawal Integrity, Export Lineage, Decoupled Governance Auditing, and Atomic Local Operations

## Status

Accepted

## Context

Following the operational hardening of the prospective pilot framework (ADR-0045), empirical testing of data lifecycle scenarios revealed critical operational gaps across data provenance, consent reconciliation, and filesystem reliability:

1. **Downstream Provenance Disconnect**:
   - When a prospective batch (`ProspectiveBatch`) is exported into a longitudinal research dataset (`LongitudinalDataset`), earlier implementations provided only basic batch identifier strings in dataset metadata.
   - Without an immutable cryptographic digest of the source batch and structured lineage tracking (such as exact lists of included submissions, excluded submissions, and reason codes), an auditor cannot mathematically verify whether a given longitudinal export matches its approved source batch.

2. **Downstream Erasure and Stale Export Invalidation**:
   - Participant consent withdrawal under research notice v2026.1 and DPDP 2023 principles is an active right. When a participant withdraws consent, their submission status in the local batch file transitions to `ReviewStatus.WITHDRAWN`.
   - However, marking a record withdrawn in a source batch file does *not* automatically modify or delete previously generated downstream artifacts (such as longitudinal JSON datasets in `data/raw/` or derived point-in-time snapshot CSVs).
   - Downstream consumers and ML pipelines lacked an automated mechanism to detect stale exports that inadvertently retain withdrawn or unapproved passenger records.

3. **Withdrawal Idempotency and Non-Identifying Audit Trail**:
   - Repeated withdrawal requests for the same submission (e.g. from follow-up participant communications or re-running scripts) risked overwriting the initial `withdrawn_at` timestamp, destroying chronological audit integrity.
   - Furthermore, tracking withdrawal actions required a dedicated, non-identifying audit log that records operator, timestamp, submission ID, salted pseudonym ID, and reason without retaining any raw PNRs or personal identifiers.

4. **Non-Deterministic Serialization**:
   - Exporting batches into longitudinal datasets previously depended on arbitrary dict iteration and submission ordering. Re-exporting the exact same source records could produce different JSON key ordering and booking group sequences, breaking byte-for-byte reproducibility.

5. **Filesystem Interruption and Corruption Risks**:
   - In-place modifications to JSON batches (e.g., during operator reviews, consent withdrawals, or dataset exports) using standard file writing risked truncating or corrupting files if interrupted mid-write.

6. **Coupled Governance Dimensions**:
   - Audit reporting conflated technical validity with regulatory compliance and operator approval. Operators required granular, independent visibility into 8 distinct governance dimensions, explicit submission accounting, and missing observation/outcome diagnostics.

## Decision

1. **Implement Structured Export Lineage and Canonical Hashing**:
   - Introduce `compute_canonical_batch_sha256(batch: ProspectiveBatch) -> str`, which computes a deterministic SHA-256 digest over submissions sorted canonically by `submission_id`.
   - Embed comprehensive lineage metadata into exported `LongitudinalDataset.metadata["lineage"]`:
     - `source_batch_id`: Identifier of the source prospective batch.
     - `source_batch_sha256`: Canonical digest of the batch at export time.
     - `source_schema_version`: Version of the prospective schema.
     - `exported_at`: ISO 8601 UTC export timestamp.
     - `total_considered`, `total_included`, `total_excluded`: Submission accounting counts.
     - `included_submissions`: Sorted list of approved `submission_id`s included in this export.
     - `excluded_submissions`: Dict mapping excluded `submission_id`s to structured reasons (`withdrawn`, `pending_review`, `quarantined`, `rejected`, `no_passengers`).
     - `exported_booking_group_ids`: Deterministically ordered list of exported booking groups.
     - `exported_journey_ids`: Sorted list of journey keys.

2. **Guarantee Deterministic Export Ordering**:
   - In `export_batch_to_longitudinal()`, enforce deterministic sorting:
     - Journeys dictionary sorted by journey key.
     - Booking groups sorted by `booking_group_id`.
     - Passenger reservations sorted by `passenger_sequence`.
     - Intermediate status observations sorted chronologically by `observed_at`.
   - Accept an optional `export_timestamp: datetime | None` parameter, ensuring byte-for-byte identical output across independent export runs with identical inputs.

3. **Implement Export Lineage Verification and Stale Export Detection**:
   - Introduce `LineageStatus` enum:
     - `VERIFIED_IN_SYNC`: Dataset perfectly matches source batch; zero withdrawn or unapproved records.
     - `STALE_WITHDRAWN_RECORDS_PRESENT`: Dataset contains booking groups whose consent was withdrawn after export.
     - `STALE_UNAPPROVED_RECORDS_PRESENT`: Dataset contains unapproved records.
     - `STALE_SOURCE_MODIFIED`: Source batch modified or contains new approved records not yet in export.
     - `INCOMPATIBLE`: Dataset was generated from a completely different batch ID.
   - Provide `verify_export_lineage(batch, dataset) -> ExportLineageReport` to audit exports against source batches and surface exact group IDs requiring remediation.

4. **Automate Safe Export Reconciliation and Atomic Re-export**:
   - Provide `reconcile_and_regenerate_export(batch, current_dataset, output_path, overwrite=True) -> tuple[LongitudinalDataset, ExportLineageReport]`.
   - Atomically regenerates a clean longitudinal dataset excluding any withdrawn or unapproved records, updates lineage metadata, and verifies that the output transitions to `VERIFIED_IN_SYNC`.

5. **Ensure Withdrawal Idempotency and Non-Identifying Audit Trail**:
   - Create `WithdrawalAuditRecord` dataclass recording `withdrawn_at`, `batch_id`, `submission_id`, `pseudonym_group_id`, `prior_review_status`, `operator`, and `reason`.
   - Attach append-only `withdrawal_log: list[WithdrawalAuditRecord]` to `ProspectiveBatch`.
   - In `withdraw_submission()`, enforce idempotency: if a submission was previously withdrawn, retain the original `withdrawn_at` timestamp while recording the operator's action in `withdrawal_log`.
   - Permit withdrawal from any prior status (`APPROVED`, `QUARANTINED`, `REJECTED`, `PENDING_REVIEW`).

6. **Implement Atomic JSON Serialization Utility**:
   - Add `atomic_write_json(path, data, indent=2, sort_keys=False) -> Path`.
   - Writes serialization output to a temporary file in the destination directory (`dir=target.parent`, prefix=`.tmp_`), flushes and fsyncs buffers, and renames atomically via `os.replace`.
   - Replaces all direct JSON file writing across `ProspectiveBatch.save()` and export utilities.

7. **Decouple Eight Governance Dimensions and Detail Missing Data Diagnostics**:
   - Update `ProspectiveAuditReport` and `validate_prospective_batch()` to evaluate eight explicit boolean gates:
     1. `is_structurally_valid`: Syntactically correct and schema-compliant.
     2. `is_technically_eligible`: Satisfies minimum row and date thresholds for intake.
     3. `is_privacy_clean`: Zero PII or raw 10-digit PNR patterns detected.
     4. `is_consent_valid`: Valid opt-in basis, notice version, and active consent.
     5. `is_operator_approved`: Human operator approved with rationale.
     6. `is_legally_reviewed`: Compliance with research purposes and DPDP 2023 obligations.
     7. `is_scientifically_adequate`: Meets operational feasibility pilot thresholds.
     8. `is_model_training_approved`: Unanimously True across all prerequisite gates.
   - Surface submission accounting (`eligible`, `pending`, `withdrawn`, `rejected`, `quarantined`).
   - Surface observation diagnostics (`missing_observation_count`, `missing_outcome_count`, `unverified_outcome_count`, `censored_outcome_count`).
   - Surface quality warnings (low observation density, high train or date concentration, post-departure observations).

8. **Expand Operator CLI Capabilities**:
   - Add `prospective verify-export <batch> <dataset> [--json]` to verify export lineage.
   - Add `prospective reconcile <batch> <dataset> [--output <path>] [--dry-run]` to purge stale records.
   - Add `--dry-run` to `prospective withdraw` and `prospective review` to preview state transitions before applying filesystem modifications.

## Consequences

### Positive

- **Full Scientific Traceability**: Every exported longitudinal dataset documents exactly which source batch produced it, its canonical SHA-256 digest, and an explicit list of included and excluded submission IDs.
- **Auditable Participant Erasure**: When a participant exercises their right to withdraw, operators can detect stale exports with `verify-export` and purge them atomically with `reconcile`.
- **Zero In-Flight Corruption**: Atomic writes ensure partial or interrupted CLI runs cannot corrupt existing batch files.
- **Granular Governance Transparency**: Decoupling the 8 governance dimensions prevents conflating technical syntax checks with human operator approval or legal compliance.
- **Deterministic Experiments**: Exports are 100% reproducible byte-for-byte across machines and environments.

### Negative & Operational Requirements

- Downstream training pipelines must invoke `verify_export_lineage` to confirm the export is `VERIFIED_IN_SYNC` before ingesting data for model training.
- Reconciling an export after a withdrawal requires re-running downstream point-in-time snapshot generation and manifest digest calculation.


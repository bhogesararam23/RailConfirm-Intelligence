# ADR-0044: Consent-Aware Prospective Collection and Operator Governance

## Status

Accepted

## Context

Phase 2 and long-term roadmap Phases 8–10 require preparing for legitimate real-world data collection while strictly respecting privacy, legal consent, and repository security constraints:
1. **PNR and personal data sensitivity:** Indian Railways 10-digit PNRs are sensitive booking references that permit retrieval of personal passenger names, contact numbers, and travel details. ADR-0005 and `AGENTS.md` explicitly prohibit committing or storing raw PNR numbers, passenger names, or personal identifiers.
2. **Consent and purpose specification:** Modern privacy regulations (such as India's Digital Personal Data Protection Act and international privacy frameworks) require explicit notice, consent basis, specified research purposes, and clear retention limits.
3. **Decoupling technical intake from research approval:** A file that is structurally valid or free of personal data is not automatically approved for model training. Operator governance must require named human reviewers and written rationale before any prospective submission can enter a research dataset.
4. **Local-first boundary (ADR-0007):** Prospective collection must not introduce public network ingestion endpoints, unauthenticated scrapers, or third-party cloud runtime dependencies. Collection must remain disabled by default, running under local operator review.

## Decision

1. **Versioned Prospective Collection Format (`PROSPECTIVE_COLLECTION_SCHEMA_VERSION = "1.0.0"`)**:
   - Organized into `ProspectiveBatch` and `ProspectiveSubmission`.
   - Each submission requires a `ConsentMetadata` record specifying `consent_basis` (`explicit_opt_in`, `user_initiated_submission`, `institutional_research_agreement`), `notice_version`, `purpose_records`, and `retention_policy`.
   - All collection is disabled by default; submissions are stored only in local storage directories.

2. **Automated Personal Data and Raw PNR Scanner**:
   - Provide `scan_for_personal_data` scanning incoming records for 10-digit Indian Railways PNR patterns (`\b[1-9]\d{2}[-\s]?\d{7}\b`), email addresses, mobile numbers, and 12-digit national ID/Aadhaar numbers.
   - Any detected personal identifier automatically fails technical intake and flags the submission as `QUARANTINED`.

3. **Cryptographically Salted Pseudonym Derivation**:
   - Provide `derive_pseudonym` utilizing HMAC-SHA256 with a local deployment secret salt.
   - Replaces raw booking references and passenger keys with one-way pseudonyms (e.g. `anon_a1b2c3d4e5f60718`), ensuring no original identifying token is retained in storage or exported datasets.

4. **Operator Review and Approval Governance**:
   - Prospective submissions transition through states: `PENDING_REVIEW` -> `APPROVED` / `REJECTED` / `QUARANTINED`.
   - `approve_batch_for_research` requires a non-empty named human reviewer and explicit rationale.
   - Quarantined submissions containing unresolved personal data patterns cannot be approved.
   - `export_batch_to_longitudinal` requires batch approval before converting prospective records into a `LongitudinalDataset` (v2.0.0).

5. **Cryptographic Quarantine Workflow**:
   - Provide `quarantine_dataset` moving contaminated or malformed files into `data/quarantine/`.
   - Generates a sidecar `.quarantine.json` recording SHA-256 digest, original path, timestamp, operator name, quarantine reason, and diagnostic details.
   - Expose `python -m railconfirm.data quarantine` CLI command.

## Consequences

- Prospective collection is safeguarded against accidental leakage of PNRs, passenger names, and contact details.
- Technical validity and human legal/ethical approval remain strictly separate.
- Approved prospective batches convert seamlessly into longitudinal research datasets for model training.
- Complies fully with ADR-0005, ADR-0007, and repository data governance rules.

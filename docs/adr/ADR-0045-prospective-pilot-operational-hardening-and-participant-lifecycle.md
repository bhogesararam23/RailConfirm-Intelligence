# ADR-0045: Prospective Pilot Operational Hardening, Scientific Coverage, and Participant Withdrawal Lifecycle

## Status

Accepted

## Context

Following the establishment of the longitudinal contract (ADR-0043) and prospective intake schema (ADR-0044), operational preparation for an empirical Indian Railways reservation outcome pilot revealed critical technical, privacy, and scientific gaps:

1. **Pseudonymization vs. Anonymization Distinction**:
   - Cryptographic HMAC hashing with a private salt constitutes **pseudonymization**, not automatically irreversible anonymization in the legal sense (e.g., under GDPR Recital 26 or India's Digital Personal Data Protection Act 2023).
   - In Indian Railways, the 10-digit PNR space is finite and bounded by at most $10^{10}$ combinations (~33 bits of entropy). If the salt is short, weak, or exposed, brute-force dictionary inversion is computationally feasible on consumer hardware.
   - Auxiliary travel parameters (train number, journey date, boarding station, destination station, coach class, and booking sequence) introduce re-identification and linkage risks that require qualitative governance beyond hashing.

2. **Scope of Consent and Software Licensing**:
   - Explicit participant consent under research notice v2026.1 authorizes non-commercial empirical queue dynamics and confirmation probability modeling; it does not confer unrestricted rights, commercial exploitation rights, or secondary data warehousing.
   - The repository's open-source license (Apache-2.0) applies strictly to original source code and artifacts authored in this project; it does not grant rights over third-party participant contributions.

3. **Technical Safeguard Boundaries**:
   - Heuristic regex scanning catches obvious identifier patterns (10-digit PNRs, emails, phone numbers, Aadhaar, PAN, passport, and credential query tokens), but cannot prove the absence of personal data (such as unpatterned names, rare itinerary combinations, or quasi-identifiers).
   - Technical validation must not be conflated with formal legal compliance or human ethical approval.

4. **Participant Consent Withdrawal and Erasure**:
   - Participants hold the right to withdraw consent prior to dataset publication.
   - Without an explicit lifecycle, a withdrawn contribution could inadvertently remain in local batches, undergo operator approval, or be exported into downstream longitudinal training frames.

5. **Defensible Scientific Pilot Thresholds**:
   - The previously suggested minimum of 200 passenger reservations across 4 journey dates is scientifically insufficient for temporal evaluation. A chronological train/validation split with gap days leaves fewer than 2 dates per partition, and rolling-origin evaluation cannot construct expanding origin windows.
   - Separate, defensible thresholds must be established for operational feasibility, technical intake, temporal baseline modeling, and subgroup analysis.

6. **Local Operator Tooling**:
   - Operators require local-first tooling to generate validated blank template batches, conduct rich audits against scientific thresholds, execute consent withdrawals, simulate exports safely via dry-runs, and prevent accidental data overwrites.

## Decision

1. **Enforce Strong Salt Entropy in `derive_pseudonym`**:
   - Require a minimum salt length of 32 characters (`MIN_SALT_LENGTH = 32`). Refuse shorter salts with `SecurityError` to resist dictionary attacks across the finite PNR space ($10^{10}$).
   - Mandate that deployment salts remain strictly confidential in environment variables and are never committed to version control or included in exports.

2. **Formalize Participant Consent Withdrawal Lifecycle**:
   - Extend `ConsentMetadata` with `withdrawn: bool = False`, `withdrawn_at: str | None = None`, and `withdrawal_reason: str | None = None`.
   - Add `ReviewStatus.WITHDRAWN` to the review lifecycle.
   - Provide `withdraw_submission(batch, submission_id, reason, operator)` and CLI subcommand `python -m railconfirm.data prospective withdraw`.
   - Enforce that `review_batch(action=ReviewStatus.APPROVED)` and `export_batch_to_longitudinal()` strictly refuse or exclude withdrawn submissions.

3. **Enforce Passenger and Journey Invariants**:
   - Refuse identical boarding and destination stations (`boarding_station != destination_station`).
   - Enforce passenger reservation bounds: $1 \le n \le 6$ for standard bookings, and $1 \le n \le 4$ for Tatkal (`TQ`) bookings, matching Indian Railways ticketing limits.
   - Require strictly positive, contiguous passenger sequences ($1, 2, \dots, n$).
   - Require strictly chronological observation timestamps ($t_0 < t_1 < \dots < t_n$) within each passenger record.
   - Validate outcome verification integrity: an outcome marked `LabelConfidence.VERIFIED` must provide a known `VerificationMethod` (not `UNKNOWN`) and document `verification_source`.
   - Detect duplicate journey contributions within a batch and report them during validation.

4. **Establish Four Scientific Pilot Thresholds in `ProspectiveAuditReport`**:
   - **Operational Feasibility Pilot**: $\ge 30$ passenger reservations, $\ge 3$ distinct journey dates, $\ge 2$ distinct trains. Validates toolchain, consent workflow, and IRCTC public chart verification. Cannot train generalizable models.
   - **Technical Intake Eligibility**: Structurally valid, $\ge 50$ passenger reservations, $\ge 2$ distinct dates. Satisfies format and manifest intake requirements.
   - **Temporal Baseline Experiment**: $\ge 300$ passenger reservations, $\ge 12$ distinct journey dates spanning $\ge 28$ days (4 weeks), $\ge 2$ major classes with $\ge 50$ rows each. Supports 1 chronological train/validation split with gap days and rolling-origin evaluation.
   - **Subgroup and Group-Outcome Evaluation**: $\ge 1,000$ passenger reservations, $\ge 30$ distinct journey dates, $\ge 150$ multi-passenger booking groups ($n \ge 2$). Supports comonotonic queue bounds vs. independence evaluation and subgroup calibration.

5. **Operationalize Local-First Operator CLI Tooling**:
   - Add `python -m railconfirm.data prospective template <output.json>` to generate valid, schema v1.0.0 starter templates with zero PII.
   - Add `python -m railconfirm.data prospective audit <batch.json>` to evaluate and report batch integrity, coverage, and threshold readiness.
   - Add `--overwrite` guard and `--dry-run` simulation mode to `prospective export`.
   - Support single-submission review via `prospective review --submission-id <id>`.

6. **Decouple the Five Governance Layers**:
   Explicitly separate and document:
   - (1) Technical safeguards (regex scanning, salted HMAC, invariant checking).
   - (2) Participant consent and documented notice purpose (v2026.1).
   - (3) Legal review and applicable data protection obligations (requiring qualified counsel).
   - (4) Human operator research approval (`approved_for_training`).
   - (5) Commercial-use permission (not granted by participant notice or Apache-2.0).

## Consequences

- The prospective intake pipeline is hardened against cryptographic salt weakness, out-of-order observations, and invalid passenger configurations.
- Data subject rights to consent withdrawal are enforced durably at the data contract, storage, and export levels.
- Scientific expectations for Phase 3 readiness are quantitatively anchored, preventing premature baseline claims on underpowered datasets.
- Operational commands are safe, reproducible, and fully local-first (ADR-0007).

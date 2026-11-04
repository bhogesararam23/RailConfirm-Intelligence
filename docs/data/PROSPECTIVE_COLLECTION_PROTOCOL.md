# Prospective pilot collection operating protocol

Last reviewed: 2026-11-04  
Status: Active operational protocol  
Governance: [ADR-0044](../adr/ADR-0044-consent-aware-prospective-collection-and-operator-governance.md), [ADR-0043](../adr/ADR-0043-versioned-longitudinal-observation-contract-and-point-in-time-snapshot-conversion.md), and [ADR-0007](../adr/ADR-0007-local-first-no-external-runtime-apis.md)  
Implementation: [backend/railconfirm/data/prospective.py](../../backend/railconfirm/data/prospective.py) and [backend/railconfirm/data/longitudinal.py](../../backend/railconfirm/data/longitudinal.py)

---

## 1. Purpose and foundational principles

This protocol establishes the operational procedure for collecting genuine, consented Indian Railways reservation outcome data. It serves as the primary actionable route to satisfy the real-data validation gate of **Phase 2 (Dataset Intake and Quality)** and enable **Phase 3 (Research Baseline)**.

### Core principles
1. **Local-first execution**: Collection operates strictly under local operator control. No public submission API, automated web crawler, or external cloud ingestion endpoints are deployed (ADR-0007).
2. **Explicit, unbundled consent**: Every participant record must carry explicit, verifiable consent metadata detailing permitted research purposes and notice versions.
3. **Data minimization**: Passenger names, email addresses, phone numbers, Aadhaar numbers, and raw 10-digit PNR numbers are strictly forbidden from entering storage or datasets.
4. **Cryptographic pseudonymization**: Group and passenger identifiers are derived using one-way HMAC-SHA256 keyed with a local deployment secret salt.
5. **Decoupled review governance**: Technical intake validity is strictly decoupled from human legal and research approval. No collected data enters training without a signed human review decision.

---

## 2. Participant contribution workflow

### What the participant provides
When a passenger books a train ticket with a waitlisted (WL) or Reservation Against Cancellation (RAC) status, they voluntarily contribute:
- **Journey parameters**: Train number (5 digits), journey date (`YYYY-MM-DD`), boarding station (IR code), destination station (IR code), class code (`1A`, `2A`, `3A`, `SL`, `CC`, `2S`), and quota code (`GN`, `TQ`, `LD`, etc.).
- **Initial reservation status**: Raw booked status text and queue position (e.g., `GNWL/45`, `RLWL/12`, `RAC/8`).
- **Passenger sequence**: Relative order of passengers in a multi-passenger booking (1, 2, ..., $n$) without names or demographics.
- **Sequential status observations**: Periodic updates as the journey date approaches.
- **Final chart outcome**: The definitive status recorded on the reservation chart.

### How the purpose is explained to participants
Participants are informed that:
- Data is collected exclusively for non-commercial academic and open-source railway confirmation probability research, queue movement modeling, and cancellation analysis.
- Raw personal data and 10-digit PNRs are never retained.
- Participation is voluntary and consent can be withdrawn at any time prior to dataset publication.

---

## 3. Observation cadence and timeline

To support longitudinal queue tracking and point-in-time snapshotting, observations should be recorded at standardized lead-time intervals:

```
[ Booking Instant ] ---------------> [ Periodic Checkpoints ] ---------------> [ Final Chart Preparation ]
     t_booking                         Day -14, Day -7, Day -3, Day -1               t_chart (Departure - 4h)
 Initial Status Recorded               Sequential Observations Logged                Definitive Outcome Frozen
```

### Standard observation checkpoints
1. **$t_{\text{booking}}$ (Initial Booking)**: Recorded immediately upon ticket generation (e.g., Day -30 to Day -120).
2. **$t_{-14\text{d}}$ (Two Weeks Prior)**: Captures early cancellation movement.
3. **$t_{-7\text{d}}$ (One Week Prior)**: Benchmark checkpoint for medium-term forecasting.
4. **$t_{-3\text{d}}$ (72 Hours Prior)**: Period preceding Tatkal quota opening.
5. **$t_{-24\text{h}}$ (24 Hours Prior)**: Immediate pre-charting movement and post-Tatkal cancellation cascade.
6. **$t_{\text{chart}}$ (Final Charting)**: Definitive chart preparation (typically 4 hours before scheduled departure, or the preceding evening for trains departing before 12:00 IST).

All observation timestamps must be recorded as timezone-aware ISO-8601 strings in Asia/Kolkata (`+05:30`) or UTC.

---

## 4. Independent final-chart outcome verification

A reservation outcome must be independently verified to qualify for empirical model evaluation. Two verification methods are supported:

### Method A: IRCTC public chart visualization (Preferred)
Indian Railways provides a public reservation chart enquiry surface at `https://www.irctc.co.in/online-charts/`:
- **Operation**: Prepared charts are published 4 hours before departure for every train and station.
- **Privacy**: The public chart visualization shows coach layouts, berth allocations, and booked status without requiring or displaying 10-digit PNR numbers.
- **Verification**: The operator inspects the chart for the specified train, date, class, and quota, cross-verifying the cleared waitlist passenger sequence against the berth allocation table.
- **Verification method label**: `VerificationMethod.CHART_SNAPSHOT` with `LabelConfidence.VERIFIED`.

### Method B: Operator attestation of passenger confirmation receipt
Where a participant provides an official confirmation SMS or final booking PDF:
- The operator redacts all personal identifiers and confirms the final status transition (`CNF`, `RAC <number>`, or `WL <number>`).
- **Verification method label**: `VerificationMethod.OPERATOR_ATTESTATION` with `LabelConfidence.VERIFIED`.

---

## 5. Automated data minimization and pseudonymization

### PII scanner safeguard
Every prospective submission batch must pass `scan_for_personal_data()` (`backend/railconfirm/data/prospective.py`) before storage or operator review:
- Scans for 10-digit PNR patterns (`\b[1-9]\d{2}[-\s]?\d{7}\b` or `\b[1-9]\d{9}\b`).
- Scans for email addresses, Indian mobile phone numbers (`+91` / 10-digit starting 6–9), and 12-digit Aadhaar / national ID patterns.
- If any violation is detected, `intake_prospective_submission` immediately transitions the submission to `ReviewStatus.QUARANTINED` and halts processing.

### Cryptographic pseudonym derivation
Identifiers are anonymized using cryptographically salted HMAC-SHA256:
$$\text{pseudonym} = \text{"anon\_"} + \text{HMAC-SHA256}(\text{salt}, \text{raw\_booking\_reference})[:16]$$
- The salt (`RAILCONFIRM_PSEUDONYM_SALT`) is a high-entropy string held exclusively by the local operator in the environment, never committed to Git.
- Pseudonymization is one-way: given the pseudonym, the original booking reference cannot be recovered without the private salt.

---

## 6. Handling anomalies, censoring, and missing outcomes

In real railway operations, reservation records frequently encounter exceptional terminal states. These must be rigorously categorized rather than silently dropped or fabricated:

1. **User cancellation (`CensoringReason.USER_CANCELLED`)**:
   - The passenger cancelled their waitlisted ticket before final charting.
   - *Handling*: The historical observations up to cancellation are valid for survival analysis, but the row is marked `is_censored = True`. It is excluded from standard final-chart classification training snapshots.
2. **Train cancellation (`CensoringReason.TRAIN_CANCELLED`)**:
   - The train service was cancelled by railway administration due to operational or weather disruption.
   - *Handling*: Marked `is_censored = True`.
3. **Missing or unverified chart outcome (`CensoringReason.CHART_NOT_RECORDED`)**:
   - The participant failed to provide the final chart status or public chart verification was missed.
   - *Handling*: Marked `is_censored = True`. Refused from training partitions.
4. **Transition anomalies**:
   - A passenger status regresses from confirmed (`CNF`) to waitlist (`WL`), or from `RAC` to higher `WL`.
   - *Handling*: Flagged by `validate_longitudinal_dataset()`. Quarantined for manual operator review to determine whether a coach restructuring occurred.

---

## 7. Sampling bias and dataset limitations

Any dataset collected under this prospective protocol possesses inherent limitations that must be recorded on the model card and artifact metadata:
- **Self-selection bias**: Passengers who actively track and submit waitlisted tickets tend to travel on high-demand routes (e.g., Delhi–Mumbai, Delhi–Howrah) and during festival or peak vacation seasons.
- **Quota concentration**: General (`GN`) and Tatkal (`TQ`) quotas will be overrepresented compared to specialized administrative quotas (`DF`, `FT`, `DP`).
- **Class imbalance**: Sleeper (`SL`) and 3-Tier AC (`3A`) account for the vast majority of waitlist bookings; 1st AC (`1A`) has very small cohort sizes.
- **Mitigation**: The training pipeline enforces `EligibilityThresholds` (minimum distinct journey dates, minimum rows per cohort, and Laplace smoothing) to ensure models abstain when sample coverage is insufficient.

---

## 8. Operator review and export lifecycle

```
[ Contributed Batch ]
        │
        ▼
[ Automated PII Scan ] ────────► (Violations Found) ──► [ QUARANTINED ]
        │ (Clean)
        ▼
[ PENDING_REVIEW ]
        │
        ├──► Operator Reviews Consent & Integrity
        │
        ▼
[ APPROVED ] ──► (Run `prospective export`) ──► [ Longitudinal Dataset (v2.0.0) ]
                                                            │
                                                            ▼ (Run `snapshot`)
                                                 [ Point-in-Time Snapshot (v1.1.0) ]
                                                            │
                                                            ▼ (Run `manifest`)
                                                 [ Signed Approved Manifest ]
                                                            │
                                                            ▼
                                                 [ Phase 3 Model Training ]
```

### Command execution steps
1. **Scan the batch**:
   ```bash
   python -m railconfirm.data prospective scan data/prospective/batch_001.json
   ```
2. **Validate the batch report**:
   ```bash
   python -m railconfirm.data validate data/prospective/batch_001.json
   ```
3. **Record operator approval**:
   ```bash
   python -m railconfirm.data prospective review data/prospective/batch_001.json \
       --action approve \
       --reviewer "maintainer_lead" \
       --rationale "Verified 240 passenger reservations across 6 journey dates. PII scan clean."
   ```
4. **Export to longitudinal research dataset**:
   ```bash
   python -m railconfirm.data prospective export data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json \
       --dataset-id pilot_longitudinal_v1 \
       --source-id prospective_pilot_2026_1
   ```
5. **Derive Day-7 training snapshot**:
   ```bash
   python -m railconfirm.data snapshot data/raw/longitudinal_pilot_v1.json \
       data/interchange/pilot_snapshot_d7.csv \
       --as-of-lead-days 7
   ```
6. **Generate and sign manifest**:
   ```bash
   python -m railconfirm.data manifest data/interchange/pilot_snapshot_d7.csv \
       --dataset-id pilot_snapshot_d7 \
       --title "Prospective Pilot Day-7 Training Snapshot" \
       --retrieved-on 2026-11-04 \
       --status candidate
   ```

---

## 9. Draft participant consent notice

> [!IMPORTANT]
> **LEGAL NOTICE**: The text below is a **DRAFT** participant consent disclosure prepared for operational planning. It does not constitute formal legal approval or finalized legal advice. It must be reviewed and customized by the maintainer and legal counsel before distribution to participants.

```text
================================================================================
DRAFT RESEARCH PARTICIPANT CONSENT NOTICE (VERSION 2026.1)
RAILCONFIRM INTELLIGENCE — RAILWAY RESERVATION OUTCOME RESEARCH PROJECT
================================================================================

1. STUDY OBJECTIVE
You are invited to contribute railway journey observation data to RailConfirm
Intelligence, an open-source, non-commercial software research initiative
aimed at studying queue dynamics, confirmation probabilities, and cancellation
rates in Indian Railways passenger reservation systems.

2. WHAT DATA IS COLLECTED
If you agree to participate, you will provide:
- Train number, journey date, travel class, and quota.
- Your initial booked waitlist/RAC status and position (e.g., GNWL 45).
- Subsequent status updates observed prior to departure.
- The final chart confirmation status for the journey.

3. WHAT IS NEVER COLLECTED OR STORED
- Your name, address, email address, or phone number.
- Your 10-digit Indian Railways PNR number.
- Payment details, transaction IDs, or ticketing receipts.
All journey records are assigned randomized, pseudonymous identifiers before
entering any research files.

4. PERMITTED USES
The contributed data will be used strictly for:
- Academic and empirical analysis of railway waitlist clearance rates.
- Training and evaluating open-source statistical and machine-learning models.
- Publishing aggregate benchmark metrics and error calibration curves.
Your data will NOT be used for commercial advertising, marketing, or passenger
tracking.

5. VOLUNTARY PARTICIPATION AND WITHDRAWAL
Participation is entirely voluntary. You may withdraw your consent and request
the permanent deletion of your un-aggregated contribution at any time by
submitting a deletion request with your submission identifier prior to formal
dataset publication.

6. RESEARCHER ATTESTATION
RailConfirm Intelligence operates under strict local-first data protection
protocols. Contributed data is validated, anonymized, and reviewed by human
research operators before any modeling analysis.

================================================================================
```

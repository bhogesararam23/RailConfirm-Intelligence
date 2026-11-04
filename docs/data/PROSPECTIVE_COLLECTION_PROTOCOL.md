# Prospective pilot collection operating protocol

Last reviewed: 2026-11-04  
Status: Active operational protocol  
Governance: [ADR-0045](../adr/ADR-0045-prospective-pilot-operational-hardening-and-participant-lifecycle.md), [ADR-0044](../adr/ADR-0044-consent-aware-prospective-collection-and-operator-governance.md), [ADR-0043](../adr/ADR-0043-versioned-longitudinal-observation-contract-and-point-in-time-snapshot-conversion.md), and [ADR-0007](../adr/ADR-0007-local-first-no-external-runtime-apis.md)  
Implementation: [backend/railconfirm/data/prospective.py](../../backend/railconfirm/data/prospective.py) and [backend/railconfirm/data/longitudinal.py](../../backend/railconfirm/data/longitudinal.py)

---

## 1. Purpose and governance framework

This protocol establishes the operational procedure for collecting genuine, consented Indian Railways reservation outcome data. It serves as the primary actionable route to satisfy the real-data validation gate of **Phase 2 (Dataset Intake and Quality)** and enable **Phase 3 (Research Baseline)**.

> [!WARNING]
> **LEGAL AND GOVERNANCE DISCLAIMER**:
> This document establishes operational and technical procedures for research planning. It does **not** constitute formal legal advice, a binding legal contract, or official regulatory approval. Prior to recruiting real human participants or initiating a live data collection campaign, the repository maintainer must obtain qualified legal counsel review in the applicable jurisdictions (including compliance with India's Digital Personal Data Protection Act 2023 and relevant privacy frameworks).

### The five decoupled governance layers

To prevent conflating software readiness with regulatory or ethical authority, prospective collection is governed across five strictly decoupled layers:

| Layer | Governance Scope | Responsible Entity | Verification Instrument |
|---|---|---|---|
| **1. Technical Safeguards** | PII regex scanning, salted HMAC derivation, structural invariant validation | Automated code execution | `scan_for_personal_data()`, `validate_prospective_batch()`, unit tests |
| **2. Participant Consent** | Explicit disclosure of study scope, notice version (v2026.1), and voluntary agreement | Participating data subject | `ConsentMetadata` record with cryptographic hash |
| **3. Legal Review** | Statutory compliance, cross-border obligations, data subject rights, terms of service | Qualified legal counsel | Formal maintainer authorization & legal opinion |
| **4. Research Operator Approval** | Data quality review, chart verification audit, research suitability decision | Named human maintainer | `prospective review --action approve`, signed manifest |
| **5. Commercial-Use Permission** | Commercial licensing, monetization, or secondary product integration | Data controller / Rights holder | Explicit commercial license (strictly excluded here) |

The project's open-source software license (**Apache-2.0**) applies exclusively to the original software code and algorithms authored in this repository. It does **not** grant rights over participant-contributed reservation data.

---

## 2. Participant contribution workflow

### What the participant provides
When a passenger books a train ticket with a waitlisted (WL) or Reservation Against Cancellation (RAC) status, they voluntarily contribute:
- **Journey parameters**: Train number (5 digits), journey date (`YYYY-MM-DD`), boarding station (IR code), destination station (IR code), class code (`1A`, `2A`, `3A`, `SL`, `CC`, `2S`), and quota code (`GN`, `TQ`, `LD`, etc.).
- **Initial reservation status**: Raw booked status text and queue position (e.g., `GNWL/45`, `RLWL/12`, `RAC/8`).
- **Passenger sequence**: Relative order of passengers in a multi-passenger booking (1, 2, ..., $n$) without names, ages, or demographics.
- **Sequential status observations**: Periodic queue updates observed prior to departure.
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

## 4. Final-chart outcome verification methods

A reservation outcome must be independently verified to qualify for empirical model evaluation. Two distinct verification methods are supported:

### Method A: IRCTC public chart visualization (Preferred)
Indian Railways provides a public reservation chart enquiry surface at `https://www.irctc.co.in/online-charts/`:
- **Operation**: Prepared charts are published 4 hours before departure for every train and station.
- **Privacy**: The public chart visualization shows coach layouts, berth allocations, and booked status without requiring or displaying 10-digit PNR numbers.
- **Verification**: The operator inspects the chart for the specified train, date, class, and quota, cross-verifying the cleared waitlist passenger sequence against the berth allocation table.
- **Verification method label**: `VerificationMethod.CHART_SNAPSHOT` with `LabelConfidence.VERIFIED`.
- **Legal and data limits**: Public chart availability permits an operator to visually verify the clearing threshold of a specific coach. It does **not** grant rights to scrape, retain full-coach passenger rosters, redistribute bulk chart archives, or use raw IRCTC chart dumps for commercial model training.

### Method B: Operator attestation of passenger confirmation receipt
Where a participant provides an official confirmation SMS or final booking PDF:
- The operator redacts all personal identifiers and confirms the final status transition (`CNF`, `RAC <number>`, or `WL <number>`).
- **Verification method label**: `VerificationMethod.OPERATOR_ATTESTATION` with `LabelConfidence.VERIFIED`.
- **Verification basis**: Unlike Method A, operator attestation relies on participant-submitted receipts. The operator must record the redacted confirmation receipt reference in `verification_source`.

---

## 5. Technical privacy safeguards and pseudonymization limits

### PII regex scanner safeguard
Every prospective submission batch must pass `scan_for_personal_data()` (`backend/railconfirm/data/prospective.py`) before storage or operator review:
- Scans for 10-digit Indian Railway PNR patterns (`\b[1-9]\d{2}[-\s]?\d{7}\b` or `\b[1-9]\d{9}\b`), including numeric integer representations.
- Scans for email addresses, Indian mobile phone numbers (`+91` / 10-digit starting with 6–9), 12-digit Aadhaar national ID numbers, Indian PAN tax IDs (`[A-Z]{5}[0-9]{4}[A-Z]{1}`), passport numbers (`[A-Z][1-9]\d{6}`), and credential query tokens (`token=`, `auth=`, `secret=`).
- If any violation is detected, `intake_prospective_submission` immediately transitions the submission to `ReviewStatus.QUARANTINED` and halts processing.
- **Technical limitation**: This regex scanner is a heuristic sanity check. It cannot detect unpatterned human names or subtle quasi-identifiers. Human operator review is mandatory.

### Cryptographic pseudonym derivation and auxiliary linkage risks
Identifiers are pseudonymized using cryptographically salted HMAC-SHA256:
$$\text{pseudonym} = \text{"anon\_"} + \text{HMAC-SHA256}(\text{salt}, \text{raw\_booking\_reference})[:16]$$
- **Entropy constraints**: The space of all possible 10-digit Indian Railway PNRs is bounded by at most $10^{10}$ combinations (~33 bits of entropy). On consumer hardware, an HMAC dictionary search across $10^{10}$ numbers takes only minutes. Therefore, **salt confidentiality is critical**.
- **Minimum salt length**: Under ADR-0045, `derive_pseudonym` strictly enforces a minimum salt length of **32 characters** (`MIN_SALT_LENGTH = 32`). Short or empty salts raise `SecurityError`.
- **Pseudonymization vs. legal anonymization**: Salted HMAC hashing constitutes **pseudonymization**, not irreversible anonymization under GDPR Recital 26 or the India DPDP Act. A dataset carrying exact train numbers, dates, stations, and passenger sequences may still allow re-identification if paired with auxiliary operational records. Deployment salts must be held strictly in local environment variables and never committed to source control.

---

## 6. Participant consent withdrawal and erasure procedure

Participants hold the right to withdraw their consent at any time prior to formal dataset publication and aggregation.

### 1. Withdrawal request execution
When a participant requests consent withdrawal:
```bash
python -m railconfirm.data prospective withdraw data/prospective/batch_001.json \
    --submission-id SUB_20261101_001 \
    --reason "Participant requested erasure prior to dataset release" \
    --operator maintainer_lead
```
- The command invokes `withdraw_submission()`, setting `consent.withdrawn = True`, recording `consent.withdrawn_at` with an aware UTC timestamp, and transitioning `review_status` to `ReviewStatus.WITHDRAWN`.

### 2. Downstream export barrier
- `export_batch_to_longitudinal()` strictly refuses or excludes any submission marked `WITHDRAWN` or carrying `consent.withdrawn == True`.
- `review_batch(action=ReviewStatus.APPROVED)` raises `SecurityError` if an operator attempts to approve a withdrawn submission.

### 3. Procedure for already-exported data
If a submission was exported prior to withdrawal:
1. The operator updates the raw prospective batch with `prospective withdraw`.
2. The operator re-exports the longitudinal dataset (`prospective export --overwrite`), which purges the withdrawn group.
3. The operator re-generates downstream point-in-time snapshots (`snapshot`) and re-derives the dataset manifest (`manifest --overwrite`).
4. Any candidate model trained on unreleased candidate snapshots must be re-fitted without the withdrawn records.

---

## 7. Scientifically defensible pilot design and thresholds

To ensure scientific defensibility, prospective data intake is governed by four explicit, quantitative thresholds. A dataset must satisfy the specific threshold corresponding to its intended research milestone:

```
[ Threshold 1: Operational Feasibility Pilot ]  --> Validates toolchain & chart checks (30+ pax, 3+ dates)
                       │
                       ▼
[ Threshold 2: Technical Intake Eligibility ]   --> Validates format & manifest ingest (50+ pax, 2+ dates)
                       │
                       ▼
[ Threshold 3: Temporal Baseline Experiment ]   --> Validates chronological modeling (300+ pax, 12+ dates, 4+ wks)
                       │
                       ▼
[ Threshold 4: Subgroup & Group Evaluation ]    --> Validates joint outcomes & classes (1,000+ pax, 30+ dates, 150+ groups)
```

### The four scientific thresholds

| Threshold | Quantitative Requirements | Primary Purpose | Scientific Limitations |
|---|---|---|---|
| **1. Operational Feasibility Pilot** | $\ge 30$ reservations, $\ge 3$ distinct journey dates, $\ge 2$ distinct trains | Validates operational toolchain: intake template, PII scanning, consent logging, and IRCTC public chart verification. | **Statistically underpowered**. Cannot train ML models, calibrate probabilities, or evaluate waitlist clearance. |
| **2. Technical Intake Eligibility** | Structurally valid schema, $\ge 50$ reservations, $\ge 2$ distinct dates | Satisfies row interchange contract (v1.1.0) and manifest generation requirements. | Merely syntactically valid. Insufficient data to generalize across quotas or seasonal travel patterns. |
| **3. Temporal Baseline Experiment** | $\ge 300$ reservations, $\ge 12$ distinct journey dates spanning $\ge 28$ days (4 weeks), $\ge 2$ major classes with $\ge 50$ rows each | Supports 1 chronological train/validation split with gap days and rolling-origin evaluation without cohort starvation. | Limited to primary trunk routes. Cannot evaluate low-frequency or regional trains. |
| **4. Subgroup & Group Evaluation** | $\ge 1,000$ reservations, $\ge 30$ distinct journey dates, $\ge 150$ multi-passenger groups ($n \ge 2$) | Supports evaluating comonotonic queue bounds vs. independence on groups of size 2–6, with subgroup calibration across `SL` and `3A`. | Volunteer selection bias still requires stratification or propensity weighting. |

### Coverage matrix for prospective pilot planning

To prevent severe class imbalance and cohort starvation, participant recruitment should aim for balanced representation across the following dimensions:

| Dimension | Target Strata | Recommended Share |
|---|---|---|
| **Quota Categories** | General (`GN`) / Tatkal (`TQ`) / Remote Location (`RL`) | 70% `GN`, 20% `TQ`, 10% Other |
| **Status Families** | GNWL (General Waitlist) / RLWL (Remote Location) / PQWL (Pooled Quota) / RAC | 60% GNWL, 20% RAC, 10% RLWL, 10% PQWL |
| **Queue Position Bands** | Low ($\le 10$) / Medium ($11–50$) / High ($> 50$) | 30% Low, 50% Medium, 20% High |
| **Travel Classes** | Sleeper (`SL`) / 3-Tier AC (`3A`) / 2-Tier AC (`2A`) | 50% `SL`, 40% `3A`, 10% `2A` |
| **Booking Group Size** | Solo (1 passenger) / Pair (2 passengers) / Family Group (3–6 passengers) | 50% Solo, 30% Pair, 20% Family |
| **Lead Times** | $> 30$ days / $14–30$ days / $3–14$ days / $< 3$ days | Evenly distributed across horizons |
| **Route Diversity** | High-demand trunk corridors (e.g., Delhi–Howrah, Delhi–Mumbai, Mumbai–Chennai) | At least 3 distinct trunk routes |

### Volunteer selection bias and mitigations
- **Self-selection bias**: Passengers submitting waitlisted tickets are disproportionately travelling on congested routes during peak festival or holiday periods.
- **Survivor bias**: Tickets that cleared early are more likely to be reported than those abandoned or cancelled without follow-up.
- **Pipeline mitigations**: Models fitted on prospective datasets must preserve Laplace smoothing, enforce minimum cohort cell floors, report observed vs. predicted calibration by lead time, and abstain when encountering unseen quotas or classes.

---

## 8. Operator review and export lifecycle

```
[ Prospective Template Generator ]
         │ (Run `prospective template`)
         ▼
[ Contributed Batch File ]
         │
         ├──► (Run `prospective scan`) ──► [ PII Scan Diagnostics ]
         │
         ├──► (Run `prospective audit`) ──► [ Audit Report & Threshold Check ]
         │
         ├──► (Run `prospective withdraw`) ──► [ Mark Consent WITHDRAWN ]
         │
         ▼
[ Operator Review ] ────────► (Run `prospective review --action approve`)
         │
         ├──► (Run `prospective export --dry-run`) ──► [ Validate Simulation ]
         │
         ▼
[ Export to Longitudinal Dataset (v2.0.0) ]
         │ (Run `snapshot`)
         ▼
[ Point-in-Time Flat Row Snapshot (v1.1.0) ]
         │ (Run `manifest`)
         ▼
[ Signed Approved Manifest ]
         │
         ▼
[ Phase 3 Baseline Model Training Gate ]
```

### Operator command execution steps

1. **Generate a clean starter batch template**:
   ```bash
   python -m railconfirm.data prospective template data/prospective/batch_template.json \
       --submissions 2 \
       --multi-passenger \
       --overwrite
   ```

2. **Scan the batch for personal data patterns**:
   ```bash
   python -m railconfirm.data prospective scan data/prospective/batch_001.json
   ```

3. **Run comprehensive batch audit and threshold assessment**:
   ```bash
   python -m railconfirm.data prospective audit data/prospective/batch_001.json
   ```

4. **Record human operator approval**:
   ```bash
   python -m railconfirm.data prospective review data/prospective/batch_001.json \
       --action approve \
       --reviewer "maintainer_lead" \
       --rationale "Verified 320 passenger reservations across 14 dates. PII scan clean."
   ```

5. **Simulate export via dry-run mode**:
   ```bash
   python -m railconfirm.data prospective export data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json \
       --dataset-id pilot_longitudinal_v1 \
       --source-id prospective_pilot_2026_1 \
       --dry-run
   ```

6. **Export approved submissions to longitudinal dataset**:
   ```bash
   python -m railconfirm.data prospective export data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json \
       --dataset-id pilot_longitudinal_v1 \
       --source-id prospective_pilot_2026_1 \
       --overwrite
   ```

7. **Verify export lineage and check for stale/withdrawn records**:
   ```bash
   python -m railconfirm.data prospective verify-export data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json
   ```

8. **Reconcile export if records were withdrawn post-export**:
   ```bash
   # Preview reconciliation via dry-run
   python -m railconfirm.data prospective reconcile data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json \
       --dry-run

   # Apply reconciliation atomically
   python -m railconfirm.data prospective reconcile data/prospective/batch_001.json \
       data/raw/longitudinal_pilot_v1.json \
       --overwrite
   ```

9. **Derive Day-7 training snapshot**:
   ```bash
   python -m railconfirm.data snapshot data/raw/longitudinal_pilot_v1.json \
       data/interchange/pilot_snapshot_d7.csv \
       --as-of-lead-days 7
   ```

10. **Generate and sign dataset manifest**:
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
> **LEGAL NOTICE**: The text below is a **DRAFT** participant disclosure prepared for operational evaluation. It does not constitute formal legal counsel or a finalized regulatory consent form. It must be reviewed and adapted by the maintainer and qualified legal counsel before distribution to participants.

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
If you voluntarily agree to participate, you will provide:
- Train number, journey date, travel class, and quota.
- Your initial booked waitlist/RAC status and position (e.g., GNWL 45).
- Subsequent status updates observed prior to departure.
- The final chart confirmation status for the journey.

3. WHAT IS NEVER COLLECTED OR STORED
- Your passenger name, address, email address, or phone number.
- Your 10-digit Indian Railways PNR number.
- Payment details, transaction IDs, or ticketing receipts.
All journey records are assigned cryptographically salted pseudonymous identifiers
before entering any research files.

4. PERMITTED RESEARCH USES
The contributed data will be used strictly for:
- Academic and empirical analysis of railway waitlist clearance rates.
- Training and evaluating open-source statistical and machine-learning models.
- Publishing aggregate benchmark metrics and error calibration curves.
Your data will NOT be used for commercial advertising, marketing, profiling,
or commercial resale.

5. VOLUNTARY PARTICIPATION AND WITHDRAWAL RIGHTS
Participation is entirely voluntary. You may withdraw your consent and request
the permanent erasure of your un-aggregated contribution at any time by
submitting a withdrawal request with your submission identifier prior to formal
dataset publication.

6. RESEARCH GOVERNANCE ATTESTATION
RailConfirm Intelligence operates under strict local-first data protection
protocols. Contributed data is pseudonymized, audited, and reviewed by human
research operators before any modeling analysis.

================================================================================
```

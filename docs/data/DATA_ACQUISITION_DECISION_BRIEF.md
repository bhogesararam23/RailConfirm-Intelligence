# Data acquisition decision brief — Phase 2 exit strategy and real-data pathways

Last reviewed: 2026-11-04  
Status: Authoritative engineering decision brief  
Audience: Project maintainer, research contributors, and autonomous engineering agents

---

## Executive summary

RailConfirm Intelligence has completed its software, mathematical, and data ingestion foundation:
- **Longitudinal observation contract (v2.0.0, ADR-0043)** supports journeys, booking groups, multi-passenger reservations, sequential observations with timezone-aware clocks, verified final outcomes, and censoring accounting.
- **Point-in-time snapshotting (v1.1.0)** safely converts rich multi-observation histories into flat training interchange frames at specified lead-time horizons without future leakage.
- **Intake and audit pipeline** enforces chronological validation, reservation syntax checking, transition anomaly detection (e.g., impossible RAC $\to$ WL regressions), schema auto-detection, and cryptographic quarantine isolation.
- **Consent-aware prospective collection framework (v1.0.0, ADR-0044)** incorporates automated PII/PNR scanning, cryptographically salted HMAC-SHA256 pseudonym derivation, and local operator review governance.
- **Test verification**: 1,240 backend pytest tests, 129 frontend Vitest tests, 6 Playwright browser E2E tests, and repository hygiene checks pass deterministically.

**The central remaining blocker**: No approved real-world Indian Railways reservation outcome dataset exists in the repository. As mandated by [ADR-0007](../adr/ADR-0007-local-first-no-external-runtime-apis.md) and repository governance, synthetic data is strictly isolated for software verification and is never passed off as railway performance. The live prediction API preserves structured abstention (`NO_APPROVED_DATA` / `NO_TRAINED_MODEL`).

This decision brief presents the findings of the exhaustive 2026-11-04 research campaign, evaluates candidate data acquisition pathways against the 10 qualification criteria, ranks the actionable options, and defines the precise decisions required from the maintainer to achieve Phase 2 exit.

---

## The 10 qualification criteria

Every candidate dataset or pathway is evaluated against the mandatory intake standards established in `docs/data/DATASET_INTAKE_CHECKLIST.md` and the longitudinal contract:

1. **Original booked status**: Preserves the initial booking reservation status category and position (e.g., `GNWL/45`, `RAC/12`).
2. **Timestamped observations**: Carries chronological status updates observed over time ($t_{booking} \le t_1 < t_2 < \dots < t_n \le t_{departure}$).
3. **Verified final-chart outcome**: Contains an independently verified final outcome recorded at chart preparation for the exact same reservation (`CNF`, `RAC`, `WL`).
4. **Journey context**: Preserves train number, journey date, travel class, and quota.
5. **Booking / group identity**: Preserves group clustering so multi-passenger bookings can be evaluated under dependent group probability models.
6. **Sample size & coverage**: Sufficient sample size across multiple train routes and lead days to support chronological splits without partition starvation.
7. **Provenance & license**: Authoritative origin with verified, documented terms of use.
8. **Storage, transformation & ML rights**: Explicit legal rights to store locally, extract features, fit models, and evaluate predictions.
9. **Commercial use status**: Permitted or clearly delimited under open-source research terms.
10. **Privacy & retention compliance**: Free of raw PII, 10-digit Indian Railways PNRs, passenger names, and contact details, with enforceable retention controls.

---

## Evaluation of candidate sources

| Source / Pathway | Booked status? | Timestamped obs? | Chart outcome? | Journey context? | Group ID? | Coverage | Provenance & License | ML & Storage rights? | Commercial? | Privacy compliant? | Overall verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Government Open Data (`data.gov.in`)** | No | No | No | Partial (static 2017) | No | National macro | GODL (Government Open Data License) | Yes | Yes | Yes (zero PII) | **Restricted / Metadata only**: Publishes macro statistics and static schedules only. Zero individual reservation outcomes exist. Cannot unblock training. |
| **CRIS Enterprise Gateway (Project Pravah)** | Yes (live) | Yes (live) | Yes (live) | Yes | Yes | National real-time | Bilateral enterprise MoUs (WSO2 gateway) | Restricted to enterprise contract | Commercial B2B only | High (enterprise VPN/Certs) | **Restricted / Enterprise only**: Closed to open-source developers. Operational live stream interchange; does not provide historical research outcome archives. |
| **IRCTC B2C PSP Scheme** | Yes (live) | Yes (live) | Yes (live) | Yes | Yes | National ticketing | Commercial B2C PSP Agreement | Operational ticketing only; secondary ML prohibited | Commercial | Heavy PII handling | **Restricted / Commercial only**: Requires corporate status, ₹5 Cr turnover, ₹20–50 Lakhs non-refundable fees. Strictly forbids third-party data redistribution or ML warehousing. |
| **Academic Literature (IEEE / ICACCTech / IJARCS)** | Varies | No | Binary only | Partial | No | Unclear | Academic copyright / no data grant | No data released | No | Unknown | **Reference only**: Papers rely on synthetic data or private consumer scraping without releasing underlying datasets. |
| **Kaggle Railofy Challenge / `Yogalakshmi4784`** | Destroyed | No | Binary target | Quota only | Non-unique pk | 36,775 rows | GPL-3.0 code; no data license; 401 on Kaggle | Unverified | Unverified | Redacted floats | **Rejected on content / Quarantined on rights**: 17 scaled floats, 0 valid rows in intake validator. Reconstructs no railway reservation states. |
| **Kaggle Aaryan Anil Ticket Dataset** | Synthetic | Synthetic | Synthetic | Synthetic | No | ~900 KB | MIT | Yes | Yes | Synthetic | **Rejected**: Author explicitly documents dataset is synthetically generated. Adds zero empirical railway evidence. |
| **GitHub `ShubhangG/Train-Ticket-prediction`** | Raw WL | No | Binary | Train, Class | No | Small CSV | **No license** (All rights reserved) | None granted | No | Unknown | **Rejected**: Unlicensed, undocumented scraping origin, binary target only. |
| **Academic Repositories (Zenodo, Dataverse, IEEE DataPort)** | None | None | None | None | None | 0 matches | N/A | N/A | N/A | N/A | **Evaluated — 0 matches**: No Indian Railways reservation outcome datasets exist on these repositories. |
| **Local Prospective Pilot Collection (ADR-0044, ADR-0045)** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | Controlled pilot | **Explicit participant research consent (v2026.1)** | **Consent-delimited research rights** | Research governed (no commercial use) | **Technical safeguards (PII scanner + Salted HMAC)** | **Qualified Path for Phase 2 Exit**: Fully implemented, validated, and operator-governed. Requires maintainer legal sign-off and cohort activation. |

---

## Ranked strategic pathways to Phase 2 exit

### Rank 1: Local-first consent-governed prospective collection pilot (ADR-0044, ADR-0045) — *The recommended actionable path*
- **Description**: Collect longitudinal reservation updates directly from consented rail passengers (maintainers, research contributors, institutional partners) using the local prospective ingestion pipeline.
- **Why it ranks first**:
  1. **Legally and ethically grounded design**: Operates on explicit participant research consent (v2026.1) with defined research purposes and an explicit participant withdrawal lifecycle (ADR-0045). Requires qualified legal review prior to recruiting human participants.
  2. **Zero external runtime dependencies (ADR-0007)**: Operates entirely local-first without commercial API subscriptions or runtime scraping.
  3. **Zero scraping / zero TOS violations**: Eliminates all anti-scraping, CAPTCHA, or provider agreement risks.
  4. **Strict privacy by design**: Automated PII scanning detects and rejects raw PNRs, emails, phones, Aadhaar numbers, PAN tax IDs, and passport numbers before storage; booking identifiers are pseudonymized via salted HMAC-SHA256 with an enforced minimum 32-character salt length.
  5. **Independent outcome verification**: Final chart outcomes can be verified directly through IRCTC's public chart visualization portal (`irctc.co.in/online-charts`), which publishes coach-wise passenger charting allocations 4 hours before departure without requiring PNR lookups. (Note: chart viewing verifies status but does not authorize bulk chart harvesting or commercial training).
  6. **Pipeline and operator tooling ready**: Contract v2.0.0, CLI commands (`prospective template`, `prospective scan`, `prospective audit`, `prospective review`, `prospective withdraw`, `prospective export` with `--dry-run`), and point-in-time snapshotting are fully implemented and verified with 1,244 backend unit tests.
- **What it requires**: Maintainer legal review and authorization, followed by activation of a volunteer prospective collection group and distribution of the consent notice.

### Rank 2: Academic institutional research partnership with CRIS / Indian Railways
- **Description**: Partner with an accredited Indian academic institution (e.g., IIT Delhi, IIT Bombay, IIIT) to submit a formal research proposal to the Centre for Railway Information Systems (CRIS) or Ministry of Railways for historical anonymized reservation outcome logs.
- **Feasibility**: High scientific legitimacy, but long timeline (6–18 months) and significant institutional overhead.
- **What it requires**: Institutional affiliation, research sponsor, ethics review board approval, and bilateral MoU with CRIS.

### Rank 3: Commercial data licensing agreement with an authorized OTA / travel aggregator
- **Description**: Enter a commercial data licensing agreement with an established travel aggregator (e.g., ConfirmTkt/Ixigo, RailYatri) that has longitudinally accumulated PNR status checks over several years.
- **Feasibility**: Moderate. Aggregators possess the data, but view their proprietary PNR clearance databases as proprietary competitive IP.
- **What it requires**: Corporate entity incorporation, commercial capital, non-disclosure agreements, and negotiated data licensing fees.

### Rank 4 (Disqualified): Automated web scraping of consumer PNR enquiry portals
- **Description**: Deploying automated bots or crawlers against `indianrail.gov.in` or third-party consumer tracking endpoints.
- **Reason for disqualification**: **Strictly prohibited.** Violates IRCTC terms of service, triggers bot-detection/CAPTCHA barriers, violates project behavioral guidelines, and risks legal action under the Information Technology Act.

### Rank 5 (Disqualified): Re-using synthetic datasets or obfuscated competition matrices
- **Description**: Fitting models on synthetic datasets (Aaryan Anil) or scaled float competition dumps (Railofy challenge).
- **Reason for disqualification**: **Strictly prohibited.** Violates AGENTS.md and foundational project rules. Fabricating predictions or claiming synthetic results as railway accuracy corrupts the scientific integrity of the product.

---

## The precise remaining blocker

The engineering components for Phase 2 are complete:
- Ingestion tooling, validation logic, longitudinal schemas, snapshotting algorithms, manifest verification, and privacy scanners are fully operational.
- The **sole remaining blocker** is the physical collection and human approval of the first genuine longitudinal reservation dataset.
- Because public open-data platforms (CRIS, data.gov.in) do not release passenger reservation records by policy, **Phase 2 cannot be exited through passive file downloads from the internet**.
- Phase 2 exit requires actively initiating the prospective pilot collection path.

---

## Maintainer action checklist

To remove the blocker and transition from Phase 2 to Phase 3, the maintainer should take the following specific actions:

1. **Adopt the prospective pilot operating protocol**:
   - Review and adopt [docs/data/PROSPECTIVE_COLLECTION_PROTOCOL.md](PROSPECTIVE_COLLECTION_PROTOCOL.md).
2. **Review the draft participant consent notice**:
   - Review the draft consent language in `PROSPECTIVE_COLLECTION_PROTOCOL.md` (ensuring alignment with the Digital Personal Data Protection Act, 2023).
3. **Initialize the local cryptographic salt**:
   - Set a private, non-committed cryptographic deployment salt (`RAILCONFIRM_PSEUDONYM_SALT`) in the local `.env` environment to enable secure HMAC pseudonym derivation.
4. **Collect the initial pilot cohort**:
   - Assemble an initial prospective batch of consented journeys (minimum 200 passenger reservations across at least 4 distinct journey dates to satisfy intake eligibility thresholds).
5. **Execute operator review and intake**:
   - Run `python -m railconfirm.data prospective scan <batch.json>` to verify clean PII status.
   - Run `python -m railconfirm.data prospective review <batch.json> --action approve --reviewer <name> --rationale <text>`.
   - Run `python -m railconfirm.data prospective export <batch.json> data/raw/pilot_v1.json --dataset-id pilot_longitudinal_v1 --source-id prospective_pilot`.
   - Run `python -m railconfirm.data snapshot data/raw/pilot_v1.json data/interchange/pilot_snapshot_d7.csv --as-of-lead-days 7`.
   - Run `python -m railconfirm.data manifest data/interchange/pilot_snapshot_d7.csv --dataset-id pilot_snapshot_d7 --title "Prospective Pilot Snapshot Day-7" --retrieved-on YYYY-MM-DD`.
   - Sign and record the human decision in the manifest (`decision: approved`).
6. **Trigger Phase 3**:
   - Once the approved manifest is signed, run `python -m railconfirm.training fit` to produce the first legitimate, non-synthetic baseline model artifact.

# Data source register

Last reviewed: 2026-11-04 (fourth pass: data.gov.in catalogue, CRIS Pravah enterprise API gateway, IRCTC B2C PSP / TIES framework, IEEE/ACM academic literature, HuggingFace, Zenodo, and GitHub machine learning projects)

This register is intentionally conservative. A source is not approved merely because it is discoverable online. Verify source-specific terms before ingestion, persistent storage, redistribution, model training or commercial use.

## Current register

| Source / category | Intended use | Status | What remains to verify |
|---|---|---|---|
| Open Government Data Platform India (`data.gov.in`, Ministry of Railways catalogue) | Route/station metadata and national traffic aggregations | **Reference metadata only.** | Evaluated 2026-11-04. Ministry of Railways catalogue publishes macroscopic data: annual route kilometers, electrification, rolling stock, financial balances, and the 2017 static timetable. Under National Data Sharing and Accessibility Policy (NDSAP), zero per-reservation records, waitlist outcomes, or PNR data are published. Cannot unblock training. |
| Centre for Railway Information Systems (CRIS) Pravah Enterprise API Gateway (`crisapis.indianrail.gov.in`) | Live operational/scheduling interchange | **Restricted — Enterprise only.** | Evaluated 2026-11-04. Pravah (launched August 2021) is an enterprise B2B/G2B gateway built on WSO2 API Manager. Strictly gated by bilateral institutional MoUs with corporate logistics partners and government agencies. Does not provide public developer APIs, and does not maintain or distribute historical reservation outcome datasets. |
| IRCTC B2C Principal Service Provider (PSP) & TIES Agreements | Operational ticketing and authorized live booking enquiry | **Restricted — Commercial ticketing only.** | Evaluated 2026-11-04. Governed by IRCTC B2C Policy. Requires corporate entity status, ₹5 Crore turnover threshold, ₹20–50 Lakhs non-refundable integration and security deposits, and rolling deposit accounts. Clause strictly forbids white-labeling, third-party PNR API sharing, or historical database warehousing for secondary ML training. |
| DataMeet `datameet/railways` metadata (`stations.json`, `trains.json`, `schedules.json`; mirrored on Kaggle as `CC0: Public Domain`) | Station codes, train numbers, classes and routes for input validation and coverage reporting | **Under review — not ingested.** Directly downloadable, but the repository has no licence file; prose citing CC0 is not a grant | An explicit licence dedication or written confirmation of CC0 and its permitted uses. No outcome labels, so this cannot unblock training. |
| National Train Enquiry System (NTES) timetable / schedule feeds (e.g. `shwetankg07/railpull`, an NTES timetable crawler/export) | Route and journey scheduling context for feature engineering | **Candidate; not ingested.** A crawler that walks NTES one train/station at a time produces schedules, stop lists and live delays; a 2026-10-31 search read its README only (`https://github.com/shwetankg07/railpull`). No per-reservation final-chart outcome | Whether NTES serves historical/archived schedule snapshots or only current data; whether the public timetable is also downloadable as a bulk file; and the service's acceptable use policy before any automated crawling. Schedules are a legitimate contextual feature; they are not a chart outcome. |
| Official railway enquiry surfaces (`indianrail.gov.in` PNR enquiry, `pnr-status-indian-railway.p.rapidapi.com`, `railengine.vercel.app`, `eRail`) | Understand public status vocabulary and user-facing constraints | **Reference only.** Per-PNR interactive enquiry only; no bulk or historical export. Live APIs (`rapidapi`, `railengine`, `eRail`) return current status for a live PNR and require an API key; automated collection, retention and ML use are not assumed permitted | Whether any authorised source publishes per-reservation historical outcomes with dates and positions. None of these services publishes booked-status + final-chart outcome batches. |
| Academic literature & conference datasets (IEEE ICACCTech, IJARCS, ScienceDirect) | Algorithmic reference and methodology benchmarking | **Reference only — no open data.** | Evaluated 2026-11-04. Published papers (e.g. LightGBM waitlist prediction, reservation chart clustering) rely either on synthetic datasets or proprietary scraping scripts against consumer portals. No peer-reviewed paper has released an open, licensed reservation-outcome dataset. |
| GitHub ML repositories (e.g. `ShubhangG/Train-Ticket-prediction`, `BitanSarkar/IRCTC-pnr-status-notifier`) | Feature engineering and tracking pipeline reference | **Rejected for training.** | Evaluated 2026-11-04. `ShubhangG/Train-Ticket-prediction` contains CSVs (`dataframe.csv`) but has **no license** (all rights reserved), lacks documented source provenance, and collapses labels to a binary target. Unusable for Apache-2.0 research. |
| HuggingFace transport datasets (`prabh21243343/indian-railways-delays`, `kiran957/railway_complaints`) | Operational delay context and complaint sentiment | **Reference metadata only.** | Evaluated 2026-11-04. Covers millions of train arrival/departure delay records and passenger tweets. Zero per-reservation booking or final-chart outcome labels. |
| Zenodo, Harvard Dataverse, IEEE DataPort | Public academic research datasets | **Evaluated — 0 matches.** | Evaluated 2026-11-04. Verified no archived Indian Railways reservation outcome datasets exist on these academic repositories. |
| Kaggle `aaryananil/indian-railway-ticket-confirmation` (`MIT`) | — | **Rejected** (2026-10-23) | The dataset page states it is synthetically generated. Labelled synthetic data may exercise code and prove nothing about railways. |
| Kaggle `bhavyarajdev/indian-railways-schedule-prices-availability-data` (`Apache 2.0`, scraped from IRCTC Oct 2023) | — | **Rejected for training** (2026-10-23) | Schedules/fares/availability snapshots, not per-reservation final-chart labels; provenance rests on unverified third-party scraping terms. |
| Kaggle `sripaadsrinivasan/indian-railways-dataset` (`CC0: Public Domain`) | — | **Under review, reference metadata only.** | Reference metadata only — no outcome labels — so at best it would sharpen station-code and train validation, not unlock training. |
| Kaggle `railofy-challenge` — "Indian Railways Challenge", hosted by Railofy, listed status "Late Submission" | Potential historical reservation outcomes | **Quarantined — terms unreadable from this environment** (2026-10-30) | Client-rendered challenge pages return HTTP 401 to unauthenticated API queries. Requires authenticated Kaggle session to verify terms, and behind that, confirmation of what Railofy was permitted to publish from its PNR tracking service. |
| `github.com/Yogalakshmi4784/PNR-Prediction` — competition work that re-publishes the Railofy CSVs | — | **Rejected for training on content** (2026-10-30); code is not reusable either | 36,775 rows: 17 scaled floats, binary target, no dates, no classes, no statuses. Validates as 0 valid rows in intake gate. GPL-3.0 code is incompatible with Apache-2.0. |
| Local Prospective Pilot Collection Protocol (ADR-0044, schema v1.0.0) | Multi-observation longitudinal training data with independent final-chart verification | **Qualified Path for Phase 2 Exit.** | Fully implemented in `backend/railconfirm/data/prospective.py` and `longitudinal.py`. Local-first, explicit consent metadata, automated PII/PNR scanner, salted HMAC pseudonymization, independent public chart verification, and human operator review controls. Requires maintainer activation of a prospective collection group. |

## Template for adding a source

Copy this block for each source.

- **Name:**
- **Publisher / owner:**
- **Canonical URL / contract reference:**
- **Date checked:**
- **Data fields:**
- **Geographic and temporal coverage:**
- **Schema documentation:**
- **Refresh interval and timestamp semantics:**
- **Licence / terms URL:**
- **Permitted storage:**
- **Permitted derived features / model training:**
- **Permitted redistribution / publication:**
- **Commercial use:**
- **Attribution requirements:**
- **Rate limits and cost:**
- **Personal or sensitive data involved:**
- **Security and retention controls:**
- **Known biases and limitations:**
- **Decision:** Approved / Restricted / Under review / Rejected
- **Decision owner and rationale:**

## Detailed source evaluations (2026-11-04)

### 1. Open Government Data Platform India (`data.gov.in`)
- **Name:** Ministry of Railways Public Dataset Catalogue
- **Publisher / owner:** Ministry of Railways / National Informatics Centre (NIC), Government of India
- **Canonical URL / contract reference:** `https://data.gov.in/ministrydepartment/ministry-railways`
- **Date checked:** 2026-11-04
- **Data fields:** Macroscopic annual indicators: total route kilometers electrified, passenger-kilometer aggregates, freight tonnage, revenue earnings, rolling stock production, static train timetable (2017).
- **Geographic and temporal coverage:** National Indian Railways network, annual summaries 1950–2023.
- **Schema documentation:** Metadata published on OGD platform per resource.
- **Refresh interval and timestamp semantics:** Annual/static.
- **Licence / terms URL:** Government Open Data Licence - India (GODL)
- **Permitted storage:** Local storage permitted for research.
- **Permitted derived features / model training:** Permitted, but contents provide macro context only.
- **Permitted redistribution / publication:** Permitted with attribution under GODL.
- **Commercial use:** Permitted under GODL.
- **Attribution requirements:** Attribute Ministry of Railways / data.gov.in.
- **Rate limits and cost:** Free; requires API registration / key for programmatic access.
- **Personal or sensitive data involved:** None. Under the National Data Sharing and Accessibility Policy (NDSAP), zero passenger PII or PNR records are published.
- **Security and retention controls:** Standard open government data controls.
- **Known biases and limitations:** **Zero reservation-outcome records, zero waitlist clearance histories, zero initial/final status pairs.** Cannot unblock model training.
- **Decision:** **Restricted — Reference metadata only.**
- **Decision owner and rationale:** Autonomous research audit 2026-11-04. Confirmed catalogue contains no individual reservation-outcome data.

### 2. Centre for Railway Information Systems (CRIS) Pravah Enterprise Gateway
- **Name:** Project Pravah Enterprise API Gateway
- **Publisher / owner:** Centre for Railway Information Systems (CRIS), IT Wing of Ministry of Railways
- **Canonical URL / contract reference:** `https://cris.org.in`, `https://crisapis.indianrail.gov.in`
- **Date checked:** 2026-11-04
- **Data fields:** Operational train movement, freight tracking, passenger transaction interchange via WSO2 API Manager.
- **Geographic and temporal coverage:** National Indian Railways network; real-time transactional streams.
- **Schema documentation:** Internal WSO2 enterprise developer portal; accessible only behind corporate authentication.
- **Refresh interval and timestamp semantics:** Live real-time sub-second transactional message flows.
- **Licence / terms URL:** Bilateral institutional enterprise agreements / MoUs with Ministry of Railways.
- **Permitted storage:** Tightly governed by bilateral enterprise contract; bulk archiving for secondary public ML generally restricted.
- **Permitted derived features / model training:** Requires specific institutional research MoU.
- **Permitted redistribution / publication:** Strictly prohibited; enterprise confidential.
- **Commercial use:** B2B commercial logistics / government enterprise use only under signed MoU.
- **Attribution requirements:** As per contract.
- **Rate limits and cost:** Enterprise tier; custom commercial terms.
- **Personal or sensitive data involved:** Handles core transactional data from PRS (CONCERT) and NGeT systems, categorized as critical national infrastructure.
- **Security and retention controls:** Enterprise VPN, client certificate authentication, IP whitelisting.
- **Known biases and limitations:** Gateway does not distribute or archive historical reservation outcome datasets for open research. Not accessible to independent open-source developers.
- **Decision:** **Restricted — Enterprise only.**
- **Decision owner and rationale:** Autonomous research audit 2026-11-04. Pravah is an operational enterprise integration gateway, not a public historical research archive.

### 3. IRCTC B2C Principal Service Provider (PSP) Framework
- **Name:** IRCTC B2C Web Service & API Integration Scheme
- **Publisher / owner:** Indian Railway Catering and Tourism Corporation Ltd. (IRCTC)
- **Canonical URL / contract reference:** IRCTC B2C Scheme Policy (`https://www.irctc.co.in`)
- **Date checked:** 2026-11-04
- **Data fields:** Booking transactions, PNR current status enquiry, seat availability checks, cancellation requests.
- **Geographic and temporal coverage:** Live Indian Railways booking horizon (up to 120 days advance).
- **Schema documentation:** Provided directly by IRCTC upon commercial onboarding and fee clearance.
- **Refresh interval and timestamp semantics:** Real-time enquiry.
- **Licence / terms URL:** IRCTC B2C PSP Agreement.
- **Permitted storage:** Transaction logging for passenger ticketing service only.
- **Permitted derived features / model training:** Secondary ML model training and public redistribution are strictly outside standard e-ticketing PSP grants.
- **Permitted redistribution / publication:** **Strictly prohibited.** PNR APIs cannot be white-labeled, shared, or redistributed to third parties under threat of severe financial penalties and license termination.
- **Commercial use:** Commercial e-ticketing allowed for licensed PSP entity only.
- **Attribution requirements:** Mandatory IRCTC co-branding and compliance notices.
- **Rate limits and cost:** Requires corporate incorporation, ₹5 Crore turnover threshold, ₹20–50 Lakhs non-refundable integration fees, ₹5–10 Lakhs annual maintenance, security deposit, and rolling advance deposit.
- **Personal or sensitive data involved:** Full passenger PII (names, age, gender, contact numbers) required for ticketing.
- **Security and retention controls:** High-security audited infrastructure, ISO 27001 compliance, strict data residency.
- **Known biases and limitations:** Service is built exclusively for commercial booking, not research data dumps.
- **Decision:** **Restricted — Commercial ticketing only.**
- **Decision owner and rationale:** Autonomous research audit 2026-11-04. Prohibitive financial barriers, strict non-redistribution clauses, and operational focus make this inappropriate for an open-source local-first baseline.

### 4. Local Prospective Pilot Collection Protocol (ADR-0044)
- **Name:** RailConfirm Local-First Prospective Pilot Collection
- **Publisher / owner:** RailConfirm Intelligence / Project Maintainer
- **Canonical URL / contract reference:** `backend/railconfirm/data/prospective.py`, `docs/data/PROSPECTIVE_COLLECTION_PROTOCOL.md`
- **Date checked:** 2026-11-04
- **Data fields:** Train number, journey date, class, quota, origin, destination, pseudonym group ID, sequence number, initial booked status, sequential timestamped status observations, independent final-chart outcome (from public chart visualization), consent metadata, notice version.
- **Geographic and temporal coverage:** Prospective train journeys contributed by consented participants.
- **Schema documentation:** Prospective Collection Schema v1.0.0 (`backend/railconfirm/data/prospective.py`) and Longitudinal Contract v2.0.0 (`backend/railconfirm/data/longitudinal.py`).
- **Refresh interval and timestamp semantics:** Timezone-aware ISO-8601 timestamps ($t_{booking} \le t_1 < t_2 < \dots < t_n \le t_{departure}$).
- **Licence / terms URL:** Explicit participant research consent under Apache-2.0 repository governance.
- **Permitted storage:** Local SQLite / JSON storage under operator control.
- **Permitted derived features / model training:** Explicitly permitted by participant consent record (`confirmation_probability_research`, `model_calibration`).
- **Permitted redistribution / publication:** Aggregated research models and anonymized benchmark scores permitted. Raw submissions remain local.
- **Commercial use:** Research use approved; commercial use depends on future organizational governance.
- **Attribution requirements:** Documented in research reports and dataset manifests.
- **Rate limits and cost:** Zero API fees; zero third-party licensing costs; operates locally.
- **Personal or sensitive data involved:** **Zero personal data in storage.** Automated PII/PNR scanner blocks raw 10-digit PNRs, emails, phone numbers, and Aadhaar numbers. Identifiers are salted HMAC-SHA256 pseudonyms.
- **Security and retention controls:** Mandatory human operator review (`review_batch`), quarantine isolation for anomalies, explicit retention policies (`pseudonymous_research_only`).
- **Known biases and limitations:** Volunteer / self-selected participant cohort bias; route coverage grows incrementally with participation.
- **Decision:** **Qualified Path for Phase 2 Exit.**
- **Decision owner and rationale:** Lead software engineer & project governance, 2026-11-04. Fully implemented, technically validated, privacy-preserving, legally defensible, and zero-cost local architecture adhering strictly to ADR-0007 and ADR-0044.

## Current scope and target-product note

The current build has no third-party runtime API or provider integration (ADR-0007). Agents may research candidate local datasets, but must submit the manifest and intake report before training. Live status and current/upcoming contextual integrations are planned core capabilities in roadmap Phases 8–10; the entries above are potential source categories, not approved providers. Do not treat planned product capability as permission to use a specific source.

## Approval rule

A source cannot enter model training until its data rights, label meaning, quality, provenance and publication constraints are clear. If a contract allows live display but does not allow historical storage or model training, treat those as distinct permissions.


## Prospective pilot collection protocol (ADR-0044)

Prospective data collection is governed by `backend/railconfirm/data/prospective.py`:
- Mode: local-first, disabled by default.
- PII/PNR scanner automatically enforces data minimization before storage.
- Storage requires explicit consent metadata, notice version, and permitted research purposes.
- Human operator review and sign-off are required prior to export into longitudinal research datasets.

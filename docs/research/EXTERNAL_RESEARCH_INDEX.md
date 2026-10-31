# External research index and source register

**Last reviewed: 2026-10-31**
**Scope: External research index, source register and evidence base**

This index is the master register of the external research campaign. It records every
source consulted, its evidence tier, its finding, and its status in the research
programme. It is updated continuously; it is never a final provenance claim — a source
is only as reliable as its original publisher.

---

## 1. Evidence-tier legend

| Tier | Source type | Use |
|---|---|---|
| Tier 1 | Official railway, government, legislation, original data publisher, official API documentation, original research papers | Authoritative; relied upon |
| Tier 2 | Peer-reviewed secondary research, recognised institutions, technical documentation, credible industry reporting | Relied upon with caveat |
| Tier 3 | Reputable journalism, established technical publications, well-documented third-party analysis | Corroborating only |
| Tier 4 | Community posts, Reddit, forums, individual repositories, unverified claims | Discovery lead only; never relied upon |

---

## 2. Source register

### 2.1 Official railway / government

| Source | Organisation | URL | Type | Date checked | Finding | Tier | Status |
|---|---|---|---|---|---|---|---|
| Indian Railways Passenger Reservation Enquiry legend | Indian Railways | https://www.indianrail.gov.in/enquiry/PNR/PnrEnquiry.html | Official enquiry legend | 2026-10-31 | Status vocabulary; charting guidance ("Current Status might upgrade/downgrade at a later stage") | 1 | Verified |
| IRCTC Terms & Conditions | IRCTC Ltd | https://contents.irctc.co.in/en/Terms%20and%20conditions.pdf | Official | 2026-10-31 | No automation/scripting; personal/non-commercial use | 1 | Verified |
| IRCTC B2C PSP Policy (Edition 2025, Ver 3.0) | IRCTC | https://contents.irctc.co.in/en/B2C_PSP_Policy_other_than_Startup_MSME.pdf | Official policy | 2026-10-31 | EACC/Rs.0.25/PEC Rs.0.25; look-to-book 1:100; penalties for PNR API sharing | 1 | Verified |
| IRCTC refund rules | Indian Railways (Ministry) | https://www.indianrailways.gov.in/railwayboard/uploads/directorate/coaching/pdf/RefundRules.pdf | Official | 2026-10-31 | Refund windows; clerkage; train-cancellation refunds; partially-confirmed refunds | 1 | Verified |
| IRCTC diversion/cancellation notice | IRCTC | https://contents.irctc.co.in/en/Important%20Message_Diversion.pdf | Official | 2026-10-31 | TDR windows; diversion/cancellation procedures | 1 | Verified |
| Ministry of Railways / PIB confirmation-prediction tool | Ministry of Railways | https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1541499 | Official | 2026-10-31 | AI confirmation-prediction tool for waitlisted tickets (General Quota), operational since 13 Jun 2018 | 1 | Verified |
| DD News / CRIS RailOne | Ministry of Railways | https://ddnews.gov.in/en/from-queues-to-clicks-how-indian-railways-passenger-reservation-system-has-transformed-travel-over-four-decades/ | Government info | 2026-10-31 | RailOne AI-based waitlist confirmation prediction; accuracy 53% → 94% | 2 | Verified |
| Year-wise Train Punctuality Index | Ministry of Railways | data.gov.in | Official open data | 2026-10-31 | Punctuality index; yearly 2011-12 to 2024-25 | 1 | Verified |
| Digital Personal Data Protection Act 2023 | Government of India | (legislation) | Legislation | 2026-10-31 | Personal data protection; consent; research exemption; penalties | 1 | Verified |

### 2.2 API and data providers

| Source | Organisation | URL | Type | Date checked | Finding | Tier | Status |
|---|---|---|---|---|---|---|---|
| NTES (official) | CRIS / Ministry of Railways | https://enquiry.indianrail.gov.in | Official | 2026-10-31 | Current/near-future schedules, live status, PNR; PNR captcha-gated | 1 | Verified |
| CRIS Pravah API | CRIS | https://crisapis.indianrail.gov.in | Partner API | 2026-10-31 | Partner terms; no reverse engineering, no sublicensing | 1 | Verified |
| ntes-client (official-surface summary) | community clients | GitHub x64vbhv / freakynit | Documentation read | 2026-10-31 | NTES current-only; unofficial clients | 3 | Read (not relied upon) |
| RailRadar delay/punctuality API | RailRadar | https://railradar.in/docs/train-delay-report | Commercial API | 2026-10-31 | Delay/punctuality from NTES 7-day rolling stats | 3 | Read |
| Hugging Face NTES delays | community | https://huggingface.co/datasets/pjay-in/indian-railways-delays | Dataset | 2026-10-31 | Per-stop delays, run status; NTES-derived | 2 | Read |

### 2.3 Research data archives

| Source | Organisation | URL | Type | Date checked | Finding | Tier | Status |
|---|---|---|---|---|---|---|---|
| Zenodo | CERN | https://zenodo.org | Repository | 2026-10-31 | No Indian Railways reservation-outcome dataset found | 3 | Read |
| Figshare | Digital Science | https://figshare.com | Repository | 2026-10-31 | Italian Railway Network dataset (CC BY 4.0) | 3 | Read |
| Open Science Framework | OSF | https://osf.io | Repository | 2026-10-31 | No IR reservation outcome dataset found | 3 | Read |

### 2.4 Academic

| Source | Organisation | URL | Type | Date checked | Finding | Tier | Status |
|---|---|---|---|---|---|---|---|
| ICACCTech 2024 LightGBM paper | Chandigarh University | IEEE | Peer-reviewed | 2026-10-31 | LightGBM, 96.67% claim, no public protocol | 2 | Read |
| IIIT LCRC | IIIT | (paper listed in register) | Research | 2026-10-31 | Indian waitlist prediction | 2 | Read |

### 2.5 Commercial prediction / booking platforms

| Source | Organisation | URL | Type | Date checked | Finding | Tier | Status |
|---|---|---|---|---|---|---|---|
| eRail | eRail | eRail | Consumer | 2026-10-31 | PNR enquiry and prediction products | 3 | Read |
| RailYatri | RailYatri | RailYatri | Consumer | 2026-10-31 | PNR enquiry and prediction products | 3 | Read |
| ixigo | ixigo | ixigo | Consumer | 2026-10-31 | Train search, PNR, prediction | 3 | Read |
| ConfirmTkt | ConfirmTkt | ConfirmTkt | Consumer | 2026-10-31 | Train search, PNR, prediction | 3 | Read |

### 2.6 Candidate datasets (rejected / quarantined)

| Candidate | Publisher | URL | Licence | Findings | Reason | Status |
|---|---|---|---|---|---|---|
| Kaggle aaryananil | Kaggle | Indian-railway-ticket-confirmation | MIT | Self-declared synthetic | Synthetic data proves code, not reality | Rejected |
| Kaggle bhavyarajdev | Kaggle | Indian-railways-schedule-prices-availability | Apache 2.0 | Schedules/fares; no outcome labels; scraping provenance unverified | No outcomes | Rejected |
| Kaggle sripaadsrinivasan | Kaggle | Indian-railways-dataset | CC0 | Reference metadata only | No outcomes | Under review |
| Kaggle railofy challenge | Kaggle | Railofy | GPL-3.0 (prose) | 36,775 rows, binary target, undocumented scaling; 0 valid rows at intake gate | Quarantined | Quarantined |
| Yogalakshmi4784/PNR-Prediction | GitHub | GitHub | GPL-3.0 | Code re-publishing; synthetic; GPL does not fit Apache-2.0 | GPL incompatible | Rejected |
| datameet/railways | GitHub | GitHub | No licence file | Reference metadata | No outcomes | Under review |
| data.gov.in timetable 2017 | Government of India | data.gov.in | CC0 prose, no file | Metadata only | No outcomes | Reference |

---

## 3. Research-opportunity backlog

| Priority | Workstream | Action | Approval status |
|---|---|---|---|
| R1 | Data | Design and test the prospective-consent measurement system | User decision required |
| R2 | Data | Negotiate a licensed historical-outcome dataset | User decision required |
| R3 | Domain | Verify the official charting timeline authoritative source | Resolved (second author check) |
| R4 | Prediction science | Temporal ablation of punctuality/delay features | Requires data; Phase 9 |
| R5 | Prediction science | Survival/hazard model (scikit-survival) once data is approved | Requires data |
| R6 | Prediction science | Group-dependence experiment on real groups | Requires data |
| R7 | Contextual | Implement and measure holiday/festival seasonality | No approval needed; Phase 9 |
| R8 | Contextual | Implement and measure booking-window/ahead-of-journey signals | No approval needed; Phase 9 |
| R9 | Privacy | DPDPA review for any live-PNR integration | Resolved |
| R10 | Engineering | Research-reproducibility automation and setup | In-scope; implement now |
| R11 | Infrastructure | Cross-stack E2E driver (Playwright) when deployment is planned | Optional |
| R12 | Infrastructure | Data-validation library, used selectively | Optional |

---

## 4. Prioritised prioritised research opportunity matrix

| Action | Immediate | In-scope now? | Needs data? | Needs user? |
|---|---|---|---|---|
| Update source register | Yes | No | No | No |
| Update DATA_ACQUISITION | Yes | No | No | No |
| Update PROJECT_STATUS | Yes | No | No | No |
| Research-reproducibility setup | Yes | No | No | No |
| Verify official charting timeline | Yes | No | No | No |
| Punctuality/delay ablation | No | No | Yes | No |
| Survival model | No | No | Yes | No |
| Group-dependence experiment | No | No | Yes | No |
| Live-PNR integration | No | No | Yes | Yes |
| Prospective consent system | No | No | Design done | Yes |

---

## 5. Open unknowns

- Whether data.gov.in serves historical/archived schedule snapshots or only current data.
- Whether NTES serves historical/archived schedule snapshots.
- Whether any authorised source publishes per-reservation historical outcomes.
- Whether any commercial aggregator publishes a training-permitting historical
  outcome dataset.
- Whether the Railofy competition terms become readable from a Kaggle session.

These are **discovery leads**, not proven absences. The source register records
each, so future research does not repeat the same dead ends.

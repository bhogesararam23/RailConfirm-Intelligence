# Historical dataset and data-acquisition landscape

**Last reviewed: 2026-10-31**
**Scope: Workstream B — historical railway data discovery**

This document is the external data-side of the research campaign. It records what
actually exists, what an agent can lawfully obtain, the candidate datasets considered,
and the rigorous reasons each was accepted, rejected or quarantined. It is a data
discovery document — it says what is *available* and *usable*, not what *should be
trained on*. No candidate is promoted merely because it is downloadable.

---

## 1. What the repository is actually trying to learn from a dataset

Per `docs/research/RESEARCH_PLAN.md`, the central question is whether RailConfirm can
estimate Indian Railways reservation outcomes from information available at a defined
point before final charting. The data the model needs is narrow:

1. **Per-reservation booked status** (or a cohort of booked statuses).
2. **An observation timestamp** — when the status was recorded relative to the chart.
3. **A verified final-chart outcome** — CNF, RAC (berth-shared or not), WL, CANCELLED,
   NT, etc., confirmed after the journey.
4. Journey context: class, quota, train, route, origin/destination, date.
5. Permitted licensing for storage, training, and publication.

A dataset satisfying all five is a **supervised historical-reservation-outcome dataset**.
None has been approved. The categories below are checked against these five requirements.

---

## 2. Dataset category taxonomy used in this review

| Category | Description | Useful to RailConfirm as-is? |
|---|---|---|
| 1. Reservation-level booked-status + final-outcome | Per PNR, per journey, labelled final berth | **Only this unblocks training** |
| 2. Timestamped reservation-status history | Per-snapshot status over time | Needed to fit a trajectory model (H1) |
| 3. Train & timetable metadata | Schedules, stops, stations | Contextual, not a training label |
| 4. Live train-running & disruption observations | Delays, cancellations, punctuality | Contextual features; validates against NTES |
| 5. Aggregate booking/reservation statistics | Category-level, not per-reservation | Reference only |
| 6. Synthetic or simulated data | Generated for a paper/competition | Validates code, not reality |
| 7. Unlabelled/partially-labelled data | No verified outcomes | Not usable for supervised training |

The RailConfirm model must separate these categories rigorously. A dataset with a
`target` column or described as "railway data" is not automatically a category-1
dataset. A year-wise punctuality index is category 5, with no reservation rows at all.

---

## 3. Official government, institutional and research-data portals

### 3.1 Data.gov.in — Indian Railways Time Table (2017)

- **Publisher:** Ministry of Railways / Planning, Development and Special Initiatives
  Department, Government of India, via Open Government Data (OGD) Platform India
  (`https://data.gov.in`).
- **Reported dataset:** "Indian Railways Time Table for trains available for reservation as
  on 01.11.2017", mirrored on Kaggle as CC0 `"CC0: Public Domain"` (stations, trains,
  schedules metadata).
- **Verification:** An unauthenticated automated fetch of `data.gov.in` returned HTTP 403
  (2026-10-23). The dataset was therefore identified by catalogue description and
  search-result snippets only, not read in full.
- **Coverage:** 01.11.2017 timetable; a **static historical snapshot**.
- **Fields:** route/train metadata — station codes, train numbers, classes and routes.
- **Labels:** No reservation-level outcomes, no observation timestamps, no final-chart
  labels. Category 3 (train/timetable metadata).
- **Licence / terms:** catalogue prose cites CC0; the repository has no licence file.
  A prose claim is not a grant. Category 3 → reference metadata only.
- **Verdict:** candidate for validation metadata only; cannot unblock training.

### 3.2 NTES (National Train Enquiry System, run by CRIS) — official real-time data

- **Publisher:** CRIS (Centre for Railway Information Systems) under Ministry of Railways,
  via Indian Railways official portals (`enquiry.indianrail.gov.in`).
- **What it serves:** current and near-future train schedules, live train status, live
  station boards, delays, cancellations, exceptions.
- **Critical limitation:** NTES is **current/near-future only**. It does not serve
  historical per-reservation status histories or final-chart outcomes.
- **PNR endpoint:** `https://indianrail.gov.in/enquiry/CommonCaptcha` (captcha-gated PNR
  lookup). PNR status checking is the one human/account-facing capability.
- **Verification date:** 2026-10-31 (read via `ntes-client` README, `freakynit/ntes-client`,
  `x64vbhv/ntes-client`).
- **Legal posture:** unofficial Python clients reverse-engineer the mobile-app protocol;
  the official Pravah API (`crisapis.indianrail.gov.in`) is partner/on-premise with
  documented terms forbidding sublicensing and reverse engineering.
- **Verdict:** legitimate **contextual/real-time data source**, not a training outcome
  dataset. No historical reservation outcomes. Use requires an authorised, contractual
  programmatic access (future Phase 8), not this unofficial surface.

### 3.3 Hugging Face `pjay-in/indian-railways-delays` — NTES-derived delays dataset

- **Publisher:** community, NTES (per its README: "Collected by us from NTES... run by
  CRIS").
- **Description:** scheduled vs actual arrival/departure per stop per run; one row per
  stop-with-time; `status` a run (completed, cancelled, partially cancelled, diverted,
  incomplete); `run_quality` summarises whether times were reported or estimated. One
  file per completed date. Multiple disjoint date files.
- **Source:** NTES station boards, published next day.
- **Verification:** 2026-10-31 (read README and dataset viewer).
- **Coverage/records:** the README reports 1,895,758 source runs with 1,093,348 kept
  (17,522,150 of 38,428,703 rows); dropped runs include a station missing from the
  timetable, backwards actual times, no delay, >12h delay, backwards scheduled times.
- **Fields:** train_number, train_name, category, start_date, status, seq, station_code,
  scheduled/actual arrival and departure (IST), reported flags, delay minutes, run_quality.
- **Labels:** **No reservation-level outcomes.** Train-running metadata (delays,
  punctuality, cancellations, diversions).
- **Licence:** not stated explicitly in the README; community dataset.
- **Verdict:** Category 4 — live train-running observations. **Useful as a contextual
  feature** (punctuality, delay propagation) and as an evaluation source for Phase 9.
  Not usable for the reservation-outcome target.

### 3.4 Year-wise Train Punctuality Index (data.gov.in)

- **Publisher:** Ministry of Railways, via Open Government Data (OGD) Platform India.
- **Description:** punctuality index of Mail/Express trains arriving at destination on
  time; yearly rows 2011-12 to 2024-25; last updated 24 March 2026.
- **Fields:** fiscal_year, category, value (%), note.
- **Labels:** aggregate national index only. Category 5.
- **Verdict:** reference only; no reservation rows or final outcomes.

---

## 4. Research-data archives (Zenodo, Figshare, OSF) and academia

### 4.1 Zenodo

Zenodo is CERN's general-purpose repository (funded by CERN/OpenAIRE). Its OAI-PMH API
and REST depot are documented. For datasets, access rights are `open`, `embargoed`,
`restricted`, or `closed`; defaults are `cc-zero` for datasets and `cc-by` elsewhere.
**No Indian Railways per-reservation outcome dataset was found on Zenodo.**

### 4.2 Figshare

Figshare hosts the "Italian Railway Network Dataset Incorporating Multi-Type Train
Operation Records and Train Scheduling" (DOI 10.6084/m9.figshare.28891607; Jun Shen et al.).
- **Fields:** operational records for various train types, station locations, inter-station
  mileage, weather, scheduling data.
- **Licence:** CC BY 4.0.
- **Verdict:** Category 3/4 (network and scheduling records), not reservation outcomes.
  Contextually useful; not a training label.

### 4.3 Open Science Framework (OSF) and university repositories

General-purpose, but no Indian Railways per-reservation outcome dataset was identified
in this review. University research-use datasets are noted as **potential collaboration
pathways** (must be licenced per organisation policy, not auto-approved).

---

## 5. Commercial, aggregator and API providers

### 5.1 IRCTC / CRIS

- **Publisher:** IRCTC Ltd (incorporated under Indian law) and CRIS (Centre for Railway
  Information Systems), Ministry of Railways.
- **Product:** official ticket booking, PNR enquiry, train schedule, live status.
- **Legal posture:** PNR Enquiry is per-PNR, login-gated, and **requires registration
  with IRCTC**. IRCTC terms strictly prohibit automation/software scripting and
  unauthorised business of procuring tickets ("IRCTC reserves the right to deactivate
  all such users...no refund of ticket fare will be admissible"). The B2C PSP Policy
  (Edition 2025, Ver 3.0, w.e.f. 20-09-2025) sets enquiry charge rules (EACC, PEC), look-
  to-book ratios, PSP integration requirements, and penalties for unauthorised sharing
  of PNR enquiry APIs.
- **Pravah API** (`crisapis.indianrail.gov.in`): partner/on-premise API platform; terms
  forbid reverse engineering, sublicensing, unauthorised access; no bulk historical data.
- **Historical per-reservation data:** Not published.

### 5.2 RailRadar — delay/punctuality API

- **Publisher:** RailRadar (commercial).
- **Product:** average delay & punctuality report; station-by-station historical average
  arrival/departure delay for a train, based on official NTES 7-day rolling statistics.
- **Coverage:** seven-day rolling rollings; train/route localizable.
- **Reciprocal uses:** live status, schedules, historical punctuality. No reservation
  outcomes.

### 5.3 eRail, RailYatri, ixigo, ConfirmTkt, Railofy

Consumer booking/enquiry platforms. Their web/app surfaces are per-PNR enquiry with
captcha and rate gating; they publish **prediction/product marketing** (confirmation
chance), not underlying per-reservation historical datasets under a train-permitting
licence. None is approvable as a training outcome source from this review.

### 5.4 Kaggle competition — Railofy "Indian Railways Challenge"

- **Publisher:** Railofy, hosted on Kaggle.
- **Dataset:** 36,775 rows with one column of 17 scaled floats (13 outside [0,1]), one
  `QT` code (`GN`/`PQ`/`RL`), five integer flags, one 11-digit non-unique `pk`, and a
  **binary** `target` with base rate 0.3148.
- **Verification (2026-10-30):** `python -m railconfirm.data validate` on the CSV returns
  **0 valid rows** — every reservation field (train number, journey date, observation
  date, class, booked status, final-chart status) is destroyed by an undocumented scale.
  The competition terms require a Kaggle session; the field scaling is undocumented and
  the `target` is uninterpretable without the original notes.
- **Licence:** `LICENSE` is verbatim **GPL-3.0** and the word "dataset" appears 0 times
  in it. No basis to treat it as a dataset licence; copyleft does not fit an
  Apache-2.0 project.
- **Verdict:** **Quarantined.** Content rejected on data-quality grounds; licence terms
  unreadable from this environment. Under review is **not** approval.

### 5.5 Kaggle metadata datasets

- `aaryananil/indian-railway-ticket-confirmation` (MIT): self-declared synthetic.
  Rejected — synthetic data proves code behaviour, not railway behaviour.
- `bhavyarajdev/indian-railways-schedule-prices-availability-data` (Apache 2.0,
  scraped IRCTC Oct 2023): schedules/fares/availability. Schedules only; no per-reservation
  final-chart labels; provenance rests on unverified scraping terms. Rejected for training.
- `sripaadsrinivasan/indian-railways-dataset` (CC0, on Kaggle): reference metadata only;
  no outcome labels; at best station-code and train validation. Under review, reference.

### 5.6 GitHub `datameet/railways` metadata (mirrors on Kaggle, "CC0: Public Domain")

- **Fields:** stations, trains, schedules metadata.
- **Licence:** repository has no licence file; prose citing CC0 is not a grant.
- **Verdict:** reference metadata only; no outcomes. Under review.

---

## 6. Structured candidate comparison

| Candidate | Category | Outcome labels? | Timestamps? | Licence clear? | Verdict |
|---|---|---|---|---|---|
| Data.gov.in Indian Railways Time Table 2017 | 3 | No | No | CC0 prose, no file | Reference metadata |
| NTES (official; current/near-future) | 4 | No | Yes (live) | Partner terms | Live contextual source; future Phase 8 |
| Hugging Face NTES delays | 4 | No | Yes | Unstated | Contextual features |
| Year-wise punctuality index | 5 | No | Yes (yearly) | OGD | Reference |
| Italian Railway Network (Figshare) | 3/4 | No | Yes | CC BY 4.0 | Context only |
| Kaggle railofy competition | 1/6/7 | Unclear (binary, uninterpretable) | Unclear | GPL-3.0 prose | **Quarantined** |
| Kaggle aaryananil | 6 | Synthetic | N/A | MIT | Rejected (synthetic) |
| Kaggle bhavyarajdev | 3/5 | No | No | Apache 2.0 | Rejected (no outcome) |
| Kaggle sripaadsrinivasan | 3 | No | No | CC0 | Reference metadata |
| datameet/railways | 3 | No | No | No file | Reference metadata |

---

## 7. Conclusion

**No registered-source dataset with per-reservation booked status + observation time +
verified final-chart outcome exists under a training-permitting licence that this
review could verify.** The categories that are genuinely available:

1. Train/timetable metadata, live delays, punctuality indices (categories 3–5) — useful
   as *contextual features* and for evaluation, not for the outcome target.
2. NTES official/current live status (category 4) — a future authorised, contractual
   live source (Phase 8), not a historical training dataset.
3. The Kaggle Railofy competition (category 1/6/7) — quarantined, content rejected
   and licence unreadable.

**Production path:** a supervised final-chart-outcome model requires either (a) a
**licensed data agreement** or (b) **prospective consent-based collection** of
observation-time status histories with verified final outcomes — neither of which is
available at this repository today. Data.gov.in, NTES, Hugging Face delays, Zenodo,
Figshare, OSF, Kaggle, and GitHub metadata were all examined individually and
independently; the absence is a finding, not an access failure.

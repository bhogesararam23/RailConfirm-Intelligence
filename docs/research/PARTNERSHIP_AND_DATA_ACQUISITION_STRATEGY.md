# Partnership and prospective data acquisition strategy

**Last reviewed: 2026-10-31**
**Scope: Partnership and prospective data acquisition**

## 1. Objective

RailConfirm needs a supervised dataset with per-reservation booked status, observation
time, and verified final-chart outcome, under a licence that permits local storage,
transformation, model training, aggregate publication and (potentially) commercial
deployment. No public source supplies all of that. The two paths that can produce it
are:

1. A **licensed data agreement** with an operator/aggregator.
2. **Prospective consent-based collection** of observation-time status histories with
   verified final outcomes.

Both paths require user authorisation before any account, contract or data transfer.

---

## 2. Path 1 — Licensed data agreement

### 2.1 What is needed

A source that publishes (or licenses) per-reservation records at the level of:
passenger, booking, ticket, class, quota, train, route, journey date, observation
timestamps, and verified final-chart outcome. The operator must authorise: storage,
transformation, model training, aggregate/publication, and any commercial deployment.

### 2.2 Candidate organisations

| Organisation | Product / what it could provide | How it would be approached | What it cannot do today |
|---|---|---|---|
| IRCTC (via PSP partner agreement) | Per-reservation booking and booking-history records if a B2C PSP agreement is granted | Engage IRCTC's B2C PSP integration channel (edit policy edition, per the 2025 B2C PSP policy) | PNR Enquiry API is not a historical outcome dataset; programmatic access is contractual and priced (EACC/PEC) |
| CRIS Pravah API | Official partner API for railway information and operational data | Formal partner/on-premise access request | Current/near-future data only; no historical per-reservation outcomes; no sublicensing |
| A railway operator / zone | Historical reservation outcome export under a data licence | Direct data-licence negotiation | Requires a signed data-licence agreement with permitted use |

### 2.3 Process for a data-licence negotiation

1. Define the minimum fields and the required labels (booked status, observation time,
   final-chart outcome).
2. Define permitted use (local storage, transformation, training, aggregate publication,
   commercial deployment).
3. Negotiate data-sufficiency, quality, schema, privacy, security, retention,
   deletion, and audit requirements.
4. Agree the licence terms for redistribution and publication.
5. Record the agreement in the source register and, if a material data decision is made,
   in a new ADR.

---

## 3. Path 2 — Prospective consent-based collection

### 3.1 What is needed

A mechanism for collecting, with informed consent, the *observation-time status
history* of a booking from a passenger at the time of booking, plus the verified
final-chart outcome after the journey. This is the only way to build a supervised
event dataset **without** a commercial data agreement, because the data is contributed
by the passenger who holds it.

### 3.2 Consent and data-protection requirements (DPDPA 2023)

- A standalone notice stating: personal data collected, purpose of processing, data
  categories, retention, user rights (access, correction, erasure), withdrawal
  mechanism, and grievance redress.
- Consent must be free, specific, informed, unconditional and unambiguous; bundled
  consent is invalid.
- The data is personal data of the contributor; processing follows DPDPA 2023 and the
  DPDP Rules, 2025 (minimisation, retention, deletion, breach notification, rights).
- Research/statistical exemptions (Rule 16, Schedule II) apply only if results are not
  used to make decisions about identifiable individuals — RailConfirm publishes only
  aggregate cohort statistics and abstentions, so this is satisfied for the anonymised
  aggregate dataset.
- Children's data requires verifiable parental consent; RailConfirm's schema does not
  collect passenger names, so minimization is built in.

### 3.3 What this can and cannot produce

**Can produce:** a training dataset of booking-level records with observation-time
status histories and verified final-chart outcomes, consented by the passenger.
**Cannot produce:** commercial deployment without a licence; it requires explicit
consent per record, per purpose, and per data category.

### 3.4 Delivered data contract

The prospective-collection dataset must meet the data contract (`DATA_CONTRACT.md`)
and the intake checklist (`DATASET_INTAKE_CHECKLIST.md`). Each row carries:
participant consent flags, purpose, purpose-limited retention, per-row consent state,
booked status, observation timestamp, final outcome, journey, class, quota, train,
route, source attribution, and retention/erasure metadata.

---

## 4. Partnership enquiry draft

A professional enquiry template is provided below for future use when the user
authorises a specific outreach. It is a draft for the user's approval; it is not a
contract.

---

**To: [Organisation / IRCTC / CRIS / Railway operator]**

**From: RailConfirm Intelligence (project)**  —  **Date: [date]**

**Subject: Data partnership enquiry — supervised Indian Railways reservation-outcome
model**

We propose to investigate, through a formal agreement, the use of historical
reservation records sufficient to train a probabilistic model of Indian Railways
reservation outcomes (booked status, observation time, and verified final-chart
outcome). We are evaluating:

1. A data licence covering per-reservation booking records with the fields above, and
2. A prospective, consent-based observation system built on that data.

**Data needs:** per-reservation booked status, observation timestamp, verified final-
chart outcome, plus journey class, quota, train, route, and date.

**Permitted use:** local storage, transformation, model training, aggregate and
documentation publication. No redistribution of raw records without a separate
licence.

**Rights required:** storage, transformation, training, aggregate publication, and
optional commercial deployment.

**Feedback:** We are open to a pilot, a written data-licence specification, or a
reference to a known licence.

**Contact:** [details]

---

## 5. Status of each path

| Path | Status | Requires user authorisation? |
|---|---|---|
| Licensed data agreement | Early stage; no source identified | Yes — for outreach |
| Prospective consent-based collection | Early stage; design complete | Yes — for collection to begin |
| Both | Not started | Yes |

**Decision required from the user:** whether to pursue either or both paths, and at
what stage. Until then, RailConfirm's data blocker remains open.

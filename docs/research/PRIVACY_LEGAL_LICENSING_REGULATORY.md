# India privacy, legal, licensing and regulatory review

**Last reviewed: 2026-10-31**
**Scope: Workstream G — privacy, legal, licensing, regulatory research**

This document records the legal and policy environment relevant to RailConfirm in
India, based on authoritative sources where available. Current requirements are
distinguished from unresolved issues. Where professional advice is required, the issue
is flagged and the exact decision the user needs is identified. This is not legal
advice.

---

## 1. Primary statute: Digital Personal Data Protection Act, 2023 (DPDPA)

- **Act:** Digital Personal Data Protection Act, 2023 (No. 22 of 2023).
- **Passed:** August 2023 (President's assent, notified by the Central Government).
- **Scope:** digital personal data; applies to processing within India and to
  processing outside India in connection with goods/services offered to Data Principals
  in India.
- **Definitions:** Data Principal (individual), Data Fiduciary (entity determining the
  purpose and means), Significant Data Fiduciary (SDF, designated by Central Government).
- **Principles:** purpose limitation, collection limitation, apprised consent.
- **Status:** enacted; operating through the DPDP Rules, 2025, which were notified 13
  November 2025. Phased implementation: immediate (13 Nov 2025), one year post-
  publication, 18 months post-publication.

### 1.1 Key obligations

- **Consent (Section 6; Rules 3–9):** consent must be free, specific, informed,
  unconditional, unambiguous, clear affirmative action; standalone notice per purpose;
  withdrawal mechanism at least as easy as giving. Bundled consent invalid. Withdrawal
  triggers erasure unless legal retention applies.
- **Legitimate uses (Section 7):** processing without consent for state function,
  legal obligation, medical emergency, public order, employment, voluntary data with
  no objection. Narrowly construed.
- **Security safeguards (Rule 6):** encryption, obfuscation/masking, access control,
  monitoring, backups, detection, contractual measures; 1-year log retention.
- **Breach notification (Rule 7):** intimation to Board without delay; full details
  within 72 hours.
- **Retention and erasure (Rule 8):** erase once purpose served; 48-hour prior
  intimation; sectoral retention up to 3 years (commerce), 1 year (state security).
- **Children's data (Rules 10, 12):** verifiable parental consent; no tracking/
  profiling/targeted ads.
- **Persons with disabilities (Rule 11):** verifiable guardian consent.
- **Grievance redress (Rule 9, 14):** published mechanism; respond within 90 days;
  publish DPO.
- **Cross-border transfers (Section 16; Rule 15):** allowed unless restricted by the
  Central Government; additional safeguards for SDFs.
- **Research, archiving, statistics (Rule 16; Schedule II):** exempts research use,
  **provided no decision is made about an identifiable individual**.
- **SDFs (Act 10; Rule 13):** DPO in India, independent data auditor, annual DPIA and
  audit, additional safeguards, restricted data may not leave India.
- **Penalties:** up to ₹200 crore per violation for core obligations and security;
  up to ₹250 crore for SDF-related non-compliance; appeals to TDSAT.

### 1.2 Relevant exemptions and scope limits

- The DPDPA applies to **digital personal data**. It does not cover non-digital
  records unless digitised. Passenger names are digital personal data; the model's
  schema does not collect names (data minimisation).
- **Research exemption (Rule 16):** data processing for research/statistical analysis
  is exempt **if** the results are not used to make decisions about identifiable
  individuals.
- **Publicly disclosed data (Schedule II):** exemption for personal data already
  publicly disclosed.

---

## 2. Data-minimisation, retention, and deletion

- Only personal data necessary for the purpose may be collected.
- Data should not be retained beyond the purpose; upon consent withdrawal, erase
  unless legal obligation.
- DPDP Rules specify log retention (1 year minimum) and sectoral caps (3 years
  commerce; 1 year state security).
- **RailConfirm applicability:** the local build does not collect passenger names.
  Any future live-PNR integration that ingests passenger identifiers must comply with
  minimisation, retention, deletion, breach, and rights workflows before any such
  integration is built.

---

## 3. IRCTC and railway website terms

- **IRCTC terms and conditions:** personal and non-commercial use; **automation
  software and scripting software strictly prohibited**; IRCTC reserves the right to
  deactivate such users and release tickets booked through unauthorised automation,
  with no refund. No robot/spider/other automatic device to monitor or copy pages
  without prior written permission.
- **IRCTC B2C PSP Policy (Edition 2025, Ver 3.0, w.e.f. 20-09-2025):** sets enquiry
  charges (EACC Rs.0.25/enquiry above look-to-book ratio 1:100; PNR enquiry charge
  Rs.0.25/enquiry), integration requirements, PSP obligations, penalties for
  unauthorised sharing of PNR Enquiry APIs.
- **B2B PSP norms:** registration, API documentation, eligibility criteria.

### 3.1 Implication for automated access

IRCTC terms **prohibit automated access without authorisation**. Any automated collection
against IRCTC or restricted services requires explicit authorisation; bypassing
logins, CAPTCHAs, rate limits or provider restrictions is barred. RailConfirm must not
automate access to IRCTC or other restricted services, and must not scrape or bypass
restrictions.

---

## 4. API-provider contractual restrictions

- **CRIS Pravah API** (`crisapis.indianrail.gov.in`): Terms of Use require access only
  by the described means; no reverse engineering/disassembly; no sublicensing;
  no probing or vulnerability testing; no interference or disruption. Use is for the
  user's own organisation, not for third parties.
- **IRCTC B2C PSP/PSP integration:** programmatic access is **contractual**; the PNR
  Enquiry API is not shareable with third parties without IRCTC approval; penalties
  apply.

**Conclusion:** authorised programmatic access requires a formal contract or partner
agreement, not self-service.

---

## 5. Dataset copyright and licence scope

- Open government data (data.gov.in) catalogue items carry usage terms that must be read
  before ingestion, storage, transformation, training, and redistribution. A catalogue
  description "CC0: Public Domain" is not a licence grant from this repository's
  perspective unless a licence file is present.
- Third-party dataset licences must be checked for model-training permission and
  redistribution rights separately. The Kaggle Railofy competition `LICENSE` was read
  as verbatim GPL-3.0 with no "dataset" wording, so it establishes no dataset terms and
  its copyleft terms do not fit an Apache-2.0 project.
- **Rule for the repository:** a source is not approvable merely because it is
  downloadable; rights for storage, training and publication must be documented per
  source.

---

## 6. Open-source software licence compatibility

- RailConfirm's original materials are Apache-2.0 (ADR-0006: Apache-2.0 for original
  repository materials).
- **GPL-3.0 is incompatible with Apache-2.0** for incorporated files (not legally
  fatal per se, but the copyleft terms do not license the project's Apache-2.0 scope;
  this is a compatibility consideration for any third-party code reused).
- The project carries no non-free or copyleft dependencies that conflict with the
  Apache-2.0 original materials. Any new dependency must be Apache-2.0-compatible.

---

## 7. Publishing aggregate model results from restricted data

- Under DPDPA Rule 16 and Schedule II, research/statistical-processing exemptions
  apply **if results are not used to make decisions about identifiable individuals**.
- Publishing aggregate, non-identifiable model outputs (e.g., Brier scores on
  aggregated cohorts) is not personal-data processing and is not restricted by the
  exemption; publishing per-reservation outcomes is.
- **RailConfirm rule:** reports contain cohort aggregates and abstentions, never
  per-reservation outcomes, unless a dataset is approved for permitted use.

---

## 8. User-contributed railway observations

- Users may contribute railway observations (status, delays, alerts). Those contributions
  are personal data of the contributor and, where an observation identifies a train,
  contextual data of the railway. Processing must follow the DPDPA: notice, consent
  where required, minimisation, and deletion upon withdrawal.
- The current build does not collect user-contributed observations; this is a future
  path if approved, with its own consent design.

---

## 9. Consumer-facing disclaimers and product claims

- The product must not represent predictions as guaranteed or official outcomes
  (out of scope until separately approved).
- Predictions are estimates based on historical-frequency and structural indicators;
  the target is final-chart outcome, not a guarantee.
- Disclaimers must state: data availability state, abstention reasons, and the
  limitation that no verified model has been trained on approved data.

---

## 10. Compliance checklist

| Requirement | Source | RailConfirm status |
|---|---|---|
| Data minimisation | DPDPA 2023 | Align: do not collect names; local build does not |
| Consent / notice | DPDP Rules 2025 | Required before any personal-data collection for a purpose |
| Erasure on consent withdrawal | DPDPA 2023; Rule 8 | Retain deletion workflow (ADR-0015/0040) |
| Breach notification | DPDP Rules 2025 | Required if personal data is processed; current build minimal |
| Security safeguards | DPDP Rules 2025 | Apply to any live-PNR integration |
| Retention limits | DPDP Rules 2025 | Apply to storage; 1-year log minimum; sectoral caps apply |
| No decisions about identifiable individuals from research | DPDPA 2023 | Apply to report/prediction outputs |
| No automated access to restricted services | IRCTC terms | Banned; do not automate IRCTC |
| Official API access contractual | CRIS Pravah; IRCTC B2C | Requires contract; no self-service |
| Licence compatibility | Apache-2.0 + third-party | Check each dependency; no GPL-3.0 reuse |
| Publication of aggregate results | DPDPA 2023 | Safe; per-reservation results need approval |

---

## 11. Flags and outstanding decisions requiring qualified review

1. **Live-PNR integration.** If RailConfirm later ingests passenger identifiers via an
   authorised live PNR API, it must follow DPDPA consent, minimisation, retention,
   deletion, breach-notification and rights workflows, and any SDF thresholds if
   applicable. **Decision needed:** does the user authorise this, and under what
   data-protection controls?
2. **Significance designation.** RailConfirm's use of passenger data (if any) should be
   assessed against the Significant Data Fiduciary thresholds by a qualified
   practitioner. **Decision needed:** is the project or any future service an SDF?

**This is not legal advice. These items require qualified Indian legal review before any
data-dependent feature is enabled.**

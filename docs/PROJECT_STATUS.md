# Project status and scope

Last reviewed: 2026-10-21

## Status

The repository now has a product specification, engineering design, research/governance baseline and phased roadmap. It remains documentation and planning only: written contracts describe intended behavior; they do not imply running application code or a validated model. Under ADR-0007, the current build is local-first and must not depend on third-party runtime APIs. ADR-0008 clarifies that authorized live status data and verified current/upcoming contextual signals remain planned core capabilities of the long-term product.

| Area | Status | Exit condition |
|---|---|---|
| Product brief and requirements | Initial baseline documented | Review requirements against a first implementation |
| User journeys and MVP acceptance | Draft documented | Implement and test the core vertical slice |
| Architecture and API contracts | Proposed design | Validate against actual stack and implementation |
| Domain/storage contracts | Logical model documented | Implement versioned schemas and tests |
| Agent-assisted local dataset intake | In progress | Source, licence/terms, labels, privacy, quality and checksum are documented |
| Historical outcome dataset | Not established | Provenance and final-outcome labels are validated |
| Baseline predictor | Not implemented | Reproducible baseline runs on eligible labelled data |
| ML model | Not implemented | Chronological evaluation demonstrates utility over baseline |
| Calibration | Not implemented | Calibration is measured on held-out journeys |
| Manual-entry web flow | Not implemented | Input and result flow works end-to-end |
| External data integrations | Planned core long-term capability; not implemented in the current build | Delivered in roadmap Phases 8–10 after local model/data gates, with source-specific ADR and verified permissions |
| Verified news/event/context feeds | Planned core long-term capability; not connected | Source and permitted use reviewed; incremental value demonstrated on temporal holdout |
| Tests and CI | Not implemented | Relevant static checks and automated tests run in CI |
| Production monitoring | Not implemented | Freshness, error rates, drift and calibration are monitored |

## In scope

- Passenger-level final-status probabilities.
- Group-level joint outcome probabilities for bookings with multiple passengers.
- WL and RAC categories, including multiple categories where suitable labels exist.
- Historical and time-stamped status progression.
- A local-first manual-input MVP powered by approved local datasets and model artifacts, with no external runtime API requirement.
- Reproducible model evaluation, calibration, coverage reporting and model cards.
- Privacy-preserving storage and an auditable data-source registry.

## Not part of the current local-first build

- Third-party runtime APIs, live PNR lookup/polling, live news or event feeds, weather/calendar APIs, and hosted inference are not implemented now. They remain planned future product capabilities in roadmap Phases 8–10, rather than permanently excluded goals. See ADR-0008.

## Out of scope until separately approved

- Representing predictions as guaranteed or official outcomes.
- Unapproved automation against IRCTC or other restricted services.
- Bypassing logins, CAPTCHAs, rate limits or provider restrictions.
- Collecting passenger names for the purpose of prediction.
- Claiming support for every train, quota or status before evidence exists.
- Training on data whose provenance, licence or permitted use is unclear.
- Allowing an LLM to directly invent or modify probability values.

## Working definition of done

A prediction feature is not complete because the UI renders a percentage. It is complete only when:

1. Its target and prediction timestamp are defined.
2. Inputs have provenance and pass validation.
3. The model and version are identifiable.
4. Evaluation uses a time-safe held-out dataset.
5. Calibration and subgroup limitations are documented.
6. Error and unavailable-data states are handled.
7. User-facing copy does not overstate certainty.

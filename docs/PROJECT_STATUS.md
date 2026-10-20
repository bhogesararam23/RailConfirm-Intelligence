# Project status and scope

Last reviewed: 2026-10-21

## Status

The repository is at the initial documentation and research-planning stage. The contents define what we intend to build and the conditions under which predictions may be described as reliable; they do not claim that the software or model has already been implemented.

| Area | Status | Exit condition |
|---|---|---|
| Product requirements | Initial draft | Requirements are testable and scoped |
| Data-source discovery | In progress | Sources, rights, coverage and costs are recorded |
| Historical outcome dataset | Not established | Provenance and final-outcome labels are validated |
| Data contract | Initial specification | Schemas and normalization tests exist in code |
| Baseline predictor | Not implemented | Reproducible baseline runs on eligible labelled data |
| ML model | Not implemented | Chronological evaluation demonstrates utility over baseline |
| Calibration | Not implemented | Calibration is measured on held-out journeys |
| Manual-entry web flow | Not implemented | Input and result flow works end-to-end |
| Live PNR tracking | Not integrated | Written permission/terms and a functioning provider are verified |
| News/event features | Research candidate | Incremental value demonstrated on temporal holdout |
| Production monitoring | Not implemented | Freshness, error rates, drift and calibration are monitored |

## In scope

- Passenger-level final-status probabilities.
- Group-level joint outcome probabilities for bookings with multiple passengers.
- WL and RAC categories, including multiple categories where suitable labels exist.
- Historical and time-stamped status progression.
- A manual-input MVP with an explicit path to authorized live tracking.
- Reproducible model evaluation, calibration, coverage reporting and model cards.
- Privacy-preserving storage and an auditable data-source registry.

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

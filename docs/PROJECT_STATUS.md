# Project status and scope

Last reviewed: 2026-10-21

## Status

The repository has completed its foundational engineering implementation (Phases 1–5 vertical slice) in local-first mode under ADR-0007. Application code, deterministic domain and API test suites, dataset validation pipeline, and interactive Next.js web application are implemented and verified. The system intentionally operates in abstention mode (`no_trained_model`) until a candidate historical dataset passes the intake checklist. External live data integrations remain planned core capabilities of the long-term product in roadmap Phases 8–10 (ADR-0008).

| Area | Status | Exit condition |
|---|---|---|
| Product brief and requirements | Initial baseline implemented | Continuous review against user testing |
| User journeys and MVP acceptance | Implemented (Phases 1–5 vertical slice) | Core local manual-input flow verified |
| Architecture and API contracts | Implemented and verified | Versioned FastAPI routes and Next.js client |
| Domain contracts and status parsing | Implemented and tested (43 tests passing) | Versioned mapping (v1.0.0); unknown codes mapped to UNKNOWN |
| Local dataset intake pipeline | Implemented (`loader`, `validator`, `manifest`) | Evaluated candidate dataset passing checklist |
| Historical outcome dataset | No approved dataset yet; candidate intake ready | Provenance and final-chart labels validated |
| Baseline predictor | Implemented (Laplace smoothing; abstains if unapproved) | Reproducible run on approved historical data |
| ML model | Deferred until approved dataset available | Chronological evaluation demonstrates utility over baseline |
| Calibration | Deferred until approved dataset available | Calibration measured on held-out future journeys |
| Manual-entry web flow | Implemented and verified (Next.js 14 + Tailwind) | Input and structured result flow working end-to-end |
| External data integrations | Planned core long-term capability; not implemented in current build | Delivered in roadmap Phases 8–10 with source-specific ADRs |
| Verified news/event/context feeds | Planned core long-term capability; not connected | Source review and incremental value on temporal holdout |
| Tests and CI | Implemented (43 pytest tests, 84% coverage, ruff, mypy, Next.js build, .github/workflows/ci.yml) | Automated execution on push to GitHub |
| Production monitoring | Planned for deployment release | Error rates, drift, and calibration monitoring |

## In scope (Current build)

- Domain models with versioned status mapping (`v1.0.0`).
- Passenger-level and group-level outcome schemas (CNF, RAC, WL, CANCELLED, OTHER).
- Local dataset intake pipeline (`railconfirm.data`) with SHA-256 manifest generation.
- Full FastAPI backend (`POST /v1/predictions/manual`, `GET /v1/health`) with structured abstention when no model is active.
- Full Next.js frontend with accessible UI, forms, status badges, and prediction report.
- Clearly labelled synthetic fixtures for deterministic tests (`backend/tests/fixtures/`).
- Automated tests passing with zero dependencies on third-party runtime APIs.

## Not part of the current local-first build

- Third-party runtime APIs, live PNR lookup/polling, live news/event feeds, and hosted inference are not implemented now. They remain planned core product capabilities in roadmap Phases 8–10. See ADR-0008.

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

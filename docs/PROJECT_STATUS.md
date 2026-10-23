# Project status and scope

Last reviewed: 2026-10-23 (after the foundation audit, the frontend rebuild and the training/evaluation pipeline)

## Status

The repository has a working local-first application core, but **no prediction is currently produced and no result has been validated against real railway data.** That is the honest state, and the code is built so that it is the visible state rather than a hidden one.

Milestone A (audit and harden the existing code) is complete: the domain, inference, API and data layers were reviewed against observed behaviour and eleven defects were fixed with regression tests. Several of the fixes removed ways the system could present an unsupported claim as a trustworthy one — an evidence-free probability from a malformed frequency table, an unverified status family mapped to the nearest familiar category, a split whose test set was empty while reporting success, and a validator that called a dataset valid because one row parsed.

Nothing is blocked by a missing dependency. The blocker is a dataset: no candidate has cleared `docs/data/DATASET_INTAKE_CHECKLIST.md`, so training, evaluation and calibration have no eligible input and the product abstains by design.

## Area status

Each row states which of these it is: **verified with real data**, **implemented and tested (synthetic fixtures only)**, **implemented but not fully tested**, **planned**, **blocked**.

| Area | Status | Exit condition |
|---|---|---|
| Product brief, requirements, journeys | Implemented and tested (synthetic fixtures only) — documentation, so "tested" means reviewed | Validated against real user testing |
| Domain contracts and status parsing | Implemented and tested (synthetic fixtures only), mapping v1.1.0 | Authoritative verification of each status family; `CK`/`CKWL` remain `UNKNOWN` until a source is recorded |
| Temporal integrity rules (as-of timestamps, leakage refusal) | Implemented and tested | Sub-second and multi-timezone evidence handling when a real source defines it |
| Prediction API (`POST /v1/predictions/manual`, `GET /v1/health`) | Implemented and tested, verified over real HTTP locally (uvicorn, health, abstention, validation, CORS, 413) | Public deployment is out of scope for the local build |
| Historical-frequency baseline | Implemented and tested (synthetic fixtures only). **Never loaded with real data anywhere in the codebase** | An approved dataset converted into a promoted artifact |
| Model registry and artifacts | Implemented and tested (ADR-0009): JSON format, two-gate promotion, metadata validation. No artifact exists | A trained artifact that clears evaluation and is explicitly promoted |
| Group outcomes | Implemented and tested as an **independence baseline only**. It is not a validated model of correlated reservation outcomes | Joint/dependence-aware estimation once booking-level labels exist |
| Dataset intake pipeline (`loader`, `validator`, `manifest`, CLI) | Implemented and tested | A real candidate file put through it |
| Historical outcome dataset | **Blocked — none approved.** No candidate has passed the intake checklist | Provenance, licence, labels, privacy and quality reviewed by a named person |
| Training pipeline | Implemented and tested against synthetic fixtures: eligibility gate, chronological split, cohort fitting, candidate artifact writing. **Never run on real data — there is none.** | A reproducible fit on an approved dataset |
| Temporal evaluation and metrics | Implemented and tested against synthetic fixtures (ADR-0011): multiclass Brier, log loss, prevalence-baseline comparison with skill, **target-event scoring for both documented targets**, reliability bands, coverage/abstention accounting, per-segment counts with low-sample flags, deterministic JSON report. Rolling-origin evaluation is **not** implemented. | A scored run on approved real data |
| Calibration | **Planned, not implemented.** Reports state explicitly that no calibration was fitted. | Calibration fitted on the validation period and measured on a locked test period |
| Persistence, prediction history | **Planned, not implemented.** Nothing is stored; `docs/technical/STORAGE_MODEL.md` describes a design that does not exist yet | A privacy-safe local store with retention rules |
| Manual-entry web flow | Implemented, tested (81 frontend tests) and **verified end-to-end in a browser against both running servers** — abstaining and supported paths, CORS preflight, provenance and evidence rendering | A public deployment and real predictions to display |
| Frontend tests | Implemented (Vitest + Testing Library): null-safety, abstention wording, error envelope, validation parity, contract rendering | Live cross-stack contract check against a running backend |
| Tests and CI | Implemented and verified green on `main` (384 backend tests, 96% branch coverage, CI jobs observed passing on pushed commits) | Continuous |
| External live integrations (Phases 8–10) | Planned core long-term capability; not implemented in the current build | Provider-specific ADR plus authorized access (ADR-0008) |
| Production monitoring and deployment | Planned | A real deployment exists |

## In scope (current build)

- Domain models with a versioned status mapping, offset-aware timestamps and stable abstention reasons.
- Passenger-level and group-level outcome schemas (`CNF`, `RAC`, `WL`, `CANCELLED`, `OTHER`).
- Local dataset intake: CSV/JSON loading with explicit safety checks, row-contract validation with per-reason accounting, deterministic manifests and manifest verification.
- Chronological splitting that reports inability to evaluate rather than faking one.
- Baseline training and temporal evaluation (`backend/railconfirm/training/`, ADR-0011): an approval-gated dataset load, cohort fitting on the training partition only, candidate artifact writing, Brier/log-loss scoring against a prevalence baseline, the target's own event scored alongside the distribution, and a deterministic report that defines every number it publishes.
- FastAPI backend with structured abstention, a documented error envelope, CORS, request bounds and privacy-aware access logging.
- JSON model artifacts with validated metadata and explicit promotion.
- Clearly labelled synthetic fixtures for deterministic tests (`backend/tests/fixtures/`).
- A Next.js frontend written against the shipped API contract, with 81 tests.

## What the system does today

Every manual prediction returns a structured abstention with `no_trained_model` and `registry_status: no_active_version`, because nothing is promoted and no approved dataset exists. A `200` response with `p_cnf: null` and a reason code is the correct product behaviour here, and it is what the tests assert. If you see a probability, either a promoted artifact was created deliberately or something is wrong.

## Not part of the current local-first build

Third-party runtime APIs, live PNR lookup or polling, live news/event feeds and hosted inference are not implemented now. They remain planned core product capabilities in roadmap Phases 8–10 (see ADR-0008), deferred rather than removed.

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

Items 4 and 5 cannot be met today and are not claimed anywhere. Items 1–3 and 6–7 are met by the current code.

## Claim discipline

No accuracy figure, benchmark, calibration result, deployment status or CI history is recorded in this repository unless the run that produced it exists and is named. `CHANGELOG.md` and `docs/DEVELOPMENT_LOG.md` distinguish what was executed from what was written.

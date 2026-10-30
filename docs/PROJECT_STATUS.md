# Project status and scope

Last reviewed: 2026-10-24 (after the foundation audit, frontend rebuild, training/evaluation pipeline, rolling-origin evaluation, history listing/deletion, dependent group outcomes, logistic calibration with subgroup measurement, frozen-artifact decay, a second cohort-position estimator, and the paired comparison that decides between them)

## Status

The repository has a working local-first application core, but **no prediction is currently produced and no result has been validated against real railway data.** That is the honest state, and the code is built so that it is the visible state rather than a hidden one.

Milestone A (audit and harden the existing code) is complete: the domain, inference, API and data layers were reviewed against observed behaviour and eleven defects were fixed with regression tests. Several of the fixes removed ways the system could present an unsupported claim as a trustworthy one — an evidence-free probability from a malformed frequency table, an unverified status family mapped to the nearest familiar category, a split whose test set was empty while reporting success, and a validator that called a dataset valid because one row parsed.

Nothing is blocked by a missing dependency. The blocker is a dataset: no candidate has cleared `docs/data/DATASET_INTAKE_CHECKLIST.md`, so training, evaluation and calibration have no eligible input and the product abstains by design. The 2026-10-23 candidate search (`docs/data/CANDIDATE_DATASET_REVIEW.md`) found nothing carrying both a booked status and a verified final-chart label under a licence that permits training — one widely-published "ticket confirmation" dataset is self-declared synthetic, the schedule/fare candidates have no outcome labels, and the licence-clean metadata (stations, trains, routes) cannot produce them.

## Area status

Each row states which of these it is: **verified with real data**, **implemented and tested (synthetic fixtures only)**, **implemented but not fully tested**, **planned**, **blocked**.

| Area | Status | Exit condition |
|---|---|---|
| Product brief, requirements, journeys | Implemented and tested (synthetic fixtures only) — documentation, so "tested" means reviewed | Validated against real user testing |
| Domain contracts and status parsing | Implemented and tested (synthetic fixtures only), mapping v1.1.0 | Authoritative verification of each status family; `CK`/`CKWL` remain `UNKNOWN` until a source is recorded |
| Temporal integrity rules (as-of timestamps, leakage refusal) | Implemented and tested | Sub-second and multi-timezone evidence handling when a real source defines it |
| Prediction API (`POST /v1/predictions/manual`, `GET /v1/predictions/{id}`, `GET /v1/health`) | Implemented and tested, verified over real HTTP locally (uvicorn, health, abstention, validation, CORS, 413, store-and-reopen, unrouted-path envelope) | Public deployment is out of scope for the local build |
| Historical-frequency baseline | Implemented and tested (synthetic fixtures only). **Never loaded with real data anywhere in the codebase** | An approved dataset converted into a promoted artifact |
| Model comparison and promotion evidence | Implemented and tested (ADR-0021): `compare` fits both estimators on one split (refusing different partitions, different targets, the same estimator on both sides and unequal prevalence baselines), scores both against one training-window baseline, pairs rows by position, counts rows only one model answered separately, and issues `candidate` only when the distribution Brier, the event Brier, the paired win count and coverage all favour it **on the locked period**. Demonstrated both ways on purpose-built synthetic fixtures. Promotion remains a human act; nothing here has been read from approved data | A real comparison over an approved dataset, then a named promotion decision |
| Second estimator: cohort position bands | Implemented and tested (ADR-0020): `cohort_position_baseline` splits each cohort by the as-of queue position in fixed doubling bands, answers from a band only when it has enough rows, records `min_band_rows` on the artifact, and says in `basis` which cell answered or why the cohort did. Its own artifact format, with load- and write-time refusal of any format/estimator/`features_used`/band mismatch. On the labelled synthetic fixture it loses to the flat baseline (locked event Brier 0.275914 vs 0.239960), because those rows' outcomes do not depend on position | The same question asked of approved data, through the ADR-0021 comparison |
| Model registry and artifacts | Implemented and tested (ADR-0009, ADR-0013, ADR-0020): two JSON formats (`/2` frequency, `cohort-position-baseline/1`), two-gate promotion, metadata validation, and load-time refusal of an artifact whose declared `cohort_semantics`, `features_used`, format or band block disagree with the estimator it names. No artifact exists | A trained artifact that clears evaluation and is explicitly promoted |
| Group outcomes | Implemented and tested (synthetic fixtures only, ADR-0003, ADR-0016): exact Poisson-binomial distribution ($P(K = k)$ and $P(K \ge k)$) under independence baseline, and queue-clearing comonotonic bounds under FIFO priority. Group outcomes scored in `score_partition()`. Not yet validated against real group data | Evaluated on an approved dataset with labelled booking groups |
| Dataset intake pipeline (`loader`, `validator`, `manifest`, CLI) | Implemented and tested | A real candidate file put through it |
| Historical outcome dataset | **Blocked — none approved.** No candidate has passed the intake checklist | Provenance, licence, labels, privacy and quality reviewed by a named person |
| Training pipeline | Implemented and tested against synthetic fixtures: a gate that enforces **technical eligibility** (not just structure) and hands on only the rows validation kept, chronological split, cohort fitting keyed by the shared as-of status, candidate artifact writing. **Never run on real data — there is none.** | A reproducible fit on an approved dataset |
| Temporal evaluation and metrics | Implemented and tested against synthetic fixtures (ADR-0011, ADR-0013, ADR-0014, ADR-0016, ADR-0017, ADR-0018): multiclass Brier, log loss, prevalence-baseline comparison with skill, **target-event scoring for both documented targets**, reliability bands, coverage/abstention accounting, per-segment counts with low-sample flags (including as-of vs booked status segments), deterministic JSON report, **rolling-origin evaluation across multiple cutoffs with per-cutoff refitting and a two-origin floor**, **frozen-artifact decay that keeps one table and one baseline fixed and judges each later horizon against it (two horizons minimum, cutoff taken from the artifact)**, and **group-event scoring for multi-passenger bookings**. 16 cohort-parity tests prove fit, score and serve query the same key. | A scored run on approved real data |
| Calibration | **Implemented and tested on synthetic fixtures** (ADR-0017, ADR-0019): logistic scaling of the target event fitted on the validation partition only, refused unless it improves validation, embedded as a reviewable artifact block, applied by the same arithmetic in evaluation and serving, and measured on the locked test in the report. Every scorecard also publishes subgroup calibration — mean predicted, observed rate and gap per class, quota and status, with the row count and a `low_sample` flag under a floor of 25 rows, and no per-segment correction fitted. **Never fitted on real data, because no approved dataset exists.** | A layer whose improvement is real, measured on an approved dataset, and segment gaps read on cohorts with enough rows to claim them |
| Persistence, prediction history | Implemented and tested (ADR-0012, ADR-0015): opt-in SQLite store, reopen by internal id, retention floor enforced, denied-key and PNR-shaped values refused at the write. **Disabled by default.** List route returns metadata-only summaries (no payload); delete route removes one row immediately; absent/expired/deleted ids return the same 404 body. Verified in a browser. | A label-feedback path with its own consent design |
| Manual-entry web flow | Implemented, tested (115 frontend tests) and **verified end-to-end in a browser** — abstaining and supported paths, CORS preflight, provenance and evidence rendering, keep-this-report, reopen, history page with two-step deletion, and confirmed berths distribution grid. | A public deployment and real predictions to display |
| Frontend tests | Implemented (Vitest + Testing Library): null-safety, abstention wording, error envelope, validation parity, contract rendering, stored-report reopening and its three failure wordings, and group outcome distribution rendering | Browser-level interaction, focus-order and screen-reader verification in CI |
| Cross-stack check | Implemented and green locally (ADR-0027): `scripts/smoke_full_stack.py` starts the real API and the production frontend build on loopback ports and checks health, the abstention, a field refusal, the same-day horizon refusal, the history round trip, a PNR-shaped id, an unrouted path, the CORS preflight and the rendered pages over sockets; asserts the built bundle names the running backend; and runs `npm run test:live`, which drives `src/lib/api.ts` against that server. **No browser runs**, so a JavaScript-only failure would still pass, and no artifact is promoted, so every prediction in it abstains | A browser driver for interaction and accessibility coverage |
| Tests and CI | Implemented and verified green on `main` (1043 backend tests, 96.18% branch coverage locally, 115 frontend tests, 5 live cross-stack tests, four CI jobs including the full-stack smoke; CI observed passing on pushed commits through `127a254`) | Continuous |
| External live integrations (Phases 8–10) | Planned core long-term capability; not implemented in the current build | Provider-specific ADR plus authorized access (ADR-0008) |
| Production monitoring and deployment | Planned | A real deployment exists |

## In scope (current build)

- Domain models with a versioned status mapping, offset-aware timestamps and stable abstention reasons.
- Passenger-level and group-level outcome schemas (`CNF`, `RAC`, `WL`, `CANCELLED`, `OTHER`).
- Multi-passenger group outcomes (ADR-0003, ADR-0016): exact Poisson-binomial distribution convolution for PMF and cumulative berth confirmation, sequential queue-clearing comonotonic upper bound modeling Indian Railways FIFO waitlist queue clearance, and group-level Brier scoring in evaluation.
- Local dataset intake: CSV/JSON loading with explicit safety checks, row-contract validation with per-reason accounting, deterministic manifests and manifest verification.
- Chronological splitting that reports inability to evaluate rather than faking one.
- Baseline training and temporal evaluation (`backend/railconfirm/training/`, ADR-0011, ADR-0013): a dataset gate that verifies the manifest, requires the human approval record, enforces technical eligibility and passes on only the rows validation kept; cohort fitting on the training partition keyed by the one as-of status rule that scoring and serving also use; candidate artifact writing; Brier/log-loss scoring against a prevalence baseline; the target's own event scored alongside the distribution; and a deterministic report that defines every number it publishes and states which features the estimator actually reads.
- Frozen-artifact decay (`railconfirm.training decay`, ADR-0018): the artifact's own `trained_to` is the cutoff, its cohorts, prevalence baseline and calibration block are applied unchanged to every horizon, a booking spanning the cutoff or a calendar short of two horizons refuses the whole run, and drift is reported as first-to-last plus spread rather than a mean that hides the ordering. On the synthetic fixture the estimator a single cutoff reports as event Brier 0.239487 vs a 0.24 base rate scores 0.243482, 0.240300, 0.239411 across three two-date horizons and beats the frozen baseline in one of three.
- Rolling-origin evaluation (`railconfirm.training origins`, ADR-0014): whole-date expanding cutoffs, the cohort table and prevalence baseline refitted from each origin's own past, scoring origins counted separately from silent ones, a Brier and coverage range reported instead of a flattering mean, and a refusal when the calendar supports fewer than two cutoffs.
- FastAPI backend with structured abstention, a documented error envelope on every failure including unrouted paths, CORS, request bounds and privacy-aware access logging.
- Opt-in local prediction history (`backend/railconfirm/storage/`, ADR-0012): a saved report reopens at `/prediction/[id]` with the model version it was served with, expires after a configured retention window, and refuses a payload carrying a name key or a PNR-shaped value. Off by default, and the response says whether a save actually happened.
- JSON model artifacts with validated metadata and explicit promotion.
- Clearly labelled synthetic fixtures for deterministic tests (`backend/tests/fixtures/`).
- A Next.js frontend written against the shipped API contract, with 115 tests.

## What the system does today

Every manual prediction returns a structured abstention with `no_trained_model` and `registry_status: no_active_version`, because nothing is promoted and no approved dataset exists. A `200` response with `p_cnf: null` and a reason code is the correct product behaviour here, and it is what the tests assert. If you see a probability, either a promoted artifact was created deliberately or something is wrong.

Nothing is stored unless the operator enables history *and* the request asks to be kept; `GET /v1/health` reports which state the server is in, and the response's `stored` field reports what happened to that request.

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
5. Calibration, subgroup-calibration and low-sample limitations are documented and enforced by report tests.
6. Error and unavailable-data states are handled.
7. User-facing copy does not overstate certainty.

Items 4 and 5 cannot be met today and are not claimed anywhere. Items 1–3 and 6–7 are met by the current code.

## Claim discipline

No accuracy figure, benchmark, calibration result, deployment status or CI history is recorded in this repository unless the run that produced it exists and is named. `CHANGELOG.md` and `docs/DEVELOPMENT_LOG.md` distinguish what was executed from what was written.

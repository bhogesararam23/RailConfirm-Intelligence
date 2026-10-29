# Architecture Decision Records

Architecture Decision Records (ADRs) capture material decisions, why they were made, and what they cost. They make the reasoning durable across coding sessions and contributors.

## Rules

- Name files `ADR-0001-short-title.md`, `ADR-0002-short-title.md`, and continue sequentially.
- Never renumber or silently rewrite an accepted ADR. Correct factual mistakes transparently or supersede a decision with a later ADR.
- Use the next available number after inspecting this directory.
- Record status as Proposed, Accepted, Rejected or Superseded.
- One ADR may cover a set of tightly related decisions made together. Separate independent decisions.
- An ADR is required for material changes to architecture, data sources/rights, model targets, evaluation protocol, privacy/security, deployment, dependency strategy or licensing.
- Trivial formatting, typo fixes, routine refactoring and purely local implementation choices do not need an ADR.
- Link the relevant ADR from the code, specification, pull request or changelog when useful.
- If a decision changes, create a new ADR that refers to the earlier one.

## Template

```markdown
# ADR-NNNN: Short decision title

- **Status:** Proposed | Accepted | Rejected | Superseded
- **Date:** YYYY-MM-DD
- **Decision owner:** Project maintainers
- **Related:** ADR-NNNN, issue/PR, specification

## Context
What problem needs a decision? Include constraints and evidence.

## Decision
State the decision clearly and narrowly.

## Alternatives considered
List credible alternatives and why they were not selected.

## Consequences
Describe benefits, costs, risks, migration and follow-up work.

## Validation
How will the decision be tested or revisited? Record evidence, not assumptions.
```

## Index

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](ADR-0001-documentation-first-and-data-gates.md) | Documentation-first foundation and data-readiness gates | Accepted |
| [ADR-0002](ADR-0002-initial-application-and-ml-stack.md) | Candidate web/API/data/ML stack | Accepted as initial direction; implementation may validate or revise it |
| [ADR-0003](ADR-0003-prediction-targets-and-joint-group-outcomes.md) | Passenger targets and dependent group outcomes | Accepted |
| [ADR-0004](ADR-0004-temporal-evaluation-and-calibration.md) | Chronological evaluation and probability calibration | Accepted |
| [ADR-0005](ADR-0005-data-governance-and-pnr-privacy.md) | Source rights, live access and PNR privacy | Accepted |
| [ADR-0006](ADR-0006-apache-2-license.md) | Apache-2.0 for original repository materials | Accepted |
| [ADR-0007](ADR-0007-local-first-no-external-runtime-apis.md) | Local-first MVP without third-party runtime APIs in Phases 0–7 | Accepted |
| [ADR-0008](ADR-0008-live-data-integrations-as-long-term-core-capability.md) | Authorized live integrations as a core long-term product capability in Phases 8–10 | Accepted; clarifies future scope while retaining ADR-0007's current-build boundary |
| [ADR-0009](ADR-0009-artifact-trust-boundaries-and-unverified-status-codes.md) | JSON model artifacts with two-gate promotion, split abstention reasons, validated frequency tables, unverified status codes kept unknown | Accepted |
| [ADR-0010](ADR-0010-declared-check-configurations-and-repository-hygiene-gate.md) | Lint and type-check rule sets declared in the repository, constrained tool ranges, and a hygiene gate that can actually fail | Accepted |
| [ADR-0011](ADR-0011-provenance-gated-baseline-fitting-and-target-event-evaluation.md) | Provenance-gated baseline fitting, candidate-only artifacts, and evaluation of the target's own event | Accepted |
| [ADR-0012](ADR-0012-opt-in-local-prediction-history.md) | Opt-in local prediction history: two switches, a retention floor, reopen by internal id only | Accepted |
| [ADR-0013](ADR-0013-asof-cohort-rule-and-eligibility-enforced-training-gate.md) | One as-of cohort rule across fit/evaluate/serve, and a training gate that enforces technical eligibility and drops rejected rows | Accepted; raises ADR-0009's artifact format to `/2` |
| [ADR-0014](ADR-0014-rolling-origin-evaluation-with-per-cutoff-refitting.md) | Rolling-origin evaluation: whole-date expanding windows, per-cutoff refit and baseline, two-origin floor, scoring-origin counts kept separate from abstentions | Accepted |
| [ADR-0015](ADR-0015-history-listing-and-per-report-deletion.md) | History listing limited to ids and clocks, immediate per-report deletion, absent/expired/deleted answered alike | Accepted |
| [ADR-0016](ADR-0016-dependent-group-outcomes-and-group-event-evaluation.md) | Dependent group outcomes: exact Poisson-binomial distribution, queue-clearing comonotonic bounds, and group-event scoring in evaluation | Accepted |
| [ADR-0017](ADR-0017-logistic-calibration-fitted-on-validation-and-measured-on-the-locked-test.md) | Logistic calibration of the target event, fitted on validation only, embedded only when it helps there, measured on the locked test | Accepted; its "subgroup calibration is not measured" statement is superseded by ADR-0019 |
| [ADR-0018](ADR-0018-frozen-artifact-decay-across-successive-horizons.md) | Frozen-artifact decay: the artifact's own cutoff, one frozen baseline and calibration layer, two horizons minimum, drift reported as an ordering | Accepted |
| [ADR-0019](ADR-0019-subgroup-calibration-measured-with-a-row-floor-on-the-claim.md) | Subgroup calibration measured as observed-minus-predicted per segment on the served probability, with a row floor on what may be claimed | Accepted |
| [ADR-0020](ADR-0020-cohort-position-estimator-and-a-second-artifact-format.md) | A second estimator: cohort cells split by fixed as-of queue position bands, with its own artifact format and loader-enforced estimator contract | Accepted |
| [ADR-0021](ADR-0021-paired-model-comparison-on-the-locked-period.md) | Paired model comparison: one split or no comparison, rows paired by position, coverage as a condition, verdict judged on the locked period only | Accepted |
| [ADR-0022](ADR-0022-calibration-identity-bound-to-its-target-event.md) | A calibration's identity is its target's event: the target determines the classes, only validation may carry a fit, and serving and scoring refuse to disagree | Accepted |

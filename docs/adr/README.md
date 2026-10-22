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

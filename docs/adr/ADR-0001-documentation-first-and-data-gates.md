# ADR-0001: Documentation-first foundation and data-readiness gates

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer

## Context

RailConfirm Intelligence is intended to combine an ML research project and a public-facing web application. The highest-risk dependency is not frontend implementation; it is obtaining enough legally usable, time-stamped reservation observations and reliable final outcomes to train and evaluate probability estimates.

Building UI features before defining targets, data rights and evaluation could make unsupported predictions appear more complete than they are.

## Decision

Establish a documentation-first foundation. Define data contracts, source governance, target semantics, evaluation rules, privacy constraints and agent workflow before adding a trained model or live tracking. Gate model claims on observed results from a time-safe held-out dataset.

## Alternatives considered

- **Build the UI first:** Rejected as the primary sequence because it does not resolve data rights or establish what a probability represents.
- **Start with a complex model:** Rejected because model choice depends on available labels, data volume, missingness and category coverage.
- **Use illustrative or synthetic histories as real training evidence:** Rejected; synthetic data can test code but cannot establish real-world performance.

## Consequences

- Documentation and schemas will precede the production model.
- The initial UI may use clearly marked examples or return a no-data/unsupported response until real model evidence exists.
- Source permissions, quality and coverage must be reported explicitly.
- Early progress may look less feature-heavy, but the project can make defensible claims.

## Validation

The data-readiness gate is met only when at least one candidate dataset has a verified licence/contract basis, clear status and final-outcome semantics, traceable provenance, and enough coverage to support the proposed evaluation. No empirical model-performance claim is authorized by this ADR alone.

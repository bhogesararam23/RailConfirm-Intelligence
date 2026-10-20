# ADR-0003: Passenger targets and joint group outcomes

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** docs/model/PREDICTION_TARGETS.md

## Context

A single booking-level confirmation percentage does not answer what users need to know about each passenger. Passengers in one booking share train, journey and queue context, so their outcomes cannot be assumed independent without evidence.

## Decision

The primary target is each passenger's explicitly defined final-chart outcome at a specified prediction time. Keep CNF, RAC and WL distinct where outcome labels support them; preserve other and censored outcomes instead of silently collapsing them.

For multi-passenger bookings, support joint group-event estimates such as all CNF, all CNF/RAC, exactly (k) CNF, at least (k) CNF and any passenger remaining WL. Derive these from a joint or validated structured outcome distribution, not from multiplying per-passenger marginals by default.

## Alternatives considered

- **One probability per booking:** Rejected because it hides different passenger-level outcomes.
- **Treat RAC as the same as a confirmed berth:** Rejected because a full berth and RAC accommodation are distinct user outcomes.
- **Multiply marginal probabilities assuming independence:** Rejected as the default because common booking context creates dependence.

## Consequences

- Dataset structure must retain passenger membership and group relationships.
- Evaluation must include passenger-level and group-level proper scoring rules.
- The first model may support fewer categories than the product eventually intends.
- UI wording must state whether a metric refers to a full berth or at least RAC accommodation.

## Validation

Evaluate all group outputs on held-out groups and compare the joint method against a clearly defined baseline. Revisit the decision if valid data shows that the current group representation is infeasible or inadequate.

# Project canvas

Last reviewed: 2026-10-21

This page is the concise working canvas for the project. It tracks current assumptions and the next decisions; the detailed specifications remain in the linked documents.

## Problem

People with WL and RAC tickets have uncertainty about final accommodation, especially when a booking contains several passengers whose outcomes may differ.

## Intended value

- Passenger-wise probability estimates.
- Group-outcome probabilities for multi-passenger bookings.
- Time-aware estimates that change only when new evidence arrives.
- A transparent explanation of data coverage, freshness and uncertainty.
- Research results that can be reproduced and audited.

## Primary users

People checking an existing ticket, people evaluating a potential journey, and researchers evaluating probabilistic reservation-outcome models. The exact first user group will be narrowed based on MVP feedback and data access.

## Assumptions to test

- Historical status trajectories can be obtained under valid rights.
- Final outcomes can be verified consistently.
- Status movement contains useful signal beyond a current WL/RAC position.
- Joint group outcomes can be evaluated on enough multi-passenger bookings.
- Context features add value beyond a strong historical/status baseline.

None of these assumptions is a result until tested.

## Constraints

- Historical PNR outcomes may not be publicly available for unrestricted reuse.
- Live status access may require an approved provider and fees.
- Coverage will differ across quota, class, route, status category and prediction horizon.
- Passenger data and ticket identifiers need careful retention and access controls.
- The project must not imply official railway affiliation or guarantee outcomes.

## Current priority

**P0 — Data feasibility and research contract**
1. Identify candidate historical outcome datasets and verify rights.
2. Finalize status and target glossary from authoritative definitions.
3. Profile the first legitimate dataset or explicitly record that none is yet available.
4. Implement schema validation and provenance.
5. Build a reproducible baseline only once eligible outcome labels exist.

**P1 — First vertical slice**
- Manual-entry API contract and form.
- Domain validation.
- Explicit unsupported/no-model response.
- Result layout ready for versioned passenger/group probabilities.

**P2 — Model evaluation**
- Historical baseline.
- Chronological split.
- Proper scoring rules and calibration.
- Group-level evaluation and ablation study.

**P3 — Live tracking**
- Provider and permissions review.
- Secure identifier handling.
- Observation retention and deletion.
- Status updates and model refresh.

## Not doing yet

- Advertising an accuracy percentage.
- Publishing synthetic predictions as evidence.
- Automatic collection from restricted railway systems.
- Making news headlines directly manipulate predicted probabilities.
- Building billing, user subscriptions or complex notifications before the core model is credible.

## Next review

Update this canvas after the first dataset audit and again when a first working end-to-end prediction path exists. Record changes to priority in the development log and material architectural changes in ADRs.

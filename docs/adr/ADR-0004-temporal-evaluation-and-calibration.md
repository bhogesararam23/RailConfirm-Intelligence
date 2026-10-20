# ADR-0004: Temporal evaluation and probability calibration

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** docs/research/EVALUATION_PROTOCOL.md

## Context

Reservation status changes over time. Randomly splitting individual status snapshots can place observations from the same booking in both training and testing, and post-prediction information can leak into earlier forecasts. Classification accuracy alone does not establish that a probability is reliable.

## Decision

Use chronological development, validation and locked-test partitions, keeping snapshots from the same booking/journey in one partition. Reconstruct features as of the historical prediction timestamp. Fit calibration only on development/validation data and use proper scoring rules and calibration analysis as primary metrics.

## Alternatives considered

- **Random snapshot-level split:** Rejected because it risks leakage and does not mimic deployment into the future.
- **Accuracy-only evaluation:** Rejected because it does not evaluate the quality of probability estimates.
- **Tune against the final test set:** Rejected because it invalidates the holdout.

## Consequences

- Evaluation code must reconstruct as-of-time features and group splits.
- The dataset must preserve timestamps and stable de-identified grouping.
- Final numbers may be less flattering than random-split results, but they are more credible.
- Results must include sample counts, uncertainty and subgroup limitations.

## Validation

Add leakage tests, verify partition grouping, and document exact split dates before locked-test evaluation. Compare baseline and candidate models using predefined metrics and report results with uncertainty intervals.

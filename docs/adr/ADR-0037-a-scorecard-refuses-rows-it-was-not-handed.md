# ADR-0037: A scorecard refuses rows it was not handed

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainers
- **Related:** ADR-0011 (target-event scoring), ADR-0017 (calibration fitted on validation), ADR-0021 (paired comparison), ADR-0035 (a figure is scored against the event its name gives), ADR-0036 (a report's definition and its figure name the same event)

## Context

`score_partition(..., pre_scored=…)` was added for the paired comparison (ADR-0021). The
comparison has to pair two models row by row, so it walks each partition with each model
once and then prints the aggregates from the rows it already has. Scoring the frame a
second time would let the published aggregates and the paired counts drift apart while both
looked right — the reason the parameter exists.

The card's labels, though, come from the call's own arguments:

- `target` selects the event whose Brier score is published, and `TARGET_EVENTS[target]`
  decides which classes that event covers;
- `calibration` decides the published `calibration_applied` flag;
- `scored_rows.rows_total` is the denominator of `coverage`.

The rows carry the arithmetic that was actually performed: each `ScoredRow` holds
`event_predicted` and `event_observed` computed against the target the walk was given, and a
calibrated hypothesis if a correction was applied while walking. Nothing compared the two
descriptions. Three mismatches were therefore publishable from an exported function:

1. **Another event.** Rows walked for `final_chart_cnf` printed on a card asking for
   `final_chart_cnf_or_rac`: the confirmed event's Brier appears under the merged event's
   name, and the report's own `target_event_classes` names CNF and RAC while the numbers
   counted CNF alone. This is ADR-0035's defect (one figure published under two names) and
   ADR-0036's defect (a label describing a different question), one layer below both.
2. **A correction the scores never received.** Rows walked uncalibrated printed on a card
   given a `CalibrationSpec`: `calibration_applied: true` beside numbers that were never
   corrected. The flag was read from the argument rather than from the rows, so a report
   could state a correction it did not contain.
3. **Another partition.** Rows from a one-row partition printed on a three-row frame:
   `coverage = scored / rows_total` divides one partition's scores by another's row count,
   and the card credits the model with rows it was never asked about.

No caller in this repository passes such a pair today: `compare.run_model_comparison`
walks with `chosen`, the model's own `calibration`, and the frame it then hands over, so
every published number is unaffected and no report changes. The defect is that the
invariant existed only in the caller's discipline, on a public function whose whole purpose
is to let a caller supply rows from somewhere else.

## Decision

1. **`RowScores` records what the walk was.** Two required fields — `target` and
   `calibrated` — are set by `score_rows` and describe the event and the arithmetic its
   rows were produced under. `score_rows` is the only construction site.
2. **`score_partition` compares the rows to the call.** When `pre_scored` is supplied,
   `_require_rows_match` refuses a target mismatch, a calibration mismatch and a row-count
   mismatch, each naming both sides. The refusal happens before any metric is computed.
3. **A matching pair is not merely tolerated, it is identical.** A regression test asserts
   that the reused-rows card equals the single-walk card key for key, so the shortcut can
   never become a different scorecard quietly.
4. **The flag now describes the arithmetic.** `calibration_applied` is published only when
   the rows it describes were walked with a correction, which the guard enforces.

## Alternatives considered

- **Remove `pre_scored` and score the frame twice.** Rejected: that is the drift the
  parameter was introduced to prevent, and ADR-0021's paired counts would once again be
  computed from a different walk than the aggregates beside them.
- **Infer calibration from the numbers.** Rejected: a slope of 1 with intercept 0 is a
  no-op, so an "uncorrected" and a "corrected" hypothesis can be identical. The fact has to
  be recorded, not deduced.
- **Accept the mismatch and relabel the card from the rows.** Rejected: the caller's target
  also selects `TARGET_EVENTS`, so relabelling would silently change the question the card
  answers. A refusal names the two sides; a repair would invent a third.
- **Check only the event figures and leave the row count alone.** Rejected: coverage is
  part of the scorecard's claim, and the comparison's coverage condition (ADR-0021) reads
  it. A denominator from another partition is a fabricated coverage.

## Consequences

- `RowScores` gained two required fields. Nothing else in the codebase constructs it, so no
  caller changed; the comparison, calibration, decay and origins paths are untouched.
- The guard runs only when `pre_scored` is supplied, so the ordinary path is unchanged in
  behaviour and in cost.
- A future harness that wants to score rows from another partition — a legitimate goal —
  must build a new `RowScores` for that frame rather than reusing one, which is the check
  this ADR wanted in the first place.

## Validation

- `tests/training/test_metrics.py` — rows walked for one target are refused by a card
  asking for the other; rows walked without a correction are refused by a card declaring
  one; rows from another partition are refused on the row count; and a matching pair
  produces a card identical to the single-walk card, with `calibration_applied` true.
- `tests/training` and `tests/api` together: 778 passed after the change, with every
  existing scorecard, comparison and calibration figure unchanged.
- Full suite at the time of the change: 1092 backend tests, 118 frontend tests, Ruff, mypy
  (44 source files), the frontend type check, lint, production build and the
  repository-hygiene gate all green.

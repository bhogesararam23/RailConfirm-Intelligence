# ADR-0030: A decay readout dates its own ends and states the two spans

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0018 (frozen-artifact decay across successive horizons),
  ADR-0028 (both aggregations published), ADR-0029 (an unmeasured period is `unknown`),
  `backend/railconfirm/training/decay.py`, `backend/railconfirm/training/report.py`

## Context

The frozen-decay run judges one artifact on successive future windows (ADR-0018). It
publishes `first_event_brier`, `last_event_brier` and their difference, which is the whole
readout: a table's target-event Brier in the window nearest the cutoff against the same
figure in the furthest one.

Those four numbers were derived from `FrozenDecayResult._values("event_brier")`, which skips
`None`. A horizon on which every row abstained produces a scorecard with no event Brier —
exactly the case ADR-0029 established as a legitimate outcome, not a failure. The two values
that came back were therefore the first and last *scored* horizons, while every sentence
around them called them the first and last *windows*:

```
Across 2 scored horizons the target event Brier ran from 0.240000 in the window nearest the
cutoff to 0.245000 in the furthest, a drift of +0.005000.
```

On a three-horizon run whose first window was silent, that sentence describes a window that
produced no reading at all, and it moves the starting point of the comparison forward by one
horizon without saying so. The metric definition carried the same claim in the other
direction — "Last horizon event Brier minus the first horizon's" — so a reader checking the
number against its definition would have found them in agreement and both wrong.

Two further problems were in the same block.

- **The coverage difference spans a different set of horizons than the event difference.**
  `coverage` is defined on every horizon (a fully abstaining horizon reports `0.0`), so
  `coverage_drift` always spans horizon 0 to the final horizon, while `event_brier_drift` may
  skip horizons at either end. Nothing said so. A reader comparing the two movements had no
  way to know they were measured over different windows, and the coupling is unavoidable:
  the alternative — dropping coverage from silent horizons — would hide the one number that
  explains why the horizon is missing from the other series.
- **One scored horizon was reported as a decay curve.** With two horizons, one silent, the
  conclusion printed `ran from X in the window nearest the cutoff to X in the furthest, a
  drift of +0.000000`. A zero difference between one number and itself is not a finding, and
  `MIN_HORIZONS = 2` is enforced precisely because a trend through one point is not a trend.

## Decision

1. **The result publishes which horizons it measured.** `scored_horizon_indices`,
   `first_scored_horizon` and `last_scored_horizon` join `FrozenDecayResult`, and both
   indices enter `summary`. This is a fact about the run, not a rendering choice: a reader
   who only has the JSON must be able to tell that the drift starts at horizon 1.

2. **The conclusion names its own endpoints.** The windows are described as "the window
   nearest the cutoff" and "in the furthest" only when they are those windows; otherwise the
   sentence says "at horizon 1, not the window nearest the cutoff". The caveat that a silent
   horizon was skipped is appended whenever one was, so an omission is stated rather than
   inferred from arithmetic.

3. **One scored horizon is a measurement, not a curve.** When exactly one horizon produced an
   event score, the conclusion reports that score, says one future window is a single
   measurement, and states that no drift can be read from it. No difference is printed.

4. **The definitions state both spans.** `event_brier_drift` is "the last horizon that
   produced a score minus the first that did, in horizon order"; `coverage_drift` says
   coverage exists on every horizon and therefore spans the whole walk. The asymmetry between
   the two is published instead of left for the reader to discover.

5. **The report moves to `1.1.0`.** `DECAY_REPORT_SCHEMA_VERSION` was `1.0.0`; the summary
   gains two keys and two definitions change wording. No key was renamed and no value was
   reinterpreted, so this is the same additive-minor rule ADR-0028 and ADR-0029 applied. A
   `1.0.0` reader of an old report is unaffected; a `1.0.0` reader of a new report is
   under-informed, which is what the version is for.

6. **Nothing about the arithmetic changes.** The drift is still the difference of two measured
   means, still an ordering rather than a tested trend, and still not the headline. This ADR
   only makes the report say which two means it subtracted.

## Alternatives considered

- **Keep the wording and document the skip in prose only.** Rejected: the JSON would still
  present `first_event_brier` beside a `first_coverage` computed on a different horizon with
  nothing in the payload to distinguish them, and the one place a downstream reader looks is
  the payload.
- **Publish coverage as `None` on a horizon that abstained everywhere.** Rejected: coverage is
  the share of rows the estimator answered, and on such a horizon that share is exactly zero
  — a measured value, not a missing one. Erasing it would remove the evidence for why the
  event series is shorter.
- **Treat a silent horizon as a failed forecast and score it as 0.25.** Rejected: ADR-0009 and
  ADR-0018 both hold that an abstention is not an error. Scoring it would mix a coverage
  decision into an accuracy metric and make the frozen table look worse for abstaining
  honestly.
- **Refuse the run when any horizon is silent.** Rejected: a thin horizon is a normal outcome
  of a fixed cohort table and is itself informative. Refusing would bias the published runs
  toward periods the table happens to reach.
- **Extend the run until two horizons score.** Rejected: the windows come from the plan and
  the data, and letting the report choose its own sample to obtain a readable drift is the
  fault ADR-0028 rejected for aggregation.
- **Bump the decay report to `2.0.0`.** Rejected: additive and wording-only changes; a major
  bump would mark old reports as suspect when nothing in their payload became wrong.

## Consequences

- Every published drift is dated. `first_scored_horizon`/`last_scored_horizon` are the
  authority, and the conclusion is checked against them by test rather than by eye.
- The terminal summary line prints `h{first} … -> h{last} …`, so a run whose early horizon was
  silent is visible at the console without opening the JSON.
- A one-scored-horizon run is now a coverage statement with one Brier attached, which is what
  the data supports. It no longer reports a zero drift that reads as stability.
- The limitations list says drift is the difference of first and last *scored* horizon means
  and notes that coverage spans every horizon, so the prose and the metric definitions agree.
- This remains a report-only change. No score, cohort, threshold or artifact is affected, and
  the numbers are unaffected on any run where every horizon scored — which is every run the
  existing fixtures produce.

## Validation

`backend/tests/training/test_decay.py` gained two tests and extended two. A new
`without_a_score(card)` helper turns a window's scorecard into a fully abstaining one and
`mute(result, indices)` applies it to named horizons, so a silent horizon can be constructed
without touching the fixtures' data. `test_the_drift_says_which_horizons_it_measured` mutes
horizon 0 and asserts the conclusion says horizon 1 is not the window nearest the cutoff, that
it states the silent horizon, that the caveat about the two ends being the ones measured is
present, and that the summary line prints `h1`. `test_a_single_scored_horizon_is_not_reported_as_a_decay_curve`
mutes every horizon but one and asserts the single-measurement wording and the absence of any
"drift of" clause. The existing drift test now also asserts the published indices, and the
nothing-scored test asserts `first_scored_horizon is None` and an empty index tuple. The
backend suite (1063 tests), Ruff, mypy (44 source files) and the repository hygiene script
were run before this change was committed.

# ADR-0028: A rolling-origin run publishes both aggregations, and says when they disagree

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0014 (rolling-origin evaluation), ADR-0018 (frozen decay), ADR-0021
  (paired comparison on the locked period), `backend/railconfirm/training/origins.py`,
  `backend/railconfirm/training/report.py`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

The rolling-origin aggregate published one number per score: the unweighted mean of the
per-origin Brier scores. Each origin's score is itself a mean over the rows that origin
scored, so the mean of means gives a horizon with two rows exactly the weight of a horizon
with two thousand. On a plan whose horizons differ in size — which is the normal case, since
the last horizon in a file is often a partial date block — that figure answers "how did the
fitting procedure do per cutoff" while reading as if it answered "what did a passenger get
per prediction". Those are different questions and they can reach opposite verdicts against
the same prevalence baseline.

The report already refused to hide this in one place: an origin that abstained on every row
is counted separately from an origin that lost, so a coverage failure is never averaged in
as a bad score. The same distinction was missing one level up. A run in which nine small
horizons scored well and one large horizon scored badly reports a mean that beats the base
rate, and the pooled error over the rows actually served says it does not.

## Decision

1. **Both figures are computed and published.** `RollingOriginResult` gains `pooled_brier`,
   `pooled_baseline_brier`, `pooled_event_brier` and `pooled_event_baseline_brier`, each
   weighted by the rows the origin scored. The mean over origins is kept unchanged, because
   it is the number that describes the fitting procedure across cutoffs. All four scores are
   means over the same scored rows inside a scorecard, so one row count weights each of them
   consistently; origins that scored nothing contribute to neither figure.

2. **The report states which way each one points.** `distribution_agreement` and
   `event_agreement` compare the two aggregations against their own baselines and return
   `agree`, `disagree` or `undetermined`. Agreement is not inferred from the sizes being
   close: both must land on the same side of their own baseline. A run with nothing scored
   is `undetermined`, not agreement, because two absent numbers agree about nothing.

3. **Disagreement is a conclusion, not a footnote.** When they disagree the report says so,
   prints both pairs of numbers, and states that which figure a reader quotes decides the
   verdict — so neither is published as *the* result. When they agree it names the pooled
   figure as the one a statement about served predictions should rest on, and says it points
   the same way as the mean over origins.

4. **Uneven horizons are a stated limitation.** `scored_rows_spread` publishes the smallest
   and largest scored-row count among origins that scored at all. When the two differ, the
   report adds a limitation saying the two figures are not interchangeable, and the terminal
   output prints the range. When every origin scored the same number of rows the two figures
   coincide by construction, and no warning is printed — a warning that fires on every
   balanced run is a warning nobody reads.

5. **The schema version moves to 1.1.0.** `ORIGIN_REPORT_SCHEMA_VERSION` becomes `1.1.0`
   because the aggregate block gained keys. No existing key changes meaning, so a 1.0.0
   reader is under-informed rather than misled — which is why this is a minor bump and not a
   reinterpretation of stored reports.

6. **Both statistics are defined in the report itself.** `ORIGIN_AGGREGATE_DEFINITIONS`
   joins `METRIC_DEFINITIONS` in the origin report's `metric_definitions` block, and stays
   out of the single-cutoff and decay reports, which publish no aggregate over origins and
   would only be defining statistics they never show.

## Alternatives considered

- **Publish only the pooled figure.** Rejected: it answers the serving question but hides
  instability across cutoffs, because a single large horizon dominates it. The instability
  is the point of running more than one origin (ADR-0014).
- **Publish only the mean over origins.** Rejected: it is the current behaviour and the
  defect this ADR records. It can report a distribution that beats the base rate on rows
  that, taken together, lost to it.
- **Silently pick whichever figure is worse** on the grounds that a pessimistic headline is
  the safe one. Rejected: it makes the published number depend on a rule the reader cannot
  see, and it would misreport the per-cutoff behaviour when the pooled figure is the one
  that lost.
- **Weight by rows outstanding rather than rows scored.** Rejected: it would let abstention
  change the weights, so a model could improve its pooled score by refusing the rows it
  finds hard while the denominator stayed fixed.
- **Test the difference between the two aggregations for significance.** Rejected: the
  origins overlap by construction, so the two figures are dependent summaries of the same
  rows. Publishing both, with the spread, describes the instability; a test statistic would
  claim an independence the plan does not have.
- **Bump the schema version to 2.0.0.** Rejected: no key was renamed or reinterpreted.
  Marking an additive change as breaking would force every reader to treat old reports as
  suspect for no reason.

## Consequences

- A reader of an origin report can no longer quote a favorable aggregate without also being
  shown whether the rows behind it supported that. On synthetic fixtures the two agree, as
  they must when horizons are the same size.
- The report is slightly larger: four pooled figures, a spread, two verdict strings and the
  two definition entries. That cost is paid once per run and is not per-row.
- `_pooled` reuses the same attribute names as `_mean`, so a future score added to
  `Scorecard` needs no change here to be pooled; it needs only a property and a definition,
  and the definition test will fail until it has one.
- The pooled figure inherits the rounding of the per-origin scorecards (six decimal
  places), so it is a weighted mean of rounded means. The difference is far below the
  precision at which any of these numbers mean anything, but it is why the pooled figure is
  not reconstructed from raw rows.
- Neither aggregation is evidence about railway behaviour. Both describe synthetic fixtures
  until an approved dataset exists, and the report keeps stating that in its limitations.

## Validation

`backend/tests/training/test_origins.py` gained seven tests: weighted pooling against
hand-computed figures, an origin that scored nothing contributing to neither average, a
constructed plan where the mean beats the baseline and the pooled figure loses to it and
both disagreements are named in the conclusions, the agreement branch that names the pooled
figure, the `undetermined` case with no scored origins, the coincidence of the two figures
on the balanced synthetic plan, and the presence of both definitions in
`metric_definitions`. The backend suite (1050 tests), Ruff and mypy were run before the
change was committed.

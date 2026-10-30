# ADR-0031: Reliability bands partition the scored rows instead of overlapping at their edges

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0014 (metrics reported per cutoff), ADR-0019 (subgroup calibration and the
  row floor on a claim), `backend/railconfirm/training/metrics.py`,
  `backend/railconfirm/training/report.py`

## Context

Every scorecard publishes reliability bands: for each outcome class, and for the target's
event, the scored predictions are grouped into ten probability bands and each band reports a
row count, the mean predicted probability and the observed frequency. The bands exist to show
whether a cohort table that says "about 30%" is right about 30% of the time.

`_bands` selected a band's members with

```python
if lower <= predicted <= upper or (index == bins - 1 and predicted == 1.0)
```

Both edges inclusive. With ten bins the boundaries are `0.1, 0.2, … 0.9`, and a prediction
sitting exactly on one satisfied the band below and the band above. That is not a corner case
here: the estimator is an add-one-smoothed frequency table over five classes, so its
probabilities are `(count + 1) / (n + 5)`, and round values are ordinary — one confirmation in
a fifteen-row cohort is `2/20 = 0.1` exactly, two in fifteen is `3/20 = 0.15`, three in
fifteen is `4/20 = 0.2`. Reproduced against a fitted fixture: one scored row predicted at
`p_cnf = 0.1` was published as

```
CNF   0.0–0.1   count 1   mean 0.1
CNF   0.1–0.2   count 1   mean 0.1
```

one row in two bands, `sum(count) == 2` for `scored_rows == 1`, and the same overlap in the
event bands. Every reading taken from the table inherits it: the row counts overstate the
sample, and each band's `observed_frequency` averages a row that the neighbouring band also
averages, so a thin band can look as if it were built from evidence it does not have. That
matters more than the arithmetic implies, because a band's count is the only thing a reader
has to judge whether the band's observed frequency means anything.

The existing test `test_reliability_bands_carry_counts` did assert
`sum(band.count for band in bands) == card.scored_rows`, but its fixture predicts `91/105`,
which is not on a boundary, so the assertion passed and the defect was invisible. It was found
by reading the membership condition, then reproduced with a cohort chosen to make the
probability land exactly on an edge.

## Decision

1. **A band is half-open, `[lower, upper)`.** The last band additionally includes `1.0`, so
   a certain prediction is still published somewhere. A prediction on a boundary belongs to
   the band it opens, and to that band only.

2. **The counts must sum to the rows scored.** That is the invariant the bands are for: they
   partition the scored rows. It is now asserted by test at the scorecard level (a cohort
   whose probability is exactly `0.1`) and at the helper level (pairs at `0.0`, `0.5` and
   `1.0` over two bins).

3. **The report states the rule where the number is defined.** `reliability` and
   `event_reliability` in `METRIC_DEFINITIONS` now say the bands are half-open, that the
   counts sum to the rows scored, and that a boundary prediction is counted once. A reader
   adding up the counts should not have to read the implementation to know what the total
   should be.

4. **No schema version changes.** No key was added, renamed or reinterpreted; the payload
   shape is identical and the values were simply wrong for boundary rows. A version number
   describes the shape of a report, and inventing a bump here would imply that a `1.0.0`
   reader must branch on it. Published reports that contain over-counted bands are wrong for
   the rows that sat on an edge, and the changelog says so.

## Alternatives considered

- **Keep both edges inclusive and publish a note that some rows appear twice.** Rejected: a
  count that does not mean "this many rows" is not a count a reader can use, and the
  alternative reading — "weighted presence" — is not what any consumer would assume.
- **Drop the boundary row from the upper band instead, keeping the last band's inclusive
  edge.** That is the same rule expressed the other way; it was rejected only because the
  half-open convention is the one `range(bins)` and the band labels already imply.
- **Widen the bins so boundaries fall on values the estimator cannot produce.** Rejected: the
  smoothed distribution can produce any `(count + 1) / (n + 5)`, so no bin width removes the
  problem, and the bins are meant to be readable round numbers.
- **Return `None` for a band whose observed frequency is ambiguous.** Rejected: nothing is
  ambiguous once each row has one band. The frequencies are all it ever claimed to be.

## Consequences

- Every reliability table now partitions its rows. `sum(count) == scored_rows` holds for each
  outcome class and for the event, on any input, not just on the fixtures.
- Band contents shift by one band for predictions that sit exactly on a boundary: a `0.1`
  prediction that used to appear in both `[0.0, 0.1]` and `[0.1, 0.2]` now appears only in
  `[0.1, 0.2]`. On a real run this changes individual band means slightly; it changes no
  score, no Brier value, no calibration fit and no artifact.
- The published numbers on the synthetic fixtures are unchanged, because their predictions do
  not sit on a boundary — which is exactly why the defect survived the suite and why the
  regression test had to construct the case deliberately.
- Nothing here is evidence about railway behaviour. The fixture is synthetic and the bands
  describe a smoothed table.

## Validation

`backend/tests/training/test_metrics.py` gained two tests and the `estimator` helper gained an
optional `cohorts` argument so a table can be built with an exact boundary probability.
`test_a_prediction_on_a_band_boundary_is_counted_once` scores one row against a cohort whose
CNF probability is exactly `0.1` and asserts the CNF table is a single `(0.1, 0.2)` band with
one row, that its mean is `0.1`, and that the event bands also sum to `scored_rows`.
`test_bands_cover_both_endpoints_and_each_row_once` passes `0.0`, `0.5` and `1.0` through two
bins and asserts the first band holds `0.0`, the last holds `1.0` and the total is three. The
defect was reproduced with a standalone probe before the fix (its output is quoted above) and
the backend suite — 1065 tests — Ruff, mypy and the repository hygiene script were run after
it.

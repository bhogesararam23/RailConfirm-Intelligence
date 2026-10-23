# ADR-0018: Frozen-artifact decay — one table scored on each successive horizon

- **Status:** Accepted
- **Date:** 2026-10-24
- **Decision owner:** Project maintainer
- **Related:** ADR-0004 (chronological evaluation), ADR-0011 (target-event scoring and the
  prevalence baseline), ADR-0013 (the as-of cohort rule an artifact must declare),
  ADR-0014 (rolling-origin evaluation, which measures the *other* question), ADR-0016
  (group scoring reused unchanged), ADR-0017 (the calibration layer a frozen artifact
  carries with it), `backend/railconfirm/data/preprocessing.py`,
  `backend/railconfirm/training/decay.py`, `backend/railconfirm/training/report.py`,
  `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0014 refits the cohort table at every cutoff and scores the horizon after it. That is
the right way to ask "does this fitting procedure hold up over time", and it is the wrong
way to ask the question a promoted artifact actually faces in service: **the table is fixed
and the calendar moves away from the period it was counted from.** A refit erases exactly
the thing decay is about — a stale cell for a cohort nobody saw in April.

Both ADR-0014 and ADR-0017 recorded this as the missing evaluation, and until now the only
answer the repository could give about a frozen artifact was one holdout period. One
holdout is not a trend: it is the number a reader will mistake for one.

The synthetic fixtures again show why the shape of the question matters. A single-cutoff
run on the balanced fixture reports test event Brier 0.239487 against a 0.24 base rate — a
win by 0.0005. Scored as three successive two-date horizons against the same frozen table
and the same frozen baseline, the same estimator runs 0.243482, 0.240300, 0.239411 and beats
the base rate in only one of the three. Nothing about the arithmetic changed; the single
number simply kept the ordering secret.

## Decision

**1. The cutoff comes from the artifact, never from the caller.**

`run_frozen_decay()` reads `metadata.trained_to` and treats every date at or before it as
frozen. An artifact that does not declare its fitted period is refused outright: without a
cutoff there is no line between "the data this table was counted from" and "evidence about
it", and a caller-supplied cutoff would let the fitted period be scored as if it were
future data. The refusal text states that, rather than defaulting to some fraction of the
file.

**2. Two horizons minimum, and no windows at all when the calendar cannot give them.**

`frozen_horizon_windows()` plans whole-date horizons after the cutoff, advancing by
`step_dates >= horizon_dates` so no outcome is scored twice, and returns **no** windows with
the reasons when fewer than `MIN_HORIZONS = 2` fit. Same rule as ADR-0014 and
`chronological_split`: an inability to evaluate must produce nothing to evaluate on,
because a one-point "curve" reads as evidence of stability.

**3. The prevalence baseline is frozen with the table.**

One reference distribution is computed from the fittable rows the file holds up to the
cutoff, and every horizon is judged against it. Recomputing the baseline per horizon would
move the yardstick toward the answer being measured — a population that drifts toward the
model's own predictions would look like a model holding steady. The report states where the
baseline came from and that it is this file's reading of the fitted population, not the
original snapshot.

**4. The estimator under test is the estimator that serves.**

`frozen_decay_estimator()` builds the baseline from the artifact's own cohorts,
`min_sample_threshold` and `laplace_alpha` through `build_estimator()` — the same
`normalize_frequency_table` gate the registry loads through — and passes the artifact's
calibration block into `score_partition()`, so a calibrated artifact's correction is
applied to every horizon by the same `apply_calibration` the engine uses. Provenance is
marked `evaluation_only`, which is how offline scoring already lets a synthetic table be
exercised; it is not a field of the artifact, so nothing measured here can become a served
number.

**5. The served contract is re-checked before scoring.**

An artifact declaring a different `cohort_semantics` or a different `features_used` than
this build answers requests with is refused, even though `load_artifact()` already refuses
the same mismatch. The decay module can be handed a constructed `LoadedArtifact`, and a
decay curve for an estimator that is not the one in service is a number about nothing.

**6. A booking that spans the cutoff invalidates the run.**

If any `booking_group_id` appears both at or before the cutoff and inside a horizon, that
horizon's outcome is already inside the table being judged. The planner refuses the whole
plan rather than dropping the offending rows, because silently removing evidence from the
side being tested is how a favorable result gets produced.

**7. Drift is reported as an ordering, not as a mean.**

The result publishes first-horizon and last-horizon values, their difference, the spread
across horizons, and two separate counts: horizons that produced a score at all, and
horizons that beat the frozen baseline. Coverage drift is reported beside accuracy drift
and labelled a reach fact — a frozen table abstaining on later rows is not the same finding
as one predicting them badly. Conclusions are derived from those measured values; a run
where nothing was scored concludes that nothing was scored and uses no word that could read
as a positive result.

**8. `decay` is a third question, named as one.**

`python -m railconfirm.training decay DATASET MANIFEST --artifact … [--horizon-dates 2]
[--step-dates 2] [--gap-days N] [--min-scored-rows N] [--report … --generated-on D]`
writes its own report shape (`DECAY_REPORT_SCHEMA_VERSION`) and prints
`one frozen artifact, scored on each successive horizon` as its method line, so the numbers
cannot be pasted into a rolling-origin claim by accident. The target is checked against the
artifact's declared target exactly as `evaluate` does. Every published scorecard field keeps
a definition, plus three new ones (`prevalence`, `event_brier_drift`, `coverage_drift`).
Output is ASCII-arrowed and cp1252-encodable: a finished run must not die on a Windows
console.

## Alternatives considered

- **Reuse `rolling_origin_windows` with a large minimum training block.** Rejected: it
  refits at every cutoff by construction, which is the exact behaviour this question has to
  switch off. Two questions need two planners, each stating its own method.
- **Let `--cutoff` be a CLI flag.** Rejected: see Decision 1. A flag would make leakage of
  the fitted period into "decay evidence" a matter of typing.
- **Recompute the prevalence baseline per horizon.** Rejected: the baseline would track the
  population being predicted, and the comparison would stop being against the fitted
  population (ADR-0011's rule that the baseline comes from training data).
- **Require the file's SHA-256 to equal the artifact's recorded `dataset_sha256`.**
  Rejected as too strict for the real use case: decay is measured on a *later* export of the
  same source, so the hash legitimately differs. The consequence — that the reference
  distribution is this file's reading of the fitted window — is recorded as a report
  limitation instead.
- **Report the mean Brier across horizons as the headline.** Rejected: the ordering is the
  finding. A mean of 0.241191 over the three windows above would hide both the range and the
  1-of-3 base-rate result.
- **Score only the furthest horizon as "the current period".** Rejected: with one window
  there is no decay, only a holdout, and it discards the shape that makes the measurement
  worth having.

## Consequences

- ADR-0014's and ADR-0017's "not implemented" line is now a command. What remains genuinely
  unmeasured is subgroup calibration and any railway number: `decay` produces its first
  real decay curve the day an approved dataset exists.
- A calibrated artifact can now be asked the question ADR-0017 left open — whether one slope
  fitted on one window holds later — because the correction travels with the table into
  every horizon. On the fixture the answer is verifiable rather than assumed: the calibrated
  artifact's horizons reproduce the `fit --calibrate` validation and locked-test numbers
  exactly (0.239898 and 0.239487), which is parity, not performance.
- Reports gain a third reproducible shape. `evaluation_method` is required reading in each:
  three shapes with similar field names and different questions is exactly how a refit
  result gets quoted as a decay result.
- `preprocessing` now exports `frozen_horizon_windows`, `FrozenHorizonPlan`,
  `HorizonWindow` and `MIN_HORIZONS`; nothing about `chronological_split` or
  `rolling_origin_windows` changed, so existing artifacts and reports are unaffected.
- Promotion gates are untouched: `decay` reads whatever artifact it is given, including an
  unservable synthetic or candidate one, and only reports. It cannot activate anything.

## Validation

- `backend/tests/data/test_frozen_horizons.py` — 39 tests: the frozen block's boundaries,
  successive non-overlapping horizons, step-wider-than-horizon leaving dates unscored rather
  than double-counted, no horizon ever scoring a fitted date, helper columns and indices
  stripped, then the refusals — one horizon only producing no windows with the reason
  stated, a cutoff after the file's last date, a file starting after the fitted period, the
  gap rule at the cutoff, a horizon below `min_scored_rows`, a booking spanning the cutoff,
  non-ISO cutoffs, and parameter validation — plus the `describe()`/`to_dict()` shapes a
  report publishes.
- `backend/tests/training/test_decay.py` — 35 tests: every horizon scored by the same
  unchanged cohort count, the target coming from the artifact, the reference prevalence
  equal to an independent recomputation from the frozen block, relabelling the future
  **not** moving the baseline, abstentions counted rather than scored, the estimator built
  with the artifact's own threshold and smoothing, a calibrated artifact corrected on every
  horizon and an uncalibrated one reporting none, group cards per horizon, drift computed
  against the frozen reference with first/last/spread agreeing with the scorecards,
  horizons-with-scores separate from horizons that lost, and the refusal paths; then the
  report: method line, baseline-provenance and non-independence limitations, every published
  metric defined, conclusions quoting the measured drift, a no-score run concluding nothing
  positive, byte-identical repeats, and six CLI cases including a refusal exit code and a
  cp1252 encodability guard on everything printed.
- Live runs on labelled synthetic fixtures (commands and full output in
  `docs/DEVELOPMENT_LOG.md`): `decay … decay_v1.json --horizon-dates 2 --step-dates 2`
  scored three horizons from a table frozen at 2026-04-06 and reported event Brier
  `0.243482 → 0.240300 → 0.239411` (drift `-0.004071`), beating the frozen base rate in
  1 of 3 horizons while the distribution lost in all three; the calibrated artifact, frozen
  at 2026-04-08, scored `0.239898 → 0.239487` with 2 of 2 horizons beating — the same two
  numbers `fit --calibrate` printed for its validation and locked-test partitions, which is
  the correction being applied identically rather than re-derived. A plan left with one
  horizon exited 1 with `at least 2` in the reason and wrote no report.
- No railway claim: every number above comes from rows that declare `is_synthetic`. Decay
  on real data waits on the same approved dataset everything else waits on.

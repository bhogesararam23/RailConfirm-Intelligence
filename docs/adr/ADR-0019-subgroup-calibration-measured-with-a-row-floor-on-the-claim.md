# ADR-0019: Subgroup calibration measured per segment, with a row floor on the claim

- **Status:** Accepted
- **Date:** 2026-10-24
- **Decision owner:** Project maintainer
- **Related:** ADR-0011 (segment reporting and the low-sample flag), ADR-0013 (the cohort key
  the served estimate comes from), ADR-0017 (the population-wide calibration layer whose
  residual this measures), ADR-0018 (decay horizons, which inherit the measurement),
  `backend/railconfirm/training/metrics.py`, `backend/railconfirm/training/report.py`,
  `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0017 fitted one slope for the whole population and recorded, honestly, that subgroup
calibration "is not measured". The evaluation protocol has required it since the start —
"calibration quality must also be examined by meaningful subgroups where sample sizes permit"
— and the product makes the same demand from the passenger's side: a served probability is
keyed by class, quota and as-of status, so the claim "these probabilities are calibrated" is a
claim about cohorts, not about the average over cohorts.

The failure mode is arithmetic rather than hypothetical. A single logistic correction moves
every row's log-odds by the same rule. Two cohorts whose true rates sit on opposite sides of
the population mean can end up closer to it on average while each one is still wrong — and the
headline event Brier, computed over all rows, shows nothing. Reliability bands do not catch it
either, because they pool the classes: they say "rows predicted in the 0.3–0.4 band confirmed
41% of the time" across every cohort at once.

So the honest statement before this change was "we do not know". The change is to know, and to
publish what is known with the count that backs it.

## Decision

**1. It is a scorecard field, not a new artifact layer.**

`segment_calibration()` groups the *scored* rows of a partition by each slice they already
belong to (`class_code`, `quota_code`, `asof_status`, `initial_status` — the same dimensions
`score_partition` segments by) and publishes, per slice: `rows`, `mean_predicted`,
`observed_rate`, and `gap`. The field appears on every `Scorecard`, so the fit report, the
rolling-origin report and each decay horizon carry it without new plumbing.

**2. The numbers are the ones a passenger was handed.**

`mean_predicted` is the mean of `event_predicted` — which is the target event's mass *after*
`apply_calibration` when the artifact carries a correction, because `score_rows` applies the
layer before anything is measured. Gaps computed beside the correction would describe a number
nobody is served.

**3. Sign convention stated once, in the definition.**

`gap = observed_rate - mean_predicted`. Positive means that cohort confirmed **more often than
it was told to** — the estimate under-confirms it. A report that printed only magnitudes would
lose the direction, which is the part a reader acts on.

**4. One row floor, shared with segment metrics.**

The floor is the `min_segment_rows` the scorecard already carries (default 25), not a second
constant that can drift out of agreement. Segments below it are still published, flagged
`low_sample`, and the report is not allowed to build a claim on them: a three-row cohort that
all confirmed is not a 33-point miscalibration, it is three rows.

**5. No per-segment correction is fitted.**

Each segment's gap is a *measurement*, not a proposal. The report states that a population-wide
slope applied to a cohort leaves residual error — which is what the gaps are — rather than
implying the correction holds cohort by cohort.

**6. Abstentions contribute nothing.**

A row the estimator refused has no probability, so it cannot be misaligned. It is counted in
`abstained_rows` and excluded from every segment, which keeps `sum(rows)` per dimension equal
to `scored_rows` — a check the tests assert, because a silent mismatch there would quietly
reweight the population toward the easy rows.

**7. When nothing clears the floor, the report says it cannot be claimed.**

`_segment_calibration_line()` names the widest gap among informative segments. If there are
none it says so plainly, in both partitions, instead of quoting a thin segment to fill the
line. A run of a real dataset will often land here for rare cohorts, and "cannot be claimed in
either direction" is the correct output, not a failure of the measurement.

## Alternatives considered

- **Fit a Platt slope per cohort.** Rejected: cohorts are counted in the tens, a slope fitted on
  them is noise, and a probability whose provenance depends on the passenger's class is not a
  model — it is a lookup table with a claim attached.
- **Rely on the existing reliability bands.** Rejected: they are pooled across cohorts by
  construction, which is exactly the averaging that hides offsetting segments.
- **Attach bootstrap intervals to each gap.** Deferred, not rejected: a defensible interval
  needs a stated resampling scheme and enough rows, and inventing one in the same change would
  put a false precision on numbers whose main job is to say "not yet". A point gap, a count and
  a flag can be read correctly; a fake confidence interval cannot.
- **Publish gaps for every segment regardless of size, unflagged.** Rejected: the flag exists
  because a small `n` is the dominant fact about most cohorts in a sparse table.
- **Put the measurement on the artifact.** Rejected: it belongs to a *scored partition*, not to
  a fitted table, and an artifact carrying its own subgroup verdict would freeze a conclusion
  drawn from whatever rows happened to be in that file.

## Consequences

- The sentence "subgroup calibration is not measured" is removed from the docs and replaced
  with what is measured, what the floor is, and what still cannot be claimed. ADR-0017's item 7
  is superseded in that respect; its fitted-on-validation decision is unchanged.
- The repository's own rule that every published scorecard number must have a definition caught
  the new field the moment it was added (`test_every_published_metric_is_defined_and_nothing_extra_is`),
  so the field ships with its definition or not at all.
- Nothing in the serving path changed: no new artifact field, no new abstention reason, no
  different probability. This is evaluation-side measurement only.
- Decay reports now show, per horizon, whether a cohort's gap widens with distance from the
  fitted period — the question ADR-0018 opened, answered with ADR-0017's correction in place.
- On sparse data the most likely honest output is "no segment holds 25 rows". That is a
  statement about the dataset's size, and it is one reason the intake minimum for distinct
  journey dates should rise before any promotion decision is made.

## Validation

- `backend/tests/training/test_segment_calibration.py` — 22 tests. The arithmetic case that
  motivates the whole thing: ten rows predicted 0.3 that all confirm plus ten predicted 0.7 that
  none do, where the population is exactly aligned at 0.5/0.5 while the two cohorts sit at
  +0.7 and -0.7. Then hand-checked segment means and rounding, the inclusive row floor,
  a single-row segment reporting its own extremes rather than hiding them, every slice dimension
  covered, order-independence and sorting, an empty scored set calibrating nothing, and
  integration through `score_partition`: one-cohort-per-scored-row accounting, abstained rows
  contributing to no segment, gaps measured on the corrected probability (a 30/70 cell smoothed
  to 31/105 moving to `sigmoid(2 · logit(31/105))` under the layer, with the gap widening
  accordingly), and the payload serialising as plain dicts. Finally the report wording: the
  widest informative segment named in the conclusions, a thin-partition run refusing to claim in
  either direction, the no-per-segment-correction limitation present whether or not a
  calibration exists, and a cp1252 encodability guard on every conclusion and limitation line.
- Live run on the labelled synthetic fixture (`fit --report`, exit 0): validation population
  event Brier 0.240085 against a 0.24 baseline, with `asof_status=WL` over 40 rows at
  predicted 0.388169 / observed 0.400000 (gap `+0.011831`, informative) alongside
  `class_code=SL` at 23 rows (`+0.005887`) and `class_code=3A` at 17 rows (`+0.019873`) both
  flagged `low_sample`. The conclusion printed
  `validation: the widest segment gap is +0.011831 in asof_status=WL over 40 rows …` and the
  limitation recorded that four segment results rest on fewer than 25 rows. The larger 3A gap is
  the one a reader would most want — and the floor is exactly why the report declines to build a
  claim on it.
- Gates: `pytest tests/ --cov-fail-under=90`, `ruff check railconfirm/ tests/`, `mypy`,
  `python scripts/check_repository_hygiene.py`, and the frontend suite — results recorded in
  `docs/DEVELOPMENT_LOG.md` for this session.
- No railway claim: the gaps above come from synthetic rows. What was built is the measurement
  and the wording discipline around it, not evidence about Indian Railways cohorts.

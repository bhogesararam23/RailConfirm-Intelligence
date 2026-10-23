# ADR-0014: Rolling-origin evaluation with per-cutoff refitting and a two-origin floor

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0004 (chronological evaluation), ADR-0011 (baseline fitting and
  target-event evaluation; this record takes up the rolling-origin task it deferred),
  ADR-0013 (the as-of cohort rule each origin refits under),
  `backend/railconfirm/data/preprocessing.py`, `backend/railconfirm/training/origins.py`,
  `docs/research/EVALUATION_PROTOCOL.md`

## Context

`chronological_split` gives one cutoff: train on the early dates, score the last stretch.
`docs/research/EVALUATION_PROTOCOL.md` said plainly that this "must be added before any
result is called temporally robust", and the reason is arithmetic rather than stylistic.
A single horizon is one draw from one period: it cannot show that a verdict depended on
when the file happened to end. The synthetic fixtures make the danger visible — the
current single-cutoff run reports a distribution Brier of 0.503704 against a 0.5 base
rate, and a reader who saw only that number would conclude the method loses. Scored
across nine cutoffs the same method loses at eight of them and the range is
0.503704–1.632000, because the fixture's label mix moves between periods. One cutoff
hid that completely.

Fitting the machinery before a real dataset exists is deliberate (this revises the
reasoning in ADR-0011, which postponed it for lack of data). When a dataset is approved,
the first run is the run most likely to be quoted. If the only available evaluation is
one cutoff, that is what will be reported, and nothing in the tool would have objected.
The refusal to report a single cutoff as a temporal result has to exist before the data
does.

## Decision

**1. Plan the origins from whole dates, and refuse when the calendar cannot support two.**

`rolling_origin_windows(frame)` walks an expanding training block forward: `min_train_dates`
dates to start, the next `horizon_dates` dates scored, the cutoff advancing by
`step_dates`. Dates, never rows, so a record cannot straddle a cutoff, and dates are
parsed strictly ISO like every other temporal boundary in the project.

A plan with fewer than `MIN_ORIGINS = 2` usable origins is **not eligible and returns no
windows**, with a reason naming the date count and the shortfall. The aggregate over one
origin is the single-cutoff number the command exists to replace, so it is refused rather
than averaged. `run_rolling_origins()` raises rather than scoring a partial plan.

**2. `step_dates >= horizon_dates` is required, and it buys the no-double-counting guarantee.**

Overlapping scored windows would put the same outcome in two origins and report one
evaluation twice. Because every earlier horizon sits inside every later training block, a
booking appearing in two scored windows must also straddle the later cutoff — so one rule
(crossing a cutoff) covers both failures, and the plan states it instead of adding a
second check that could never fire.

**3. Each origin refits, and each origin gets its own baseline.**

For every window: `fit_cohorts(window.train)` → cohort table and prevalence →
`build_estimator(...)` → `score_partition(window.scored, ...)`. Both come from the same
functions the single-cutoff path uses, so the two cannot drift apart.

- The prevalence baseline always comes from **that origin's training window**, never the
  scored one. Consequence worth stating: the baselines differ between origins by
  construction, so "the mean baseline" is a description of the set, not a constant.
- Refitting means the run measures the **fitting procedure across time**, not one
  promoted artifact's decay. The report prints that as its `evaluation_method` line
  (`refit-per-origin, score-the-next-horizon`) so nobody reads it as artifact monitoring.
  Scoring a frozen artifact against successive horizons is a different question and will
  need its own declaration.

**4. The aggregate counts scoring origins and silent origins separately.**

An origin whose every row abstained has no score, which is not a score that lost. The
result exposes `origins_with_scores` and `origins_with_event_scores` next to
`origins_beating_baseline`, and conclusions are written against the origins that actually
produced numbers: "1 of 2 scoring origins beat their prevalence baseline", or, when
nothing scored, "No origin measured anything: all N horizon rows abstained, so this run is
evidence about coverage, not about accuracy."

**5. Instability is the finding, and it is never smoothed into a mean.**

Conclusions say whether the verdict held at every cutoff, at none, or at some — and quote
the range: "Brier ranged from 0.396694 to 1.135802 across origins; the spread is a
description of instability, not a tested difference." Coverage range gets the same
treatment. Fixed limitations: overlapping training windows mean the origins are **not
independent evaluations**, no multiplicity correction is applied, per-origin baselines
differ, and no calibration was fitted.

**6. Reports stay byte-reproducible.**

`origins --report` requires `--generated-on` like the other report paths, publishes the
plan (boundaries, row counts, gap), one block per origin with its own scorecard, the
aggregate and the definitions, and two identical runs produce identical bytes.

## Alternatives considered

- **Freeze one fitted table and score successive horizons.** Different question (model
  decay), and it would quietly praise or blame a single fit for data it never saw. The
  method line names what was actually varied, so the two cannot be confused; a frozen
  artifact run is a separate future decision with its own declaration.
- **Report the mean across origins as the headline.** Rejected: averaging hides exactly
  what the run is for. The mean is published, but beside the counts and the range.
- **Allow a one-origin run and label it "rolling".** Rejected: a plural name for one
  measurement is the misleading case, and the tool would be the source of the claim.
- **Skip origins whose horizon is too small instead of refusing.** Rejected: silently
  dropping cutoffs produces a plan that looks complete and is a selected subset.
- **Weight origins by row count in the aggregate.** Rejected for now: unweighted is
  legible and hand-checkable, and per-origin rows are published so a reader can reweight.
  If a real dataset needs weighting, that is a new decision, not a quiet default.

## Consequences

- A dataset needs roughly `2 × min_train_dates + 2 × horizon_dates` distinct journey
  dates (plus any gap) before rolling evaluation is possible. The intake thresholds already
  demand four distinct dates, which is enough for the defaults (`min_train_dates=3,
  horizon_dates=1, step_dates=1`) to produce two origins and no more — real temporal
  robustness needs a longer file, and the report will say so by refusing.
- Runs cost one refit per origin. On a 240-row fixture nine origins fit and score in well
  under a second; a large file will need batching or fewer origins via `--step-dates`.
- `MIN_ORIGINS`, the per-origin prevalence rule and the "scoring origins" wording are now
  the contract tests assert against; changing them is a decision, not a refactor.
- Nothing here produces an empirical claim. No approved dataset exists, so every number
  from this path comes from labelled synthetic rows.

## Validation

- `tests/data/test_rolling_origins.py` — 25 tests: boundaries grow by the step, no origin
  scores a date it trained on, scored windows are disjoint, row order does not move a
  boundary, a scarce horizon / an unhonourable gap / a single usable origin / a booking on
  both sides of a cutoff all refuse with reasons naming the counts, ambiguous dates raise,
  argument rules raise, and `to_dict()` carries no frames.
- `tests/training/test_origins.py` — 19 tests with hand-computed cells: origin 0's
  all-CNF training block gives baseline Brier 2.0 and model Brier 92/81; origin 1's
  4-CNF/2-WL block gives 2/9 and 48/121; the mean and spread match; a threshold that only
  one horizon clears produces "1 of 2 origins produced no score at all" and a coverage
  range instead of a false loss; a fixture where both horizons waitlist reports "All 2
  scoring origins beat…"; one cutoff refuses; an unfittable window names its origin; the
  merged target scores 6/9 mass; reports are byte-stable.
- CLI: `python -m railconfirm.training origins` on the labelled synthetic moving fixture
  (240 rows, 12 distinct journey dates) produced 9 origins, mean Brier 0.958270 against a
  mean baseline of 0.607018 with **1 of 9** origins beating it, mean event 0.473334 against
  0.303509 with **2 of 9** beating, and the conclusion that the verdict is not stable
  across cutoffs. A six-date file asked for a five-date training block refused with
  "Only 1 origin usable" and exit 1. Full commands and exit codes are in
  `docs/DEVELOPMENT_LOG.md`.

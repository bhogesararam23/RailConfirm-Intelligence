# Evaluation protocol

Status: pre-registered plan draft. Final split dates and sample sizes must be set after the data audit, before inspecting locked-test performance.

## Goals

Evaluate probability quality and practical coverage on journeys that occur after the model-development period. Classification accuracy alone is insufficient for a prediction product.

## Data partitioning

Use chronological development, validation and locked-test periods:
- **Development/train:** fit parameters and candidate models.
- **Validation:** compare configurations and select calibration methods.
- **Locked test:** report final results once the pipeline and thresholds are fixed.

All snapshots from the same booking/journey must remain in one partition. Deduplicate by stable, de-identified booking/journey references before splitting. Check for near-duplicates, repeat uploads and derived features that could encode the final outcome.

For each training example, reconstruct the exact information available at `prediction_at`. Exclude later status movements, final outcomes, events published later, and any data fields computed using future information. Late-ingested records must not be backdated to pretend they were available to the model.

Record split dates and eligibility rules before model selection. Use rolling-origin evaluation across multiple cutoffs whenever the time span permits it; when it does not, `rolling_origin_windows` refuses rather than reporting one cutoff as a temporal result.

### Implemented split behaviour

`backend/railconfirm/data/preprocessing.py` provides both the single-cutoff case (`chronological_split`) and the multi-cutoff plan (`rolling_origin_windows`, ADR-0014). Rolling-origin evaluation is implemented; it has never run on approved real data, because no approved dataset exists yet.

- `chronological_split` allocates **whole dates**, not rows, so records sharing a journey date cannot straddle a boundary, and the result is independent of input row order. Dates are parsed strictly as ISO `YYYY-MM-DD`: an ambiguous value such as `01/02/2026` is refused rather than resolved by locale, because a wrong resolution silently reorders which records are "future".
- A split that cannot give all three partitions at least one date and `min_rows_per_partition` rows, or that cannot respect `gap_days`, returns `eligible=False` with reasons **and no partitions at all**. Returning every row as `train` with an empty test frame — which is what the first implementation did for fewer than four distinct dates, and at exactly three dates — lets a later step fit, score and report a metric on data that was never held back.
- When `booking_group_id` is present, a booking appearing on dates that fall in more than one partition blocks the split rather than splitting one outcome across training and evaluation.
- `extract_features` reads only as-of information and refuses a frame that still carries an outcome column; the caller must pass `strip_labels(df)` first. Queue positions are nullable (`pd.NA`), never fabricated as zero, and `lead_days` is null for a missing or post-departure observation instead of clamped to `0`.
- `asof_statuses(frame)` is the **one** definition of the status a record describes: `current_status` when the source recorded one, otherwise `initial_status`, with an unmappable value left `UNKNOWN`. Fitting, scoring and serving all call it. This is not a style rule: the baseline was once keyed by `initial_status` while requests were answered from `current_status`, so every metric described a lookup the product never performs and a served estimate came from a different population (ADR-0013).
- `FEATURE_SCHEMA_VERSION` and `FEATURE_COLUMNS` are the shared definition that training and inference must agree on. Changing feature meaning or nullability requires a version bump so a stored artifact can be rejected rather than misread. Version 3.0.0 renamed the derived status columns `asof_normalized`/`asof_position` and made a blank `current_status` fall back per row instead of becoming `UNKNOWN`.

Every split result carries `PartitionSummary` counts — rows, distinct dates, distinct bookings and boundaries — which are what an evaluation report must publish alongside its metrics.

### Implemented rolling-origin behaviour

`rolling_origin_windows(df, min_train_dates=3, horizon_dates=1, step_dates=1, gap_days=0)` plans expanding-window cutoffs on **whole dates**: origin *k* trains on the first `min_train_dates + k × step_dates` dates and is scored on the `horizon_dates` dates immediately after them, separated by more than `gap_days` calendar days.

- **Two origins minimum.** A plan that yields fewer than `MIN_ORIGINS = 2` usable origins is not eligible and returns **no windows**, with a reason naming the date count. One cutoff is what `chronological_split` already measures; reporting it under a plural name would turn a single draw into a temporal claim.
- **`step_dates >= horizon_dates` is required.** Overlapping horizons would score the same outcome twice. Because every earlier horizon sits inside every later training block, one rule — no booking on both sides of a cutoff — also guarantees no booking is scored by two origins.
- **Bookings that straddle a cutoff block the plan**, exactly as in the single-cutoff split.
- **Each origin refits.** `run_rolling_origins` calls `fit_cohorts` on that window's training block, builds the estimator from those cohorts and scores the horizon with `score_partition`, so the baseline prevalence always comes from the origin's own past. Consequences the report states: the method line is `refit-per-origin, score-the-next-horizon` (this measures the fitting procedure across time; one frozen artifact's decay is ADR-0018's separate question and its own command), per-origin baselines differ by construction, and overlapping windows mean the origins are **not independent evaluations** — no multiplicity correction is applied.
- **Origins that produced no score are counted separately from origins that lost.** A horizon where every row abstained contributes no Brier, and the conclusions are written against `origins_with_scores`, not against the origin count.
- **Instability is the output.** Conclusions report how many scoring origins beat their baseline (all / none / some), the Brier range and the coverage range across origins. `--report` is byte-reproducible and requires `--generated-on`.
- **Both aggregations are published, and a disagreement is stated (ADR-0028).** Each origin's score is a mean over the rows it scored, so a mean of those means weights a two-row horizon exactly as heavily as a two-thousand-row one. The aggregate therefore publishes the mean over origins *and* the figure pooled over scored rows, plus `scored_rows_spread` and a verdict per score — `distribution_agreement`, `event_agreement` — that says whether the two land on the same side of their own baselines (`agree`, `disagree`, or `undetermined` when nothing scored). When they disagree the report prints both pairs of numbers and states that which figure a reader quotes decides the verdict; when they agree it names the pooled figure as the one a statement about served predictions rests on. The origin report schema is `1.1.0`; no key changed meaning.

Reproduce it with `python -m railconfirm.training origins DATASET MANIFEST --min-train-dates 3 --horizon-dates 1 --step-dates 1 --allow-synthetic-for-testing`.

### Implemented frozen-artifact decay behaviour

Rolling origins refit, so they measure the fitting procedure. `frozen_horizon_windows(df, fitted_to=…, horizon_dates=1, step_dates=1, gap_days=0)` answers the other question — one table, fixed, judged further and further from the period it was counted from (ADR-0018):

- **The cutoff is the artifact's own `trained_to`.** A caller cannot choose it, because a chosen cutoff lets dates the table was counted from be reported as evidence about it. An artifact that declares no fitted period is refused before any arithmetic.
- **Two horizons minimum.** `MIN_HORIZONS = 2`, and a plan that cannot give two returns **no windows**, with the reason. One future block is a holdout, and a decay curve drawn through one point is a stability claim nothing measured.
- **Nothing refits between horizons.** The cohorts, `min_sample_threshold`, `laplace_alpha` and any `calibration` block come from the artifact and are used unchanged on every horizon, through `build_estimator()` — the same loading gate the registry serves through — so a decay number and a served number describe one estimator.
- **One frozen prevalence baseline.** It is computed once from the fittable rows at or before the cutoff. Recomputing it per horizon would move the yardstick toward the answer being judged; the report states which rows produced it and that it is this file's reading of the fitted population rather than the original snapshot.
- **A booking spanning the cutoff invalidates the run.** Its outcome is already inside the table being judged, and the planner refuses the whole plan rather than dropping rows from the side under test.
- **Drift is an ordering.** The result publishes first and last horizon values, their difference and the spread, and counts horizons that scored at all separately from horizons that lost to the frozen baseline. Coverage drift is reported as a reach fact, not an accuracy one.

Reproduce it with `python -m railconfirm.training decay DATASET MANIFEST --artifact models/<version>.json --horizon-dates 2 --step-dates 2 --allow-synthetic-for-testing`. On the labelled synthetic fixture the same estimator that a single cutoff reports as event Brier 0.239487 against a 0.24 base rate scores 0.243482, 0.240300, 0.239411 across three two-date horizons and beats the frozen base rate in one of the three — the ordering is the finding, which is why the mean is not published as the headline.

### Implemented scoring

`backend/railconfirm/training/` now performs the fitting and scoring this protocol describes, for the single-cutoff case:

- **Gate before fitting.** `load_approved_dataset` verifies the manifest against the file (hash, size, recounted rows), requires an `approved` decision with a named reviewer and rationale, requires the licence review to permit `model_training`, and refuses rows that declare `is_synthetic` unless the caller opts in for pipeline testing. It then requires **technical eligibility** — structural validity is not enough — and hands the trainer only the rows the validator kept, so duplicates, contradictions, censored labels, impossible dates and unmappable statuses cannot enter a count or a score. The synthetic pipeline opt-in may fit below the thresholds because its artifact is marked unservable; a non-synthetic file gets no such relief, and the relaxation itself is written into the artifact's limitations.
- **Fit.** Cohorts are counted from the training partition only and keyed by `(class_code, quota_code, asof_normalized)` through the same `asof_statuses()` call that scoring and serving use; the artifact is written with `promotion: "candidate"`, so fitting never activates anything, and it records the dataset SHA-256, the target, the feature-schema and status-mapping versions, the features it actually reads (`features_used`) and the cohort rule its keys follow (`cohort_semantics`), plus its own limitations. An artifact that declares a different cohort rule or a different feature set is refused at load, so a table can never be queried under a contract it was not built with.
- **Score.** Multiclass Brier and log loss against a training-period prevalence baseline, with `brier_skill`, coverage and abstention counts reported separately. Abstained rows are excluded from the scores rather than counted as errors — a refused prediction is not a wrong probability. The target's own event is scored alongside the distribution: `final_chart_cnf` puts the confirmed mass against a 0/1 label, `final_chart_cnf_or_rac` sums the confirmed and RAC mass. Both partitions therefore publish a distribution verdict and an event verdict, and when the two disagree about beating the base rate the report says so instead of quoting the flattering one. On the synthetic fixture they do disagree: the distribution loses to the base rate (Brier 0.501038 vs 0.500000) while the CNF event narrowly beats it (0.232664 vs 0.250000) — re-verified unchanged on 2026-10-23 after the as-of keying change, because that fixture records no `current_status` and its as-of status is therefore its booked status.
- **Report.** Deterministic JSON: same inputs and same `--generated-on` produce the same bytes. It publishes split boundaries, rows used and excluded per reason, the feature list with its availability statement plus `used_by_estimator`, `not_used_by_estimator` and the cohort rule the fit recorded, metric definitions, segment counts with low-sample flags (segments cover class, quota, the booked status **and** the as-of status, because the gap between those two is where a keying mistake would hide), and a limitations block that states when no calibration was fitted. Every published scorecard field has a definition in the report, and a test fails if a metric is added without one.

Fitting or scoring an artifact for a target it was not fitted for is refused rather than tolerated: `evaluate --target` is checked against the artifact's declared target, and `--target` accepts only the targets `TARGET_EVENTS` defines.

Not implemented: empirical copula/correlation group models fitted on real data (ADR-0016 implements Poisson-binomial convolution and sequential queue-clearing bounds, scored in `score_partition()`), and a per-segment calibration correction (ADR-0019 measures the observed-minus-predicted gap inside each cohort and deliberately fits nothing per cohort). No number produced by this code has come from approved real data.

## Baselines and candidates

1. Historical-frequency baseline with smoothing and a documented fallback for sparse strata.
2. Status-and-time baseline using current normalized status, queue position and time remaining.
3. Tabular ML candidate such as CatBoost or LightGBM, selected only after dataset and leakage review.
4. A joint/group-outcome method evaluated against a documented baseline.
5. Context-augmented variants, introduced one feature group at a time.

Implemented so far: baseline 1 (`historical_frequency_baseline`) and baseline 2 partially, as
`cohort_position_baseline` — cohort key plus the as-of queue position in fixed doubling bands
(ADR-0020). Time remaining is **not** read by either estimator: `lead_days` is derived and
published as unused, and a model that consulted it would have to be re-examined for the
leakage rule the feature schema already enforces. Baselines 3–5 need both an approved dataset
and, for 4, real multi-passenger bookings; nothing has been fitted on real data.

Choosing between two estimators is not a matter of which produces the prettier number on one
split: ADR-0021 defines the paired comparison on a locked later period that decides whether a
candidate may replace the baseline, including what happens when a candidate wins on validation
and loses on the locked test.

Do not choose algorithms before understanding the actual sample size, class imbalance, missingness, label quality and feature coverage.

## Metrics

### Primary probability metrics
- Multiclass Brier score for eligible passenger outcomes.
- Multiclass log loss, with explicit handling of zero/near-zero probabilities and excluded classes.
- Reliability diagrams and calibration summaries.
- Group-event Brier score/log loss for events such as all CNF or at least (k) CNF.

Define the exact Brier variant and averaging method in result tables. Lower is better for Brier score and log loss.

### Supplementary metrics
- Confusion matrix and per-class precision/recall.
- PR-AUC or one-vs-rest metrics when appropriate for a defined binary target.
- Calibration-in-the-large and calibration slope where statistically supportable.
- Prediction coverage and abstention rate.
- Latency and provider/data freshness for the serving system.

### Segment reporting
Report metrics and sample counts by ticket-status category, quota, class, prediction horizon, route/train coverage, initial position bands, data freshness and other predeclared segments. Avoid drawing strong conclusions from tiny groups. Apply privacy-preserving aggregation to small cells where relevant.

## Uncertainty

Provide uncertainty intervals for metrics. Resampling should respect journey/booking dependence; do not treat many snapshots from one booking as independent units. Note the number of journeys and eligible passengers behind every reported estimate.

## Calibration

Calibration may be fitted on validation data only. Evaluate the calibration layer on the locked test set. A stated 70% probability should correspond to an approximately 70% observed rate over a sufficiently large representative set, not merely a high ranking score.

### Implemented calibration behaviour

`python -m railconfirm.training fit --calibrate` (ADR-0017) fits `platt_logistic_v1` — logistic scaling of the target event's log-odds, two parameters from the validation rows in fixed order — and writes it into the artifact as a block naming the method, target, event classes, slope, intercept, fitted partition, row count and period.

- The correction moves the **event mass only**. Classes inside the event keep their proportions, because nothing was fitted for them separately, and the artifact's limitations say so. A distribution already certain about the event is returned untouched.
- It is embedded only if it strictly reduces the event Brier **on validation**; otherwise the run refuses and writes nothing. The report always states the locked-test movement as well, phrased whichever way it goes.
- **A locked period that scored nothing is `unknown`, not a failure (ADR-0029).** The locked partition is scored by the estimator that serves requests, so it abstains when no cohort answers — `scored_rows == 0`, `event_brier` absent. The calibration block then reports `locked_test_measured: false` and `helps_on_locked_test: null`, and the conclusion says the effect there is unknown and that the artifact's calibration rests on the validation window alone. `null` is not `false`: a correction that measured nothing has not been shown to fail. The artifact is still written, because the fit decision belongs to validation (ADR-0017), and promotion stays `candidate`. A *validation* scorecard with no score is a different matter and is refused with `DatasetValidationError`, since no fit can exist without scored validation rows. The evaluation report schema is `1.1.0`.
- `score_partition(..., calibration=…)` and the inference engine call the same `apply_calibration`, so a measured score and a served number cannot come from different arithmetic. A served `basis` gains `calibrated=platt_logistic_v1`.
- Fitting refuses evidence it cannot use: fewer than `--calibrate-min-rows` scored rows (default 50), one label only, no spread in the predicted probability, certainty rows dropping the usable count below the floor, or perfectly separable rows whose maximum-likelihood slope runs away.
- Subgroup calibration **is** measured (ADR-0019). Every scorecard publishes, per `class_code`, `quota_code`, booked status and as-of status, the mean predicted event probability, the observed event rate, their difference and the row count — the numbers being the corrected ones when a layer is applied, because a gap measured beside the probability a passenger was handed describes a number nobody sees. Reliability bands stay a description, and they are pooled across cohorts by construction, which is exactly why the per-segment table exists beside them.
- No per-segment correction is fitted, and the report says so. One population-wide slope leaves residual error inside each cohort; the segment gaps **are** that residual, not evidence that the correction holds cohort by cohort. A segment below the scorecard's row floor (default 25) is flagged `low_sample` and may not carry a claim in either direction, and when no segment clears the floor the report states that subgroup calibration cannot be claimed rather than quoting a thin cohort to fill the line.
- `artifact_format` stays `/2`: the block is optional and its absence has exactly one meaning, so no previously accepted artifact changes meaning.
- An artifact that carries the layer stops describing itself as "not a trained or calibrated model". The limitation list is what a reader sees on a served report, and a surviving base sentence would deny the line printed beneath it; the replacement still says the numbers are smoothed cohort counts, because a fitted slope does not make them a trained model.

Calibration quality must also be examined by meaningful subgroups where sample sizes permit. Do not claim strong calibration in a subgroup without evidence.

## Feature ablation

Compare the status/history baseline to models with:
- calendar and holiday features;
- structured operational events;
- other external context only when a source is approved.

Accept new features only when the preregistered evaluation shows incremental benefit without unacceptable harm to calibration, coverage, latency, privacy or reproducibility. An LLM's explanation of a news article is not evidence that the event should alter prediction.

## Model selection and reporting

- Choose primary metrics and acceptance rules before reviewing locked-test results.
- Keep code revision, environment, dataset version, feature list, split, random seed and configuration with each experiment.
- Save predictions with model version, target definition and timestamp.
- Report failed experiments and category gaps.
- Do not claim an accuracy threshold before actual evaluation.
- If a candidate does not beat the baseline, report that result and revisit data or formulation.
- Implemented (ADR-0021): `python -m railconfirm.training compare` is the acceptance rule above,
  executed rather than advised. It chooses no metric after seeing data — the deciding partition is
  fixed to the locked period, the paired lens is the target event, and the four conditions
  (distribution Brier, event Brier, coverage, paired wins over losses) must all hold there. A
  candidate that fails is reported as `baseline` with each failing condition printed at its own
  numbers, and a locked period with no rows both models answered is `undetermined` rather than a
  tie. Neither model is promoted by the run.
- Implemented (ADR-0023): the comparison refuses before it scores when it would not be one.
  Both models must name the same `(dataset_id, sha256)` pair and that pair must be the file
  being scored; `status_mapping_version`, `cohort_semantics`, `outcome_classes` and
  `feature_schema_version` must match, because each changes what a row means; and
  `laplace_alpha` and `min_sample_threshold` must match, because a delta across a smoothing
  change cannot be attributed to the model. Partition summaries matching by dates and row
  counts is not enough: each partition's rows are fingerprinted in stored order, since
  scoring walks the baseline's frames for both models and pairing is by position. Pairing
  itself refuses a repeated position and a partition total below the rows answered.
- Synthetic data is allowed for unit and UI tests, but must not appear in empirical performance reporting.

## Minimum experiment record

- Experiment ID and owner.
- Question/hypothesis.
- Dataset version and source register IDs.
- Inclusion/exclusion rules.
- Split dates and grouping method.
- Feature set and target definition.
- Code revision and environment.
- Model parameters and random seed.
- Metrics with sample counts and uncertainty.
- Calibration and subgroup results.
- Failure analysis, limitations and decision.

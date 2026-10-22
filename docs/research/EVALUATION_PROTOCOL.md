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

Record split dates and eligibility rules before model selection. If the time span permits, use rolling-origin evaluation across multiple cutoffs.

### Implemented split behaviour

`backend/railconfirm/data/preprocessing.py` currently provides the single-cutoff case; rolling-origin evaluation is not implemented and must be added before any result is called temporally robust.

- `chronological_split` allocates **whole dates**, not rows, so records sharing a journey date cannot straddle a boundary, and the result is independent of input row order. Dates are parsed strictly as ISO `YYYY-MM-DD`: an ambiguous value such as `01/02/2026` is refused rather than resolved by locale, because a wrong resolution silently reorders which records are "future".
- A split that cannot give all three partitions at least one date and `min_rows_per_partition` rows, or that cannot respect `gap_days`, returns `eligible=False` with reasons **and no partitions at all**. Returning every row as `train` with an empty test frame — which is what the first implementation did for fewer than four distinct dates, and at exactly three dates — lets a later step fit, score and report a metric on data that was never held back.
- When `booking_group_id` is present, a booking appearing on dates that fall in more than one partition blocks the split rather than splitting one outcome across training and evaluation.
- `extract_features` reads only as-of information and refuses a frame that still carries an outcome column; the caller must pass `strip_labels(df)` first. Queue positions are nullable (`pd.NA`), never fabricated as zero, and `lead_days` is null for a missing or post-departure observation instead of clamped to `0`.
- `FEATURE_SCHEMA_VERSION` and `FEATURE_COLUMNS` are the shared definition that training and inference must agree on. Changing feature meaning or nullability requires a version bump so a stored artifact can be rejected rather than misread.

Every split result carries `PartitionSummary` counts — rows, distinct dates, distinct bookings and boundaries — which are what an evaluation report must publish alongside its metrics.

## Baselines and candidates

1. Historical-frequency baseline with smoothing and a documented fallback for sparse strata.
2. Status-and-time baseline using current normalized status, queue position and time remaining.
3. Tabular ML candidate such as CatBoost or LightGBM, selected only after dataset and leakage review.
4. A joint/group-outcome method evaluated against a documented baseline.
5. Context-augmented variants, introduced one feature group at a time.

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

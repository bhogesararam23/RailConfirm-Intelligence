# Observability

Status: proposed operational standard.

## What needs to be observable

### Application/API
- request count and latency by route;
- validation failures by reason code;
- error rates and timeouts;
- model load and prediction failures;
- response state: supported, abstained or unavailable;
- saturation and resource use once measured.

### Data sources
- last successful fetch time;
- observation age;
- request/error/rate-limit counts;
- schema validation failures;
- unknown status frequency;
- duplicate/conflicting record rates;
- data coverage by source and supported field.

### Model behavior
- model and feature-schema version in each prediction record;
- feature distribution and missingness drift;
- outcome distribution when verified labels become available;
- Brier score/log loss and calibration over a defined period;
- subgroup metrics when there are enough labels;
- abstention rate and reasons;
- group-level probability quality separately from passenger-level quality.

Do not infer model drift solely from changes in predictions; demand, data collection and user sampling can change simultaneously.

## Privacy-safe logging

Logs should use random request/prediction IDs and controlled reason codes. Redact raw PNRs, names, provider credentials, raw private payloads and unnecessary route/date combinations. Do not log complete user requests by default.

Define a log retention policy separately from ticket tracking retention. Keep production and research access separated and auditable.

## Alerts

Initial alert conditions should include:
- provider authorization failures or unexpected rate limiting;
- source freshness exceeding a documented threshold;
- provider schema changes or sudden unknown status spikes;
- prediction failures or model artifact incompatibility;
- impossible probability output;
- database/storage errors;
- unexpected rise in abstention or missing features;
- model quality falling below a predeclared threshold once sufficient outcome labels arrive.

Thresholds must be configured from provider terms, measured baseline behavior and operational requirements. Do not invent numeric alert thresholds in advance of those inputs.

## Monitoring data quality

A successful HTTP response does not mean the observation is valid. Track schema pass rate, time ordering, missingness, conflicting rows, label verification and coverage. Route data-quality issues to review before model training.

## Model-performance monitoring

When final outcomes are available:
1. Join them to the prediction that was made at the historical time.
2. Verify that target and prediction-time definitions match.
3. Exclude or separately account for censored outcomes.
4. Calculate metrics from a documented cohort/window.
5. Report sample count and uncertainty.
6. Compare to the baseline and calibration expectations.
7. Create a research record for significant degradation or recalibration.

Never silently replace a model or recalibrate from the locked test set.

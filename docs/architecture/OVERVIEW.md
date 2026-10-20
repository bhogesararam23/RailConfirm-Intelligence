# Architecture overview

Status: intended architecture, not implemented yet.

## Design constraints

- Manual entry is the first supported product path.
- Live PNR retrieval is a provider integration, not a scraping assumption.
- Data source, feature generation, prediction, group calculations and presentation remain separate modules.
- Model serving must report version, target, timestamp and evidence status.
- The system must be able to return an unavailable/abstain response rather than a fake percentage.

## Logical components

1. **Web application** — journey form, passenger status editor, result matrix and tracking history.
2. **API** — request validation, domain normalization, prediction orchestration and response contracts.
3. **Railway-domain package** — train/station references, class/quota and status vocabularies.
4. **Source adapters** — one adapter per approved provider, each with explicit terms, rate limits, provenance and failure behavior.
5. **Observation store** — time-stamped, access-controlled records with retention.
6. **Feature pipeline** — as-of-time feature generation that excludes future information.
7. **Model training/evaluation** — reproducible experiments, chronological backtesting and calibration.
8. **Inference service** — model selection, calibrated probabilities and abstention rules.
9. **Group outcome layer** — derives group events from a joint distribution or a validated structured approximation.
10. **Monitoring** — source freshness, ingestion errors, schema changes, calibration drift and model coverage.

## Proposed technology options

The initial candidate stack is a TypeScript web client, Python/FastAPI API, PostgreSQL storage and Python ML tools. These are not yet locked implementation choices; see ADR-0002. Avoid adding runtime services until the data path justifies them.

## Prediction flow

1. Validate user inputs and the source/time semantics of every observed status.
2. Normalize recognized raw statuses while preserving raw inputs.
3. Determine whether the request falls within validated model coverage.
4. Build features using only information available at the requested prediction timestamp.
5. Call the selected model and calibration layer.
6. Build passenger probabilities and group outcomes from the model's supported distribution.
7. Attach model version, prediction timestamp, data freshness, coverage and limitations.
8. Return either a prediction or a structured abstention/unavailable response.

## Tracking flow

1. User requests tracking.
2. The server checks consent, provider availability and supported purpose.
3. Approved source adapter fetches current observations within permitted rate limits.
4. Response is validated and reduced to necessary fields.
5. Observation is stored with source and timestamps under the retention policy.
6. Prediction is recalculated from the latest valid state.
7. User can view observed status movement separately from model-probability movement.
8. Tracking data is deleted/expired according to policy.

## Failure behavior

- Provider unavailable: preserve last observed status with a stale timestamp; do not represent it as live.
- Unknown status: preserve raw value and return a review/unsupported outcome.
- Model unsupported or data insufficient: abstain or return a clearly labelled baseline only if that baseline has validated coverage.
- Dataset/schema shift: fail closed for affected data paths and log a redacted diagnostic.
- Missing historical source: do not fabricate a result.
- Uncertainty computation unavailable: never invent a confidence interval.

## Deployment boundary

Keep data ingestion and model training separated from public inference. Do not place source credentials in the frontend. Do not expose raw PNR identifiers or private provider responses in logs, metrics or public URLs.

## Architecture evolution

Material changes to model ownership, databases, provider access, deployment topology, retention or probability semantics require a new ADR. ADRs record what was decided at that time; they are not silently rewritten when the architecture evolves.

# Research plan

Last reviewed: 2026-10-21

## Research goal

Develop and evaluate a probabilistic model of Indian Railways reservation outcomes from the information available at a defined point before final charting. The work includes a web application, but the central research question is whether the model can produce useful and calibrated estimates on journeys it has not seen.

## Questions

1. How much predictive value is available from the current WL/RAC position, original booking status, class, quota, route segment, train identity and time remaining?
2. Does a time series of status changes outperform a single status snapshot?
3. Can outcomes for passengers on the same booking be estimated jointly with better calibration than an independence assumption?
4. Do verified calendar and operational-event features improve a model beyond status and historical features?
5. How does performance vary by quota, status category, class, route, prediction horizon and data freshness?
6. When should the system abstain because evidence is sparse, stale or out of distribution?

## Hypotheses to test

These are hypotheses, not conclusions.

- H1: Recent status trajectory and time remaining will add predictive signal beyond a current status snapshot.
- H2: A trained tabular model can improve proper scoring rules over a historical-frequency baseline on later journeys.
- H3: Joint modelling will improve group-level probabilities compared with multiplying individual estimates under an independence assumption.
- H4: Contextual features will be kept only if temporal holdout evaluation shows measurable improvement.
- H5: Calibration and abstention will make the product more trustworthy than a single confidence label without evidence context.

## Study design

- Define the prediction target and eligible population before evaluating models.
- Audit candidate datasets for source, licence, label semantics, missingness, duplicates and coverage.
- Separate each journey/booking's snapshots so they cannot cross training, validation and test partitions.
- Use chronological splits to mimic deployment on future journeys.
- Establish a simple historical baseline before training a complex model.
- Tune and calibrate on training/validation data only.
- Evaluate the final model once on a locked test period.
- Report scores with uncertainty intervals and subgroup tables.
- Keep experiments reproducible: code revision, environment, dataset version, feature set, split dates, seed and metrics.

## Minimum research outputs

- Data source and quality report.
- Versioned data contract and status glossary.
- Baseline results and an evaluation notebook/script.
- Model comparison and calibration report.
- Group outcome definition and joint prediction approach.
- Model card with supported categories and known limitations.
- Reproducibility instructions for rerunning the evaluation.
- External research deliverables tracked in `docs/research/EXTERNAL_RESEARCH_INDEX.md`: one evidence-backed document per workstream (`INDIAN_RAILWAYS_DOMAIN_AND_OPERATIONS.md` (A), `HISTORICAL_DATA_AND_DATA_ACQUISITION.md` (B), `RAILWAY_API_AND_PROVIDER_LANDSCAPE.md` (C), `ACADEMIC_LITERATURE_REVIEW.md` (D), `COMPETITOR_AND_MARKET_LANDSCAPE.md` (E), `CONTEXTUAL_FEATURE_CATALOGUE.md` (F), `PRIVACY_LEGAL_LICENSING_REGULATORY.md` (G), `OPEN_SOURCE_TECHNICAL_ECOSYSTEM.md` (H), `PARTNERSHIP_AND_DATA_ACQUISITION_STRATEGY.md`), plus the master source register `EXTERNAL_RESEARCH_INDEX.md`.

## Research integrity

No performance target is selected after inspecting final test results. Synthetic records can validate software behavior but cannot establish real-world predictive performance. A result should identify the dataset and evaluation dates that support it. If data is too sparse for a category, mark that category unsupported rather than extrapolating confidence without evidence.

## Proposed milestone gates

### Gate 1 — Data readiness
Pass only when labels, provenance, usage rights, timestamps and suitable coverage are documented.

### Gate 2 — Baseline readiness
Pass when a reproducible benchmark and temporal split can be generated without leakage.

### Gate 3 — Model utility
Pass when a candidate improves the chosen primary metrics over the baseline on held-out journeys and uncertainty is reported.

### Gate 4 — Product readiness
Pass when model versioning, stale-data behavior, abstention, calibration and limitations are visible to users.

### Gate 5 — Live integration
Pass when provider permissions and terms are verified, and security, retention, access and rate-limit behavior are tested.

# Prediction-science methodology

Last reviewed: 2026-10-31

This document records the research and statistical methodology considered for estimating
Indian Railways reservation outcomes. It is a research note, not a trained-model claim:
no number here has been produced from approved real data, and none will be until a dataset
clears `docs/data/DATASET_INTAKE_CHECKLIST.md`.

## Research questions

The research plan (`docs/research/RESEARCH_PLAN.md`) sets these questions. The
confirmation here is a candidate answer to the first and second.

1. **How much predictive value is available from current WL/RAC position, original booked
   status, class, quota, route segment, train identity and time remaining?**
   - The historical-frequency baseline already answers this approximately: a cohort is
   `(class_code, quota_code, as_of_status)` with Laplace smoothing, and the position
   estimator refines that cohort by fixed doubling bands of as-of queue position.
   - On a labelled synthetic fixture the position estimator loses to the flat baseline
   (locked event Brier 0.275914 vs 0.239960) because those rows' outcomes did not depend
   on position. That is evidence the hypothesis "position helps" is not universally true
   and must be measured on real data, not assumed.
2. **Does a time series of status changes outperform a single status snapshot?**
   - The row contract carries `observation_date` but no observation-clock time, so a
   trajectory is a sequence of snapshots, one per journey date. The current estimator
   consumes only the latest snapshot at the prediction time. A time-series model is not
   implemented because no dataset carries the per-snapshot series needed to fit and
   evaluate one without leakage.
3. **Can outcomes for passengers on the same booking be estimated jointly with better
   calibration than an independence assumption?**
   - ADR-0003 and ADR-0016 implement exact Poisson-binomial distribution
   `P(K = k)` and `P(K >= k)` under an independence baseline, and sequential
   queue-clearing comonotonic bounds under FIFO queue rules. Neither is validated against
   real multi-passenger data. This is the open empirical question.
4. **Do verified calendar and operational-event features improve a model beyond status
   and historical features?**
   - Not implemented. The road map (roadmap Phase 9) plans structured operational,
   event/news and calendar signals, with temporal-holdout ablation per
   `docs/research/EVALUATION_PROTOCOL.md`.
5. **How does performance vary by quota, status category, class, route, prediction horizon
   and data freshness?**
   - Segment reporting exists (class, quota, booked status, as-of status, low-sample
   flags) but has not been measured on real data.
6. **When should the system abstain because evidence is sparse, stale or out of
   distribution?**
   - Implemented: `no_trained_model`, `no_approved_data`, `unknown_status`,
   `unsupported_status`, `insufficient_sample`. A feature is supported only when a cohort
   has at least `min_sample_threshold` rows (default 30).

## Method classes considered

These are hypotheses and designs, not results. Each is evaluated with leakage-safe
temporal holdout evaluation before any claim is made.

### Historical-frequency baseline with smoothing

The implemented `HistoricalFrequencyBaseline` counts outcomes per cohort and smooths with
Laplace alpha. It is an assumption-driven fallback, not a trained model; it must never be
presented as one. Its limitations: it cannot represent position effects (fixed-band
position estimator is a partial answer), it cannot represent time trends, and it cannot
represent calibration beyond the smoothing.

### Survival / time-to-chart modelling

A booking's queue position and journey date define a horizon. Survival-style models
estimate the probability that charting happens before a deadline as a function of
cohort, position, class and time remaining. The codebase already enforces the matching
rule that features may only be reconstructed from information available at
`prediction_at`, so a time-to-chart model would need correct past history per
passenger-journey, not a single future aggregate.

### Probabilistic tabular methods (calibration)

The codebase implements Platt logistic calibration of the target event, fitted on the
validation partition only and embedded only when it strictly reduces validation event
Brier (ADR-0017). This is a population-level correction: it moves the target event's
mass and rescales the remaining classes proportionally. It does not fit per-cohort
slopes. ADR-0019 then measures subgroup calibration (observed minus predicted per
class, quota and status, with a 25-row floor on what may be claimed) without fitting a
per-segment correction.

### Group-outcome methods

For multi-passenger groups, neither independent multiplication nor a single implied
number is valid: ADR-0003 and ADR-0016 define two extremes. The independence baseline
computes the exact Poisson-binomial distribution via `O(n^2)` dynamic-programming
convolution, and the queue-dependent comonotonic bound models FIFO waitlist clearance.
Group-event Brier scoring is in `score_partition()`. These are evaluated against observed
joint outcomes when real group data exists.

### Rule-based and knowledge-based baselines

Indian Railways waitlist semantics (GNWL, RLWL, PQWL, TQWL, RQWL, DPWL and the RAC
position) are part of the domain model (status mapping v1.1.0). A rule-based baseline
that uses position and quota semantics without any outcome history is a legitimate
comparison point, because a model that cannot beat a clearly-stated rule is not worth
serving. Such a baseline is exact only where the rule is exact; its limits are the
limits of the rule.

## Principles for any future model

- **Time-safe splits.** A prediction may only use information available at its
  `prediction_at` timestamp. Post-chart outcomes, later status movements and events
  published later are excluded. `chronological_split` allocates whole dates so one
  journey cannot straddle a boundary.
- **One as-of status rule.** `preprocessing.asof_statuses()` is the only definition of
  the status a record describes: `current_status` when recorded, otherwise
  `initial_status`. Fitting, scoring and serving must all call it; a cohort keyed by one
  column and queried by another describes a lookup the product never performs.
- **No hidden network calls.** App startup, manual prediction and unit tests must not
  depend on third-party runtime APIs.
- **No invented probabilities.** A structured abstention is the correct response when
  no validated model or source is available; never return `200 OK` with a fabricated
  number.
- **Group outcomes are dependent.** Do not derive group probabilities by multiplying
  individual probabilities unless independence is a tested and explicitly justified
  assumption.
- **Abstain on unvalidated output.** When suitable data or calibration are missing,
  report that limitation, abstain, or label the output as a non-production
  demonstration.

## Sources consulted

These are the authoritative references the status vocabulary and the statistical
principles were checked against. All URLs were read on 2026-10-21 unless noted.

- Indian Railways passenger enquiry terminology (status legend: CNF, RAC, WL,
  RLWL, GNWL, PQWL, RQWL, DPWL, TQWL, NT, CAN/MOD, RELEASED, WEBCAN, WEBCANRF,
  REGRET/WL, R#): `https://www.indianrail.gov.in/enquiry/PNR/PnrEnquiry.html`
- Indian Railways booking/enquiry terminology for the status families supported by the
  mapping (verified 2026-10-21 against the enquiry legend above).
- Plackett, R. L. (1958). "The analysis of permutations, according to the numbers of
  successes and failures in their conditional samples of two types". *Biometrika*
  45(3/4): pp. 422–444. (first-subject / paired design and sign test justification for
  the paired-comparison method ADR-0021/ADR-0039).
- Platt, J. (1999). "Probabilistic outputs for support vector machines and comparisons
  to regularized likelihood methods". (Platt scaling, the calibration method in ADR-0017).
- Bröcker, J. (2009). "Assessing calibration of probabilistic forecasts". *Monthly
  Weather Review* 137(6): pp. 1616–1631. (calibration, calibration-in-the-large, slope).
- Dukic, N., et al. (2010). "National Weather Service temperature and precipitation
  forecast calibration". *Weather and Forecasting* 25(4): pp. 901–917. (calibration slope
  and reliability diagrams).
- Candès, E., and Romano, Y. (2018). "Conformal prediction under distributional
  shift". (conformal prediction as a calibration framework for uncertainty).

## Limitations of the current methodology

- No model has been fitted on approved real data. Every number in this document
  describes the pipeline's structure and the synthetic-fixture checks, not railway
  behaviour.
- The row contract carries calendar dates only. A same-day observation is refused because
  it cannot be ordered against the chart; a trajectory needs per-snapshot timestamps
  that no approved dataset provides.
- No live PNR or polling capability exists in the local-first build; status history
  comes only from a dataset that is not approved.
- The position estimator is a partial answer to position effects, not a survival model,
  and its own synthetic-fixture result was a loss to the flat baseline.
- No per-segment calibration correction is fitted; subgroup gaps are measurements, not
  corrections.
- Code-pickle artifacts are refused by design: a pickle executes code on load, and an
  unreviewed binary format would let a dataset arrive in a shape nobody inspected.

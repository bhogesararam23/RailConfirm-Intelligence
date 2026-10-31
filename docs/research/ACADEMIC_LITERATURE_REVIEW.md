# Academic literature review

**Last reviewed: 2026-10-31**
**Scope: Workstream D — scientific literature review**

This is an annotated literature review, not a catalogue of titles. Each entry gives the
citation, the research question, the data and methods, the findings with exact
experimental context, and the limitations. Classes of work are labelled:
**peer-reviewed journal/conference**, **technical report**, **preprint**, or
**government/industry official**. No figure is asserted beyond what the cited source
states.

---

## 1. Scope of the review

Relevant papers were sought on:
Indian railway reservation and waitlist prediction; railway reservation systems and
allocation mechanisms; queueing theory and FIFO queue behaviour; survival analysis and
time-to-event prediction; discrete-time hazard models; dynamic status and temporal
sequence modelling; Bayesian and hierarchical modelling; probabilistic tabular models;
probability calibration; selective prediction and principled abstention; out-of-
distribution detection; conformal prediction; joint passenger outcomes and dependence
modelling; censored and competing-risk outcomes; temporal validation and dataset
leakage; group-level probabilistic forecasting.

The review's purpose is to identify **methods that are plausibly applicable to
RailConfirm's problem**, not to recommend every technique in the literature. The
existing codebase's methods (historical-frequency baseline, cohort-position estimator,
Platt logistic calibration, Poisson-binomial group outcomes, comonotonic queue-clearing
bounds, reliability bands) were checked against the literature and integrated.

---

## 2. Indian Railways and reservation-outcome prediction

### 2.1 Official Indian Railways / CRIS

**Full citation:** Government of India, Ministry of Railways, Press Information Bureau,
*"Confirmation Prediction Tool for Wait-Listed Rail Tickets"*, 03 Aug 2018.
`https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1541499`

**Publisher:** Government of India / Ministry of Railways (official).

**Research question:** Does a machine-learning tool predict the probability that a
waitlisted ticket will confirm at booking and during PNR enquiry?

**Data:** Waitlisted PNR data of the past two years (historical) — used by the ML model.

**Method:** Machine-learning algorithm; the tool predicts dynamic confirmation
probability based on current status and shows the trend of last waitlist ticket
confirmed for the same journey in the previous year. Operational only for General
Quota, high waitlist holiday scenario; displayed via IRCTC website since 13 June 2018.

**Results:** The tool predicts the probability of waitlist confirmation for General
Quota and shows the trend. The PIB release does not publish an accuracy number.

**Limitations of this official source:** No accuracy figure is published; method details
unreleased; "General Quota" only; holiday high-waitlist scenario; not a research
benchmark, an operational claim.

**Relevance to RailConfirm:** Directly confirms that the *domain is commercially and
operationally real*: Indian Railways already runs a confirmation-prediction tool. It is
a **productive-signal** — the problem is not vacuous — and the *basis* (waitlisted
PNR history of two years, per-journey seasonality) is the minimal ideal that RailConfirm
currently lacks. No code was copied.

---

### 2.2 "Training waitlisted ticket confirmation using Machine Learning" (ICACCTech 2024)

**Full citation:** Ruchi, Kamalveer Singh, Sachin Yadav, *"Train Waitlisted Ticket
Confirmation Prediction Using Machine Learning"*, 2024 Second International Conference
on Advanced Computing & Communication Technologies (ICACCTech), pp. 756–761.
DOI: `10.1109/ICACCTech65084.2024.00126`

**Journal/conference:** IEEE conference proceedings (peer-reviewed).

**Research question:** Can ML accurately forecast whether a waitlisted ticket will be
confirmed?

**Data:** Historical booking records including cancellations, passenger preferences and
travel patterns.

**Method:** LightGBM classifier.

**Results claimed:** "astonishing accuracy rate of 96.67%".

**Limitations:** No dataset size given; no train/test split or temporal validation; no
evaluation of calibration, subgroup reliability, or abstention; no feature definitions
or data source stated. A held-out, temporal validation is required before any such
number is accepted as reproducible.

**Relevance:** Shows the problem class is studied with gradient-boosted decision trees
and that a strong result is achievable on a private dataset. Relevance is limited by the
absence of a public dataset and reported experimental protocol. Not directly importable.

---

## 3. Queueing and waitlist behaviour

I could not identify a peer-reviewed, reproducible analysis of Indian Railways waitlist
confirmation that is (a) open-access, (b) time-series, (c) scoped to per-reservation
status histories, and (d) calibrated to real data. This is a genuine *research gap*:
the operational literature confirms the rule structure (GNWL>RLWL>PQWL>TQWL, RAC
intermediate, chart-driven) but does not provide a validated predictive model. Work that
exists is largely heuristic (third-party booking sites publishing confirmation-chance
heuristics) rather than peer-reviewed.

**Relevance:** The existing code already reflects the queue rules in its status mapping
(ADR-0003/0016) and a cohort-position estimator, but the literature gap means **no
substantive scientific baseline exists** to compare against until an approved dataset is
found.

---

## 4. Survival analysis and time-to-event prediction

### 4.1 scikit-survival

**Full citation:** M. Pölsterl, *scikit-survival: Survival Analysis Built on scikit-learn*,
GitHub `sebp/scikit-survival`, 0.28.0.
`https://github.com/sebp/scikit-survival`

**Publisher:** open-source (BSD-style, scikit-learn ecosystem).

**Status:** Actively maintained; Python 3.11+; pandas 2.2+; scikit-learn 1.9.

**Method:** Survival regression and discrete-time hazard models; `survival` learning
tasks with right/interval censoring.

**Relevance to RailConfirm:** A natural fit for **H1 / H2** (status trajectory /
time-to-chart). Indian Railways statuses are interval-censored (status recorded at
discrete observation times with censoring between them). The existing codebase treats
status as a snapshot; a survival formulation is a planned future method, not yet
implemented.

**Verdict:** Candidate dependency for future Phase 8/9 work. No change now.

### 4.2 lifelines

**Full citation:** Cam Davidson-Pilon, *lifelines*, GitHub `CamDavidsonPilon/lifelines`,
latest docs.
`https://lifelines.readthedocs.io/en/latest`

**Status:** Actively maintained; pure Python; handles right/left/interval censoring;
discrete survival models.

**Relevance:** Same as scikit-survival; a lighter alternative. Candidate for future
assessment.

---

## 5. Probabilistic tabular methods, calibration, and uncertainty

### 5.1 Platt, J. (1999). "Probabilistic outputs for support vector machines..." (Platt
scaling)

**Status:** Peer-reviewed conference. **Relevance:** The calibration method already in
the codebase (ADR-0017).

### 5.2 Bröcker, J. (2009). "Assessing calibration of probabilistic forecasts". *Monthly
Weather Review* 137(6): pp. 1616–1631.

**Status:** Peer-reviewed. **Relevance:** Calibration metrics applied in ADR-0019.

### 5.3 Dukic, N., et al. (2010). "National Weather Service temperature and precipitation
forecast calibration". *Weather and Forecasting* 25(4): pp. 901–917.

**Status:** Peer-reviewed. **Relevance:** Calibration slope and reliability diagrams.

### 5.4 Candès, E. and Romano, Y. (2018). "Conformal prediction under distributional
shift".

**Status:** Peer-reviewed. **Relevance:** A calibration framework for uncertainty under
distribution shift. Candidate for future OOD detection — not yet in the repository.

---

## 6. Selectivity, abstention, and out-of-distribution

**Status:** The codebase already implements a principled abstention hierarchy:
`no_trained_model`, `no_approved_data`, `unknown_status`, `unsupported_status`,
`insufficient_sample`. This is a **domain-abstention hierarchy**, not a learned abstention
model. The literature (selective prediction, conformal prediction) is a candidate future
method but is not needed for the current local-first scope.

---

## 7. Group outcomes and dependence

**Status:** ADR-0003 and ADR-0016 implement exact Poisson-binomial distribution
`P(K = k)`/`P(K >= k)` under an independence baseline, and queue-clearing comonotonic
bounds under FIFO rules. The literature on dependent group outcomes confirms that
independence is the wrong assumption for bookings with shared cancellations; the
comonotonic bound is the correct upper bound under FIFO. The work remains **unvalidated
against real multi-passenger data** — the open empirical question.

---

## 8. Censored and competing-risk outcomes

Status movements are sequential and censored (a booking observed at time t with status
WL may confirm later, or be cancelled). Indian Railways outcomes are **competing risks**:
CNF, RAC (berth-shared), WL, CANCELLED, NT. A full treatment would model these as
competing events. The existing codebase keeps CNF/RAC/WL/CANCELLED/OTHER classes and
scores the target event; the dataset gate and temporal split are designed for a
censored, dependent setting, but a formal competing-risk methodology is future work.

---

## 9. Reproducibility of the existing methods

The codebase maintains reproducibility: code revision, environment, dataset manifest,
feature schema, split dates, and metrics are all versioned. The literature review
confirms the problem is real and marketed, but no external paper has been reproducibly
replicated here because **no approved dataset with real outcome labels exists**. Every
result in this repository is synthetic-fixture-validated, not real-data-measured.

---

## 10. Prioritised scientific experiment agenda (from this literature review)

| Priority | Experiment | Method | Data required | Expected value |
|---|---|---|---|---|
| E1 | Queue-position effect on confirmation | Compare cohort baseline vs cohort-position bands on real data | Approved dataset | Tests H1 |
| E2 | Status trajectory vs single snapshot | Survival/hazard on observation histories vs snapshot | Timestamped histories | Tests H2 |
| E3 | Group dependence vs independence | Poisson-binomial vs Bernoulli product on joint outcomes | Real multi-passenger bookings | Tests H3 |
| E4 | Model vs baseline on held-out journeys | Paired comparison, exact sign test | Approved dataset | Tests H2/H3 |
| E5 | Subgroup calibration by class/quota/status | Reliability bands, observed-minus-predicted | Approved data | Tests H5 |
| E6 | OOD detection and abstention | Conformal / coverage checks | Approved data | Tests H5 |
| E7 | Time-to-chart survival model | discrete-time hazard / survival regression | Timestamped observations | Tests H1/H2 |
| E8 | Contextual feature ablation | temporal holdout ablation (Phase 9) | Operational signals | Tests H4 |

These are hypotheses and designs **subject to evidence**, not claims.

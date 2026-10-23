# ADR-0011: Provenance-gated baseline fitting and target-event evaluation

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0003, ADR-0004, ADR-0005, ADR-0007, ADR-0009, `docs/research/EVALUATION_PROTOCOL.md`, `backend/railconfirm/training/`

## Context

ADR-0009 defined what a trustworthy model artifact looks like, but nothing in the
repository could produce one: fitting, splitting, scoring and reporting existed only as
prose in `docs/research/EVALUATION_PROTOCOL.md`. That left three problems open at once.

- **The pipeline could not be verified at all.** No dataset is approved for training, so
  a fit-then-score path that only runs on approved real data cannot be executed today.
  Shipping it untested and claiming it works would be the exact fabrication the
  repository rules forbid, and testing it on synthetic fixtures risks the opposite
  failure: an artifact that looks servable because it passed every technical check.
- **Who decides that training is allowed was never coded.** `data/manifest.py` records a
  decision, and `inference/registry.py` refuses unapproved data, but nothing joined the
  two. A script could have read any CSV and produced a model.
- **The documented metrics were the wrong ones for this product.** Accuracy and AUC do
  not judge a probability claim. Worse, the product's headline number is the probability
  of an *event* — "confirmed", or "confirmed or RAC" — and a score that only measures the
  full five-class distribution never tests the number a user actually reads.

## Decision

**Implement fitting and evaluation with the permission check inside the code, and score
the event the product claims.**

- `training/dataset.py` is the only way training obtains data. It verifies the manifest
  against the file it describes (SHA-256, size, recounted rows), requires an `approved`
  decision with a named `reviewed_by`, `reviewed_on` and rationale, requires
  `source.licence_review_status: approved` **and** `allowed_uses.model_training:
  permitted`, and refuses rows that declare `is_synthetic`. Pipeline testing may opt in
  with `allow_synthetic_for_testing`; that flag is copied into the artifact's
  `is_synthetic`, which the registry then refuses to serve. Fitting on synthetic rows is
  therefore possible, and being fooled by the result is not.
- `training/fitter.py` counts cohorts from the training partition only, requires an
  eligible chronological split (no split, no fit), validates the fitted table through the
  same `normalize_frequency_table` gate inference uses, and always writes
  `promotion: "candidate"`. Fitting never activates anything; activation still needs the
  separate two-gate promotion from ADR-0009.
- `training/metrics.py` scores with proper scoring rules — multiclass Brier and multiclass
  log loss — against a **training-period prevalence** baseline, so a configuration that
  cannot beat "predict the base rate" is visible as exactly that. Abstained rows are
  excluded from the scores and counted separately; a refused prediction is not a wrong
  probability. Segments publish their row counts with a `low_sample` flag instead of being
  quietly averaged.
- `TARGET_EVENTS` maps each prediction target to the outcome classes its event covers
  (`final_chart_cnf` → CNF; `final_chart_cnf_or_rac` → CNF + RAC). Every partition is
  scored twice: as a distribution and as that event, with its own binary Brier, log loss,
  prevalence baseline, skill and reliability bands. When the two verdicts disagree about
  beating the base rate the report states both and says they disagree. On the synthetic
  fixture they do: the distribution loses (0.501038 against 0.500000) while the CNF event
  narrowly wins (0.232664 against 0.250000), which is a result a single headline would
  have hidden.
- `training/report.py` is deterministic — `--generated-on` is required, nothing reads the
  clock — and self-describing: `METRIC_KEYS` is derived from the scorecard's own fields and
  a test fails if a published number has no definition in the report, or a definition
  describes nothing that is published. Conclusions are derived from the measured verdicts,
  not written by hand.
- The CLI (`python -m railconfirm.training fit|evaluate`) accepts only targets that have a
  defined event, and `evaluate` checks the requested target against the artifact's declared
  target rather than assuming `final_chart_cnf`. Artifact and table errors exit 1 with
  `Refused: …` instead of raising a traceback.
- Scoring synthetic rows needed an estimator that would actually produce estimates, so
  `FrequencyTableProvenance` gained `evaluation_only`. It is a memory-only flag: it is not
  a field of `ModelArtifactMetadata`, cannot be written into or read from an artifact, and
  does not override the approval requirement — an unapproved real dataset stays blocked with
  the flag set. Tests assert both properties.

## Alternatives considered

- **Fit with scikit-learn and store a pickle.** Rejected: there is no data to fit a real
  model on, ADR-0009 already removed pickle from the trust boundary, and a smoothed
  contingency table is the reference every later model has to beat.
- **Report accuracy, precision or AUC as the primary metric.** Rejected: none of them
  judges a stated probability, and the product states probabilities.
- **Score only the full distribution and treat the target as metadata.** Rejected: the
  merged target is a different question, and a number that never touches the claim the
  user reads is not an evaluation of that claim.
- **Allow a synthetic-fitted artifact to be served in a labelled demo mode.** Rejected: a
  plausible percentage on a railway page is the failure mode AGENTS.md names, and a label
  a reader cannot see is not a control. The evaluation-only flag lives in memory, where it
  cannot reach a browser.
- **Compute the prevalence baseline from the scored partition.** Rejected: the baseline
  would be fitted on the answer and could not be beaten by anything except leakage.
- **Add rolling-origin evaluation now.** Rejected for this change: it needs a dataset long
  enough for several cutoffs, which is the same blocker as everything else. It stays the
  next evaluation task rather than being written as if it existed.

## Consequences

- When a dataset is approved, fitting and evaluating is one command with a reproducible
  report, and the report will say plainly whether the configuration beat the base rate.
- Every number produced today comes from synthetic rows and is labelled as pipeline
  verification. The pipeline being green is evidence about the code, not about railways.
- Reliability bands are a description. No calibration is fitted or applied, and the report
  adds that limitation whenever `calibrated` is false, which it always is.
- Group-event metrics (`all CNF`, `at least k confirmed`) are still not implemented; ADR-0003's
  dependence warning still applies to any group number the engine derives.
- `--target` for fitting is now constrained by what can be scored, so adding a target
  requires adding its event definition deliberately.
- The gates are tamper-evident, not tamper-proof. Verified against a real fitted artifact:
  as written it resolves `not_promoted` / `no_trained_model`; with `promotion` changed by an
  operator it resolves `data_not_approved` / `no_approved_data` because `is_synthetic` is
  still true; only falsifying `is_synthetic` to false makes it `ready`. Nothing detects that
  last edit, so the artifact's `dataset_id` and `dataset_sha256` are what make the claim
  auditable afterwards, and promotion remains a named human act.

## Validation

- 74 tests in `backend/tests/training/` cover the gate, the fit, the metrics, the CLI and
  the report; the full backend suite is 461 tests at 95.78% branch coverage, with `ruff`
  and `mypy` clean.
- Brier and log-loss values are checked against hand-computed smoothing arithmetic
  (counts 90/0/10/0/0 with `alpha=1` over five classes gives denominators of 105), and the
  event arithmetic is checked separately for both targets.
- Byte stability is asserted by fitting the same fixture twice and comparing the report
  files; target mismatch, unscorable targets and unservable synthetic artifacts are each
  asserted to be refused.
- `python -m railconfirm.training fit … --report …` and `evaluate …` were run against the
  synthetic fixture in a temporary directory outside the repository; the output quoted
  above came from that run and is recorded in `docs/DEVELOPMENT_LOG.md`.
- No run has used approved real data, because none exists. CI is observed on the pushed
  commit rather than assumed.

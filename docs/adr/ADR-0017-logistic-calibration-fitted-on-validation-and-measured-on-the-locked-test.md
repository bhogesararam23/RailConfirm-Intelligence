# ADR-0017: Logistic calibration fitted on validation, embedded only when it helps, measured on the locked test

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0004 (chronological evaluation and calibration policy), ADR-0009
  (artifact trust boundaries), ADR-0011 (target-event scoring), ADR-0013 (the as-of
  cohort rule the calibration is fitted under), ADR-0014 (rolling-origin evaluation),
  `backend/railconfirm/inference/calibration.py`,
  `backend/railconfirm/training/calibration.py`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0004 already set the policy: fit calibration on development/validation data only,
evaluate the layer on the locked test set, and never present an uncalibrated number as
calibrated. Until now the code honoured the last clause by always saying
`calibrated: false`, and `ModelArtifactMetadata` carried a `calibration_method` string
that nothing could fill in.

That left the product's central claim — a probability — with nothing correcting the
baseline's known bias. Laplace smoothing pulls every cohort toward the base rate on
purpose, which is honest about small samples but makes the numbers systematically
shrunken: the earlier rolling-origin run showed the same method beating the base rate at
one cutoff of nine. A reviewer could see the reliability bands and note the miscalibration,
but the tool could not repair it, and a `calibrated: true` claim could be written into an
artifact as an unsupported string with nothing behind it.

Two hazards had to be closed at the same time as the capability was added: an artifact
asserting calibration it does not carry, and a correction that helps on the rows it was
fitted on and is presented as though it had been proven elsewhere.

## Decision

**1. One method, two numbers, reviewable by hand.**

`platt_logistic_v1` — logistic (Platt) scaling of the target event's log-odds,
`p -> sigmoid(slope * logit(p) + intercept)`, fitted by Newton–Raphson from the
validation rows in a fixed order so the same data always yields the same parameters.
Isotonic regression was rejected for this sample size: it needs a step table per band,
overfits sparse strata, and cannot be checked in a minute the way two coefficients can.

**2. The correction moves the event mass and nothing else.**

`apply_calibration()` rescales so the event classes carry the calibrated total, keeping
each group's internal proportions: the split between CNF and RAC inside
`final_chart_cnf_or_rac` was never fitted, so inventing one would present an unmeasured
number as a measured one. The artifact's own limitation says this. A distribution that is
already certain (event mass exactly 0 or 1) is returned untouched rather than clipped
into a fabricated confidence.

**3. One implementation, used by evaluation and serving.**

`score_partition(..., calibration=spec)` and `InferenceEngine` both call
`apply_calibration`, so a measured score and a served number cannot come from different
arithmetic. The estimator stays the same object; the layer sits on top of it and is
carried by the artifact, not by configuration. A served `basis` gains
`calibrated=platt_logistic_v1`, because "cohort SL/GN/WL n=91" alone no longer describes
the arithmetic that produced the number.

**4. The claim is structural, not prose.**

An artifact either carries a `calibration` block — method, target, event classes, slope,
intercept, fitted partition, fitted row count and period — or it declares
`calibrated: false`. `metadata_from_mapping()` refuses a bare claim, a block on an
uncalibrated artifact, a method string disagreeing with the block, a block fitted for a
different target, a negative or non-finite slope, and a partial block. `calibrated` is
read off the block rather than asserted beside it. The JSON layout only *adds* an
optional object whose absence has one meaning, so `artifact_format` stays
`railconfirm.frequency-baseline/2`: `/2` files load unchanged as uncalibrated, and
nothing that was previously accepted changes meaning.

**5. Fitted on validation, refused on validation, then reported against the locked test.**

`fit_and_measure()` walks the same path the single-cutoff report uses. It refuses to write
a layer that does not strictly reduce the **validation** event Brier — "a layer that does
not help on the rows it was chosen for is a decoration, and a decorated number is worse
than an honest uncalibrated one" — and it always reports the locked-test movement in the
conclusion, phrased whichever way it goes. The headline validation/test scorecards in a
report built from a calibrated run carry `calibration_applied: true`, with the
uncorrected numbers kept beside them in the `calibration` section, so nothing is
compared against a baseline the deployed model never faced.

**6. Degenerate evidence is refused rather than fitted.**

`fit_platt()` raises when the partition has fewer than `--calibrate-min-rows` scored rows
(default 50), carries one label only, has no spread in the predicted probability, or drops
below the floor once certainty rows (which carry no log-odds) are excluded. Perfectly
separable evidence collapses the Hessian and is refused with the reason named: the
maximum-likelihood slope runs away, so any finite answer printed would be an artefact.
Probabilities outside `[0, 1]` are treated as a scoring bug, not an input to smooth over.

**7. Subgroup calibration is measured nowhere, and says so.**

The protocol permits subgroup calibration claims only with counts; this implements none,
so every calibrated report carries a limitation stating that per-class, per-quota and
per-status calibration are not evaluated. Reliability bands remain a description.

**8. Calibration changes the numbers, not the trust gates.**

A calibrated artifact is still a candidate until a human promotes it, and a synthetic one
is still unservable whatever it contains: the promotion, approval and synthetic-provenance
checks run before a distribution is ever produced. Verified live on 2026-10-24: the
synthetic calibrated fixture resolved `not_promoted` as a candidate and `data_not_approved`
after its promotion field was edited to `approved_for_local_use`.

**9. The limitation list is edited, not appended to.**

The base artifact carries "Smoothed historical frequencies, not a trained or calibrated
model." `with_calibration()` replaces that sentence rather than adding beneath it: the
limitations are what a reader of a served report reads, and a list that names its
calibration layer in one line and disclaims calibration in the next is a list that has
stopped describing the artifact. The replacement keeps "still cohort counts, not a trained
model", because a fitted slope does not turn frequencies into a model.

## Alternatives considered

- **Let an artifact assert `calibrated: true` with a method string (the previous shape).**
  Rejected: exactly the unbacked claim ADR-0009 exists to prevent.
- **Fit on train, or on train+validation.** Rejected: ADR-0004, and a correction tuned on
  the rows that produce the headline score flatters itself.
- **Fit on the scored partition because the data is scarce.** Rejected: that is the case
  the refusal path exists for. A thin file leaves the artifact uncalibrated and says so.
- **Temperature scaling.** Rejected here for being one parameter over quantities
  (per-class logits) that a smoothed frequency table does not have.
- **Per-class Platt, then renormalise.** Rejected: it invents the within-event split the
  event-only correction explicitly refuses to claim.
- **Isotonic regression.** Rejected for these sample sizes; revisit with real data volume
  under its own ADR and a monotonicity test.
- **Refuse calibration below some minimum file size instead of a minimum scored row
  count.** Rejected: abstentions mean rows and scored rows differ, and the fit only sees
  the latter.

## Consequences

- `ARTIFACT_FORMAT` stays `/2`; an artifact carrying a calibration block loads only under
  a build that knows the method, and the registry still refuses one that was fitted from
  synthetic or unapproved rows.
- Reports grow a `calibration` section and a summary line; the `calibration_applied`
  field on a scorecard is structural metadata, so the report's "every metric has a
  definition" test keeps its meaning.
- Fitting costs one extra pass over the validation partition plus a handful of Newton
  steps; a 240-row fixture fits and measures in well under a second.
- Operators now have a real choice at `fit` time, and a wrong one is visible: `--calibrate`
  either prints the before/after movement or refuses and writes nothing.
- A calibration is per target. Reusing an artifact under another target is already blocked
  by the load-time target check, and the block checks it again.
- The correction is fitted on one window. Whether it holds over later periods is a
  rolling-origin question (ADR-0014) which currently refits tables and does not apply any
  calibration layer, and the origin report now states that explicitly.

## Validation

- `tests/inference/test_calibration.py` — 28 tests: logit/sigmoid inverses and edge
  clipping; the identity spec leaving a table alone; a doubled slope moving the event mass
  to the hand-computed value while outside-class ratios hold; the merged event moving as
  one mass; certainties untouched; abstentions returned unchanged; the `basis` marker not
  stacking; every `CalibrationSpec`/`spec_from_mapping` refusal.
- `tests/inference/test_engine_artifact.py` — 5 serving tests: an identity calibration
  reproducing the raw 71/110 while marking the basis; a flat calibration producing exactly
  0.5 with every other class scaled by the hand-computed (1-0.5)/(1-p) and the five
  probabilities summing to 1; a group estimate built from calibrated members; the
  uncalibrated artifact still carrying its limitation; an abstention not rescaled into a
  number.
- `tests/training/test_calibration.py` — 40 tests: a flat fit recovering zero slope
  exactly, an already-calibrated table recovered within tolerance, systematic
  overconfidence pulled down, determinism under reversed row order, all refusal paths
  (too few rows, one label, no spread, certainties dropped below the floor, out-of-range
  prediction, separable Hessian collapse, unknown target, invalid `min_rows`),
  `fit_and_measure` against the validation partition only with the locked-test effect
  reported whichever way it goes, artifact round-trip of the block, the calibrated
  limitation list replacing the uncalibrated sentence, trust gates still refusing a
  promoted synthetic calibrated artifact, report wording in all three
  claim/measurement combinations, byte-identical reports, the two CLI paths, and two
  guards asserting every printed report line and refusal message survives a cp1252
  console — the bug that only a real terminal shows.
- `tests/inference/test_registry.py` — 16 added artifact cases for the block: bare claim,
  round-trip, nine unusable parameter combinations, three partial blocks, a block on an
  uncalibrated artifact, and a method disagreeing with its block.
- Live runs, all on labelled synthetic fixtures (`docs/DEVELOPMENT_LOG.md` holds the
  commands), re-run on 2026-10-24 after the limitation replacement: `fit --calibrate
  --calibrate-min-rows 10` wrote an artifact whose block
  records `slope 3.124728, intercept 1.016226` from 40 validation rows, with the report
  stating `validation event Brier 0.240085 -> 0.239898, locked test 0.23996 -> 0.239487
  (helped)`; `evaluate` printed `calibration applied (platt_logistic_v1)`; the default
  50-row floor refused the same file's 40-row validation partition with exit 1 and wrote
  no artifact; a 900-row version of the fixture refused differently — `The fitted slope is
  negative (-13.829494)` — which is the refusal working on real variation, not only in a
  test; a temporary promoted copy served `p_cnf 0.391304348` where the raw table
  gives `0.385416667`, matching the hand-computed correction with the basis noting
  `calibrated=platt_logistic_v1`; and `ModelRegistry.resolve()` on the fitted file answered
  `not_promoted` as written and `data_not_approved` once its promotion field was edited to
  `approved_for_local_use`, so the synthetic provenance gate is what stopped it, not the
  candidate flag alone.
- No empirical railway claim: the improvement measured here is on synthetic rows, and it
  is small because the fixture gives the cohorts nearly the same outcome mix. The
  mechanism is what was built; the number is not evidence.

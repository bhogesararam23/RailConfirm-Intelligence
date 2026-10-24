# ADR-0020: A second estimator — cohort cells split by as-of queue position

- **Status:** Accepted
- **Date:** 2026-10-24
- **Decision owner:** Project maintainer
- **Related:** ADR-0011 (fitting gate and target-event scoring), ADR-0013 (the single as-of
  rule and the artifact that must declare its own contract), ADR-0016 (group estimates read
  whatever the passengers get), ADR-0017 (the calibration layer applies to either model),
  ADR-0018 (decay, which must judge the model the artifact declares), ADR-0019 (segment
  gaps, now measurable per estimator), ADR-0021 (the comparison that decides promotion),
  `backend/railconfirm/inference/queue.py`, `backend/railconfirm/inference/artifacts.py`,
  `backend/railconfirm/data/preprocessing.py`

## Context

`FEATURE_COLUMNS` has declared eight derived features since schema 3.0.0 and the served
estimator has read three of them. ADR-0013 fixed the report so it could no longer claim
otherwise — but the honest fix exposed a real gap rather than closing it: the as-of queue
position is derived, validated, null-safe, and used by nothing.

For a waitlisted reservation that is the most information in the record. A flat cohort rate
answers a passenger first in the queue and a passenger two hundred deep with the same number,
which is not a model of a queue but an average over one. The evaluation protocol has listed
"status-and-time baseline using current normalized status, queue position and time remaining"
as the second baseline since Phase 3, and roadmap Phase 4 is named after calibration of
candidates that do not exist yet.

Building a candidate before an approved dataset exists is the same deliberate choice ADR-0014
and ADR-0018 recorded: when real data arrives, the first run is the run that gets quoted, and
the machinery that judges it has to exist first, with its refusals already in place.

## Decision

**1. A second estimator, not a second branch inside the first.**

`CohortPositionBaseline` is its own class in `inference/queue.py`, keeping the same
`estimate(passenger_id, asof_status, class_code, quota_code, asof_position)` shape as the
frequency baseline. Both satisfy the `ProbabilityEstimator` protocol, which is what the
engine, the registry and the evaluator depend on. One class with an `if position_table` flag
inside would let a single artifact mean two different things depending on which optional
field happened to be populated.

**2. Band widths are fixed and doubling, never quantiles of the training file.**

Bands are 1, 2-3, 4-7, 8-15, 16-31, 32-63, 64-127, 128+. A cut derived from the data moves
when the data moves, so a served probability would depend on which rows happened to be in the
fitting period, and two artifacts fitted a week apart would not be comparable. Fixed widths
also mean a band's meaning is stable enough to talk about in a report.

**3. The position comes from the as-of status, and from nowhere else.**

`asof_statuses()` already resolves the status held at the time being estimated; the position
is taken from that same parsed record. The fitter, `score_rows` and the engine all read
`asof.position`, so the value that keys the cohort and the value that bands it come from one
source. This is ADR-0013's rule applied one field wider: an estimator keyed on one column and
banded on another would be measured by a code path the product does not run.

**4. A band too thin to carry a rate does not get one.**

The cohort answers instead, and the basis says so: `band=8-15 n=1 below the 2-row band floor,
cohort rate used`. The band floor (`min_band_rows`, default 2) is deliberately far below the
cohort floor, because bands split a cohort: requiring 25 rows per band would leave positions
almost unused and the artifact would claim a model that answers flat. A single-row cell
cannot express a rate — it expresses one outcome.

**5. An absent position stays absent.**

A status written without a position token (`GNWL`) yields `None`, is answered from the cohort,
and the basis records `as-of queue position unavailable`. Banding it as position 1 would
assign the shallowest, most confident queue in the table to the reservations about which the
source said least — the same fabrication the feature schema refuses for `lead_days` and
queue positions.

**6. The artifact declares which arithmetic produced it, and the loader believes nothing else.**

A position artifact carries `artifact_format = railconfirm.cohort-position-baseline/1`,
`estimator = cohort_position_baseline`, `features_used` including `asof_position`, a
`bands` block keyed `CLASS|QUOTA|STATUS|BAND`, and its `min_band_rows`. Frequency artifacts
stay at `/2` and mean exactly what they meant. `load_artifact()` refuses: a format that
disagrees with the estimator, an estimator it does not know, band cells on a frequency
artifact, a position artifact with no band cells, a three-part band key, a malformed band
cell, and `features_used` that does not match the declared estimator. `build_artifact_document`
refuses the same mismatches on the write side, so a confusing file cannot be produced either.

**7. Every construction goes through the artifact.**

`LoadedArtifact.estimator()` builds the declared model with the artifact's provenance (the
serving path), and `estimator_for(provenance)` builds the same model with a caller-supplied
provenance so offline evaluation can use `evaluation_only` on synthetic fixtures. Nothing
external may assemble an estimator from a cohort table by hand.

That rule was earned, not theoretical: the decay path initially built every artifact with the
frequency builder, so a position artifact was evaluated as if it had no band cells and
reported **identical numbers** to the flat model on the same rows. The regression test
(`test_decay_scores_the_model_the_artifact_declared_not_the_one_that_was_handiest`) fails
against that version. The CLI `evaluate` path had the same shape and was fixed the same way.

**8. Trust gates, calibration and group arithmetic are unchanged.**

Provenance still decides whether a table may estimate; a synthetic or unapproved artifact
abstains from either estimator. `apply_calibration` moves the target event's mass and applies
to whichever model produced it. Group outcomes read the passengers they are given, so they
inherit the position model without change. Promotion still needs a human, a candidate flag
and an approval field.

## Alternatives considered

- **Optional bands inside the existing `/2` artifact.** Rejected: an artifact whose numbers
  depend on whether an optional block is present is not a reviewable object, and the format
  string would stop telling anyone which model they are looking at.
- **Position bands from training quantiles.** Rejected: see Decision 2 — the cut points would
  move with the file, which is exactly what makes two artifacts non-comparable.
- **A regression on position and lead days (logistic or gradient boosting).** Deferred, not
  rejected: it needs a dependency and real data, ADR-0007 keeps this build local-first, and a
  fitted model with no approved dataset to validate it against is how unverified numbers get
  into a product. The banded cohort model is the strongest claim the current evidence supports.
- **Band floor equal to the cohort floor (25).** Rejected: bands split cohorts, so with real
  cohort sizes most positions would never be used and the artifact would declare a model that
  answers flat. The floor is recorded in the artifact so a reviewer can see what was allowed.
- **Filling a missing position with the cohort median.** Rejected: that is inventing data about
  a reservation whose queue depth the source did not record.

## Consequences

- Two artifact shapes now exist, and a promotion review has to read `estimator` and
  `artifact_format` before reading any number. The registry, decay and the report all refuse a
  mismatch, so an accidental mix cannot produce plausible output.
- The report line "read by the estimator" becomes load-bearing: it is derived from
  `features_used`, so a position artifact now credibly claims `asof_position` while the
  frequency artifact still lists queue positions as derived-but-unread.
- `min_band_rows` joins the settings that travel with an artifact, because it changes the
  served number. It is omitted from frequency artifacts rather than written as noise.
- On the labelled synthetic fixture the position model is **worse** than the flat one —
  locked-test event Brier `0.275914` against the flat model's `0.239960`, because the balanced
  fixture's labels are deliberately independent of queue position. That is the expected result
  for a model that reads a signal the fixture does not contain, and it is why ADR-0021 exists:
  whether the position model wins is an empirical question that has never been asked of real
  data.
- Decay now reports the position model's own drift: over two horizons from a cutoff at
  2026-04-08, event Brier moved `0.246575 → 0.275914` (+0.029339) and beat the frozen base
  rate in 0 of 2 — versus the flat model's `-0.000125` and 1 of 2 on the same rows. Two
  different models, two different curves, which is the whole point.
- No railway claim. Both numbers come from rows that declare `is_synthetic`.

## Validation

- `backend/tests/inference/test_queue_model.py` — 52 tests: the fixed doubling band boundaries
  (12 parametrised positions), an absent position staying absent, a non-positive position
  refused rather than clamped, band-level rates checked by hand against add-alpha smoothing,
  the band floor falling back to the cohort **and saying so in the basis**, a configurable
  floor, `None` position answered from the cohort, the distribution still summing to one over
  all five classes with unseen classes keeping smoothed mass, broad-cohort fallback that stays
  position-aware, missing cohort and thin cohort abstaining, unsupported and unmappable
  statuses, the provenance gate abstaining for every position, an unloaded table abstaining,
  band-table validation (empty, unknown outcome, negative, fractional, boolean and zero-sum
  cells, colliding keys, three-part keys), settings validation, and the parity test that the
  frequency baseline returns byte-identical results whether or not a position is supplied.
- `backend/tests/inference/test_queue_artifact.py` — 21 tests: the written payload declaring
  the position format and band block, frequency artifacts written unchanged with no band block,
  deterministic bytes, refusals at write for bands-on-frequency and no-bands-on-position, load
  round-trip of both tables, dispatch building the declared class (and answering from the band),
  format/estimator mismatch in both directions, unknown estimator, `features_used` mismatch in
  both directions, missing and misplaced band blocks, malformed band cells and three-part keys
  refused at load, the as-of cohort rule still required, promotion and synthetic gates
  estimator-agnostic, and the registry serving the position model from a promoted artifact.
- `backend/tests/training/test_queue_pipeline.py` — 21 tests: band cells per cohort with
  hand-checkable positions, band cells summing to their cohort, a position-less row counted in
  the cohort and no band, `with_bands=False` changing nothing, fits through the real gate
  declaring estimator/features/band floor and the position-specific limitation text, an unknown
  estimator refused rather than defaulted, band cells drawn from the training partition only
  (asserted equal to a direct refit of that partition, and that a locked-period band cell does
  not exist), scoring passing the same as-of position a request supplies, the frequency model
  unchanged whatever the position, artifacts round-tripping into the estimator that scored
  them (with the synthetic serving gate still refusing to answer a passenger), decay judging
  the declared model rather than the flat one, decay's contract check refusing a stale feature
  declaration, the report crediting `asof_position` to the model that reads it, and three CLI
  cases including `evaluate` distinguishing the two artifacts.
- Live runs on labelled synthetic fixtures (full transcript in `docs/DEVELOPMENT_LOG.md`):
  `fit --estimator cohort_position_baseline` wrote 4 cohorts and 12 position cells from 160
  training rows; `evaluate` gave the position artifact validation event Brier `0.246575` and
  locked test `0.275914` against the flat artifact's `0.240085` and `0.239960` on the same
  rows; `decay` on the position artifact reported the drift quoted above.
- Gates: `pytest tests/` → 918 passed; `ruff check railconfirm/ tests/` → clean; `mypy` → no
  issues in 43 source files; `scripts/check_repository_hygiene.py` and the frontend suite —
  results recorded in `docs/DEVELOPMENT_LOG.md`.

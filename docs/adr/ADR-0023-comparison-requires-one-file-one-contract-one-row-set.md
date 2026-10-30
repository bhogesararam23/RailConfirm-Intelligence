# ADR-0023: A model comparison must compare one file, one contract and one set of rows

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0021 (the paired comparison this refines), ADR-0013 (the as-of cohort
  rule and mapping version), ADR-0022 (calibration identity),
  `backend/railconfirm/training/compare.py`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0021 established that two models may only be compared if they were fitted on "one
split" and required the partitions to agree by name, boundaries and row count. The
implementation of that rule, `_require_comparable`, checked the estimator, the target, the
partition summary tuples and the training-window prevalence — and nothing else.

Read against the code, that left five ways to publish a comparison that was not one:

- **The scored file was never checked.** `run_model_comparison(dataset, ...)` scores on
  `dataset` and stamps `dataset.dataset_id` and `sha256` into the report, but neither
  model's metadata was compared with the argument. A model fitted on one file could be
  scored against another and the result published under a dataset one of them never saw.
- **A file name is not a file.** Nothing compared the two models' own `dataset_id` and
  `dataset_sha256`, so two models from different exports were comparable whenever their
  partitions happened to line up.
- **Matching dates and counts are not matching rows.** The scoring loop walks
  `baseline.split.val` / `baseline.split.test` for *both* models. Two splits that record the
  same window and the same row count but hold different reservations (a re-export, a
  deduplication, a different tie-break at a date boundary) would silently publish the
  candidate's numbers from frames it never saw — and pairing by position would then compare
  the wrong reservation against the wrong reservation.
- **Contract differences were invisible.** `status_mapping_version`, `cohort_semantics`,
  `outcome_classes` and `feature_schema_version` all change what a row *means*. Two models
  reading one file under different mappings are not two models of one question.
- **Smoothing was invisible.** `laplace_alpha` and `min_sample_threshold` change the served
  number materially. A delta measured across both a model change and a smoothing change
  cannot be attributed to either.

A separate, smaller defect sat in the pairing itself: `pair_scores` built
`{row.position: row}` and kept the last row for a repeated position, so a duplicated
position silently reduced the paired count and paired two reservations, and a `rows_total`
smaller than the rows answered produced a negative `neither_scored`.

## Decision

**1. The report's dataset is a check, not a label.**

Both models' `dataset_id` and `dataset_sha256` must equal the `ApprovedDataset` being
scored. A model from another id is refused with the two ids; a model from another content
under the same id is refused with both hashes, because that is the case a name check misses.

**2. The two models must have been fitted from the same file.**

`_require_comparable` compares the `(dataset_id, dataset_sha256)` pair, not the id alone.

**3. One contract, or no comparison.**

`status_mapping_version`, `cohort_semantics`, `outcome_classes` and `feature_schema_version`
must match. Each refusal names the field and why the difference is not the model.

**4. One change at a time, including smoothing.**

`laplace_alpha` and `min_sample_threshold` must match. `min_band_rows` is excluded: it is
only read by the position estimator, and the same-estimator rule already prevents comparing
two position models.

**5. The partitions must hold the same rows, in the same order.**

After the summary check, each partition's rows are fingerprinted — the row count plus a
digest over the frame's columns in sorted order and its rows in stored order. Order is part
of the digest because pairing is by position: the same reservations in a different order
would be paired against the wrong ones. A mismatch is refused rather than repaired, because
the available repair — scoring each model on its own frames — requires a per-row identity
the frame does not carry.

**6. Pairing refuses an ambiguous alignment.**

`pair_scores` raises on a repeated position and raises when `rows_total` is smaller than the
rows answered. Both are invariant violations that would publish an impossible count.

**7. An explicit target must be the target both models were fitted for.**

`run_model_comparison(..., target=...)` may no longer select an event neither artifact
answers; the scores would describe a question the comparison is not about.

## Alternatives considered

- **Compare a per-row identity column instead of a frame digest.** Rejected: the row
  contract has no single primary key (`booking_group_id` is optional, and a group holds
  several passenger records), so the digest over all columns is the honest identity — and
  it fails closed, since a column added in one frame changes the digest.
- **Score each model on its own frames and pair by a derived key.** Rejected: it needs an
  identity the data does not guarantee, and it would silently accept two different row sets
  as a comparison.
- **Warn instead of refuse on smoothing differences.** Rejected: the verdict is a binary
  promotion decision; a warning beside a `candidate` outcome reads as a footnote, not as a
  refusal.
- **Require equal `min_band_rows` as well.** Rejected as meaningless for the frequency
  table, which never reads it.

## Consequences

- A comparison between artifacts produced by two different dataset exports is now refused;
  the operator must refit both from one file. That is the intended cost.
- A comparison whose splits line up on dates and counts but not on rows is refused before
  any scoring, so the numbers in a published report always came from frames both models
  were fitted around.
- `pair_scores` can now raise on malformed input where it previously returned a plausible
  count. The pairing contract is explicit rather than best-effort.
- Nothing about the verdict rule changed: the locked-period requirement, the coverage
  condition and the paired win/loss condition are untouched. This ADR only makes more
  conditions necessary, never fewer, and does not make promotion easier.

## Validation

- `tests/training/test_compare.py` covers: a model fitted on another file with the same id
  (refused on hash), a model fitted on another dataset id, a parametrized contract/smoothing
  mismatch across six fields, a reordered partition whose summary still matches (refused on
  rows), an explicit target the models were not fitted for, a repeated position, and a
  `rows_total` below the rows answered.
- The existing same-split, same-estimator, same-target, prevalence and verdict tests are
  unchanged and still pass, which shows the new checks add refusals without removing the
  comparability the earlier tests established.

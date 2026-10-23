# ADR-0013: One as-of cohort rule and a dataset gate that enforces eligibility

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0004 (temporal evaluation), ADR-0009 (artifact trust boundaries),
  ADR-0011 (provenance-gated fitting), `backend/railconfirm/data/validator.py`,
  `backend/railconfirm/data/preprocessing.py`, `backend/railconfirm/training/`,
  `docs/data/DATASET_INTAKE_CHECKLIST.md`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

Two audit findings, both of which made the pipeline look more capable than it was.

**The gate checked the wrong verdict.** `railconfirm/training/dataset.py` called
`validate_dataset()` and then tested `report.structurally_valid`, which means only
"the file parsed and at least one row is interpretable". It handed on the original
frame. So a 32-row file, a single-outcome file, or a file whose dates cannot be split
chronologically was eligible to be fitted on, and rows the validator had explicitly
rejected — exact duplicates, contradictory labels, censored outcomes, unparseable
dates, observations after the journey, unmappable statuses — were still in the frame
that `fit_cohorts()` and `score_partition()` read. The report said 9 rows were
rejected; the fit used them anyway. `docs/technical/STORAGE_MODEL.md` and the intake
checklist both describe a stricter gate than the code implemented.

**Fit and serve disagreed about which reservation a row describes.** The fitter keyed
cohort cells by `initial_status`; `score_partition()` and the engine queried with
`current_status` when it existed. A booking taken at `GNWL/40` and observed at `RAC 2`
was counted in the WL cell and looked up in the RAC cell, so every evaluation number
described a lookup the product would never perform, and any artifact whose cohorts
came from the booked status answered observed-status requests with counts from a
different population. Nothing in the artifact said which column its keys came from, so
the mistake was invisible at load time. Separately, the artifact and the report listed
the eight derived features as if the baseline read them; it reads three values.

## Decision

**1. The validator decides once, and its decision is the data.**

`assess_dataset(frame)` returns `(report, usable_frame)` where the frame holds only the
rows that passed every row-level check. `validate_dataset()` stays as the report-only
wrapper. One pass produces both outputs, so the counts cannot drift away from the rows.
The frame's index is reset internally, which also removes a latent failure: a caller
supplied index with duplicate labels made the per-row duplicate lookup ambiguous.

**2. Training requires technical eligibility, not just structure.**

`load_approved_dataset()` now refuses a dataset with any eligibility finding, quoting
the findings. The order of blockers is deliberate: manifest verification, then
structural validity, then the human permission rules (`assert_trainable`), then
eligibility — a file whose licence says "rejected" is reported as rejected rather than
as a quality problem.

**3. One eligibility relaxation exists, it is synthetic-only, and it is written down.**

`allow_synthetic_for_testing` may fit below the thresholds *only* when rows declare
`is_synthetic`. The relaxation is recorded as `ApprovedDataset.eligibility_relaxed` and
appears in the artifact's `limitations`, so the fitted file itself says it did not meet
intake. A non-synthetic file gets no relief: passing the flag changes nothing, which is
the point of tying it to the row marker rather than to the argument.

Synthetic detection still reads the whole file, before filtering, so a marker that
lives only on a rejected row cannot make the remaining rows look like real evidence.

**4. The as-of status has one definition.**

`preprocessing.asof_statuses(frame)` is the rule: `current_status` when the source
recorded one, otherwise `initial_status`; a blank later look means no later look, not
an unknown status, while an unmappable value stays UNKNOWN and abstains. Fitting,
scoring and serving all call it — the served request supplies its as-of status through
`StatusObservation`, which is the same quantity flattened into a column.
`extract_features()` now derives `asof_normalized`/`asof_position` from it, so
`FEATURE_SCHEMA_VERSION` goes to **3.0.0**: the meaning and nullability of those columns
changed, and an artifact must be rejected rather than misread.

Cohort keys come from `baseline.cohort_key()`, used by the fitter, the artifact
decoder and the estimator's lookup, so normalisation is not reimplemented per site.

**5. An artifact declares what it reads and what its keys mean, and load enforces both.**

`ModelArtifactMetadata` gains `features_used` (`class_code`, `quota_code`,
`asof_normalized`) and `cohort_semantics` (`asof_status_v1`). `metadata_from_mapping()`
requires both to match this build's declarations, so a table keyed by the booked status
is refused with an explanation instead of serving wrong-population numbers. That
changes the JSON layout, so `ARTIFACT_FORMAT` becomes
**`railconfirm.frequency-baseline/2`**, superseding the identifier recorded in
ADR-0009; `/1` files, which declare neither field, are refused.

**6. Reports state the gap between the schema and the estimator.**

The evaluation report publishes `used_by_estimator`, `not_used_by_estimator`,
`cohort_semantics` and which status columns the fit had, and the fitted artifact carries
a limitation naming the features it does not read.

## Alternatives considered

- **Filter inside `fit_cohorts()` and `score_partition()` separately.** Rejected: two
  implementations of eleven row-level rules drift, and the report would then describe a
  set of rows nobody uses.
- **Let `allow_synthetic_for_testing` relax eligibility for any file.** Rejected: the
  flag is an argument, and an argument can be passed by accident. Tying the relaxation
  to `is_synthetic` keeps the bypass unreachable without labelling the data as fake,
  which is what makes the resulting artifact unservable.
- **Keep keying cohorts by `initial_status` and serve from it.** Rejected: the product
  answers "given what we can see now, what will the chart say". Booking-time status is
  one observation of it, not the definition.
- **Add the as-of column to the estimator's signature only.** Rejected: the failure was
  a shared *meaning*, so the fix is a shared function plus a declaration that can be
  checked at the boundary.
- **Silently accept artifacts with no `cohort_semantics`.** Rejected: the whole point is
  that an undeclared key rule cannot be defended.

## Consequences

- Fits that used rejected rows now see fewer rows, and small files that used to fit are
  refused. Both are the intended correction, not a regression: a `fit` run prints how
  many rows validation kept and why the rest were rejected.
- Existing `/1` artifacts must be refitted. There are none in the repository — no
  dataset has been approved, so nothing promoted can be orphaned.
- Group outcomes and any later model inherit the as-of rule from
  `asof_statuses()`; a model that needs more than the cohort key reads the same feature
  frame.
- `features_used` is a per-estimator declaration. A future estimator with a wider
  feature set is a new `ESTIMATOR_*` value plus its own vocabulary, not a widened
  constant here.
- The synthetic pipeline path is unchanged in volume — it gains one recorded limitation.

## Validation

Backend: 563 tests, 96.03% branch coverage, `ruff` and `mypy` clean locally.

- `tests/data/test_validator.py` — `assess_dataset` returns only surviving rows, keeps
  neither side of a contradiction, tolerates a duplicate-labeled caller index, and
  agrees with `validate_dataset` on the verdict.
- `tests/training/test_dataset_gate.py` — 24 parseable rows are refused as technically
  ineligible with the findings quoted; the same file is still refused with the synthetic
  flag when it does not declare synthetic rows; rejected rows never appear in the frame
  the fit reads; a synthetic marker on a rejected row still marks the file.
- `tests/training/test_cohort_parity.py` (16 tests) — the moved-status, blank-look,
  unmappable-value, changed-position and broad-fallback cases are asserted in fitting,
  in scoring and through the served estimator, including a whole-fixture run where
  coverage is 100% because the fitted keys and the query keys agree.
- `tests/inference/test_registry.py` — an artifact declaring `initial_status_v1`, a
  wrong `features_used` list, or omitting either field is refused at load.
- Live check: `uvicorn` on port 8041 with a temporary, non-committed artifact fitted
  from the labelled synthetic fixture. Two passengers booked at `GNWL/40` — one observed
  at `RAC 2`, one unchanged — were answered from `cohort=SL/GN/RAC n=40`
  (`p_cnf 0.4666667`) and `cohort=SL/GN/WL n=80` (`p_cnf 0.4823529`), matching the
  hand-computed smoothed cells; a third with `MYSTERY/4` abstained with
  `unknown_status`. Before this change both would have read the WL cell.
- No empirical claim: nothing here was fitted or scored on approved railway data, and
  the synthetic numbers do not describe railway behaviour.

# ADR-0025: A band cell must be reachable — the label must be one the banding rule returns, and the cohort must exist

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0020 (the cohort-position estimator and its fixed bands), ADR-0013 (the
  as-of cohort rule), `backend/railconfirm/inference/queue.py`,
  `backend/railconfirm/inference/artifacts.py`,
  `docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`

## Context

ADR-0020 split each cohort by the as-of queue position into fixed doubling bands and made
the artifact declare which estimator produced it, so a cohort table could never be answered
by band arithmetic. The band table's own keys were never checked against the code that
produces them. `normalize_band_table` stripped and uppercased the four parts and refused an
empty one; that was all. Three consequences followed.

1. **An unreachable label loaded.** `position_band` returns one of `1`, `2-3`, `4-7`,
   `8-15`, `16-31`, `32-63`, `64-127`, `128+`. A cell keyed `1-3` — a plausible misreading
   of the first two cuts — or `128` — the open-ended band written as a ceiling — loaded,
   was counted as position evidence, was written back into the artifact, and could never be
   read by a request. `band_count` overstated how much position evidence a file held.

2. **A band key could name a status the estimator cannot look up.** The cohort table
   validates its status part against the normalized status categories plus the broad `ALL`
   cohort. The band table validated nothing, so `("SL", "GN", "WAITING", "1")` was a legal
   key. `_lookup_cohort` can only return `asof_status.normalized.value` or `ALL`, so such a
   cell is unreachable for exactly the same reason.

3. **An orphan cell loaded.** `estimate` resolves the cohort first and only then asks for a
   band cell under the resolved cohort key. A band cell whose cohort has no row is therefore
   unreachable — and a band table consisting only of such cells passes the "carries band
   cells" check, making the artifact a frequency model that declares itself position-aware.
   Nothing in the loader compared the two tables.

The failure mode is uniform: a file that looks more informative than it is, and a
`band_count` that says so.

## Decision

1. **The accepted band labels are derived from the banding rule.** `_validate_band_key`
   refuses any label outside `band_labels()`, and `band_labels()` is the same tuple that
   `position_band` falls through. A test asserts the set of labels `position_band` returns
   over a long run of positions is exactly `set(band_labels())`, so a change to the cuts
   cannot leave a stale literal list behind.

2. **The cohort part of a band key is validated as a cohort key.** `validate_cohort_key`
   is now public in `baseline.py` (it was `_validate_cohort_key`) and does the status check
   the cohort table already relied on. `_validate_band_key` calls it on `raw_key[:3]`, so the
   two tables cannot disagree about what a status is.

3. **A band cell with no cohort row is refused, and the refusal is in three places.**
   `validate_band_cohorts(cohorts, bands)` refuses any band key whose first three parts are
   absent from the cohort table. It runs in `CohortPositionBaseline.load_tables` (before
   either table is installed, so a refused load leaves the estimator unloaded),
   in `build_artifact_document` (so the writer refuses what the loader would), and in
   `load_artifact` (so the file surfaces as `model_artifact_invalid` rather than as a
   surprise at the first request).

4. **No new format version.** The refusals reject files that could never have answered a
   request; a file that loaded and served before still loads and serves. Bumping the format
   would force a refit to recover behaviour that is unchanged.

## Alternatives considered

- **Accept an unreachable label and ignore it at lookup.** Rejected: silently keeping dead
  cells is what made `band_count` misleading, and a reader of the artifact cannot tell a
  dead cell from a live one.
- **Map a near-miss label onto the nearest real band** (`1-3` → `2-3`). Rejected: it
  rewrites the artifact's own claim about what it measured. If the table was fitted with
  different cuts, the numbers belong to a different model.
- **Check only at load, not at write.** Rejected: the writer is where the mistake is made,
  and a fit that produced orphan cells would otherwise succeed and fail later, after the
  artifact was on disk and the process exited.
- **Require the cohort row to be above `min_sample_threshold` too.** Rejected: that
  threshold lives on the artifact and is a serving policy, not a property of the table; a
  thin cohort is already handled at request time by the documented abstention.

## Consequences

- `tests/support/artifacts.py` carried orphan cells: `POSITION_BANDS` had `ALL` band cells
  but `COHORTS` had no `("SL", "GN", "ALL")` row. The fixture was wrong, not the rule; it
  now declares `POSITION_COHORTS`, the exact cells plus the broad cohort its bands refine,
  and is used only when a band table is requested. Frequency-artifact fixtures are unchanged.
- A hand-assembled position artifact must now carry a cohort row for every band it
  refines. Fit-produced artifacts already do: `fit_cohorts(with_bands=True)` writes the
  exact and broad band cells from the same row that populates both cohorts.
- `validate_cohort_key` and `validate_band_cohorts` are public names. Neither changes any
  served number.
- This says nothing about whether the position model beats the flat one. That remains the
  paired comparison of ADR-0021, still unanswered for real data.

## Validation

`backend/tests/inference/test_queue_model.py` covers eight unreachable labels, every
reachable label, the label-set equality with `position_band`, an unlookuppable status, an
empty band, an empty class, and an orphan cell that leaves the estimator unloaded.
`backend/tests/inference/test_queue_artifact.py` covers the same two refusals through the
JSON reader and the writer. The full backend suite, Ruff and mypy were run before the change
was committed.

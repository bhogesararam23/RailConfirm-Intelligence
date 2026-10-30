# ADR-0024: Group arithmetic refuses invalid input instead of clamping it, and checks its own figures

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0003 (joint group outcomes), ADR-0016 (the Poisson-binomial
  distribution and the comonotonic bounds this refines), `backend/railconfirm/inference/group.py`,
  `backend/railconfirm/domain/prediction.py`, `docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`

## Context

ADR-0016 introduced two ways to answer "how does this booking resolve": the exact
Poisson-binomial distribution under an independence assumption, and the comonotonic
queue-clearing bound. Both return the same `GroupOutcome` shape, and both are labelled only
in free-text `assumptions` and a `method` string. That shape is what made four defects
individually cheap to fix and collectively expensive to leave:

1. **The clamp ran before the check.** `compute_poisson_binomial_pmf` applied
   `min(1.0, max(0.0, p))` and only then tested the value. A marginal of `1.5`
   contributed `1.0` — certainty — and so did `float("nan")`. Neither raised, and neither
   left any trace in the output that the input had been outside the space a probability
   lives in.
2. **An unknown method silently became the independence baseline.**
   `compute_group_outcomes(..., method=...)` compared only against
   `"queue_dependent_comonotonic"` and treated every other string as the independence
   branch. `method="queue_dependent"` — the plausible typo, missing the suffix — returned a
   product of marginals labelled with the caller's own string. A bound and an
   approximation are different claims about the same booking; nothing downstream could
   tell which one it had received.
3. **`GroupOutcome` validated nothing.** Any three numbers were accepted, in any relation
   to each other. `p_all_cnf=0.7` with `p_all_cnf_or_rac=0.6` was a constructible object,
   as was a group said to be 70% confirmed-or-RAC and 40% carrying at least one waitlist —
   figures that cannot both describe one booking.
4. **Absence was read as the least likely outcome.** Both methods wrote `po.p_cnf or 0.0`
   when reading marginals. `PassengerOutcome` refuses to construct a supported outcome
   with a missing probability, so this is defence in depth rather than a live bug — but a
   substituted zero is indistinguishable from an estimate, and the substitution was in the
   arithmetic rather than in the constructor that forbids the state.

The count tables had a related weakness: the independence branch convolved the marginals
once for `P(K = k)` and then recomputed `P(K >= k)` from the same marginal list, so the two
published tables could disagree by a rounding step. The comonotonic branch clamped its own
sorted differences with `max(0.0, ...)`, which hid an ordering error as a zero row.

## Decision

1. **Invalid input raises `ProbabilityError`, and nothing is clamped.**
   `ProbabilityError` subclasses both `RailConfirmError` and `ValueError`, so a caller that
   already handled malformed input keeps working, and one that did not still sees a
   failure. `_require_probability` refuses a `bool`, a non-number, a NaN, an infinity and
   anything outside `[0, 1]`, naming the passenger index so the message points at a row
   rather than at the algorithm.

2. **The method list is closed.** `GROUP_METHODS` names both implemented methods, and a
   name outside it raises instead of falling through. A caller asking for an unimplemented
   method gets a rejection, not an approximation under the requested name.

3. **A missing marginal is refused, not substituted.** `_marginal` reads the field and
   raises if it is `None`. The branch is unreachable from a validated `PassengerOutcome`,
   which is why it is cheap; it is present so the arithmetic cannot be the place where a
   number is invented.

4. **`GroupOutcome` checks its own invariants on construction**, whichever method produced
   it: all three joint figures or none; each a finite number in `[0, 1]`;
   `P(all CNF) <= P(all CNF or RAC)`; `P(all CNF or RAC) + P(at least one WL) <= 1`; and,
   when the count tables are published, `P(K = k)` keyed by every count from 0 to the group
   size, summing to one, with `P(K >= k)` its tail and `P(K >= n) = P(all CNF)`.

5. **An abstaining group carries no figure and no count table.** The constructor refuses
   both. An abstention is the absence of an answer, and a figure beside one reads as a
   computed result.

6. **The two count tables are derived from one another.** The independence branch sums the
   rounded `P(K = k)` values into `P(K >= k)`, and sets `p_all_cnf = p_exactly_k[n]`, so
   the published tables reconcile by construction rather than to within a tolerance. The
   comonotonic branch keeps its sorted differences and drops the `max(0.0, ...)`; the
   differences are non-negative because the list is sorted, and if they are not, the
   constructor now says so instead of printing a zero.

7. **Tolerance is named once.** `GROUP_DERIVED_TOLERANCE = 1e-5` covers the gap between two
   six-decimal tables. It is not a licence to accept a contradictory figure.

## Alternatives considered

- **Clamp and warn.** Rejected: the output of a clamped group figure is a number, so the
  warning is the only thing standing between a reader and a wrong probability. The
  directive that governs this build is to abstain rather than publish something
  unsupportable, and an exception is the same decision made earlier.
- **Validate in the engine instead of in the domain type.** Rejected: `GroupOutcome` is
  constructed by the group module, the API serialiser tests, the storage layer and the
  tests. A check in one caller leaves the others free to build a contradictory object; the
  type is where the invariant belongs.
- **Round the group figures to four decimals and stop publishing the count tables.**
  Rejected: the tables are the evidence that the group events come from one distribution
  rather than from independent multiplications, and ADR-0016's evaluation scores them.
- **Make `compute_group_outcomes` raise on an unknown method but keep the clamp**, on the
  grounds that a clamp never fails a request. Rejected for the reason above, and because
  the clamped case is the one where the caller most needs to know.

## Consequences

- `ProbabilityError` is a new public name in `railconfirm.domain.exceptions`. Nothing
  catches it specifically yet; existing `except ValueError` handlers continue to work.
- A malformed group input now fails the request instead of degrading the figure. In this
  build the only producer of group inputs is the engine, from validated passenger
  outcomes, so no served path changes behaviour; the API's own abstention path is
  unchanged.
- Tests that built `GroupOutcome` directly must publish a consistent pair of tables. The
  suite's existing helpers already did, which is evidence the constraint is natural rather
  than restrictive.
- The six-decimal summary remains. Nothing here improves precision; it makes the published
  precision self-consistent.
- Passing these tests says the arithmetic is internally consistent. It says nothing about
  whether either bound describes a real booking, which still requires labelled group
  outcomes from an approved dataset.

## Validation

`backend/tests/inference/test_group_invariants.py` covers each refusal by name and each
invariant by construction, including the two degenerate groups (`all certain`, `all
impossible`) for both methods, and the reconciliation of the two tables across five
marginal profiles. The pre-existing arithmetic tests in
`backend/tests/inference/test_group.py` continue to assert the published values for the two
reference bookings, unchanged by this decision. The full backend suite, Ruff and mypy were
run before the change was committed.

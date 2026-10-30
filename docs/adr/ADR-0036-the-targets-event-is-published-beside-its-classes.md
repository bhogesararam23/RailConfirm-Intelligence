# ADR-0036: The target's event is published beside its classes

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainers
- **Related:** ADR-0003 (prediction targets), ADR-0016 (group events), ADR-0022 (a calibration's identity is its target's event), ADR-0035 (a group figure is scored against the event its name gives)

## Context

The API asked for a target and then declined to answer it. A request with
`target: final_chart_cnf_or_rac` received, per passenger, the five-class distribution and a
`target_definition` that read:

> Probability of each final-chart outcome for each passenger (CNF = confirmed berth, RAC =
> Reservation Against Cancellation, …). These are mutually exclusive and exhaustive over the
> supported population.

That text describes the *distribution*, not the target, and it was identical for both
targets. So a report could name the merged question in `target` and caption it with the
confirmed question in `target_definition` — two fields, one report, two different claims.

The figure the user actually asked for was not published anywhere per passenger. For
`final_chart_cnf` it happens to equal `p_cnf`; for `final_chart_cnf_or_rac` it is
`p_cnf + p_rac`. The frontend made the gap visible: it rendered the class grid and then
told the reader "CNF and RAC … are not added together here", directly beneath a control
that had asked for exactly that sum.

This is the same class of defect ADR-0035 fixed in the evaluation: a figure whose name
promises one event and whose arithmetic measures another. There the duplicate was
`brier_all_cnf`; here it is the served answer to a merged-target request.

## Decision

1. **The domain owns the wording and the arithmetic.** `TARGET_DEFINITIONS` sits beside
   `EVENT_CLASSES_BY_TARGET` in `domain/prediction.py`, and every value names the event its
   own class tuple covers. `PassengerOutcome.probability_of(classes)` returns the sum of the
   named classes, or `None` when the outcome abstains.
2. **The API publishes the event per passenger** as `p_target_event`, computed on the served
   distribution from the target's own class tuple. It is `null` exactly when the passenger
   abstains — never `0`, for the reason `formatProbability` already encodes in the frontend.
3. **`target_definition` names the target's event.** It is no longer a description of the
   distribution; `outcome_classes` already carries that, and continues to.
4. **A client renders the served figure and does not re-derive it.** The frontend headlines
   `p_target_event` under a label drawn from `target`, keeps the five-class distribution
   beside it, and replaces its "not added together" sentence with wording that says what the
   target's event is and what the distribution shows.
5. **Stored reports are not recomputed.** The field defaults to `null`, so a payload written
   under the previous contract still validates and reopens byte-for-byte as it was served.
   A reopened old report shows the definition it was sent with and no event figure, rather
   than a number this build calculated afterwards.

## Alternatives considered

- **Let the frontend sum `p_cnf + p_rac`.** Rejected: that is a second implementation of the
  quantity the evaluation scores, and the two can drift through rounding or a later change
  in which classes a target covers. ADR-0022 made the same argument about calibration
  arithmetic — a served probability computed differently from the measured one is not the
  number the report measured.
- **Keep `target_definition` as a description of the distribution.** Rejected: the field is
  named for the target and is read as one. A description that is identical for two different
  questions is not a definition of either.
- **Rename the field to `outcome_classes_description` and add a separate definition.** That
  would be a breaking rename for no gain: the string was already meant to define the target,
  and `outcome_classes` already describes the class set.
- **Recompute `p_target_event` for old stored payloads on read.** Rejected: the reopen route
  exists to show what was said, and `docs/architecture/API_CONTRACT.md` states that nothing is
  recomputed. A derived number appearing on a report that never carried it would be exactly
  the silent reinterpretation the storage rules forbid.
- **Make the abstaining value `0.0` so charts and tables have a number.** Rejected: an absent
  estimate and a certain non-outcome are different claims, which is the rule the frontend has
  enforced since the zeroed-probability regression.

## Consequences

- The response has one more per-passenger field, and the two targets now produce different
  `target_definition` strings and different `p_target_event` values from the same served
  distribution. The OpenAPI schema, the contract document, the frontend types and the
  component fixtures move together; a test in `tests/api/test_contract.py` pins the field and
  a second test pins the merged target to `p_cnf + p_rac`.
- A caller reading only `p_cnf` under a merged target still sees the confirmed class, and the
  response now says plainly which figure answers the question asked.
- The group block keeps its own three figures (`p_all_cnf`, `p_all_cnf_or_rac`,
  `p_at_least_one_wl`). `p_target_event` is per passenger and does not replace them, and
  neither is derived from the other: a booking's joint probability is not a product or a sum
  of its passengers' event probabilities.
- Reports stored before this change reopen with `p_target_event: null`. That is a fact about
  when they were served, visible as an em dash, not a gap to backfill.

## Validation

- `tests/domain/test_prediction.py` — the event is the sum of its classes, the merged event
  is never narrower than confirmed, an abstention has no event probability, an unknown class
  name is refused rather than skipped, an event covering no class is refused rather than
  scored as zero, and every target publishes a definition naming its own event.
- `tests/api/test_contract.py` — the served definition differs between targets and names the
  event; an abstaining outcome publishes `p_target_event: null`; an injected artifact serves
  `p_target_event == p_cnf` for `final_chart_cnf` and `p_target_event == p_cnf + p_rac` for
  `final_chart_cnf_or_rac`; the OpenAPI schema documents the field.
- `frontend/src/components/__tests__/contract.test.tsx` — the card headlines the served
  figure under the target's own label, the merged target's copy no longer claims the classes
  are never combined, and a report without the field renders a dash.
- Full suite at the time of the change: 1088 backend tests, 118 frontend tests, Ruff, mypy
  (44 source files), the frontend type check, lint, production build and the
  repository-hygiene gate all green.

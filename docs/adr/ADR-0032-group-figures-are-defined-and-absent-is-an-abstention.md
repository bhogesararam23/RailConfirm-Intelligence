# ADR-0032: Every published group figure carries a definition, and a missing one is an abstention

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0016 (dependent group outcomes and group-event evaluation), ADR-0024 (group
  arithmetic refuses invalid input and checks its own figures), ADR-0019 (a segment below the
  row floor carries no claim), `backend/railconfirm/training/metrics.py`,
  `backend/railconfirm/training/report.py`

## Context

A scorecard carries a nested `GroupScorecard` whenever the partition has bookings with more
than one passenger. It publishes eight numbers: the independence-method Brier for "all in the
target event", "all CNF or RAC" and "at least one waitlisted"; the same three computed from
the comonotonic queue bound; a baseline; and a skill figure against that baseline.

Two things were wrong with it.

**Nothing defined those numbers.** `test_every_published_metric_is_defined_and_nothing_extra_is`
enforces that every field in `METRIC_KEYS` has a sentence in `METRIC_DEFINITIONS`, and a field
is excluded from `METRIC_KEYS` by being listed in `STRUCTURAL_FIELDS`. `group` is structural —
it describes *how many* groups were scored — so the whole nested block was exempt, and the
eight figures inside it were published with no definition at all. That is exactly the gap the
rule exists to prevent, moved one level down. It matters most for the three `queue_brier_*`
values: they are Brier scores of a **mathematical bound**, and the repository's operating rules
say a bound and an approximation must never be presented as the same claim or as validated
group behaviour. A reader had a column called `queue_brier_all_cnf` and no way to learn that it
is the comonotonic limit, not a forecast. `brier_all_cnf` had the same problem in a quieter
form: its label means "every passenger confirmed" for one target and "every passenger confirmed
or RAC" for the other, because it is built from the target's event classes.

**A missing figure was scored as a zero.** Each of the six probabilities was read as

```python
p_indep_cnf = indep.p_all_cnf if indep and indep.p_all_cnf is not None else 0.0
```

A group method returns no figure when the booking cannot be combined. Substituting `0.0` turns
"no probability" into "certainly did not happen", then computes a squared error against it and
averages that into the published Brier. ADR-0024 removed this exact substitution from the group
methods themselves — `_marginal` now raises rather than reading `p_cnf or 0.0` — and the same
pattern survived one layer up in the scoring path, where it is worse, because a wrong Brier
looks like a result.

## Decision

1. **The group figures are declared as metrics.** `GROUP_STRUCTURAL_FIELDS` names the five
   counting fields and `GROUP_METRIC_KEYS` is everything else in `GroupScorecard`, so the eight
   measurements are enumerable instead of implicit. The report's definition block now covers
   all eight, and `metric_definitions` is checked against `METRIC_KEYS | GROUP_METRIC_KEYS`.

2. **The definitions say what each number is and is not.** `queue_brier_*` states that the
   probability scored is the extreme joint arrangement the marginals allow, that a Brier score
   of a bound is not a Brier score of a calibrated probability, and that it is never an
   empirically validated claim about group behaviour. `brier_all_cnf` states that its label is
   the target's event classes and that the field name is exact only for `final_chart_cnf`.
   `baseline_brier_all_cnf` states that the exponent is the group's own size, so groups of
   different sizes are averaged against baselines that differ by construction.
   `brier_skill_all_cnf` states that it compares the independence approximation only, and says
   nothing about the bound reported beside it.

3. **A group without figures is an abstention.** Both methods are asked before anything is
   scored; if either comes back without a figure the group is counted in `abstained_groups` and
   contributes to no mean. The three published Brier figures then become `None` when no group
   could be scored, rather than `0.5`-shaped numbers computed from substituted zeros.

4. **The report's own coverage test applies to the nested block.** A test asserts that every
   `GroupScorecard` field is either structural or defined, in the same spirit as the existing
   top-level check, so a newly added group figure cannot be published without a sentence.

5. **No schema version changes.** No key was added, renamed or reinterpreted; the payload shape
   is identical and the definitions are a new block inside `metric_definitions`, which the
   report already declares to be free-form text keyed by metric name. Adding keys to that dict
   is the mechanism, not a breaking change to it.

## Alternatives considered

- **Leave the group block undefined because it is nested.** Rejected: nesting is a layout
  decision, not a statement that the numbers need no explanation. The exemption was an accident
  of how `STRUCTURAL_FIELDS` is written.
- **Rename `brier_all_cnf` to something target-neutral.** Rejected here: the field names are in
  published report bytes and in the report text, and a rename is a breaking change to every
  consumer for a clarity gain a definition achieves without one. The definition names the
  ambiguity instead. A rename belongs in a release that is already bumping the schema.
- **Keep the `0.0` substitution and document it.** Rejected: a documented zero is still a
  fabricated probability, and this one flows into a proper scoring rule. ADR-0024 settled this
  argument one layer down.
- **Raise when a figure is missing.** Rejected: an abstention is a legitimate outcome of the
  group arithmetic (ADR-0016), so a run in which one booking cannot be combined should report a
  coverage fact, not fail. Raising is reserved for invalid *input*, which is not what this is.
- **Drop the queue-bound scores entirely, since a bound is not a probability.** Rejected: they
  are the only published measure of how close real bookings came to the queue-clearing limit,
  and the report's job is to show that distance while labelling what it is. Removing them would
  hide the comparison rather than state its terms.

## Consequences

- Every number in the group block now has a definition in all three report shapes, because they
  share `METRIC_DEFINITIONS`.
- A run in which some bookings cannot be combined publishes fewer scored groups and states the
  abstentions, instead of publishing Brier values built partly from zeros. On the existing
  fixtures every booking combines, so their numbers are unchanged.
- `GROUP_METRIC_KEYS` is now an enforced contract: a new field on `GroupScorecard` fails the
  coverage test until it has a definition and a structural-or-metric decision.
- Nothing here is evidence about railway behaviour. The group figures come from synthetic
  fixtures and describe a smoothed table's arithmetic.

## Validation

`backend/tests/training/test_metrics.py` gained
`test_a_group_figure_that_is_absent_is_an_abstention_and_never_a_zero`, which monkeypatches
`compute_group_outcomes` to return an abstaining `GroupOutcome` and asserts the group is counted
in `abstained_groups`, that `scored_groups` stays zero, and that all three Brier figures are
`None` rather than the `1.0` a substituted zero produces. `backend/tests/training/test_report.py`
gained `test_a_group_figure_cannot_be_published_without_a_definition`, which asserts the field
partition covers `GroupScorecard` exactly, that every group metric key appears in
`metric_definitions`, and that the queue-bound definition says "mathematical bound". The existing
definition-coverage test now expects `METRIC_KEYS | GROUP_METRIC_KEYS`. The backend suite (1067
tests), Ruff, mypy and the repository hygiene script were run before this change was committed.

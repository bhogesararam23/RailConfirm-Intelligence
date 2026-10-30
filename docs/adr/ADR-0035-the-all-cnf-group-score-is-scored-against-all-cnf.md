# ADR-0035: The all-CNF group score is scored against all-CNF, whatever the run's target is

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0016 (dependent group outcomes and group-event evaluation), ADR-0022 (a
  contract definition lives in the domain), ADR-0032 (every published group figure carries a
  definition), `backend/railconfirm/training/metrics.py`,
  `backend/railconfirm/training/report.py`

## Context

`_group_scorecard` scored the group block with `event_classes`, the classes of the run's target:

```python
true_all_cnf = 1.0 if all(lbl in event_classes for lbl in labels) else 0.0
p_prev_event = _event_probability(prevalence, event_classes)
```

The probabilities it scores are not target-relative. `compute_group_outcomes` and
`compute_queue_dependent_bounds` answer fixed questions about a booking — every passenger
confirmed, every passenger confirmed or RAC, at least one waitlisted — and the block publishes
all three side by side on every run. So the label used for `brier_all_cnf` was the run's event,
while the probability scored against it was always `P(all CNF)`.

On the default target those are the same event and nothing showed. On `final_chart_cnf_or_rac`
the run's event is `{CNF, RAC}`, which is the label of the field printed next to it, and
`brier_all_cnf` became a copy of `brier_all_cnf_or_rac`. Measured on one two-passenger booking
labels `(CNF, RAC)` in one cohort (`p_cnf = 91/105`):

| figure | `final_chart_cnf` | `final_chart_cnf_or_rac` |
| --- | --- | --- |
| `brier_all_cnf` | 0.4096 | 0.1296 |
| `brier_all_cnf_or_rac` | 0.009506 | 0.009506 |
| `baseline_brier_all_cnf` | 0.0625 | 0.2601 |
| `brier_skill_all_cnf` | -5.5536 | 0.50173 |

The same booking therefore scored two different numbers under two names, and on the merged
target the pair was indistinguishable. The baseline moved too, because it raised the *merged*
event's prevalence (`0.7²`) where the figure it is compared against had been scored against the
all-CNF event. `brier_skill_all_cnf` then reported that the independence approximation beat the
base rate when the two had been measured on different events.

`brier_all_cnf_or_rac` was already hardcoded to `("CNF", "RAC")`, so only one field of the pair
followed the target — the pair was not even parameterised the same way.

ADR-0032 saw this and treated it as a naming problem: the definition stated that "the label the
field name suggests is only exact for the first target", and a rename was deferred. That was
incomplete. The number was not merely misnamed: it scored a `P(all CNF)` claim against a
different event, so it was wrong on the target where it differed from its name, and the
definition made the arithmetic look deliberate. Documentation does not repair a numerator
paired with the wrong outcome.

## Decision

1. **The group block's labels are fixed by the figure names.** `GROUP_ALL_CNF_EVENT` and
   `GROUP_CNF_OR_RAC_EVENT` are read from `EVENT_CLASSES_BY_TARGET` in the domain and used
   directly. `_group_scorecard` no longer takes `event_classes`, so the run's target cannot
   reach the group arithmetic by any route.

2. **The group baseline is the confirmed share raised to the booking's size.** It is
   `prevalence["CNF"] ** passengers`, scored against the same all-CNF label, because that is the
   reference the figure beside it is measured against.

3. **No field is renamed and no report schema version changes.** The names are now true, which
   is the cheaper way to fix a wrong name: under the default target every group figure is
   bit-identical to before, and under the merged target `brier_all_cnf` starts reporting the
   event it has always claimed. A rename would have broken published bytes and every consumer
   to label a figure that was still measuring the wrong thing.

4. **The definitions state the fixed event.** `brier_all_cnf` says the event does not follow the
   run's target and why, `queue_brier_all_cnf` says it scores the same all-CNF event from the
   bound, and `baseline_brier_all_cnf` names the confirmed share. The caveat ADR-0032 added is
   removed rather than left to contradict the code.

## Alternatives considered

- **Keep the target-relative label and rely on the definition (ADR-0032's position).** Rejected:
  a documented mismatch is still a wrong number, it published one value under two names, and it
  made the report's claim — that `brier_all_cnf_or_rac` sits beside `brier_all_cnf` so a reader
  can see how much of it is the merged event being easier — false, because they were the same
  number.
- **Rename the field to `brier_all_target_event`.** Rejected: the figure was never the target's
  event, so the rename would have blessed the mismatch and still broken the report bytes.
- **Make the whole block target-relative.** Rejected: the group methods answer fixed questions
  about a booking. The block describes bookings; it does not restate the run's headline.
- **Drop `brier_all_cnf` when the target is the merged one.** Rejected: the all-CNF outcome of a
  booking is well defined and measured on every run. Hiding a figure avoids a wrong label by
  removing a correct measurement.
- **Bump `COMPARISON_REPORT_SCHEMA_VERSION` / the evaluation schema.** Rejected: no key was
  added, removed or reinterpreted; one number was corrected, and a version bump would tell a
  reader the layout changed when what changed is that a figure no longer contradicts its name.

## Consequences

- Under `final_chart_cnf` nothing moves: the target's event classes were already `("CNF",)`.
- Under `final_chart_cnf_or_rac`, `brier_all_cnf`, `queue_brier_all_cnf`,
  `baseline_brier_all_cnf` and `brier_skill_all_cnf` change to the values their names describe.
  A report generated before this change under that target carries the old numbers and cannot be
  compared with a new one figure by figure.
- The invariance is now a property a test can assert: one booking, two targets, one group block
  for the fixed events.
- Nothing in serving, fitting, promotion or the API changed. The group block is evaluation
  output only, and every number in it still comes from synthetic fixtures.

## Validation

`backend/tests/training/test_metrics.py` gained
`test_the_all_cnf_group_score_is_scored_against_cnf_whatever_the_target_is`, which scores one
booking of `CNF` and `RAC/4` under both targets and asserts the hand-computed all-CNF error,
that the merged target's `brier_all_cnf` is larger than its `brier_all_cnf_or_rac`, that both
targets report the same `brier_all_cnf`, `queue_brier_all_cnf` and `baseline_brier_all_cnf`, and
that the baseline is the confirmed share squared. The file's `booking` helper builds the
multi-passenger frame the existing group tests did not have. The abstention test now calls
`_group_scorecard` without the removed parameter. The backend suite (**1079 passed**, 236.5 s),
Ruff, mypy (44 source files) and the repository hygiene script were run before this decision was
committed.
